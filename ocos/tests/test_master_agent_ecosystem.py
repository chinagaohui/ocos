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

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from ocos.agent.master_agent import MasterAgent
from ocos.ecosystem.manager import EcosystemManager


@pytest.fixture
def mock_agent():
    """创建 Mock MasterAgent。"""
    agent = MasterAgent(agent_id="test-agent-ac", trust_anchor=MagicMock())
    agent._ecosystem_manager = MagicMock(spec=EcosystemManager)
    return agent


class TestEcosystemInjection:
    """管理器注入测试。"""

    def test_ecosystem_manager_injection(self, mock_agent):
        """管理器应正确注入。"""
        assert mock_agent.ecosystem_manager is not None

    def test_ecosystem_manager_property(self, mock_agent):
        """获取属性应返回注入的管理器。"""
        manager = EcosystemManager()
        mock_agent._ecosystem_manager = manager
        assert mock_agent.ecosystem_manager == manager


class TestExtensionMethods:
    """扩展管理方法测试。"""

    def test_register_extension(self, mock_agent):
        """注册扩展应委托给管理器。"""
        mock_ext = MagicMock()
        mock_ext.extension_id = "ext:test123"
        mock_ext.name = "test-ext"
        mock_ext.state.value = "active"
        mock_agent.ecosystem_manager.register_extension.return_value = mock_ext

        result = mock_agent.register_extension("test-ext", "perception")

        assert result["extension_id"] == "ext:test123"
        assert result["name"] == "test-ext"
        mock_agent.ecosystem_manager.register_extension.assert_called_once()

    def test_approve_extension(self, mock_agent):
        """批准扩展。"""
        mock_agent.ecosystem_manager.approve_extension.return_value = True
        result = mock_agent.approve_extension("ext:test")
        assert result["success"] is True

    def test_integrate_extension(self, mock_agent):
        """集成扩展。"""
        mock_agent.ecosystem_manager.integrate_extension.return_value = True
        result = mock_agent.integrate_extension("ext:test")
        assert result["success"] is True

    def test_activate_extension(self, mock_agent):
        """激活扩展。"""
        mock_agent.ecosystem_manager.activate_extension.return_value = True
        result = mock_agent.activate_extension("ext:test")
        assert result["success"] is True

    def test_register_extension_max_reached(self, mock_agent):
        """超过限制时应返回错误。"""
        mock_agent.ecosystem_manager.register_extension.return_value = None
        result = mock_agent.register_extension("test", "perception")
        assert "error" in result


class TestPluginMethods:
    """插件管理方法测试。"""

    def test_load_plugin(self, mock_agent):
        """加载插件。"""
        mock_plugin = MagicMock()
        mock_plugin.plugin_id = "plugin:test123"
        mock_plugin.name = "test-plugin"
        mock_plugin.state.value = "loaded"
        mock_agent.ecosystem_manager.load_plugin.return_value = mock_plugin

        result = mock_agent.load_plugin("test-plugin", "tp:Plugin")

        assert result["plugin_id"] == "plugin:test123"
        assert result["name"] == "test-plugin"

    def test_start_plugin(self, mock_agent):
        """启动插件。"""
        mock_agent.ecosystem_manager.start_plugin.return_value = True
        result = mock_agent.start_plugin("plugin:test")
        assert result["success"] is True

    def test_load_plugin_max_reached(self, mock_agent):
        """超过插件限制。"""
        mock_agent.ecosystem_manager.load_plugin.return_value = None
        result = mock_agent.load_plugin("test", "tp:Plugin")
        assert "error" in result


class TestStats:
    """统计信息测试。"""

    def test_get_stats(self, mock_agent):
        """获取统计信息。"""
        mock_stats = {
            "extension_count": 5,
            "active_extensions": 3,
            "plugin_count": 2,
            "adapter_count": 10,
        }
        mock_agent.ecosystem_manager.get_stats.return_value = mock_stats

        result = mock_agent.get_ecosystem_stats()
        assert result["extension_count"] == 5
        assert result["active_extensions"] == 3


class TestTick:
    """Tick 接口测试。"""

    def test_tick_with_ecosystem(self, mock_agent):
        """含生态管理器的 tick。"""
        mock_stats = {"extensions": [], "plugins": []}
        mock_agent.ecosystem_manager.get_stats.return_value = mock_stats

        result = mock_agent.tick()

        assert "ecosystem" in result
        assert result["ecosystem"] == mock_stats

    def test_tick_without_ecosystem(self, mock_agent):
        """无生态管理器时的 tick。"""
        mock_agent._ecosystem_manager = None
        result = mock_agent.tick()

        assert "ecosystem" in result
        assert result["ecosystem"] == {}


class TestErrorHandling:
    """错误处理测试。"""

    def test_register_extension_error(self, mock_agent):
        """注册扩展异常。"""
        mock_agent.ecosystem_manager.register_extension.side_effect = Exception("test error")
        result = mock_agent.register_extension("test", "perception")
        assert "error" in result
        assert "test error" in result["error"]

    def test_load_plugin_error(self, mock_agent):
        """加载插件异常。"""
        mock_agent.ecosystem_manager.load_plugin.side_effect = Exception("load failed")
        result = mock_agent.load_plugin("test", "tp:Plugin")
        assert "error" in result
        assert "load failed" in result["error"]
