"""OCOS event_bus 事件总线测试。

宪法 Rule 2: Event Bus 是模块间唯一通信通道。
"""

import pytest
from unittest.mock import MagicMock

from ocos.events.event_bus import EventBus
from ocos.kernel.abi import Event, EventType


@pytest.fixture
def bus():
    return EventBus()


class TestSubscribe:
    def test_subscribe_returns_id(self, bus):
        cb = MagicMock()
        sid = bus.subscribe(EventType.GOAL_SET, cb)
        assert isinstance(sid, str)
        assert len(sid) > 0

    def test_subscribe_multiple_same_type(self, bus):
        cb1 = MagicMock()
        cb2 = MagicMock()
        s1 = bus.subscribe(EventType.GOAL_SET, cb1)
        s2 = bus.subscribe(EventType.GOAL_SET, cb2)
        assert s1 != s2

    def test_subscribe_all(self, bus):
        cb = MagicMock()
        sid = bus.subscribe_all(cb)
        assert isinstance(sid, str)


class TestPublish:
    def test_publish_no_subscribers(self, bus):
        event = Event(
            event_id="E1", event_type=EventType.GOAL_SET,
            source="test", timestamp="", payload={}, trace_id="", schema_version="1.0",
        )
        count = bus.publish(event)
        assert count == 0

    def test_publish_sync_delivers(self, bus):
        received = []
        bus.subscribe(EventType.GOAL_SET, lambda e: received.append(e))
        event = Event(
            event_id="E1", event_type=EventType.GOAL_SET,
            source="test", timestamp="", payload={"goal_id": "G1"}, trace_id="", schema_version="1.0",
        )
        count = bus.publish(event)
        assert count == 1
        assert len(received) == 1
        assert received[0].event_id == "E1"

    def test_publish_to_multiple_subscribers(self, bus):
        received1, received2 = [], []
        bus.subscribe(EventType.GOAL_SET, lambda e: received1.append(e))
        bus.subscribe(EventType.GOAL_SET, lambda e: received2.append(e))
        event = Event(
            event_id="E2", event_type=EventType.GOAL_SET,
            source="test", timestamp="", payload={}, trace_id="", schema_version="1.0",
        )
        count = bus.publish(event)
        assert count == 2
        assert len(received1) == 1
        assert len(received2) == 1

    def test_global_subscriber_receives_all(self, bus):
        received = []
        bus.subscribe_all(lambda e: received.append(e.event_type))
        bus.publish(Event(
            event_id="E3", event_type=EventType.TRACE_RECORDED,
            source="test", timestamp="", payload={}, trace_id="", schema_version="1.0",
        ))
        assert EventType.TRACE_RECORDED in received

    def test_unmatched_event_type_no_delivery(self, bus):
        cb = MagicMock()
        bus.subscribe(EventType.GOAL_SET, cb)
        bus.publish(Event(
            event_id="E4", event_type=EventType.MEMORY_STORED,
            source="test", timestamp="", payload={}, trace_id="", schema_version="1.0",
        ))
        cb.assert_not_called()


class TestUnsubscribe:
    def test_unsubscribe_removes_callback(self, bus):
        received = []
        sid = bus.subscribe(EventType.GOAL_SET, lambda e: received.append(e))
        bus.unsubscribe(sid)
        bus.publish(Event(
            event_id="E5", event_type=EventType.GOAL_SET,
            source="test", timestamp="", payload={}, trace_id="", schema_version="1.0",
        ))
        assert len(received) == 0

    def test_unsubscribe_nonexistent(self, bus):
        result = bus.unsubscribe("nonexistent-id")
        assert result is True  # simplified implementation

    def test_unsubscribe_all_types(self, bus):
        sid = bus.subscribe(EventType.GOAL_SET, lambda e: None)
        bus.subscribe(EventType.MEMORY_STORED, lambda e: None)
        bus.unsubscribe(sid)
        assert bus.subscriber_count(EventType.GOAL_SET) == 0


class TestSubscriberCount:
    def test_zero_initially(self, bus):
        assert bus.subscriber_count() == 0

    def test_counts_specific_type(self, bus):
        bus.subscribe(EventType.GOAL_SET, lambda e: None)
        bus.subscribe(EventType.GOAL_SET, lambda e: None)
        assert bus.subscriber_count(EventType.GOAL_SET) == 2

    def test_counts_all(self, bus):
        bus.subscribe(EventType.GOAL_SET, lambda e: None)
        bus.subscribe(EventType.MEMORY_STORED, lambda e: None)
        assert bus.subscriber_count() == 2


class TestClear:
    def test_clear_removes_all(self, bus):
        bus.subscribe(EventType.GOAL_SET, lambda e: None)
        bus.subscribe_all(lambda e: None)
        bus.clear()
        assert bus.subscriber_count() == 0
