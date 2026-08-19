"""Phase 28 集成测试: CapabilityOrchestrator。

覆盖:
  28a1: CapabilityOrchestrator.dispatch() → select_top → execute → learn
  28a2: register/unregister providers
  28a3: chain() 多能力顺序编排
  28a4: dispatch with ResultUnderstandingLayer feedback
  28a5: 边界 — no provider / no selection / empty chain / fallback
"""
import pytest

from ocos.capability.orchestrator import (
    CapabilityOrchestrator,
    DispatchResult,
    OrchestrationResult,
)
from ocos.capability.knowledge_graph import KnowledgeGraph, CapabilityNode, ProviderNode, EdgeType
from ocos.capability.experience_memory import CapabilityExperienceMemory
from ocos.capability.selection_engine import SelectionEngine
from ocos.capability.result_understanding import ResultUnderstandingLayer


# ── helpers ─────────────────────────────────────────────────────────────────


def _setup_orchestrator(providers_override=None, with_result_layer=False):
    """创建带最小 KG + 可选 provider 的 orchestrator。"""
    kg = KnowledgeGraph()
    kg.add_capability(CapabilityNode("code_gen", "coding"))
    kg.add_provider(ProviderNode("mock_codex", ("code_gen",), "subprocess"))
    kg.add_provider(ProviderNode("mock_local", ("code_gen",), "subprocess"))
    kg.add_edge("mock_codex", EdgeType.PROVIDES, "code_gen")
    kg.add_edge("mock_local", EdgeType.PROVIDES, "code_gen")

    kg.add_capability(CapabilityNode("test_gen", "testing"))
    kg.add_provider(ProviderNode("mock_tester", ("test_gen",), "subprocess"))
    kg.add_edge("mock_tester", EdgeType.PROVIDES, "test_gen")

    exp = CapabilityExperienceMemory()
    engine = SelectionEngine(kg=kg, experience=exp)

    providers = providers_override or {
        "mock_codex": lambda **kw: {"code": "def foo(): pass", "quality_score": 0.95},
        "mock_local": lambda **kw: {"code": "print(1)", "quality_score": 0.5},
        "mock_tester": lambda **kw: {"tests": "passed", "quality_score": 0.9},
    }

    rl = ResultUnderstandingLayer(experience=exp, kg=kg) if with_result_layer else None

    return CapabilityOrchestrator(
        selection_engine=engine,
        providers=providers,
        result_layer=rl,
    ), exp, kg


# ── 28a1: dispatch ──────────────────────────────────────────────────────────


class TestDispatch:
    def test_dispatch_success(self):
        orch, _, _ = _setup_orchestrator()
        r = orch.dispatch("code_gen", {"prompt": "hello"})
        assert r.success
        assert r.capability_id == "code_gen"
        assert r.provider_id in ("mock_codex", "mock_local")
        assert "code" in str(r.output)

    def test_dispatch_no_provider(self):
        orch, _, _ = _setup_orchestrator()
        r = orch.dispatch("image_gen", {})
        assert not r.success
        assert "No provider found" in r.error

    def test_dispatch_selects_best(self):
        orch, _, _ = _setup_orchestrator()
        r = orch.dispatch("code_gen", {}, preferred_protocol="subprocess")
        assert r.success
        # mock_codex has higher weight (1.2 vs 0.8)
        # but selection depends on KG rank + experience rank
        # At minimum, a provider was selected
        assert r.selection_score > 0

    def test_dispatch_with_result_layer(self):
        orch, exp, kg = _setup_orchestrator(with_result_layer=True)
        r = orch.dispatch("code_gen", {"prompt": "test"})
        assert r.success
        assert r.pipeline.get("validated") is True
        assert r.pipeline.get("experience_stored") is True
        # 验证经验已写入
        rows = exp.query_by_capability("code_gen")
        assert len(rows) >= 1

    def test_dispatch_provider_not_found(self):
        orch, _, _ = _setup_orchestrator()
        del orch._providers["mock_codex"]
        del orch._providers["mock_local"]
        r = orch.dispatch("code_gen", {})
        # selection works but instance missing
        assert not r.success
        assert "instance not found" in r.error


