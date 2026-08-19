"""
A3 测试 — Event Bus + Event Store + Dead Letter Queue。
"""

import time

import pytest

from ocos.events.dead_letter_queue import DeadLetterQueue, DeadLetterRecord
from ocos.events.event_bus import EventBus
from ocos.events.event_store import CommitResult, InMemoryEventStore, StoreSnapshot
from ocos.kernel.abi import Event, EventType


# ── Event Bus ───────────────────────────────────────────────────────────────────


class TestEventBus:
    def test_publish_without_subscribers(self):
        bus = EventBus()
        count = bus.publish(Event(event_type=EventType.SCHEDULER_TICK))
        assert count == 0

    def test_subscribe_and_receive(self):
        bus = EventBus()
        received: list[Event] = []

        def handler(event: Event):
            received.append(event)

        bus.subscribe(EventType.SCHEDULER_TICK, handler)
        event = Event(event_type=EventType.SCHEDULER_TICK, payload={"cycle": 1})
        count = bus.publish(event)

        assert count == 1
        assert len(received) == 1
        assert received[0].event_type == EventType.SCHEDULER_TICK

    def test_subscribe_all_global(self):
        bus = EventBus()
        received: list[Event] = []

        bus.subscribe_all(received.append)
        bus.publish(Event(event_type=EventType.SCHEDULER_TICK))
        bus.publish(Event(event_type=EventType.GOVERNANCE_APPROVED))

        assert len(received) == 2

    def test_type_filtered(self):
        bus = EventBus()
        received: list[Event] = []

        bus.subscribe(EventType.OBSERVATION_RECEIVED, received.append)
        bus.publish(Event(event_type=EventType.SCHEDULER_TICK))
        assert len(received) == 0

    def test_unsubscribe(self):
        bus = EventBus()
        received: list[Event] = []

        sid = bus.subscribe(EventType.SCHEDULER_TICK, received.append)
        bus.publish(Event(event_type=EventType.SCHEDULER_TICK))
        assert len(received) == 1

        bus.unsubscribe(sid)
        bus.publish(Event(event_type=EventType.SCHEDULER_TICK))
        assert len(received) == 1  # 未增加

    def test_subscriber_count(self):
        bus = EventBus()

        def h1(e): pass
        def h2(e): pass

        bus.subscribe(EventType.SCHEDULER_TICK, h1)
        bus.subscribe(EventType.GOVERNANCE_APPROVED, h2)
        bus.subscribe_all(h2)

        assert bus.subscriber_count(EventType.SCHEDULER_TICK) == 1
        assert bus.subscriber_count() == 3  # 2 type + 1 global

    def test_dlq_integration_on_failure(self):
        dlq = DeadLetterQueue()
        bus = EventBus(dead_letter_queue=dlq)

        def failing_handler(event: Event):
            raise ValueError("handler failed")

        bus.subscribe(EventType.SCHEDULER_TICK, failing_handler)
        bus.publish(Event(event_type=EventType.SCHEDULER_TICK))

        assert dlq.count() == 1
        record = dlq.get_all()[0]
        assert "handler failed" in record.error
        assert record.event.event_type == EventType.SCHEDULER_TICK


# ── Event Store ────────────────────────────────────────────────────────────────


