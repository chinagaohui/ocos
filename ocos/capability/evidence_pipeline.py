"""Phase 37 §5: Evidence Promotion Pipeline — Feedback → Evidence → Belief 链。

§5.4: Evidence 累积多条后才影响 Belief（阻止单次噪声）。

Usage:
    pipeline = EvidencePipeline(belief_system=belief)
    pipeline.process_feedback(cognitive_feedback)
"""

from __future__ import annotations

from typing import Any, Optional

from ocos.contracts.feedback_abi import (
    CognitiveFeedback,
    Evidence,
    FeedbackState,
    EvaluationStatus,
)
from ocos.logging import get_logger

logger = get_logger(__name__)

# 提升门槛 (§5.3)
PROMOTION_MIN_EVIDENCE = 3        # 同类证据至少 3 条
PROMOTION_MIN_OUTCOME_SCORE = 0.7 # 每条 outcome_score > 0.7
BELIEF_MIN_SAMPLES = 5            # §5.4: Evidence 累积 5+ 条才写入 Belief
BELIEF_MIN_CONFIDENCE = 0.6       # §5.4: 置信度 ≥ 0.6 才形成 Belief


class EvidencePipeline:
    """Evidence 累积与 Belief 更新管道。

    链路:
      CognitiveFeedback → Evidence → Evidence Pool → (累积) → Belief

    不直接: CognitiveFeedback → Belief
    """

    def __init__(self, *, belief_system: Any = None):
        self._pool: dict[str, Evidence] = {}  # statement → Evidence
        self._belief = belief_system
        self._feedback_history: list[str] = []  # 最近 feedback_id

    def process_feedback(self, feedback: CognitiveFeedback) -> EvidenceResult:
        """处理一条 CognitiveFeedback。

        1. 检查 evaluation 状态
        2. 检查是否 rejected（直接丢弃）
        3. 生成 Evidence → 加入 Pool
        4. 检查 Pool 是否达到 Belief 门槛

        Returns:
            EvidenceResult with promotion info
        """
        # 检查 evaluation
        if feedback.evaluation.status in (
            EvaluationStatus.REJECTED,
            EvaluationStatus.REJECTED_USER_MISALIGNED,
        ):
            logger.debug("Feedback %s rejected: %s", feedback.feedback_id, feedback.evaluation.status)
            return EvidenceResult(accepted=False, reason="evaluation_rejected")

        # 生成 Evidence statement
        statement = self._make_statement(feedback)
        evidence = Evidence(
            source_feedback_id=feedback.feedback_id,
            statement=statement,
            confidence=feedback.evaluation.score,
            sample_count=1,
        )

        # 加入 Pool（合并同类）
        existing = self._pool.get(statement)
        if existing:
            merged = existing.merge(evidence)
            self._pool[statement] = merged
            evidence = merged
        else:
            self._pool[statement] = evidence

        self._feedback_history.append(feedback.feedback_id)

        # 检查 Pattern Promotion（§5.3）
        promotion = self._check_promotion(statement, evidence)
        if promotion["ready"]:
            feedback_state = FeedbackState.PROMOTED
        elif evidence.sample_count >= BELIEF_MIN_SAMPLES:
            feedback_state = FeedbackState.CONFIRMED
        else:
            feedback_state = FeedbackState.TEMPORARY

        # 检查 Belief 更新（§5.4）
        belief_updated = False
        if evidence.sample_count >= BELIEF_MIN_SAMPLES and evidence.confidence >= BELIEF_MIN_CONFIDENCE:
            belief_updated = self._update_belief(evidence)

        return EvidenceResult(
            accepted=True,
            statement=statement,
            samples=evidence.sample_count,
            confidence=evidence.confidence,
            promotion_ready=promotion["ready"],
            belief_updated=belief_updated,
            new_state=feedback_state,
        )

    def _make_statement(self, fb: CognitiveFeedback) -> str:
        """从 CognitiveFeedback 生成 Evidence statement。"""
        outcome = "success" if fb.actual.success else "failure"
        return (
            f"Capability '{fb.capability_id}' via provider '{fb.provider_id}' "
            f"achieved {outcome} (score={fb.evaluation.score:.2f})"
        )

    def _check_promotion(self, statement: str, evidence: Evidence) -> dict:
        """检查是否应提升为 Pattern。"""
        similar = sum(
            1 for stmt, ev in self._pool.items()
            if ev.confidence >= PROMOTION_MIN_OUTCOME_SCORE
            and self._has_overlap(stmt, statement)
        )
        # 需要同名证据 ≥ PROMOTION_MIN_EVIDENCE + 至少 3 条同类
        return {
            "ready": evidence.sample_count >= PROMOTION_MIN_EVIDENCE
                     and evidence.confidence >= PROMOTION_MIN_OUTCOME_SCORE
                     and similar >= PROMOTION_MIN_EVIDENCE,
            "similar_count": similar,
            "threshold": PROMOTION_MIN_EVIDENCE,
        }

    def _has_overlap(self, stmt_a: str, stmt_b: str) -> bool:
        """检查两个 statement 是否描述同类能力（简单 key word 匹配）。"""
        # 提取 capability_id 进行匹配
        words_a = set(stmt_a.replace("'", " ").split())
        words_b = set(stmt_b.replace("'", " ").split())
        return len(words_a & words_b) >= 3  # 至少 3 个共同词

    def _update_belief(self, evidence: Evidence) -> bool:
        """将 Evidence 提升为 Belief（§5.4）。"""
        if self._belief is None:
            return False
        try:
            self._belief.add(
                statement=evidence.statement,
                confidence=evidence.confidence,
            )
            logger.info("Belief updated: %s (conf=%.2f)", evidence.statement, evidence.confidence)
            return True
        except Exception:
            logger.debug("Belief update failed", exc_info=True)
            return False

    def get_pool_summary(self) -> dict[str, Any]:
        """获取 Evidence Pool 摘要。"""
        return {
            "pool_size": len(self._pool),
            "total_evidence": sum(ev.sample_count for ev in self._pool.values()),
            "promoted": sum(
                1 for stmt, ev in self._pool.items()
                if ev.sample_count >= PROMOTION_MIN_EVIDENCE
            ),
            "feedback_processed": len(self._feedback_history),
        }


class EvidenceResult:
    """一次 Evidence 处理的结果。"""

    def __init__(
        self,
        accepted: bool,
        reason: str = "",
        statement: str = "",
        samples: int = 0,
        confidence: float = 0.0,
        promotion_ready: bool = False,
        belief_updated: bool = False,
        new_state: FeedbackState = FeedbackState.TEMPORARY,
    ):
        self.accepted = accepted
        self.reason = reason
        self.statement = statement
        self.samples = samples
        self.confidence = confidence
        self.promotion_ready = promotion_ready
        self.belief_updated = belief_updated
        self.new_state = new_state

    def __repr__(self) -> str:
        return (
            f"EvidenceResult(accepted={self.accepted}, samples={self.samples}, "
            f"promotion={self.promotion_ready}, belief={self.belief_updated})"
        )
