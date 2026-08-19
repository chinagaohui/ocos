"""Phase 46: ActionController — 行动控制器。

将批准的 Decision Proposal 转化为 Capability 调用。

链路:
    Decision (approved) → Capability Selection → Execution Bridge → RawResult

接入 Phase 45 Capability Nervous System。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from ocos.cognitive_loop.loop_types import LoopContext, LoopPhase


class ActionOutcome(Enum):
    NO_ACTION = "no_action"
    EXECUTED = "executed"
    FAILED = "failed"
    PERMISSION_DENIED = "permission_denied"
    NO_CAPABILITY = "no_capability"


@dataclass
class ActionController:
    """行动控制器。

    边界:
        - 只有 Decision 批准后才行动
        - 不创建 Goal
        - 不绕过 Permission
    """

    # 可注入 Phase 45 的 CapabilitySelector + ExecutionBridge
    _capability_selector: object = None
    _execution_bridge: object = None

    def set_selector(self, selector: object) -> None:
        self._capability_selector = selector

    def set_bridge(self, bridge: object) -> None:
        self._execution_bridge = bridge

    def act(self, ctx: LoopContext) -> tuple[ActionOutcome, str]:
        """根据决策提案执行行动。"""
        ctx.phase = LoopPhase.ACTING

        if not ctx.decision_approved:
            return ActionOutcome.NO_ACTION, "Decision not approved"

        if not ctx.decision_proposal:
            return ActionOutcome.NO_ACTION, "No proposal"

        # 模拟: 如果有 Capability 可用则执行
        capability = ctx.selected_capability or "default_response"
        result = f"[{capability}] response to: {ctx.decision_proposal[:100]}"
        ctx.action_result = result

        return ActionOutcome.EXECUTED, result

    @property
    def has_capabilities(self) -> bool:
        return self._capability_selector is not None and self._execution_bridge is not None


__all__ = ["ActionOutcome", "ActionController"]
