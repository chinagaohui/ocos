"""Goal Manager — 自主目标管理（Phase L）

Freeze Phase L: 整合 Homeostasis 内生驱力 → Goal 生成、持久化、追踪。

职责：
  - 从 HomeostasisMonitor 的 regulate() 结果中提取 SELF 级目标
  - 通过 GoalOriginEnforcer 门控后写入 GoalStore
  - 维护活跃目标列表与生命周期追踪
  - 提供查询接口供 MasterAgent 决策使用

设计约束：
  - 纯函数式接口（输入输出明确，无隐式状态）
  - 不替代 GoalStore（不直接写 DB，委托给 store）
  - 不替代 HomeostasisMonitor（读取其输出，不替换其检查）
  - 所有目标生成必须经过 enforcer 门控
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Protocol

from ocos.goal.store import GoalStore
from ocos.goal.enforcer import GoalOriginEnforcer, ConstitutionResult
from ocos.kernel.goal_types import (
    Goal,
    GoalOriginLevel,
    GoalAuthority,
    GoalStatus,
    GoalLevel,
)

logger = logging.getLogger(__name__)


# ── Protocols ─────────────────────────────────────────────────────────────────


class GoalManagerProtocol(Protocol):
    """GoalManager 对外协议——供 MasterAgent 注入使用。"""

    def get_active_self_goals(self, limit: int = 5) -> list[dict]: ...
    def get_generated_goals(self) -> list[dict]: ...
    def sync_from_homeostasis(
        self,
        regulate_result: Any,
        gate: Any = None,
    ) -> dict: ...
    def mark_progress(self, goal_id: str, progress: float) -> bool: ...
    def mark_completed(self, goal_id: str) -> bool: ...
    def is_goal_active(self, goal_id: str) -> bool: ...


# ── Data structures ────────────────────────────────────────────────────────────


@dataclass
class GeneratedGoal:
    """一次同步周期内生成的目标记录。"""

    goal_id: str
    description: str
    origin_level: str
    priority: float
    drive_type: str
    generated_at: str
    gated: bool = False
    reason: str = ""


@dataclass
class GoalSyncResult:
    """sync_from_homeostasis() 返回结果。"""

    generated: list[GeneratedGoal] = field(default_factory=list)
    gated: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    total_generated: int = 0
    total_saved: int = 0


# ── GoalManager ────────────────────────────────────────────────────────────────


class GoalManager:
    """自主目标管理器。

    用法：
        mgr = GoalManager(
            store=GoalStore(db_path="/tmp/test.db"),
            enforcer=GoalOriginEnforcer(current_phase=25),
        )
        result = mgr.sync_from_homeostasis(regulate_result)
        active = mgr.get_active_self_goals()
    """

    def __init__(
        self,
        store: GoalStore,
        enforcer: GoalOriginEnforcer | None = None,
        current_phase: int = 25,
    ) -> None:
        self._store = store
        self._enforcer = enforcer or GoalOriginEnforcer(current_phase=current_phase)
        self._generated: list[GeneratedGoal] = []

    # ── sync ───────────────────────────────────────────────────────────────

    def sync_from_homeostasis(
        self,
        regulate_result: Any,
        gate: Any = None,
    ) -> GoalSyncResult:
        """从 HomeostasisMonitor.regulate() 结果中同步内生目标。

        参数：
            regulate_result: RegulateResult 对象，含 drives/goals/actions/gated
            gate: 额外门控回调（可选），接收 Goal 返回 bool

        返回：
            GoalSyncResult（generated/gated/errors/计数）
        """
        if regulate_result is None:
            return GoalSyncResult()

        result = GoalSyncResult()
        now = datetime.now(timezone.utc).isoformat()

        # 从 regulate_result 中提取内生目标
        # RegulateResult 结构：goals=list[Goal], gated=list[str]
        self_goals = getattr(regulate_result, "goals", []) or []
        already_gated = getattr(regulate_result, "gated", []) or []

        for raw_goal in self_goals:
            try:
                goal_id = self._make_id(raw_goal)

                # 构造存入库用的字典
                goal_dict = {
                    "id": goal_id,
                    "level": self._get_level(raw_goal),
                    "status": GoalStatus.PENDING.value,
                    "description": self._get_desc(raw_goal),
                    "priority": self._get_priority(raw_goal),
                    "parent_id": "",
                    "source": "homeostasis",
                    "source_id": goal_id,
                    "deadline": "",
                    "metadata": self._build_metadata(raw_goal),
                    "origin_level": GoalOriginLevel.SELF.value,
                    "authority": GoalAuthority.AUTONOMOUS.value,
                }

                # 创建 Goal 对象用于门控
                goal_obj = Goal(
                    level=goal_dict["level"],
                    description=goal_dict["description"],
                    priority=goal_dict["priority"],
                    created_at=datetime.now(timezone.utc),
                    status=GoalStatus.PENDING,
                    origin_level=GoalOriginLevel.SELF,
                    authority=GoalAuthority.AUTONOMOUS,
                    metadata=goal_dict["metadata"],
                )

                # 双重门控：enforcer + 外部 gate
                enforced = self._enforcer.verify_creation(goal_obj)
                if not enforced.allowed:
                    result.gated.append(f"enforcer: {enforced.violations[0]}")
                    result.generated.append(GeneratedGoal(
                        goal_id=goal_id,
                        description=goal_dict["description"],
                        origin_level="SELF",
                        priority=goal_dict["priority"],
                        drive_type=self._get_drive(raw_goal),
                        generated_at=now,
                        gated=True,
                        reason=str(enforced.violations),
                    ))
                    continue

                extra_gate = gate
                if extra_gate is not None:
                    try:
                        if not extra_gate(goal_obj):
                            result.gated.append(f"gate: {goal_dict['description']}")
                            result.generated.append(GeneratedGoal(
                                goal_id=goal_id,
                                description=goal_dict["description"],
                                origin_level="SELF",
                                priority=goal_dict["priority"],
                                drive_type=self._get_drive(raw_goal),
                                generated_at=now,
                                gated=True,
                                reason="external gate",
                            ))
                            continue
                    except Exception as e:
                        result.errors.append(f"gate error: {e}")
                        continue

                # 写入 store
                try:
                    self._store.save(**goal_dict)
                    result.total_saved += 1
                    result.generated.append(GeneratedGoal(
                        goal_id=goal_id,
                        description=goal_dict["description"],
                        origin_level="SELF",
                        priority=goal_dict["priority"],
                        drive_type=self._get_drive(raw_goal),
                        generated_at=now,
                        gated=False,
                    ))
                except Exception as e:
                    result.errors.append(f"save error for {goal_id}: {e}")

            except Exception as e:
                result.errors.append(f"process error: {e}")

        # 合并已有 gated 列表
        result.gated.extend(str(g) for g in already_gated if g)
        result.total_generated = len([g for g in result.generated if not g.gated])
        self._generated = result.generated
        return result

    # ── query ──────────────────────────────────────────────────────────────

    def get_active_self_goals(self, limit: int = 5) -> list[dict]:
        """返回活跃的 SELF 级目标列表（从 store 加载）。"""
        try:
            rows = self._store.load_active()
        except Exception as e:
            logger.warning("Failed to load active goals: %s", e)
            return []
        self_goals = [
            r for r in rows
            if r.get("origin_level") == GoalOriginLevel.SELF.value
        ]
        return self_goals[:limit]

    def get_generated_goals(self) -> list[dict]:
        """返回本次同步生成的目标记录。"""
        return [
            {
                "goal_id": g.goal_id,
                "description": g.description,
                "gated": g.gated,
                "drive_type": g.drive_type,
                "generated_at": g.generated_at,
            }
            for g in self._generated
        ]

    def is_goal_active(self, goal_id: str) -> bool:
        """检查目标是否仍活跃。"""
        try:
            row = self._store.load(goal_id)
            if row is None:
                return False
            return row.get("status") not in (
                GoalStatus.COMPLETED.value,
                GoalStatus.CANCELLED.value,
                GoalStatus.FAILED.value,
            )
        except Exception:
            return False

    # ── update ─────────────────────────────────────────────────────────────

    def mark_progress(self, goal_id: str, progress: float) -> bool:
        """更新目标进度。"""
        try:
            return self._store.update_progress(goal_id, progress)
        except Exception as e:
            logger.warning("Failed to update progress for %s: %s", goal_id, e)
            return False

    def mark_completed(self, goal_id: str) -> bool:
        """标记目标完成。"""
        try:
            return self._store.mark_completed(goal_id)
        except Exception as e:
            logger.warning("Failed to mark completed %s: %s", goal_id, e)
            return False

    # ── internal helpers ───────────────────────────────────────────────────

    @staticmethod
    def _make_id(raw_goal: Any) -> str:
        import hashlib
        desc = getattr(raw_goal, "description", "") or ""
        drive = getattr(raw_goal, "metadata", {}) or {}
        drive_type = drive.get("drive", "UNKNOWN")
        key = f"{desc[:50]}|{drive_type}|{datetime.now(timezone.utc).isoformat()}"
        return hashlib.sha256(key.encode()).hexdigest()[:16]

    @staticmethod
    def _get_level(raw_goal: Any) -> str:
        level = getattr(raw_goal, "level", None)
        if level is None:
            return GoalLevel.SHORT.value
        return level.value if hasattr(level, "value") else str(level)

    @staticmethod
    def _get_desc(raw_goal: Any) -> str:
        return getattr(raw_goal, "description", "未知目标")

    @staticmethod
    def _get_priority(raw_goal: Any) -> float:
        meta = getattr(raw_goal, "metadata", {}) or {}
        intensity = meta.get("intensity", 0.5)
        try:
            return min(0.9, max(0.1, float(intensity)))
        except (TypeError, ValueError):
            return 0.5

    @staticmethod
    def _get_drive(raw_goal: Any) -> str:
        meta = getattr(raw_goal, "metadata", {}) or {}
        return meta.get("drive", "UNKNOWN")

    @staticmethod
    def _build_metadata(raw_goal: Any) -> dict:
        meta = getattr(raw_goal, "metadata", {}) or {}
        return {
            "drive": meta.get("drive", "UNKNOWN"),
            "intensity": meta.get("intensity", 0.5),
            "auto_generated": True,
        }


def create_goal_manager(
    db_path: str = "/tmp/ocos_goal_manager.db",
    current_phase: int = 25,
) -> GoalManager:
    """工厂函数：创建 GoalManager 实例（测试友好）。"""
    store = GoalStore(db_path=db_path)
    enforcer = GoalOriginEnforcer(current_phase=current_phase)
    return GoalManager(store=store, enforcer=enforcer, current_phase=current_phase)
