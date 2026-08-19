"""Phase 48 Acceptance Tests — PM48-01 ~ PM48-04.

验证 Personal Intelligence Maturity 四大边界:
    PM48-01: Personalization != Overfitting — 适应用户，不丧失通用能力
    PM48-02: Meta-cognition != Self-doubt    — 解释决策，不陷入瘫痪
    PM48-03: Goal Coordination != Goal Creation — 跟踪目标，不创造目标
    PM48-04: Consistency != Rigidity        — 稳定身份，允许演化
"""
import pytest

from ocos.personal_intelligence import (
    RiskTolerance,
    ExplanationDepth,
    InteractionStyle,
    DomainPriority,
    CognitiveSignature,
    ConsistencyMetrics,
    GoalStatus,
    LongTermGoal,
    MaturityLevel,
    CognitiveSignatureEngine,
    ConsistencyMonitor,
    MetaCognitionEngine,
    GoalCoordinator,
    PersonalizationEngine,
    calculate_maturity,
)


# ═══════════════════════════════════════════════════════════════════════════════
# 辅助
# ═══════════════════════════════════════════════════════════════════════════════

def _make_signature(mature: bool = False) -> CognitiveSignature:
    sig = CognitiveSignature()
    if mature:
        sig.update_confidence(50)
    return sig


# ═══════════════════════════════════════════════════════════════════════════════
# PM48-01: Personalization != Overfitting
# ═══════════════════════════════════════════════════════════════════════════════

class TestPM48_01_PersonalizationNotOverfitting:
    """适配不等于过拟合。"""

    def test_confidence_capped_at_95(self):
        engine = CognitiveSignatureEngine()
        engine.signature.pattern_confidence = 0.99
        engine.signature.update_confidence(1000)
        assert engine.signature.pattern_confidence <= 0.95

    def test_unreliable_signature_skips_adaptation(self):
        engine = CognitiveSignatureEngine()
        # No observations → not reliable
        assert not engine.is_personalized
        result = engine.get_personalized_options_count()
        # 不可靠时返回默认
        assert result == 3  # default preference_for_options

    def test_domain_priority_confidence_grows_slowly(self):
        engine = CognitiveSignatureEngine()
        engine.observe_domain_interest("writing", 1)
        assert engine.signature.domain_priorities[0].confidence < 0.5

        engine.observe_domain_interest("writing", 50)
        assert engine.signature.domain_priorities[0].confidence > 0.7

    def test_personalization_engine_fallback_when_unreliable(self):
        engine = PersonalizationEngine()
        # No observations — engine not ready
        assert not engine.is_ready

        options = ["A", "B", "C", "D", "E"]
        result = engine.personalize_options(options)
        # 不可靠时返回全部
        assert len(result) == 5


# ═══════════════════════════════════════════════════════════════════════════════
# PM48-02: Meta-cognition != Self-doubt
# ═══════════════════════════════════════════════════════════════════════════════

class TestPM48_02_MetaCognitionNotSelfDoubt:
    """元认知解释决策，不陷入分析瘫痪。"""

    def test_trace_decision_records_rationale(self):
        engine = MetaCognitionEngine()
        rationale = engine.trace_decision(
            question="Should I use library A or B?",
            chosen="Library A",
            alternatives=["Library B", "Library C"],
            evidence=["A has better docs", "A has larger community"],
            past_similar=5,
            confidence=0.8,
        )
        assert rationale.decision_id.startswith("dc:")
        assert rationale.chosen_option == "Library A"
        assert len(rationale.alternatives_considered) == 2
        assert engine.total_decisions == 1

    def test_explain_decision_formats_correctly(self):
        engine = MetaCognitionEngine()
        rationale = engine.trace_decision(
            question="Rewrite or refactor?",
            chosen="Refactor incrementally",
            alternatives=["Full rewrite"],
            evidence=["Lower risk", "Faster delivery"],
            past_similar=12,
            confidence=0.75,
            signature=CognitiveSignature(risk_tolerance=RiskTolerance.CONSERVATIVE),
            learnings="Refactoring safer with existing tests",
        )
        explanation = engine.explain_decision(rationale.decision_id)
        assert "Refactor incrementally" in explanation
        assert "conservative" in explanation

    def test_similar_decisions_search(self):
        engine = MetaCognitionEngine()
        engine.trace_decision("Should I write parser?", "Yes", [], ["need it"], confidence=0.9)
        engine.trace_decision("Application config fix?", "Patch", [], [], confidence=0.5)
        engine.trace_decision("Should I write parser?", "No", [], ["not needed now"], confidence=0.3)

        similar = engine.similar_decisions("parser")
        assert len(similar) == 2

    def test_no_infinite_reevaluation(self):
        """MetaCognitionEngine 没有 reevaluate/reconsider/loop 方法。"""
        engine = MetaCognitionEngine()
        assert not hasattr(engine, 'reevaluate')
        assert not hasattr(engine, 'reconsider')
        assert not hasattr(engine, 'loop_decide')

    def test_recent_insights_deduplicates(self):
        engine = MetaCognitionEngine()
        engine.trace_decision("Q1", "A", [], [], learnings="Pattern X works")
        engine.trace_decision("Q2", "B", [], [], learnings="Pattern X works")
        engine.trace_decision("Q3", "C", [], [], learnings="Pattern Y fails")

        insights = engine.recent_insights
        assert len(insights) == 2
        assert "Pattern X works" in insights


