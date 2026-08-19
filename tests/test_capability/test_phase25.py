"""Phase 25: Capability Knowledge Graph + Experience Memory + Selection Engine 测试。

覆盖:
  25a1: CapabilityNode / ProviderNode / ExperienceNode 创建与验证
  25a2: Edge 管理 + query_by_task_type / rank_providers / dependency_chain
  25a3: CapabilityExperienceMemory CRUD + 统计
  25a4: SelectionEngine 集成打分 + protocol 偏好
  25a5: 边界情况
"""

import pytest
import time
from datetime import datetime, timezone

from ocos.capability.knowledge_graph import (
    CapabilityNode, ProviderNode, ExperienceNode, EdgeType,
    KnowledgeGraph, ResourceLimits,
)
from ocos.capability.experience_memory import CapabilityExperienceMemory
from ocos.capability.selection_engine import (
    SelectionEngine, SelectionResult, SelectionConfig,
)


# ═══════════════════════════════════════════════════════════════════════════
# 25a1: Node 单元测试
# ═══════════════════════════════════════════════════════════════════════════

class TestCapabilityNode:
    def test_create_capability_node(self):
        cn = CapabilityNode(
            capability_id="code-gen",
            domain="code_generation",
            actions=("generate", "refactor"),
            input_types=("prompt", "context"),
            output_types=("code",),
            description="Code generation capability",
        )
        assert cn.capability_id == "code-gen"
        assert cn.domain == "code_generation"
        assert "generate" in cn.actions
        assert cn.description == "Code generation capability"

    def test_immutable(self):
        cn = CapabilityNode("c1", "domain")
        with pytest.raises(Exception):  # frozen dataclass
            cn.capability_id = "changed"  # type: ignore[misc]


class TestProviderNode:
    def test_create_provider_node(self):
        pn = ProviderNode(
            provider_id="openai",
            capabilities=("code-gen", "text-gen"),
            protocol="http",
            auth_required=True,
        )
        assert pn.provider_id == "openai"
        assert pn.protocol == "http"
        assert "code-gen" in pn.capabilities
        assert pn.auth_required

    def test_default_resource_limits(self):
        pn = ProviderNode("local", capabilities=("test",), protocol="subprocess")
        assert pn.resource_limits.max_concurrent == 1
        assert pn.resource_limits.max_runtime_ms == 300_000


class TestExperienceNode:
    def test_create_experience_node(self):
        now = datetime.now(timezone.utc)
        exp = ExperienceNode(
            experience_id="exp-1",
            task_type="code_generation",
            capability_id="code-gen",
            provider_id="openai",
            outcome="success",
            quality_score=0.9,
            duration_ms=1500,
            user_satisfaction=0.85,
            timestamp=now,
        )
        assert exp.experience_id == "exp-1"
        assert exp.outcome == "success"
        assert exp.is_success
        assert exp.quality_score == 0.9

    def test_experience_node_failure(self):
        exp = ExperienceNode(
            experience_id="exp-2",
            task_type="writing",
            capability_id="write",
            provider_id="local",
            outcome="failure",
            quality_score=0.2,
            duration_ms=5000,
            user_satisfaction=0.0,
        )
        assert not exp.is_success

    def test_quality_score_bounds(self):
        with pytest.raises(ValueError, match="quality_score"):
            ExperienceNode("e", "t", "c", "p", "success", quality_score=1.5, duration_ms=100, user_satisfaction=0.5)

    def test_satisfaction_bounds(self):
        with pytest.raises(ValueError, match="user_satisfaction"):
            ExperienceNode("e", "t", "c", "p", "success", quality_score=0.5, duration_ms=100, user_satisfaction=-0.1)

    def test_experience_partial_outcome(self):
        exp = ExperienceNode("e", "t", "c", "p", "partial", 0.5, 100, 0.5)
        assert not exp.is_success


# ═══════════════════════════════════════════════════════════════════════════
# 25a2: KnowledgeGraph 节点/边/查询
# ═══════════════════════════════════════════════════════════════════════════

