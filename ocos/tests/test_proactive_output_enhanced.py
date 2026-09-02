"""Phase AJ: ProactiveOutputEnhanced 单元测试。

覆盖维度（8 类，24 个测试）：
1. 初始化配置
2. 输出流程
3. 频率限制
4. 优先级
5. 通道管理
6. 历史记录
7. 统计信息
8. 边界约束
"""

from __future__ import annotations

import pytest
import time
from unittest.mock import MagicMock

from ocos.proactive.enhanced_output import (
    ProactiveOutputEnhanced,
    OutputChannel,
    OutputPriority,
    OutputRecord,
    OutputStats,
)


# ── Fixtures ──────────────────────────────────────────────────────────────

@pytest.fixture
def output_mgr():
    return ProactiveOutputEnhanced(
        daily_limit=3,
        hourly_limit=10,
        min_interval_seconds=0.0,
    )


@pytest.fixture
def output_callback():
    return MagicMock()


@pytest.fixture
def notif_callback():
    return MagicMock()


# ── 1. 初始化配置 ────────────────────────────────────────────────────────

class TestInitialization:
    def test_create_default(self):
        mgr = ProactiveOutputEnhanced()
        assert mgr is not None

    def test_create_with_config(self):
        mgr = ProactiveOutputEnhanced(daily_limit=3, hourly_limit=10, min_interval_seconds=0.5)
        status = mgr.get_status()
        assert status["daily_limit"] == 3
        assert status["hourly_limit"] == 10
        assert status["min_interval_seconds"] == 0.5

    def test_empty_initial_state(self, output_mgr):
        stats = output_mgr.get_stats()
        assert stats["total_outputs"] == 0
        assert stats["granted_outputs"] == 0


# ── 2. 输出流程 ─────────────────────────────────────────────────────────

class TestOutputFlow:
    def test_emit_basic(self, output_mgr):
        record = output_mgr.emit("observation", "Test content")
        assert record.granted == True
        assert record.output_type == "observation"
        assert record.content == "Test content"

    def test_emit_different_types(self, output_mgr):
        for t in ["greeting", "suggestion", "alert"]:
            record = output_mgr.emit(t, f"Content for {t}")
            assert record.granted == True
            assert record.output_type == t

    def test_emit_with_callback(self, output_mgr, output_callback):
        output_mgr._output_callback = output_callback
        output_mgr.emit("test", "Hello")
        output_callback.assert_called_once()

    def test_emit_with_notification(self, output_mgr, notif_callback):
        output_mgr._notification_callback = notif_callback
        output_mgr.emit("alert", "Warning", priority=OutputPriority.HIGH, channel=OutputChannel.NOTIFICATION)
        notif_callback.assert_called_once()


# ── 3. 频率限制 ─────────────────────────────────────────────────────────

class TestRateLimiting:
    def test_daily_limit(self, output_mgr):
        # daily_limit=3，第4次应该被拒绝
        for i in range(3):
            record = output_mgr.emit("test", f"Content {i}")
            assert record.granted == True
        # 第4次
        record = output_mgr.emit("test", "Over limit")
        assert record.granted == False
        assert "rate_limited" in record.reason

    def test_hourly_limit(self):
        mgr = ProactiveOutputEnhanced(hourly_limit=2, min_interval_seconds=0.0)
        for i in range(2):
            record = mgr.emit("test", f"Content {i}")
            assert record.granted == True
        record = mgr.emit("test", "Over hourly")
        assert record.granted == False

    def test_min_interval(self, output_callback):
        mgr = ProactiveOutputEnhanced(min_interval_seconds=0.5)
        mgr._output_callback = output_callback
        mgr.emit("test", "First")
        time.sleep(0.1)
        record = mgr.emit("test", "Too soon")
        assert record.granted == False
        assert "too_frequent" in record.reason


# ── 4. 优先级 ────────────────────────────────────────────────────────────

class TestPriority:
    def test_priority_levels(self, output_mgr):
        for prio in [OutputPriority.LOW, OutputPriority.MEDIUM, OutputPriority.HIGH, OutputPriority.CRITICAL]:
            record = output_mgr.emit("test", "Content", priority=prio)
            assert record.priority == prio.value

    def test_default_priority(self, output_mgr):
        record = output_mgr.emit("test", "Default")
        assert record.priority == OutputPriority.MEDIUM.value


