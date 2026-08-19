"""Phase 24.2-A — SignificanceEvaluator。

四维度评分组合 + 阈值判定 + Gate 决策。

签名:
    evaluator.evaluate(candidate, context) → GateDecision

原则:
    仅对 COMPLETE Candidate 进行评估。
    INCOMPLETE Candidate 直接 FAIL — 不完整的经历不能进入 Episode。
"""

from __future__ import annotations

from typing import Optional

from ocos.memory.experience.models import ExperienceCandidate, ExperienceStatus
from ocos.memory.significance.models import (
    DimensionScore,
    SignificanceScore,
    GateDecision,
    GateVerdict,
)
from ocos.memory.significance.rules import (
    SignificanceConfig,
    score_goal_impact,
    score_prediction_error,
    score_knowledge_change,
    score_future_relevance,
)


class SignificanceEvaluator:
    """四维度 Significance Score 合成 + 门控决策。

    使用示例:
        evaluator = SignificanceEvaluator()
        decision = evaluator.evaluate(candidate, active_goals=["g1"])
        if decision.passed():
            # 准予进入 Episode
            ...
    """

    def __init__(
        self,
        config: Optional[SignificanceConfig] = None,
        active_goals: Optional[list[str]] = None,
    ) -> None:
        self._config = config or SignificanceConfig()
        self._active_goals = active_goals or []
        self._decisions: list[GateDecision] = []

    # ── 公共 API ────────────────────────────────────────────────────────────

    def evaluate(
        self,
        candidate: ExperienceCandidate,
        *,
        active_goals: Optional[list[str]] = None,
        expected_outcome: Optional[dict] = None,
    ) -> GateDecision:
        """对 ExperienceCandidate 执行 Significance Gate 评估。

        Args:
            candidate: 待评估的候选经历
            active_goals: 当前活跃 Goal ID 列表 (覆盖构造器默认值)
            expected_outcome: 预期结果 (用于 prediction_error 计算)

        Returns:
            GateDecision — PASS 或 FAIL
        """
        goals = active_goals if active_goals is not None else self._active_goals

        # 0. 完整性门控 — INCOMPLETE 直接拒绝
        if candidate.status != ExperienceStatus.COMPLETE:
            decision = GateDecision(
                candidate_id=candidate.id,
                verdict=GateVerdict.FAIL,
                score=SignificanceScore(
                    goal_impact=DimensionScore("goal_impact", 0.0, 0.25, ["candidate is INCOMPLETE"]),
                    prediction_error=DimensionScore("prediction_error", 0.0, 0.30, ["candidate is INCOMPLETE"]),
                    knowledge_change=DimensionScore("knowledge_change", 0.0, 0.20, ["candidate is INCOMPLETE"]),
                    future_relevance=DimensionScore("future_relevance", 0.0, 0.25, ["candidate is INCOMPLETE"]),
                ),
                reason="Candidate is INCOMPLETE — cannot evaluate significance",
            )
            self._decisions.append(decision)
            return decision

        # 1. 四维度评分
        gi_score, gi_evidence = score_goal_impact(candidate, goals)
        pe_score, pe_evidence = score_prediction_error(candidate, expected_outcome)
        kc_score, kc_evidence = score_knowledge_change(candidate)
        fr_score, fr_evidence = score_future_relevance(candidate)

        # 2. 合成 SignificanceScore
        significance = SignificanceScore(
            goal_impact=DimensionScore(
                "goal_impact",
                gi_score,
                self._config.goal_impact_weight,
                gi_evidence,
            ),
            prediction_error=DimensionScore(
                "prediction_error",
                pe_score,
                self._config.prediction_error_weight,
                pe_evidence,
            ),
            knowledge_change=DimensionScore(
                "knowledge_change",
                kc_score,
                self._config.knowledge_change_weight,
                kc_evidence,
            ),
            future_relevance=DimensionScore(
                "future_relevance",
                fr_score,
                self._config.future_relevance_weight,
                fr_evidence,
            ),
            threshold=self._config.threshold,
        )

        # 3. 阈值判定
        verdict = (
            GateVerdict.PASS
            if significance.weighted_total >= self._config.threshold
            else GateVerdict.FAIL
        )

        # 4. 生成理由
        reason = self._build_reason(significance, verdict)

        decision = GateDecision(
            candidate_id=candidate.id,
            verdict=verdict,
            score=significance,
            reason=reason,
        )
        self._decisions.append(decision)
        return decision

    # ── 批量评估 ──────────────────────────────────────────────────────────

    def evaluate_all(
        self,
        candidates: list[ExperienceCandidate],
        **kwargs,
    ) -> list[GateDecision]:
        """批量评估。"""
        return [self.evaluate(c, **kwargs) for c in candidates]

    # ── 检索 ──────────────────────────────────────────────────────────────

    def get_passed(self) -> list[GateDecision]:
        """获取所有 PASS 决策。"""
        return [d for d in self._decisions if d.passed()]

    def get_failed(self) -> list[GateDecision]:
        """获取所有 FAIL 决策。"""
        return [d for d in self._decisions if d.failed()]

    def get_by_candidate_id(self, candidate_id: str) -> Optional[GateDecision]:
        """按 candidate ID 检索决策。"""
        for d in self._decisions:
            if d.candidate_id == candidate_id:
                return d
        return None

    def clear(self) -> None:
        """清空历史决策。"""
        self._decisions.clear()

    # ── 内部 ──────────────────────────────────────────────────────────────

    def _build_reason(
        self,
        significance: SignificanceScore,
        verdict: GateVerdict,
    ) -> str:
        """构建人类可读的决策理由。"""
        dims = significance.dimension_summary()
        top_dim = max(dims, key=lambda k: dims[k])

        if verdict == GateVerdict.PASS:
            return (
                f"PASS (score={significance.weighted_total:.3f} >= "
                f"threshold={significance.threshold:.2f}); "
                f"top dimension: {top_dim} ({dims[top_dim]:.3f})"
            )
        else:
            return (
                f"FAIL (score={significance.weighted_total:.3f} < "
                f"threshold={significance.threshold:.2f}); "
                f"top dimension: {top_dim} ({dims[top_dim]:.3f})"
            )
