"""OCOS event_memory/event_types 测试。"""

import pytest
from ocos.event_memory.event_types import (
    CognitiveEventType,
    EventConfidence,
    EventLifecyclePhase,
    EventReference,
    CognitiveEvent,
    EventHeader,
    EventArchive,
    EventQuery,
)


class TestCognitiveEventType:
    def test_values(self):
        assert CognitiveEventType.PERCEPTION.value == "perception"
        assert CognitiveEventType.ATTENTION.value == "attention"
        assert CognitiveEventType.DECISION.value == "decision"
        assert CognitiveEventType.ACTION.value == "action"
        assert CognitiveEventType.RESULT.value == "result"
        assert CognitiveEventType.LEARNING.value == "learning"
        assert CognitiveEventType.INTERACTION.value == "interaction"
        assert CognitiveEventType.HEALTH.value == "health"
        assert CognitiveEventType.EVOLUTION.value == "evolution"


class TestEventConfidence:
    def test_values(self):
        assert EventConfidence.CERTAIN.value == "certain"
        assert EventConfidence.HIGH.value == "high"
        assert EventConfidence.MEDIUM.value == "medium"
        assert EventConfidence.LOW.value == "low"


class TestEventLifecyclePhase:
    def test_values(self):
        assert EventLifecyclePhase.HOT.value == "hot"
        assert EventLifecyclePhase.WARM.value == "warm"
        assert EventLifecyclePhase.COLD.value == "cold"
        assert EventLifecyclePhase.ARCHIVED.value == "archived"


class TestEventReference:
    def test_creation(self):
        ref = EventReference(
            event_id="e1",
            event_type=CognitiveEventType.ACTION,
            timestamp=1234567890.0,
        )
        assert ref.event_id == "e1"
        assert ref.event_type == CognitiveEventType.ACTION
        assert ref.timestamp == 1234567890.0

    def test_frozen(self):
        ref = EventReference(
            event_id="e2",
            event_type=CognitiveEventType.ACTION,
            timestamp=1234567890.0,
        )
        with pytest.raises(AttributeError):
            ref.event_id = "modified"


class TestCognitiveEvent:
    def test_custom_event(self):
        event = CognitiveEvent(
            event_id="e1",
            event_type=CognitiveEventType.DECISION,
            source="decision_engine",
            context={"goal_id": "g1"},
            payload={"option": "a"},
            confidence=EventConfidence.HIGH,
        )
        assert event.event_id == "e1"
        assert event.source == "decision_engine"
        assert event.context == {"goal_id": "g1"}
        assert event.payload == {"option": "a"}
        assert event.confidence == EventConfidence.HIGH

    def test_default_values(self):
        event = CognitiveEvent(
            event_id="e2",
            event_type=CognitiveEventType.ACTION,
        )
        assert event.source == ""
        assert event.context == {}
        assert event.confidence == EventConfidence.HIGH
        assert event.lifecycle == EventLifecyclePhase.HOT

    def test_is_recent_property(self):
        import time
        event = CognitiveEvent(
            event_id="e3",
            event_type=CognitiveEventType.RESULT,
            timestamp=time.time(),
        )
        assert event.is_recent is True

    def test_age_seconds_property(self):
        import time
        event = CognitiveEvent(
            event_id="e4",
            event_type=CognitiveEventType.RESULT,
            timestamp=time.time() - 1800,
        )
        assert event.age_seconds > 1700

    def test_to_reference(self):
        event = CognitiveEvent(
            event_id="e5",
            event_type=CognitiveEventType.ACTION,
            timestamp=1234567890.0,
        )
        ref = event.to_reference()
        assert ref.event_id == "e5"
        assert ref.event_type == CognitiveEventType.ACTION
        assert ref.timestamp == 1234567890.0

    def test_with_lifecycle(self):
        event = CognitiveEvent(
            event_id="e6",
            event_type=CognitiveEventType.ACTION,
        )
        archived = event.with_lifecycle(EventLifecyclePhase.ARCHIVED)
        assert archived.lifecycle == EventLifecyclePhase.ARCHIVED
        # Original should be unchanged (frozen)
        assert event.lifecycle == EventLifecyclePhase.HOT

    def test_frozen(self):
        event = CognitiveEvent(
            event_id="e7",
            event_type=CognitiveEventType.ACTION,
        )
        # Should not be able to modify
        with pytest.raises(AttributeError):
            event.event_id = "modified"


class TestEventHeader:
    def test_from_event(self):
        event = CognitiveEvent(
            event_id="e8",
            event_type=CognitiveEventType.DECISION,
            source="engine",
            context={"key1": "value1", "key2": "value2"},
            confidence=EventConfidence.MEDIUM,
        )
        header = EventHeader.from_event(event)
        assert header.event_id == "e8"
        assert header.source == "engine"
        assert set(header.context_keys) == {"key1", "key2"}
        assert header.confidence == EventConfidence.MEDIUM


class TestEventArchive:
    def test_empty_archive(self):
        archive = EventArchive(
            archive_id="a1",
            start_time=1000.0,
            end_time=2000.0,
            event_count=10,
        )
        assert archive.compressed_data == b""
        assert archive.checksum == ""
        assert archive.can_restore() is False

    def test_valid_archive(self):
        archive = EventArchive(
            archive_id="a2",
            start_time=1000.0,
            end_time=2000.0,
            event_count=10,
            compressed_data=b"fake_data",
            checksum="abc123",
        )
        assert archive.can_restore() is True


class TestEventQuery:
    def test_defaults(self):
        query = EventQuery()
        assert query.event_types is None
        assert query.limit == 100
        assert query.offset == 0

    def test_custom(self):
        query = EventQuery(
            event_types=[CognitiveEventType.ACTION],
            sources=["decision_engine"],
            time_from=1000.0,
            time_to=2000.0,
            limit=50,
            offset=10,
        )
        assert len(query.event_types) == 1
        assert query.limit == 50