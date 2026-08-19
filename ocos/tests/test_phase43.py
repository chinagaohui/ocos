"""Phase 43 Acceptance Tests — D43-01 ~ D43-06.

验证 Decision Intelligence 六大边界:
    D43-01: Decision ≠ Goal        — 决策不能创建/修改 Goal
    D43-02: Decision ≠ Execution   — 决策不能直接执行
    D43-03: Wisdom ≠ Rule          — 智慧不能取代情境判断
    D43-04: Context Integration    — 四源聚合正确
    D43-05: Risk Assessment        — 选项风险分析
    D43-06: Value Evaluation       — 价值框架评估
"""
import pytest
from ocos.decision import (
    DecisionContext, DecisionOption, OptionType,
    RiskAssessment, RiskCategory, RiskLevel,
    ValueEvaluation, ValueDimension,
    DecisionState, DecisionProposal,
    ContextBuilder, OptionGenerator, RiskEngine, ValueModel,
    DecisionTracer, Violation, DecisionValidator,
)


# ═══════════════════════════════════════════════════════════════════════════════
# D43-01: Decision ≠ Goal
# ═══════════════════════════════════════════════════════════════════════════════

class TestD43_01_DecisionNotGoal:
    """决策提案不能创建或修改 Goal。"""

    def test_goal_like_description_rejected(self):
        v = DecisionValidator()
        opt = DecisionOption(
            option_id="g1",
            description="创建目标: 学习 Rust",
            option_type=OptionType.DIRECT_ACTION,
        )
        proposal = DecisionProposal(
            proposal_id="p1", context_id="c",
            ranked_options=[opt],
        )
        result = v.validate(proposal)
        assert not result.is_valid
        assert Violation.PROPOSES_GOAL in result.violations

    def test_non_goal_description_passes(self):
        v = DecisionValidator()
        opt = DecisionOption(
            option_id="ok1",
            description="调查异步框架的适用性",
            option_type=OptionType.INVESTIGATE,
        )
        proposal = DecisionProposal(
            proposal_id="p2", context_id="c",
            ranked_options=[opt],
        )
        result = v.validate(proposal)
        assert result.is_valid


# ═══════════════════════════════════════════════════════════════════════════════
# D43-02: Decision ≠ Execution
# ═══════════════════════════════════════════════════════════════════════════════

class TestD43_02_DecisionNotExecution:
    """决策提案不能直接包含执行指令。"""

    def test_execute_like_description_rejected(self):
        v = DecisionValidator()
        opt = DecisionOption(
            option_id="e1",
            description="执行 pip install package",
            option_type=OptionType.DIRECT_ACTION,
        )
        proposal = DecisionProposal(
            proposal_id="p1", context_id="c",
            ranked_options=[opt],
        )
        result = v.validate(proposal)
        assert not result.is_valid
        assert Violation.DIRECT_EXECUTION in result.violations

    def test_investigate_passes(self):
        v = DecisionValidator()
        opt = DecisionOption(
            option_id="ok1",
            description="研究任务队列方案，收集性能数据",
            option_type=OptionType.INVESTIGATE,
        )
        proposal = DecisionProposal(
            proposal_id="p2", context_id="c",
            ranked_options=[opt],
        )
        result = v.validate(proposal)
        assert result.is_valid


# ═══════════════════════════════════════════════════════════════════════════════
# D43-03: Wisdom ≠ Rule
# ═══════════════════════════════════════════════════════════════════════════════

class TestD43_03_WisdomNotRule:
    """智慧建议不能成为不可违反的规则。"""

    def test_high_conf_wisdom_rejected(self):
        v = DecisionValidator()
        opt = DecisionOption(
            option_id="w1",
            description="基于智慧做X",
            source="wisdom_suggested",
            confidence=0.99,  # 过高
        )
        proposal = DecisionProposal(
            proposal_id="p1", context_id="c",
            ranked_options=[opt],
        )
        result = v.validate(proposal)
        assert not result.is_valid
        assert Violation.WISDOM_AS_RULE in result.violations

    def test_moderate_conf_wisdom_accepted(self):
        v = DecisionValidator()
        opt = DecisionOption(
            option_id="w2",
            description="基于智慧做Y",
            source="wisdom_suggested",
            confidence=0.7,  # 合理
        )
        proposal = DecisionProposal(
            proposal_id="p2", context_id="c",
            ranked_options=[opt],
        )
        result = v.validate(proposal)
        assert result.is_valid


# ═══════════════════════════════════════════════════════════════════════════════
# D43-04: Context Integration
# ═══════════════════════════════════════════════════════════════════════════════

class TestD43_04_ContextIntegration:
    """四源（Goal + Self + Wisdom + World）聚合正确。"""

    def test_full_context_builds(self):
        cb = ContextBuilder()
        cb.set_goal_context("选择异步框架")
        cb.set_self_context("偏好可靠性")
        cb.add_wisdom("先冻结ABI")
        cb.set_world_context("asyncio 成熟稳定")
        cb.add_constraint("必须向后兼容")

        ctx = cb.build(tick_id=1)
        assert ctx.goal_summary == "选择异步框架"
        assert ctx.self_summary == "偏好可靠性"
        assert len(ctx.wisdom_hints) == 1
        assert ctx.world_snapshot == "asyncio 成熟稳定"
        assert len(ctx.constraints) == 1
        assert not ctx.is_empty

    def test_empty_context_is_empty(self):
        cb = ContextBuilder()
        ctx = cb.build()
        assert ctx.is_empty

    def test_reset_clears(self):
        cb = ContextBuilder()
        cb.set_goal_context("test")
        cb.reset()
        ctx = cb.build()
        assert ctx.is_empty

    def test_duplicate_wisdom_not_added(self):
        cb = ContextBuilder()
        cb.add_wisdom("A")
        cb.add_wisdom("")
        cb.add_wisdom("   ")
        ctx = cb.build()
        assert len(ctx.wisdom_hints) == 1


