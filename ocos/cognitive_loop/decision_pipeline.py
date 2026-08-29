"""Phase 46: DecisionPipeline — 决策流水线。

整合 Phase 43 Decision Intelligence 到循环中。

流程:
    Synced Context → Decision Proposal → Governance Approval

GAP-P1-1: 原 _generate_proposal 为字符串占位（"Respond to: ..."），
已接入 ocos.decision 真实组件链:
    ContextBuilder → OptionGenerator → RiskEngine + ValueModel → DecisionValidator
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ocos.cognitive_loop.loop_types import LoopContext, LoopPhase
from ocos.decision import (
    ContextBuilder,
    DecisionContext,
    DecisionOption,
    DecisionProposal,
    DecisionState,
    DecisionTracer,
    DecisionValidator,
    OptionGenerator,
    RiskAssessment,
    RiskEngine,
    ValueEvaluation,
    ValueModel,
)


@dataclass
class DecisionPipeline:
    """决策流水线——循环中集成 Phase 43 Decision Intelligence。

    边界 CL46-01: Loop 不自行创建 Goal，Decision 提案需 Governance 批准。
    """

    _history: list[dict] = field(default_factory=list)
    _tracer: DecisionTracer = field(default_factory=DecisionTracer)
    _validator: DecisionValidator = field(default_factory=DecisionValidator)
    _last_proposal: DecisionProposal | None = None

    def process(self, ctx: LoopContext) -> LoopContext:
        """在循环中执行决策阶段。"""
        ctx.phase = LoopPhase.DECIDING

        if not ctx.perception_input and not ctx.active_wisdom:
            # 无输入 + 无记忆触发 → 无决策需要
            return ctx

        proposal, text, context, options, risks, values = self._generate_proposal(ctx)
        self._last_proposal = proposal
        ctx.decision_proposal = text
        if proposal is not None:
            validation = self._validator.validate(proposal)
            ctx.decision_approved = validation.is_valid
            self._tracer.record(
                proposal, context, options, [], risks, values, tick_id=ctx.tick_id,
            )
        else:
            ctx.decision_approved = True  # 维持现状不是风险决策

        return ctx

    def _generate_proposal(self, ctx: LoopContext) -> tuple[
        DecisionProposal | None, str, DecisionContext,
        list[DecisionOption], list[RiskAssessment], list[ValueEvaluation],
    ]:
        """用真实 Decision Intelligence 组件链生成决策提案。"""
        builder = ContextBuilder()
        builder.set_self_context("agent current state")
        for wisdom in ctx.active_wisdom or []:
            builder.add_wisdom(wisdom)
        if ctx.perception_input:
            builder.set_world_context(ctx.perception_input)
        context = builder.build(tick_id=ctx.tick_id)

        options = OptionGenerator().generate(context, tick_id=ctx.tick_id)
        if not options:
            return None, "Maintain current state", context, [], [], []

        risks = RiskEngine().assess_all(options)
        values = ValueModel().evaluate_all(options)
        risk_by_id = {r.option_id: r for r in risks}
        value_by_id = {v.option_id: v for v in values}

        # 选优: overall_score - risk.score（价值优先、风险惩罚）
        def _rank_key(opt_id: str) -> float:
            val = value_by_id.get(opt_id)
            risk = risk_by_id.get(opt_id)
            return (val.overall_score if val else 0.0) - (risk.score if risk else 0.5)

        ranked = sorted(options, key=lambda o: _rank_key(o.option_id), reverse=True)
        best = ranked[0]

        proposal = DecisionProposal(
            proposal_id=f"p-{ctx.tick_id}",
            context_id=context.context_id,
            ranked_options=ranked,
            risk_summary=(risk_by_id[best.option_id].description
                          if best.option_id in risk_by_id else ""),
            value_summary=(f"score={value_by_id[best.option_id].overall_score:.2f}"
                           if best.option_id in value_by_id else ""),
            rationale=(
                f"best option {best.option_id} by value-risk ranking"
                f" ({len(ranked)} options)"
            ),
            state=DecisionState.PROPOSED,
            created_tick=ctx.tick_id,
        )
        return proposal, best.description, context, options, risks, values

    def record_decision(self, ctx: LoopContext) -> None:
        self._history.append({
            "tick": ctx.tick_id,
            "proposal": ctx.decision_proposal,
            "approved": ctx.decision_approved,
        })

    @property
    def recent_decisions(self) -> list[dict]:
        return self._history[-10:]

    @property
    def last_proposal(self) -> DecisionProposal | None:
        """最近一次生成的完整决策提案（GAP-P1-1: 可追溯）。"""
        return self._last_proposal


__all__ = ["DecisionPipeline"]
