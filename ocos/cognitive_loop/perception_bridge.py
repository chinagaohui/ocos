"""Phase 46: PerceptionBridge — 感知桥。

将外部感知信号接入认知循环的 EventBus。

负责:
    - 接收多模态输入 (text/audio/event)
    - 标准化为 PerceptionEvent
    - 推送到事件总线

边界 CL46-03: Perception ≠ Truth — 感知是输入信号，不是客观事实。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class PerceptionMode(Enum):
    """感知模式。"""
    TEXT = "text"
    EVENT = "event"
    SYSTEM = "system"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class PerceptionEvent:
    """标准化感知事件。"""
    event_id: str
    mode: PerceptionMode = PerceptionMode.TEXT
    raw_content: str = ""
    source: str = ""           # 来源标识
    tick_id: int = 0
    confidence: float = 1.0    # 信号置信度 (CL46-03: 不是 truth)
    processed: bool = False    # 是否已被 Attention 处理

    @property
    def is_trusted_source(self) -> bool:
        """来源是否可信？注意: trusted ≠ true。"""
        return self.confidence > 0.7


@dataclass
class PerceptionBridge:
    """感知桥——外部信号 → EventBus。

    不判定真假 (CL46-03)，只做标准化路由。
    """

    _events: list[PerceptionEvent] = field(default_factory=list)

    def receive(
        self, content: str, source: str = "user",
        mode: PerceptionMode = PerceptionMode.TEXT,
        tick_id: int = 0,
    ) -> PerceptionEvent:
        """接收一条感知输入。"""
        event = PerceptionEvent(
            event_id=f"perc:{tick_id}:{len(self._events)}",
            mode=mode,
            raw_content=content,
            source=source,
            tick_id=tick_id,
        )
        self._events.append(event)
        return event

    def pending_events(self) -> list[PerceptionEvent]:
        """获取未处理的感知事件。"""
        return [e for e in self._events if not e.processed]

    def mark_processed(self, event_id: str) -> None:
        """标记事件已被 Attention 处理。"""
        for i, e in enumerate(self._events):
            if e.event_id == event_id:
                self._events[i] = PerceptionEvent(
                    event_id=e.event_id, mode=e.mode,
                    raw_content=e.raw_content, source=e.source,
                    tick_id=e.tick_id, confidence=e.confidence,
                    processed=True,
                )
                return

    def flush_processed(self, max_age_ticks: int = 100) -> int:
        """清理已处理的旧事件。"""
        before = len(self._events)
        self._events = [
            e for e in self._events
            if not e.processed or e.tick_id > max_age_ticks
        ]
        return before - len(self._events)

    @property
    def event_count(self) -> int:
        return len(self._events)


__all__ = ["PerceptionMode", "PerceptionEvent", "PerceptionBridge"]