# ═══════════════════════════════════════════════════════════════════════════════
# D43-05: Risk Assessment
# ═══════════════════════════════════════════════════════════════════════════════

class TestD43_05_RiskAssessment:
    """选项风险分析。"""

    def test_low_confidence_is_high_risk(self):
        re = RiskEngine()
        opt = DecisionOption("o1", "desc", confidence=0.2)
        result = re.assess(opt)
        assert result.score >= 0.7
        assert result.level in (RiskLevel.HIGH, RiskLevel.CRITICAL)

    def test_high_confidence_is_low_risk(self):
        re = RiskEngine()
        opt = DecisionOption("o1", "desc", confidence=0.9)
        result = re.assess(opt)
        assert result.score < 0.6

    def test_prerequisites_increase_risk(self):
        re = RiskEngine()
        opt = DecisionOption("o1", "desc", confidence=0.5,
                             prerequisites=["a", "b", "c"])
        result = re.assess(opt)
        assert result.score >= 0.4
        assert result.category == RiskCategory.RESOURCE


# ═══════════════════════════════════════════════════════════════════════════════
# D43-06: Value Evaluation
# ═══════════════════════════════════════════════════════════════════════════════

class TestD43_06_ValueEvaluation:
    """价值框架评估。"""

    def test_investigate_has_high_learning(self):
        vm = ValueModel()
        opt = DecisionOption("o1", "调查方案", option_type=OptionType.INVESTIGATE,
                             confidence=0.7, risk_score=0.2, value_score=0.6)
        result = vm.evaluate(opt)
        assert result.dimensions[ValueDimension.LEARNING] >= 0.7

    def test_do_nothing_has_zero_novelty(self):
        vm = ValueModel()
        opt = DecisionOption("o1", "不做", option_type=OptionType.DO_NOTHING)
        result = vm.evaluate(opt)
        assert result.dimensions[ValueDimension.NOVELTY] == 0.0

    def test_weighted_score_fallback(self):
        vm = ValueModel()
        opt = DecisionOption("o1", "test", confidence=0.8, risk_score=0.3,
                             value_score=0.7)
        result = vm.evaluate(opt)
        assert 0 <= result.overall_score <= 1

    def test_high_risk_reduces_safety_score(self):
        vm = ValueModel()
        opt = DecisionOption("o1", "test", risk_score=0.9)
        result = vm.evaluate(opt)
        assert result.dimensions[ValueDimension.SAFETY] < 0.3


# ═══════════════════════════════════════════════════════════════════════════════
# Integration: Full pipeline
# ═══════════════════════════════════════════════════════════════════════════════

class TestFullPipeline:
    """端到端决策流水线。"""

    def test_full_pipeline(self):
        # 1. Build context
        cb = ContextBuilder()
        cb.set_goal_context("选择合适的测试框架")
        cb.set_self_context("OCOS 偏好 pytest")
        cb.add_wisdom("过去选择 pytest 成功7次/8次尝试")
        cb.set_world_context("可用: pytest / unittest / nose2")
        ctx = cb.build(tick_id=1)

        # 2. Generate options
        og = OptionGenerator()
        options = og.generate(ctx, tick_id=1)
        assert len(options) >= 2

        # 3. Risk analysis
        re = RiskEngine()
        risks = re.assess_all(options)
        assert len(risks) == len(options)

        # 4. Value evaluation
        vm = ValueModel()
        values = vm.evaluate_all(options)
        assert len(values) == len(options)

        # 5. Rank and propose
        ranked = sorted(
            options,
            key=lambda o: next(v for v in values if v.option_id == o.option_id).overall_score
                          - next(r for r in risks if r.option_id == o.option_id).score,
            reverse=True,
        )
        proposal = DecisionProposal(
            proposal_id="p_full",
            context_id=ctx.context_id,
            ranked_options=ranked,
            state=DecisionState.PROPOSED,
        )

        # 6. Validate
        v = DecisionValidator()
        result = v.validate(proposal)
        assert result.is_valid

        # 7. Trace
        tracer = DecisionTracer()
        discarded = [o.option_id for o in options if o not in ranked[:3]]
        trace = tracer.record(proposal, ctx, options, discarded, risks, values)
        assert trace.context_snapshot.goal_summary  # captured

    def test_pipeline_without_wisdom_still_works(self):
        """即使没有 wisdom 也应该能正常工作。"""
        cb = ContextBuilder()
        cb.set_goal_context("测试")
        ctx = cb.build(tick_id=1)

        og = OptionGenerator()
        options = og.generate(ctx)
        assert len(options) == 1  # only defer

    def test_proposal_state_transitions(self):
        """提案状态管理。"""
        proposal = DecisionProposal(
            proposal_id="p",
            context_id="c",
            state=DecisionState.DRAFT,
        )
        assert not proposal.is_ready
        assert proposal.recommended is None