# ── 5. 通道管理 ─────────────────────────────────────────────────────────

class TestChannels:
    def test_log_channel(self, output_mgr):
        record = output_mgr.emit("test", "Log", channel=OutputChannel.LOG)
        assert record.channel == "log"

    def test_callback_channel(self, output_mgr, output_callback):
        output_mgr._output_callback = output_callback
        record = output_mgr.emit("test", "Callback", channel=OutputChannel.CALLBACK)
        assert record.channel == "callback"
        output_callback.assert_called()

    def test_broadcast_channel(self, output_mgr, output_callback):
        output_mgr._output_callback = output_callback
        record = output_mgr.emit("test", "Broadcast", channel=OutputChannel.BROADCAST)
        assert record.channel == "broadcast"
        output_callback.assert_called()


# ── 6. 历史记录 ─────────────────────────────────────────────────────────

class TestHistory:
    def test_history_records(self, output_mgr):
        output_mgr.emit("test", "Content 1")
        output_mgr.emit("test", "Content 2")
        history = output_mgr.get_history()
        assert len(history) == 2

    def test_history_limit(self, output_mgr):
        for i in range(20):
            output_mgr.emit("test", f"Content {i}")
        history = output_mgr.get_history(limit=5)
        assert len(history) <= 5

    def test_clear_history(self, output_mgr):
        output_mgr.emit("test", "Content")
        output_mgr.clear_history()
        history = output_mgr.get_history()
        assert len(history) == 0


# ── 7. 统计信息 ─────────────────────────────────────────────────────────

class TestStatistics:
    def test_stats_after_emits(self, output_mgr):
        output_mgr.emit("test", "Content 1")
        output_mgr.emit("test", "Content 2")
        output_mgr.emit("test", "Content 3")
        stats = output_mgr.get_stats()
        assert stats["total_outputs"] == 3
        assert stats["granted_outputs"] == 3

    def test_stats_after_rejection(self, output_mgr):
        for _ in range(3):
            output_mgr.emit("test", "Content")
        record = output_mgr.emit("test", "Rejected")
        stats = output_mgr.get_stats()
        assert stats["rejected_outputs"] == 1
        assert stats["rejection_rate"] > 0

    def test_stats_by_channel(self, output_mgr):
        output_mgr.emit("test", "Log", channel=OutputChannel.LOG)
        output_mgr.emit("test", "Callback", channel=OutputChannel.CALLBACK)
        stats = output_mgr.get_stats()
        assert "log" in stats["by_channel"]
        assert "callback" in stats["by_channel"]


# ── 8. 边界约束 ─────────────────────────────────────────────────────────

class TestBoundary:
    def test_empty_content(self, output_mgr):
        record = output_mgr.emit("test", "")
        assert record.content == ""

    def test_long_content_truncated(self, output_mgr):
        long_content = "x" * 1000
        record = output_mgr.emit("test", long_content)
        assert len(record.content) <= 500

    def test_set_limits(self, output_mgr):
        output_mgr.set_limits(daily_limit=10, hourly_limit=50)
        status = output_mgr.get_status()
        assert status["daily_limit"] == 10
        assert status["hourly_limit"] == 50

    def test_negative_limits(self, output_mgr):
        output_mgr.set_limits(daily_limit=-1)
        status = output_mgr.get_status()
        assert status["daily_limit"] == 1  # min 1


# ── 辅助测试 ─────────────────────────────────────────────────────────────

class TestHelpers:
    def test_output_record_to_dict(self):
        record = OutputRecord(
            record_id="r1",
            output_type="test",
            content="Hello",
            priority=2,
            channel="log",
            granted=True,
        )
        d = record.to_dict()
        assert d["record_id"] == "r1"
        assert d["granted"] == True

    def test_output_stats_recording(self):
        stats = OutputStats()
        record = OutputRecord(
            record_id="r1",
            output_type="test",
            content="Hello",
            priority=1,
            channel="log",
            granted=True,
        )
        stats.record(record)
        assert stats.total_outputs == 1
        assert stats.granted_outputs == 1
