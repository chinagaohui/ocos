"""Stage ①: Event Ingestion — 外部/内部/定时器事件读取。

39.2: EventBus 接入（GAP-P2-2 接线）：从注入的 EventBus drain 积压事件。
不解析事件，不创建 Goal。事件 → 候选刺激，不能直接触发决策。

无 EventBus 注入 → 空事件（降级，兼容既有装配）。
"""

from __future__ import annotations

from typing import Any, Optional

from ..pipeline_protocol import TickStage
from ..tick_context import TickContext


class EventIngestionStage:
    """事件摄取阶段。

    39.2 接口: 从 EventBus 读取积压事件，注入 TickContext。
    不执行事件解析、不触发 Goal 创建。
    """

    name = "EVENT_INGESTION"

    def __init__(self, event_bus: Any = None, max_events: int = 10) -> None:
        """注入 EventBus（ocos/perception_bus.EventBus，原 ocos/event）。

        GAP-P2-2: 生产装配时传入 EventBus；缺省 None 保持旧行为（空事件）。
        """
        self._event_bus = event_bus
        self._max_events = max_events

    def execute(self, context: TickContext) -> TickContext:
        """从 EventBus drain 积压事件（GAP-P2-2 接线）。"""
        if self._event_bus is not None:
            events = tuple(self._event_bus.ingest(max_events=self._max_events))
        else:
            events = ()
        return context.with_updates(events=events).with_stage_trace(self.name)
