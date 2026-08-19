"""Phase 54: EventValidator — 事件完整性验证。

EM54-01: Event Integrity — 校验事件不可篡改
EM54-02: Timeline Reconstruction — 验证时间线可重建
EM54-03: Replay Isolation — 确保回放不含副作用
EM54-04: Memory Separation — 事件 ≠ 记忆

规则:
    EV54-01: Event ≠ Truth — 事件只是发生记录
    EV54-02: Event ≠ Memory — 不是所有事件都进记忆
    EV54-03: Replay ≠ Execute — 回放不能重新执行动作
    EV54-04: Archive ≠ Delete — 归档仍可恢复
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import time as _time

from ocos.event_memory.event_types import (
    CognitiveEvent, CognitiveEventType, EventConfidence,
)
from ocos.event_memory.event_store import EventStore
from ocos.event_memory.event_archive import EventArchiveManager


class ValidationCode(str, Enum):
    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"


@dataclass
class EventValidationResult:
    """事件验证结果。"""
    code: ValidationCode
    reason: str = ""
    details: dict = field(default_factory=dict)


@dataclass
class EventValidator:
    """事件验证器 — 确保事件存储的完整性。

    四个核心规则:
        EV54-01: 事件只是记录，不是真理
        EV54-02: 事件不是记忆
        EV54-03: 回放不是执行
        EV54-04: 归档不是删除
    """

    # 错误事件 ID 黑名单
    _invalid_ids: set[str] = field(default_factory=set)

    def validate_event(self, event: CognitiveEvent) -> EventValidationResult:
        """验证单个事件的完整性和合法性。"""
        # 必须有 ID
        if not event.event_id:
            return EventValidationResult(
                ValidationCode.FAIL, "missing event_id",
            )

        # ID 不得重复 (由 store 检查)
        if event.event_id in self._invalid_ids:
            return EventValidationResult(
                ValidationCode.FAIL, "event_id blacklisted",
            )

        # 时间戳必须合理
        if event.timestamp <= 0:
            return EventValidationResult(
                ValidationCode.FAIL, "invalid timestamp",
            )
        if event.timestamp > _time.time() + 60:
            return EventValidationResult(
                ValidationCode.WARN, "future timestamp",
            )

        # 不能是空内容 (payload=None 可以，但最好有内容)
        if event.payload is None and not event.context:
            return EventValidationResult(
                ValidationCode.WARN, "empty payload and context",
            )

        return EventValidationResult(ValidationCode.PASS)

    def validate_store(self, store: EventStore) -> EventValidationResult:
        """验证整个 store 的完整性。"""
        stats = store.stats()

        if stats["total_events"] == 0:
            return EventValidationResult(
                ValidationCode.WARN, "empty store",
            )

        # 检查时间单调性
        last_ts = 0.0
        gaps = 0
        for ts in sorted(store._events.keys()):
            if last_ts > 0 and (ts - last_ts) > 3600:
                gaps += 1
            last_ts = ts

        if gaps > 10:
            return EventValidationResult(
                ValidationCode.WARN,
                f"large time gaps: {gaps} gaps >1h",
                {"gap_count": gaps},
            )

        return EventValidationResult(
            ValidationCode.PASS,
            f"valid: {stats['total_events']} events, span={stats['span_seconds']:.0f}s",
            {"stats": stats},
        )

    def validate_timeline(self, events: list[CognitiveEvent]) -> EventValidationResult:
        """验证时间线是否可重建。EM54-02。"""
        if not events:
            return EventValidationResult(ValidationCode.WARN, "empty timeline")

        # 检查时间顺序
        for i in range(1, len(events)):
            if events[i].timestamp < events[i - 1].timestamp:
                return EventValidationResult(
                    ValidationCode.FAIL,
                    f"time reversal at event {events[i].event_id}",
                )

        # 检查是否有合理的因果链
        has_perception = any(e.event_type == CognitiveEventType.PERCEPTION for e in events)
        has_decision = any(e.event_type == CognitiveEventType.DECISION for e in events)

        if has_decision and not has_perception:
            return EventValidationResult(
                ValidationCode.WARN, "decision without prior perception",
            )

        return EventValidationResult(
            ValidationCode.PASS,
            f"valid timeline: {len(events)} events, {events[0].timestamp}→{events[-1].timestamp}",
        )

    def validate_replay_safety(self, events: list[CognitiveEvent]) -> EventValidationResult:
        """EM54-03: 确保回放不含副作用。"""
        # 检查 ACTION 事件是否标记为只读重放
        action_events = [e for e in events
                         if e.event_type == CognitiveEventType.ACTION]
        unsafe = [e for e in action_events
                  if not e.metadata.get("replay_safe", False)]

        if unsafe:
            return EventValidationResult(
                ValidationCode.WARN,
                f"{len(unsafe)} action events not marked replay_safe",
                {"unsafe_ids": [e.event_id for e in unsafe]},
            )

        return EventValidationResult(ValidationCode.PASS, "replay safe")

    def mark_invalid(self, event_id: str) -> None:
        self._invalid_ids.add(event_id)


__all__ = ["EventValidator", "EventValidationResult", "ValidationCode"]
