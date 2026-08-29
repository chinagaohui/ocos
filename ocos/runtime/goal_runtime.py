"""
Goal Runtime Engine — Goal 生命周期管理器。

Phase 18 Runtime Foundation 的第一个 Runtime Engine。

职责:
1. 订阅 Goal 事件（GOAL_SET, GOAL_UPDATED, GOAL_COMPLETED, etc.）
2. 验证状态转移合法性（委托 GoalStatus.can_transition_to）
3. 自动推进 Goal 生命周期（如 GOAL_SET → CREATED → ACTIVE）
4. 周期性过期检查（Expiration）
5. 处理 Superseding（新 Goal 覆盖旧 Goal 并记录）
6. 事件审计追踪

依赖: EventBus, ContextManager（Working Memory 存储 Goal）
"""

from __future__ import annotations

import dataclasses
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from ocos.kernel.abi import Event, EventType, Goal
from ocos.events.event_bus import EventBus
from ocos.models.goal import GoalStatus
from ocos.runtime.context_manager import WorkingMemory
from ocos.logging import get_logger


logger = get_logger(__name__)


# ── Event Payload Builders ─────────────────────────────────────

def _make_event(
    event_type: EventType,
    goal_id: str,
    extra: dict[str, Any] | None = None,
) -> Event:
    """构建 Goal 事件。"""
    payload: dict[str, Any] = {"goal_id": goal_id}
    if extra:
        payload.update(extra)
    return Event(
        event_id=uuid.uuid4().hex,
        event_type=event_type,
        source="goal_runtime",
        payload=payload,
    )


# ── Runtime Result ─────────────────────────────────────────────

@dataclass(frozen=True)
class RuntimeResult:
    """Runtime 操作的结果。"""
    success: bool
    goal_id: str
    message: str = ""
    schema_version: str = "1.0"


# ── Helper: 从 ContextManager 获取单个 Goal ───────────────────

def _get_goal(wm: WorkingMemory, goal_id: str) -> Goal | None:
    """从 Working Memory 的 Goal 列表中查找单个 Goal。"""
    for g in wm.get_goals(status=None):
        if g.goal_id == goal_id:
            return g
    return None


# ── GoalRuntimeEngine ──────────────────────────────────────────

