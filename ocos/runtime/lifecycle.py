"""Phase 39.1: Lifecycle Manager — Runtime 生命周期控制。

管理状态转换: BOOT → RUNNING → CHECKPOINT → SHUTDOWN。

约束 (Phase 38):
    - SIGTERM → create checkpoint → graceful shutdown
    - 状态转换必须在 ALLOWED_TRANSITIONS 内
"""

from __future__ import annotations

from .runtime_state import RuntimeState, ALLOWED_TRANSITIONS


class InvalidTransitionError(Exception):
    """无效的状态转换。"""


class LifecycleManager:
    """Runtime 生命周期管理器。

    职责:
        - 维护当前状态
        - 强制状态转换约束
        - 处理 shutdown 信号
    """

    def __init__(self, initial_state: RuntimeState = RuntimeState.BOOTING):
        self._state = initial_state
        self._shutdown_requested = False

    @property
    def state(self) -> RuntimeState:
        return self._state

    @property
    def shutdown_requested(self) -> bool:
        return self._shutdown_requested

    def transition(self, target: RuntimeState) -> RuntimeState:
        """执行状态转换。

        Raises:
            InvalidTransitionError: 转换不在 ALLOWED_TRANSITIONS 中。
        """
        allowed = ALLOWED_TRANSITIONS.get(self._state, set())
        if target not in allowed:
            raise InvalidTransitionError(
                f"Cannot transition from {self._state.value} to {target.value}. "
                f"Allowed: {[s.value for s in allowed]}"
            )
        self._state = target
        if target == RuntimeState.SHUTDOWN:
            self._shutdown_requested = True
        return self._state

    def request_shutdown(self):
        """请求正常关机。"""
        self._shutdown_requested = True

    def boot(self) -> RuntimeState:
        """BOOTING → RUNNING。"""
        return self.transition(RuntimeState.RUNNING)

    def shutdown(self) -> RuntimeState:
        """→ SHUTDOWN。"""
        return self.transition(RuntimeState.SHUTDOWN)

    def enter_safe_mode(self) -> RuntimeState:
        """进入 SAFE MODE。"""
        return self.transition(RuntimeState.SAFE_MODE)

    def enter_degraded(self) -> RuntimeState:
        """进入 DEGRADED。"""
        return self.transition(RuntimeState.DEGRADED)

    def recover(self) -> RuntimeState:
        """DEGRADED → RUNNING 恢复。"""
        return self.transition(RuntimeState.RUNNING)
