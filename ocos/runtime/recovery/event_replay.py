"""Phase 39.4: EventReplay — 事件日志与状态重放。

OCOS 遵循 Event Sourcing: 状态由事件序列推导，不直接保存。
Event Log ← append-only → Replay → Rebuild State

39.4: 最小实现 — 事件追加 + 游标追踪。
Full Event Sourcing 留 Phase 41+ (CQRS/EventStore)。
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class EventType(Enum):
    """认知事件类型 — 39.4 最小集。"""

    GOAL_CREATED = "goal_created"
    GOAL_UPDATED = "goal_updated"
    GOAL_COMPLETED = "goal_completed"
    TASK_DECOMPOSED = "task_decomposed"
    AGENT_INVOKED = "agent_invoked"
    AGENT_COMPLETED = "agent_completed"
    MEMORY_CONSOLIDATED = "memory_consolidated"
    PERMISSION_REQUESTED = "permission_requested"
    PERMISSION_APPROVED = "permission_approved"
    PERMISSION_DENIED = "permission_denied"
    ATTENTION_SHIFTED = "attention_shifted"
    CHECKPOINT_CREATED = "checkpoint_created"
    RUNTIME_SNAPSHOT = "runtime_snapshot"


@dataclass(frozen=True)
class CognitiveEvent:
    """认知事件 — 不可变的日志条目。

    Fields:
        event_id:   事件唯一 ID
        event_type: 事件类型
        tick_id:    事件发生的 tick
        payload:    事件负载 (序列化为 JSON)
        timestamp:  事件时间戳
        seq:        全局序列号 (自增)
    """

    event_id: str
    event_type: str
    tick_id: int
    payload: dict[str, Any]
    timestamp: float = field(default_factory=time.time)
    seq: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "tick_id": self.tick_id,
            "payload": self.payload,
            "timestamp": self.timestamp,
            "seq": self.seq,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> CognitiveEvent:
        return cls(
            event_id=d["event_id"],
            event_type=d["event_type"],
            tick_id=d["tick_id"],
            payload=d.get("payload", {}),
            timestamp=d.get("timestamp", 0),
            seq=d.get("seq", 0),
        )


class EventLog:
    """Append-only event log。

    存储: ocos_data/events/event_log.jsonl
    每个事件一行 JSON。
    """

    def __init__(self, base_dir: Path | None = None):
        self._base = base_dir or Path("ocos_data/events")
        self._base.mkdir(parents=True, exist_ok=True)
        self._log_path = self._base / "event_log.jsonl"
        self._seq = self._count_existing()

    def append(self, event_type: EventType | str, tick_id: int, payload: dict[str, Any]) -> CognitiveEvent:
        event = CognitiveEvent(
            event_id=str(uuid.uuid4()),
            event_type=event_type.value if isinstance(event_type, Enum) else event_type,
            tick_id=tick_id,
            payload=payload,
            seq=self._seq + 1,
        )
        with open(self._log_path, "a") as f:
            f.write(json.dumps(event.to_dict()) + "\n")
        self._seq += 1
        return event

    def replay_from(self, from_seq: int = 0) -> list[CognitiveEvent]:
        """从指定序列号重放事件。"""
        events: list[CognitiveEvent] = []
        if not self._log_path.exists():
            return events
        for line in self._log_path.read_text().splitlines():
            if not line.strip():
                continue
            d = json.loads(line)
            ev = CognitiveEvent.from_dict(d)
            if ev.seq >= from_seq:
                events.append(ev)
        return events

    def replay_all(self) -> list[CognitiveEvent]:
        """重放全部事件。"""
        return self.replay_from(0)

    def cursor(self) -> int:
        """当前最大序列号。"""
        return self._seq

    def clear(self) -> None:
        """清空日志（测试用）。"""
        self._log_path.unlink(missing_ok=True)
        self._seq = 0

    def _count_existing(self) -> int:
        if not self._log_path.exists():
            return 0
        count = 0
        for line in self._log_path.read_text().splitlines():
            if line.strip():
                count += 1
        return count


class EventReplayEngine:
    """事件重放引擎。

    用法:
        engine = EventReplayEngine(event_log, handlers)
        state = engine.rebuild_state(from_cursor=100)
    """

    def __init__(self, event_log: EventLog):
        self._log = event_log
        self._handlers: dict[str, list] = {}  # event_type → [(handler, state_key)]

    def register_handler(self, event_type: EventType | str, handler, state_key: str = "default"):
        """注册事件处理器。

        handler(event: CognitiveEvent, current_state: dict) → dict
        """
        key = event_type.value if isinstance(event_type, Enum) else event_type
        if key not in self._handlers:
            self._handlers[key] = []
        self._handlers[key].append((handler, state_key))

    def rebuild_state(self, from_cursor: int = 0) -> dict[str, Any]:
        """从游标重放事件并重建状态。"""
        events = self._log.replay_from(from_cursor)
        state: dict[str, Any] = {"replay_cursor": from_cursor, "events_processed": 0}

        for event in events:
            handlers = self._handlers.get(event.event_type, [])
            for handler, state_key in handlers:
                result = handler(event, state.get(state_key, {}))
                if result is not None:
                    state[state_key] = result
            state["events_processed"] += 1
            state["replay_cursor"] = event.seq

        return state
