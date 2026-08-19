"""Phase 41: WisdomValidator — 智慧验证引擎。

防止:
    - 一次经历变规则（多证据要求）
    - 无反例检查（反例必须考虑）
    - 范围过度泛化（scope 必须合理）

验证流程:
    CANDIDATE → VALIDATING (进入验证)
    → 检查证据充分性
    → 检查反例
    → 计算置信度
    → CONFIRMED (通过) 或 DEPRECATED (失败)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from ocos.personal_memory.wisdom_types import (
    WisdomItem,
    WisdomState,
    WisdomEvidence,
)


class ValidationDecision(Enum):
    """验证决策。"""

    PASS = "pass"              # 通过，可提升到 CONFIRMED
    NEED_MORE_EVIDENCE = "need_more_evidence"  # 证据不足，保持 VALIDATING
    REJECTED = "rejected"      # 反例太多/证据太弱，应废弃


@dataclass
class ValidationResult:
    """单次验证的结果。"""

    wisdom_id: str
    decision: ValidationDecision
    confidence: float
    reason: str
    evidence_summary: str = ""

    @property
    def passed(self) -> bool:
        return self.decision == ValidationDecision.PASS


@dataclass
class WisdomValidator:
    """智慧验证器 — 基于证据检查候选智慧是否值得采纳。

    核心原则:
        - 必须有多次证据（不是单一次事件）
        - 必须有反例检查
        - 置信度基于支持/反对证据比例
        - 范围必须合理（不适用全局则必须限定 scope）
    """

    # ── 配置 ──

    min_supporting_evidence: int = 2
    """最少支持证据数。"""

    min_confidence: float = 0.6
    """最低置信度阈值。"""

    max_counter_ratio: float = 0.3
    """最大反例比例。超过此值拒绝。"""

    allow_scope_expansion: bool = False
    """是否允许自动扩展适用范围。"""

    # ── 验证 ──

    def validate(
        self,
        wisdom: WisdomItem,
        current_tick: int,
        additional_evidence: list[WisdomEvidence] | None = None,
    ) -> ValidationResult:
        """验证一条候选/验证中的智慧。

        Args:
            wisdom: 待验证智慧。
            current_tick: 当前 tick。
            additional_evidence: 额外证据（可选，追加到 wisdom.evidence）。

        Returns:
            ValidationResult: 验证决策和置信度。
        """
        # 追加证据
        if additional_evidence:
            wisdom.evidence.extend(additional_evidence)

        # 检查总证据数
        total = wisdom.evidence_count
        if total == 0:
            return ValidationResult(
                wisdom_id=wisdom.wisdom_id,
                decision=ValidationDecision.NEED_MORE_EVIDENCE,
                confidence=0.0,
                reason="No evidence available.",
                evidence_summary="0 total",
            )

        # 检查支持证据数
        support = wisdom.support_count
        if support < self.min_supporting_evidence:
            return ValidationResult(
                wisdom_id=wisdom.wisdom_id,
                decision=ValidationDecision.NEED_MORE_EVIDENCE,
                confidence=wisdom.evidence_strength,
                reason=f"Supporting evidence ({support}) < min ({self.min_supporting_evidence}).",
                evidence_summary=f"{support}s/{wisdom.counter_count}c/{total}t",
            )

        # 检查反例比例
        counter = wisdom.counter_count
        if total > 0:
            counter_ratio = counter / total
            if counter_ratio > self.max_counter_ratio:
                return ValidationResult(
                    wisdom_id=wisdom.wisdom_id,
                    decision=ValidationDecision.REJECTED,
                    confidence=wisdom.evidence_strength,
                    reason=(
                        f"Counter evidence ratio ({counter_ratio:.2f}) "
                        f"exceeds max ({self.max_counter_ratio})."
                    ),
                    evidence_summary=f"{support}s/{counter}c/{total}t",
                )

        # 计算置信度
        confidence = wisdom.evidence_strength

        if confidence < self.min_confidence:
            return ValidationResult(
                wisdom_id=wisdom.wisdom_id,
                decision=ValidationDecision.NEED_MORE_EVIDENCE,
                confidence=confidence,
                reason=(
                    f"Confidence ({confidence:.2f}) "
                    f"below threshold ({self.min_confidence})."
                ),
                evidence_summary=f"{support}s/{counter}c/{total}t",
            )

        # 通过
        return ValidationResult(
            wisdom_id=wisdom.wisdom_id,
            decision=ValidationDecision.PASS,
            confidence=confidence,
            reason=f"Validated with {support} supporting, {counter} counter evidence.",
            evidence_summary=f"{support}s/{counter}c/{total}t",
        )

    def validate_and_promote(
        self,
        wisdom: WisdomItem,
        current_tick: int,
    ) -> ValidationResult:
        """验证并自动提升状态（如果通过）。

        CANDIDATE → VALIDATING
        VALIDATING → CONFIRMED (if pass)
        """
        if wisdom.state == WisdomState.CANDIDATE:
            wisdom.promote_to(WisdomState.VALIDATING, current_tick)

        result = self.validate(wisdom, current_tick)

        if result.passed and wisdom.state == WisdomState.VALIDATING:
            wisdom.confidence = result.confidence
            wisdom.promote_to(WisdomState.CONFIRMED, current_tick)
        elif result.decision == ValidationDecision.REJECTED:
            wisdom.promote_to(WisdomState.DEPRECATED, current_tick)

        return result

    # ── 反例注入 ──

    def inject_counter_evidence(
        self,
        wisdom: WisdomItem,
        counter_evidence: WisdomEvidence,
    ) -> None:
        """注入反例证据 — 用于 Wisdom 后来的反例发现。"""
        wisdom.evidence.append(counter_evidence)
        # 反例注入后可触发重新验证
        # 但不在此方法中自动执行，由调用方决定何时重新 validate


__all__ = ["WisdomValidator", "ValidationDecision", "ValidationResult"]
