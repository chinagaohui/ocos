"""Phase 49: Continuity Types — 认知连续性类型系统。

解决核心问题:
    一个 OCOS 使用 5 年、10 年后，如何保持连续人格和认知积累？

核心概念:
    - Life Memory Graph: 经验 → 周 → 月 → 年 的层次化记忆
    - Cognitive Timeline: 过去的我 → 当前的我 → 未来规划中的我
    - Identity Snapshot: 定期冻结的身份快照
    - Knowledge Aging: 知识/智慧的时效性管理

核心边界:
    CC49-01: Continuity ≠ Archive   — 质量筛选，不保存一切
    CC49-02: Identity Continuity ≠ Freeze — 检测漂移，不阻止演化 (Phase 47)
    CC49-03: Knowledge Aging ≠ Amnesia — 分级老化，不丢失核心记忆
    CC49-04: Timeline ≠ Prediction  — 记录过去与现在，不预测未来
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


# ═══════════════════════════════════════════════════════════════════════════════
# 时间层次
# ═══════════════════════════════════════════════════════════════════════════════


class TimeGranularity(Enum):
    """记忆的时间粒度层次。"""
    EXPERIENCE = "experience"  # 单次经验
    DAY = "day"               # 日汇总
    WEEK = "week"             # 周总结
    MONTH = "month"           # 月摘要
    SEASON = "season"         # 季度反思
    YEAR = "year"             # 年度结晶


class TimeAnchor(Enum):
    """认知时间锚点——定位在时间线上的位置。"""
    PAST = "past"           # 过去的记录
    PRESENT = "present"     # 当前状态
    FUTURE_INTENT = "future_intent"  # 未来规划 (CC49-04: 意图≠预测)


# ═══════════════════════════════════════════════════════════════════════════════
# Life Memory Graph
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class ExperienceNode:
    """单次经验的记忆节点。"""
    node_id: str = ""
    tick_id: int = 0
    summary: str = ""                # 精简摘要 (CC49-01: 质量筛选)
    importance: float = 0.0          # [0,1] 重要性评分
    tags: list[str] = field(default_factory=list)
    created_at_tick: int = 0


@dataclass
class TimeContainer:
    """时间容器——层次化记忆存储。

    CC49-01: 每一层做质量筛选。
    DAY: 保留重要的经验
    WEEK: 日汇总的精选总结
    MONTH: 周总结的模式提炼
    SEASON: 月度反思
    YEAR: 年度智慧结晶
    """
    granularity: TimeGranularity = TimeGranularity.DAY
    label: str = ""                  # e.g. "2026-W30", "2026-07"
    entries: list = field(default_factory=list)   # ExperienceNode or str
    summary: str = ""                # 本时间段的提炼总结
    max_entries: int = 20            # 容量限制 (CC49-01)


@dataclass
class LifeMemoryGraph:
    """Life Memory Graph — 层次化长期记忆。

    结构:
        Years → Months → Weeks → Days → Experiences

    不是存档所有——是层次提炼 (CC49-01)。
    """

    years: list[TimeContainer] = field(default_factory=list)
    months: list[TimeContainer] = field(default_factory=list)
    weeks: list[TimeContainer] = field(default_factory=list)
    days: list[TimeContainer] = field(default_factory=list)
    experiences: list[ExperienceNode] = field(default_factory=list)

    @property
    def total_experiences(self) -> int:
        return len(self.experiences)


# ═══════════════════════════════════════════════════════════════════════════════
# Cognitive Timeline
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class TimelineEntry:
    """时间线条目——单一的认知时刻。"""
    entry_id: str = ""
    anchor: TimeAnchor = TimeAnchor.PRESENT
    tick_id: int = 0
    label: str = ""             # 人类可读标签
    summary: str = ""           # 发生了/将要发生什么
    significance: float = 0.0   # [0,1] 重要性


@dataclass
class CognitiveTimeline:
    """认知时间线——我看到了自己如何变化。

    三部分:
        past_timeline: 决策/经验历史
        present_snapshot: 当前状态快照
        future_intents: 用户规划的意图 (CC49-04: 不是预测)

    CC49-04: future_intents 只记录用户明确意图，
             不推测"OCOS 认为用户应该做什么"。
    """

    past: list[TimelineEntry] = field(default_factory=list)
    present: list[TimelineEntry] = field(default_factory=list)
    future_intents: list[TimelineEntry] = field(default_factory=list)

    def add_past(self, entry: TimelineEntry) -> None:
        entry.anchor = TimeAnchor.PAST
        self.past.append(entry)

    def add_present(self, entry: TimelineEntry) -> None:
        entry.anchor = TimeAnchor.PRESENT
        self.present.append(entry)

    def add_intent(self, entry: TimelineEntry) -> None:
        """CC49-04: 添加用户意图。禁止 OCOS 自行生成 future 条 目。"""
        entry.anchor = TimeAnchor.FUTURE_INTENT
        self.future_intents.append(entry)

    @property
    def past_count(self) -> int:
        return len(self.past)

    @property
    def intent_count(self) -> int:
        return len(self.future_intents)


# ═══════════════════════════════════════════════════════════════════════════════
# Identity Snapshot (定期身份快照)
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class IdentitySnapshot:
    """身份快照——定期冻结，用于连续性验证。

    CC49-02: 快照是检测工具，不是锁。
             检测漂移时报告，不自动阻止演化。
    """
    snapshot_id: str = ""
    tick_id: int = 0
    label: str = ""              # e.g. "2026-W30 snapshot"
    risk_tolerance: str = ""     # 当时的风险偏好
    decision_style: str = ""     # 当时的决策风格
    key_memories: list[str] = field(default_factory=list)
    wisdom_count: int = 0
    evolution_count: int = 0


# ═══════════════════════════════════════════════════════════════════════════════
# Knowledge Aging (知识时效性)
# ═══════════════════════════════════════════════════════════════════════════════


class KnowledgeAge(Enum):
    """知识年龄等级。"""
    FRESH = "fresh"           # < 1 月
    CURRENT = "current"       # < 6 月
    AGING = "aging"           # 6-12 月
    LEGACY = "legacy"         # > 1 年
    ARCHIVED = "archived"     # > 3 年


@dataclass
class AgedKnowledge:
    """带时效性标记的知识条目。"""
    knowledge_id: str = ""
    content: str = ""
    ticks_age: int = 0
    age: KnowledgeAge = KnowledgeAge.FRESH
    last_referenced_tick: int = 0
    reference_count: int = 0
    weight: float = 1.0         # 权重随 age 衰减
    is_core: bool = False       # 核心知识不受 aging 影响 (CC49-03)


__all__ = [
    "TimeGranularity",
    "TimeAnchor",
    "ExperienceNode",
    "TimeContainer",
    "LifeMemoryGraph",
    "TimelineEntry",
    "CognitiveTimeline",
    "IdentitySnapshot",
    "KnowledgeAge",
    "AgedKnowledge",
]
