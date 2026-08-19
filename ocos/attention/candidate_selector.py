"""Phase 39.5: Candidate Selector — 注意力候选项收集。

职责：接收外部输入的候选项（来自 TickPipeline 上游 stage），标准化为
AttentionCandidate 列表。自身不 import Goal/Event/Maintenance 模块。

设计约束：
    - 纯函数模块，不访问 GoalTree / EventQueue
    - 候选项由 TickPipeline 的 upstream stages 提供
    - Attention 只选择，不创建
"""

from __future__ import annotations

from .attention_types import AttentionCandidate, FocusType


class CandidateCollector:
    """候选项收集器 — 外部注入候选项的容器。

    每一 tick 清空后重新收集。
    TickPipeline 的 goal_check / event_ingest 阶段调用 add_* 方法填充。
    """

    def __init__(self) -> None:
        self._candidates: list[AttentionCandidate] = []

    # ── 注入接口 ──

    def add_goal(self, goal_id: str, importance: float,
                 summary: str = "", urgency: float = 0.0,
                 context_relevance: float = 0.0, user_preference: float = 0.0,
                 created_tick: int = 0, age: int = 0) -> None:
        """添加 Goal 候选项。"""
        self._candidates.append(AttentionCandidate(
            candidate_id=goal_id,
            candidate_type=FocusType.GOAL,
            goal_importance=importance,
            urgency=urgency,
            context_relevance=context_relevance,
            user_preference=user_preference,
            summary=summary,
            created_tick=created_tick,
            age=age,
            source="goal_tree",
        ))

    def add_event(self, event_id: str, urgency: float,
                  summary: str = "", context_relevance: float = 0.0,
                  created_tick: int = 0, age: int = 0) -> None:
        """添加 Event 候选项。"""
        self._candidates.append(AttentionCandidate(
            candidate_id=event_id,
            candidate_type=FocusType.EVENT,
            urgency=urgency,
            context_relevance=context_relevance,
            summary=summary,
            created_tick=created_tick,
            age=age,
            source="event_queue",
        ))

    def add_maintenance(self, maintenance_id: str, urgency: float,
                        summary: str = "", context_relevance: float = 0.0,
                        created_tick: int = 0, age: int = 0) -> None:
        """添加 Maintenance 候选项。"""
        self._candidates.append(AttentionCandidate(
            candidate_id=maintenance_id,
            candidate_type=FocusType.MAINTENANCE,
            urgency=urgency,
            context_relevance=context_relevance,
            summary=summary,
            created_tick=created_tick,
            age=age,
            source="maintenance_queue",
        ))

    # ── 查询接口 ──

    def candidates(self) -> list[AttentionCandidate]:
        """返回当前 tick 收集的所有候选项。"""
        return list(self._candidates)

    def clear(self) -> None:
        """清空候选项（每 tick 开始时调用）。"""
        self._candidates.clear()

    @property
    def count(self) -> int:
        return len(self._candidates)

    @property
    def has_candidates(self) -> bool:
        return len(self._candidates) > 0