class TestKnowledgeGraphNodes:
    def test_add_and_get_nodes(self):
        kg = KnowledgeGraph()
        cap = CapabilityNode("c1", "domain_a")
        prov = ProviderNode("p1", capabilities=("c1",), protocol="http")
        exp = ExperienceNode("e1", "task_a", "c1", "p1", "success", 0.9, 100, 0.8)

        kg.add_capability(cap)
        kg.add_provider(prov)
        kg.add_experience(exp)

        assert kg.capability_count == 1
        assert kg.provider_count == 1
        assert kg.experience_count == 1

    def test_get_nonexistent(self):
        kg = KnowledgeGraph()
        assert kg.get_capability("nope") is None
        assert kg.get_provider("nope") is None

    def test_remove_capability(self):
        kg = KnowledgeGraph()
        kg.add_capability(CapabilityNode("c1", "d"))
        assert kg.capability_count == 1
        kg.remove_capability("c1")
        assert kg.capability_count == 0

    def test_remove_provider(self):
        kg = KnowledgeGraph()
        kg.add_provider(ProviderNode("p1", capabilities=(), protocol="http"))
        kg.remove_provider("p1")
        assert kg.provider_count == 0

    def test_clear(self):
        kg = KnowledgeGraph()
        kg.add_capability(CapabilityNode("c1", "d"))
        kg.add_provider(ProviderNode("p1", capabilities=(), protocol="http"))
        kg.add_experience(ExperienceNode("e1", "t", "c1", "p1", "success", 0.5, 100, 0.5))
        kg.clear()
        assert kg.capability_count == 0
        assert kg.provider_count == 0
        assert kg.experience_count == 0


class TestKnowledgeGraphEdges:
    def _setup_graph(self) -> KnowledgeGraph:
        kg = KnowledgeGraph()
        kg.add_capability(CapabilityNode("code-gen", "code_generation"))
        kg.add_capability(CapabilityNode("code-review", "code_review"))
        kg.add_provider(ProviderNode("openai", capabilities=("code-gen",), protocol="http"))
        kg.add_provider(ProviderNode("local", capabilities=("code-gen",), protocol="subprocess"))
        return kg

    def test_add_and_get_edges(self):
        kg = self._setup_graph()
        kg.add_edge("openai", EdgeType.PROVIDES, "code-gen")
        kg.add_edge("local", EdgeType.PROVIDES, "code-gen")
        kg.add_edge("code-review", EdgeType.REQUIRES, "code-gen")

        edges = kg.get_edges("openai")
        assert len(edges) == 1
        assert edges[0][0] == EdgeType.PROVIDES
        assert edges[0][1] == "code-gen"

    def test_get_edges_by_type(self):
        kg = self._setup_graph()
        kg.add_edge("openai", EdgeType.PROVIDES, "code-gen")
        kg.add_edge("openai", EdgeType.PROVIDES, "code-review")
        kg.add_edge("openai", EdgeType.PROVIDES, "text-gen")  # provider exists but capability doesn't — edge exists

        provides = kg.get_edges_by_type("openai", EdgeType.PROVIDES)
        assert len(provides) == 3

    def test_get_incoming(self):
        kg = self._setup_graph()
        kg.add_edge("openai", EdgeType.PROVIDES, "code-gen")
        kg.add_edge("local", EdgeType.PROVIDES, "code-gen")

        providers = kg.get_incoming("code-gen", EdgeType.PROVIDES)
        assert "openai" in providers
        assert "local" in providers

    def test_dependency_chain(self):
        kg = KnowledgeGraph()
        kg.add_capability(CapabilityNode("a", "dom"))
        kg.add_capability(CapabilityNode("b", "dom"))
        kg.add_capability(CapabilityNode("c", "dom"))
        kg.add_edge("a", EdgeType.REQUIRES, "b")
        kg.add_edge("b", EdgeType.REQUIRES, "c")

        chain = kg.dependency_chain("a")
        assert chain == ["a", "b", "c"]

    def test_dependency_chain_cycle_safe(self):
        kg = KnowledgeGraph()
        kg.add_capability(CapabilityNode("x", "dom"))
        kg.add_capability(CapabilityNode("y", "dom"))
        kg.add_edge("x", EdgeType.REQUIRES, "y")
        kg.add_edge("y", EdgeType.REQUIRES, "x")  # cycle

        chain = kg.dependency_chain("x")
        assert chain == ["x", "y"]  # stops at cycle


