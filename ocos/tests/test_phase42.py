"""Phase 42 Acceptance Tests — WM42-01 ~ WM42-06.

验证 World Model 六大边界:
    WM42-01: Entity Isolation     — 实体独立存在
    WM42-02: Relation Integrity   — 关系图一致性
    WM42-03: State Evolution      — 状态变化可追踪
    WM42-04: Causality Boundary   — 因果不是简单关联
    WM42-05: Belief Separation    — World Model 不直接产生 Belief
    WM42-06: External Input Gov   — Agent 数据不能绕过验证写入
"""
import pytest
from ocos.world_model import (
    EntityType, Entity, EntityState, StateChange,
    RelationType, Relation,
    WorldEventType, WorldEvent,
    CausalityType, CausalityLink,
    Observation,
    EntityModel, RelationGraph, StateTracker,
    EventModel, CausalityEngine,
    WorldValidator, ValidationDecision, ValidationResult,
    WorldStore,
)


# ═══════════════════════════════════════════════════════════════════════════════
# WM42-01: Entity Isolation — 实体独立存在
# ═══════════════════════════════════════════════════════════════════════════════

class TestWM42_01_EntityIsolation:
    """实体应该是自包含的，不隐式依赖其他实体。"""

    def test_entity_creation_is_independent(self):
        """实体可以被独立创建，不需要预先存在其他实体。"""
        em = EntityModel()
        e = em.create_entity("test1", "Test", EntityType.CONCEPT)
        assert em.exists("test1")
        assert em.get("test1").entity_type == EntityType.CONCEPT

    def test_entity_removal_doesnt_affect_others(self):
        """移除一个实体不应影响其他实体。"""
        em = EntityModel()
        em.create_entity("a", "A", EntityType.PERSON)
        em.create_entity("b", "B", EntityType.PERSON)
        assert em.count == 2
        em.remove("a")
        assert em.count == 1
        assert em.exists("b")
        assert not em.exists("a")

    def test_type_distribution(self):
        """类型分布统计应准确。"""
        em = EntityModel()
        em.create_entity("p1", "Person1", EntityType.PERSON)
        em.create_entity("p2", "Person2", EntityType.PERSON)
        em.create_entity("t1", "Tech1", EntityType.TECHNOLOGY)
        dist = em.type_distribution
        assert dist[EntityType.PERSON] == 2
        assert dist[EntityType.TECHNOLOGY] == 1

    def test_get_by_type(self):
        """可按类型筛选实体。"""
        em = EntityModel()
        em.create_entity("a", "A", EntityType.LOCATION)
        em.create_entity("b", "B", EntityType.CONCEPT)
        assert len(em.get_by_type(EntityType.LOCATION)) == 1
        assert len(em.get_by_type(EntityType.CONCEPT)) == 1
        assert len(em.get_by_type(EntityType.PERSON)) == 0

    def test_entity_is_concrete(self):
        """具体/抽象实体区分。"""
        assert EntityType.PERSON.is_concrete
        assert EntityType.TECHNOLOGY.is_concrete
        assert not EntityType.CONCEPT.is_concrete


# ═══════════════════════════════════════════════════════════════════════════════
# WM42-02: Relation Integrity — 关系图一致性
# ═══════════════════════════════════════════════════════════════════════════════

class TestWM42_02_RelationIntegrity:
    """关系图必须保持一致（add/remove/查询）。"""

    def test_add_and_query_outgoing(self):
        rg = RelationGraph()
        rg.add_relation(Relation("r1", "a", "b", RelationType.DEPENDS_ON))
        outgoing = rg.outgoing("a")
        assert len(outgoing) == 1
        assert outgoing[0].to_entity_id == "b"

    def test_add_and_query_incoming(self):
        rg = RelationGraph()
        rg.add_relation(Relation("r1", "a", "b", RelationType.DEPENDS_ON))
        incoming = rg.incoming("b")
        assert len(incoming) == 1
        assert incoming[0].from_entity_id == "a"

    def test_remove_cleans_both_indexes(self):
        rg = RelationGraph()
        rg.add_relation(Relation("r1", "a", "b", RelationType.DEPENDS_ON))
        rg.remove("r1")
        assert rg.outgoing("a") == []
        assert rg.incoming("b") == []
        assert rg.count == 0

    def test_find_by_type(self):
        rg = RelationGraph()
        rg.add_relation(Relation("r1", "a", "b", RelationType.DEPENDS_ON))
        rg.add_relation(Relation("r2", "a", "c", RelationType.COMPETES_WITH))
        rels = rg.find_by_type(from_id="a", rel_type=RelationType.DEPENDS_ON)
        assert len(rels) == 1
        assert rels[0].relation_type == RelationType.DEPENDS_ON

    def test_neighbors(self):
        rg = RelationGraph()
        rg.add_relation(Relation("r1", "a", "b", RelationType.DEPENDS_ON))
        neighbors = rg.neighbors("a")
        assert len(neighbors) == 1
        assert neighbors[0][0] == "b"

    def test_causal_relations(self):
        rg = RelationGraph()
        rg.add_relation(Relation("r1", "a", "b", RelationType.CAUSES))
        rg.add_relation(Relation("r2", "a", "c", RelationType.DEPENDS_ON))
        causal = rg.causal_relations("a")
        assert len(causal) == 1
        assert causal[0].relation_type == RelationType.CAUSES


