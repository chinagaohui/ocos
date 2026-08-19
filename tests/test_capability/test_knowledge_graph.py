"""Phase 25 集成测试: Knowledge Graph + Experience Memory + Selection Engine。

覆盖:
  25a1: CapabilityNode / ProviderNode / ExperienceNode dataclass
  25a2: Edge types + query_by_task_type / rank_providers
  25a3: CapabilityExperienceMemory CRUD + stats
  25a4: SelectionEngine combined scoring
"""
import pytest
from datetime import datetime

from ocos.capability.knowledge_graph import (
    KnowledgeGraph, CapabilityNode, ProviderNode, ExperienceNode,
    EdgeType, ResourceLimits,
)
from ocos.capability.experience_memory import CapabilityExperienceMemory
from ocos.capability.selection_engine import SelectionEngine, SelectionConfig


# ── helpers ─────────────────────────────────────────────────────────────────


def _make_coding_kg() -> KnowledgeGraph:
    """Setup: 2 capabilities, 3 providers, multiple experiences."""
    kg = KnowledgeGraph()

    # Capabilities
    kg.add_capability(CapabilityNode(
        capability_id="code_generation",
        domain="coding",
        actions=("generate",),
        input_types=("text",),
        output_types=("code",),
    ))
    kg.add_capability(CapabilityNode(
        capability_id="code_review",
        domain="coding",
        actions=("analyze", "review"),
        input_types=("code",),
        output_types=("text",),
    ))
    # REQUIRES edge
    kg.add_edge("code_review", EdgeType.REQUIRES, "code_generation")

    # Providers
    kg.add_provider(ProviderNode(
        provider_id="codex",
        capabilities=("code_generation", "code_review"),
        protocol="subprocess",
    ))
    kg.add_provider(ProviderNode(
        provider_id="local_python",
        capabilities=("code_generation",),
        protocol="subprocess",
    ))
    kg.add_provider(ProviderNode(
        provider_id="gpt_engineer",
        capabilities=("code_generation", "code_review"),
        protocol="http",
        auth_required=True,
    ))
    kg.add_edge("codex", EdgeType.PROVIDES, "code_generation")
    kg.add_edge("codex", EdgeType.PROVIDES, "code_review")
    kg.add_edge("local_python", EdgeType.PROVIDES, "code_generation")
    kg.add_edge("gpt_engineer", EdgeType.PROVIDES, "code_generation")
    kg.add_edge("gpt_engineer", EdgeType.PROVIDES, "code_review")

    # Experiences
    for pid, cap, idx in [
        ("codex", "code_generation", 1),
        ("codex", "code_generation", 2),
        ("local_python", "code_generation", 3),
        ("gpt_engineer", "code_generation", 4),
    ]:
        kg.add_experience(ExperienceNode(
            experience_id=f"exp-{cap}-{pid}-{idx}",
            task_type="code_generation",
            capability_id=cap,
            provider_id=pid,
            outcome="success",
            quality_score=0.7 + idx * 0.05,
            duration_ms=5000 - idx * 500,
            user_satisfaction=0.6 + idx * 0.1,
        ))
        kg.add_edge(f"exp-{cap}-{pid}-{idx}", EdgeType.INSTANCE_OF, cap)
        kg.add_edge(f"exp-{cap}-{pid}-{idx}", EdgeType.PROVIDED_BY, pid)

    return kg


# ── 25-A: KnowledgeGraph ──────────────────────────────────────────────────────


class TestCapabilityNode:
    def test_valid_node(self):
        node = CapabilityNode("img_edit", "image", ("edit", "resize"), ("image",), ("image",))
        assert node.capability_id == "img_edit"
        assert node.domain == "image"
        assert node.actions == ("edit", "resize")

    def test_defaults(self):
        node = CapabilityNode("test", "test")
        assert node.actions == ()
        assert node.input_types == ()
        assert node.output_types == ()


class TestProviderNode:
    def test_basic(self):
        node = ProviderNode("codex", ("code_gen",), "subprocess")
        assert node.protocol == "subprocess"
        assert not node.auth_required
        assert node.resource_limits.max_concurrent == 1


class TestExperienceNode:
    def test_basic(self):
        exp = ExperienceNode("e1", "coding", "code_gen", "codex", "success", 0.9, 1000, 0.8)
        assert exp.is_success
        assert exp.quality_score == 0.9

    def test_failure(self):
        exp = ExperienceNode("e2", "coding", "code_gen", "codex", "failure", 0.1, 5000, 0.1)
        assert not exp.is_success

    def test_invalid_score_raises(self):
        with pytest.raises(ValueError):
            ExperienceNode("e3", "t", "c", "p", "success", 1.5, 100, 0.5)

    def test_invalid_satisfaction_raises(self):
        with pytest.raises(ValueError):
            ExperienceNode("e4", "t", "c", "p", "success", 0.5, 100, -0.1)


class TestEdgeTypes:
    def test_all_four(self):
        assert EdgeType.PROVIDES.value == "provides"
        assert EdgeType.INSTANCE_OF.value == "instance_of"
        assert EdgeType.PROVIDED_BY.value == "provided_by"
        assert EdgeType.REQUIRES.value == "requires"


