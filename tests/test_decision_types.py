"""OCOS decision_types 决策类型不变式测试。

D43-01: Decision ≠ Goal
D43-02: Decision ≠ Execution
D43-03: Wisdom ≠ Rule
"""

import pytest

from ocos.decision.decision_types import (
    DecisionContext,
    OptionType,
    DecisionOption,
    RiskCategory,
    RiskLevel,
    RiskAssessment,
    ValueDimension,
    ValueEvaluation,
    DecisionState,
    DecisionProposal,
    DecisionTrace,
    DecisionResult,
)


class TestDecisionContext:
    def test_empty_context(self):
        ctx = DecisionContext(context_id="ctx-1")
        assert ctx.is_empty is True

    def test_non_empty_context(self):
        ctx = DecisionContext(
            context_id="ctx-2",
            goal_summary="write novel",
        )
        assert ctx.is_empty is False

    def test_all_fields_populated(self):
        ctx = DecisionContext(
            context_id="ctx-3",
            goal_summary="g",
            self_summary="s",
            wisdom_hints=["h1"],
            world_snapshot="w",
            constraints=["c1"],
            tick_id=42,
        )
        assert ctx.is_empty is False
        assert ctx.tick_id == 42
        assert len(ctx.constraints) == 1


class TestOptionType:
    def test_five_types(self):
        vals = {t.value for t in OptionType}
        assert vals == {
            "do_nothing", "direct_action", "delegate", "investigate", "defer"
        }


class TestDecisionOption:
    def test_default(self):
        opt = DecisionOption(
            option_id="opt-1",
            description="investigate",
        )
        assert opt.option_type == OptionType.INVESTIGATE
        assert opt.confidence == 0.0
        assert opt.risk_score == 0.0
        assert opt.value_score == 0.0
        assert opt.source == "generated"

    def test_custom(self):
        opt = DecisionOption(
            option_id="opt-2",
            description="direct action",
            option_type=OptionType.DIRECT_ACTION,
            confidence=0.8,
            risk_score=0.3,
            value_score=0.7,
            source="wisdom_suggested",
            evidence=["E1", "E2"],
        )
        assert opt.confidence == 0.8
        assert len(opt.evidence) == 2
        assert opt.source == "wisdom_suggested"

    def test_option_is_frozen(self):
        opt = DecisionOption(option_id="o", description="d")
        with pytest.raises((TypeError, AttributeError)):
            opt.confidence = 1.0  # type: ignore[misc]


class TestRiskCategory:
    def test_all_categories(self):
        vals = {r.value for r in RiskCategory}
        expected = {"operational", "resource", "reputational",
                    "security", "dependency", "unknown"}
        assert vals == expected


class TestRiskLevel:
    def test_all_levels(self):
        vals = {r.value for r in RiskLevel}
        assert vals == {"negligible", "low", "medium", "high", "critical"}


class TestRiskAssessment:
    def test_defaults(self):
        ra = RiskAssessment(option_id="opt-1", assessment_id="ra-1")
        assert ra.category == RiskCategory.OPERATIONAL
        assert ra.level == RiskLevel.MEDIUM
        assert ra.score == 0.5
        assert ra.probability == 0.5

    def test_custom(self):
        ra = RiskAssessment(
            option_id="opt-1",
            assessment_id="ra-2",
            category=RiskCategory.SECURITY,
            level=RiskLevel.HIGH,
            score=0.8,
            description="data leak risk",
            mitigation="encrypt",
            probability=0.6,
        )
        assert ra.category == RiskCategory.SECURITY
        assert ra.level == RiskLevel.HIGH


class TestValueDimension:
    def test_all_dimensions(self):
        vals = {d.value for d in ValueDimension}
        assert vals == {"efficiency", "reliability", "learning",
                        "alignment", "safety", "novelty"}


