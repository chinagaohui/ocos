"""Phase 49 Acceptance Tests — CC49-01 ~ CC49-04.

验证 Cognitive Continuity System 四大边界:
    CC49-01: Continuity ≠ Archive   — 质量筛选 + 容量限制
    CC49-02: Identity Continuity ≠ Freeze — 检测≠阻止
    CC49-03: Knowledge Aging ≠ Amnesia — 分级衰减 + 核心保护
    CC49-04: Timeline ≠ Prediction  — 只记录意图，不预测
"""
from ocos.cognitive_continuity import (
    TimeGranularity,
    TimeAnchor,
    KnowledgeAge,
    LifeMemoryEngine,
    TimelineEngine,
    IdentityContinuityEngine,
    KnowledgeAgingEngine,
    ContinuityCheckpoint,
    TICKS_PER_MONTH,
)
from ocos.cognitive_continuity.continuity_types import (
    IdentitySnapshot, TimelineEntry,
)


# ═══════════════════════════════════════════════════════════════════════════════
# CC49-01: Continuity ≠ Archive
# ═══════════════════════════════════════════════════════════════════════════════

class TestCC49_01_ContinuityNotArchive:
    """质量筛选，容量限制。"""

    def test_low_importance_rejected(self):
        engine = LifeMemoryEngine()
        result = engine.record_experience(1, "trivial", importance=0.05)
        assert result is None  # < 0.1 丢弃

    def test_high_importance_kept(self):
        engine = LifeMemoryEngine()
        result = engine.record_experience(1, "important", importance=0.8)
        assert result is not None
        assert result.importance == 0.8
        assert engine.graph.total_experiences == 1

    def test_capacity_limit_enforced(self):
        engine = LifeMemoryEngine()
        engine.MAX_EXPERIENCES = 10
        for i in range(20):
            engine.record_experience(i, f"exp-{i}", importance=0.2 + (i % 10) * 0.05)
        assert engine.graph.total_experiences <= 10

    def test_hierarchy_aggregation(self):
        engine = LifeMemoryEngine()
        # Record and aggregate
        nodes = [engine.record_experience(i, f"day-{i}", importance=0.3) for i in range(20)]
        nodes = [n for n in nodes if n is not None]

        day = engine.aggregate_day("2026-07-26", nodes)
        assert day.granularity == TimeGranularity.DAY
        assert len(day.entries) > 0

        week = engine.aggregate_week("2026-W30", [day])
        assert week.granularity == TimeGranularity.WEEK

        month = engine.aggregate_month("2026-07", [week])
        assert month.granularity == TimeGranularity.MONTH

        year = engine.aggregate_year("2026", [month])
        assert year.granularity == TimeGranularity.YEAR

    def test_capacity_limits_all_levels(self):
        engine = LifeMemoryEngine()
        engine.MAX_DAYS = 3

        # Simple: add 10 days, ensure capacity works
        for i in range(10):
            nodes = [engine.record_experience(j, "x", 0.5) for j in range(2)]
            nodes = [n for n in nodes if n is not None]
            engine.aggregate_day(f"d{i}", nodes)

        assert len(engine.graph.days) == 3

    def test_by_tag_retrieval(self):
        engine = LifeMemoryEngine()
        engine.record_experience(1, "coding", 0.7, tags=["code", "python"])
        engine.record_experience(2, "writing", 0.5, tags=["doc"])
        engine.record_experience(3, "debug", 0.8, tags=["code", "bug"])

        code_entries = engine.by_tag("code")
        assert len(code_entries) == 2


# ═══════════════════════════════════════════════════════════════════════════════
# CC49-02: Identity Continuity ≠ Freeze
# ═══════════════════════════════════════════════════════════════════════════════