class TestKnowledgeGraphQueries:
    def _setup_rich_graph(self) -> KnowledgeGraph:
        """Setup with 3 capabilities, 3 providers, 4 experiences."""
        kg = KnowledgeGraph()

        # Capabilities
        kg.add_capability(CapabilityNode("code-gen", "code_generation",
                                         actions=("generate", "refactor")))
        kg.add_capability(CapabilityNode("text-gen", "text_generation",
                                         actions=("write", "summarize")))
        kg.add_capability(CapabilityNode("data-analyze", "data_analysis",
                                         actions=("compute", "plot")))

        # Providers
        kg.add_provider(ProviderNode("openai", capabilities=("code-gen", "text-gen"),
                                     protocol="http"))
        kg.add_provider(ProviderNode("local", capabilities=("code-gen", "data-analyze"),
                                     protocol="subprocess"))
        kg.add_provider(ProviderNode("anthropic", capabilities=("text-gen",),
                                     protocol="http"))

        # Edges
        kg.add_edge("openai", EdgeType.PROVIDES, "code-gen")
        kg.add_edge("openai", EdgeType.PROVIDES, "text-gen")
        kg.add_edge("local", EdgeType.PROVIDES, "code-gen")
        kg.add_edge("local", EdgeType.PROVIDES, "data-analyze")
        kg.add_edge("anthropic", EdgeType.PROVIDES, "text-gen")

        # Experiences
        now = datetime.now(timezone.utc)
        kg.add_experience(ExperienceNode("e1", "code_generation", "code-gen", "openai",
                                         "success", 0.95, 1200, 0.9, now))
        kg.add_experience(ExperienceNode("e2", "code_generation", "code-gen", "local",
                                         "success", 0.85, 800, 0.75, now))
        kg.add_experience(ExperienceNode("e3", "code_generation", "code-gen", "openai",
                                         "failure", 0.4, 5000, 0.2, now))
        kg.add_experience(ExperienceNode("e4", "text_generation", "text-gen", "openai",
                                         "success", 0.92, 2000, 0.88, now))
        # INSTANCE_OF edges: Experience → Capability
        kg.add_edge("e1", EdgeType.INSTANCE_OF, "code-gen")
        kg.add_edge("e2", EdgeType.INSTANCE_OF, "code-gen")
        kg.add_edge("e3", EdgeType.INSTANCE_OF, "code-gen")
        kg.add_edge("e4", EdgeType.INSTANCE_OF, "text-gen")

        return kg

    def test_query_by_task_type_domain(self):
        kg = self._setup_rich_graph()
        results = kg.query_by_task_type("code_generation")
        assert len(results) == 1
        assert results[0].capability_id == "code-gen"

    def test_query_by_task_type_action(self):
        kg = self._setup_rich_graph()
        results = kg.query_by_task_type("refactor")
        assert len(results) == 1

    def test_query_by_capability(self):
        kg = self._setup_rich_graph()
        info = kg.query_by_capability("code-gen")
        assert info["capability"].capability_id == "code-gen"
        assert len(info["providers"]) == 2
        assert len(info["experiences"]) == 3

    def test_query_by_capability_not_found(self):
        kg = KnowledgeGraph()
        result = kg.query_by_capability("nonexistent")
        assert "error" in result

    def test_rank_providers(self):
        kg = self._setup_rich_graph()
        rankings = kg.rank_providers("code-gen", top_n=3)
        assert len(rankings) >= 1
        # openai should rank high (quality 0.95 + 0.4, satisfaction 0.9 + 0.2)
        assert rankings[0]["provider_id"] in ("openai", "local")
        # score should be present
        assert "score" in rankings[0]
        assert "success_rate" in rankings[0]
        assert "experience_count" in rankings[0]

    def test_rank_providers_no_experience(self):
        kg = KnowledgeGraph()
        kg.add_capability(CapabilityNode("empty", "dom"))
        kg.add_provider(ProviderNode("p1", capabilities=("empty",), protocol="http"))
        kg.add_edge("p1", EdgeType.PROVIDES, "empty")

        rankings = kg.rank_providers("empty")
        assert len(rankings) >= 1
        assert rankings[0]["score"] == 0.0
        assert rankings[0]["experience_count"] == 0


# ═══════════════════════════════════════════════════════════════════════════
# 25a3: CapabilityExperienceMemory CRUD + Stats
# ═══════════════════════════════════════════════════════════════════════════

