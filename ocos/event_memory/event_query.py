"""Phase 54: EventQuery — 事件查询引擎。

EM54-06: 按时间/类型/目标/实体/来源 多维查询。

组合 EventStore (存储) + EventIndex (索引) 实现高效查询。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ocos.event_memory.event_types import (
    CognitiveEvent, EventQuery as EventQueryParams,
)
from ocos.event_memory.event_store import EventStore
from ocos.event_memory.event_index import EventIndex


@dataclass
class QueryResult:
    """查询结果。"""
    events: list[CognitiveEvent] = field(default_factory=list)
    total_hits: int = 0
    query_time_ms: float = 0.0


@dataclass
class EventQueryEngine:
    """事件查询引擎 — 统一的查询入口。

    策略:
        1. 有索引 → 先用索引缩小范围，再从 store 查找
        2. 无索引 → 直接用 store.range 扫描
    """

    store: EventStore = field(default_factory=EventStore)
    index: EventIndex = field(default_factory=EventIndex)

    def query(self, params: EventQueryParams) -> QueryResult:
        """执行查询。"""
        import time as _time
        start = _time.time()

        # 先用索引缩小范围
        candidate_ids: set[str] | None = None

        if params.entity or params.goal_id or params.event_types:
            if params.event_types and len(params.event_types) == 1:
                ids = set(self.index.by_type.get(params.event_types[0], []))
                candidate_ids = ids if candidate_ids is None else candidate_ids & ids

            if params.entity:
                ids = set(self.index.by_entity.get(params.entity, []))
                candidate_ids = ids if candidate_ids is None else candidate_ids & ids

            if params.goal_id:
                ids = set(self.index.by_goal.get(params.goal_id, []))
                candidate_ids = ids if candidate_ids is None else candidate_ids & ids
        else:
            candidate_ids = None

        # 如果索引没命中，fallback 到时间范围扫描
        if candidate_ids is None:
            events = self.store.range(
                time_from=params.time_from,
                time_to=params.time_to,
                limit=params.limit + params.offset,
            )
            total = len(events)
            events = events[params.offset:params.offset + params.limit]

            # 后过滤
            if params.event_types and len(params.event_types) > 1:
                events = [e for e in events if e.event_type in params.event_types]
            if params.sources:
                events = [e for e in events if e.source in params.sources]

        else:
            # 从 store 按 ID 查找
            events = []
            for eid in candidate_ids:
                e = self.store.find(eid)
                if e is None:
                    continue
                # 时间过滤
                if params.time_from is not None and e.timestamp < params.time_from:
                    continue
                if params.time_to is not None and e.timestamp > params.time_to:
                    continue
                events.append(e)

            events.sort(key=lambda e: e.timestamp)
            total = len(events)
            events = events[params.offset:params.offset + params.limit]

        elapsed = (_time.time() - start) * 1000
        return QueryResult(events=events, total_hits=total, query_time_ms=elapsed)

    def index_event(self, event: CognitiveEvent) -> None:
        self.index.index(event)

    def index_batch(self, events: list[CognitiveEvent]) -> None:
        for e in events:
            self.index.index(e)

    def get_context(self, event_id: str, radius: int = 5) -> list[CognitiveEvent]:
        """获取事件的前后上下文 (前后 N 个事件)。"""
        event = self.store.find(event_id)
        if event is None:
            return []

        ts = event.timestamp
        all_timestamps = sorted(self.store._events.keys())
        idx = all_timestamps.index(ts)

        context_events: list[CognitiveEvent] = []

        # 前 radius 个
        for i in range(max(0, idx - radius), idx):
            context_events.extend(self.store._events[all_timestamps[i]])

        # 当前事件
        context_events.append(event)

        # 后 radius 个
        for i in range(idx + 1, min(len(all_timestamps), idx + radius + 1)):
            context_events.extend(self.store._events[all_timestamps[i]])

        return context_events


__all__ = ["EventQueryEngine", "QueryResult"]
