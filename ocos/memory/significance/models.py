"""Phase 24.2-A — Significance Gate 数据模型。

SignificanceScore: 四维度评分模型
    GoalImpact + PredictionError + KnowledgeChange + FutureRelevance

GateDecision: PASS / FAIL 决策
    阈值判定 + 理由

核心原则:
    Episode is not a stored experience.
    Episode is an experience that passed significance evaluation
    and is allowed to influence future cognition.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


# ── 门控决策 ──────────────────────────────────────────────────────────────────


class GateVerdict(Enum):
    PASS = "pass"       # 准予进入 Episode
    FAIL = "fail"       # 拒绝 — 价值不足


# ── 四维度评分 ───────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class DimensionScore:
    """单个维度的评分详情。"""
    name: str                  # "goal_impact" / "prediction_error" / etc.
    raw_score: float           # 0.0 ~ 1.0
    weight: float              # 维度权重 (总和 1.0)
    evidence: list[str] = field(default_factory=list)  # 评分依据


@dataclass(frozen=True)
class SignificanceScore:
    """四维度重要性评分。

    Significance = Σ(dimension.raw_score × dimension.weight)

    四个维度:
      goal_impact      — 是否与活跃 Goal 相关
      prediction_error  — 结果与预期偏差程度
      knowledge_change  — 是否产生了新知识
      future_relevance  — 是否可能影响未来决策
    """

    goal_impact: DimensionScore
    prediction_error: DimensionScore
    knowledge_change: DimensionScore
    future_relevance: DimensionScore

    weighted_total: float = 0.0           # 加权总分
    threshold: float = 0.5                # 判定阈值

    def __post_init__(self) -> None:
        total = (
            self.goal_impact.raw_score * self.goal_impact.weight
            + self.prediction_error.raw_score * self.prediction_error.weight
            + self.knowledge_change.raw_score * self.knowledge_change.weight
            + self.future_relevance.raw_score * self.future_relevance.weight
        )
        object.__setattr__(self, "weighted_total", round(total, 4))

    def all_evidence(self) -> list[str]:
        """收集所有维度的证据。"""
        evidence: list[str] = []
        for dim in [
            self.goal_impact,
            self.prediction_error,
            self.knowledge_change,
            self.future_relevance,
        ]:
            evidence.extend(dim.evidence)
        return evidence

    def dimension_summary(self) -> dict[str, float]:
        """返回 {维度名: 加权分数} 字典。"""
        return {
            d.name: round(d.raw_score * d.weight, 4)
            for d in [
                self.goal_impact,
                self.prediction_error,
                self.knowledge_change,
                self.future_relevance,
            ]
        }


# ── 门控决策 ──────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class GateDecision:
    """Significance Gate 的最终决策。"""

    candidate_id: str
    verdict: GateVerdict
    score: SignificanceScore
    reason: str                          # 人类可读的决策理由

    def passed(self) -> bool:
        return self.verdict == GateVerdict.PASS

    def failed(self) -> bool:
        return self.verdict == GateVerdict.FAIL
