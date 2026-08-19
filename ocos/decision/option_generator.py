"""Phase 43: OptionGenerator — 从上下文生成决策选项。

对给定 DecisionContext，生成一组可能的 DecisionOption。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ocos.decision.decision_types import (
    DecisionContext, DecisionOption, OptionType,
)


@dataclass
class OptionGenerator:
    """选项生成器 — 从上下文生成候选行动方案。

    生成策略:
        - wisdom_suggested: 从 wisdom_hints 推断
        - generated:        通用选项（investigate/do_nothing/defer）
    """

    max_options: int = 10

    def generate(self, context: DecisionContext, tick_id: int = 0) -> list[DecisionOption]:
        options: list[DecisionOption] = []

        # 总是包含的基线选项
        options.append(self._baseline_defer(context, tick_id))

        # 从 wisdom hints 生成建议选项
        for idx, hint in enumerate(context.wisdom_hints):
            if len(options) >= self.max_options:
                break
            opt = self._from_wisdom(hint, idx, tick_id)
            options.append(opt)

        # 从 goal + world 生成调查选项
        if context.goal_summary and context.world_snapshot:
            if len(options) < self.max_options:
                options.append(self._investigate_option(context, tick_id))

        return options

    def _baseline_defer(self, ctx: DecisionContext, tick: int) -> DecisionOption:
        return DecisionOption(
            option_id=f"defer:{tick}",
            description="推迟决策，等待更多信息",
            option_type=OptionType.DEFER,
            confidence=1.0,
            value_score=0.5,
            risk_score=0.0,
            source="generated",
        )

    def _from_wisdom(self, hint: str, idx: int, tick: int) -> DecisionOption:
        return DecisionOption(
            option_id=f"wisdom:{idx}:{tick}",
            description=f"基于经验智慧: {hint[:200]}",
            option_type=OptionType.DIRECT_ACTION,
            confidence=0.7,
            value_score=0.6,
            risk_score=0.3,
            source="wisdom_suggested",
            evidence=[hint],
        )

    def _investigate_option(self, ctx: DecisionContext, tick: int) -> DecisionOption:
        desc_parts = []
        if ctx.goal_summary:
            desc_parts.append(ctx.goal_summary[:100])
        return DecisionOption(
            option_id=f"investigate:{tick}",
            description=f"调查: {' / '.join(desc_parts) if desc_parts else '探索更多信息'}",
            option_type=OptionType.INVESTIGATE,
            confidence=0.5,
            value_score=0.4,
            risk_score=0.2,
            source="generated",
        )


__all__ = ["OptionGenerator"]
