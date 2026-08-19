"""AgentLifecycle — 线程安全的生命周期管理器。

Phase 22: Subject Emergence

宏观生命周期 (Macro Cycle):
  BOOTING → ACTIVE → SLEEPING → DREAMING → ACTIVE → ... → SHUTDOWN

微观循环 (Micro Cycle, within ACTIVE):
  OBSERVING → THINKING → DECIDING → ACTING → REFLECTING → LEARNING → OBSERVING

设计约束:
  - threading.RLock 保证线程安全
  - 严格遵循 _VALID_TRANSITIONS 矩阵
  - 宏观阶段和微观状态独立管理
  - 不替换 AgentState，作为上层包装
"""

from __future__ import annotations

import threading
from enum import Enum, auto
from typing import Callable, Optional

from ocos.agent.state import AgentState, AgentStatus


class LifecyclePhase(Enum):
    """宏观生命周期阶段。"""
    BOOTING = auto()       # 启动中
    ACTIVE = auto()        # 活跃（微循环运行中）
    SLEEPING = auto()      # 休眠
    DREAMING = auto()      # 梦境
    SHUTDOWN = auto()      # 关闭
    ERROR = auto()         # 异常


class MicroState(Enum):
    """微观循环状态（仅在 ACTIVE 阶段内）。"""
    IDLE = auto()
    OBSERVING = auto()
    THINKING = auto()
    DECIDING = auto()
    ACTING = auto()
    REFLECTING = auto()
    LEARNING = auto()


