"""Phase 22-C — Event Ingestion 层 (Tick Step 1)。

职责:
  - 从 EventBus 拉取未处理事件
  - 事件过滤（系统事件 vs 用户事件）
  - 事件排队到 Agent 的感知管道
  - 与 Observation 层解耦

设计:
  - EventIngestion 是 AgentRuntime 的私有组件
  - 每次 tick() 拉取最多 batch_size 个事件
  - 系统事件（heartbeat 等）优先级低于用户事件
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from ocos.logging import get_logger

logger = get_logger(__name__)


# ── 事件过滤器类型 ──────────────────────────────────────────────────────────

# 系统事件类型：低优先级、周期性
SYSTEM_EVENT_TYPES: frozenset[str] = frozenset({
    "heartbeat",
    "health_check",
    "maintenance_tick",
    "memory_consolidation",
})

# 用户/外部事件优先级高于系统事件
_PRIORITY_MAP: dict[str, int] = {
    "user_input": 100,
    "goal_request": 90,
    "external_stimulus": 80,
    "observation": 50,
    "engine_result": 40,
    "heartbeat": 10,
    "health_check": 10,
    "maintenance_tick": 5,
}


@dataclass
class IngestedEvent:
    """从 EventBus 拉取后的事件包装。"""
    event_id: str
    event_type: str
    payload: dict[str, Any] = field(default_factory=dict)
    priority: int = 0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    source: str = ""


@dataclass
class EventIngestion:
    """事件摄取层 — 将 EventBus 事件注入 Agent 感知管道。

    用法:
        ingestion = EventIngestion(event_bus, batch_size=10)
        events = ingestion.ingest()  # 每次 tick() 调用一次
    """

    event_bus: Any  # EventBus instance
    batch_size: int = 10
    ingestion_history: list[IngestedEvent] = field(default_factory=list)

    def ingest(self) -> list[IngestedEvent]:
        """拉取并过滤待处理事件。

        Returns:
            按优先级排序的事件列表
        """
        raw_events = self._pull_events()
        if not raw_events:
            return []

        ingested: list[IngestedEvent] = []
        for evt in raw_events:
            ie = self._wrap_event(evt)
            if ie is not None:
                ingested.append(ie)

        # 按优先级排序（高优先级在前）
        ingested.sort(key=lambda e: -e.priority)

        # 记录历史
        self.ingestion_history.extend(ingested)
        if len(self.ingestion_history) > 1000:
            self.ingestion_history = self.ingestion_history[-1000:]

        return ingested

    def _pull_events(self) -> list[dict[str, Any]]:
        """从 EventBus 拉取事件。"""
        try:
            if hasattr(self.event_bus, "pending_events"):
                events = self.event_bus.pending_events[:self.batch_size]
                self.event_bus.pending_events.clear()
                return events
            elif hasattr(self.event_bus, "get_pending"):
                return self.event_bus.get_pending(self.batch_size)
            elif hasattr(self.event_bus, "poll"):
                result = self.event_bus.poll(self.batch_size)
                return result if isinstance(result, list) else []
        except Exception as e:
            logger.debug(f"EventIngestion: pull failed: {e}")
        return []

    def _wrap_event(self, raw: Any) -> IngestedEvent | None:
        """将原始事件包装为 IngestedEvent。"""
        if isinstance(raw, dict):
            etype = raw.get("type", raw.get("event_type", "unknown"))
            return IngestedEvent(
                event_id=raw.get("id", raw.get("event_id", "")),
                event_type=etype,
                payload=raw.get("payload", raw.get("data", raw)),
                priority=self._priority_for(etype),
                source=raw.get("source", ""),
                timestamp=raw.get(
                    "timestamp",
                    datetime.now(timezone.utc),
                ),
            )
        # 未知格式
        try:
            return IngestedEvent(
                event_id=str(id(raw)),
                event_type="unknown",
                payload={"raw": str(raw)},
            )
        except Exception:
            return None

    @staticmethod
    def _priority_for(event_type: str) -> int:
        return _PRIORITY_MAP.get(event_type, 30)  # 默认中等优先级

    @property
    def has_pending_input(self) -> bool:
        """是否有用户输入待处理（用于激活 Agent）。"""
        return any(
            e.event_type in ("user_input", "goal_request")
            for e in self.ingestion_history[-10:]
        )
