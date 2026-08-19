"""Phase 48: MaturityMetrics — 成熟度度量。

量化 OCOS 个人智能成熟度。

度量维度:
    - 认知特征可靠性 (pattern_confidence)
    - 一致性基线漂移 (drift_from_baseline)
    - 决策元认知覆盖 (meta-cognition ratio)
    - 个性化适配深度 (personalization_depth)
    - 目标协调完整度 (goal tracking coverage)
    - 经验学习转化率 (Wisdom accumulation rate)

输出: MaturityLevel + 综合分数。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ocos.personal_intelligence.pi_types import MaturityLevel


@dataclass
class MaturityReport:
    """成熟度报告。"""
    level: MaturityLevel = MaturityLevel.INITIALIZING
    score: float = 0.0
    dimensions: dict[str, float] = field(default_factory=dict)
    recommendations: list[str] = field(default_factory=list)


def calculate_maturity(
    pattern_confidence: float,
    consistency_drift: float,
    meta_cognition_ratio: float,
    personalization_depth: float,
    goal_tracking_coverage: float,
    wisdom_accumulation_rate: float,
) -> MaturityReport:
    """综合计算个人智能成熟度。"""
    weights = {
        "pattern_confidence": 0.25,
        "consistency": 0.20,
        "meta_cognition": 0.15,
        "personalization": 0.20,
        "goal_tracking": 0.10,
        "wisdom": 0.10,
    }

    # consistency_drift 越低越好 (1 - drift)
    consistency_score = max(0.0, 1.0 - consistency_drift)

    dims = {
        "pattern_confidence": pattern_confidence,
        "consistency": consistency_score,
        "meta_cognition": meta_cognition_ratio,
        "personalization": personalization_depth,
        "goal_tracking": goal_tracking_coverage,
        "wisdom": min(1.0, wisdom_accumulation_rate),
    }

    score = sum(dims[k] * weights[k] for k in weights)

    if score < 0.3:
        level = MaturityLevel.INITIALIZING
    elif score < 0.5:
        level = MaturityLevel.LEARNING
    elif score < 0.7:
        level = MaturityLevel.ADAPTING
    elif score < 0.85:
        level = MaturityLevel.MATURE
    else:
        level = MaturityLevel.DEEPENING

    recommendations = []
    if pattern_confidence < 0.3:
        recommendations.append("Need more user interaction data")
    if consistency_drift > 0.3:
        recommendations.append("Consistency drift detected — review evolution history")
    if meta_cognition_ratio < 0.3:
        recommendations.append("Enable meta-cognition tracing for more decisions")
    if personalization_depth < 0.2:
        recommendations.append("Build cognitive signature through more observations")
    if goal_tracking_coverage < 0.5:
        recommendations.append("Register long-term goals for better coordination")

    return MaturityReport(
        level=level,
        score=score,
        dimensions=dims,
        recommendations=recommendations,
    )


__all__ = ["MaturityReport", "calculate_maturity"]