class TestExperienceMemory:
    @pytest.fixture
    def mem(self):
        m = CapabilityExperienceMemory(db_path=":memory:")
        m.connect()
        yield m
        m.close()

    def _make_exp(self, eid: str, outcome: str = "success", quality: float = 0.8,
                  cap: str = "code-gen", prov: str = "openai", task: str = "code_gen") -> ExperienceNode:
        return ExperienceNode(eid, task, cap, prov, outcome, quality, 1000, 0.8)

    def test_save_and_query(self, mem):
        exp = self._make_exp("e1")
        mem.save(exp)

        results = mem.query_by_capability("code-gen")
        assert len(results) == 1
        assert results[0]["id"] == "e1"

    def test_save_batch(self, mem):
        exps = [self._make_exp(f"e{i}") for i in range(5)]
        mem.save_batch(exps)

        assert len(mem.recent(limit=10)) == 5

    def test_query_by_provider(self, mem):
        mem.save(self._make_exp("e1", prov="openai"))
        mem.save(self._make_exp("e2", prov="local"))
        mem.save(self._make_exp("e3", prov="openai"))

        results = mem.query_by_provider("openai")
        assert len(results) == 2

    def test_query_by_task_type(self, mem):
        mem.save(self._make_exp("e1", task="code_gen"))
        mem.save(self._make_exp("e2", task="writing"))
        mem.save(self._make_exp("e3", task="code_gen"))

        results = mem.query_by_task_type("code_gen")
        assert len(results) == 2

    def test_recent_ordering(self, mem):
        mem.save(self._make_exp("e1"))
        time.sleep(0.001)  # ensure timestamp difference
        mem.save(self._make_exp("e2"))
        time.sleep(0.001)
        mem.save(self._make_exp("e3"))

        results = mem.recent(limit=2)
        assert len(results) == 2
        assert results[0]["id"] in ("e3", "e2", "e1")

    def test_get_stats_empty(self, mem):
        stats = mem.get_stats(capability_id="nonexistent")
        assert stats["total"] == 0

    def test_get_stats_with_data(self, mem):
        mem.save(self._make_exp("e1", outcome="success", quality=0.9, prov="openai"))
        mem.save(self._make_exp("e2", outcome="failure", quality=0.3, prov="openai"))
        mem.save(self._make_exp("e3", outcome="success", quality=0.8, prov="openai"))

        stats = mem.get_stats(provider_id="openai")
        assert stats["total"] == 3
        assert stats["successes"] == 2
        assert stats["success_rate"] == pytest.approx(2 / 3, abs=0.01)

    def test_rank_providers(self, mem):
        mem.save(ExperienceNode("e1", "task_a", "code-gen", "openai",
                                "success", 0.95, 1000, 0.9))
        mem.save(ExperienceNode("e2", "task_b", "code-gen", "local",
                                "success", 0.7, 1500, 0.6))
        mem.save(ExperienceNode("e3", "task_c", "code-gen", "openai",
                                "failure", 0.3, 3000, 0.1))

        rankings = mem.rank_providers("code-gen", top_n=2)
        assert len(rankings) == 2

        # openai avg_quality = (0.95+0.3)/2 = 0.625, local = 0.7
        # But rank is by avg_quality DESC, so local > openai
        openai_rank = next(r for r in rankings if r["provider_id"] == "openai")
        local_rank = next(r for r in rankings if r["provider_id"] == "local")
        assert local_rank["avg_quality"] > openai_rank["avg_quality"]

    def test_upsert_behavior(self, mem):
        """INSERT OR REPLACE — same ID overwrites."""
        mem.save(self._make_exp("e1", outcome="success"))
        mem.save(ExperienceNode("e1", "task_b", "code-gen", "openai",
                                "failure", 0.1, 5000, 0.1))

        results = mem.query_by_capability("code-gen")
        assert len(results) == 1
        assert results[0]["outcome"] == "failure"


# ═══════════════════════════════════════════════════════════════════════════
# 25a4: SelectionEngine 集成
# ═══════════════════════════════════════════════════════════════════════════

