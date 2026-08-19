"""Phase 43: ValueModel — 决策价值评估框架。

对每个选项做多维度价值评估。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ocos.decision.decision_types import (
    DecisionOption, ValueEvaluation, ValueDimension, OptionType,
)


@dataclass
class ValueModel:
    """价值模型 — 定义哪些维度重要以及如何评估。

    默认权重: Safety > Alignment > Reliability > Efficiency > Learning > Novelty
    """

    weights: dict[ValueDimension, float] = field(default_factory=lambda: {
        ValueDimension.SAFETY: 0.25,
        ValueDimension.ALIGNMENT: 0.20,
        ValueDimension.RELIABILITY: 0.20,
        ValueDimension.EFFICIENCY: 0.15,
        ValueDimension.LEARNING: 0.10,
        ValueDimension.NOVELTY: 0.10,
    })

    def evaluate(self, option: DecisionOption) -> ValueEvaluation:
        dims = self._score_dimensions(option)
        overall = self._weighted(dims)
        return ValueEvaluation(
            option_id=option.option_id,
            evaluation_id=f"val:{option.option_id}",
            dimensions=dims,
            overall_score=overall,
        )

    def evaluate_all(self, options: list[DecisionOption]) -> list[ValueEvaluation]:
        return [self.evaluate(opt) for opt in options]

    def _score_dimensions(self, opt: DecisionOption) -> dict[ValueDimension, float]:
        dims: dict[ValueDimension, float] = {}

        # 可靠性: 基于置信度
        dims[ValueDimension.RELIABILITY] = opt.confidence

        # 安全性: 基于风险
        dims[ValueDimension.SAFETY] = 1.0 - opt.risk_score

        # 对齐度: 基于 value_score（外部赋值）
        dims[ValueDimension.ALIGNMENT] = opt.value_score

        # 效率: defer > do_nothing > investigate > direct
        efficiency_map = {
            "defer": 0.5,
            "do_nothing": 0.6,
            "investigate": 0.4,
            "direct_action": 0.7,
            "delegate": 0.6,
        }
        dims[ValueDimension.EFFICIENCY] = efficiency_map.get(
            opt.option_type.value, 0.5
        )

        # 学习价值: investigate > direct > defer
        learning_map = {
            "investigate": 0.8,
            "direct_action": 0.6,
            "delegate": 0.4,
            "defer": 0.2,
            "do_nothing": 0.0,
        }
        dims[ValueDimension.LEARNING] = learning_map.get(
            opt.option_type.value, 0.3
        )

        # 新颖性: 非 DO_NOTHING
        if opt.option_type != OptionType.DO_NOTHING:
            dims[ValueDimension.NOVELTY] = 0.5
        else:
            dims[ValueDimension.NOVELTY] = 0.0

        return dims

    def _weighted(self, dims: dict[ValueDimension, float]) -> float:
        total = 0.0
        weight_sum = 0.0
        for dim, w in self.weights.items():
            total += dims.get(dim, 0.0) * w
            weight_sum += w
        return round(total / weight_sum, 4)


__all__ = ["ValueModel"]
