"""Phase 54: EventLifecycle — 事件全生命周期管理。

组合 EventStore + EventIndex + EventArchiveManager 为一个协调器。

完整流程:
    Cognitive Loop → EventBus → EventLifecycle.record()
        ↓
    EventStore.append (HOT)
        ↓
    EventIndex.index
        ↓
    ... 时间流逝 ...
        ↓
    EventLifecycle.maintain()
        ↓
    HOT → WARM → COLD → ARCHIVED
"""

from __future__ import annotations

from dataclasses import dataclass, field
import time as _time
import uuid

from ocos.event_memory.event_types import (
    CognitiveEvent, CognitiveEventType, EventConfidence,
    EventLifecyclePhase,
)
from ocos.event_memory.event_store import EventStore
from ocos.event_memory.event_index import EventIndex
from ocos.event_memory.event_archive import (
    EventArchiveManager, LifecycleConfig,
)
from ocos.event_memory.event_validator import EventValidator
from ocos.event_memory.event_query import EventQueryEngine, EventQueryParams


@dataclass
class EventLifecycle:
    """事件生命周期管理器 — 协调存储、索引、归档的统一入口。

    用法:
        el = EventLifecycle()
        el.record(event_type, source="perception", payload={"text": "hello"}, ...)
        el.maintain()  # 周期性维护 (HOT→WARM→COLD)
        results = el.query(EventQueryParams(...))
    """

    store: EventStore = field(default_factory=EventStore)
    index: EventIndex = field(default_factory=EventIndex)
    archiver: EventArchiveManager = field(default_factory=EventArchiveManager)
    validator: EventValidator = field(default_factory=EventValidator)
    query_engine: EventQueryEngine | None = None

    # 统计
    total_recorded: int = 0
    total_validated: int = 0
    bootstrap_timestamp: float = field(default_factory=_time.time)

    def __post_init__(self):
        if self.query_engine is None:
            self.query_engine = EventQueryEngine(store=self.store, index=self.index)

    def record(self,
               event_type: CognitiveEventType,
               source: str = "",
               payload: object = None,
               context: dict | None = None,
               confidence: EventConfidence = EventConfidence.HIGH,
               caused_by_id: str | None = None,
               ) -> CognitiveEvent:
        """记录一个认知事件。

        完整链路:
            1. 创建事件
            2. 验证
            3. 存储 (append)
            4. 索引
            5. 返回事件 (供调用方使用)
        """
        event_id = f"ev-{event_type.value}-{uuid.uuid4().hex[:8]}"

        caused_by = None
        if caused_by_id:
            caused_event = self.store.find(caused_by_id)
            if caused_event:
                caused_by = caused_event.to_reference()

        event = CognitiveEvent(
            event_id=event_id,
            event_type=event_type,
            source=source,
            context=context or {},
            payload=payload,
            confidence=confidence,
            caused_by=caused_by,
        )

        # 验证
        result = self.validator.validate_event(event)
        self.total_validated += 1
        if result.code == "fail":
            self.validator.mark_invalid(event_id)
            # 仍存储但标记 (EM54-01: 不可篡改)
            event = event.with_lifecycle(EventLifecyclePhase.ARCHIVED)

        # 存储
        self.store.append(event)

        # 索引
        self.index.index(event)

        self.total_recorded += 1
        return event

    def record_batch(self, events: list[dict]) -> list[CognitiveEvent]:
        """批量记录事件。events 是 dict 列表，每个 dict 是 record() 的参数。"""
        results = []
        for params in events:
            e = self.record(**params)
            results.append(e)
        return results

    def maintain(self) -> dict:
        """维护生命周期 — 将旧事件降级。"""
        return self.archiver.apply_lifecycle(self.store)

    def query(self, params: EventQueryParams):
        """查询事件。"""
        if self.query_engine is None:
            self.query_engine = EventQueryEngine(store=self.store, index=self.index)
        return self.query_engine.query(params)

    def snapshot(self) -> dict:
        """导出完整状态用于持久化。"""
        return {
            "store": self.store.snapshot(),
            "stats": self.store.stats(),
            "index_stats": self.index.stats(),
            "total_recorded": self.total_recorded,
            "total_validated": self.total_validated,
            "bootstrap_timestamp": self.bootstrap_timestamp,
        }

    def restore(self, data: dict) -> int:
        """从持久化状态恢复。"""
        self.bootstrap_timestamp = data.get("bootstrap_timestamp", _time.time())
        self.total_recorded = data.get("total_recorded", 0)
        self.total_validated = data.get("total_validated", 0)

        count = self.store.restore(data.get("store", {}))

        # 重建索引
        self.index.clear()
        for batch in self.store.iterate():
            for e in batch:
                self.index.index(e)

        # 重建 query_engine
        self.query_engine = EventQueryEngine(store=self.store, index=self.index)

        return count

    def clear(self) -> None:
        self.store.clear()
        self.index.clear()
        self.archiver.clear()
        self.total_recorded = 0
        self.total_validated = 0
        self.query_engine = None


__all__ = ["EventLifecycle"]