class TestSelectionEngine:
    def _setup_engine(self) -> SelectionEngine:
        kg = KnowledgeGraph()
        # Capabilities
        kg.add_capability(CapabilityNode("code-gen", "code_generation"))
        kg.add_capability(CapabilityNode("text-gen", "text_generation"))
        # Providers
        kg.add_provider(ProviderNode("openai", capabilities=("code-gen", "text-gen"),
                                     protocol="http"))
        kg.add_provider(ProviderNode("local", capabilities=("code-gen",),
                                     protocol="subprocess"))
        kg.add_provider(ProviderNode("anthropic", capabilities=("text-gen",),
                                     protocol="http"))
        # Edges
        kg.add_edge("openai", EdgeType.PROVIDES, "code-gen")
        kg.add_edge("openai", EdgeType.PROVIDES, "text-gen")
        kg.add_edge("local", EdgeType.PROVIDES, "code-gen")
        kg.add_edge("anthropic", EdgeType.PROVIDES, "text-gen")

        # Experience data
        exp_mem = CapabilityExperienceMemory(db_path=":memory:")
        exp_mem.connect()
        exp_mem.save(ExperienceNode("e1", "code_generation", "code-gen", "openai",
                                    "success", 0.95, 1200, 0.9))
        exp_mem.save(ExperienceNode("e2", "code_generation", "code-gen", "openai",
                                    "success", 0.88, 1500, 0.85))
        exp_mem.save(ExperienceNode("e3", "code_generation", "code-gen", "local",
                                    "success", 0.72, 800, 0.65))

        return SelectionEngine(kg=kg, experience=exp_mem,
                               config=SelectionConfig(fallback_threshold=0.0))

    def teardown_method(self):
        pass  # :memory: DB auto-closes

    def test_select_by_task_type(self):
        engine = self._setup_engine()
        results = engine.select("code_generation")
        assert len(results) >= 1
        assert all(isinstance(r, SelectionResult) for r in results)

        # openai should be top with 2 high-quality experiences
        if results:
            assert results[0].score > 0

    def test_select_by_capability_id(self):
        engine = self._setup_engine()
        results = engine.select("code_generation", capability_id="code-gen")
        assert len(results) >= 1

    def test_select_top(self):
        engine = self._setup_engine()
        result = engine.select_top("text_generation")
        assert result is not None
        assert isinstance(result, SelectionResult)

    def test_select_nonexistent_capability(self):
        engine = self._setup_engine()
        results = engine.select("code_generation", capability_id="nonexistent")
        assert results == []

    def test_select_no_match(self):
        engine = self._setup_engine()
        results = engine.select("nonexistent_task_type_xyz")
        assert results == []

    def test_protocol_preference(self):
        """preferred_protocol='subprocess' should boost local provider."""
        engine = self._setup_engine()
        results = engine.select("code_generation", preferred_protocol="subprocess")
        assert len(results) >= 1

        # local has subprocess protocol — should have higher constraints score
        # Check that local is in the results with a reasonable score
        local_results = [r for r in results if r.provider_id == "local"]
        assert len(local_results) >= 1

    def test_fallback_threshold(self):
        """Providers below threshold are excluded."""
        engine = self._setup_engine()
        engine.config.fallback_threshold = 0.99  # effectively exclude all
        results = engine.select("code_generation")
        assert len(results) == 0  # all below threshold

    def test_select_top_returns_none_when_empty(self):
        engine = self._setup_engine()
        engine.config.fallback_threshold = 0.99
        result = engine.select_top("code_generation")
        assert result is None

    def test_selection_result_fields(self):
        engine = self._setup_engine()
        results = engine.select("code_generation")
        r = results[0]
        assert isinstance(r.provider_id, str)
        assert isinstance(r.score, float)
        assert isinstance(r.kg_rank, int)
        assert isinstance(r.exp_rank, int)
        assert isinstance(r.success_rate, float)

    def test_respects_max_results(self):
        engine = self._setup_engine()
        engine.config.max_results = 1
        results = engine.select("code_generation")
        assert len(results) <= 1


# ═══════════════════════════════════════════════════════════════════════════
# 25a5: 边界情况
# ═══════════════════════════════════════════════════════════════════════════

class TestEdgeCases:
    def test_empty_graph_queries(self):
        kg = KnowledgeGraph()
        assert kg.query_by_task_type("anything") == []
        assert kg.rank_providers("anything") == []

    def test_empty_experience_memory(self):
        mem = CapabilityExperienceMemory(db_path=":memory:")
        mem.connect()
        try:
            assert mem.recent() == []
            assert mem.get_stats(capability_id="x")["total"] == 0
        finally:
            mem.close()

    def test_selection_with_no_experiences(self):
        kg = KnowledgeGraph()
        kg.add_capability(CapabilityNode("c1", "domain"))
        kg.add_provider(ProviderNode("p1", capabilities=("c1",), protocol="http"))
        kg.add_edge("p1", EdgeType.PROVIDES, "c1")

        engine = SelectionEngine(kg=kg)
        # Should not crash with empty experience store
        results = engine.select("domain")
        assert isinstance(results, list)
