"""Phase 48: MetaCognitionEngine — 元认知引擎。

"我为什么这样判断？"

不只是输出方案A，而是:
    - 基于过去20次类似任务
    - 结合当前风险评估
    - 考虑了方案B/C但排除了
    - 用户特征影响了偏好
    - 选择方案A

边界 PM48-02: Meta-cognition ≠ Self-doubt
    解释决策，不陷入分析瘫痪。
    不因为"是否需要重新考虑"而无限循环。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ocos.personal_intelligence.pi_types import (
    DecisionRationale, CognitiveSignature,
)


@dataclass
class MetaCognitionEngine:
    """元认知引擎——解释决策过程。

    记录每个决策的推理链:
        - 面对什么问题
        - 考虑过哪些方案
        - 证据链
        - 过去类似决策
        - 用户特征如何影响
    """

    _rationales: list[DecisionRationale] = field(default_factory=list)
    _counter: int = 0

    def trace_decision(
        self,
        question: str,
        chosen: str,
        alternatives: list[str],
        evidence: list[str],
        past_similar: int = 0,
        confidence: float = 0.5,
        signature: CognitiveSignature | None = None,
        world_context: str = "",
        learnings: str = "",
    ) -> DecisionRationale:
        """记录一次决策的完整推理链。"""
        self._counter += 1
        decision_id = f"dc:{self._counter}"

        sig_influence = (
            f"Risk={signature.risk_tolerance.value}, Speed={signature.speed_over_accuracy:.2f}"
            if signature else "No signature yet"
        )

        rationale = DecisionRationale(
            decision_id=decision_id,
            question=question,
            chosen_option=chosen,
            alternatives_considered=alternatives,
            evidence_chain=evidence,
            past_similar_count=past_similar,
            confidence=confidence,
            learning_from_past=learnings,
            signature_influence=sig_influence,
            world_context=world_context,
        )

        self._rationales.append(rationale)
        # 保持最近 500 条
        if len(self._rationales) > 500:
            self._rationales = self._rationales[-250:]

        return rationale

    def explain_decision(self, decision_id: str) -> str:
        """生成决策说明——"我为什么这样判断？" """
        for r in self._rationales:
            if r.decision_id == decision_id:
                return self._format_rationale(r)
        return f"No decision found: {decision_id}"

    def _format_rationale(self, r: DecisionRationale) -> str:
        parts = [
            f"Decision {r.decision_id}: \"{r.question}\"",
            f"Chosen: {r.chosen_option}",
        ]
        if r.alternatives_considered:
            parts.append(f"Alternatives considered: {', '.join(r.alternatives_considered[:5])}")
        if r.evidence_chain:
            parts.append(f"Evidence: {' → '.join(r.evidence_chain[:5])}")
        if r.past_similar_count > 0:
            parts.append(f"Past similar decisions: {r.past_similar_count}")
        if r.learning_from_past:
            parts.append(f"Learning from past: {r.learning_from_past}")
        if r.signature_influence:
            parts.append(f"User signature influence: {r.signature_influence}")
        parts.append(f"Confidence: {r.confidence:.2f}")
        return "\n".join(parts)

    def similar_decisions(self, question_keyword: str, limit: int = 5) -> list[DecisionRationale]:
        """查找类似决策。"""
        keyword_lower = question_keyword.lower()
        matches = [
            r for r in self._rationales
            if keyword_lower in r.question.lower()
            or keyword_lower in r.chosen_option.lower()
        ]
        return matches[-limit:]

    def average_confidence(self) -> float:
        if not self._rationales:
            return 0.0
        return sum(r.confidence for r in self._rationales) / len(self._rationales)

    @property
    def total_decisions(self) -> int:
        return len(self._rationales)

    @property
    def recent_insights(self) -> list[str]:
        """从最近的决策中提取的洞见。"""
        if not self._rationales:
            return []
        recent = self._rationales[-20:]
        insights = []
        for r in recent:
            if r.learning_from_past:
                insights.append(r.learning_from_past)
        return list(dict.fromkeys(insights))  # deduplicate, keep order


__all__ = ["MetaCognitionEngine"]
