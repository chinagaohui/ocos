"""Phase 54: EventStore — 事件持久化存储。

核心操作:
    append: 追加事件 (不可变!)
    find: 按 ID 查找
    range: 时间范围扫描
    snapshot: 导出完整状态 (用于 Checkpoint)
    restore: 从 snapshot 恢复

EM54-01: 事件追加后不可修改 (append-only)。
EM54-05: 跨 session 持久化 (export → import)。

边界:
    EventStore ≠ Memory — 不自动提炼知识。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from collections import OrderedDict
from typing import Any, Iterator
import time as _time

from ocos.event_memory.event_types import (
    CognitiveEvent, EventHeader, EventLifecyclePhase,
)


@dataclass
class EventStore:
    """事件存储 — OCOS 的"经历记录仪"。

    内部按时间顺序组织，支持:
        - 追加 (append)
        - 按 ID 查找 (find)
        - 时间范围扫描 (range)
        - 分页遍历 (iterate)
        - 统计 (stats)

    GAP-P2-3: 可选 SQLite 持久化后端。注入 connection（storage/connection
    get_connection + schema CREATE_EVENT_STORE）后，append/append_batch
    同步写入 event_store 表（INSERT OR IGNORE，保持 append-only 语义）；
    load_from_db() 从库重建。不注入 → 纯内存（旧行为）。
    """

    # 主存储: timestamp → list of events (同一时间戳可有多个事件)
    _events: dict[float, list[CognitiveEvent]] = field(default_factory=dict)
    _by_id: dict[str, CognitiveEvent] = field(default_factory=dict)
    _headers: dict[str, EventHeader] = field(default_factory=dict)

    # GAP-P2-3: 可选 SQLite 持久化后端
    connection: Any = None

    # 时间范围
    _earliest: float = 0.0
    _latest: float = 0.0

    # 统计
    total_appended: int = 0
    total_bytes_approx: int = 0

    def append(self, event: CognitiveEvent) -> bool:
        """追加一个事件。重复 ID 静默忽略。"""
        if event.event_id in self._by_id:
            return False

        ts = event.timestamp
        if ts not in self._events:
            self._events[ts] = []
        self._events[ts].append(event)
        self._by_id[event.event_id] = event
        self._headers[event.event_id] = EventHeader.from_event(event)

        if self._earliest == 0 or ts < self._earliest:
            self._earliest = ts
        if ts > self._latest:
            self._latest = ts

        self.total_appended += 1
        self.total_bytes_approx += len(str(event.payload)) if event.payload else 0
        self._persist(event)
        return True

    def _persist(self, event: CognitiveEvent) -> None:
        """GAP-P2-3: 可选 SQLite 持久化（INSERT OR IGNORE，append-only）。"""
        if self.connection is None:
            return
        import json as _json
        payload = _json.dumps(event.payload, ensure_ascii=False) if event.payload else "{}"
        self.connection.execute(
            "INSERT OR IGNORE INTO event_store "
            "(event_id, event_type, payload, source, created_at, sequence) "
            "VALUES (?, ?, ?, ?, ?, "
            "(SELECT COALESCE(MAX(sequence), 0) + 1 FROM event_store))",
            (
                event.event_id,
                event.event_type.value,
                payload,
                event.source,
                _time.strftime("%Y-%m-%dT%H:%M:%S", _time.localtime(event.timestamp)),
            ),
        )
        self.connection.commit()

    @classmethod
    def load_from_db(cls, connection: Any) -> "EventStore":
        """GAP-P2-3: 从 SQLite event_store 表重建内存存储。

        跨 session 持久化（EM54-05）：新进程从库恢复事件流。
        """
        import json as _json
        from ocos.event_memory.event_types import CognitiveEventType

        store = cls(connection=connection)
        rows = connection.execute(
            "SELECT event_id, event_type, payload, source, created_at FROM event_store "
            "ORDER BY sequence"
        ).fetchall()
        for event_id, event_type, payload, source, created_at in rows:
            ts = 0.0
            if created_at:
                try:
                    ts = _time.mktime(_time.strptime(created_at, "%Y-%m-%dT%H:%M:%S"))
                except ValueError:
                    ts = 0.0
            ev = CognitiveEvent(
                event_id=event_id,
                event_type=CognitiveEventType(event_type),
                timestamp=ts,
                source=source or "",
                payload=_json.loads(payload),
            )
            store.append(ev)
        return store

    def mark_archived(self, event_id: str) -> bool:
        """GAP-P2-3: 标记事件已归档（header.lifecycle=ARCHIVED）。

        不改事件本体（EM54-01 append-only），仅更新头摘要。
        """
        header = self._headers.get(event_id)
        if header is None:
            return False
        header.lifecycle = EventLifecyclePhase.ARCHIVED
        return True

    def append_batch(self, events: list[CognitiveEvent]) -> int:
        """批量追加。返回成功追加的数量。"""
        count = 0
        for e in events:
            if self.append(e):
                count += 1
        return count

    def find(self, event_id: str) -> CognitiveEvent | None:
        """按 ID 查找。"""
        return self._by_id.get(event_id)

    def range(self, time_from: float | None = None,
              time_to: float | None = None,
              limit: int = 100) -> list[CognitiveEvent]:
        """时间范围查询。"""
        results: list[CognitiveEvent] = []
        for ts in sorted(self._events.keys()):
            if time_from is not None and ts < time_from:
                continue
            if time_to is not None and ts > time_to:
                break
            results.extend(self._events[ts])
            if len(results) >= limit:
                break
        return results[:limit]

    def iterate(self, from_time: float = 0.0,
                batch_size: int = 100) -> Iterator[list[CognitiveEvent]]:
        """分页迭代器。"""
        current = from_time
        while True:
            batch = self.range(time_from=current, limit=batch_size)
            if not batch:
                break
            yield batch
            current = batch[-1].timestamp + 0.001  # 微增，避免重复
            if len(batch) < batch_size:
                break

    def headers(self, limit: int = 100, offset: int = 0) -> list[EventHeader]:
        """获取事件头列表 (用于浏览)。"""
        sorted_headers = sorted(
            self._headers.values(),
            key=lambda h: h.timestamp,
        )
        return sorted_headers[offset:offset + limit]

    def stats(self) -> dict:
        """统计信息。"""
        return {
            "total_events": len(self._by_id),
            "earliest": self._earliest,
            "latest": self._latest,
            "span_seconds": self._latest - self._earliest if self._earliest > 0 else 0,
            "total_appended": self.total_appended,
            "approx_bytes": self.total_bytes_approx,
        }

    def clear(self) -> None:
        self._events.clear()
        self._by_id.clear()
        self._headers.clear()
        self._earliest = 0.0
        self._latest = 0.0
        self.total_appended = 0
        self.total_bytes_approx = 0

    # ——— 持久化接口 ———

    def snapshot(self) -> dict:
        """导出完整存储状态 (用于 Checkpoint)。"""
        return {
            "events": [
                {
                    "event_id": e.event_id,
                    "event_type": e.event_type.value,
                    "timestamp": e.timestamp,
                    "source": e.source,
                    "context": e.context,
                    "payload": str(e.payload) if e.payload else None,
                    "confidence": e.confidence.value,
                    "lifecycle": e.lifecycle.value,
                }
                for events_list in self._events.values()
                for e in events_list
            ],
            "stats": self.stats(),
        }

    def restore(self, data: dict) -> int:
        """从 snapshot 恢复。返回恢复的事件数。"""
        self.clear()
        count = 0
        for e_data in data.get("events", []):
            event = CognitiveEvent(
                event_id=e_data["event_id"],
                event_type=CognitiveEventType(e_data["event_type"]),
                timestamp=e_data["timestamp"],
                source=e_data.get("source", ""),
                context=e_data.get("context", {}),
                payload=e_data.get("payload"),
                confidence=EventConfidence(e_data.get("confidence", "high")),
                lifecycle=EventLifecyclePhase(e_data.get("lifecycle", "warm")),
            )
            if self.append(event):
                count += 1
        return count


# Import at bottom to resolve circular refs in restore
from ocos.event_memory.event_types import CognitiveEventType, EventConfidence  # noqa: E402


__all__ = ["EventStore"]
