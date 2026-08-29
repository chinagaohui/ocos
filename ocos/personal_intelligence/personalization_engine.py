"""Phase 48: PersonalizationEngine — 个性化引擎。

让 OCOS 的输出适配特定用户，而非通用输出。

基于 CognitiveSignature 进行:
    - 输出风格适配
    - 选项数量适配
    - 风险偏好适配
    - 解释深度适配
    - 领域优先级适配

边界 PM48-01: Personalization ≠ Overfitting
    适配用户，但保持通用能力。
    置信度不足时不强制适配。
    永远保留非个性化回退。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ocos.personal_intelligence.pi_types import (
    RiskTolerance,
    ExplanationDepth,
    InteractionStyle,
    CognitiveSignature,
)
from ocos.personal_intelligence.cognitive_signature import CognitiveSignatureEngine


@dataclass
class PersonalizationEngine:
    """个性化引擎——PM48-01 守卫。

    不是"记住用户喜欢什么"，而是
    "理解用户是谁，并以此为参照调整输出"。
    """

    signature_engine: CognitiveSignatureEngine = field(
        default_factory=CognitiveSignatureEngine,
    )

    def personalize_response(
        self, content: str, context: str = "",
    ) -> str:
        """个性化输出内容。"""
        sig = self.signature_engine.signature

        prefix = ""
        suffix = ""

        if sig.interaction_style == InteractionStyle.FORMAL:
            # Formal: 结构化前缀（GAP-P2-4: pass → 确定性中文映射）
            prefix = "结构化总结：\n\n"
            suffix = "\n\n如需进一步探讨，请随时告知。"
        elif sig.interaction_style == InteractionStyle.COLLABORATIVE:
            prefix = "Let me think through this with you:\n\n"
        elif sig.interaction_style == InteractionStyle.SOCRATIC:
            suffix = "\n\nWhat do you think about this approach?"
        elif sig.interaction_style == InteractionStyle.DIRECT:
            # Direct — no changes
            pass

        return f"{prefix}{content}{suffix}"

    def personalize_options(
        self, options: list[str],
    ) -> list[str]:
        """个性化方案列表——排序和裁剪。"""
        sig = self.signature_engine.signature

        if not sig.is_reliable:
            # 特征不可靠 → 不强制适配
            return options[:]

        # 根据选项数量偏好裁剪
        max_options = sig.preference_for_options
        if len(options) > max_options:
            options = options[:max_options]

        # 基于风险偏好排序（GAP-P2-4: BOLD pass → 反转，高回报在前）
        if sig.risk_tolerance == RiskTolerance.CONSERVATIVE:
            # 保守用户 — 已知方案在前（原顺序即低风险优先）
            pass
        elif sig.risk_tolerance == RiskTolerance.BOLD:
            # 冒险用户 — 反转顺序，高回报方案在前
            options = list(reversed(options))

        return options

    def personalize_explanation(
        self, short: str, medium: str, detailed: str,
    ) -> str:
        """基于用户偏好的解释深度选择。"""
        sig = self.signature_engine.signature

        if not sig.is_reliable:
            return medium  # 默认中等

        match sig.explanation_depth:
            case ExplanationDepth.MINIMAL:
                return short
            case ExplanationDepth.SUMMARY:
                return medium
            case ExplanationDepth.DETAILED:
                return detailed
            case ExplanationDepth.PEDAGOGICAL:
                return f"{detailed}\n\n---\nTo learn more about why this works:\n1. ...\n2. ..."
            case _:
                return medium

    def personalize_risk_assessment(
        self, risk_level: float, recommendation: str,
    ) -> str:
        """基于用户风险偏好调整风险评估表达。"""
        sig = self.signature_engine.signature

        if risk_level < 0.3 and sig.risk_tolerance == RiskTolerance.CONSERVATIVE:
            return f"[Low Risk — Safe Choice] {recommendation}"
        elif risk_level > 0.7 and sig.risk_tolerance == RiskTolerance.CONSERVATIVE:
            return f"[⚠ High Risk — Consider Alternatives] {recommendation}"
        elif risk_level > 0.7 and sig.risk_tolerance == RiskTolerance.BOLD:
            return f"[High Risk / High Reward] {recommendation}"
        return recommendation

    @property
    def is_ready(self) -> bool:
        """个性化引擎是否准备好——需要足够的用户数据。"""
        return self.signature_engine.is_personalized


__all__ = ["PersonalizationEngine"]
