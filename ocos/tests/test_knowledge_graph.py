"""Phase S: KnowledgeGraph 单元测试。"""

import time

import pytest

from ocos.knowledge import (
    KnowledgeGraph,
    KnowledgeGraphManager,
    Entity,
    Relation,
    Fact,
    EntityType,
    RelationType,
)


class TestEntity:
    """Entity 测试。"""

    def test_create(self):
        e = Entity(
            entity_id="e1",
            name="Alice",
            entity_type=EntityType.PERSON,
            confidence=0.9,
        )
        assert e.name == "Alice"
        assert e.confidence == 0.9
        assert e.source_count == 1

    def test_update_confidence(self):
        e = Entity("e1", "Alice", EntityType.PERSON)
        e.update_confidence(0.8, weight=0.5)
        assert e.confidence == 0.9  # 0.5*1.0 + 0.5*0.8
        assert e.source_count == 2


class TestRelation:
    """Relation 测试。"""

    def test_create(self):
        r = Relation(
            relation_id="r1",
            subject_id="e1",
            predicate=RelationType.KNOWS,
            object_id="e2",
        )
        assert r.predicate == RelationType.KNOWS
        assert r.confidence == 1.0

    def test_update_confidence(self):
        r = Relation("r1", "e1", RelationType.KNOWS, "e2")
        r.update_confidence(0.6, weight=0.4)
        assert r.confidence == 0.84  # 0.6*1.0 + 0.4*0.6


class TestKnowledgeGraph:
    """KnowledgeGraph 核心功能测试。"""

    def test_empty_initial_state(self):
        kg = KnowledgeGraph()
        assert kg.entity_count == 0
        assert kg.relation_count == 0

    def test_add_and_get_entity(self):
        kg = KnowledgeGraph()
        e = Entity("e1", "Alice", EntityType.PERSON)
        kg.add_entity(e)
        assert kg.entity_count == 1
        assert kg.get_entity("e1") == e

    def test_remove_entity(self):
        kg = KnowledgeGraph()
        kg.add_entity(Entity("e1", "Alice", EntityType.PERSON))
        assert kg.remove_entity("e1") is True
        assert kg.entity_count == 0
        assert kg.remove_entity("nonexistent") is False

    def test_add_and_get_relation(self):
        kg = KnowledgeGraph()
        kg.add_entity(Entity("e1", "Alice", EntityType.PERSON))
        kg.add_entity(Entity("e2", "Bob", EntityType.PERSON))
        rel = Relation("r1", "e1", RelationType.KNOWS, "e2")
        kg.add_relation(rel)
        assert kg.relation_count == 1
        assert kg.get_relation("r1") == rel

    def test_outgoing_relations(self):
        kg = KnowledgeGraph()
        kg.add_entity(Entity("e1", "Alice", EntityType.PERSON))
        kg.add_entity(Entity("e2", "Bob", EntityType.PERSON))
        kg.add_relation(Relation("r1", "e1", RelationType.KNOWS, "e2"))
        out = kg.outgoing("e1")
        assert len(out) == 1
        assert out[0].predicate == RelationType.KNOWS

    def test_incoming_relations(self):
        kg = KnowledgeGraph()
        kg.add_entity(Entity("e1", "Alice", EntityType.PERSON))
        kg.add_entity(Entity("e2", "Bob", EntityType.PERSON))
        kg.add_relation(Relation("r1", "e1", RelationType.KNOWS, "e2"))
        inc = kg.incoming("e2")
        assert len(inc) == 1
        assert inc[0].subject_id == "e1"

    def test_neighbors(self):
        kg = KnowledgeGraph()
        kg.add_entity(Entity("e1", "Alice", EntityType.PERSON))
        kg.add_entity(Entity("e2", "Bob", EntityType.PERSON))
        kg.add_relation(Relation("r1", "e1", RelationType.KNOWS, "e2"))
        neighs = kg.neighbors("e1")
        assert len(neighs) == 1
        assert neighs[0][0] == "e2"

    def test_find_by_name(self):
        kg = KnowledgeGraph()
        kg.add_entity(Entity("e1", "Alice", EntityType.PERSON))
        kg.add_entity(Entity("e2", "Bob", EntityType.PERSON))
        results = kg.find_by_name("alice")
        assert len(results) == 1
        assert results[0].name == "Alice"

    def test_resolve_entity(self):
        kg = KnowledgeGraph()
        kg.add_entity(Entity("e1", "Alice", EntityType.PERSON, confidence=0.9))
        kg.add_entity(Entity("e2", "Alice Smith", EntityType.PERSON, confidence=0.7))
        resolved = kg.resolve_entity("alice")
        assert resolved == "e1"  # 高置信度优先

    def test_infer_relations(self):
        kg = KnowledgeGraph()
        kg.add_entity(Entity("e1", "A", EntityType.PERSON))
        kg.add_entity(Entity("e2", "B", EntityType.PERSON))
        kg.add_entity(Entity("e3", "C", EntityType.PERSON))
        kg.add_relation(Relation("r1", "e1", RelationType.KNOWS, "e2"))
        kg.add_relation(Relation("r2", "e2", RelationType.KNOWS, "e3"))
        inferred = kg.infer_relations("e1", depth=2)
        ids = [n[0] for n in inferred]
        assert "e2" in ids
        assert "e3" in ids

    def test_find_relations_filter(self):
        kg = KnowledgeGraph()
        kg.add_entity(Entity("e1", "A", EntityType.PERSON))
        kg.add_entity(Entity("e2", "B", EntityType.PERSON))
        kg.add_relation(Relation("r1", "e1", RelationType.KNOWS, "e2"))
        kg.add_relation(Relation("r2", "e1", RelationType.WORKS_AT, "e2"))
        knows = kg.find_relations(predicate=RelationType.KNOWS)
        assert len(knows) == 1
        assert knows[0].predicate == RelationType.KNOWS

    def test_stats(self):
        kg = KnowledgeGraph()
        kg.add_entity(Entity("e1", "Alice", EntityType.PERSON))
        kg.add_entity(Entity("e2", "Bob", EntityType.ORGANIZATION))
        kg.add_relation(Relation("r1", "e1", RelationType.WORKS_AT, "e2"))
        stats = kg.get_stats()
        assert stats["entity_count"] == 2
        assert stats["relation_count"] == 1
        assert stats["entity_types"]["PERSON"] == 1
        assert stats["entity_types"]["ORGANIZATION"] == 1

    def test_export_json(self):
        kg = KnowledgeGraph()
        kg.add_entity(Entity("e1", "Alice", EntityType.PERSON))
        json_str = kg.export_json()
        assert "Alice" in json_str
        assert "PERSON" in json_str

    def test_clear(self):
        kg = KnowledgeGraph()
        kg.add_entity(Entity("e1", "Alice", EntityType.PERSON))
        kg.clear()
        assert kg.entity_count == 0
        assert kg.relation_count == 0


