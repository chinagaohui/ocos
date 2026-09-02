"""Phase AK: ExternalCommunicationManager 单元测试。

覆盖维度（8 类，24 个测试）：
1. 初始化配置
2. 通道管理
3. 消息发送
4. 通道状态
5. 历史记录
6. 统计信息
7. Tick 接口
8. 边界约束
"""

from __future__ import annotations

import pytest

from ocos.external_communication.manager import (
    ExternalCommunicationManager,
    ChannelType,
    MessagePriority,
    CommunicationMessage,
    CommunicationRecord,
    CommunicationChannelManager,
)


@pytest.fixture
def comm_mgr():
    return ExternalCommunicationManager()


class TestInitialization:
    def test_create_default(self):
        mgr = ExternalCommunicationManager()
        assert mgr is not None

    def test_create_with_config(self):
        mgr = ExternalCommunicationManager(
            default_timeout=60.0,
            default_retry_count=5,
            max_record_history=5000,
        )
        assert mgr is not None

    def test_initialize(self, comm_mgr):
        result = comm_mgr.initialize()
        assert result is True


class TestChannelManagement:
    def test_register_websocket_channel(self, comm_mgr):
        result = comm_mgr.register_websocket_channel("ws-main", "ws://localhost:8080")
        assert result is True

    def test_register_http_channel(self, comm_mgr):
        result = comm_mgr.register_http_channel("http-api", "http://localhost:8081")
        assert result is True

    def test_unregister_channel(self, comm_mgr):
        comm_mgr.register_http_channel("test-http", "http://test")
        result = comm_mgr.unregister_channel("test-http")
        assert result is True

    def test_list_channels(self, comm_mgr):
        comm_mgr.register_http_channel("http-test", "http://test")
        channels = comm_mgr.list_channels()
        assert len(channels) >= 1

    def test_get_channel_status(self, comm_mgr):
        comm_mgr.register_http_channel("status-test", "http://test")
        status = comm_mgr.get_channel_status("status-test")
        assert status is not None
        assert "status" in status

    def test_get_nonexistent_channel(self, comm_mgr):
        status = comm_mgr.get_channel_status("nonexistent")
        assert status is None


class TestMessageSending:
    def test_send_websocket_message(self, comm_mgr):
        comm_mgr.register_websocket_channel("ws-test", "ws://localhost")
        record = comm_mgr.send_websocket_message("Hello WS", "ws-test")
        assert record is not None
        assert record.status == "sent"

    def test_send_http_message(self, comm_mgr):
        comm_mgr.register_http_channel("http-test", "http://localhost")
        record = comm_mgr.send_http_message("Hello HTTP", "http-test")
        assert record is not None
        assert record.status == "sent"

    def test_send_generic_message(self, comm_mgr):
        record = comm_mgr.send_message(
            "Generic content",
            ChannelType.WEBSOCKET,
            priority=MessagePriority.HIGH,
        )
        assert record is not None

    def test_send_with_priority(self, comm_mgr):
        comm_mgr.register_websocket_channel("pri-test", "ws://localhost")
        for prio in [MessagePriority.LOW, MessagePriority.NORMAL, MessagePriority.HIGH, MessagePriority.CRITICAL]:
            record = comm_mgr.send_websocket_message("Priority test", "pri-test", priority=prio)
            assert record is not None

    def test_send_without_channel(self, comm_mgr):
        record = comm_mgr.send_message("No channel", ChannelType.WEBSOCKET)
        assert record is not None
        assert record.status == "failed"


class TestChannelStatus:
    def test_channel_health_after_send(self, comm_mgr):
        comm_mgr.register_websocket_channel("health-test", "ws://localhost")
        comm_mgr.send_websocket_message("Test", "health-test")
        status = comm_mgr.get_channel_status("health-test")
        assert status is not None

    def test_multiple_channels_independent(self, comm_mgr):
        comm_mgr.register_websocket_channel("ws-1", "ws://localhost:1")
        comm_mgr.register_http_channel("http-1", "http://localhost:2")
        assert len(comm_mgr.list_channels()) >= 2


class TestHistory:
    def test_records_after_send(self, comm_mgr):
        comm_mgr.register_http_channel("hist-test", "http://localhost")
        comm_mgr.send_http_message("Record me", "hist-test")
        history = comm_mgr.get_history()
        assert len(history) >= 1

    def test_history_limit(self, comm_mgr):
        comm_mgr.register_http_channel("limit-test", "http://localhost")
        for i in range(5):
            comm_mgr.send_http_message(f"Msg {i}", "limit-test")
        history = comm_mgr.get_history(limit=3)
        assert len(history) == 3

    def test_clear_history(self, comm_mgr):
        comm_mgr.register_http_channel("clear-test", "http://localhost")
        comm_mgr.send_http_message("Clear me", "clear-test")
        comm_mgr.clear_history()
        assert len(comm_mgr.get_history()) == 0


class TestStatistics:
    def test_stats_after_sends(self, comm_mgr):
        comm_mgr.register_http_channel("stats-test", "http://localhost")
        for _ in range(3):
            comm_mgr.send_http_message("Count me", "stats-test")
        stats = comm_mgr.get_statistics()
        assert stats["total_messages"] >= 3

    def test_failed_message_counted(self, comm_mgr):
        comm_mgr.send_message("Fail", ChannelType.WEBSOCKET)
        stats = comm_mgr.get_statistics()
        assert stats["failed_messages"] >= 1


class TestHealthSummary:
    def test_health_summary(self, comm_mgr):
        summary = comm_mgr.get_health_summary()
        assert "total_channels" in summary
        assert "active_channels" in summary

    def test_health_after_registration(self, comm_mgr):
        comm_mgr.register_http_channel("summary-test", "http://localhost")
        summary = comm_mgr.get_health_summary()
        assert summary["total_channels"] >= 1


class TestTick:
    def test_tick_returns_dict(self, comm_mgr):
        result = comm_mgr.tick()
        assert isinstance(result, dict)
        assert "health_summary" in result
        assert "stats" in result

    def test_tick_initialized_state(self, comm_mgr):
        comm_mgr.initialize()
        result = comm_mgr.tick()
        assert result["initialized"] is True


class TestBoundaryConstraints:
    def test_unregister_nonexistent(self, comm_mgr):
        result = comm_mgr.unregister_channel("nonexistent")
        assert result is False

    def test_duplicate_registration(self, comm_mgr):
        comm_mgr.register_http_channel("dup-test", "http://localhost")
        result = comm_mgr.register_http_channel("dup-test", "http://localhost")
        assert result is False

    def test_max_records_limit(self):
        mgr = CommunicationChannelManager()
        assert mgr._max_records == 10000
