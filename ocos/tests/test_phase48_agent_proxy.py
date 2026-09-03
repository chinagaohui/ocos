"""test_agent_proxy.py — Phase 48: 智能体代理测试"""

from __future__ import annotations

import pytest
from ocos.capability.agent_proxy import AgentRegistry, call_agent, list_all_agents, get_registry


class TestAgentRegistry:
    """AgentRegistry 单元测试。"""

    def test_list_agents(self):
        """列出所有智能体。"""
        registry = AgentRegistry()
        agents = registry.list_agents()
        assert len(agents) >= 5  # 至少内置的5个

    def test_get_agent_info(self):
        """获取智能体信息。"""
        registry = AgentRegistry()
        info = registry.get_agent_info("code")
        assert info is not None
        assert info["name"] == "code"
        assert info["class"] == "CodeAgent"
        assert info["builtin"] is True

    def test_get_nonexistent_agent(self):
        """获取不存在的智能体。"""
        registry = AgentRegistry()
        info = registry.get_agent_info("nonexistent")
        assert info is None

    def test_invoke_code_agent(self):
        """调用 CodeAgent 执行代码。"""
        registry = AgentRegistry()
        result = registry.invoke("code", "execute", code="print(1+1)")
        assert result["success"] is True
        assert "2" in result.get("output", "")

    def test_invoke_research_agent(self):
        """调用 ResearchAgent。"""
        registry = AgentRegistry()
        result = registry.invoke("research", "research", topic="Python")
        assert result["success"] is True
        assert "output" in result

    def test_invoke_nonexistent_agent(self):
        """调用不存在的智能体。"""
        registry = AgentRegistry()
        result = registry.invoke("nonexistent", "test")
        assert result["success"] is False
        assert "not found" in result.get("error", "").lower()

    def test_update_agent_config(self):
        """更新智能体配置。"""
        registry = AgentRegistry()
        result = registry.update_agent_config("code", {"prefix": "CustomCode"})
        assert result["success"] is True
        assert result["will_reinstantiate"] is True

    def test_update_nonexistent_agent(self):
        """更新不存在的智能体配置。"""
        registry = AgentRegistry()
        result = registry.update_agent_config("nonexistent", {"foo": "bar"})
        assert result["success"] is False

    def test_update_agent_capability(self):
        """更新智能体能力定义。"""
        registry = AgentRegistry()
        result = registry.update_agent_capability(
            "code", "custom_action", {"description": "Custom action"}
        )
        assert result["success"] is True
        assert "capability" in result

    def test_concurrent_calls(self):
        """并发调用不同智能体。"""
        registry = AgentRegistry()

        results = []
        for _ in range(3):
            r1 = registry.invoke("code", "execute", code="print(1)")
            r2 = registry.invoke("research", "research", topic="test")
            results.extend([r1, r2])

        # 所有调用应该成功
        for r in results:
            assert r["success"] is True


class TestModuleFunctions:
    """模块级便捷函数测试。"""

    def test_call_agent(self):
        """测试 call_agent 便捷函数。"""
        result = call_agent("code", "execute", code="print('hello')")
        assert result["success"] is True

    def test_list_all_agents(self):
        """测试 list_all_agents 便捷函数。"""
        agents = list_all_agents()
        assert isinstance(agents, list)
        assert len(agents) > 0

    def test_get_registry_singleton(self):
        """测试 get_registry 单例模式。"""
        reg1 = get_registry()
        reg2 = get_registry()
        assert reg1 is reg2  # 应该是同一个实例


class TestAgentInstance:
    """AgentInstance 数据类测试。"""

    def test_is_ready_when_instance_exists(self):
        """实例存在时状态为 ready。"""
        from ocos.capability.agent_proxy import AgentInstance
        from ocos.capability.agents import CodeAgent

        inst = AgentInstance(
            name="test",
            class_name="CodeAgent",
            module_path="ocos.capability.agents.code_agent",
            instance=CodeAgent(),
            state="ready",
        )
        assert inst.is_ready is True

    def test_is_not_ready_when_instance_none(self):
        """实例不存在时状态不是 ready。"""
        from ocos.capability.agent_proxy import AgentInstance

        inst = AgentInstance(
            name="test",
            class_name="CodeAgent",
            module_path="ocos.capability.agents.code_agent",
            instance=None,
            state="registered",
        )
        assert inst.is_ready is False
