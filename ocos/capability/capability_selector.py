"""Phase 45: CapabilitySelector — 能力选择器。

输入: Decision Proposal (Phase 43)
输出: SelectionResult

边界 CNS45-02: Selector ≠ Decision
    能力选择不能替代决策。
    正确: Decision → Selector → Capability
    错误: 发现能力 → 自动决定使用
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ocos.capability.capability_types import (
    Capability, CapabilityMatch, SelectionResult, CapabilityType,
)
from ocos.capability.capability_registry import CapabilityRegistry


@dataclass
class CapabilitySelector:
    """能力选择器。

    根据 Decision Proposal 中的需求选择最匹配的能力。

    考虑因素:
        - 匹配度（能力类型 vs 需求类型）
        - 历史成功率（performance_score）
        - 信任等级
        - 成本
        - 可用性
    """

    registry: CapabilityRegistry = field(default_factory=CapabilityRegistry)

    def select(self, required_type: CapabilityType) -> SelectionResult:
        """根据需求类型选择能力。"""
        candidates = self.registry.query_by_type(required_type)
        callable_candidates = [c for c in candidates if c.is_callable]

        if not callable_candidates:
            return SelectionResult()

        # 排序: performance_score > trust > cost
        trust_order = {"TRUSTED": 4, "VERIFIED": 3, "OBSERVING": 2, "UNKNOWN": 1, "DISTRUSTED": 0}

        scored = []
        for cap in callable_candidates:
            trust_score = trust_order.get(cap.trust_level, 0) / 4
            match_score = (
                cap.performance_score * 0.5 +
                trust_score * 0.3 +
                (1 - min(cap.cost_estimate, 1)) * 0.2
            )
            scored.append(CapabilityMatch(
                capability=cap,
                match_score=round(match_score, 4),
                reason=f"perf={cap.performance_score:.2f}, trust={cap.trust_level}, cost={cap.cost_estimate:.2f}",
            ))

        scored.sort(key=lambda m: m.match_score, reverse=True)
        return SelectionResult(
            matches=scored,
            selected=scored[0].capability if scored else None,
        )

    def select_by_tags(self, tags: list[str]) -> SelectionResult:
        """根据标签选择能力。"""
        matches = []
        for tag in tags:
            for cap in self.registry.query_by_tag(tag):
                if cap.is_callable:
                    matches.append(CapabilityMatch(
                        capability=cap,
                        match_score=cap.performance_score,
                        reason=f"matched tag: {tag}",
                    ))
        matches.sort(key=lambda m: m.match_score, reverse=True)
        return SelectionResult(
            matches=matches,
            selected=matches[0].capability if matches else None,
        )


__all__ = ["CapabilitySelector"]
