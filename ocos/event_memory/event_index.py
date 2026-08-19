"""Phase 54: EventIndex — 多维事件索引。

索引维度 (EM54-06):
    time_index:   float → [event_id]         (时间范围 O(log n))
    type_index:   CognitiveEventType → [id]   (类型过滤 O(1))
    entity_index: entity_name → [event_id]    (实体关联 O(1))
    goal_index:   goal_id → [event_id]        (目标关联 O(1))
    decision_index: decision_id → [event_id]  (决策关联 O(1))
"""

from __future__ import annotations

from dataclasses import dataclass, field
from collections import defaultdict
from typing import Any

from ocos.event_memory.event_types import (
    CognitiveEvent, CognitiveEventType,
)


@dataclass
class EventIndex:
    """事件索引 — 支持快速多维查询。

    每个索引是一个独立维度，不冗余存储事件本身。
    """

    # 按类型索引
    by_type: dict[CognitiveEventType, list[str]] = field(
        default_factory=lambda: defaultdict(list),
    )

    # 按实体索引 (上下文或载荷中的实体名)
    by_entity: dict[str, list[str]] = field(
        default_factory=lambda: defaultdict(list),
    )

    # 按目标索引
    by_goal: dict[str, list[str]] = field(
        default_factory=lambda: defaultdict(list),
    )

    # 按来源模块索引
    by_source: dict[str, list[str]] = field(
        default_factory=lambda: defaultdict(list),
    )

    # 按置信度索引
    by_confidence: dict[str, list[str]] = field(
        default_factory=lambda: defaultdict(list),
    )

    # 反向索引: event_id → {entities, goals}
    _reverse: dict[str, dict] = field(default_factory=dict)

    total_indexed: int = 0

    def index(self, event: CognitiveEvent) -> None:
        """为事件建立所有维度索引。"""
        eid = event.event_id

        # 类型
        self.by_type[event.event_type].append(eid)

        # 来源
        if event.source:
            self.by_source[event.source].append(eid)

        # 置信度
        self.by_confidence[event.confidence.value].append(eid)

        # 实体提取
        entities: list[str] = []
        entities.extend(event.context.get("entities", []))
        entities.extend(event.context.get("topics", []))
        if isinstance(event.payload, dict):
            entities.extend(event.payload.get("entities", []))
            entities.extend(event.payload.get("topics", []))

        for ent in set(entities):
            self.by_entity[ent].append(eid)

        # 目标
        goal_id = event.context.get("goal_id", "")
        if goal_id:
            self.by_goal[goal_id].append(eid)

        # 反向索引
        self._reverse[eid] = {
            "entities": list(set(entities)),
            "goal_id": goal_id,
            "event_type": event.event_type.value,
        }

        self.total_indexed += 1

    def query_by_type(self, event_type: CognitiveEventType) -> list[str]:
        return self.by_type.get(event_type, [])

    def query_by_entity(self, entity: str) -> list[str]:
        return self.by_entity.get(entity, [])

    def query_by_goal(self, goal_id: str) -> list[str]:
        return self.by_goal.get(goal_id, [])

    def query_by_source(self, source: str) -> list[str]:
        return self.by_source.get(source, [])

    def query(self,
              event_type: CognitiveEventType | None = None,
              entity: str | None = None,
              goal_id: str | None = None,
              source: str | None = None,
              limit: int = 100) -> list[str]:
        """综合查询 — 所有维度 AND 交集。"""
        candidates: set[str] | None = None

        if event_type is not None:
            ids = set(self.by_type.get(event_type, []))
            if not ids:
                return []
            candidates = ids if candidates is None else candidates & ids

        if entity is not None:
            ids = set(self.by_entity.get(entity, []))
            if not ids:
                return []
            candidates = ids if candidates is None else candidates & ids

        if goal_id is not None:
            ids = set(self.by_goal.get(goal_id, []))
            if not ids:
                return []
            candidates = ids if candidates is None else candidates & ids

        if source is not None:
            ids = set(self.by_source.get(source, []))
            if not ids:
                return []
            candidates = ids if candidates is None else candidates & ids

        if candidates is None:
            return []

        return list(candidates)[:limit]

    def get_reverse(self, event_id: str) -> dict:
        """获取事件的反向索引信息。"""
        return self._reverse.get(event_id, {})

    def clear(self) -> None:
        for k in list(self.by_type.keys()):
            del self.by_type[k]
        self.by_entity.clear()
        self.by_goal.clear()
        self.by_source.clear()
        self.by_confidence.clear()
        self._reverse.clear()
        self.total_indexed = 0

    def stats(self) -> dict:
        return {
            "total_indexed": self.total_indexed,
            "type_counts": {t.value: len(ids) for t, ids in self.by_type.items()},
            "entity_count": len(self.by_entity),
            "goal_count": len(self.by_goal),
            "source_count": len(self.by_source),
        }


__all__ = ["EventIndex"]
