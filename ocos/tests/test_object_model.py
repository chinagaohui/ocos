"""
A1 Architecture Tests — 核心对象模型校验。

验证 ocos/kernel/abi.py 中的 6 个核心对象符合宪法定义：
1. 所有核心对象必须是 frozen dataclass
2. 必须包含 schema_version 字段
3. EventType 必须包含 12 个核心事件类型
4. Event 必须包含宪法要求的字段
"""

import dataclasses
from typing import Any

from ocos.kernel.abi import (
    SCHEMA_VERSION,
    Action,
    Decision,
    Event,
    EventType,
    Goal,
    Knowledge,
    Memory,
    Observation,
)

# 核心对象列表（宪法 Part 1）
CORE_OBJECTS = [Observation, Memory, Knowledge, Goal, Decision, Action]


def test_all_core_objects_are_frozen_dataclasses():
    """宪法 Part 1: 6 个核心对象必须是 frozen dataclass。"""
    for cls in CORE_OBJECTS:
        assert dataclasses.is_dataclass(cls), f"{cls.__name__} 不是 dataclass"
        assert cls.__dataclass_fields__ is not None  # type: ignore[arg-type]
        # frozen 属性在 dataclass 上的体现
        assert hasattr(cls, "__dataclass_params__")
        assert cls.__dataclass_params__.frozen, f"{cls.__name__} 不是 frozen"


def test_all_core_objects_have_schema_version():
    """宪法 Part 1: 所有核心对象必须包含 schema_version 字段。"""
    for cls in CORE_OBJECTS:
        fields = cls.__dataclass_fields__
        assert "schema_version" in fields, f"{cls.__name__} 缺少 schema_version"
        field_type = fields["schema_version"].type
        # 兼容 str 类和 'str' 字符串化类型
        assert field_type in (str, 'str'), (
            f"{cls.__name__}.schema_version 类型应为 str，当前: {field_type}"
        )


def test_schema_version_is_valid():
    """SCHEMA_VERSION 必须符合 MAJOR.MINOR.PATCH 格式。"""
    parts = SCHEMA_VERSION.split(".")
    assert len(parts) == 3, f"SCHEMA_VERSION 应为 MAJOR.MINOR.PATCH，当前: {SCHEMA_VERSION}"
    for part in parts:
        assert part.isdigit(), f"版本段应为数字: {part}"


def test_event_type_has_23_values():
    """EventType 必须有 23 个事件类型。"""
    assert len(EventType) >= 23, f"EventType 应有 >=23 个值，当前 {len(EventType)}"


def test_core_event_types_exist():
    """宪法 Part 2 定义的 12 个核心事件类型必须存在。"""
    required = [
        EventType.OBSERVATION_RECEIVED,
        EventType.OBSERVATION_VALIDATED,
        EventType.MEMORY_STORED,
        EventType.MEMORY_RETRIEVED,
        EventType.KNOWLEDGE_CANDIDATE_PROPOSED,
        EventType.KNOWLEDGE_PROMOTED,
        EventType.GOAL_SET,
        EventType.DECISION_FORMED,
        EventType.DECISION_VALIDATED,
        EventType.ACTION_PROPOSED,
        EventType.ACTION_EXECUTED,
        EventType.ACTION_FAILED,
    ]
    for et in required:
        assert et in EventType, f"缺少事件类型: {et.value}"


def test_event_has_all_required_fields():
    """Event 必须包含宪法 Part 2 要求的所有字段。"""
    fields = Event.__dataclass_fields__
    required = {"event_id", "event_type", "source", "timestamp", "payload", "schema_version"}
    missing = required - set(fields.keys())
    assert not missing, f"Event 缺少字段: {missing}"


def test_event_has_trace_id():
    """Event 必须包含 trace_id 字段（关联追踪链）。"""
    assert "trace_id" in Event.__dataclass_fields__


def test_knowledge_has_level_and_status():
    """Knowledge 必须包含 level 和 status 字段。"""
    fields = Knowledge.__dataclass_fields__
    assert "level" in fields
    assert "status" in fields


def test_decision_has_goal_id_and_confidence():
    """Decision 必须包含 goal_id 和 confidence 字段。"""
    fields = Decision.__dataclass_fields__
    assert "goal_id" in fields
    assert "confidence" in fields


def test_action_has_decision_id():
    """Action 必须包含 decision_id（宪法 Rule 6：每个 Action 必须有对应 Decision）。"""
    assert "decision_id" in Action.__dataclass_fields__


def test_core_objects_can_be_instantiated():
    """所有核心对象可以无参实例化（默认值必须存在）。"""
    for cls in CORE_OBJECTS:
        instance = cls()
        assert instance is not None
        assert instance.schema_version == SCHEMA_VERSION


def test_event_can_be_instantiated():
    """Event 可以无参实例化。"""
    event = Event()
    assert event.event_id != ""
    assert event.timestamp != ""


def test_observation_content_is_optional():
    """Observation.content 应为可选字段（默认为空 dict）。"""
    obs = Observation()
    assert obs.content == {}


def test_memory_type_deprecated_backward_compat():
    """Memory.memory_type 应保持 deprecated 向后兼容（v2.0 移除）。"""
    mem = Memory()
    assert mem.memory_type == "episodic"