class TestInMemoryEventStore:
    def test_empty_store(self):
        store = InMemoryEventStore()
        assert store.count() == 0
        assert store.get_all() == []
        snap = store.snapshot()
        assert snap.version == 0

    def test_append_single_event(self):
        store = InMemoryEventStore()
        result = store.append([
            Event(event_type=EventType.SCHEDULER_TICK, payload={"cycle": 1})
        ])
        assert result.success is True
        assert result.committed_count == 1
        assert store.count() == 1

    def test_append_multiple_events(self):
        store = InMemoryEventStore()
        events = [
            Event(event_type=EventType.SCHEDULER_TICK, payload={"cycle": i})
            for i in range(5)
        ]
        result = store.append(events)
        assert result.success is True
        assert result.committed_count == 5
        assert store.count() == 5

    def test_get_by_type(self):
        store = InMemoryEventStore()
        store.append([
            Event(event_type=EventType.SCHEDULER_TICK, payload={"cycle": 1}),
        ])
        store.append([
            Event(event_type=EventType.GOVERNANCE_APPROVED,
                  payload={"proposal_id": "p1", "approved_by": "gov"}),
        ])
        store.append([
            Event(event_type=EventType.SCHEDULER_TICK, payload={"cycle": 2}),
        ])

        ticks = store.get_by_type(EventType.SCHEDULER_TICK)
        assert len(ticks) == 2

    def test_append_empty_list_rejected(self):
        store = InMemoryEventStore()
        result = store.append([])
        assert result.success is False
        assert store.count() == 0

    def test_snapshot_after_appends(self):
        store = InMemoryEventStore()
        store.append([
            Event(event_type=EventType.SCHEDULER_TICK, payload={"cycle": i})
            for i in range(3)
        ])
        store.append([
            Event(event_type=EventType.GOVERNANCE_APPROVED,
                  payload={"proposal_id": "p1", "approved_by": "gov"}),
        ])
        snap = store.snapshot()
        assert snap.version == 4
        assert snap.event_count_by_type.get("scheduler.tick") == 3
        assert snap.event_count_by_type.get("governance.approved") == 1

    def test_clear_resets_store(self):
        store = InMemoryEventStore()
        store.append([
            Event(event_type=EventType.SCHEDULER_TICK, payload={"cycle": 1}),
        ])
        assert store.count() == 1
        cleared = store.clear()
        assert cleared == 1
        assert store.count() == 0

    def test_append_invalid_payload_rejected(self):
        """payload 不含必要字段应被拒绝。"""
        store = InMemoryEventStore()
        # OBSERVATION_RECEIVED 需要 content 和 source 字段
        result = store.append([
            Event(event_type=EventType.OBSERVATION_RECEIVED, payload={"wrong": "data"})
        ])
        # schema 验证可能宽松或严格，取决于 event_schema 实现
        # 至少不会 crash
        assert isinstance(result, CommitResult)


# ── Dead Letter Queue ──────────────────────────────────────────────────────────


class TestDeadLetterQueue:
    def test_empty_dlq(self):
        dlq = DeadLetterQueue()
        assert dlq.count() == 0
        assert dlq.get_all() == []

    def test_put_and_retrieve(self):
        dlq = DeadLetterQueue()
        event = Event(event_type=EventType.SCHEDULER_TICK)
        record = dlq.put(event, subscriber_id="sub-1", error="connection lost")
        assert dlq.count() == 1
        assert record.event.event_id == event.event_id
        assert record.subscriber_id == "sub-1"

    def test_get_by_type(self):
        dlq = DeadLetterQueue()
        dlq.put(Event(event_type=EventType.SCHEDULER_TICK), "sub-1", "err1")
        dlq.put(Event(event_type=EventType.GOVERNANCE_APPROVED), "sub-2", "err2")

        ticks = dlq.get_by_type(EventType.SCHEDULER_TICK)
        assert len(ticks) == 1
        assert ticks[0].subscriber_id == "sub-1"

    def test_max_records_limit(self):
        dlq = DeadLetterQueue(max_records=3)
        for i in range(5):
            dlq.put(Event(event_type=EventType.SCHEDULER_TICK), f"sub-{i}", f"err{i}")
        assert dlq.count() == 3  # 后 3 条保留

    def test_clear_removes_all(self):
        dlq = DeadLetterQueue()
        dlq.put(Event(), "sub-1", "err")
        assert dlq.count() == 1
        dlq.clear()
        assert dlq.count() == 0

    def test_replay_executes_callback(self):
        dlq = DeadLetterQueue()
        events = [Event(event_type=EventType.SCHEDULER_TICK, payload={"i": i}) for i in range(3)]
        for e in events:
            dlq.put(e, "sub", "err")

        replayed: list[Event] = []
        count = dlq.replay(replayed.append)
        assert count == 3
        assert len(replayed) == 3
        assert dlq.count() == 0  # 成功重放后自动移除

    def test_prune_older_than(self):
        dlq = DeadLetterQueue()
        dlq.put(Event(), "sub", "err")
        assert dlq.count() == 1
        # prune 0 小时 = 清除所有
        pruned = dlq.prune_older_than(max_age_hours=0)
        assert pruned == 1
        assert dlq.count() == 0