# ═══════════════════════════════════════════════════════════════════════════════
# PM48-03: Goal Coordination != Goal Creation
# ═══════════════════════════════════════════════════════════════════════════════

class TestPM48_03_GoalCoordinationNotGoalCreation:
    """协调不等于创建目标。"""

    def test_has_goal_creation_capability_false(self):
        coordinator = GoalCoordinator()
        assert not coordinator.has_goal_creation_capability

    def test_no_create_goal_method(self):
        coordinator = GoalCoordinator()
        assert not hasattr(coordinator, 'create_goal')
        assert not hasattr(coordinator, 'generate_goal')
        assert not hasattr(coordinator, 'auto_goal')

    def test_reject_non_user_goal(self):
        coordinator = GoalCoordinator()
        with_auto = LongTermGoal(
            goal_id="g:auto", title="AI decided goal",
            created_by="system",
        )
        with pytest.raises(ValueError, match="PM48-03"):
            coordinator.register_goal(with_auto)

    def test_register_user_goal(self):
        coordinator = GoalCoordinator()
        goal = LongTermGoal(
            goal_id="g:1", title="Learn Rust",
            created_by="user",
        )
        coordinator.register_goal(goal)
        assert len(coordinator.goals) == 1

    def test_decompose_goal(self):
        coordinator = GoalCoordinator()
        goal = LongTermGoal(goal_id="g:2", title="Start company", created_by="user")
        coordinator.register_goal(goal)

        ok = coordinator.decompose_goal("g:2", ["Research", "MVP", "Launch"])
        assert ok
        assert len(goal.milestones) == 3

    def test_update_progress(self):
        coordinator = GoalCoordinator()
        goal = LongTermGoal(goal_id="g:3", title="Write book", created_by="user")
        coordinator.register_goal(goal)
        coordinator.decompose_goal("g:3", ["Outline", "Draft 1", "Draft 2", "Edit", "Publish"])

        progress = coordinator.update_progress("g:3", ["Outline", "Draft 1"])
        assert progress == 0.4

        assert goal.progress == 0.4
        assert goal.status == GoalStatus.ACTIVE

    def test_goal_completion(self):
        coordinator = GoalCoordinator()
        goal = LongTermGoal(goal_id="g:4", title="Simple task", created_by="user")
        coordinator.register_goal(goal)
        coordinator.decompose_goal("g:4", ["Do it"])

        progress = coordinator.update_progress("g:4", ["Do it"])
        assert progress == 1.0
        assert goal.status == GoalStatus.COMPLETED

    def test_detect_stagnation(self):
        coordinator = GoalCoordinator()
        goal = LongTermGoal(
            goal_id="g:5", title="Long project",
            created_by="user", last_reviewed_tick=0,
        )
        coordinator.register_goal(goal)

        assert coordinator.detect_stagnation("g:5", current_tick=200, max_ticks=100)

    def test_active_and_completed_goals(self):
        coordinator = GoalCoordinator()
        g1 = LongTermGoal(goal_id="g:a", title="Active", created_by="user")
        g2 = LongTermGoal(goal_id="g:b", title="Done", created_by="user")
        coordinator.register_goal(g1)
        coordinator.register_goal(g2)
        coordinator.decompose_goal("g:b", ["x"])
        coordinator.update_progress("g:b", ["x"])

        assert len(coordinator.active_goals()) == 1
        assert len(coordinator.completed_goals()) == 1


# ═══════════════════════════════════════════════════════════════════════════════
# PM48-04: Consistency != Rigidity
# ═══════════════════════════════════════════════════════════════════════════════