class GoalRuntimeEngine:
    """Goal 运行时引擎 — 事件驱动的生命周期管理器。

    工作流:
        Event Bus → GoalRuntimeEngine → ContextManager（存储）
                   → 事件验证 → 状态推进 → 新事件发出
    """

    def __init__(
        self,
        event_bus: EventBus,
        working_memory: WorkingMemory,
    ):
        self._event_bus = event_bus
        self._wm = working_memory
        self._subscription_ids: list[str] = []

        # 过期检查配置
        self._expiration_check_interval: timedelta = timedelta(hours=1)
        self._default_goal_ttl: timedelta | None = None  # None = 永不自动过期

        # 已注册订阅
        self._subscribe_all()
        logger.debug("GoalRuntimeEngine initialized",
                      component="goal_runtime",
                      subscription_count=len(self._subscription_ids))

    # ── 属性 ─────────────────────────────────────────────

    @property
    def active_goal_count(self) -> int:
        return self._wm.active_goal_count

    @property
    def goal_count(self) -> int:
        return self._wm.goal_count

    @property
    def subscription_ids(self) -> list[str]:
        return list(self._subscription_ids)

    # ── 配置 ─────────────────────────────────────────────

    def configure_expiration(
        self,
        check_interval_seconds: float = 3600,
        default_ttl_seconds: float | None = None,
    ) -> None:
        """配置过期检查参数。"""
        self._expiration_check_interval = timedelta(seconds=check_interval_seconds)
        if default_ttl_seconds is not None:
            self._default_goal_ttl = timedelta(seconds=default_ttl_seconds)
        logger.info("Expiration configured",
                     component="goal_runtime",
                     check_interval=check_interval_seconds,
                     default_ttl=default_ttl_seconds)

    # ── 订阅管理 ─────────────────────────────────────────

    def _subscribe_all(self) -> None:
        """订阅所有 Goal 相关事件。"""
        goal_events = [
            EventType.GOAL_SET,
            EventType.GOAL_UPDATED,
            EventType.GOAL_COMPLETED,
            EventType.GOAL_PAUSED,
            EventType.GOAL_RESUMED,
            EventType.GOAL_FAILED,
            EventType.GOAL_CANCELLED,
            EventType.GOAL_SUPERSEDED,
            EventType.GOAL_EXPIRED,
        ]
        for et in goal_events:
            try:
                sid = self._event_bus.subscribe(
                    et, self._on_goal_event,
                    subscriber_id=f"goal_runtime-{et.value}",
                )
                self._subscription_ids.append(sid)
            except Exception:
                logger.warning(
                    "GoalRuntime: 订阅事件 %s 失败（事件类型可能未注册）",
                    et.value,
                )

    def unsubscribe_all(self) -> None:
        """取消所有订阅。"""
        count = len(self._subscription_ids)
        for sid in self._subscription_ids:
            self._event_bus.unsubscribe(sid)
        self._subscription_ids.clear()
        logger.info("Unsubscribed from all goal events",
                     component="goal_runtime", count=count)

    # ── 事件处理 ─────────────────────────────────────────

    def _on_goal_event(self, event: Event) -> None:
        """处理 Goal 事件（主入口）。"""
        goal_id = event.payload.get("goal_id", "")
        if not goal_id:
            return

        if event.event_type == EventType.GOAL_SET:
            self._handle_goal_set(event)
        elif event.event_type == EventType.GOAL_UPDATED:
            self._handle_goal_updated(event)
        elif event.event_type == EventType.GOAL_COMPLETED:
            self._handle_state_transition(
                goal_id, GoalStatus.COMPLETED, "completed",
            )
        elif event.event_type == EventType.GOAL_PAUSED:
            self._handle_state_transition(
                goal_id, GoalStatus.PAUSED, "paused",
            )
        elif event.event_type == EventType.GOAL_RESUMED:
            self._handle_state_transition(
                goal_id, GoalStatus.ACTIVE, "resumed",
            )
        elif event.event_type == EventType.GOAL_FAILED:
            self._handle_state_transition(
                goal_id, GoalStatus.FAILED, "failed",
            )
        elif event.event_type == EventType.GOAL_CANCELLED:
            self._handle_state_transition(
                goal_id, GoalStatus.CANCELLED, "cancelled",
            )
        elif event.event_type == EventType.GOAL_SUPERSEDED:
            self._handle_superseded(event)
        elif event.event_type == EventType.GOAL_EXPIRED:
            self._handle_state_transition(
                goal_id, GoalStatus.EXPIRED, "expired",
            )

    # ── 事件处理逻辑 ─────────────────────────────────────

    def _handle_goal_set(self, event: Event) -> None:
        """处理 Goal 设定事件。"""
        goal_id = event.payload.get("goal_id", "")
        description = event.payload.get("description", "")
        priority = event.payload.get("priority", 1)
        source = event.payload.get("source", "system")
        parent_goal_id = event.payload.get("parent_goal_id", "")
        success_criterion = event.payload.get("success_criterion", "")

        # 构造 Goal 对象（CREATED 状态）
        goal = Goal(
            goal_id=goal_id,
            description=description,
            priority=int(priority),
            status=GoalStatus.CREATED.value,
            source=source,
            parent_goal_id=parent_goal_id or "",
            success_criterion=success_criterion or "",
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
        self._wm.add_goal(goal)

        # 自动推进到 ACTIVE
        self._handle_state_transition(goal_id, GoalStatus.ACTIVE, "activated")

    def _handle_goal_updated(self, event: Event) -> None:
        """处理 Goal 更新事件。"""
        goal_id = event.payload.get("goal_id", "")
        goal = _get_goal(self._wm, goal_id)
        if goal is None:
            return

        # 仅允许更新 ACTIVE/PAUSED 状态的 Goal
        current = GoalStatus(goal.status)
        if current not in (GoalStatus.ACTIVE, GoalStatus.PAUSED):
            return

        # 更新可修改字段
        new_description = event.payload.get("description")
        new_priority = event.payload.get("priority")
        new_success_criterion = event.payload.get("success_criterion")

        updates: dict[str, Any] = {}
        if new_description:
            updates["description"] = str(new_description)
        if new_priority is not None:
            updates["priority"] = int(new_priority)
        if new_success_criterion:
            updates["success_criterion"] = str(new_success_criterion)
        # source 在设定后不可修改（Theory Invariant）

        if updates:
            updated = dataclasses.replace(goal, **updates)
            self._wm.add_goal(updated)

    def _handle_state_transition(
        self,
        goal_id: str,
        target: GoalStatus,
        reason: str,
    ) -> RuntimeResult:
        """通用状态转移处理。

        验证转移合法性后，更新 ContextManager 中的 Goal 状态。
        """
        goal = _get_goal(self._wm, goal_id)
        if goal is None:
            return RuntimeResult(
                success=False,
                goal_id=goal_id,
                message=f"Goal not found: {goal_id}",
            )

        current = GoalStatus(goal.status)
        if not current.can_transition_to(target):
            return RuntimeResult(
                success=False,
                goal_id=goal_id,
                message=f"Invalid transition: {current.value} → {target.value}",
            )

        self._wm.update_goal_status(goal_id, target.value)

        return RuntimeResult(
            success=True,
            goal_id=goal_id,
            message=f"Transitioned: {current.value} → {target.value} ({reason})",
        )

    def _handle_superseded(self, event: Event) -> None:
        """处理 Superseding（新 Goal 覆盖旧 Goal）。"""
        goal_id = event.payload.get("goal_id", "")
        superseder_id = event.payload.get("superseder_goal_id", "")

        if not superseder_id:
            return

        # Superseded 的 Goal 必须是 ACTIVE 或 PAUSED
        goal = _get_goal(self._wm, goal_id)
        if goal is None:
            return

        current = GoalStatus(goal.status)
        if current not in (GoalStatus.ACTIVE, GoalStatus.PAUSED):
            return

        # 先进状态转移
        self._handle_state_transition(
            goal_id, GoalStatus.SUPERSEDED,
            f"superseded_by_{superseder_id}",
        )

        # 确保 superseder 是 ACTIVE
        superseder = _get_goal(self._wm, superseder_id)
        if superseder and GoalStatus(superseder.status) == GoalStatus.CREATED:
            self._handle_state_transition(
                superseder_id, GoalStatus.ACTIVE,
                "auto_activated_by_superseding",
            )

    # ── 过期检查 ─────────────────────────────────────────

    def check_expirations(self) -> list[RuntimeResult]:
        """检查所有 Goal 的过期状态。

        Returns:
            已执行 EXPIRED 转移的结果列表。
        """
        if self._default_goal_ttl is None:
            return []

        now = datetime.now(timezone.utc)
        expired_results: list[RuntimeResult] = []

        all_goals = self._wm.get_goals(status=None)
        for goal in all_goals:
            current = GoalStatus(goal.status)
            if current not in (GoalStatus.ACTIVE, GoalStatus.PAUSED, GoalStatus.CREATED):
                continue

            # 解析创建时间
            try:
                created = datetime.fromisoformat(goal.timestamp)
            except (ValueError, TypeError):
                continue

            if now - created > self._default_goal_ttl:
                result = self._handle_state_transition(
                    goal.goal_id, GoalStatus.EXPIRED, "auto_expired",
                )
                if result.success:
                    expired_results.append(result)

        logger.info("Expiration check completed",
                     component="goal_runtime",
                     expired_count=len(expired_results))
        return expired_results

    # ── 生命周期管理 ─────────────────────────────────────

    def set_goal(
        self,
        description: str,
        priority: int = 1,
        source: str = "system",
        parent_goal_id: str = "",
        success_criterion: str = "",
        goal_id: str | None = None,
    ) -> RuntimeResult:
        """创建并设定一个新 Goal。

        发出 GOAL_SET 事件 → 引擎自动推进到 ACTIVE。
        """
        gid = goal_id or uuid.uuid4().hex
        event = _make_event(
            EventType.GOAL_SET,
            gid,
            extra={
                "description": description,
                "priority": priority,
                "source": source,
                "parent_goal_id": parent_goal_id,
                "success_criterion": success_criterion,
            },
        )
        self._event_bus.publish(event)
        logger.info("Goal set",
                     component="goal_runtime",
                     goal_id=gid,
                     description=description,
                     priority=priority,
                     source=source)
        return RuntimeResult(success=True, goal_id=gid, message=f"Goal set: {gid}")

    def transition_goal(
        self,
        goal_id: str,
        target_status: GoalStatus,
    ) -> RuntimeResult:
        """向指定 Goal 发出状态转移事件。

        先验证转移合法性（同步验证），再发出事件。
        发出对应事件类型 → 引擎处理状态推进。
        """
        # 同步预验证
        goal = _get_goal(self._wm, goal_id)
        if goal is None:
            return RuntimeResult(
                success=False,
                goal_id=goal_id,
                message=f"Goal not found: {goal_id}",
            )

        current = GoalStatus(goal.status)
        if not current.can_transition_to(target_status):
            return RuntimeResult(
                success=False,
                goal_id=goal_id,
                message=f"Invalid transition: {current.value} → {target_status.value}",
            )

        status_to_event = {
            GoalStatus.COMPLETED: EventType.GOAL_COMPLETED,
            GoalStatus.FAILED: EventType.GOAL_FAILED,
            GoalStatus.CANCELLED: EventType.GOAL_CANCELLED,
            GoalStatus.PAUSED: EventType.GOAL_PAUSED,
            GoalStatus.EXPIRED: EventType.GOAL_EXPIRED,
            GoalStatus.SUPERSEDED: EventType.GOAL_SUPERSEDED,
        }
        event_type = status_to_event.get(target_status)
        if event_type is None:
            return RuntimeResult(
                success=False,
                goal_id=goal_id,
                message=f"Unsupported direct transition: {target_status.value}",
            )

        event = _make_event(event_type, goal_id)
        self._event_bus.publish(event)
        logger.info("Goal transition requested",
                     component="goal_runtime",
                     goal_id=goal_id,
                     target_status=target_status.value,
                     source_status=current.value)
        return RuntimeResult(
            success=True,
            goal_id=goal_id,
            message=f"Transition requested: → {target_status.value}",
        )

    def get_goal(self, goal_id: str) -> Goal | None:
        """查询 Goal 状态。"""
        return _get_goal(self._wm, goal_id)

    def list_active_goals(self) -> list[Goal]:
        """列出所有 ACTIVE 状态的 Goal。"""
        return self._wm.get_goals(status=GoalStatus.ACTIVE.value)

    def list_goals(self, status: str | None = None) -> list[Goal]:
        """按状态列出 Goal。status=None 返回全部。"""
        return self._wm.get_goals(status=status)

    # ── 清理 ─────────────────────────────────────────────

    def reset(self) -> None:
        """重置引擎状态（保留订阅）。"""
        self._wm.clear()
        logger.info("GoalRuntimeEngine reset",
                     component="goal_runtime")
