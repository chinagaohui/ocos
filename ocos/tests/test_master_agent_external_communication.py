"""Phase AK: ExternalCommunicationManager — MasterAgent 集成测试。

覆盖维度：
1. 管理器注入
2. 通道管理
3. 消息发送
4. 历史记录
5. 统计信息
6. tick 接口
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock

from ocos.agent.master_agent import MasterAgent
from ocos.external_communication.manager import (
    ExternalCommunicationManager,
    ChannelType,
    MessagePriority,
)


@pytest.fixture
def comm_mgr():
    return ExternalCommunicationManager()


@pytest.fixture
def mock_agent():
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
def agent_with_comm(mock_agent, comm_mgr):
    mock_agent._external_communication_manager = comm_mgr
    return mock_agent, comm_mgr


class TestManagerInjection:
    def test_none_manager(self, mock_agent):
        assert mock_agent.external_communication_manager is None

    def test_injected_manager(self, agent_with_comm):
        agent, mgr = agent_with_comm
        assert agent.external_communication_manager is mgr
        assert isinstance(mgr, ExternalCommunicationManager)


class TestChannelManagement:
    def test_register_channels(self, agent_with_comm):
        agent, mgr = agent_with_comm
        mgr.register_websocket_channel("ws-main", "ws://localhost")
        mgr.register_http_channel("http-api", "http://localhost")
        channels = mgr.list_channels()
        assert len(channels) >= 2

    def test_unregister_channel(self, agent_with_comm):
        agent, mgr = agent_with_comm
        mgr.register_http_channel("test-http", "http://test")
        result = mgr.unregister_channel("test-http")
        assert result is True

    def test_get_channel_status(self, agent_with_comm):
        agent, mgr = agent_with_comm
        mgr.register_http_channel("status-test", "http://test")
        status = mgr.get_channel_status("status-test")
        assert status is not None


class TestMessageSending:
    def test_send_websocket_message(self, agent_with_comm):
        agent, mgr = agent_with_comm
        mgr.register_websocket_channel("ws-test", "ws://localhost")
        record = mgr.send_websocket_message("Hello", "ws-test")
        assert record is not None
        assert record.status == "sent"

    def test_send_http_message(self, agent_with_comm):
        agent, mgr = agent_with_comm
        mgr.register_http_channel("http-test", "http://localhost")
        record = mgr.send_http_message("Hello HTTP", "http-test")
        assert record is not None
        assert record.status == "sent"

    def test_send_with_priority(self, agent_with_comm):
        agent, mgr = agent_with_comm
        for prio in [MessagePriority.LOW, MessagePriority.NORMAL, MessagePriority.HIGH, MessagePriority.CRITICAL]:
            record = mgr.send_message("Test", ChannelType.HTTP, priority=prio)
            assert record is not None


class TestHistory:
    def test_records_after_sends(self, agent_with_comm):
        agent, mgr = agent_with_comm
        mgr.register_http_channel("hist-test", "http://localhost")
        for i in range(3):
            mgr.send_http_message(f"Msg {i}", "hist-test")
        history = mgr.get_history()
        assert len(history) >= 3

    def test_clear_history(self, agent_with_comm):
        agent, mgr = agent_with_comm
        mgr.register_http_channel("clear-test", "http://localhost")
        mgr.send_http_message("Clear", "clear-test")
        mgr.clear_history()
        assert len(mgr.get_history()) == 0


class TestStatistics:
    def test_stats_after_sends(self, agent_with_comm):
        agent, mgr = agent_with_comm
        mgr.register_http_channel("stats-test", "http://localhost")
        for _ in range(5):
            mgr.send_http_message("Count", "stats-test")
        stats = mgr.get_statistics()
        assert stats["total_messages"] >= 5

    def test_failed_counted(self, agent_with_comm):
        agent, mgr = agent_with_comm
        mgr.send_message("Fail", ChannelType.WEBSOCKET)
        stats = mgr.get_statistics()
        assert stats["failed_messages"] >= 1


class TestTickIntegration:
    def test_tick_includes_communication(self, agent_with_comm):
        agent, mgr = agent_with_comm
        result = agent.tick()
        assert "tick" in result
        assert "external_communication" in result

    def test_tick_with_none_manager(self, mock_agent):
        result = mock_agent.tick()
        assert "tick" in result
        assert "external_communication" not in result or result.get("external_communication") is None


class TestNoneManager:
    def test_methods_with_none(self, mock_agent):
        result = mock_agent.tick()
        assert "tick" in result