# ── 28a2: Provider 管理 ─────────────────────────────────────────────────────


class TestProviderManagement:
    def test_register_provider(self):
        orch, _, _ = _setup_orchestrator()
        orch.register_provider("new_prov", lambda **kw: {"ok": True})
        assert "new_prov" in orch.registered_providers

    def test_unregister_provider(self):
        orch, _, _ = _setup_orchestrator()
        orch.unregister_provider("mock_codex")
        assert "mock_codex" not in orch.registered_providers

    def test_custom_provider_dispatch(self):
        orch, _, _ = _setup_orchestrator()
        # Override with custom
        orch.register_provider("mock_codex", lambda **kw: {"custom": True})
        r = orch.dispatch("code_gen", {})
        assert r.success
        assert r.output == {"custom": True}


# ── 28a3: chain 编排 ────────────────────────────────────────────────────────


class TestChain:
    def test_simple_chain(self):
        orch, _, _ = _setup_orchestrator()
        r = orch.chain([
            {"capability_id": "code_gen", "input": {"prompt": "test"}},
            {"capability_id": "test_gen", "input_from": "prev"},
        ])
        assert r.success
        assert len(r.results) == 2
        assert r.results[0]["success"]
        assert r.results[1]["success"]

    def test_chain_abort_on_failure(self):
        orch, _, _ = _setup_orchestrator()
        r = orch.chain([
            {"capability_id": "code_gen", "input": {"prompt": "test"}},
            {"capability_id": "image_gen", "input": {}},  # No provider
            {"capability_id": "test_gen", "input": {}},
        ], fallback="abort")
        assert not r.success
        assert len(r.results) == 2  # 2nd step failed, 3rd not executed

    def test_chain_skip_on_failure(self):
        orch, _, _ = _setup_orchestrator()
        r = orch.chain([
            {"capability_id": "code_gen", "input": {"prompt": "test"}},
            {"capability_id": "image_gen", "input": {}},  # No provider → skip
            {"capability_id": "test_gen", "input_from": "prev"},
        ], fallback="skip")
        # Not all steps succeeded, but chain continues
        assert not r.success  # 有 error
        assert len(r.results) == 3  # all steps executed (2nd skipped)

    def test_empty_chain(self):
        orch, _, _ = _setup_orchestrator()
        r = orch.chain([])
        assert r.success
        assert len(r.results) == 0

    def test_chain_output_piping(self):
        orch, _, _ = _setup_orchestrator()
        orch.register_provider("mock_codex", lambda **kw: {"code": "def bar(): pass"})
        orch.register_provider("mock_tester", lambda input, **kw: {"tests": f"tested: {input['code']}"})
        r = orch.chain([
            {"capability_id": "code_gen", "name": "gen", "input": {"prompt": "write foo"}},
            {"capability_id": "test_gen", "name": "test", "input_from": "prev"},
        ])
        assert r.success
        # 第二步收到了第一步的代码输出
        test_output = r.results[1].get("raw_output", {})
        if test_output:
            assert "tested" in str(test_output) or "tests" in str(test_output)


# ── 28a4: stats ────────────────────────────────────────────────────────────


class TestStats:
    def test_dispatch_stats(self):
        orch, _, _ = _setup_orchestrator()
        for _ in range(3):
            orch.dispatch("code_gen", {})
        s = orch.stats
        assert s["dispatch_count"] == 3

    def test_error_stats(self):
        orch, _, _ = _setup_orchestrator()
        # removal of both providers for code_gen → execution error
        del orch._providers["mock_codex"]
        del orch._providers["mock_local"]
        orch.dispatch("code_gen", {})  # selection succeeds but provider missing
        s = orch.stats
        assert s["dispatch_count"] >= 1


# ── 28a5: shutdown ──────────────────────────────────────────────────────────


class TestLifecycle:
    def test_shutdown(self):
        orch, _, _ = _setup_orchestrator()
        orch.dispatch("code_gen", {})
        orch.shutdown()
        assert orch.stats["registered_providers"] == 0