class LifecycleManager:
    """线程安全的生命周期管理器。

    管理两层状态:
      1. 宏观阶段 (LifecyclePhase) — 与 AgentStatus 映射
      2. 微观状态 (MicroState) — ACTIVE 阶段内的微循环

    用法:
        lm = LifecycleManager()
        lm.transition_to_phase(LifecyclePhase.ACTIVE)
        lm.transition_micro(MicroState.OBSERVING)
    """

    # 宏观阶段 → AgentStatus 映射
    PHASE_TO_STATUS: dict[LifecyclePhase, AgentStatus] = {
        LifecyclePhase.BOOTING: AgentStatus.BOOTING,
        LifecyclePhase.ACTIVE: AgentStatus.IDLE,
        LifecyclePhase.SLEEPING: AgentStatus.SLEEP,
        LifecyclePhase.DREAMING: AgentStatus.DREAM,
        LifecyclePhase.SHUTDOWN: AgentStatus.SHUTDOWN,
        LifecyclePhase.ERROR: AgentStatus.ERROR,
    }

    # Macro Phase 有效转换
    _VALID_PHASE_TRANSITIONS: dict[LifecyclePhase, set[LifecyclePhase]] = {
        LifecyclePhase.BOOTING: {LifecyclePhase.ACTIVE, LifecyclePhase.ERROR,
                                 LifecyclePhase.SHUTDOWN},
        LifecyclePhase.ACTIVE: {LifecyclePhase.SLEEPING, LifecyclePhase.ERROR,
                                LifecyclePhase.SHUTDOWN},
        LifecyclePhase.SLEEPING: {LifecyclePhase.DREAMING, LifecyclePhase.ACTIVE,
                                  LifecyclePhase.ERROR, LifecyclePhase.SHUTDOWN},
        LifecyclePhase.DREAMING: {LifecyclePhase.ACTIVE, LifecyclePhase.ERROR,
                                  LifecyclePhase.SHUTDOWN},
        LifecyclePhase.ERROR: {LifecyclePhase.ACTIVE, LifecyclePhase.SHUTDOWN},
        LifecyclePhase.SHUTDOWN: set(),
    }

    # Micro State 有效转换（仅在 ACTIVE 阶段内）
    _VALID_MICRO_TRANSITIONS: dict[MicroState, set[MicroState]] = {
        MicroState.IDLE: {MicroState.OBSERVING},
        MicroState.OBSERVING: {MicroState.THINKING, MicroState.IDLE},
        MicroState.THINKING: {MicroState.DECIDING, MicroState.IDLE},
        MicroState.DECIDING: {MicroState.ACTING, MicroState.IDLE},
        MicroState.ACTING: {MicroState.REFLECTING, MicroState.IDLE},
        MicroState.REFLECTING: {MicroState.LEARNING, MicroState.IDLE},
        MicroState.LEARNING: {MicroState.IDLE, MicroState.OBSERVING},
    }

    def __init__(
        self,
        agent_state: Optional[AgentState] = None,
        on_phase_change: Optional[Callable[[LifecyclePhase, LifecyclePhase], None]] = None,
    ) -> None:
        self._agent_state = agent_state or AgentState()
        self._lock = threading.RLock()
        self._phase: LifecyclePhase = LifecyclePhase.BOOTING
        self._micro_state: MicroState = MicroState.IDLE
        self._on_phase_change = on_phase_change

    # ── 属性 ────────────────────────────────────────────────────────

    @property
    def phase(self) -> LifecyclePhase:
        return self._phase

    @property
    def micro_state(self) -> MicroState:
        return self._micro_state

    @property
    def agent_status(self) -> AgentStatus:
        return self._agent_state.status

    @property
    def lock(self) -> threading.RLock:
        """公开锁供 ControlLoop 使用。"""
        return self._lock

    # ── 宏观阶段转换 ────────────────────────────────────────────────

    def transition_to_phase(self, target: LifecyclePhase) -> None:
        """转换宏观生命周期阶段。

        自动同步 AgentState.status。

        Raises:
            ValueError: 非法转换
        """
        with self._lock:
            allowed = self._VALID_PHASE_TRANSITIONS.get(self._phase, set())
            if target not in allowed:
                raise ValueError(
                    f"Cannot transition lifecycle phase "
                    f"from {self._phase.name} to {target.name}"
                )
            old = self._phase
            self._phase = target

            # 同步 AgentState
            agent_target = self.PHASE_TO_STATUS.get(target)
            if agent_target is not None and agent_target != self._agent_state.status:
                try:
                    self._agent_state.transition(agent_target)
                except ValueError:
                    pass  # AgentState may already be in the right state

            if self._on_phase_change:
                self._on_phase_change(old, target)

    # ── 微观状态转换 ────────────────────────────────────────────────

    def transition_micro(self, target: MicroState) -> None:
        """转换微观循环状态。

        仅当 phase == ACTIVE 时有效。

        Raises:
            ValueError: 不在 ACTIVE 阶段或非法转换
        """
        with self._lock:
            if self._phase != LifecyclePhase.ACTIVE:
                raise ValueError(
                    f"Micro transitions only allowed in ACTIVE phase, "
                    f"current phase: {self._phase.name}"
                )
            allowed = self._VALID_MICRO_TRANSITIONS.get(self._micro_state, set())
            if target not in allowed:
                raise ValueError(
                    f"Cannot transition micro state "
                    f"from {self._micro_state.name} to {target.name}"
                )
            self._micro_state = target

            # 同步 AgentState 微状态
            micro_to_agent: dict[MicroState, AgentStatus] = {
                MicroState.IDLE: AgentStatus.IDLE,
                MicroState.OBSERVING: AgentStatus.THINKING,
                MicroState.THINKING: AgentStatus.THINKING,
                MicroState.DECIDING: AgentStatus.DECIDING,
                MicroState.ACTING: AgentStatus.ACTING,
                MicroState.REFLECTING: AgentStatus.REFLECTING,
                MicroState.LEARNING: AgentStatus.LEARNING,
            }
            agent_target = micro_to_agent.get(target)
            if agent_target is not None and agent_target != self._agent_state.status:
                try:
                    self._agent_state.transition(agent_target)
                except ValueError:
                    pass

    # ── 运行完整微循环 ──────────────────────────────────────────────

    def run_micro_cycle(
        self,
        observe_fn: Callable[[], None],
        think_fn: Callable[[], None],
        decide_fn: Callable[[], None],
        act_fn: Callable[[], None],
        reflect_fn: Callable[[], None],
        learn_fn: Callable[[], None],
    ) -> None:
        """运行一个完整的微观认知循环。

        OBSERVE → THINK → DECIDE → ACT → REFLECT → LEARN

        任何步骤失败都会尝试回到 IDLE。
        """
        with self._lock:
            if self._phase != LifecyclePhase.ACTIVE:
                raise ValueError("Micro cycle only runs in ACTIVE phase")
            if self._micro_state not in (MicroState.IDLE, MicroState.LEARNING):
                raise ValueError(
                    f"Micro cycle must start from IDLE or LEARNING, "
                    f"current: {self._micro_state.name}"
                )

        steps: list[tuple[MicroState, Callable[[], None]]] = [
            (MicroState.OBSERVING, observe_fn),
            (MicroState.THINKING, think_fn),
            (MicroState.DECIDING, decide_fn),
            (MicroState.ACTING, act_fn),
            (MicroState.REFLECTING, reflect_fn),
            (MicroState.LEARNING, learn_fn),
        ]

        for target, fn in steps:
            try:
                self.transition_micro(target)
                fn()
            except Exception:
                # 任何步骤失败，回到 IDLE
                try:
                    self._micro_state = MicroState.IDLE
                except Exception:
                    pass
                raise

    # ── 查询 ─────────────────────────────────────────────────────────

    def is_active(self) -> bool:
        """是否处于 ACTIVE 阶段。"""
        return self._phase == LifecyclePhase.ACTIVE

    def is_sleeping(self) -> bool:
        return self._phase == LifecyclePhase.SLEEPING

    def force_idle(self) -> None:
        """强制回到 IDLE（仅用于异常恢复）。

        跳过验证矩阵，直接设置微观状态。
        """
        with self._lock:
            self._micro_state = MicroState.IDLE

    def is_idle(self) -> bool:
        return self._phase == LifecyclePhase.ACTIVE and self._micro_state == MicroState.IDLE

    # ── 全局状态快照 ────────────────────────────────────────────────

    def freeze(self) -> dict:
        """返回当前状态的不可变快照。"""
        with self._lock:
            return {
                "phase": self._phase.name,
                "micro_state": self._micro_state.name,
                "agent_status": self._agent_state.status.name,
            }

    def __repr__(self) -> str:
        return (
            f"<LifecycleManager: phase={self._phase.name} "
            f"micro={self._micro_state.name}>"
        )
