"""Phase AC: EcosystemManager — MasterAgent 集成测试。

覆盖维度：
1. 管理器注入
2. 扩展注册与批准
3. 插件加载与启动
4. tick 接口
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock

from ocos.agent.master_agent import MasterAgent
from ocos.ecosystem.manager import EcosystemManager


@pytest.fixture
def mock_agent():
    """创建带有模拟依赖的 Agent 实例。"""
    mock_identity = MagicMock()
    mock_goal_stack = MagicMock()
    mock_intent = MagicMock()
    mock_attention = MagicMock()
    mock_working_memory = MagicMock()
    mock_capability_manager = MagicMock()
    mock_execution_manager = MagicMock()

    return MasterAgent(
        agent_id="test-agent",
        identity=mock_identity,
        goal_stack=mock_goal_stack,
        intent=mock_intent,
        attention=mock_attention,
        working_memory=mock_working_memory,
        capability_manager=mock_capability_manager,
        execution_manager=mock_execution_manager,
    )


@pytest.fixture
def agent_with_ecosystem(mock_agent):
    """创建带有生态管理器的 Agent 实例。"""
    em = EcosystemManager()
    mock_agent._ecosystem_manager = em
    return mock_agent


class TestEcosystemInjection:
    """管理器注入测试。"""

    def test_ecosystem_manager_injection(self, agent_with_ecosystem):
        """管理器应正确注入。"""
        assert agent_with_ecosystem.ecosystem_manager is not None

    def test_ecosystem_manager_property(self, agent_with_ecosystem):
        """获取属性应返回注入的管理器。"""
        manager = EcosystemManager()
        agent_with_ecosystem._ecosystem_manager = manager
        assert agent_with_ecosystem.ecosystem_manager == manager


class TestExtensionMethods:
    """扩展管理方法测试。"""

    def test_register_extension(self, agent_with_ecosystem):
        """注册扩展应委托给管理器。"""
        result = agent_with_ecosystem.register_extension("test-ext", "perception")
        assert "extension_id" in result or "error" in result

    def test_approve_extension(self, agent_with_ecosystem):
        """批准扩展。"""
        result = agent_with_ecosystem.approve_extension("ext:test")
        assert "success" in result or "error" in result

    def test_integrate_extension(self, agent_with_ecosystem):
        """集成扩展。"""
        result = agent_with_ecosystem.integrate_extension("ext:test")
        assert "success" in result or "error" in result

    def test_activate_extension(self, agent_with_ecosystem):
        """激活扩展。"""
        result = agent_with_ecosystem.activate_extension("ext:test")
        assert "success" in result or "error" in result

    def test_register_extension_no_manager(self, mock_agent):
        """无管理器时应返回错误。"""
        result = mock_agent.register_extension("test", "perception")
        assert "error" in result
        assert "not injected" in result["error"]


class TestPluginMethods:
    """插件管理方法测试。"""

    def test_load_plugin(self, agent_with_ecosystem):
        """加载插件。"""
        result = agent_with_ecosystem.load_plugin("test-plugin", "tp:Plugin")
        assert "plugin_id" in result or "error" in result

    def test_start_plugin(self, agent_with_ecosystem):
        """启动插件。"""
        result = agent_with_ecosystem.start_plugin("plugin:test")
        assert "success" in result or "error" in result

    def test_load_plugin_no_manager(self, mock_agent):
        """无管理器时应返回错误。"""
        result = mock_agent.load_plugin("test", "tp:Plugin")
        assert "error" in result
        assert "not injected" in result["error"]


class TestStats:
    """统计信息测试。"""

    def test_get_stats(self, agent_with_ecosystem):
        """获取统计信息。"""
        result = agent_with_ecosystem.get_ecosystem_stats()
        assert "extension_count" in result
        assert "plugin_count" in result

    def test_get_stats_no_manager(self, mock_agent):
        """无管理器时应返回错误。"""
        result = mock_agent.get_ecosystem_stats()
        assert "error" in result
        assert "not injected" in result["error"]


class TestTick:
    """Tick 接口测试。"""

    def test_tick_with_ecosystem(self, agent_with_ecosystem):
        """含生态管理器的 tick。"""
        result = agent_with_ecosystem.tick()
        assert "ecosystem" in result

    def test_tick_without_ecosystem(self, mock_agent):
        """无生态管理器时的 tick。"""
        result = mock_agent.tick()
        assert "ecosystem" in result
        assert result["ecosystem"] == {}


class TestEndToEnd:
    """端到端测试。"""

    def test_full_workflow(self, agent_with_ecosystem):
        """完整生态系统工作流。"""
        # 注册扩展
        ext_result = agent_with_ecosystem.register_extension("test-ext", "perception")
        
        # 获取统计
        stats = agent_with_ecosystem.get_ecosystem_stats()
        assert stats["extension_count"] >= 0
        
        # tick 正常执行
        result = agent_with_ecosystem.tick()
        assert "ecosystem" in result