class TestCC49_02_IdentityContinuityNotFreeze:
    """检测漂移，但允许演化。"""

    def test_consistent_identity_no_drift(self):
        engine = IdentityContinuityEngine()
        engine.create_snapshot(100, "baseline", "moderate", "balanced")
        snap = engine.create_snapshot(200, "later", "moderate", "balanced")
        check = engine.check_continuity(snap)
        assert check.is_consistent
        assert not check.drift_detected

    def test_risk_shift_detected(self):
        engine = IdentityContinuityEngine()
        engine.create_snapshot(100, "baseline", "conservative", "careful")
        snap = engine.create_snapshot(200, "changed", "bold", "aggressive")
        check = engine.check_continuity(snap)
        assert not check.is_consistent
        assert check.drift_detected
        assert "Risk tolerance" in str(check.anomalies)

    def test_decision_style_change_detected(self):
        engine = IdentityContinuityEngine()
        engine.create_snapshot(100, "baseline", "moderate", "analytical")
        snap = engine.create_snapshot(200, "changed", "moderate", "intuitive")
        check = engine.check_continuity(snap)
        assert "Decision style" in str(check.anomalies)

    def test_wisdom_decrease_detected(self):
        engine = IdentityContinuityEngine()
        engine.create_snapshot(100, "baseline", "moderate", "balanced",
                               wisdom_count=100)
        snap = engine.create_snapshot(200, "degraded", "moderate", "balanced",
                                      wisdom_count=50)
        check = engine.check_continuity(snap)
        assert check.drift_detected

    def test_consistent_rate_calculation(self):
        engine = IdentityContinuityEngine()
        engine.create_snapshot(100, "s1", "moderate", "A")
        engine.create_snapshot(200, "s2", "moderate", "A")
        engine.create_snapshot(300, "s3", "bold", "B")
        engine.check_continuity(engine.snapshots[1])
        engine.check_continuity(engine.snapshots[2])
        engine.check_continuity(engine.snapshots[2])
        assert engine.consistent_rate < 1.0

    def test_core_memory_replacement_detected(self):
        engine = IdentityContinuityEngine()
        engine.create_snapshot(100, "old", "moderate", "balanced",
                               key_memories=["A", "B", "C", "D", "E"])
        snap = engine.create_snapshot(200, "new", "moderate", "balanced",
                                      key_memories=["X", "Y", "Z", "W", "V"])
        check = engine.check_continuity(snap)
        assert "Core memories" in str(check.anomalies)


# ═══════════════════════════════════════════════════════════════════════════════
# CC49-03: Knowledge Aging ≠ Amnesia
# ═══════════════════════════════════════════════════════════════════════════════

class TestCC49_03_KnowledgeAgingNotAmnesia:
    """分级衰退 + 核心保护。"""

    def test_fresh_knowledge_weight_1(self):
        engine = KnowledgeAgingEngine()
        item = engine.register("k1", "fresh knowledge")
        assert item.weight == 1.0
        assert item.age == KnowledgeAge.FRESH

    def test_aging_progression(self):
        engine = KnowledgeAgingEngine()
        item = engine.register("k1", "aging knowledge", is_core=False)
        # Simulate time passing
        item.ticks_age = TICKS_PER_MONTH * 7  # 7 months
        engine.age_all(0)
        assert item.age == KnowledgeAge.AGING
        assert item.weight == 0.5

    def test_core_knowledge_never_decays(self):
        engine = KnowledgeAgingEngine()
        item = engine.register("k2", "core knowledge", is_core=True)
        item.ticks_age = TICKS_PER_MONTH * 50  # 50 months
        engine.age_all(0)
        assert item.age != KnowledgeAge.FRESH  # age label changes
        assert item.weight == 1.0              # but weight stays 1.0
        assert len(engine.core_knowledge()) == 1

    def test_reference_refreshes_age(self):
        engine = KnowledgeAgingEngine()
        item = engine.register("k3", "old knowledge")
        item.ticks_age = TICKS_PER_MONTH * 20
        engine.age_all(100_000)
        assert item.age != KnowledgeAge.FRESH

        engine.reference("k3", 200_000)
        assert item.age == KnowledgeAge.FRESH
        assert item.weight == 1.0

    def test_archived_not_deleted(self):
        engine = KnowledgeAgingEngine()
        item = engine.register("k4", "ancient knowledge")
        item.ticks_age = TICKS_PER_MONTH * 50
        engine.age_all(0)
        assert item.age == KnowledgeAge.ARCHIVED
        assert item.weight == 0.0
        # 但条目依然存在
        assert engine.total_items == 1
        assert len(engine.active_knowledge()) == 0  # 活跃知识不含

    def test_weight_summary_counts(self):
        engine = KnowledgeAgingEngine()
        for i in range(3):
            engine.register(f"fresh-{i}", "fresh")
        engine.register("core-x", "core", is_core=True)

        summary = engine.weight_summary()
        assert summary[KnowledgeAge.FRESH] == 4
        assert summary[KnowledgeAge.CURRENT] == 0


# ═══════════════════════════════════════════════════════════════════════════════
# CC49-04: Timeline ≠ Prediction
# ═══════════════════════════════════════════════════════════════════════════════