class TestPM48_04_ConsistencyNotRigidity:
    """一致性是基线参照，不是阻止演化的锁。"""

    def test_establish_and_measure_baseline(self):
        monitor = ConsistencyMonitor()
        baseline = ConsistencyMetrics(
            identity_stability=1.0,
            memory_health=0.9,
            wisdom_accumulation_rate=0.3,
            decision_pattern_stability=1.0,
            goal_alignment=1.0,
            personalization_depth=0.1,
        )
        monitor.establish_baseline(baseline)
        assert monitor._baseline is not None
        assert monitor.measurement_count == 1

    def test_drift_from_baseline(self):
        monitor = ConsistencyMonitor()
        baseline = ConsistencyMetrics(
            identity_stability=1.0, memory_health=1.0,
            decision_pattern_stability=1.0, goal_alignment=1.0,
        )
        monitor.establish_baseline(baseline)

        # Later: personalization improved, slight memory degradation
        current = monitor.measure(
            identity_stability=1.0,
            memory_health=0.8,
            wisdom_rate=0.4,
            decision_stability=0.95,
            goal_alignment=1.0,
            personalization_depth=0.5,
        )
        drift = monitor.drift_from_baseline()
        assert drift is not None
        assert 0 < drift < 1.0  # Some drift but identity stable

    def test_maturity_level_progression(self):
        monitor = ConsistencyMonitor()

        # Phase 1: INITIALIZING
        assert monitor.maturity_level() == MaturityLevel.INITIALIZING

        # Phase 2: LEARNING
        monitor.measure(personalization_depth=0.1)
        assert monitor.maturity_level() == MaturityLevel.LEARNING

        # Phase 3: ADAPTING
        monitor.measure(personalization_depth=0.3)
        assert monitor.maturity_level() == MaturityLevel.ADAPTING

        # Phase 4: MATURE (high personalization, lower other scores)
        monitor.measure(
            personalization_depth=0.6,
            memory_health=0.5,
            decision_stability=0.6,
            identity_stability=0.8,
        )
        assert monitor.maturity_level() == MaturityLevel.MATURE

        # Phase 5: DEEPENING
        monitor.measure(
            personalization_depth=0.8,
            wisdom_rate=0.9,
            decision_stability=0.95,
        )
        current = monitor.maturity_level()
        # With high enough scores, should reach DEEPENING
        assert current in (MaturityLevel.MATURE, MaturityLevel.DEEPENING)

    def test_overall_maturity_score(self):
        metrics = ConsistencyMetrics(
            identity_stability=1.0,
            memory_health=0.9,
            wisdom_accumulation_rate=0.5,
            decision_pattern_stability=0.9,
            goal_alignment=0.8,
            personalization_depth=0.6,
        )
        score = metrics.overall_maturity
        assert 0.6 < score < 1.0

    def test_calculate_maturity_full(self):
        report = calculate_maturity(
            pattern_confidence=0.7,
            consistency_drift=0.1,
            meta_cognition_ratio=0.6,
            personalization_depth=0.5,
            goal_tracking_coverage=0.8,
            wisdom_accumulation_rate=0.4,
        )
        assert report.level in (MaturityLevel.ADAPTING, MaturityLevel.MATURE)
        assert 0.5 <= report.score <= 0.9
        assert "pattern_confidence" in report.dimensions


# ═══════════════════════════════════════════════════════════════════════════════
# 集成测试
# ═══════════════════════════════════════════════════════════════════════════════

class TestPersonalIntelligenceIntegration:
    """整体集成测试。"""

    def test_signature_learning_pipeline(self):
        """完整认知特征学习管道。"""
        engine = CognitiveSignatureEngine()

        # 初始状态: 不可靠
        assert not engine.is_personalized

        # 模拟 20 次风险观察
        for _ in range(20):
            engine.observe_risk_choice(
                [("Safe", 0.1), ("Medium", 0.5), ("Risky", 0.9)],
                "Safe",
            )

        assert engine.signature.risk_tolerance == RiskTolerance.CONSERVATIVE
        assert engine.is_personalized

    def test_personalization_to_meta_cognition_integration(self):
        """个性化 + 元认知集成。"""
        sig_engine = CognitiveSignatureEngine()
        meta_engine = MetaCognitionEngine()

        sig_engine.observe_risk_choice(
            [("low", 0.1), ("high", 0.9)], "low",
        )

        rationale = meta_engine.trace_decision(
            question="Deploy to production?",
            chosen="Wait for additional testing",
            alternatives=["Deploy now"],
            evidence=["Failed 2 of 5 smoke tests"],
            past_similar=3,
            confidence=0.65,
            signature=sig_engine.signature,
            learnings="Conservative approach avoided outages in past",
        )

        explanation = meta_engine.explain_decision(rationale.decision_id)
        assert "conservative" in explanation

    def test_goal_to_maturity_integration(self):
        """目标协调 + 成熟度集成。"""
        coordinator = GoalCoordinator()
        for i in range(3):
            g = LongTermGoal(
                goal_id=f"g:int:{i}", title=f"Goal {i}", created_by="user",
            )
            coordinator.register_goal(g)
            coordinator.decompose_goal(g.goal_id, [f"Step {j}" for j in range(3)])

        assert len(coordinator.active_goals()) == 3

    def test_goal_coordinator_rejects_system_created_goals(self):
        """坚定拒绝系统创建的目标。"""
        coordinator = GoalCoordinator()
        bad_goal = LongTermGoal(
            goal_id="evil",
            title="AI decides this",
            created_by="ai",
        )
        with pytest.raises(ValueError):
            coordinator.register_goal(bad_goal)