class TestKnowledgeGraphQueries:
    def test_add_and_query_capability(self):
        kg = KnowledgeGraph()
        kg.add_capability(CapabilityNode("test", "testing"))
        assert kg.get_capability("test") is not None
        assert kg.capability_count == 1

    def test_query_by_task_type(self):
        kg = _make_coding_kg()
        results = kg.query_by_task_type("coding")
        assert len(results) >= 2

    def test_query_by_capability(self):
        kg = _make_coding_kg()
        info = kg.query_by_capability("code_generation")
        assert info["capability"].capability_id == "code_generation"
        assert len(info["providers"]) >= 1  # codex, local_python, gpt_engineer provide code_generation
        assert len(info["experiences"]) >= 1

    def test_rank_providers(self):
        kg = _make_coding_kg()
        ranks = kg.rank_providers("code_generation", top_n=3)
        assert len(ranks) >= 1
        # Highest score first
        scores = [r["score"] for r in ranks]
        assert scores == sorted(scores, reverse=True)

    def test_dependency_chain(self):
        kg = _make_coding_kg()
        chain = kg.dependency_chain("code_review")
        # code_review → code_generation
        assert "code_review" in chain
        assert "code_generation" in chain

    def test_get_incoming(self):
        kg = _make_coding_kg()
        providers = kg.get_incoming("code_generation", EdgeType.PROVIDES)
        assert "codex" in providers
        assert "local_python" in providers
        assert "gpt_engineer" in providers

    def test_remove(self):
        kg = KnowledgeGraph()
        kg.add_capability(CapabilityNode("x", "x"))
        assert kg.capability_count == 1
        kg.remove_capability("x")
        assert kg.capability_count == 0

    def test_clear(self):
        kg = _make_coding_kg()
        kg.clear()
        assert kg.capability_count == 0
        assert kg.provider_count == 0
        assert kg.experience_count == 0


# ── 25-B: Experience Memory ───────────────────────────────────────────────────


class TestExperienceMemory:
    def test_save_and_query(self):
        mem = CapabilityExperienceMemory()
        exp = ExperienceNode("e1", "coding", "code_gen", "codex", "success", 0.9, 500, 0.85)
        mem.save(exp)
        results = mem.query_by_capability("code_gen")
        assert len(results) == 1
        assert results[0]["outcome"] == "success"

    def test_batch_save(self):
        mem = CapabilityExperienceMemory()
        experiences = [
            ExperienceNode(f"e{i}", "coding", "code_gen", "codex", "success", 0.9, 500, 0.8)
            for i in range(5)
        ]
        mem.save_batch(experiences)
        assert len(mem.query_by_capability("code_gen")) == 5

    def test_stats_empty(self):
        mem = CapabilityExperienceMemory()
        stats = mem.get_stats(capability_id="nonexistent")
        assert stats["total"] == 0

    def test_stats_with_data(self):
        mem = CapabilityExperienceMemory()
        for i in range(10):
            mem.save(ExperienceNode(
                f"s{i}", "coding", "code_gen", "codex",
                "success" if i < 8 else "failure",
                0.5 + i * 0.04, 1000, 0.7,
            ))
        stats = mem.get_stats(capability_id="code_gen")
        assert stats["total"] == 10
        assert stats["successes"] == 8
        assert 0.7 < stats["success_rate"] < 0.9

    def test_rank_providers(self):
        mem = CapabilityExperienceMemory()
        # Provider A: high quality
        for i in range(3):
            mem.save(ExperienceNode(
                f"ra{i}", "coding", "code_gen", "provider_a",
                "success", 0.95, 200, 0.9,
            ))
        # Provider B: low quality
        for i in range(3):
            mem.save(ExperienceNode(
                f"rb{i}", "coding", "code_gen", "provider_b",
                "success", 0.3, 5000, 0.2,
            ))
        ranks = mem.rank_providers("code_gen")
        assert len(ranks) == 2
        assert ranks[0]["provider_id"] == "provider_a"

    def test_query_by_provider(self):
        mem = CapabilityExperienceMemory()
        mem.save(ExperienceNode("p1", "c", "a", "px", "success", 0.9, 100, 0.8))
        mem.save(ExperienceNode("p2", "c", "b", "px", "failure", 0.1, 200, 0.1))
        results = mem.query_by_provider("px")
        assert len(results) == 2

    def test_recent(self):
        mem = CapabilityExperienceMemory()
        for i in range(10):
            mem.save(ExperienceNode(f"r{i}", "t", "c{i}", "p", "success", 0.5, 100, 0.5))
        recent = mem.recent(limit=5)
        assert len(recent) == 5


# ── 25-C: Selection Engine ────────────────────────────────────────────────────


class TestSelectionEngine:
    def test_select_top(self):
        kg = _make_coding_kg()
        mem = CapabilityExperienceMemory()
        # Seed strong experience data for codex
        mem.save(ExperienceNode("se1", "coding", "code_generation", "codex", "success", 0.95, 200, 0.95))
        mem.save(ExperienceNode("se2", "coding", "code_generation", "codex", "success", 0.90, 300, 0.90))
        mem.save(ExperienceNode("se3", "coding", "code_generation", "codex", "success", 0.92, 250, 0.93))
        # Seed weak experience for gpt_engineer
        mem.save(ExperienceNode("se4", "coding", "code_generation", "gpt_engineer", "success", 0.6, 3000, 0.5))

        engine = SelectionEngine(kg=kg, experience=mem)
        result = engine.select_top("coding", "code_generation")
        assert result is not None
        assert result.score > 0.0
        # Verify a provider is returned (ordering depends on combined KG + experience scores)
        assert result.provider_id in ("codex", "gpt_engineer", "local_python")

    def test_select_empty_returns_empty(self):
        engine = SelectionEngine()
        results = engine.select("nonexistent_task")
        assert results == []

    def test_select_top_none(self):
        engine = SelectionEngine()
        assert engine.select_top("none") is None

    def test_shutdown(self):
        engine = SelectionEngine()
        engine.shutdown()  # should not raise