# ═══════════════════════════════════════════════════════════════════════════════
# WM42-03: State Evolution — 状态变化可追踪
# ═══════════════════════════════════════════════════════════════════════════════

class TestWM42_03_StateEvolution:
    """状态版本必须可追踪，包括历史查询和变更记录。"""

    def test_record_and_current(self):
        st = StateTracker()
        st.record_state(EntityState("s1", "e1", {"x": 1}))
        st.record_state(EntityState("s2", "e1", {"x": 2}))
        assert st.current("e1").get("x") == 2

    def test_history_is_chronological(self):
        st = StateTracker()
        st.record_state(EntityState("s1", "e1", {"x": 1}, tick_id=1))
        st.record_state(EntityState("s2", "e1", {"x": 2}, tick_id=2))
        st.record_state(EntityState("s3", "e1", {"x": 3}, tick_id=3))
        history = st.history("e1")
        assert len(history) == 3
        assert [h.get("x") for h in history] == [1, 2, 3]

    def test_changes_since(self):
        st = StateTracker()
        st.record_state(EntityState("s1", "e1", {"x": 1}, tick_id=1))
        st.record_state(EntityState("s2", "e1", {"x": 2}, tick_id=5))
        changes = st.changes_since("e1", since_tick=3)
        assert len(changes) >= 1

    def test_between(self):
        """between 返回指定范围内的状态。"""
        st = StateTracker()
        st.record_state(EntityState("s1", "e1", {"x": 1}, tick_id=0))
        st.record_state(EntityState("s2", "e1", {"x": 2}, tick_id=10))
        st.record_state(EntityState("s3", "e1", {"x": 3}, tick_id=20))
        # at_tick(5) should return s1
        s = st.at_tick("e1", 5)
        assert s is not None
        assert s.get("x") == 1

    def test_changed_keys(self):
        st = StateTracker()
        st.record_state(EntityState("s1", "e1", {"a": 1, "b": "ok"}, tick_id=1))
        st.record_state(EntityState("s2", "e1", {"a": 2, "b": "ok"}, tick_id=2))
        st.record_state(EntityState("s3", "e1", {"a": 2, "b": "changed"}, tick_id=3))
        keys = st.changed_keys("e1")
        assert "a" in keys
        assert "b" in keys


# ═══════════════════════════════════════════════════════════════════════════════
# WM42-04: Causality Boundary — 因果不是简单关联
# ═══════════════════════════════════════════════════════════════════════════════

class TestWM42_04_CausalityBoundary:
    """因果必须基于证据，不是简单关联。"""

    def test_add_link_and_query_causes(self):
        ce = CausalityEngine()
        ce.add_link(CausalityLink(
            link_id="l1",
            cause_event_id="e1",
            effect_event_id="e2",
            causality_type=CausalityType.DIRECT,
            confidence=0.9,
            evidence_ids=("ev1", "ev2"),
        ))
        causes = ce.causes_of("e2")
        assert len(causes) == 1
        assert causes[0].cause_event_id == "e1"

    def test_effects_of(self):
        ce = CausalityEngine()
        ce.add_link(CausalityLink("l1", "e1", "e2", CausalityType.DIRECT))
        effects = ce.effects_of("e1")
        assert len(effects) == 1

    def test_chain(self):
        """因果链 A→B→C 可追踪。"""
        ce = CausalityEngine()
        ce.add_link(CausalityLink("l1", "e1", "e2", CausalityType.DIRECT, confidence=0.9))
        ce.add_link(CausalityLink("l2", "e2", "e3", CausalityType.DIRECT, confidence=0.8))
        chain = ce.causal_chain("e1")
        assert len(chain) == 2
        assert chain[0].link_id == "l1"
        assert chain[1].link_id == "l2"

    def test_contested(self):
        """有反例的因果链应被标记。"""
        ce = CausalityEngine()
        ce.add_link(CausalityLink(
            "l1", "e1", "e2", CausalityType.DIRECT,
            counter_evidence_ids=("c1",),
        ))
        assert len(ce.contested()) == 1

    def test_upstream_chain(self):
        """向上追溯原因链。"""
        ce = CausalityEngine()
        ce.add_link(CausalityLink("l1", "e1", "e2", CausalityType.DIRECT, confidence=0.9))
        ce.add_link(CausalityLink("l2", "e2", "e3", CausalityType.DIRECT, confidence=0.8))
        upstream = ce.upstream_chain("e3")
        assert len(upstream) == 2
        assert upstream[0].link_id == "l1"
        assert upstream[1].link_id == "l2"


