"""Phase 54: Event Memory Infrastructure — Tests.

验收:
    EM54-01: Event Integrity — 事件不可篡改
    EM54-02: Timeline Reconstruction — 时间线重建
    EM54-03: Replay Isolation — 回放不含副作用
    EM54-04: Memory Separation — 事件 ≠ 记忆
    EM54-05: Persistence — 跨 session 恢复
    EM54-06: Query — 多维查询
"""

import pytest
import time
import uuid

from ocos.event_memory.event_types import (
    CognitiveEventType, EventConfidence, EventLifecyclePhase,
    EventReference, CognitiveEvent,
    EventQuery as EventQueryParams,
)
from ocos.event_memory.event_store import EventStore
from ocos.event_memory.event_index import EventIndex
from ocos.event_memory.event_replay import EventReplay
from ocos.event_memory.event_archive import (
    EventArchiveManager, LifecycleConfig,
)
from ocos.event_memory.event_validator import (
    EventValidator, ValidationCode,
)
from ocos.event_memory.event_query import EventQueryEngine
from ocos.event_memory.event_lifecycle import EventLifecycle


def make_event(event_id="ev-001", **kw):
    defaults = {
        "event_id": event_id,
        "event_type": CognitiveEventType.PERCEPTION,
        "source": "test",
    }
    defaults.update(kw)
    return CognitiveEvent(**defaults)


# ══════════════════════════════════════════════════
# Event Types
# ══════════════════════════════════════════════════

class TestEventTypes:
    def test_frozen_immutable(self):
        """CognitiveEvent 是 frozen dataclass，不可修改。"""
        event = make_event()
        with pytest.raises(Exception):
            event.event_id = "new-id"

    def test_to_reference(self):
        event = make_event()
        ref = event.to_reference()
        assert ref.event_id == "ev-001"
        assert ref.event_type == CognitiveEventType.PERCEPTION

    def test_with_lifecycle(self):
        event = make_event()
        archived = event.with_lifecycle(EventLifecyclePhase.ARCHIVED)
        assert archived.lifecycle == EventLifecyclePhase.ARCHIVED
        assert archived.archived_at > 0
        # 原事件不变
        assert event.lifecycle == EventLifecyclePhase.HOT

    def test_age(self):
        event = make_event()
        assert event.age_seconds >= 0

    def test_is_recent(self):
        event = make_event()
        assert event.is_recent is True

    def test_causal_chain(self):
        ref = EventReference("ev-0", CognitiveEventType.PERCEPTION, time.time())
        event = make_event(caused_by=ref)
        assert event.caused_by.event_id == "ev-0"

    def test_all_event_types(self):
        for t in CognitiveEventType:
            event = make_event(event_type=t)
            assert event.event_type == t

    def test_confidence_levels(self):
        for c in EventConfidence:
            event = make_event(confidence=c)
            assert event.confidence == c


# ══════════════════════════════════════════════════
# Event Store
# ══════════════════════════════════════════════════

class TestEventStore:
    def test_append_and_find(self):
        store = EventStore()
        event = make_event("ev-1")
        assert store.append(event) is True
        assert store.find("ev-1") is event

    def test_append_duplicate_id(self):
        store = EventStore()
        assert store.append(make_event("ev-1")) is True
        assert store.append(make_event("ev-1")) is False

    def test_append_batch(self):
        store = EventStore()
        events = [
            make_event(f"ev-{i}") for i in range(5)
        ]
        n = store.append_batch(events)
        assert n == 5
        assert store.stats()["total_events"] == 5

    def test_range_query(self):
        store = EventStore()
        t0 = time.time()
        events = [
            make_event(f"ev-{i}", timestamp=t0 + i * 10)
            for i in range(5)
        ]
        store.append_batch(events)

        results = store.range(time_from=t0 + 5, time_to=t0 + 25)
        assert len(results) >= 1

    def test_range_empty(self):
        store = EventStore()
        assert store.range() == []

    def test_stats(self):
        store = EventStore()
        store.append(make_event("ev-1"))
        s = store.stats()
        assert s["total_events"] == 1
        assert s["earliest"] > 0

    def test_clear(self):
        store = EventStore()
        store.append(make_event("ev-1"))
        store.clear()
        assert store.stats()["total_events"] == 0

    def test_snapshot_and_restore(self):
        store = EventStore()
        store.append(make_event(
            "ev-1",
            event_type=CognitiveEventType.DECISION,
            context={"goal_id": "goal-A", "entities": ["opentale"]},
            payload="test payload",
        ))
        snap = store.snapshot()
        assert len(snap["events"]) == 1

        store2 = EventStore()
        n = store2.restore(snap)
        assert n == 1
        restored = store2.find("ev-1")
        assert restored is not None
        assert restored.event_type == CognitiveEventType.DECISION
        assert restored.context["goal_id"] == "goal-A"


