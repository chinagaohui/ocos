"""Phase 49: LifeMemoryGraph — 生命记忆图引擎。

管理 OCOS 的长期记忆结构。

层次:
    Experience → Day → Week → Month → Season → Year

每一层做质量筛选和提炼 (CC49-01)。
质量和意义优先于数量。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ocos.cognitive_continuity.continuity_types import (
    ExperienceNode,
    TimeContainer,
    TimeGranularity,
    LifeMemoryGraph,
)


@dataclass
class LifeMemoryEngine:
    """生命记忆图引擎。

    管理层次化记忆:
        - 记录重要经验
        - 日/周/月/季/年 周期性提炼
        - 容量限制防止膨胀 (CC49-01: 质量>数量)
    """

    graph: LifeMemoryGraph = field(default_factory=LifeMemoryGraph)

    # 容量限制 (CC49-01)
    MAX_EXPERIENCES = 10000
    MAX_DAYS = 365
    MAX_WEEKS = 52
    MAX_MONTHS = 24
    MAX_SEASONS = 16
    MAX_YEARS = 10

    def record_experience(
        self, tick_id: int, summary: str,
        importance: float = 0.5, tags: list[str] | None = None,
    ) -> ExperienceNode | None:
        """记录一次经验——重要性筛选 (CC49-01)。"""
        if importance < 0.1:
            # 低重要性经验直接丢弃
            return None

        node = ExperienceNode(
            node_id=f"exp:{tick_id}:{len(self.graph.experiences)}",
            tick_id=tick_id,
            summary=summary[:200],  # 长度限制
            importance=importance,
            tags=tags or [],
            created_at_tick=tick_id,
        )

        self.graph.experiences.append(node)

        # 容量管理: 重要性最低的优先淘汰
        if len(self.graph.experiences) > self.MAX_EXPERIENCES:
            # 按重要性排序，丢弃低重要性
            sorted_nodes = sorted(
                self.graph.experiences, key=lambda n: n.importance,
            )
            cutoff = len(self.graph.experiences) - self.MAX_EXPERIENCES
            self.graph.experiences = sorted_nodes[cutoff:]

        return node

    def aggregate_day(
        self, label: str, entries: list[ExperienceNode],
    ) -> TimeContainer:
        """日汇总——提炼当天重点经验。"""
        container = TimeContainer(
            granularity=TimeGranularity.DAY,
            label=label,
            max_entries=30,
        )
        # 取重要性最高的前N个
        sorted_entries = sorted(entries, key=lambda e: e.importance, reverse=True)
        container.entries = sorted_entries[:container.max_entries]
        container.summary = self._summarize(sorted_entries[:5])

        self.graph.days.append(container)
        if len(self.graph.days) > self.MAX_DAYS:
            self.graph.days = self.graph.days[-self.MAX_DAYS:]
        return container

    def aggregate_week(
        self, label: str, days: list[TimeContainer],
    ) -> TimeContainer:
        """周总结——日汇总的精选提炼。"""
        container = TimeContainer(
            granularity=TimeGranularity.WEEK,
            label=label,
            max_entries=20,
        )
        # 从每日总结中提取重点
        all_summaries = [d.summary for d in days if d.summary]
        container.entries = all_summaries[:container.max_entries]
        container.summary = self._summarize(all_summaries[:3])

        self.graph.weeks.append(container)
        if len(self.graph.weeks) > self.MAX_WEEKS:
            self.graph.weeks = self.graph.weeks[-self.MAX_WEEKS:]
        return container

    def aggregate_month(
        self, label: str, weeks: list[TimeContainer],
    ) -> TimeContainer:
        """月摘要——周总结的模式提炼。"""
        container = TimeContainer(
            granularity=TimeGranularity.MONTH,
            label=label,
            max_entries=15,
        )
        all_summaries = [w.summary for w in weeks if w.summary]
        container.entries = all_summaries[:container.max_entries]
        container.summary = self._summarize(all_summaries[:2])

        self.graph.months.append(container)
        if len(self.graph.months) > self.MAX_MONTHS:
            self.graph.months = self.graph.months[-self.MAX_MONTHS:]
        return container

    def aggregate_year(
        self, label: str, months: list[TimeContainer],
    ) -> TimeContainer:
        """年度结晶——月度反思的模式汇聚 (CC49-01)。"""
        container = TimeContainer(
            granularity=TimeGranularity.YEAR,
            label=label,
            max_entries=10,
        )
        # 年度总结: 最深层次的提炼
        all_summaries = [m.summary for m in months if m.summary]
        container.entries = all_summaries[:container.max_entries]
        container.summary = self._summarize(all_summaries[:3])

        self.graph.years.append(container)
        if len(self.graph.years) > self.MAX_YEARS:
            self.graph.years = self.graph.years[-self.MAX_YEARS:]
        return container

    def recent_memory(self, limit: int = 50) -> list[ExperienceNode]:
        """最近的记忆 (按时间)。"""
        return self.graph.experiences[-limit:]

    def important_memories(self, threshold: float = 0.7) -> list[ExperienceNode]:
        """高重要性记忆。"""
        return [e for e in self.graph.experiences if e.importance >= threshold]

    def by_tag(self, tag: str) -> list[ExperienceNode]:
        """按标签检索。"""
        return [e for e in self.graph.experiences if tag in e.tags]

    def _summarize(self, items, max_len: int = 200) -> str:
        if not items:
            return ""
        # items can be str or ExperienceNode
        parts = [getattr(i, "summary", str(i)) for i in items]
        return "; ".join(parts)[:max_len]

    @property
    def is_full(self) -> bool:
        return len(self.graph.experiences) >= self.MAX_EXPERIENCES


__all__ = ["LifeMemoryEngine"]
