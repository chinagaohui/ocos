"""Phase 49: CognitiveTimeline — 认知时间线引擎。

记录 OCOS 从过去到现在的认知演变。

三部分:
    - Past: 经验/决策/成长的完整历史
    - Present: 当前状态快照
    - Future Intents: 用户明确规划的意图 (CC49-04: 不是预测)

CC49-04: 只记录用户意图，不生成预测。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ocos.cognitive_continuity.continuity_types import (
    TimelineEntry,
    TimeAnchor,
    CognitiveTimeline,
)


@dataclass
class TimelineEngine:
    """认知时间线引擎。

    管理 OCOS 的时间维度的自我认知。
    """

    timeline: CognitiveTimeline = field(default_factory=CognitiveTimeline)

    def record_decision(
        self, tick_id: int, label: str, summary: str,
        significance: float = 0.5,
    ) -> TimelineEntry:
        """记录一次决策到过去时间线。"""
        entry = TimelineEntry(
            entry_id=f"tl:decision:{tick_id}:{self.timeline.past_count}",
            anchor=TimeAnchor.PAST,
            tick_id=tick_id,
            label=label,
            summary=summary[:200],
            significance=significance,
        )
        self.timeline.add_past(entry)
        return entry

    def record_milestone(
        self, tick_id: int, label: str, summary: str,
        significance: float = 0.8,
    ) -> TimelineEntry:
        """记录重要里程碑。"""
        return self.record_decision(tick_id, label, summary, significance)

    def record_evolution(
        self, tick_id: int, label: str, summary: str,
        significance: float = 0.9,
    ) -> TimelineEntry:
        """记录 Phase 47 演化事件。"""
        return self.record_decision(tick_id, label, summary, significance)

    def snapshot_present(
        self, tick_id: int, labels: list[str],
    ) -> list[TimelineEntry]:
        """创建当前状态快照——替换 present 部分。"""
        self.timeline.present = []
        entries = []
        for label in labels:
            entry = TimelineEntry(
                entry_id=f"tl:present:{tick_id}:{label}",
                anchor=TimeAnchor.PRESENT,
                tick_id=tick_id,
                label=label,
                summary=label,
                significance=1.0,
            )
            self.timeline.add_present(entry)
            entries.append(entry)
        return entries

    def record_intent(
        self, tick_id: int, label: str, summary: str,
        significance: float = 0.5,
    ) -> TimelineEntry:
        """CC49-04: 记录用户意图。严格拒绝非用户来源。"""
        entry = TimelineEntry(
            entry_id=f"tl:intent:{tick_id}:{self.timeline.intent_count}",
            anchor=TimeAnchor.FUTURE_INTENT,
            tick_id=tick_id,
            label=label,
            summary=summary[:200],
            significance=significance,
        )
        self.timeline.add_intent(entry)
        return entry

    def significant_events(self, limit: int = 20) -> list[TimelineEntry]:
        """重要事件 (significance >= 0.7)。"""
        significant = [e for e in self.timeline.past if e.significance >= 0.7]
        significant.sort(key=lambda e: e.significance, reverse=True)
        return significant[:limit]

    def recent_past(self, limit: int = 50) -> list[TimelineEntry]:
        """最近的历史。"""
        return self.timeline.past[-limit:]

    @property
    def past_count(self) -> int:
        return self.timeline.past_count

    @property
    def intent_count(self) -> int:
        return self.timeline.intent_count


__all__ = ["TimelineEngine"]