# ══════════════════════════════════════════════════
# Event Index
# ══════════════════════════════════════════════════

class TestEventIndex:
    def test_index_by_type(self):
        idx = EventIndex()
        e = make_event(event_type=CognitiveEventType.DECISION)
        idx.index(e)
        assert e.event_id in idx.by_type[CognitiveEventType.DECISION]

    def test_index_by_entity(self):
        idx = EventIndex()
        e = make_event(
            context={"entities": ["opentale", "hermes"]},
        )
        idx.index(e)
        assert e.event_id in idx.by_entity["opentale"]
        assert e.event_id in idx.by_entity["hermes"]

    def test_index_by_goal(self):
        idx = EventIndex()
        e = make_event(context={"goal_id": "goal-42"})
        idx.index(e)
        assert e.event_id in idx.by_goal["goal-42"]

    def test_index_by_source(self):
        idx = EventIndex()
        e = make_event(source="perception")
        idx.index(e)
        assert e.event_id in idx.by_source["perception"]

    def test_query_intersection(self):
        idx = EventIndex()
        e1 = make_event(
            "ev-1",
            event_type=CognitiveEventType.DECISION,
            context={"goal_id": "goal-A", "entities": ["stock"]},
        )
        e2 = make_event(
            "ev-2",
            event_type=CognitiveEventType.ACTION,
            context={"goal_id": "goal-B", "entities": ["stock"]},
        )
        idx.index(e1)
        idx.index(e2)

        results = idx.query(
            event_type=CognitiveEventType.DECISION,
            entity="stock",
        )
        assert "ev-1" in results
        assert "ev-2" not in results

    def test_query_empty_result(self):
        idx = EventIndex()
        assert idx.query(entity="nonexistent") == []

    def test_reverse_index(self):
        idx = EventIndex()
        e = make_event(
            "ev-1", context={"goal_id": "G", "entities": ["E"]},
        )
        idx.index(e)
        rev = idx.get_reverse("ev-1")
        assert "E" in rev["entities"]
        assert rev["goal_id"] == "G"


# ══════════════════════════════════════════════════
# Event Replay
# ══════════════════════════════════════════════════

class TestEventReplay:
    def test_replay_range(self):
        store = EventStore()
        t0 = time.time()
        store.append(make_event("ev-1", timestamp=t0))
        store.append(make_event("ev-2", timestamp=t0 + 1))
        store.append(make_event("ev-3", timestamp=t0 + 2))

        replay = EventReplay()
        session = replay.replay_range(store, t0, t0 + 2)
        assert len(session.events) >= 2

    def test_replay_navigation(self):
        store = EventStore()
        t0 = time.time()
        store.append(make_event("ev-1", timestamp=t0))
        store.append(make_event("ev-2", timestamp=t0 + 1))

        replay = EventReplay()
        session = replay.replay_range(store, t0, t0 + 2)

        assert session.current() is not None
        first = session.current().event_id
        session.next()
        assert session.current().event_id != first
        session.reset()
        assert session.current().event_id == first

    def test_trace_causal_chain(self):
        store = EventStore()
        t0 = time.time()

        e1 = make_event("ev-1", timestamp=t0)
        e2 = make_event(
            "ev-2", timestamp=t0 + 1,
            caused_by=e1.to_reference(),
        )
        e3 = make_event(
            "ev-3", timestamp=t0 + 2,
            caused_by=e2.to_reference(),
        )

        store.append_batch([e1, e2, e3])

        replay = EventReplay()
        chain = replay.trace_causal_chain(e3, store)
        # chain is ordered earliest→latest
        assert chain[0].event_id == "ev-1"
        assert chain[-1].event_id == "ev-3"

    def test_reconstruct_timeline(self):
        store = EventStore()
        store.append(make_event("ev-1", context={"goal_id": "goal-A"}))
        store.append(make_event("ev-2", context={"goal_id": "goal-B"}))
        store.append(make_event("ev-3", context={"goal_id": "goal-A"}))

        replay = EventReplay()
        timeline = replay.reconstruct_timeline(store, "goal-A")
        assert len(timeline) == 2

    def test_generate_reflection(self):
        replay = EventReplay()
        events = [
            make_event("ev-1", event_type=CognitiveEventType.PERCEPTION,
                        context={"topics": ["architecture"]}),
            make_event("ev-2", event_type=CognitiveEventType.DECISION,
                        context={"decision": "refactor"}),
            make_event("ev-3", event_type=CognitiveEventType.LEARNING,
                        payload="learned: tests first"),
        ]
        reflection = replay.generate_reflection(events)
        assert reflection["event_count"] == 3
        assert "architecture" in reflection["key_topics"]
        assert len(reflection["decisions"]) == 1

    def test_generate_evolution_narrative(self):
        replay = EventReplay()
        t0 = time.time()
        events = [
            make_event("ev-1", timestamp=t0,
                       event_type=CognitiveEventType.PERCEPTION, source="user"),
            make_event("ev-2", timestamp=t0 + 1,
                       event_type=CognitiveEventType.DECISION,
                       context={"decision": "audit first"}),
            make_event("ev-3", timestamp=t0 + 2,
                       event_type=CognitiveEventType.LEARNING,
                       payload="user prefers boundary checks"),
        ]
        narrative = replay.generate_evolution_narrative(events)
        assert len(narrative) == 3
        joined = "".join(narrative)
        assert "audit" in joined or "decision" in joined


