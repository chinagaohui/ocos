"""Phase P: ProactiveOutput 单元测试。"""

import time
from unittest.mock import MagicMock, patch

import pytest

from ocos.proactive.output import (
    ProactiveOutput,
    OutputRecord,
    OutputPriority,
    OutputChannel,
)
from ocos.attention.focus import AttentionFocus, FocusType


class TestOutputRecord:
    """OutputRecord 测试。"""

    def test_create_record(self):
        record = OutputRecord(
            record_id="test-1",
            output_type="greeting",
            content="Hello",
            priority=1,
            channel="log",
        )
        assert record.record_id == "test-1"
        assert record.output_type == "greeting"
        assert record.granted is True

    def test_record_defaults(self):
        record = OutputRecord(
            record_id="test-2",
            output_type="alert",
            content="Warning",
            priority=3,
            channel="callback",
        )
        assert record.timestamp is not None
        assert record.reason == ""


class TestProactiveOutput:
    """ProactiveOutput 核心功能测试。"""

    def test_create_output_manager(self):
        output = ProactiveOutput()
        assert isinstance(output.focus, AttentionFocus)
        assert output.today_count == 0
        assert output.hourly_count == 0

    def test_output_observation(self):
        output = ProactiveOutput()
        record = output.output_observation("Test observation")
        assert record is not None
        assert record.output_type == "observation"
        assert record.granted is True
        assert output.today_count == 1

    def test_output_suggestion(self):
        output = ProactiveOutput()
        record = output.output_suggestion("Test suggestion")
        assert record is not None
        assert record.output_type == "suggestion"
        assert record.granted is True

    def test_output_alert(self):
        output = ProactiveOutput()
        record = output.output_alert("Test alert")
        assert record is not None
        assert record.output_type == "alert"
        assert record.priority == OutputPriority.HIGH.value

    def test_throttle_by_daily_limit(self):
        # 设置 min_interval=0 避免间隔节流干扰
        output = ProactiveOutput(daily_limit=2, min_interval_seconds=0.0)
        output.output_observation("obs1")
        output.output_observation("obs2")
        result = output.output_observation("obs3")
        assert result is None
        # 今日计数只有成功输出的才计入
        assert output.today_count == 2

    def test_throttle_by_hourly_limit(self):
        output = ProactiveOutput(hourly_limit=2, min_interval_seconds=0.0)
        output.output_observation("obs1")
        output.output_observation("obs2")
        result = output.output_observation("obs3")
        assert result is None

    def test_min_interval_throttle(self):
        output = ProactiveOutput(min_interval_seconds=1.0)
        output.output_observation("obs1")
        # 立即调用应该被节流
        result = output.output_observation("obs2")
        assert result is None
    def test_hooks(self):
        output = ProactiveOutput()
        outputs = []

        def on_output(record):
            outputs.append(record)

        output.on_output(on_output)
        output.output_observation("test")
        assert len(outputs) == 1
        assert outputs[0].content == "[观察] test"

    def test_get_stats(self):
        output = ProactiveOutput(min_interval_seconds=0.0)
        output.output_observation("obs1")
        output.output_suggestion("sug1")
        stats = output.get_output_stats()
        assert stats["today_count"] == 2
        assert stats["hourly_count"] == 2
        assert len(stats["recent_outputs"]) == 2

    def test_focus_integration(self):
        focus = AttentionFocus()
        focus.set_focus(FocusType.EXTERNAL, "user-message", 0.8)
        output = ProactiveOutput(focus=focus, min_interval_seconds=0.0)
        record = output.output_observation("related to user message", focus_target="user-message")
        assert record is not None


class TestOutputPriority:
    """OutputPriority 枚举测试。"""

    def test_priority_values(self):
        assert OutputPriority.LOW.value == 1
        assert OutputPriority.MEDIUM.value == 2
        assert OutputPriority.HIGH.value == 3
        assert OutputPriority.CRITICAL.value == 4
