"""
Execution Runtime Engine — Execution 生命周期管理器。

Phase 18 Runtime Foundation 的第三个 Runtime Engine。

职责:
1. 订阅 Execution 事件（EXECUTION_STARTED, EXECUTION_COMPLETED 等）
2. 验证状态转移合法性（委托 ExecutionStatus.can_transition_to）
3. 管理 Execution 对象的创建、更新、查询
4. 支持超时检查和重置

依赖链: Goal → Decision → Execution → Process
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone, timedelta
from typing import Any

from ocos.kernel.abi import Event, EventType
from ocos.events.event_bus import EventBus
from ocos.models.execution import Execution, ExecutionStatus
from ocos.runtime.context_manager import WorkingMemory
from ocos.logging import get_logger

logger = get_logger(__name__)


# ── Valid Transitions ─────────────────────────────────────────────────────────
# 委托 ExecutionStatus.can_transition_to（已定义在 models/execution.py）

_TERMINAL_STATUSES = {
    ExecutionStatus.SUCCEEDED,
    ExecutionStatus.FAILED,
    ExecutionStatus.INTERRUPTED,
    ExecutionStatus.CANCELLED,
}


# ── Event Mapping ────────────────────────────────────────────────────────────

_STATUS_TO_EVENT: dict[ExecutionStatus, EventType] = {
    ExecutionStatus.RUNNING: EventType.EXECUTION_STARTED,
    ExecutionStatus.SUCCEEDED: EventType.EXECUTION_COMPLETED,
    ExecutionStatus.FAILED: EventType.EXECUTION_FAILED,
    ExecutionStatus.INTERRUPTED: EventType.EXECUTION_INTERRUPTED,
    ExecutionStatus.CANCELLED: EventType.EXECUTION_CANCELLED,
}

_EVENT_TO_TARGET_STATUS: dict[EventType, ExecutionStatus] = {
    EventType.EXECUTION_STARTED: ExecutionStatus.RUNNING,
    EventType.EXECUTION_COMPLETED: ExecutionStatus.SUCCEEDED,
    EventType.EXECUTION_FAILED: ExecutionStatus.FAILED,
    EventType.EXECUTION_INTERRUPTED: ExecutionStatus.INTERRUPTED,
    EventType.EXECUTION_CANCELLED: ExecutionStatus.CANCELLED,
}


# ── Helper ────────────────────────────────────────────────────────────────────

def _get_execution(wm: WorkingMemory, execution_id: str) -> Execution | None:
    for e in wm.get_executions():
        if e.execution_id == execution_id:
            return e
    return None


# ── Runtime Result ────────────────────────────────────────────────────────────

class RuntimeResult:
    def __init__(self, success: bool, execution_id: str, message: str):
        self.success = success
        self.execution_id = execution_id
        self.message = message

    def __repr__(self) -> str:
        return f"RuntimeResult(success={self.success}, execution_id={self.execution_id!r}, message={self.message!r})"


# ── Constants ─────────────────────────────────────────────────────────────────

_SUBSCRIBED_EVENTS = frozenset({
    EventType.EXECUTION_STARTED,
    EventType.EXECUTION_COMPLETED,
    EventType.EXECUTION_FAILED,
    EventType.EXECUTION_INTERRUPTED,
    EventType.EXECUTION_CANCELLED,
})


# ═══════════════════════════════════════════════════════════════════════════════
# ExecutionRuntimeEngine
# ═══════════════════════════════════════════════════════════════════════════════

class ExecutionRuntimeEngine:
    """Execution 运行时引擎 — 生命周期管理。"""

    def __init__(
        self,
        event_bus: EventBus,
        working_memory: WorkingMemory,
    ) -> None:
        self._event_bus = event_bus
        self._wm = working_memory
        self._subscription_ids: list[str] = []
        self._default_timeout: timedelta | None = None
        self._subscribe_all()
        logger.debug("ExecutionRuntimeEngine initialized")

    # ── Event Subscription ──────────────────────────────────────────────────

    def _subscribe_all(self) -> None:
        logger.debug("Subscribing to execution events")
        for event_type in _SUBSCRIBED_EVENTS:
            sub_id = self._event_bus.subscribe(event_type, self._on_execution_event)
            self._subscription_ids.append(sub_id)

    @property
    def subscription_ids(self) -> list[str]:
        return list(self._subscription_ids)

    def unsubscribe_all(self) -> None:
        for sub_id in self._subscription_ids:
            self._event_bus.unsubscribe(sub_id)
        self._subscription_ids.clear()

    def _on_execution_event(self, event: Event) -> None:
        """通用 Execution 事件处理器。"""
        payload = event.payload
        execution_id = payload.get("execution_id", "")
        if not execution_id:
            logger.warning(f"Execution event missing execution_id: type={event.event_type}")
            return
        target_status = _EVENT_TO_TARGET_STATUS.get(event.event_type)
        if target_status is None:
            logger.warning(f"No target status mapping for event: type={event.event_type}")
            return
        logger.info(f"Execution event: type={event.event_type} execution_id={execution_id}")
        self._apply_transition(execution_id, target_status, payload)

    def _apply_transition(self, execution_id: str, target_status: ExecutionStatus, payload: dict | None = None) -> None:
        """执行 Execution 状态转移。"""
        execution = _get_execution(self._wm, execution_id)
        if execution is None:
            logger.error(f"Execution not found for transition: execution_id={execution_id}")
            return
        current = ExecutionStatus(execution.status)
        if not current.can_transition_to(target_status):
            logger.warning(f"Invalid transition: {current.value} -> {target_status.value} execution_id={execution_id}")
            return

        import dataclasses
        updates: dict[str, Any] = {"status": target_status.value}
        if target_status in _TERMINAL_STATUSES:
            updates["completed_at"] = datetime.now(timezone.utc).isoformat()
        new_execution = dataclasses.replace(execution, **updates)
        self._wm.update_execution(new_execution)
        logger.info(f"Execution transitioned: {current.value} -> {target_status.value} execution_id={execution_id}")

    # ── Public API ──────────────────────────────────────────────────────────

    def schedule_execution(
        self,
        decision_id: str = "",
        action_ids: tuple[str, ...] | None = None,
        execution_id: str | None = None,
    ) -> RuntimeResult:
        """创建新的 Execution（PENDING 状态）。"""
        eid = execution_id or uuid.uuid4().hex
        execution = Execution(
            execution_id=eid,
            decision_id=decision_id,
            status=ExecutionStatus.PENDING,
            action_ids=action_ids or (),
        )
        self._wm.add_execution(execution)
        logger.info(f"Execution scheduled: execution_id={eid} decision_id={decision_id}")
        # 初始创建不发布事件（避免触发订阅器自循环）
        return RuntimeResult(
            success=True,
            execution_id=eid,
            message=f"Execution scheduled: {ExecutionStatus.PENDING.value}",
        )

    def start_execution(self, execution_id: str) -> RuntimeResult:
        """将 PENDING Execution 推进到 RUNNING。"""
        logger.info(f"Starting execution: execution_id={execution_id}")
        return self.transition_execution(execution_id, ExecutionStatus.RUNNING)

    def transition_execution(
        self,
        execution_id: str,
        target_status: ExecutionStatus,
    ) -> RuntimeResult:
        """向指定 Execution 发出状态转移事件。"""
        execution = _get_execution(self._wm, execution_id)
        if execution is None:
            logger.error(f"Execution not found: execution_id={execution_id}")
            return RuntimeResult(
                success=False,
                execution_id=execution_id,
                message=f"Execution not found: {execution_id}",
            )
        current = ExecutionStatus(execution.status)
        if not current.can_transition_to(target_status):
            logger.warning(f"Invalid transition request: {current.value} -> {target_status.value} execution_id={execution_id}")
            return RuntimeResult(
                success=False,
                execution_id=execution_id,
                message=f"Invalid transition: {current.value} → {target_status.value}",
            )
        event_type = _STATUS_TO_EVENT.get(target_status)
        if event_type is None:
            logger.error(f"No event mapping for target: {target_status.value}")
            return RuntimeResult(
                success=False,
                execution_id=execution_id,
                message=f"No event mapping for target: {target_status.value}",
            )
        self._event_bus.publish(Event(
            event_type=event_type,
            payload={
                "execution_id": execution_id,
                "status": target_status.value,
            },
        ))
        logger.info(f"Transition requested: {current.value} -> {target_status.value} execution_id={execution_id}")
        return RuntimeResult(
            success=True,
            execution_id=execution_id,
            message=f"Transition requested: {current.value} → {target_status.value}",
        )

    # ── Query ───────────────────────────────────────────────────────────────

    @property
    def execution_count(self) -> int:
        return len(self._wm.get_executions())

    @property
    def active_execution_count(self) -> int:
        return sum(1 for e in self._wm.get_executions() if e.status not in _TERMINAL_STATUSES)

    def get_execution(self, execution_id: str) -> Execution | None:
        return _get_execution(self._wm, execution_id)

    def list_executions(self, status: ExecutionStatus | None = None) -> list[Execution]:
        all_e = self._wm.get_executions()
        if status is None:
            return list(all_e)
        return [e for e in all_e if e.status == status.value]

    # ── Timeout Check ───────────────────────────────────────────────────────

    def configure_timeout(
        self,
        check_interval_seconds: int = 60,
        default_timeout_seconds: int = 3600,
    ) -> None:
        self._default_timeout = timedelta(seconds=default_timeout_seconds)

    def check_timeouts(self, now: datetime | None = None) -> list[RuntimeResult]:
        """检查 RUNNING 的 Execution 是否超时（超时视为 FAILED）。"""
        if self._default_timeout is None:
            return []
        now = now or datetime.now(timezone.utc)
        timed_out: list[RuntimeResult] = []
        for e in self._wm.get_executions():
            if e.status != ExecutionStatus.RUNNING.value:
                continue
            try:
                started = datetime.fromisoformat(e.started_at)
            except (ValueError, TypeError):
                continue
            if now - started > self._default_timeout:
                self.transition_execution(e.execution_id, ExecutionStatus.FAILED)
                timed_out.append(RuntimeResult(
                    success=True,
                    execution_id=e.execution_id,
                    message=f"Execution timed out: {e.execution_id}",
                ))
                logger.info(f"Execution timed out: execution_id={e.execution_id}")
        if timed_out:
            logger.info(f"check_timeouts: {len(timed_out)} execution(s) timed out")
        return timed_out

    # ── Reset ────────────────────────────────────────────────────────────────

    def reset(self) -> int:
        count = self.execution_count
        self._wm._executions.clear()
        logger.info(f"ExecutionRuntimeEngine reset: cleared {count} executions")
        return count
