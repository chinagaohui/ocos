"""Phase 26 集成测试: ResultUnderstandingLayer。

覆盖:
  26a1: validate() → StatementValidator 扫描
  26a2: structure() → 自动提取 quality_score / user_satisfaction
  26a3: learn() → ExperienceMemory 写入 + KG 更新
  26a4: process_result() → 完整管道
  26a5: AgentRuntime._tick_step_result_ingest with pipeline
  26a6: 边界情况：空输出 / 违规输出 / 无 KG 无 Experience
"""
import pytest

from ocos.capability.result_understanding import (
    ResultUnderstanding,
    ResultUnderstandingLayer,
    StructuredResult,
    ProcessedResult,
    ExaminationResult,
)
from ocos.capability.knowledge_graph import (
    KnowledgeGraph, CapabilityNode, ProviderNode, EdgeType,
)
from ocos.capability.experience_memory import CapabilityExperienceMemory


# ── helpers ─────────────────────────────────────────────────────────────────


def _setup_layer(with_kg: bool = True, with_exp: bool = True) -> ResultUnderstandingLayer:
    kg = KnowledgeGraph() if with_kg else None
    exp = CapabilityExperienceMemory() if with_exp else None
    if kg:
        kg.add_capability(CapabilityNode("code_gen", "coding"))
        kg.add_provider(ProviderNode("codex", ("code_gen",), "subprocess"))
        kg.add_edge("codex", EdgeType.PROVIDES, "code_gen")
    return ResultUnderstandingLayer(experience=exp, kg=kg)


# ── 26-A: validate() ────────────────────────────────────────────────────────


class TestValidate:
    def test_clean_output(self):
        layer = ResultUnderstandingLayer()
        result = layer.validate("This is a code generation result.")
        assert result.passed

    def test_forbidden_person_agency(self):
        layer = ResultUnderstandingLayer()
        result = layer.validate("I think I should take control of this system.")
        assert not result.passed

    def test_forbidden_emotion(self):
        layer = ResultUnderstandingLayer()
        result = layer.validate("I feel happy and excited about this task!")
        assert not result.passed

    def test_block_on_violation(self):
        layer = ResultUnderstandingLayer(block_on_violation=True)
        result = layer.validate("I feel love for the user")  # e.g. VALUE_JUDGMENT
        # block_on_violation 不影响 validate() 的返回结果
        assert isinstance(result, ExaminationResult)


# ── 26-A: structure() ──────────────────────────────────────────────────────


class TestStructure:
    def test_basic_extraction(self):
        layer = ResultUnderstandingLayer()
        s = layer.structure(
            "generated code: print('hello')",
            capability_id="code_gen",
            provider_id="codex",
        )
        assert s.capability_id == "code_gen"
        assert s.provider_id == "codex"
        assert 0.0 <= s.quality_score <= 1.0

    def test_auto_extract_quality_score(self):
        layer = ResultUnderstandingLayer()
        s = layer.structure(
            {"content": "ok", "quality_score": 0.92},
            capability_id="cg",
            provider_id="px",
        )
        assert s.quality_score == 0.92

    def test_quality_score_clamped(self):
        layer = ResultUnderstandingLayer()
        s = layer.structure(
            {"quality": 1.5},
            capability_id="cg",
            provider_id="px",
        )
        assert s.quality_score == 1.0

    def test_content_summary_truncation(self):
        layer = ResultUnderstandingLayer()
        long_text = "x" * 300
        s = layer.structure(long_text, capability_id="cg", provider_id="px")
        assert len(s.content_summary) <= 200

    def test_structured_result_is_success(self):
        s = StructuredResult("cg", "px", outcome="success", quality_score=0.95)
        assert s.is_success
        s2 = StructuredResult("cg", "px", outcome="failure")
        assert not s2.is_success


# ── 26-A: learn() ──────────────────────────────────────────────────────────