class TestFact:
    """Fact 时序测试。"""

    def test_active_fact(self):
        f = Fact(
            fact_id="f1",
            subject_id="e1",
            predicate=RelationType.KNOWS,
            object_id="e2",
            valid_from=time.time(),
        )
        assert f.is_active is True

    def test_expired_fact(self):
        f = Fact(
            fact_id="f1",
            subject_id="e1",
            predicate=RelationType.KNOWS,
            object_id="e2",
            valid_from=time.time() - 1000,
            valid_until=time.time() - 100,
        )
        assert f.is_active is False


class TestKnowledgeGraphManager:
    """KnowledgeGraphManager 测试。"""

    def test_create(self):
        mgr = KnowledgeGraphManager()
        assert mgr.graph.entity_count == 0

    def test_add_entity(self):
        mgr = KnowledgeGraphManager()
        eid = mgr.add_entity("Alice", EntityType.PERSON)
        assert eid is not None
        assert mgr.graph.entity_count == 1
        entity = mgr.get_entity(eid)
        assert entity is not None
        assert entity.name == "Alice"

    def test_add_relation(self):
        mgr = KnowledgeGraphManager()
        e1 = mgr.add_entity("Alice", EntityType.PERSON)
        e2 = mgr.add_entity("Bob", EntityType.PERSON)
        rid = mgr.add_relation(e1, RelationType.KNOWS, e2)
        assert rid is not None
        assert mgr.graph.relation_count == 1

    def test_search_entities(self):
        mgr = KnowledgeGraphManager()
        mgr.add_entity("Alice", EntityType.PERSON)
        mgr.add_entity("Bob", EntityType.PERSON)
        results = mgr.search_entities("alice")
        assert len(results) == 1
        assert results[0].name == "Alice"

    def test_learn_from_text_no_extractor(self):
        mgr = KnowledgeGraphManager()
        result = mgr.learn_from_text("Alice knows Bob")
        assert result.confidence == 0.0

    def test_stats(self):
        mgr = KnowledgeGraphManager()
        mgr.add_entity("Alice", EntityType.PERSON)
        stats = mgr.get_stats()
        assert stats["entity_count"] == 1
        assert isinstance(stats["uptime_seconds"], float)

    def test_generate_report(self):
        mgr = KnowledgeGraphManager()
        mgr.add_entity("Alice", EntityType.PERSON)
        report = mgr.generate_report()
        assert "知识图谱报告" in report
        assert "实体数: 1" in report

    def test_clear(self):
        mgr = KnowledgeGraphManager()
        mgr.add_entity("Alice", EntityType.PERSON)
        mgr.clear()
        assert mgr.graph.entity_count == 0
