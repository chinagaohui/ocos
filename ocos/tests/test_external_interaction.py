"""Phase Q: ExternalInteraction 单元测试。"""

import logging
from unittest.mock import MagicMock

import pytest

from ocos.interaction.channel import (
    ExternalInteraction,
    LogChannel,
    CallbackChannel,
    WebhookChannel,
    BroadcastChannel,
    ChannelType,
    ChannelStatus,
    ChannelConfig,
)


class TestLogChannel:
    def test_create(self):
        channel = LogChannel(name="test-log", priority=1)
        assert channel.config.name == "test-log"
        assert channel.config.channel_type == ChannelType.LOG
        assert channel.health.status == ChannelStatus.ACTIVE

    def test_send(self, caplog):
        channel = LogChannel()
        with caplog.at_level(logging.INFO):
            result = channel.send("Test message", priority=1)
        assert result is True
        assert channel.health.success_count == 1


class TestCallbackChannel:
    def test_create(self):
        callback = MagicMock()
        channel = CallbackChannel(name="test-cb", callback=callback, priority=5)
        assert channel.config.priority == 5

    def test_send_calls_callback(self):
        calls = []
        def cb(msg, pri):
            calls.append((msg, pri))
        channel = CallbackChannel(name="cb", callback=cb, priority=5)
        result = channel.send("Hello", priority=2)
        assert result is True
        assert len(calls) == 1
        assert calls[0] == ("Hello", 2)

    def test_send_failure(self):
        def failing_cb(msg, pri):
            raise RuntimeError("callback failed")
        channel = CallbackChannel(name="cb", callback=failing_cb, priority=5)
        result = channel.send("test")
        assert result is False
        assert channel.health.status == ChannelStatus.ERROR


class TestBroadcastChannel:
    def test_create(self):
        bc = BroadcastChannel(name="bc-test")
        assert bc.config.channel_type == ChannelType.BROADCAST

    def test_add_and_send(self):
        bc = BroadcastChannel()
        log = LogChannel(name="log1")
        cb_calls = []
        cb = CallbackChannel(name="cb1", callback=lambda m, p: cb_calls.append(m))
        bc.add_channel(log)
        bc.add_channel(cb)
        result = bc.send("broadcast msg", priority=1)
        assert result is True
        assert len(cb_calls) == 1
        assert cb_calls[0] == "broadcast msg"

    def test_partial_failure(self):
        bc = BroadcastChannel()
        good = LogChannel(name="good")
        bad = CallbackChannel(name="bad", callback=lambda m, p: (_ for _ in []).throw(RuntimeError("fail")))
        bc.add_channel(good)
        bc.add_channel(bad)
        result = bc.send("msg")
        assert result is False


class TestExternalInteraction:
    def test_create(self):
        interaction = ExternalInteraction()
        assert interaction.channel_count == 0
        assert interaction.active_channels == []

    def test_add_and_remove_channel(self):
        interaction = ExternalInteraction()
        log = interaction.create_log_channel()
        name = interaction.add_channel(log)
        assert interaction.channel_count == 1
        assert name == "log"
        removed = interaction.remove_channel("log")
        assert removed is True
        assert interaction.channel_count == 0

    def test_send_to_multiple_channels(self):
        interaction = ExternalInteraction()
        log = interaction.create_log_channel()
        cb_calls = []
        cb = interaction.create_callback_channel("cb", lambda m, p: cb_calls.append(m))
        interaction.add_channel(log)
        interaction.add_channel(cb)
        results = interaction.send("test message", channel_names=["log", "cb"])
        assert results["log"] is True
        assert results["cb"] is True
        assert len(cb_calls) == 1

    def test_broadcast(self):
        interaction = ExternalInteraction()
        log = interaction.create_log_channel()
        cb_calls = []
        cb = interaction.create_callback_channel("cb", lambda m, p: cb_calls.append(m))
        bc = interaction.create_broadcast_channel()
        bc.add_channel(log)
        bc.add_channel(cb)
        interaction.add_channel(bc)
        result = interaction.send_broadcast("broadcast")
        assert result is True
        assert len(cb_calls) == 1

    def test_get_stats(self):
        interaction = ExternalInteraction()
        log = interaction.create_log_channel()
        interaction.add_channel(log)
        interaction.send("test")
        stats = interaction.get_stats()
        assert stats["total_channels"] == 1
        assert stats["active_channels"] == 1
        assert stats["total_sent"] == 1

    def test_factory_methods(self):
        interaction = ExternalInteraction()
        assert isinstance(interaction.create_log_channel(), LogChannel)
        assert isinstance(interaction.create_callback_channel("x", lambda m, p: None), CallbackChannel)
        assert isinstance(interaction.create_broadcast_channel(), BroadcastChannel)


class TestChannelHealth:
    def test_initial_status(self):
        channel = LogChannel(name="test")
        assert channel.health.status == ChannelStatus.ACTIVE
        assert channel.health.success_count == 0
        assert channel.health.error_count == 0

    def test_error_tracking(self):
        channel = CallbackChannel(name="fail", callback=lambda m, p: (_ for _ in []).throw(ValueError("err")))
        channel.send("test")
        assert channel.health.status == ChannelStatus.ERROR
        assert channel.health.error_count == 1
        assert channel.health.last_error == "err"
