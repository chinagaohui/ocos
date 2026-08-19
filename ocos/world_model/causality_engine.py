"""Phase 42: CausalityEngine — 因果推断引擎。

World Model 与 Knowledge Base 最大区别: 有因果层。

不是"X 和 Y 相关"，而是"因为 X 所以 Y"。

约束:
    - 因果必须是基于证据的
    - 区分 DIRECT/CONTRIBUTES/ENABLES/PREVENTS/CORRELATED
    - 因果链可以被反驳
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from ocos.world_model.world_types import (
    CausalityLink, CausalityType, WorldEvent,
)


@dataclass
class CausalityEngine:
    """因果推断引擎 — 发现和查询因果链。

    不是通用推理引擎，而是专门针对 WorldEvent 的因果分析。
    """

    _links: dict[str, CausalityLink] = field(default_factory=dict)
    _cause_index: dict[str, list[str]] = field(default_factory=dict)  # event_id → link_ids
    _effect_index: dict[str, list[str]] = field(default_factory=dict)

    # ── CRUD ──

    def add_link(self, link: CausalityLink) -> None:
        if link.link_id in self._links:
            raise ValueError(f"CausalityLink {link.link_id} already exists")
        self._links[link.link_id] = link
        self._cause_index.setdefault(link.cause_event_id, []).append(link.link_id)
        self._effect_index.setdefault(link.effect_event_id, []).append(link.link_id)

    def get(self, link_id: str) -> Optional[CausalityLink]:
        return self._links.get(link_id)

    # ── 查询 ──

    def causes_of(self, event_id: str) -> list[CausalityLink]:
        """查询导致该事件的原因。"""
        return [self._links[lid] for lid in self._effect_index.get(event_id, [])]

    def effects_of(self, event_id: str) -> list[CausalityLink]:
        """查询该事件导致的结果。"""
        return [self._links[lid] for lid in self._cause_index.get(event_id, [])]

    def causal_chain(self, start_event_id: str, max_depth: int = 5) -> list[CausalityLink]:
        """从起始事件开始，追踪因果链（下游方向）。

        A → B → C → ... 直到 max_depth 或无下游。
        """
        chain: list[CausalityLink] = []
        current = start_event_id
        for _ in range(max_depth):
            effects = self.effects_of(current)
            if not effects:
                break
            # 取置信度最高的
            best = max(effects, key=lambda l: l.confidence)
            chain.append(best)
            current = best.effect_event_id
        return chain

    def upstream_chain(self, end_event_id: str, max_depth: int = 5) -> list[CausalityLink]:
        """从终止事件往上追溯原因链。

        ... → X → Y → Z (end_event_id)
        """
        chain: list[CausalityLink] = []
        current = end_event_id
        for _ in range(max_depth):
            causes = self.causes_of(current)
            if not causes:
                break
            best = max(causes, key=lambda l: l.confidence)
            chain.append(best)
            current = best.cause_event_id
        chain.reverse()  # 从最早原因到最近
        return chain

    def well_supported(self) -> list[CausalityLink]:
        """获取所有充分支持的因果链。"""
        return [l for l in self._links.values() if l.is_well_supported]

    def contested(self) -> list[CausalityLink]:
        """获取有反例的因果链。"""
        return [l for l in self._links.values() if l.has_counter_evidence]

    # ── 统计 ──

    @property
    def count(self) -> int:
        return len(self._links)

    def confidence_distribution(self) -> list[float]:
        return [l.confidence for l in self._links.values()]


__all__ = ["CausalityEngine"]
