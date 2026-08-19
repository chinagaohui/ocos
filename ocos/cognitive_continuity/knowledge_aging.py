"""Phase 49: KnowledgeAging — 知识时效性管理。

长期运行中的知识/智慧会过时。

分级老化策略:
    FRESH → 权重 1.0  (0-1 月)
    CURRENT → 权重 0.8  (1-6 月)
    AGING → 权重 0.5   (6-12 月)
    LEGACY → 权重 0.2  (>1 年)
    ARCHIVED → 权重 0.0 (>3 年)

    核心知识 (is_core=True) 不受 aging 影响 (CC49-03)。

CC49-03: Knowledge Aging ≠ Amnesia
    分级衰减，核心知识保护。
    不是删除——是降权。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ocos.cognitive_continuity.continuity_types import (
    AgedKnowledge,
    KnowledgeAge,
)


# Tick-to-month approximations (assuming ~1000 ticks/day)
_TICKS_PER_DAY = 1000
TICKS_PER_MONTH = 30 * _TICKS_PER_DAY     # ~30K
TICKS_PER_HALF_YEAR = 6 * TICKS_PER_MONTH  # ~180K
TICKS_PER_YEAR = 12 * TICKS_PER_MONTH      # ~360K
TICKS_PER_3Y = 3 * TICKS_PER_YEAR          # ~1.08M


@dataclass
class KnowledgeAgingEngine:
    """知识老化引擎——管理知识/智慧的时效性。

    CC49-03: 分级衰减。核心知识永不过期。
    """

    items: list[AgedKnowledge] = field(default_factory=list)

    def register(
        self, knowledge_id: str, content: str, is_core: bool = False,
    ) -> AgedKnowledge:
        """注册新知识。"""
        item = AgedKnowledge(
            knowledge_id=knowledge_id,
            content=content[:500],
            ticks_age=0,
            age=KnowledgeAge.FRESH,
            last_referenced_tick=0,
            is_core=is_core,
            weight=1.0,
        )
        self.items.append(item)
        return item

    def age_all(self, current_tick: int = 0) -> list[AgedKnowledge]:
        """对所有知识执行时效推进。

        current_tick: 当前 tick 数，用于判断被引用过的知识的年龄。
        如果知识曾被引用过，用 last_referenced_tick 计算；
        否则保留存储的 ticks_age (可用于模拟外部时间流逝)。
        """
        changed: list[AgedKnowledge] = []
        for item in self.items:
            if item.last_referenced_tick > 0:
                item.ticks_age = current_tick - item.last_referenced_tick

            old_age = item.age
            new_age = self._classify_age(item.ticks_age)

            if new_age != old_age:
                item.age = new_age
                changed.append(item)

            # 更新权重——核心知识不受影响 (CC49-03)
            if not item.is_core:
                item.weight = self._weight_for_age(new_age)
            else:
                item.weight = 1.0  # 核心知识保持 1.0

        return changed

    def reference(self, knowledge_id: str, tick_id: int) -> bool:
        """引用知识——刷新时效性。"""
        for item in self.items:
            if item.knowledge_id == knowledge_id:
                item.last_referenced_tick = tick_id
                item.reference_count += 1
                item.ticks_age = 0
                item.age = KnowledgeAge.FRESH
                item.weight = 1.0
                return True
        return False

    def _classify_age(self, ticks: int) -> KnowledgeAge:
        if ticks < TICKS_PER_MONTH:
            return KnowledgeAge.FRESH
        elif ticks < TICKS_PER_HALF_YEAR:
            return KnowledgeAge.CURRENT
        elif ticks < TICKS_PER_YEAR:
            return KnowledgeAge.AGING
        elif ticks < TICKS_PER_3Y:
            return KnowledgeAge.LEGACY
        return KnowledgeAge.ARCHIVED

    @staticmethod
    def _weight_for_age(age: KnowledgeAge) -> float:
        return {
            KnowledgeAge.FRESH: 1.0,
            KnowledgeAge.CURRENT: 0.8,
            KnowledgeAge.AGING: 0.5,
            KnowledgeAge.LEGACY: 0.2,
            KnowledgeAge.ARCHIVED: 0.0,
        }[age]

    def active_knowledge(self) -> list[AgedKnowledge]:
        """活跃知识 (weight > 0) — CC49-03: 不是删除，是降权。"""
        return [item for item in self.items if item.weight > 0.0]

    def core_knowledge(self) -> list[AgedKnowledge]:
        """核心知识——永远权重 1.0。"""
        return [item for item in self.items if item.is_core]

    def weight_summary(self) -> dict[KnowledgeAge, int]:
        """各年龄段的条目数量统计。"""
        counts: dict[KnowledgeAge, int] = {a: 0 for a in KnowledgeAge}
        for item in self.items:
            counts[item.age] += 1
        return counts

    @property
    def total_items(self) -> int:
        return len(self.items)


__all__ = ["KnowledgeAgingEngine", "TICKS_PER_MONTH"]