# ══════════════════════════════════════════════════
# Event Archive
# ══════════════════════════════════════════════════

class TestEventArchive:
    def test_archive_and_restore(self):
        mgr = EventArchiveManager()
        t0 = time.time()
        events = [
            make_event(f"ev-{i}", timestamp=t0 + i)
            for i in range(10)
        ]

        archive = mgr.archive_batch(events)
        assert archive.event_count == 10
        assert archive.can_restore() is True

        restored = mgr.restore_archive(archive.archive_id)
        assert len(restored) == 10

    def test_archive_checksum_validation(self):
        mgr = EventArchiveManager()
        events = [make_event("ev-1")]
        archive = mgr.archive_batch(events)

        # 篡改数据
        archive.compressed_data = archive.compressed_data + b"tampered"

        with pytest.raises(RuntimeError, match="checksum"):
            mgr.restore_archive(archive.archive_id)

    def test_lifecycle_apply(self):
        store = EventStore()
        config = LifecycleConfig(hot_ttl_seconds=0.001, warm_ttl_seconds=0.001)
        mgr = EventArchiveManager(config=config)

        event = make_event("ev-1", timestamp=time.time() - 10)
        store.append(event)

        stats = mgr.apply_lifecycle(store)
        assert stats["to_archived"] == 1

    def test_clear(self):
        mgr = EventArchiveManager()
        events = [make_event("ev-1")]
        mgr.archive_batch(events)
        mgr.clear()
        assert len(mgr.archives) == 0
        assert mgr.total_archived == 0


# ══════════════════════════════════════════════════
# Event Validator
# ══════════════════════════════════════════════════

class TestEventValidator:
    def test_valid_event(self):
        v = EventValidator()
        result = v.validate_event(make_event("ev-1", payload="hello"))
        assert result.code == ValidationCode.PASS

    def test_missing_id(self):
        v = EventValidator()
        result = v.validate_event(make_event(""))
        assert result.code == ValidationCode.FAIL

    def test_future_timestamp(self):
        v = EventValidator()
        event = make_event("ev-1", timestamp=time.time() + 3600)
        result = v.validate_event(event)
        assert result.code == ValidationCode.WARN

    def test_empty_payload_and_context(self):
        v = EventValidator()
        event = make_event("ev-1", payload=None, context={})
        result = v.validate_event(event)
        assert result.code == ValidationCode.WARN

    def test_validate_store(self):
        store = EventStore()
        store.append(make_event("ev-1"))
        v = EventValidator()
        result = v.validate_store(store)
        assert result.code == ValidationCode.PASS

    def test_validate_timeline_order(self):
        v = EventValidator()
        e1 = make_event("ev-1", timestamp=100)
        e2 = make_event("ev-2", timestamp=50)  # 时间倒流
        result = v.validate_timeline([e1, e2])
        assert result.code == ValidationCode.FAIL

    def test_validate_timeline_valid(self):
        v = EventValidator()
        events = [
            make_event("ev-1", timestamp=100,
                        event_type=CognitiveEventType.PERCEPTION),
            make_event("ev-2", timestamp=200,
                        event_type=CognitiveEventType.DECISION),
        ]
        result = v.validate_timeline(events)
        assert result.code == ValidationCode.PASS

    def test_validate_replay_safety(self):
        v = EventValidator()
        events = [
            make_event("ev-1", event_type=CognitiveEventType.ACTION),
        ]
        result = v.validate_replay_safety(events)
        assert result.code == ValidationCode.WARN  # not marked replay_safe

    def test_validate_replay_safe_marked(self):
        v = EventValidator()
        events = [
            make_event("ev-1",
                        event_type=CognitiveEventType.ACTION,
                        metadata={"replay_safe": True}),
        ]
        result = v.validate_replay_safety(events)
        assert result.code == ValidationCode.PASS

    def test_mark_invalid(self):
        v = EventValidator()
        v.mark_invalid("ev-bad")
        result = v.validate_event(make_event("ev-bad"))
        assert result.code == ValidationCode.FAIL


