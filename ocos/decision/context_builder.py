"""Phase 43: ContextBuilder — 决策上下文聚合。

从四个Phase 39-42 层中提取相关信息:
    - Goal (Phase 39):   当前活跃目标
    - Self (Phase 40):   自我认知状态
    - Personal Wisdom (Phase 41):  相关经验智慧
    - World (Phase 42):  外部世界状态

产出统一 DecisionContext。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from ocos.decision.decision_types import DecisionContext


@dataclass
class ContextBuilder:
    """将分散的认知层聚合成统一决策上下文。

    各数据源通过 set_* 方法注入，build() 产出标准化上下文。
    """

    _goal_text: str = ""
    _self_text: str = ""
    _wisdom_texts: list[str] = field(default_factory=list)
    _world_text: str = ""
    _constraints: list[str] = field(default_factory=list)

    # ── 注入 ──

    def set_goal_context(self, summary: str) -> None:
        """注入当前活跃目标摘要。"""
        self._goal_text = summary

    def set_self_context(self, summary: str) -> None:
        """注入 SelfModel 关键信息摘要。"""
        self._self_text = summary

    def add_wisdom(self, wisdom_text: str) -> None:
        """注入一条相关智慧。"""
        if wisdom_text.strip():
            self._wisdom_texts.append(wisdom_text)

    def set_world_context(self, world_state_summary: str) -> None:
        """注入世界模型相关部分摘要。"""
        self._world_text = world_state_summary

    def add_constraint(self, constraint: str) -> None:
        """添加显式约束。"""
        if constraint.strip():
            self._constraints.append(constraint)

    # ── 构建 ──

    def build(self, tick_id: int = 0) -> DecisionContext:
        return DecisionContext(
            context_id=f"ctx:{tick_id}",
            goal_summary=self._goal_text,
            self_summary=self._self_text,
            wisdom_hints=list(self._wisdom_texts),
            world_snapshot=self._world_text,
            constraints=list(self._constraints),
            tick_id=tick_id,
        )

    def reset(self) -> None:
        self._goal_text = ""
        self._self_text = ""
        self._wisdom_texts = []
        self._world_text = ""
        self._constraints = []


__all__ = ["ContextBuilder"]
