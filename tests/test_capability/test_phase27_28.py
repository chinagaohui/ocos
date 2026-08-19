"""Phase 27-28: Capability Sovereignty Freeze + Agent Ecosystem 接入 测试。

Phase 27: 参考实现验证 (echo_agent)
Phase 28: Custom Agent 模板 + Provider 集成
"""

import pytest

# ── Phase 27: echo_agent ──────────────────────────────────────────────

from ocos.capability.echo_agent import EchoAgent


class TestEchoAgent:
    """27a7: echo_agent 参考实现。"""

    def test_create_and_execute(self):
        agent = EchoAgent()
        result = agent.execute(prompt="hello world")
        assert result["output"] == "Echo: hello world"
        assert "prompt" in result["echoed_keys"]

    def test_custom_prefix(self):
        agent = EchoAgent(prefix="Test")
        result = agent.execute(text="data")
        assert result["output"] == "Test: data"

    def test_execute_no_recognized_key(self):
        agent = EchoAgent()
        result = agent.execute(x=1, y=2, z=3)
        assert "received keys" in result["output"]
        assert "x" in result["output"]

    def test_execute_empty_value(self):
        agent = EchoAgent()
        result = agent.execute(prompt="", text="valid")
        # Should skip empty prompt and use text
        assert result["output"] == "Echo: valid"

    def test_no_ocos_import(self):
        """EchoAgent 不 import OCOS 内部模块（单向依赖）。"""
        import inspect
        source = inspect.getsource(EchoAgent)
        # 搜索 import 语句，确认没有 import ocos (除了 __future__)
        import_lines = [l.strip() for l in source.split("\n")
                        if l.strip().startswith("import ") or l.strip().startswith("from ")]
        ocos_imports = [l for l in import_lines if "ocos" in l]
        # 允许 from __future__ import annotations
        non_future = [l for l in ocos_imports if "__future__" not in l]
        assert len(non_future) == 0, f"EchoAgent should not import ocos: {non_future}"


# ── Phase 28: custom_agent_template ──────────────────────────────────

from ocos.capability.custom_agent_template import AgentProvider


class MockAgent(AgentProvider):
    """用于测试的 mock agent。"""
    def execute(self, **inputs):
        return {"output": f"Mock: {inputs.get('prompt', '')}", "status": "success"}

    def manifest(self):
        return {
            "name": "MockAgent",
            "version": "1.0.0",
            "capabilities": ["mock-execution"],
            "protocol": "subprocess",
        }


class TestCustomAgentTemplate:
    """28a5: Custom Agent 模板。"""

    def test_mock_agent_execute(self):
        agent = MockAgent()
        result = agent.execute(prompt="test")
        assert result["output"] == "Mock: test"
        assert result["status"] == "success"

    def test_mock_agent_manifest(self):
        agent = MockAgent()
        m = agent.manifest()
        assert m["name"] == "MockAgent"
        assert m["version"] == "1.0.0"
        assert "mock-execution" in m["capabilities"]

    def test_default_manifest(self):
        """Abstract base has default manifest."""
        class Minimal(AgentProvider):
            def execute(self, **inputs):
                return {"output": "ok"}

        agent = Minimal()
        m = agent.manifest()
        assert m["name"] == "Minimal"
        assert m["version"] == "0.1.0"
        assert m["protocol"] == "subprocess"

    def test_default_health_check(self):
        class Minimal(AgentProvider):
            def execute(self, **inputs):
                return {"output": "ok"}

        agent = Minimal()
        assert agent.health_check()

    def test_protocol_enforcement(self):
        """AgentProvider ABC 强制 execute 实现。"""
        with pytest.raises(TypeError):
            AgentProvider()  # type: ignore[abstract]


# ── Integration: echo_agent as Provider ─────────────────────────────

class TestAgentAsProvider:
    """验证 echo_agent 可以作为 SelectionEngine/KnowledgeGraph 的 Provider。"""

    def test_echo_agent_in_knowledge_graph(self):
        from ocos.capability.knowledge_graph import \
            KnowledgeGraph, CapabilityNode, ProviderNode, EdgeType

        kg = KnowledgeGraph()
        kg.add_capability(CapabilityNode("echo-cap", "text_generation"))
        kg.add_provider(ProviderNode("echo", capabilities=("echo-cap",),
                                     protocol="subprocess"))
        kg.add_edge("echo", EdgeType.PROVIDES, "echo-cap")

        info = kg.query_by_capability("echo-cap")
        assert info["capability"].capability_id == "echo-cap"
        assert len(info["providers"]) == 1
        assert info["providers"][0].provider_id == "echo"

    def test_selection_engine_with_echo_provider(self):
        from ocos.capability.knowledge_graph import \
            KnowledgeGraph, CapabilityNode, ProviderNode, EdgeType
        from ocos.capability.selection_engine import SelectionEngine

        kg = KnowledgeGraph()
        kg.add_capability(CapabilityNode("echo", "echo_domain"))
        kg.add_provider(ProviderNode("echo-prov", capabilities=("echo",),
                                     protocol="subprocess"))
        kg.add_edge("echo-prov", EdgeType.PROVIDES, "echo")

        engine = SelectionEngine(kg=kg)
        results = engine.select("echo_domain")
        assert len(results) == 1
        assert results[0].provider_id == "echo-prov"
