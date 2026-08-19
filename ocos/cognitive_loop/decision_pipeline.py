"""Phase 46: DecisionPipeline — 决策流水线。

整合 Phase 43 Decision Intelligence 到循环中。

流程:
    Synced Context → Decision Proposal → Governance Approval
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ocos.cognitive_loop.loop_types import LoopContext, LoopPhase


@dataclass
class DecisionPipeline:
    """决策流水线——循环中集成 Phase 43 Decision Intelligence。

    边界 CL46-01: Loop 不自行创建 Goal，Decision 提案需 Governance 批准。
    """

    _history: list[dict] = field(default_factory=list)

    def process(self, ctx: LoopContext) -> LoopContext:
        """在循环中执行决策阶段。

        目前为占位——实际接入 Phase 43:
            from ocos.decision import ContextBuilder, OptionGenerator, RiskEngine, ValueModel, DecisionTracer, DecisionValidator
        """
        ctx.phase = LoopPhase.DECIDING

        if not ctx.perception_input and not ctx.active_wisdom:
            # 无输入 + 无记忆触发 → 无决策需要
            return ctx

        # 模拟决策建议
        proposal = self._generate_proposal(ctx)
        ctx.decision_proposal = proposal
        ctx.decision_approved = self._governance_check(proposal, ctx)

        return ctx

    def _generate_proposal(self, ctx: LoopContext) -> str:
        """根据上下文生成决策提案。"""
        if ctx.perception_input:
            return f"Respond to: {ctx.perception_input[:100]}"
        if ctx.active_wisdom:
            return f"Recall: {ctx.active_wisdom[0][:100]}"
        return "Maintain current state"

    def _governance_check(self, proposal: str, ctx: LoopContext) -> bool:
        """治理审核——Phase 43 GOVERNANCE Approval。"""
        # 禁止项检查: Decision ≠ Goal, Decision ≠ Execution
        forbidden = ["create_goal", "execute_directly", "auto_override"]
        if any(fw in proposal.lower() for fw in forbidden):
            return False
        return True  # 默认允许内部决策提案

    def record_decision(self, ctx: LoopContext) -> None:
        self._history.append({
            "tick": ctx.tick_id,
            "proposal": ctx.decision_proposal,
            "approved": ctx.decision_approved,
        })

    @property
    def recent_decisions(self) -> list[dict]:
        return self._history[-10:]


__all__ = ["DecisionPipeline"]
