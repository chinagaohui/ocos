"""Phase 24.4-B — Confidence Engine。

Evidence 集合 → Confidence + Uncertainty。

核心原则:
    Confidence 只回答 "这个判断可信度是多少？"
    不回答 "我应该做什么？" (→ Goal)
    不回答 "我是什么？" (→ Self)

计算维度:
    1. Quality    — 证据质量 (加权平均)
    2. Consistency — 证据间一致性 (dispersion)
    3. Recency    — 新近度衰减 (时间权重)
    4. Counter    — 反证惩罚 (counterexamples)
    5. Volume     — 证据量饱和曲线 (边际递减)

禁止:
    Confidence → Priority
    Confidence → Goal
    Confidence → Self
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Optional

from ocos.memory.belief.models import Evidence


# ── ConfidenceConfig ──────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ConfidenceConfig:
    """Confidence Engine 的权重配置 (可审计)。"""

    # 维度权重 (sum = 1.0)
    weight_quality: float = 0.35        # 证据质量权重
    weight_consistency: float = 0.30    # 证据一致性权重
    weight_recency: float = 0.20        # 新近度权重
    weight_volume: float = 0.10         # 证据量权重 (边际递减)
    weight_counter: float = 0.05        # 反证惩罚权重

    # 阈值
    min_confidence: float = 0.3         # 低于此值 → INVALIDATED
    weak_threshold: float = 0.6         # 低于此值 → WEAKENED
    saturation_limit: int = 15          # 证据量饱和点
    recency_half_life_days: float = 30.0  # 新近度半衰期 (天)

    # 反证
    counter_impact_max: float = 0.15    # 反证最大影响 (cap)

    def __post_init__(self) -> None:
        total = (
            self.weight_quality
            + self.weight_consistency
            + self.weight_recency
            + self.weight_volume
            + self.weight_counter
        )
        if abs(total - 1.0) > 0.001:
            raise ValueError(f"Weights must sum to 1.0, got {total}")


# ── ConfidenceResult ─────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ConfidenceResult:
    """Confidence Engine 计算结果 (带维度审计)。"""

    confidence: float                           # 综合置信度 [0.0, 1.0]
    uncertainty: float                          # 不确定性 [0.0, 1.0]
    dimensions: dict[str, float]                # 各维度得分
    evidence_count: int                         # 证据数量
    status: str                                 # active | weakened | invalidated

    @property
    def is_confident(self) -> bool:
        return self.status == "active"

    @property
    def is_weakened(self) -> bool:
        return self.status == "weakened"

    @property
    def is_invalidated(self) -> bool:
        return self.status == "invalidated"


# ── ConfidenceEngine ─────────────────────────────────────────────────────────


class ConfidenceEngine:
    """Evidence → Confidence 的独立计算引擎。

    不依赖 Goal / Self / Priority。
    只基于 Evidence 数学特性计算置信度。
    """

    def __init__(self, config: ConfidenceConfig | None = None) -> None:
        self._config = config or ConfidenceConfig()

    @property
    def config(self) -> ConfidenceConfig:
        return self._config

    # ── 公共接口 ─────────────────────────────────────────────────────────

    def evaluate(
        self,
        evidence: list[Evidence],
        counterexamples: int = 0,
        now: datetime | None = None,
    ) -> ConfidenceResult:
        """计算 Evidence 集合的综合置信度。

        Args:
            evidence: 证据列表
            counterexamples: 反例数量 (来自 KnowledgeEntry)
            now: 参考时间 (默认当前)

        Returns:
            ConfidenceResult with per-dimension audit.
        """
        if not evidence:
            return ConfidenceResult(
                confidence=0.0,
                uncertainty=1.0,
                dimensions={},
                evidence_count=0,
                status="invalidated",
            )

        ref_time = now or datetime.now(timezone.utc)
        n = len(evidence)

        # 维度计算
        dim_quality = self._compute_quality(evidence)
        dim_consistency = self._compute_consistency(evidence)
        dim_recency = self._compute_recency(evidence, ref_time)
        dim_volume = self._compute_volume(n)
        dim_counter = self._compute_counter_penalty(counterexamples)

        # 加权合成
        raw = (
            dim_quality * self._config.weight_quality
            + dim_consistency * self._config.weight_consistency
            + dim_recency * self._config.weight_recency
            + dim_volume * self._config.weight_volume
            + dim_counter * self._config.weight_counter
        )

        confidence = round(max(0.0, min(1.0, raw)), 4)
        uncertainty = self._compute_uncertainty(dim_quality, dim_consistency, n)

        # 状态判定
        if confidence < self._config.min_confidence:
            status = "invalidated"
        elif confidence < self._config.weak_threshold:
            status = "weakened"
        else:
            status = "active"

        return ConfidenceResult(
            confidence=confidence,
            uncertainty=round(max(0.0, min(1.0, uncertainty)), 4),
            dimensions={
                "quality": round(dim_quality, 4),
                "consistency": round(dim_consistency, 4),
                "recency": round(dim_recency, 4),
                "volume": round(dim_volume, 4),
                "counter": round(dim_counter, 4),
            },
            evidence_count=n,
            status=status,
        )

    # ── 维度计算 ────────────────────────────────────────────────────────

    @staticmethod
    def _compute_quality(evidence: list[Evidence]) -> float:
        """证据质量 → 加权平均 (高质量证据权重更大)。"""
        if not evidence:
            return 0.0
        # 用 quality² 加权 —— 高质量证据的影响力指数增长
        weighted_sum = sum(e.quality * e.quality for e in evidence)
        total_weight = sum(e.quality for e in evidence)
        if total_weight == 0:
            return 0.0
        return min(1.0, weighted_sum / total_weight)

    @staticmethod
    def _compute_consistency(evidence: list[Evidence]) -> float:
        """证据一致性 → consistency_score 均值 + 方差惩罚。"""
        if not evidence:
            return 0.0
        n = len(evidence)
        scores = [e.consistency_score for e in evidence]
        mean = sum(scores) / n
        if n < 2:
            return mean  # 单条证据一致性 = 自身分数
        # 方差惩罚
        variance = sum((s - mean) ** 2 for s in scores) / n
        dispersion_penalty = min(0.3, variance * 0.5)
        return max(0.0, mean - dispersion_penalty)

    def _compute_recency(
        self,
        evidence: list[Evidence],
        now: datetime,
    ) -> float:
        """新近度 → 时间衰减权重 (平均 decay)。"""
        if not evidence:
            return 0.0
        half_life = timedelta(days=self._config.recency_half_life_days)
        weights = []
        for e in evidence:
            age = now - e.timestamp
            # 指数衰减: weight = 0.5 ^ (age / half_life)
            decay = 0.5 ** (age.total_seconds() / half_life.total_seconds())
            weights.append(max(0.01, decay))  # floor 0.01
        # 平均 decay 权重 — 不受 quality 遮蔽
        return sum(weights) / len(weights)

    def _compute_volume(self, n: int) -> float:
        """证据量 → 饱和曲线。边际递减，饱和点可配置。"""
        limit = self._config.saturation_limit
        return min(1.0, n / limit)  # 线性增长到饱和

    def _compute_counter_penalty(self, counterexamples: int) -> float:
        """反证惩罚 → 影响递增但 capped。"""
        if counterexamples <= 0:
            return 1.0  # 无惩罚
        impact = min(
            self._config.counter_impact_max,
            counterexamples * 0.03  # 每个反例降 3%
        )
        return max(0.0, 1.0 - impact)

    @staticmethod
    def _compute_uncertainty(
        quality: float,
        consistency: float,
        n: int,
    ) -> float:
        """不确定性 → 质量 + 一致性 + 证据量 共同决定。"""
        # 高质量 + 高一致性 + 多证据 → 低不确定性
        base = 1.0
        base -= quality * 0.4           # 质量高 → 不确定低
        base -= consistency * 0.30       # 一致高 → 不确定低
        base -= min(0.25, n * 0.02)      # 证据多 → 不确定低 (cap ~12条)
        return max(0.05, min(0.99, base))  # 永不 0 或 1