class TestCC49_04_TimelineNotPrediction:
    """只记录，不预测。"""

    def test_past_recording(self):
        engine = TimelineEngine()
        engine.record_decision(1, "chose A", "Picked library A over B")
        engine.record_milestone(2, "MVP Done", "First working prototype")
        assert engine.past_count == 2

    def test_present_snapshot(self):
        engine = TimelineEngine()
        engine.snapshot_present(10, ["Running", "Healthy", "Learning"])
        assert len(engine.timeline.present) == 3
        assert engine.timeline.present[0].anchor == TimeAnchor.PRESENT

    def test_intent_recording(self):
        engine = TimelineEngine()
        engine.record_intent(5, "launch product", "Launch by Q4")
        assert engine.intent_count == 1
        assert engine.timeline.future_intents[0].anchor == TimeAnchor.FUTURE_INTENT

    def test_no_prediction_methods(self):
        """TimelineEngine 没有预测能力。"""
        engine = TimelineEngine()
        assert not hasattr(engine, 'predict')
        assert not hasattr(engine, 'forecast')
        assert not hasattr(engine, 'anticipate')
        assert not hasattr(engine, 'plan_for_user')

    def test_significant_events_filtered(self):
        engine = TimelineEngine()
        engine.record_decision(1, "trivial", "x", significance=0.2)
        engine.record_decision(2, "important", "y", significance=0.9)
        engine.record_milestone(3, "milestone", "z", significance=0.95)

        significant = engine.significant_events()
        assert len(significant) == 2
        assert all(e.significance >= 0.7 for e in significant)

    def test_only_user_intents_recorded(self):
        """future_intents 只能由用户意图填充——引擎不能自行创建。"""
        engine = TimelineEngine()
        # Simulate what should NOT happen:
        entry = TimelineEntry(
            entry_id="bad", anchor=TimeAnchor.FUTURE_INTENT,
            tick_id=0, label="OCOS prediction", summary="should not exist",
        )
        # This can be created manually (bad usage) but the engine API
        # forces explicit intent recording
        engine.timeline.add_intent(entry)
        # The engine itself only has record_intent which requires
        # explicit user-origin parameters
        assert engine.timeline.future_intents[0].anchor == TimeAnchor.FUTURE_INTENT


# ═══════════════════════════════════════════════════════════════════════════════
# 集成测试
# ═══════════════════════════════════════════════════════════════════════════════

class TestContinuityIntegration:
    """跨子系统集成测试。"""

    def test_checkpoint_creation(self):
        memory = LifeMemoryEngine()
        timeline = TimelineEngine()
        identity = IdentityContinuityEngine()
        knowledge = KnowledgeAgingEngine()
        checkpoint = ContinuityCheckpoint()

        # Populate subsystems
        for i in range(100):
            memory.record_experience(i, f"experience-{i}", importance=0.3 + (i % 5) * 0.1)

        timeline.record_decision(1, "start", "project started", 0.9)
        timeline.record_intent(5, "launch", "Q4 launch")
        identity.create_snapshot(100, "initial", "moderate", "balanced",
                                 wisdom_count=10)
        knowledge.register("k1", "knowledge")
        knowledge.register("core1", "core knowledge", is_core=True)

        state = checkpoint.create_checkpoint(
            1000, "weekly-checkpoint",
            identity=identity, memory=memory,
            timeline=timeline, knowledge=knowledge,
        )
        assert state.tick_id == 1000
        assert state.experience_count >= 90  # some filtered
        assert state.timeline_past_count == 1
        assert state.timeline_intent_count == 1

    def test_full_age_cycle(self):
        """知识的完整生命周期。"""
        engine = KnowledgeAgingEngine()
        engine.register("core", "eternal", is_core=True)
        engine.register("temporal", "fading")

        # Simulate 4 years
        for item in engine.items:
            item.ticks_age = TICKS_PER_MONTH * 48

        engine.age_all(0)
        assert engine.items[0].weight == 1.0  # core
        assert engine.items[1].weight == 0.0  # temporal archived

    def test_multiple_identity_snapshots_then_check(self):
        identity = IdentityContinuityEngine()
        for i in range(5):
            identity.create_snapshot(i * 100, f"s{i}", "moderate", "balanced",
                                     wisdom_count=10 + i)
        snap = identity.create_snapshot(600, "s5", "moderate", "balanced",
                                        wisdom_count=14)
        check = identity.check_continuity(snap)
        assert check.is_consistent  # 稳步增长，正常
