"""Information Transformation 事件测试。

对应 Phase 15 — Process Foundation 的 3 个统一事件：
- INFORMATION_TRANSFORMATION_STARTED
- INFORMATION_TRANSFORMATION_COMPLETED
- INFORMATION_TRANSFORMATION_FAILED

测试通过 EventBus 发射和接收，验证事件 schema 正确性。
"""

import pytest

from ocos.kernel.abi import Event, EventType
from ocos.events.event_bus import EventBus
from ocos.kernel.event_schema import EVENT_SCHEMA_REGISTRY, validate_event_payload


class TestTransformationEventValues:
    """事件枚举值的有效性验证。"""

    def test_started_event_value(self):
        assert EventType.INFORMATION_TRANSFORMATION_STARTED.value == "information.transformation_started"

    def test_completed_event_value(self):
        assert EventType.INFORMATION_TRANSFORMATION_COMPLETED.value == "information.transformation_completed"

    def test_failed_event_value(self):
        assert EventType.INFORMATION_TRANSFORMATION_FAILED.value == "information.transformation_failed"


class TestTransformationEventSchemas:
    """事件 schema 注册验证。"""

    def test_started_schema_registered(self):
        schema = EVENT_SCHEMA_REGISTRY.get(EventType.INFORMATION_TRANSFORMATION_STARTED)
        assert schema is not None
        assert "process_id" in schema["required_payload_fields"]
        assert "process_type" in schema["required_payload_fields"]
        assert "input_addresses" in schema["required_payload_fields"]

    def test_completed_schema_registered(self):
        schema = EVENT_SCHEMA_REGISTRY.get(EventType.INFORMATION_TRANSFORMATION_COMPLETED)
        assert schema is not None
        assert "process_id" in schema["required_payload_fields"]
        assert "process_type" in schema["required_payload_fields"]
        assert "output_addresses" in schema["required_payload_fields"]

    def test_failed_schema_registered(self):
        schema = EVENT_SCHEMA_REGISTRY.get(EventType.INFORMATION_TRANSFORMATION_FAILED)
        assert schema is not None
        assert "process_id" in schema["required_payload_fields"]
        assert "process_type" in schema["required_payload_fields"]
        assert "error" in schema["required_payload_fields"]

    def test_no_redundant_reasoning_events(self):
        """验证不存在遗留的独立 Reasoning 事件。"""
        assert not hasattr(EventType, "REASONING_STARTED")
        assert not hasattr(EventType, "REASONING_COMPLETED")
        assert not hasattr(EventType, "REASONING_FAILED")
        assert not hasattr(EventType, "INFORMATION_REASONING_STARTED")

    def test_no_individual_process_events(self):
        """验证不存在按 ProcessType 拆分的独立事件。"""
        for suffix in ["reasoning", "planning", "simulation", "learning"]:
            started = f"information.{suffix}_started"
            completed = f"information.{suffix}_completed"
            failed = f"information.{suffix}_failed"
            for member in EventType:
                assert member.value != started, f"不应存在独立事件 {started}"
                assert member.value != completed, f"不应存在独立事件 {completed}"
                assert member.value != failed, f"不应存在独立事件 {failed}"


class TestTransformationEventLifecycle:
    """3 个转换事件的完整生命周期验证。"""

    @pytest.fixture
    def bus(self):
        return EventBus()

    def test_started_event_roundtrip(self, bus):
        """发射 INFORMATION_TRANSFORMATION_STARTED 并验证。"""
        received_events = []
        bus.subscribe(EventType.INFORMATION_TRANSFORMATION_STARTED, lambda e: received_events.append(e))

        event = Event(
            event_type=EventType.INFORMATION_TRANSFORMATION_STARTED,
            source="test",
            payload={
                "process_id": "proc-001",
                "process_type": "reasoning",
                "input_addresses": ["info:observation:obs-001", "info:knowledge:k-001"],
            },
        )
        bus.publish(event, sync=True)

        assert len(received_events) == 1
        assert received_events[0].payload["process_id"] == "proc-001"
        assert received_events[0].payload["process_type"] == "reasoning"

    def test_completed_event_roundtrip(self, bus):
        """发射 INFORMATION_TRANSFORMATION_COMPLETED 并验证。"""
        received_events = []
        bus.subscribe(EventType.INFORMATION_TRANSFORMATION_COMPLETED, lambda e: received_events.append(e))

        event = Event(
            event_type=EventType.INFORMATION_TRANSFORMATION_COMPLETED,
            source="test",
            payload={
                "process_id": "proc-001",
                "process_type": "reasoning",
                "output_addresses": ["info:hypothesis:hyp-001"],
            },
        )
        bus.publish(event, sync=True)

        assert len(received_events) == 1
        assert received_events[0].payload["output_addresses"] == ["info:hypothesis:hyp-001"]

    def test_failed_event_roundtrip(self, bus):
        """发射 INFORMATION_TRANSFORMATION_FAILED 并验证。"""
        received_events = []
        bus.subscribe(EventType.INFORMATION_TRANSFORMATION_FAILED, lambda e: received_events.append(e))

        event = Event(
            event_type=EventType.INFORMATION_TRANSFORMATION_FAILED,
            source="test",
            payload={
                "process_id": "proc-001",
                "process_type": "reasoning",
                "error": "Insufficient evidence for conclusion",
            },
        )
        bus.publish(event, sync=True)

        assert len(received_events) == 1
        assert "Insufficient evidence" in received_events[0].payload["error"]

    def test_event_bus_isolation(self, bus):
        """每个事件类型应触发自己的回调，不相互干扰。"""
        started_events = []
        completed_events = []
        bus.subscribe(EventType.INFORMATION_TRANSFORMATION_STARTED, lambda e: started_events.append(e))
        bus.subscribe(EventType.INFORMATION_TRANSFORMATION_COMPLETED, lambda e: completed_events.append(e))

        bus.publish(
            Event(
                event_type=EventType.INFORMATION_TRANSFORMATION_STARTED,
                source="test",
                payload={"process_id": "p1", "process_type": "planning", "input_addresses": []},
            ),
            sync=True,
        )
        bus.publish(
            Event(
                event_type=EventType.INFORMATION_TRANSFORMATION_COMPLETED,
                source="test",
                payload={"process_id": "p2", "process_type": "planning", "output_addresses": []},
            ),
            sync=True,
        )

        assert len(started_events) == 1
        assert len(completed_events) == 1
        assert started_events[0].payload["process_id"] == "p1"
        assert completed_events[0].payload["process_id"] == "p2"

    def test_schema_payload_validation(self):
        """验证 3 个事件的 payload schema 校验。"""
        # started: 缺少 output_addresses 不应该导致校验失败（因为它不是 required）
        assert validate_event_payload(
            EventType.INFORMATION_TRANSFORMATION_STARTED,
            {"process_id": "p1", "process_type": "reasoning", "input_addresses": ["addr1"]},
        )
        # started: 缺少 input_addresses 应该失败
        assert not validate_event_payload(
            EventType.INFORMATION_TRANSFORMATION_STARTED,
            {"process_id": "p1", "process_type": "reasoning"},
        )
        # completed: 完整 payload 应该通过
        assert validate_event_payload(
            EventType.INFORMATION_TRANSFORMATION_COMPLETED,
            {"process_id": "p1", "process_type": "reasoning", "output_addresses": ["addr1"]},
        )
        # failed: 缺少 error 应该失败
        assert not validate_event_payload(
            EventType.INFORMATION_TRANSFORMATION_FAILED,
            {"process_id": "p1", "process_type": "reasoning"},
        )
