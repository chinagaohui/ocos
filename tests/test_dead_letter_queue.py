"""OCOS dead_letter_queue 死信队列测试。"""

import pytest
from ocos.events.dead_letter_queue import DeadLetterQueue, DeadLetterRecord
from ocos.kernel.abi import Event, EventType


@pytest.fixture
def event():
    return Event(
        event_id="E-DLQ-001",
        event_type=EventType.GOAL_SET,
        source="test",
        timestamp="",
        payload={"goal_id": "G1"},
        trace_id="",
        schema_version="1.0",
    )


class TestDeadLetterRecord:
    def test_defaults(self):
        r = DeadLetterRecord()
        assert r.record_id == ""
        assert r.subscriber_id == ""
        assert r.error == ""
        assert r.retry_count == 0

    def test_custom(self):
        r = DeadLetterRecord(
            record_id="REC-001",
            event=Event(event_id="E1", event_type=EventType.TRACE_RECORDED,
                        source="t", timestamp="", payload={}, trace_id="", schema_version="1.0"),
            subscriber_id="sub-1",
            error="callback failed",
            retry_count=2,
        )
        assert r.retry_count == 2
        assert r.error == "callback failed"


class TestDeadLetterQueue:
    @pytest.fixture
    def dlq(self):
        return DeadLetterQueue(max_records=10)

    def test_empty_initially(self, dlq, event):
        assert dlq.count() == 0
        assert dlq.get_all() == []

    def test_put_adds_record(self, dlq, event):
        record = dlq.put(event, "sub-1", "callback error")
        assert record.event.event_id == event.event_id
        assert record.subscriber_id == "sub-1"
        assert record.error == "callback error"
        assert dlq.count() == 1

    def test_get_by_type_filters(self, dlq):
        e1 = Event(event_id="E1", event_type=EventType.GOAL_SET,
                   source="t", timestamp="", payload={}, trace_id="", schema_version="1.0")
        e2 = Event(event_id="E2", event_type=EventType.MEMORY_STORED,
                   source="t", timestamp="", payload={}, trace_id="", schema_version="1.0")
        dlq.put(e1, "s1", "err1")
        dlq.put(e2, "s2", "err2")
        goal_records = dlq.get_by_type(EventType.GOAL_SET)
        memory_records = dlq.get_by_type(EventType.MEMORY_STORED)
        assert len(goal_records) == 1
        assert len(memory_records) == 1
        assert goal_records[0].event.event_id == "E1"
        assert memory_records[0].event.event_id == "E2"

    def test_max_records_limit(self):
        dlq = DeadLetterQueue(max_records=3)
        for i in range(5):
            e = Event(event_id=f"E{i}", event_type=EventType.GOAL_SET,
                      source="t", timestamp="", payload={}, trace_id="", schema_version="1.0")
            dlq.put(e, "s", f"error {i}")
        assert dlq.count() == 3
        ids = [r.event.event_id for r in dlq.get_all()]
        assert "E2" in ids
        assert "E4" in ids
        assert "E0" not in ids  # evicted

    def test_replay_success(self, dlq, event):
        dlq.put(event, "sub-1", "error")
        received = []
        count = dlq.replay(lambda e: received.append(e))
        assert count == 1
        assert len(received) == 1
        assert received[0].event_id == "E-DLQ-001"
        assert dlq.count() == 0  # emptied after replay

    def test_replay_partial(self, dlq, event):
        for i in range(5):
            e = Event(event_id=f"E{i}", event_type=EventType.GOAL_SET,
                      source="t", timestamp="", payload={}, trace_id="", schema_version="1.0")
            dlq.put(e, "s", "err")
        count = dlq.replay(lambda e: None, max_records=2)
        assert count == 2
        assert dlq.count() == 3

    def test_replay_callback_raises(self, dlq, event):
        dlq.put(event, "sub-1", "original error")
        def bad_cb(e):
            raise RuntimeError("replay failed")
        count = dlq.replay(bad_cb)
        # Replayed once, callback failed → re-queued with retry_count=1
        assert count == 0
        assert dlq.count() == 1
        record = dlq.get_all()[0]
        assert record.retry_count == 1

    def test_clear(self, dlq, event):
        dlq.put(event, "s", "err")
        dlq.put(Event(event_id="E2", event_type=EventType.MEMORY_STORED,
                      source="t", timestamp="", payload={}, trace_id="", schema_version="1.0"),
                "s", "err2")
        removed = dlq.clear()
        assert removed == 2
        assert dlq.count() == 0

    def test_prune_older_than(self, dlq, event):
        import time
        dlq.put(event, "s", "err")
        # Fresh record should not be pruned
        pruned = dlq.prune_older_than(max_age_hours=24)
        assert pruned == 0
        assert dlq.count() == 1
