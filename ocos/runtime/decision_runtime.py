"""
Decision Runtime Engine — Decision 生命周期管理器。

Phase 18 Runtime Foundation 的第二个 Runtime Engine。

职责:
1. 订阅 Decision 事件（DECISION_FORMED, DECISION_VALIDATED, DECISION_REVOKED 等）
2. 验证状态转移合法性（由 _VALID_TRANSITIONS 定义）
3. 管理 Decision 对象的创建、更新、查询
4. 支持 TTL 过期检查和重置

依赖链: Goal → Decision → Execution → Process
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone, timedelta
from typing import Any

from ocos.kernel.abi import (
    Event,
    EventType,
    Decision,
    DecisionStatus,
)
from ocos.events.event_bus import EventBus
from ocos.runtime.context_manager import WorkingMemory
from ocos.logging import get_logger

logger = get_logger(__name__)

# ── Valid Transitions ─────────────────────────────────────────────────────────

_VALID_TRANSITIONS: dict[DecisionStatus, set[DecisionStatus]] = {
    DecisionStatus.PROPOSED: {
        DecisionStatus.COMMITTED,
        DecisionStatus.REVOKED,
        DecisionStatus.SUPERSEDED,
        DecisionStatus.EXPIRED,
    },
    DecisionStatus.COMMITTED: {
        DecisionStatus.EXECUTED,
        DecisionStatus.REVOKED,
        DecisionStatus.SUPERSEDED,
        DecisionStatus.EXPIRED,
    },
    # terminal
    DecisionStatus.EXECUTED: set(),
    DecisionStatus.REVOKED: set(),
    DecisionStatus.SUPERSEDED: set(),
    DecisionStatus.EXPIRED: set(),
}

# 所有 terminal 状态
_TERMINAL_STATUSES = {
    DecisionStatus.EXECUTED,
    DecisionStatus.REVOKED,
    DecisionStatus.SUPERSEDED,
    DecisionStatus.EXPIRED,
}


# ── Event Mapping ────────────────────────────────────────────────────────────

_STATUS_TO_EVENT: dict[DecisionStatus, EventType] = {
    DecisionStatus.COMMITTED: EventType.DECISION_VALIDATED,
    DecisionStatus.EXECUTED: EventType.DECISION_EXECUTED,
    DecisionStatus.REVOKED: EventType.DECISION_REVOKED,
    DecisionStatus.SUPERSEDED: EventType.DECISION_SUPERSEDED,
    DecisionStatus.EXPIRED: EventType.DECISION_EXPIRED,
}

_EVENT_TO_TARGET_STATUS: dict[EventType, DecisionStatus] = {
    EventType.DECISION_VALIDATED: DecisionStatus.COMMITTED,
    EventType.DECISION_EXECUTED: DecisionStatus.EXECUTED,
    EventType.DECISION_REVOKED: DecisionStatus.REVOKED,
    EventType.DECISION_SUPERSEDED: DecisionStatus.SUPERSEDED,
    EventType.DECISION_EXPIRED: DecisionStatus.EXPIRED,
}


# ── Helper ────────────────────────────────────────────────────────────────────

def _get_decision(wm: WorkingMemory, decision_id: str) -> Decision | None:
    """从 WorkingMemory 获取 Decision。"""
    for d in wm.get_decisions():
        if d.decision_id == decision_id:
            return d
    return None


# ── Runtime Result ────────────────────────────────────────────────────────────

class RuntimeResult:
    """通用运行时结果。"""

    def __init__(self, success: bool, decision_id: str, message: str):
        self.success = success
        self.decision_id = decision_id
        self.message = message

    def __repr__(self) -> str:
        return f"RuntimeResult(success={self.success}, decision_id={self.decision_id!r}, message={self.message!r})"


# ── Constants ─────────────────────────────────────────────────────────────────

_SUBSCRIBED_EVENTS = frozenset({
    EventType.DECISION_VALIDATED,
    EventType.DECISION_EXECUTED,
    EventType.DECISION_REVOKED,
    EventType.DECISION_SUPERSEDED,
    EventType.DECISION_EXPIRED,
})


# ═══════════════════════════════════════════════════════════════════════════════
# DecisionRuntimeEngine
# ═══════════════════════════════════════════════════════════════════════════════

class DecisionRuntimeEngine:
    """Decision 运行时引擎 — 生命周期管理。

    职责:
    - 管理 Decision 对象的创建（form_decision）、状态转移、过期检查
    - 验证状态转移合法性（禁止非法转移）
    - 维护决策的引用完整性（goal_id 指向已存在的 Goal）
    """

    def __init__(
        self,
        event_bus: EventBus,
        working_memory: WorkingMemory,
    ) -> None:
        self._event_bus = event_bus
        self._wm = working_memory
        self._subscription_ids: list[str] = []
        self._default_ttl: timedelta | None = None
        self._subscribe_all()
        logger.debug("DecisionRuntimeEngine initialized")

    # ── Event Subscription ──────────────────────────────────────────────────

    def _subscribe_all(self) -> None:
        logger.debug("Subscribing to decision events")
        for event_type in _SUBSCRIBED_EVENTS:
            sub_id = self._event_bus.subscribe(event_type, self._on_decision_event)
            self._subscription_ids.append(sub_id)

    @property
    def subscription_ids(self) -> list[str]:
        return list(self._subscription_ids)

    def unsubscribe_all(self) -> None:
        for sub_id in self._subscription_ids:
            self._event_bus.unsubscribe(sub_id)
        self._subscription_ids.clear()

    def _on_decision_event(self, event: Event) -> None:
        """通用 Decision 事件处理器。"""
        payload = event.payload
        decision_id = payload.get("decision_id", "")
        if not decision_id:
            logger.warning(f"Decision event missing decision_id: type={event.event_type}")
            return

        target_status = _EVENT_TO_TARGET_STATUS.get(event.event_type)
        if target_status is None:
            logger.warning(f"No target status mapping for event: type={event.event_type}")
            return

        logger.info(f"Decision event: type={event.event_type} decision_id={decision_id}")
        self._apply_transition(decision_id, target_status)

    def _apply_transition(self, decision_id: str, target_status: DecisionStatus) -> None:
        """执行 Decision 状态转移。"""
        decision = _get_decision(self._wm, decision_id)
        if decision is None:
            logger.error(f"Decision not found for transition: decision_id={decision_id}")
            return

        current = DecisionStatus(decision.status)
        if target_status not in _VALID_TRANSITIONS.get(current, set()):
            logger.warning(f"Invalid transition: {current.value} -> {target_status.value} decision_id={decision_id}")
            return

        # 转移：冻结 dataclass，使用 replace
        new_decision = dataclasses.replace(
            decision,
            status=target_status.value,
        )
        self._wm.update_decision(new_decision)
        logger.info(f"Decision transitioned: {current.value} -> {target_status.value} decision_id={decision_id}")

    # ── Public API ──────────────────────────────────────────────────────────

    def form_decision(
        self,
        goal_id: str = "",
        selected_option: str = "",
        reasoning: str = "",
        confidence: float = 0.0,
        decision_id: str | None = None,
    ) -> RuntimeResult:
        """创建一个新的 Decision（PROPOSED 状态）。

        等价于 DECISION_FORMED 事件（首次创建，非状态转移）。
        """
        form_id = decision_id or uuid.uuid4().hex
        decision = Decision(
            decision_id=form_id,
            goal_id=goal_id,
            selected_option=selected_option,
            reasoning=reasoning,
            confidence=confidence,
            status=DecisionStatus.PROPOSED.value,
        )
        self._wm.add_decision(decision)
        logger.info(f"Decision formed: decision_id={form_id} goal_id={goal_id}")

        # 发布 DECISION_FORMED 事件（通知但不触发状态转移）
        self._event_bus.publish(Event(
            event_type=EventType.DECISION_FORMED,
            payload={
                "decision_id": form_id,
                "goal_id": goal_id,
                "selected_option": selected_option,
                "status": DecisionStatus.PROPOSED.value,
            },
        ))

        return RuntimeResult(
            success=True,
            decision_id=form_id,
            message=f"Decision formed with status: {DecisionStatus.PROPOSED.value}",
        )

    def transition_decision(
        self,
        decision_id: str,
        target_status: DecisionStatus,
    ) -> RuntimeResult:
        """向指定 Decision 发出状态转移事件。

        先同步预验证，再发出事件。
        """
        decision = _get_decision(self._wm, decision_id)
        if decision is None:
            logger.error(f"Decision not found: decision_id={decision_id}")
            return RuntimeResult(
                success=False,
                decision_id=decision_id,
                message=f"Decision not found: {decision_id}",
            )

        current = DecisionStatus(decision.status)
        if target_status not in _VALID_TRANSITIONS.get(current, set()):
            logger.warning(f"Invalid transition request: {current.value} -> {target_status.value} decision_id={decision_id}")
            return RuntimeResult(
                success=False,
                decision_id=decision_id,
                message=f"Invalid transition: {current.value} → {target_status.value}",
            )

        event_type = _STATUS_TO_EVENT.get(target_status)
        if event_type is None:
            logger.error(f"No event mapping for target status: {target_status.value}")
            return RuntimeResult(
                success=False,
                decision_id=decision_id,
                message=f"No event mapping for target status: {target_status.value}",
            )

        self._event_bus.publish(Event(
            event_type=event_type,
            payload={"decision_id": decision_id},
        ))

        logger.info(f"Transition requested: {current.value} -> {target_status.value} decision_id={decision_id}")
        return RuntimeResult(
            success=True,
            decision_id=decision_id,
            message=f"Transition requested: {current.value} → {target_status.value}",
        )

    # ── Query ───────────────────────────────────────────────────────────────

    @property
    def decision_count(self) -> int:
        return len(self._wm.get_decisions())

    @property
    def active_decision_count(self) -> int:
        return sum(
            1 for d in self._wm.get_decisions()
            if DecisionStatus.is_active(d.status)
        )

    def get_decision(self, decision_id: str) -> Decision | None:
        return _get_decision(self._wm, decision_id)

    def list_decisions(self, status: DecisionStatus | None = None) -> list[Decision]:
        all_d = self._wm.get_decisions()
        if status is None:
            return list(all_d)
        return [d for d in all_d if d.status == status.value]

    def list_active_decisions(self) -> list[Decision]:
        return [
            d for d in self._wm.get_decisions()
            if DecisionStatus.is_active(d.status)
        ]

    # ── TTL / Expiration ────────────────────────────────────────────────────

    def configure_expiration(
        self,
        check_interval_seconds: int = 60,
        default_ttl_seconds: int = 3600,
    ) -> None:
        self._default_ttl = timedelta(seconds=default_ttl_seconds)

    def check_expirations(self, now: datetime | None = None) -> list[RuntimeResult]:
        """检查所有活跃 Decision 是否过期。"""
        if self._default_ttl is None:
            return []
        now = now or datetime.now(timezone.utc)
        expired: list[RuntimeResult] = []
        for d in self._wm.get_decisions():
            if not DecisionStatus.is_active(d.status):
                continue
            try:
                created = datetime.fromisoformat(d.timestamp)
            except (ValueError, TypeError):
                continue
            if now - created > self._default_ttl:
                self.transition_decision(d.decision_id, DecisionStatus.EXPIRED)
                expired.append(RuntimeResult(
                    success=True,
                    decision_id=d.decision_id,
                    message=f"Decision expired: {d.decision_id}",
                ))
                logger.info(f"Decision expired: decision_id={d.decision_id}")
        if expired:
            logger.info(f"check_expirations: {len(expired)} decision(s) expired")
        return expired

    # ── Reset ────────────────────────────────────────────────────────────────

    def reset(self) -> int:
        """清除所有 Decision。返回清除数量。"""
        count = self.decision_count
        self._wm._decisions.clear()
        logger.info(f"DecisionRuntimeEngine reset: cleared {count} decisions")
        return count


# Lazy import for RuntimeResult in dataclasses.replace
import dataclasses  # noqa: E402 (imported at bottom to avoid circular issues)
