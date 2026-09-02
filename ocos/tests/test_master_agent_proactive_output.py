"""Phase AJ: ProactiveOutputEnhanced — MasterAgent 集成测试。

覆盖维度：
1. 管理器注入
2. 输出接口
3. 频率限制
4. 历史记录
5. 统计信息
6. tick 接口
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock

from ocos.agent.master_agent import MasterAgent
from ocos.proactive.enhanced_output import (
    ProactiveOutputEnhanced,
    OutputChannel,
    OutputPriority,
)


@pytest.fixture
def output_mgr():
    return ProactiveOutputEnhanced(daily_limit=5, hourly_limit=20, min_interval_seconds=0.0)


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
def agent_with_output(mock_agent, output_mgr):
    mock_agent._proactive_output_enhanced = output_mgr
    return mock_agent, output_mgr


class TestManagerInjection:
    def test_none_manager(self, mock_agent):
        assert mock_agent.proactive_output_enhanced is None

    def test_injected_manager(self, agent_with_output):
        agent, mgr = agent_with_output
        assert agent.proactive_output_enhanced is mgr
        assert isinstance(mgr, ProactiveOutputEnhanced)


class TestOutputFlow:
    def test_emit(self, agent_with_output):
        agent, mgr = agent_with_output
        record = mgr.emit("observation", "Test content")
        assert record.granted == True

    def test_emit_different_priorities(self, agent_with_output):
        agent, mgr = agent_with_output
        for prio in [OutputPriority.LOW, OutputPriority.MEDIUM, OutputPriority.HIGH, OutputPriority.CRITICAL]:
            record = mgr.emit("test", f"Priority {prio.name}", priority=prio)
            assert record.granted == True
            assert record.priority == prio.value

    def test_emit_different_channels(self, agent_with_output):
        agent, mgr = agent_with_output
        for chan in [OutputChannel.LOG, OutputChannel.CALLBACK, OutputChannel.BROADCAST]:
            record = mgr.emit("test", "Channel test", channel=chan)
            assert record.granted == True
            assert record.channel == chan.value


class TestRateLimiting:
    def test_daily_limit(self, output_mgr):
        for i in range(5):
            record = output_mgr.emit("test", f"Content {i}")
            assert record.granted == True
        record = output_mgr.emit("test", "Over limit")
        assert record.granted == False
        assert "rate_limited" in record.reason


class TestHistory:
    def test_history_records(self, output_mgr):
        output_mgr.emit("test", "Content 1")
        output_mgr.emit("test", "Content 2")
        history = output_mgr.get_history()
        assert len(history) == 2

    def test_clear_history(self, output_mgr):
        output_mgr.emit("test", "Content")
        output_mgr.clear_history()
        assert len(output_mgr.get_history()) == 0


class TestStats:
    def test_stats_after_emits(self, output_mgr):
        for _ in range(3):
            output_mgr.emit("test", "Content")
        stats = output_mgr.get_stats()
        assert stats["total_outputs"] == 3
        assert stats["granted_outputs"] == 3

    def test_stats_after_rejection(self, output_mgr):
        for _ in range(5):
            output_mgr.emit("test", "Content")
        output_mgr.emit("test", "Rejected")
        stats = output_mgr.get_stats()
        assert stats["rejected_outputs"] >= 1


class TestTickIntegration:
    def test_tick_includes_proactive_output(self, agent_with_output):
        agent, mgr = agent_with_output
        result = agent.tick()
        assert "tick" in result
        assert "proactive_output" in result


class TestNoneManager:
    def test_methods_with_none(self, mock_agent):
        result = mock_agent.tick()
        assert "tick" in result
