"""Phase 43: RiskEngine — 决策选项风险分析。

对每个 DecisionOption 评估多维度风险。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ocos.decision.decision_types import (
    DecisionOption, RiskAssessment, RiskCategory, RiskLevel,
)


@dataclass
class RiskEngine:
    """风险评估引擎 — 分析每个选项的风险。

    评分规则:
        - 操作风险: 基于 confidence + option_type
        - 资源风险: 基于 prerequisites
        - 安全风险: 基于 source
    """

    risk_threshold: float = 0.7  # 高于此值视为高风险

    def assess(self, option: DecisionOption) -> RiskAssessment:
        """对一个选项执行风险分析，返回单一评估（主要风险）。"""
        cat, score, desc = self._analyze(option)
        return RiskAssessment(
            option_id=option.option_id,
            assessment_id=f"risk:{option.option_id}",
            category=cat,
            level=self._score_to_level(score),
            score=score,
            description=desc,
            probability=score,
        )

    def assess_all(self, options: list[DecisionOption]) -> list[RiskAssessment]:
        return [self.assess(opt) for opt in options]

    def _analyze(self, opt: DecisionOption) -> tuple[RiskCategory, float, str]:
        # 置信度低 → 高风险
        if opt.confidence < 0.3:
            return RiskCategory.OPERATIONAL, 0.8, f"低置信度 ({opt.confidence:.2f})"

        # 外部来源 → 安全/依赖风险
        if opt.source == "wisdom_suggested":
            score = 0.3 + (1 - opt.confidence) * 0.3
            return RiskCategory.DEPENDENCY, score, "基于历史智慧的建议需要验证"

        # 有前置条件
        if opt.prerequisites:
            prereq_score = min(0.8, len(opt.prerequisites) * 0.15)
            return RiskCategory.RESOURCE, prereq_score, f"需要 {len(opt.prerequisites)} 个前置条件"

        # 默认
        return RiskCategory.OPERATIONAL, 0.35, "一般操作风险"

    def _score_to_level(self, score: float) -> RiskLevel:
        if score < 0.2:
            return RiskLevel.NEGLIGIBLE
        if score < 0.4:
            return RiskLevel.LOW
        if score < 0.6:
            return RiskLevel.MEDIUM
        if score < 0.8:
            return RiskLevel.HIGH
        return RiskLevel.CRITICAL


__all__ = ["RiskEngine"]
