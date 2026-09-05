"""Phase 37: Outcome Evaluator — 五维评估引擎。

Freeze §2: 对 CognitiveFeedback 执行加权多维度评估。

五维:
  Success (0.35) — 目标是否完成
  Quality (0.25) — 结果质量
  Efficiency (0.20) — 时间/资源效率
  Reliability (0.10) — 历史稳定性
  User Alignment (0.10) — 符合用户意图（最高优先级 veto）

§2.3: Alignment < 0.3 → rejected, 不论总分。
"""

from __future__ import annotations

from typing import Any, Optional

from ocos.contracts.feedback_abi import (
    CognitiveFeedback,
    OutcomeEvaluation,
    EvaluationStatus,
    USER_ALIGNMENT_REJECT_THRESHOLD,
)
from ocos.logging import get_logger

logger = get_logger(__name__)

# 五维权重 (§2.1)
WEIGHTS = {
    "success": 0.35,
    "quality": 0.25,
    "efficiency": 0.20,
    "reliability": 0.10,
    "alignment": 0.10,
}


class OutcomeEvaluator:
    """五维执行结果评估器。

    Usage:
        evaluator = OutcomeEvaluator(experience_memory=cem)
        evaluation = evaluator.evaluate(feedback)

    评估流程:
      1. 检查 User Alignment (veto)
      2. 计算五维加权分
      3. 查询 CapabilityExperienceMemory 补充 Reliability
      4. 返回 OutcomeEvaluation (frozen)
    """

    VERSION = "0.1.0"  # §1.4 evaluator_version

    def __init__(self, *, experience_memory: Any = None):
        self._experience = experience_memory

    def evaluate(self, feedback: CognitiveFeedback) -> OutcomeEvaluation:
        """对一条 CognitiveFeedback 执行五维评估。

        Args:
            feedback: 已通过 Validator 的认知反馈

        Returns:
            OutcomeEvaluation (总是 frozen, accepted 或 rejected)
        """
        actual = feedback.actual

        # ── Step 1: User Alignment Veto (§2.3) ──
        if actual.user_alignment < USER_ALIGNMENT_REJECT_THRESHOLD:
            return OutcomeEvaluation(
                score=0.0,
                status=EvaluationStatus.REJECTED_USER_MISALIGNED,
                reason=f"User alignment {actual.user_alignment:.2f} < {USER_ALIGNMENT_REJECT_THRESHOLD}",
                a_score=actual.user_alignment,
            )

        # ── Step 2: 五维计算 ──
        s_score = 1.0 if actual.success else 0.0          # Success
        q_score = actual.quality_score                      # Quality
        e_score = self._efficiency_score(actual.duration_ms, feedback.expected.estimated_duration_ms)
        r_score = self._reliability_score(feedback.capability_id, feedback.provider_id)
        a_score = actual.user_alignment                     # Alignment

        total = (
            WEIGHTS["success"] * s_score
            + WEIGHTS["quality"] * q_score
            + WEIGHTS["efficiency"] * e_score
            + WEIGHTS["reliability"] * r_score
            + WEIGHTS["alignment"] * a_score
        )

        return OutcomeEvaluation(
            score=round(total, 4),
            status=EvaluationStatus.ACCEPTED,
            reason="",
            s_score=s_score,
            q_score=q_score,
            e_score=e_score,
            r_score=r_score,
            a_score=a_score,
        )

    def _efficiency_score(self, actual_ms: float, estimated_ms: float) -> float:
        """效率评分：实际耗时 vs 预估耗时。

        规则:
          - 实际 <= 预估: score=1.0
          - 实际 > 预估: score = estimated / actual (linear decay)
          - 预估为 0 时（无预估），默认返回 0.5
        """
        if estimated_ms <= 0:
            return 0.5
        if actual_ms <= estimated_ms:
            return 1.0
        ratio = estimated_ms / actual_ms
        return max(0.0, min(1.0, ratio))

    def _reliability_score(self, capability_id: str, provider_id: str) -> float:
        """从 CapabilityExperienceMemory 查询历史可靠性。

        如果无历史数据（冷启动），返回中性值 0.5。
        """
        if self._experience is None:
            return 0.5
        try:
            stats = self._experience.get_stats(capability_id, provider_id)
            # S2.14 (白皮书 P2): get_stats 返回键为 total（原查 count
            # 恒不存在 → 即使有历史 reliability 恒 0.5 兜底）
            if stats and stats.get("total", 0) > 0:
                return stats.get("success_rate", 0.5)
        except Exception:
            logger.debug(
                "reliability lookup failed: %s/%s", capability_id, provider_id,
                exc_info=True,
            )
        return 0.5


def evaluate_feedback(
    feedback: CognitiveFeedback,
    *,
    experience_memory: Any = None,
) -> OutcomeEvaluation:
    """便捷函数：评估一条 CognitiveFeedback。

    相当于 `OutcomeEvaluator.evaluate()` 的单次调用。
    """
    evaluator = OutcomeEvaluator(experience_memory=experience_memory)
    return evaluator.evaluate(feedback)
