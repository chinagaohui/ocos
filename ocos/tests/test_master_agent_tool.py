"""Phase AI: ToolIntegrationManager — MasterAgent 集成测试。

覆盖维度：
1. 管理器注入
2. 工具注册/注销
3. 工具调用
4. 调用历史
5. 统计信息
6. tick 接口
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock

from ocos.agent.master_agent import MasterAgent
from ocos.tool.manager import (
    ToolIntegrationManager,
    ToolCategory,
    ToolPermission,
)


@pytest.fixture
def tool_mgr():
    return ToolIntegrationManager(rate_limit_per_second=100)


@pytest.fixture
def mock_agent():
    """创建带有模拟依赖的 Agent 实例。"""
    return MasterAgent(
        agent_id="test-agent",
        identity=MagicMock(),
        goal_stack=MagicMock(),
        intent=MagicMock(),
        attention=MagicMock(),
        working_memory=MagicMock(),
        capability_manager=MagicMock(),
        execution_manager=MagicMock(),
    )


@pytest.fixture
def agent_with_tools(mock_agent, tool_mgr):
    """创建带工具管理器的 Agent 实例。"""
    mock_agent._tool_manager = tool_mgr
    return mock_agent, tool_mgr


class TestManagerInjection:
    """测试管理器注入。"""

    def test_none_manager(self, mock_agent):
        assert mock_agent.tool_manager is None

    def test_injected_manager(self, agent_with_tools):
        agent, mgr = agent_with_tools
        assert agent.tool_manager is mgr
        assert isinstance(mgr, ToolIntegrationManager)


class TestToolCRUD:
    """测试工具 CRUD。"""

    def test_register_tool(self, agent_with_tools):
        agent, mgr = agent_with_tools
        desc = mgr.register_tool(
            "search", "Web Search", ToolCategory.KNOWLEDGE, ToolPermission.READ_ONLY
        )
        assert desc is not None
        assert mgr.has_tool("search")

    def test_unregister_tool(self, agent_with_tools):
        agent, mgr = agent_with_tools
        mgr.register_tool("t1", "T1", ToolCategory.SYSTEM, ToolPermission.READ_ONLY)
        assert mgr.unregister_tool("t1") == True
        assert not mgr.has_tool("t1")

    def test_list_tools(self, agent_with_tools):
        agent, mgr = agent_with_tools
        mgr.register_tool("t1", "T1", ToolCategory.SYSTEM, ToolPermission.READ_ONLY)
        mgr.register_tool("t2", "T2", ToolCategory.NETWORK, ToolPermission.READ_ONLY)
        tools = mgr.list_tools()
        assert len(tools) == 2


class TestToolCall:
    """测试工具调用。"""

    def test_call_tool(self, agent_with_tools):
        agent, mgr = agent_with_tools
        mgr.register_tool("t1", "T1", ToolCategory.COMPUTE, ToolPermission.READ_ONLY)
        result = mgr.call_tool("t1", {"x": 1})
        assert result["success"] == True
        assert "call_id" in result

    def test_call_unregistered_tool(self, agent_with_tools):
        agent, mgr = agent_with_tools
        result = mgr.call_tool("nonexistent")
        assert result["success"] == False


class TestHistory:
    """测试调用历史。"""

    def test_history_records(self, agent_with_tools):
        agent, mgr = agent_with_tools
        mgr.register_tool("t1", "T1", ToolCategory.COMPUTE, ToolPermission.READ_ONLY)
        mgr.call_tool("t1")
        history = mgr.get_call_history()
        assert len(history) == 1


class TestStats:
    """测试统计信息。"""

    def test_stats_after_calls(self, agent_with_tools):
        agent, mgr = agent_with_tools
        mgr.register_tool("t1", "T1", ToolCategory.COMPUTE, ToolPermission.READ_ONLY)
        for _ in range(3):
            mgr.call_tool("t1")
        stats = mgr.get_call_stats()
        assert stats["total_calls"] == 3
        assert stats["success_rate"] == 1.0


class TestTickIntegration:
    """测试 tick 接口集成。"""

    def test_tick_includes_tool(self, agent_with_tools):
        agent, mgr = agent_with_tools
        result = agent.tick()
        assert "tick" in result
        assert "tool" in result


class TestNoneManager:
    """工具管理器 None 边界。"""

    def test_methods_with_none(self, mock_agent):
        result = mock_agent.tick()
        assert "tick" in result