# ══════════════════════════════════════════════════
# Event Lifecycle — 完整集成
# ══════════════════════════════════════════════════

class TestEventLifecycle:
    def test_record_and_find(self):
        el = EventLifecycle()
        event = el.record(
            CognitiveEventType.PERCEPTION,
            source="user",
            payload={"text": "hello"},
        )
        assert event.event_id.startswith("ev-perception-")
        found = el.store.find(event.event_id)
        assert found is not None
        assert found.payload == {"text": "hello"}

    def test_record_with_causal_chain(self):
        el = EventLifecycle()
        e1 = el.record(CognitiveEventType.PERCEPTION, source="user")
        e2 = el.record(
            CognitiveEventType.DECISION,
            source="decision_engine",
            caused_by_id=e1.event_id,
            context={"decision": "audit"},
        )

        chain = el.query_engine.get_context(e2.event_id, radius=1)
        assert any(c.event_id == e1.event_id for c in chain)

    def test_record_batch(self):
        el = EventLifecycle()
        results = el.record_batch([
            {"event_type": CognitiveEventType.PERCEPTION, "source": "user"},
            {"event_type": CognitiveEventType.ATTENTION, "source": "attention"},
            {"event_type": CognitiveEventType.DECISION, "source": "decision"},
        ])
        assert len(results) == 3
        assert el.total_recorded == 3

    def test_query_by_type(self):
        el = EventLifecycle()
        el.record(CognitiveEventType.PERCEPTION)
        el.record(CognitiveEventType.DECISION)
        el.record(CognitiveEventType.ACTION)

        params = EventQueryParams(
            event_types=[CognitiveEventType.DECISION],
        )
        result = el.query(params)
        assert result.total_hits == 1

    def test_query_by_entity(self):
        el = EventLifecycle()
        el.record(
            CognitiveEventType.PERCEPTION,
            context={"entities": ["opentale"]},
        )
        el.record(
            CognitiveEventType.DECISION,
            context={"entities": ["hermes"]},
        )

        params = EventQueryParams(entity="opentale")
        result = el.query(params)
        assert result.total_hits == 1

    def test_query_by_goal(self):
        el = EventLifecycle()
        el.record(
            CognitiveEventType.DECISION,
            context={"goal_id": "stock-analysis"},
        )

        params = EventQueryParams(goal_id="stock-analysis")
        result = el.query(params)
        assert result.total_hits == 1

    def test_persistence_roundtrip(self):
        """EM54-05: 跨 session 持久化。"""
        el1 = EventLifecycle()
        el1.record(CognitiveEventType.PERCEPTION, payload="day1 data")
        el1.record(CognitiveEventType.DECISION,
                     context={"goal_id": "project-1"})

        snap = el1.snapshot()

        # 模拟新 session
        el2 = EventLifecycle()
        count = el2.restore(snap)
        assert count == 2

        params = EventQueryParams(goal_id="project-1")
        result = el2.query(params)
        assert result.total_hits == 1

    def test_maintain_lifecycle(self):
        """事件生命周期降级。"""
        el = EventLifecycle()
        el.archiver.config.hot_ttl_seconds = 0.001
        el.archiver.config.warm_ttl_seconds = 0.001

        # 创建过去时间的事件并手动放入 store
        past_ts = time.time() - 10
        old_event = CognitiveEvent(
            event_id="ev-old",
            event_type=CognitiveEventType.PERCEPTION,
            timestamp=past_ts,
            source="test",
            payload="old",
        )
        el.store.append(old_event)
        el.index.index(old_event)

        stats = el.maintain()
        found = el.store.find("ev-old")
        assert found is not None
        # 过去 10 秒的事件应被归档 (超过 warm_ttl)
        assert found.lifecycle == EventLifecyclePhase.ARCHIVED

    def test_deduplication(self):
        """同一 session 同一 ID 不重复。"""
        el = EventLifecycle()
        e1 = el.record(
            CognitiveEventType.PERCEPTION,
            source="sensor",
        )
        # Direct append with same ID should fail
        dup = make_event(e1.event_id)
        assert el.store.append(dup) is False

    def test_clear_and_reset(self):
        el = EventLifecycle()
        el.record(CognitiveEventType.PERCEPTION)
        el.clear()
        assert el.total_recorded == 0
        assert el.store.stats()["total_events"] == 0
