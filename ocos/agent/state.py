"""AgentState — Agent 状态机。

状态转换：
  INIT → BOOT → IDLE → THINKING → ACTING → WAITING → IDLE → SLEEP → DREAM → IDLE
  error → ERROR → RECOVER → IDLE
"""

from __future__ import annotations

from enum import Enum, auto


class AgentStatus(Enum):
    """Agent 运行状态。"""
    INIT = auto()
    BOOTING = auto()
    IDLE = auto()
    THINKING = auto()
    DECIDING = auto()
    ACTING = auto()
    WAITING = auto()
    REFLECTING = auto()
    LEARNING = auto()
    SLEEP = auto()
    DREAM = auto()
    ERROR = auto()
    RECOVERING = auto()
    SHUTDOWN = auto()


class AgentState:
    """Agent 状态机。

    管理 Agent 的状态转换和生命周期。
    """

    VALID_TRANSITIONS: dict[AgentStatus, set[AgentStatus]] = {
        AgentStatus.INIT: {AgentStatus.BOOTING},
        AgentStatus.BOOTING: {AgentStatus.IDLE, AgentStatus.ERROR},
        AgentStatus.IDLE: {
            AgentStatus.THINKING, AgentStatus.SLEEP, AgentStatus.SHUTDOWN,
        },
        AgentStatus.THINKING: {AgentStatus.DECIDING, AgentStatus.ERROR, AgentStatus.IDLE},
        AgentStatus.DECIDING: {AgentStatus.ACTING, AgentStatus.ERROR, AgentStatus.IDLE},
        AgentStatus.ACTING: {AgentStatus.WAITING, AgentStatus.REFLECTING, AgentStatus.ERROR},
        AgentStatus.WAITING: {AgentStatus.ACTING, AgentStatus.IDLE, AgentStatus.ERROR},
        AgentStatus.REFLECTING: {AgentStatus.LEARNING, AgentStatus.ERROR, AgentStatus.IDLE},
        AgentStatus.LEARNING: {AgentStatus.IDLE, AgentStatus.ERROR},
        AgentStatus.SLEEP: {AgentStatus.DREAM, AgentStatus.IDLE, AgentStatus.ERROR},
        AgentStatus.DREAM: {AgentStatus.IDLE, AgentStatus.ERROR},
        AgentStatus.ERROR: {AgentStatus.RECOVERING, AgentStatus.SHUTDOWN},
        AgentStatus.RECOVERING: {AgentStatus.IDLE, AgentStatus.ERROR},
        AgentStatus.SHUTDOWN: set(),
    }

    def __init__(self) -> None:
        self._status: AgentStatus = AgentStatus.INIT
        self._previous: AgentStatus | None = None

    @property
    def status(self) -> AgentStatus:
        return self._status

    @property
    def previous(self) -> AgentStatus | None:
        return self._previous

    def transition(self, target: AgentStatus) -> None:
        """尝试转换到目标状态。"""
        allowed = self.VALID_TRANSITIONS.get(self._status, set())
        if target not in allowed:
            raise ValueError(
                f"Cannot transition from {self._status.name} to {target.name}"
            )
        self._previous = self._status
        self._status = target

    def is_active(self) -> bool:
        """Agent 是否在活跃状态（非 SLEEP / DREAM / SHUTDOWN）。"""
        return self._status not in (
            AgentStatus.SLEEP, AgentStatus.DREAM, AgentStatus.SHUTDOWN, AgentStatus.INIT,
        )

    def reset(self) -> None:
        """重置到初始状态。"""
        self._status = AgentStatus.INIT
        self._previous = None

    def __repr__(self) -> str:
        prev = f" (was {self._previous.name})" if self._previous else ""
        return f"<AgentState: {self._status.name}{prev}>"
