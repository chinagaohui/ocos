"""Phase 42: EventModel — 世界事件溯源。

记录世界中发生的变化事件。
与 WorldEvent (数据结构) 解耦，EventModel 是事件的存储/查询层。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from collections import defaultdict

from ocos.world_model.world_types import WorldEvent, WorldEventType


@dataclass
class EventModel:
    """世界事件存储 — 不可变事件日志。

    每个 WorldEvent 是一个不可变记录。
    """

    _events: list[WorldEvent] = field(default_factory=list)
    _by_entity: dict[str, list[int]] = field(default_factory=lambda: defaultdict(list))

    # ── 写入 ──

    def record(self, event: WorldEvent) -> None:
        idx = len(self._events)
        self._events.append(event)
        if event.entity_id:
            self._by_entity[event.entity_id].append(idx)

    # ── 查询 ──

    def all(self) -> list[WorldEvent]:
        return list(self._events)

    def by_entity(self, entity_id: str) -> list[WorldEvent]:
        return [self._events[i] for i in self._by_entity.get(entity_id, [])]

    def by_type(self, event_type: WorldEventType) -> list[WorldEvent]:
        return [e for e in self._events if e.event_type == event_type]

    def since(self, tick_id: int) -> list[WorldEvent]:
        return [e for e in self._events if e.tick_id >= tick_id]

    def count_by_type(self) -> dict[WorldEventType, int]:
        c: dict[WorldEventType, int] = {}
        for e in self._events:
            c[e.event_type] = c.get(e.event_type, 0) + 1
        return c

    @property
    def count(self) -> int:
        return len(self._events)


__all__ = ["EventModel"]