class TestValueEvaluation:
    def test_defaults(self):
        ve = ValueEvaluation(option_id="opt-1", evaluation_id="ve-1")
        assert ve.dimensions == {}
        assert ve.overall_score == 0.0

    def test_weighted_score(self):
        ve = ValueEvaluation(
            option_id="opt-1",
            evaluation_id="ve-2",
            dimensions={ValueDimension.SAFETY: 0.8, ValueDimension.EFFICIENCY: 0.6},
        )
        weights = {ValueDimension.SAFETY: 1.0, ValueDimension.EFFICIENCY: 0.5}
        score = ve.weighted_score(weights)
        # (0.8*1.0 + 0.6*0.5) / (1.0 + 0.5) = 1.1 / 1.5 ≈ 0.733
        assert abs(score - 0.7333) < 0.01

    def test_weighted_score_zero_weights(self):
        ve = ValueEvaluation(option_id="o", evaluation_id="e",
                             dimensions={ValueDimension.SAFETY: 0.5})
        score = ve.weighted_score({})
        assert score == 0.0


class TestDecisionState:
    def test_all_states(self):
        vals = {s.value for s in DecisionState}
        expected = {"draft", "analyzing", "proposed", "approved",
                    "rejected", "executed", "archived"}
        assert vals == expected


class TestDecisionProposal:
    def test_default_draft(self):
        dp = DecisionProposal(proposal_id="p-1", context_id="c-1")
        assert dp.state == DecisionState.DRAFT
        assert dp.recommended is None
        assert dp.is_ready is False

    def test_recommended_returns_best(self):
        dp = DecisionProposal(
            proposal_id="p-2",
            context_id="c-1",
            ranked_options=[
                DecisionOption(option_id="o1", description="a", value_score=0.9, risk_score=0.2),
                DecisionOption(option_id="o2", description="b", value_score=0.5, risk_score=0.1),
            ],
        )
        rec = dp.recommended
        assert rec is not None
        assert rec.option_id == "o1"  # highest value - risk

    def test_is_ready_when_proposed(self):
        dp = DecisionProposal(
            proposal_id="p-3", context_id="c-1",
            state=DecisionState.PROPOSED,
        )
        assert dp.is_ready is True

    def test_not_ready_when_draft(self):
        dp = DecisionProposal(proposal_id="p-4", context_id="c-1")
        assert dp.is_ready is False

    def test_empty_ranked_returns_none(self):
        dp = DecisionProposal(proposal_id="p-5", context_id="c-1")
        assert dp.recommended is None


class TestDecisionTrace:
    def test_defaults(self):
        import datetime as dt
        trace = DecisionTrace(
            trace_id="t-1",
            proposal_id="p-1",
            context_snapshot=DecisionContext(context_id="c-1"),
            generated_options=[],
        )
        assert trace.discarded_options == []
        assert trace.risk_assessments == []
        assert trace.tick_id == 0
        assert trace.timestamp <= dt.datetime.now(dt.timezone.utc)


class TestDecisionResult:
    def test_accepted_when_proposed(self):
        dp = DecisionProposal(proposal_id="p-1", context_id="c-1")
        dp.state = DecisionState.PROPOSED
        result = DecisionResult(proposal=dp)
        assert result.accepted is True

    def test_accepted_when_proposed(self):
        dp = DecisionProposal(proposal_id="p-2", context_id="c-1")
        result = DecisionResult(proposal=dp)
        assert result.accepted is False

    def test_accepted_when_proposed(self):
        dp = DecisionProposal(
            proposal_id="p-3", context_id="c-1",
            state=DecisionState.PROPOSED,
        )
        result = DecisionResult(proposal=dp)
        assert result.accepted is True

    def test_accepted_when_proposed(self):
        dp = DecisionProposal(
            proposal_id="p-3", context_id="c-1",
            state=DecisionState.PROPOSED,
        )
        result = DecisionResult(proposal=dp)
        assert result.accepted is True
