"""Phase 54: EventReplay — 事件回放引擎。

EM54-03: Replay Isolation — 回放不能重新执行动作。

核心能力:
    1. 时间线重建: 从事件存储重建完整认知过程
    2. 上下文重建: 恢复当时的状态快照
    3. Reflection 生成: 从过去经历提炼新的理解
    4. Evolution Narrative: 从事件序列提取演化故事

类似人脑的"回忆":
    过去事件 → 重建上下文 → 重新理解 → 生成反思
"""

from __future__ import annotations

from dataclasses import dataclass, field
from collections import defaultdict
from typing import Any

from ocos.event_memory.event_types import (
    CognitiveEvent, CognitiveEventType, EventConfidence, EventReference,
)
from ocos.event_memory.event_store import EventStore


@dataclass
class ReplaySession:
    """单次回放会话的状态。"""
    events: list[CognitiveEvent] = field(default_factory=list)
    position: int = 0
    paused: bool = False
    started_at: float = 0.0

    def current(self) -> CognitiveEvent | None:
        if 0 <= self.position < len(self.events):
            return self.events[self.position]
        return None

    def next(self) -> CognitiveEvent | None:
        if self.position + 1 < len(self.events):
            self.position += 1
            return self.current()
        return None

    def reset(self) -> None:
        self.position = 0


@dataclass
class EventReplay:
    """事件回放引擎 — OCOS 的"记忆回放"。

    不执行: EM54-03 — 回放只读，不会触发实际动作。
    """

    def replay_range(self, store: EventStore,
                     time_from: float, time_to: float) -> ReplaySession:
        """按时间范围创建回放会话。"""
        events = store.range(time_from=time_from, time_to=time_to, limit=10000)
        import time as _time
        return ReplaySession(
            events=events,
            started_at=_time.time(),
        )

    def replay_session(self, events: list[CognitiveEvent]) -> ReplaySession:
        """从已有事件列表创建回放会话。"""
        import time as _time
        return ReplaySession(
            events=events,
            started_at=_time.time(),
        )

    def trace_causal_chain(self, event: CognitiveEvent,
                            store: EventStore) -> list[CognitiveEvent]:
        """追溯因果链 — 从当前事件回溯到源头。"""
        seen: set[str] = {event.event_id}
        chain: list[CognitiveEvent] = [event]
        current = event

        while current.caused_by and current.caused_by.event_id not in seen:
            prev = store.find(current.caused_by.event_id)
            if prev is None:
                break
            seen.add(prev.event_id)
            chain.append(prev)
            current = prev

        chain.reverse()  # 从最早到最新
        return chain

    def reconstruct_timeline(self, store: EventStore,
                              goal_id: str) -> list[CognitiveEvent]:
        """重建与某个目标相关的完整时间线。"""
        results: list[CognitiveEvent] = []
        for batch in store.iterate():
            for event in batch:
                gid = event.context.get("goal_id", "")
                if gid == goal_id or goal_id in str(event.payload):
                    results.append(event)
        return results

    def generate_reflection(self, events: list[CognitiveEvent]) -> dict:
        """从事件序列生成反思摘要。

        EM54-03: 这只生成摘要，不执行任何动作。
        """
        if not events:
            return {"summary": "no events", "patterns": []}

        # 事件类型统计
        type_counts: dict[str, int] = defaultdict(int)
        for e in events:
            type_counts[e.event_type.value] += 1

        # 时间跨度
        times = [e.timestamp for e in events]
        time_span = max(times) - min(times) if times else 0

        # 置信度分布
        conf_counts: dict[str, int] = defaultdict(int)
        for e in events:
            conf_counts[e.confidence.value] += 1

        # 提取决策事件作为模式
        decisions = [
            {"id": e.event_id, "context": e.context, "time": e.timestamp}
            for e in events
            if e.event_type == CognitiveEventType.DECISION
        ]

        # 提取学习事件
        learnings = [
            str(e.payload) for e in events
            if e.event_type == CognitiveEventType.LEARNING and e.payload
        ]

        return {
            "summary": f"{len(events)} events over {time_span:.0f}s",
            "event_count": len(events),
            "time_span_seconds": time_span,
            "type_distribution": dict(type_counts),
            "confidence_distribution": dict(conf_counts),
            "decisions": decisions,
            "learnings": learnings,
            "key_topics": list(set(
                t for e in events
                for t in (e.context.get("topics", []) + e.context.get("entities", []))
            )),
        }

    def generate_evolution_narrative(self, events: list[CognitiveEvent]) -> list[str]:
        """从事件序列生成演化叙事 — 像讲故事一样总结变化过程。"""
        if len(events) < 2:
            return []

        narrative: list[str] = []
        prev_type: str = ""

        for e in events:
            if e.event_type.value != prev_type:
                ts = f"T+{e.timestamp - events[0].timestamp:.0f}s" if events else ""
                source = e.source or "unknown"

                if e.event_type == CognitiveEventType.PERCEPTION:
                    narrative.append(f"[{ts}] 感知到来自 {source} 的输入")
                elif e.event_type == CognitiveEventType.DECISION:
                    narrative.append(f"[{ts}] 做出决策: {e.context.get('decision', 'unspecified')}")
                elif e.event_type == CognitiveEventType.ACTION:
                    narrative.append(f"[{ts}] 执行行动")
                elif e.event_type == CognitiveEventType.LEARNING:
                    narrative.append(f"[{ts}] 提炼经验: {e.payload}")
                elif e.event_type == CognitiveEventType.INTERACTION:
                    narrative.append(f"[{ts}] 与用户交互")
                elif e.event_type == CognitiveEventType.HEALTH:
                    narrative.append(f"[{ts}] 健康检查")
                else:
                    narrative.append(f"[{ts}] {e.event_type.value}")

            prev_type = e.event_type.value

        return narrative


__all__ = ["ReplaySession", "EventReplay"]