class TestLearn:
    def test_store_to_experience(self):
        kg = KnowledgeGraph()
        kg.add_capability(CapabilityNode("test", "testing"))
        kg.add_provider(ProviderNode("tester", ("test",), "subprocess"))
        kg.add_edge("tester", EdgeType.PROVIDES, "test")
        exp = CapabilityExperienceMemory()

        layer = ResultUnderstandingLayer(experience=exp, kg=kg)
        s = StructuredResult("test", "tester", "success", 0.9, 500, 0.85, "testing")
        result = layer.learn(s)

        assert result["experience_stored"]
        assert result["kg_updated"]
        assert len(exp.query_by_capability("test")) == 1

    def test_learn_no_experience(self):
        layer = ResultUnderstandingLayer(experience=None, kg=None)
        s = StructuredResult("t", "p", "success")
        result = layer.learn(s)
        assert not result["experience_stored"]
        assert not result["kg_updated"]

    def test_learn_only_kg(self):
        kg = KnowledgeGraph()
        kg.add_capability(CapabilityNode("t", "t"))
        kg.add_provider(ProviderNode("p", ("t",), "http"))
        kg.add_edge("p", EdgeType.PROVIDES, "t")
        layer = ResultUnderstandingLayer(experience=None, kg=kg)
        s = StructuredResult("t", "p", "success")
        result = layer.learn(s)
        assert result["kg_updated"]

    def test_learn_only_experience(self):
        exp = CapabilityExperienceMemory()
        layer = ResultUnderstandingLayer(experience=exp, kg=None)
        s = StructuredResult("t", "p", "success")
        result = layer.learn(s)
        assert result["experience_stored"]
        assert not result["kg_updated"]


# ── 26-A: process_result() 完整管道 ─────────────────────────────────────────


class TestProcessResult:
    def test_full_pipeline(self):
        layer = _setup_layer()
        processed = layer.process_result(
            "Code generated successfully.",
            capability_id="code_gen",
            provider_id="codex",
            outcome="success",
            quality_score=0.95,
            duration_ms=300,
        )
        assert processed.validated
        assert processed.experience_stored
        assert processed.kg_updated
        assert processed.structured.quality_score == 0.95

    def test_pipeline_with_violations(self):
        layer = _setup_layer()
        processed = layer.process_result(
            "I feel so proud of this code I wrote!",
            capability_id="code_gen",
            provider_id="codex",
        )
        assert not processed.validated
        assert len(processed.errors) > 0
        # 结构化 + 学习仍执行（不阻断）
        assert processed.structured is not None
        assert processed.experience_stored

    def test_pipeline_auto_learn_disabled(self):
        layer = _setup_layer()
        layer._auto_learn = False
        processed = layer.process_result(
            "result",
            capability_id="code_gen",
            provider_id="codex",
        )
        assert not processed.experience_stored
        assert not processed.kg_updated

    def test_pipeline_no_backends(self):
        layer = ResultUnderstandingLayer()  # no experience, no kg
        processed = layer.process_result(
            "Clean output.",
            capability_id="none",
            provider_id="none",
        )
        assert processed.validated
        assert not processed.experience_stored
        assert not processed.kg_updated

    def test_auto_extract_from_dict(self):
        layer = _setup_layer()
        processed = layer.process_result(
            {"output": "done", "quality": 0.88, "satisfaction": 0.91},
            capability_id="code_gen",
            provider_id="codex",
            duration_ms=250,
        )
        assert processed.validated
        assert processed.structured.quality_score == 0.88
        assert processed.structured.user_satisfaction == 0.91


# ── 26-A: Phase 24-B backward compat ────────────────────────────────────────


class TestBackwardCompat:
    def test_original_result_understanding(self):
        ru = ResultUnderstanding()
        result = ru.examine("Normal output text.")
        assert result.passed

    def test_original_block_on_violation(self):
        ru = ResultUnderstanding(block_on_violation=True)
        result = ru.examine("I feel powerful.")  # violates EMOTION_STATEMENT
        assert not result.passed
        assert result.blocked


# ── 26-B: AgentRuntime integration ──────────────────────────────────────────


class TestAgentRuntimeIntegration:
    def test_runtime_has_layer_property(self):
        from unittest.mock import MagicMock
        from ocos.agent.agent_runtime import AgentRuntime

        agent = MagicMock()
        rt = AgentRuntime(agent, max_cycles=1)
        layer = rt.result_understanding_layer
        assert layer is not None
        assert isinstance(layer, ResultUnderstandingLayer)

    def test_tick_step_result_ingest(self):
        from unittest.mock import MagicMock
        from ocos.agent.agent_runtime import AgentRuntime

        agent = MagicMock()
        rt = AgentRuntime(agent, max_cycles=1)
        rt.boot()
        result = rt._tick_step_result_ingest()
        assert result["step"] == 9
        # Phase 32: cursor-based ingest, no results queued yet → ingested=False
        assert result["name"] == "result_ingest"
        assert "ingested" in result