# ═══════════════════════════════════════════════════════════════════════════════
# WM42-05: Belief Separation — World Model 不直接产生 Belief
# ═══════════════════════════════════════════════════════════════════════════════

class TestWM42_05_BeliefSeparation:
    """World Model 是结构表示，不包含 Belief 判断。"""

    def test_world_store_has_no_belief_text(self):
        """WorldStore 不应该有 belief_* 属性/方法。"""
        ws = WorldStore()
        assert not hasattr(ws, "belief_level")
        assert not hasattr(ws, "belief_confidence")

    def test_entity_has_no_belief(self):
        """Entity 没有 belief 属性。"""
        e = Entity("e1", "Test", EntityType.CONCEPT)
        assert not hasattr(e, "belief_level")

    def test_relation_has_no_truth_judgment(self):
        """Relation 只有 type/weight，没有 truth 判断。"""
        r = Relation("r1", "a", "b", RelationType.DEPENDS_ON)
        assert "truth" not in r.__dict__

    def test_state_is_just_attributes(self):
        """State 只是属性快照，不包含 belief。"""
        s = EntityState("s1", "e1", {"x": 1})
        assert "belief" not in s.attributes


# ═══════════════════════════════════════════════════════════════════════════════
# WM42-06: External Input Governance — Agent 不能绕过验证
# ═══════════════════════════════════════════════════════════════════════════════

class TestWM42_06_ExternalInputGovernance:
    """外部输入必须经过 Observation→Validation→World Update 流水线。"""

    def test_unknown_source_rejected(self):
        ws = WorldStore()
        ws.validator.trusted_sources = {"trusted_agent"}
        obs = Observation(
            observation_id="o1",
            source="untrusted_agent",
            entity_id="evil",
        )
        result = ws.update_from_observation(obs)
        assert not result.accepted

    def test_trusted_source_accepted(self):
        ws = WorldStore()
        ws.validator.trusted_sources = {"my_agent"}
        obs = Observation(
            observation_id="o1",
            source="my_agent",
            entity_id="good",
            claimed_state=EntityState("st", "good", {"progress": 0.5}),
        )
        result = ws.update_from_observation(obs)
        assert result.accepted
        assert ws.entities.exists("good")

    def test_empty_observation_rejected(self):
        """空观察应被拒接。"""
        ws = WorldStore()
        obs = Observation(
            observation_id="o1",
            source="someone",
            # no entity_id, no relation, no state
        )
        result = ws.validator.validate_observation(obs)
        assert not result.accepted

    def test_multiple_sources_recorded(self):
        ws = WorldStore()
        ws.validator.trusted_sources = {"a1"}
        obs1 = Observation("o1", "a1", "e1",
                           claimed_state=EntityState("st1", "e1", {"x": 1}))
        obs2 = Observation("o2", "a1", "e2",
                           claimed_state=EntityState("st2", "e2", {"x": 2}))
        ws.update_from_observation(obs1)
        ws.update_from_observation(obs2)
        assert ws.entities.count == 2

    def test_observation_with_relation(self):
        ws = WorldStore()
        ws.validator.trusted_sources = {"a1"}
        obs = Observation(
            observation_id="o1",
            source="a1",
            entity_id="parent",
            claimed_relation=Relation("r1", "parent", "child", RelationType.CONTAINS),
        )
        result = ws.update_from_observation(obs)
        assert result.accepted
        assert ws.relations.count == 1
