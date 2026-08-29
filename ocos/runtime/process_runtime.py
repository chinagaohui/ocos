"""
Process Runtime Engine — TransformProcess 生命周期管理器。

Phase 18 Runtime Foundation 的第四个 Runtime Engine。

职责:
1. 订阅 Process 事件（PROCESS_CREATED, PROCESS_STARTED, PROCESS_COMPLETED, PROCESS_FAILED）
2. 验证状态转移合法性（CREATED → RUNNING → COMPLETED/FAILED）
3. 管理 TransformProcess 对象的创建、更新、查询

依赖链: Goal → Decision → Execution → Process
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone, timedelta
from typing import Any

from ocos.kernel.abi import Event, EventType
from ocos.events.event_bus import EventBus
from ocos.models.process import TransformProcess, ProcessState, ProcessType, ProcessStep
from ocos.runtime.context_manager import WorkingMemory
from ocos.logging import get_logger

logger = get_logger(__name__)


# ── Valid Transitions ─────────────────────────────────────────────────────────

_VALID_TRANSITIONS: dict[ProcessState, set[ProcessState]] = {
    ProcessState.CREATED: {ProcessState.RUNNING},
    ProcessState.RUNNING: {ProcessState.COMPLETED, ProcessState.FAILED},
    ProcessState.COMPLETED: set(),  # terminal
    ProcessState.FAILED: set(),      # terminal
}

_TERMINAL_STATUSES = {ProcessState.COMPLETED, ProcessState.FAILED}


# ── Event Mapping ────────────────────────────────────────────────────────────

_STATUS_TO_EVENT: dict[ProcessState, EventType] = {
    ProcessState.RUNNING: EventType.PROCESS_STARTED,
    ProcessState.COMPLETED: EventType.PROCESS_COMPLETED,
    ProcessState.FAILED: EventType.PROCESS_FAILED,
}

_EVENT_TO_TARGET_STATUS: dict[EventType, ProcessState] = {
    EventType.PROCESS_STARTED: ProcessState.RUNNING,
    EventType.PROCESS_COMPLETED: ProcessState.COMPLETED,
    EventType.PROCESS_FAILED: ProcessState.FAILED,
}


# ── Helper ────────────────────────────────────────────────────────────────────

def _get_process(wm: WorkingMemory, process_id: str) -> TransformProcess | None:
    for p in wm.get_processes():
        if p.process_id == process_id:
            return p
    return None


# ── Runtime Result ────────────────────────────────────────────────────────────

class RuntimeResult:
    def __init__(self, success: bool, process_id: str, message: str):
        self.success = success
        self.process_id = process_id
        self.message = message

    def __repr__(self) -> str:
        return f"RuntimeResult(success={self.success}, process_id={self.process_id!r}, message={self.message!r})"


# ── Constants ─────────────────────────────────────────────────────────────────

_SUBSCRIBED_EVENTS = frozenset({
    EventType.PROCESS_STARTED,
    EventType.PROCESS_COMPLETED,
    EventType.PROCESS_FAILED,
})


# ═══════════════════════════════════════════════════════════════════════════════
# ProcessRuntimeEngine
# ═══════════════════════════════════════════════════════════════════════════════

class ProcessRuntimeEngine:
    """Process 运行时引擎 — TransformProcess 生命周期管理。"""

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
        logger.debug("ProcessRuntimeEngine initialized")

    # ── Event Subscription ──────────────────────────────────────────────────

    def _subscribe_all(self) -> None:
        logger.debug("Subscribing to process events")
        for event_type in _SUBSCRIBED_EVENTS:
            sub_id = self._event_bus.subscribe(event_type, self._on_process_event)
            self._subscription_ids.append(sub_id)

    @property
    def subscription_ids(self) -> list[str]:
        return list(self._subscription_ids)

    def unsubscribe_all(self) -> None:
        for sub_id in self._subscription_ids:
            self._event_bus.unsubscribe(sub_id)
        self._subscription_ids.clear()

    def _on_process_event(self, event: Event) -> None:
        """通用 Process 事件处理器。"""
        payload = event.payload
        process_id = payload.get("process_id", "")
        if not process_id:
            logger.warning(f"Process event missing process_id: type={event.event_type}")
            return
        target_status = _EVENT_TO_TARGET_STATUS.get(event.event_type)
        if target_status is None:
            logger.warning(f"No target status mapping for event: type={event.event_type}")
            return
        logger.info(f"Process event: type={event.event_type} process_id={process_id}")
        self._apply_transition(process_id, target_status)

    def _apply_transition(self, process_id: str, target_status: ProcessState) -> None:
        """执行 Process 状态转移。"""
        process = _get_process(self._wm, process_id)
        if process is None:
            logger.error(f"Process not found for transition: process_id={process_id}")
            return
        current = ProcessState(process.process_state)
        if target_status not in _VALID_TRANSITIONS.get(current, set()):
            logger.warning(f"Invalid transition: {current.value} -> {target_status.value} process_id={process_id}")
            return
        import dataclasses
        new_process = dataclasses.replace(process, process_state=target_status)
        self._wm.update_process(new_process)
        logger.info(f"Process transitioned: {current.value} -> {target_status.value} process_id={process_id}")

    # ── Public API ──────────────────────────────────────────────────────────

    def create_process(
        self,
        process_type: ProcessType = ProcessType.REASONING,
        input_addresses: tuple | None = None,
        output_addresses: tuple | None = None,
        steps: tuple[ProcessStep, ...] | None = None,
        confidence: float = 0.0,
        metadata: dict[str, Any] | None = None,
        process_id: str | None = None,
    ) -> RuntimeResult:
        """创建新的 TransformProcess（CREATED 状态）。

        发布 PROCESS_CREATED 事件（通知而非状态转移）。
        """
        pid = process_id or uuid.uuid4().hex
        process = TransformProcess(
            process_id=pid,
            process_type=process_type,
            process_state=ProcessState.CREATED,
            input_addresses=input_addresses or (),
            output_addresses=output_addresses or (),
            steps=steps or (),
            confidence=confidence,
            metadata=metadata or {},
        )
        self._wm.add_process(process)
        logger.info(f"Process created: process_id={pid} process_type={process_type.value}")
        self._event_bus.publish(Event(
            event_type=EventType.PROCESS_CREATED,
            payload={
                "process_id": pid,
                "process_type": process_type.value,
                "process_state": ProcessState.CREATED.value,
            },
        ))
        return RuntimeResult(
            success=True,
            process_id=pid,
            message=f"Process created: {ProcessState.CREATED.value}",
        )

    def start_process(self, process_id: str) -> RuntimeResult:
        """将 CREATED Process 推进到 RUNNING。"""
        logger.info(f"Starting process: process_id={process_id}")
        return self.transition_process(process_id, ProcessState.RUNNING)

    def complete_process(self, process_id: str) -> RuntimeResult:
        """将 RUNNING Process 推进到 COMPLETED。"""
        logger.info(f"Completing process: process_id={process_id}")
        return self.transition_process(process_id, ProcessState.COMPLETED)

    def transition_process(
        self,
        process_id: str,
        target_status: ProcessState,
    ) -> RuntimeResult:
        """向指定 Process 发出状态转移事件。"""
        process = _get_process(self._wm, process_id)
        if process is None:
            logger.error(f"Process not found: process_id={process_id}")
            return RuntimeResult(
                success=False,
                process_id=process_id,
                message=f"Process not found: {process_id}",
            )
        current = ProcessState(process.process_state)
        if target_status not in _VALID_TRANSITIONS.get(current, set()):
            logger.warning(f"Invalid transition request: {current.value} -> {target_status.value} process_id={process_id}")
            return RuntimeResult(
                success=False,
                process_id=process_id,
                message=f"Invalid transition: {current.value} → {target_status.value}",
            )
        event_type = _STATUS_TO_EVENT.get(target_status)
        if event_type is None:
            logger.error(f"No event mapping for target: {target_status.value}")
            return RuntimeResult(
                success=False,
                process_id=process_id,
                message=f"No event mapping for target: {target_status.value}",
            )
        self._event_bus.publish(Event(
            event_type=event_type,
            payload={
                "process_id": process_id,
                "process_state": target_status.value,
            },
        ))
        logger.info(f"Transition requested: {current.value} -> {target_status.value} process_id={process_id}")
        return RuntimeResult(
            success=True,
            process_id=process_id,
            message=f"Transition requested: {current.value} → {target_status.value}",
        )

    # ── Query ───────────────────────────────────────────────────────────────

    @property
    def process_count(self) -> int:
        return len(self._wm.get_processes())

    @property
    def active_process_count(self) -> int:
        return sum(
            1 for p in self._wm.get_processes()
            if p.process_state not in _TERMINAL_STATUSES
        )

    def get_process(self, process_id: str) -> TransformProcess | None:
        return _get_process(self._wm, process_id)

    def list_processes(self, state: ProcessState | None = None) -> list[TransformProcess]:
        all_p = self._wm.get_processes()
        if state is None:
            return list(all_p)
        return [p for p in all_p if p.process_state == state.value]

    # ── Reset ────────────────────────────────────────────────────────────────

    def reset(self) -> int:
        count = self.process_count
        self._wm._processes.clear()
        logger.info(f"ProcessRuntimeEngine reset: cleared {count} processes")
        return count
