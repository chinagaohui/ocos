"""ControlLoop — Single Authority 控制回路。

Phase 22: Subject Emergence

核心原则:
  1. ControlLoop 是 MasterAgent 的绝对私有组件 — 绝不注入到 Engine/Runtime 中
  2. Engine 只能通过 EventBus 发出 Observation，MasterAgent 主动拉取
  3. 所有 Goal 创建必经 GoalOriginEnforcer → GoalFactory 双关卡

设计约束:
  - 不使用 inspect.currentframe() 进行调用方验证
  - 依赖可见性隔离：ControlLoop 作为 MasterAgent 私有成员
  - 测试环境中通过 contextvars 传递 caller_id 模拟验证
"""

from __future__ import annotations

import contextvars
from typing import Any, Callable, Optional

from ocos.agent.goal_types import (
    Goal,
    GoalAuthority,
    GoalLevel,
    GoalOriginLevel,
)
from ocos.agent.lifecycle import LifecycleManager, LifecyclePhase, MicroState
from ocos.goal.enforcer import GoalOriginEnforcer, ConstitutionResult
from ocos.goal.factory import GoalFactory, ConstitutionViolationError


# contextvars: 测试环境中的调用方追踪
# 生产环境中不设置此值，依赖架构级可见性隔离
_caller_ctx: contextvars.ContextVar[str] = contextvars.ContextVar(
    "control_loop_caller", default=""
)


def set_test_caller(caller_id: str) -> None:
    """设置测试调用方 ID（仅测试用）。"""
    _caller_ctx.set(caller_id)


def clear_test_caller() -> None:
    """清除测试调用方。"""
    _caller_ctx.set("")


def get_caller() -> str:
    """获取当前调用方。生产环境返回空字符串。"""
    return _caller_ctx.get()


class ControlLoop:
    """Single Authority 控制回路。

    MasterAgent 的绝对私有组件。负责:
      - 目标创建（双关卡：Enforcer → Factory）
      - 微观循环编排
      - 观察拉取

    禁止注入到 Engine/Runtime/任何外部模块。
    """

    def __init__(
        self,
        lifecycle: LifecycleManager,
        goal_enforcer: Optional[GoalOriginEnforcer] = None,
        current_phase: int = 22,
    ) -> None:
        self._lifecycle = lifecycle
        self._goal_enforcer = goal_enforcer or GoalOriginEnforcer(
            current_phase=current_phase
        )
        self._current_phase = current_phase

    # ── 目标创建（双关卡）───────────────────────────────────────────

    def create_goal(
        self,
        description: str,
        level: GoalLevel = GoalLevel.TASK,
        origin_level: GoalOriginLevel = GoalOriginLevel.SYSTEM,
        priority: float = 5.0,
        parent_id: Optional[str] = None,
        creator_context: Optional[dict[str, Any]] = None,
        **kwargs: Any,
    ) -> Goal:
        """创建 Goal — 双关卡：Enforcer 校验 → Factory 创建。

        流程:
          1. 构建临时 Goal 供 Enforcer 校验
          2. GoalOriginEnforcer.verify_creation() → ConstitutionResult
          3. 仅当 result.allowed == True 时调用 GoalFactory.create()

        Args:
            description: 目标描述
            level: GoalLevel
            origin_level: 来源层级（默认 SYSTEM）
            priority: 优先级
            parent_id: 父目标 ID
            creator_context: 创建上下文（HUMAN 目标需 human_authorized）
            **kwargs: 额外参数

        Returns:
            创建的 Goal

        Raises:
            ConstitutionViolationError: 校验失败
        """
        # Step 1: 构建临时 Goal 供 Enforcer 校验
        temp = Goal(
            description=description,
            level=level,
            origin_level=origin_level,
            authority=GoalAuthority.AUTONOMOUS,
        )

        # Step 2: Enforcer 校验
        result: ConstitutionResult = self._goal_enforcer.verify_creation(
            temp, creator_context
        )

        if not result.allowed:
            raise ConstitutionViolationError(
                f"Goal creation blocked: {result.violations}"
            )

        # Step 3: Factory 创建（仅当校验通过）
        return GoalFactory.create(
            level=level,
            description=description,
            priority=priority,
            parent_id=parent_id,
            origin_level=origin_level,
            current_phase=self._current_phase,
            **kwargs,
        )

    # ── 微观循环 ────────────────────────────────────────────────────

    def run_cycle(
        self,
        observe_fn: Callable[[], None],
        think_fn: Callable[[], None],
        decide_fn: Callable[[], None],
        act_fn: Callable[[], None],
        reflect_fn: Callable[[], None],
        learn_fn: Callable[[], None],
    ) -> None:
        """运行完整的微观认知循环。

        通过 LifecycleManager.run_micro_cycle() 保证:
          - 状态转换合法性
          - 失败安全回到 IDLE
        """
        self._lifecycle.run_micro_cycle(
            observe_fn=observe_fn,
            think_fn=think_fn,
            decide_fn=decide_fn,
            act_fn=act_fn,
            reflect_fn=reflect_fn,
            learn_fn=learn_fn,
        )

    # ── 生命周期快捷方法 ────────────────────────────────────────────

    def boot_complete(self) -> None:
        """标记启动完成，进入 ACTIVE（幂等）。"""
        if self._lifecycle.phase != LifecyclePhase.ACTIVE:
            self._lifecycle.transition_to_phase(LifecyclePhase.ACTIVE)

    def enter_sleep(self) -> None:
        """进入休眠。"""
        self._lifecycle.transition_to_phase(LifecyclePhase.SLEEPING)

    def wake_from_sleep(self) -> None:
        """从休眠唤醒。"""
        self._lifecycle.transition_to_phase(LifecyclePhase.ACTIVE)

    def enter_dream(self) -> None:
        """进入梦境。"""
        self._lifecycle.transition_to_phase(LifecyclePhase.DREAMING)

    def shutdown(self) -> None:
        """安全关闭。"""
        self._lifecycle.transition_to_phase(LifecyclePhase.SHUTDOWN)

    # ── 查询 ─────────────────────────────────────────────────────────

    @property
    def lifecycle(self) -> LifecycleManager:
        return self._lifecycle

    @property
    def enforcer(self) -> GoalOriginEnforcer:
        return self._goal_enforcer

    @property
    def current_phase(self) -> int:
        return self._current_phase
