"""Phase 43: DecisionTrace — 决策可追溯性。

记录决策的生成过程以便审计。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ocos.decision.decision_types import (
    DecisionContext, DecisionOption, DecisionProposal,
    RiskAssessment, ValueEvaluation, DecisionTrace,
)


@dataclass
class DecisionTracer:
    """决策追踪器 — 累积记录决策生成过程的每个步骤。"""

    _traces: dict[str, DecisionTrace] = field(default_factory=dict)

    def record(
        self,
        proposal: DecisionProposal,
        context: DecisionContext,
        all_options: list[DecisionOption],
        discarded: list[str],
        risks: list[RiskAssessment],
        values: list[ValueEvaluation],
        tick_id: int = 0,
    ) -> DecisionTrace:
        trace = DecisionTrace(
            trace_id=f"trace:{proposal.proposal_id}",
            proposal_id=proposal.proposal_id,
            context_snapshot=context,
            generated_options=all_options,
            discarded_options=discarded,
            risk_assessments=risks,
            value_evaluations=values,
            tick_id=tick_id,
        )
        self._traces[trace.trace_id] = trace
        return trace

    def get(self, trace_id: str) -> DecisionTrace | None:
        return self._traces.get(trace_id)


__all__ = ["DecisionTracer"]
