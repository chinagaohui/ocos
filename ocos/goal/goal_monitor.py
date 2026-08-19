"""Phase 39.6: GoalMonitor — 目标健康状态评估器。

职责:
    - 读取 Goal 状态 + 进展数据
    - 评估健康状态 (ACTIVE/WARNING/STALLED/BLOCKED/COMPLETED/INACTIVE)
    - 产出 GoalHealthSnapshot

设计约束:
    - 纯函数模块，不 import GoalStore（接收 Goal 对象作为参数）
    - 不修改 Goal（只读）
    - 不创建 Goal（只评估）
    - 阈值可配置
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from .maintenance_types import GoalHealth, GoalHealthSnapshot, MaintenanceEvent


# ═══════════════════════════════════════════════════════════════════════════
# 配置
# ═══════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class GoalMonitorConfig:
    """目标监控配置。"""

    # 停滞判定阈值（tick 数）
    stall_ticks: int = 500
    # 警告阈值（tick 数，< stall_ticks）
    warning_ticks: int = 200
    # 注意力失焦阈值（tick 数）
    attention_age_threshold: int = 100
    # 最低进展分数（低于此值视为停滞）
    min_progress_score: float = 0.1

    def __post_init__(self) -> None:
        if self.warning_ticks >= self.stall_ticks:
            raise ValueError(
                f"warning_ticks ({self.warning_ticks}) must be < stall_ticks ({self.stall_ticks})"
            )


# ═══════════════════════════════════════════════════════════════════════════
# GoalMonitor
# ═══════════════════════════════════════════════════════════════════════════

class GoalMonitor:
    """目标健康评估器。

    为每个活跃 Goal 评估健康状态，产出 GoalHealthSnapshot。

    用法:
        monitor = GoalMonitor()
        snapshots = monitor.evaluate(goals, progress_data, attention_focus_history, current_tick)
        events = monitor.to_events(snapshots, current_tick)

    约束:
        ✅ 读取 Goal 状态 → 判定健康
        ✅ 产出 MaintenanceEvent → 输入 EventBus
        ❌ 不修改 Goal
        ❌ 不创建 Goal (create_goal)
        ❌ 不删除 Goal (delete_goal)
        ❌ 不改变 Goal 优先级
    """

    def __init__(self, config: GoalMonitorConfig | None = None) -> None:
        self._config = config or GoalMonitorConfig()

    def evaluate(
        self,
        goals: list[Any],
        progress_data: dict[str, float] | None = None,
        attention_focus_history: dict[str, int] | None = None,
        current_tick: int = 0,
    ) -> list[GoalHealthSnapshot]:
        """评估所有 Goal 的健康状态。

        Args:
            goals: Goal 对象列表 (kernel/goal_types.Goal)
            progress_data: {goal_id: progress_score} — 进展分数
            attention_focus_history: {goal_id: last_focus_tick} — 上次关注时间
            current_tick: 当前 tick ID

        Returns:
            GoalHealthSnapshot 列表
        """
        if progress_data is None:
            progress_data = {}
        if attention_focus_history is None:
            attention_focus_history = {}

        results: list[GoalHealthSnapshot] = []
        for goal in goals:
            health = self._evaluate_one(goal, progress_data, attention_focus_history, current_tick)
            if health is not None:
                results.append(health)
        return results

    def _evaluate_one(
        self,
        goal: Any,
        progress_data: dict[str, float],
        attention_focus_history: dict[str, int],
        current_tick: int,
    ) -> GoalHealthSnapshot | None:
        """评估单个 Goal 的健康状态。

        Returns:
            GoalHealthSnapshot 或 None（如果 Goal 不需要监控，如 COMPLETED/CANCELLED）
        """
        goal_id = getattr(goal, "goal_id", "")
        status = getattr(goal, "status", None)

        # 将 GoalStatus 转为字符串判断
        # 优先用 .name (GoalStatus.ACTIVE.name == "ACTIVE")
        if hasattr(status, "name"):
            status_lower = status.name.lower()
        elif hasattr(status, "value"):
            status_lower = str(status.value).lower()
        else:
            status_lower = str(status).lower()

        # 终态: 不需要监控
        if status_lower in ("completed", "cancelled", "failed", "abandoned"):
            return GoalHealthSnapshot(
                goal_id=goal_id,
                health=GoalHealth.COMPLETED if "complet" in status_lower else GoalHealth.INACTIVE,
                last_progress_tick=self._get_last_progress_tick(goal, current_tick),
                attention_age=self._get_attention_age(goal_id, attention_focus_history, current_tick),
                progress_score=progress_data.get(goal_id, 1.0),
            )

        # 未激活
        if status_lower == "pending":
            return GoalHealthSnapshot(
                goal_id=goal_id,
                health=GoalHealth.INACTIVE,
                last_progress_tick=current_tick,
                attention_age=0,
                progress_score=0.0,
            )

        # 活跃目标: ACTIVE
        progress = progress_data.get(goal_id, 0.0)
        last_progress_tick = self._get_last_progress_tick(goal, current_tick)
        attention_age = self._get_attention_age(goal_id, attention_focus_history, current_tick)
        idle_ticks = current_tick - last_progress_tick

        warnings: list[str] = []

        # 判定健康状态
        if idle_ticks >= self._config.stall_ticks:
            health = GoalHealth.STALLED
            warnings.append(f"Stalled: {idle_ticks} ticks without progress (threshold: {self._config.stall_ticks})")
        elif idle_ticks >= self._config.warning_ticks:
            health = GoalHealth.WARNING
            warnings.append(f"Slow progress: {idle_ticks} ticks without progress (threshold: {self._config.warning_ticks})")
        elif progress < self._config.min_progress_score:
            health = GoalHealth.WARNING
            warnings.append(f"Low progress: {progress:.2f} < {self._config.min_progress_score}")
        else:
            health = GoalHealth.ACTIVE

        # 注意力年龄大也标记为 WARNING（即使进展正常）
        if attention_age > self._config.attention_age_threshold and health == GoalHealth.ACTIVE:
            health = GoalHealth.WARNING
            warnings.append(f"Lost attention for {attention_age} ticks (threshold: {self._config.attention_age_threshold})")

        return GoalHealthSnapshot(
            goal_id=goal_id,
            health=health,
            last_progress_tick=last_progress_tick,
            attention_age=attention_age,
            progress_score=progress,
            warnings=tuple(warnings),
        )

    def to_events(
        self,
        snapshots: list[GoalHealthSnapshot],
        current_tick: int,
    ) -> list[MaintenanceEvent]:
        """将健康快照转换为维护事件。

        只有需要关注（needs_attention）的目标才会产生事件。
        正常 ACTIVE/COMPLETED/INACTIVE 目标不产生事件。
        """
        events: list[MaintenanceEvent] = []
        for snap in snapshots:
            if snap.health.needs_attention:
                events.append(
                    MaintenanceEvent(
                        goal_id=snap.goal_id,
                        health=snap.health,
                        severity=snap.health.severity,
                        tick_id=current_tick,
                        reason=f"{snap.health.value}: {snap.warnings[0] if snap.warnings else 'needs attention'}",
                        progress_tag=f"age={snap.attention_age}",
                    )
                )
        return events

    # ── 私有方法 ──────────────────────────────────────────────────────

    @staticmethod
    def _get_last_progress_tick(goal: Any, current_tick: int) -> int:
        """获取目标上一次有进展的时刻。"""
        metadata = getattr(goal, "metadata", {}) or {}
        if isinstance(metadata, dict):
            return metadata.get("last_progress_tick", current_tick)
        return current_tick

    @staticmethod
    def _get_attention_age(goal_id: str, attention_history: dict[str, int], current_tick: int) -> int:
        """计算目标有多久没被关注（ticks）。"""
        last_focus = attention_history.get(goal_id, 0)
        if last_focus == 0:
            return current_tick  # 从未被关注过
        return max(0, current_tick - last_focus)
