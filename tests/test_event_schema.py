"""OCOS event_schema 事件模式测试。

宪法 Part 2: Event Model
- Event 序列化/反序列化往返一致
- schema_version MAJOR 必须匹配
- EVENT_SCHEMA_REGISTRY 中每个 EventType 有 description
- validate_event_payload 正确验证必填字段
"""

import pytest
from datetime import datetime, timezone

from ocos.kernel.abi import Event, EventType, SCHEMA_VERSION
from ocos.kernel.event_schema import (
    serialize_event,
    deserialize_event,
    validate_schema_version,
    EVENT_SCHEMA_REGISTRY,
    validate_event_payload,
)


class TestSerializeDeserialize:
    """Event 往返一致性。"""

    def test_roundtrip(self):
        original = Event(
            event_id="EVT-001",
            event_type=EventType.OBSERVATION_RECEIVED,
            source="external",
            timestamp="2026-01-01T00:00:00Z",
            payload={"content": "hello", "source": "user"},
            trace_id="TRC-001",
            schema_version=SCHEMA_VERSION,
        )
        raw = serialize_event(original)
        restored = deserialize_event(raw)
        assert restored.event_id == original.event_id
        assert restored.event_type == original.event_type
        assert restored.source == original.source
        assert restored.payload == original.payload
        assert restored.schema_version == original.schema_version

    def test_roundtrip_dict_input(self):
        data = {
            "event_id": "EVT-002",
            "event_type": "trace.recorded",
            "source": "runtime",
            "timestamp": "2026-01-01T00:00:00Z",
            "payload": {"trace_id": "T", "trace_type": "decision"},
            "trace_id": "",
            "schema_version": "1.0.0",
        }
        restored = deserialize_event(data)
        assert restored.event_id == "EVT-002"
        assert restored.event_type == EventType.TRACE_RECORDED

    def test_missing_fields_fallback(self):
        empty = "{}"
        e = deserialize_event(empty)
        assert e.event_id == ""
        assert e.payload == {}
        assert e.schema_version == SCHEMA_VERSION

    def test_json_format_valid(self):
        e = Event(
            event_id="EVT-003",
            event_type=EventType.TRACE_RECORDED,
            source="kernel",
            timestamp="",
            payload={"trace_id": "T", "trace_type": "decision"},
            trace_id="",
            schema_version=SCHEMA_VERSION,
        )
        raw = serialize_event(e)
        import json
        data = json.loads(raw)
        assert "event_id" in data
        assert data["event_id"] == "EVT-003"


class TestSchemaVersionValidation:
    """schema_version MAJOR 必须匹配。"""

    def test_same_major_passes(self):
        assert validate_schema_version("1.2.3") is True
        assert validate_schema_version("1.0.0") is True

    def test_different_major_fails(self):
        assert validate_schema_version("2.0.0") is False
        assert validate_schema_version("0.9.0") is False

    def test_empty_version_fails(self):
        assert validate_schema_version("") is False
        assert validate_schema_version(None) is False  # type: ignore[arg-type]


class TestEventSchemaRegistry:
    """EVENT_SCHEMA_REGISTRY 完整性。"""

    def test_all_event_types_have_schema(self):
        """每个 EventType 必须在注册表中。"""
        for et in EventType:
            assert et in EVENT_SCHEMA_REGISTRY, f"Missing schema for {et.value}"

    def test_all_schemas_have_description(self):
        """每个 schema 必须有 description。"""
        for et, schema in EVENT_SCHEMA_REGISTRY.items():
            assert "description" in schema, f"Missing description for {et.value}"
            assert len(schema["description"]) > 0

    def test_all_schemas_have_required_fields(self):
        """每个 schema 必须有 required_payload_fields。"""
        for et, schema in EVENT_SCHEMA_REGISTRY.items():
            assert "required_payload_fields" in schema


class TestValidateEventPayload:
    """validate_event_payload 正确验证。"""

    def test_valid_observation_payload(self):
        assert validate_event_payload(
            EventType.OBSERVATION_RECEIVED,
            {"content": "test", "source": "user"}
        ) is True

    def test_missing_required_field_fails(self):
        assert validate_event_payload(
            EventType.OBSERVATION_RECEIVED,
            {"content": "test"}  # missing "source"
        ) is False

    def test_unknown_event_type_fails(self):
        """未注册的 EventType 返回 False。"""
        assert validate_event_payload(
            EventType.TRACE_RECORDED,
            {}  # missing trace_id and trace_type
        ) is False

    def test_goal_set_payload(self):
        assert validate_event_payload(
            EventType.GOAL_SET,
            {"goal_id": "GOAL-001", "description": "写书", "priority": 3}
        ) is True

    def test_decision_executed_payload(self):
        assert validate_event_payload(
            EventType.DECISION_EXECUTED,
            {"decision_id": "DEC-001"}
        ) is True
