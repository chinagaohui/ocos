"""Phase 48: CognitiveSignatureEngine — 认知特征引擎。

从交互中学习用户认知特征，构建 User Cognitive Signature。

学习方式:
    - 观察用户选择偏好
    - 观察用户对方案的态度
    - 记录交互风格模式
    - 增量更新置信度

边界 PM48-01: Personalization ≠ Overfitting
    适应用户，但保持通用能力——置信度上限 0.95，永远留不确定性。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ocos.personal_intelligence.pi_types import (
    CognitiveSignature,
    RiskTolerance,
    ExplanationDepth,
    InteractionStyle,
    DomainPriority,
)


@dataclass
class CognitiveSignatureEngine:
    """认知特征引擎——从交互中学习用户是谁。"""

    signature: CognitiveSignature = field(default_factory=CognitiveSignature)

    def observe_risk_choice(
        self, options_with_risk: list[tuple[str, float]], chosen: str,
    ) -> None:
        """观察用户的风险选择。"""
        # 评估选择的风险倾向
        for desc, risk in options_with_risk:
            if desc == chosen:
                if risk < 0.3:
                    # 低风险选择
                    if self.signature.risk_tolerance == RiskTolerance.BOLD:
                        self.signature.risk_tolerance = RiskTolerance.MODERATE
                    elif self.signature.risk_tolerance == RiskTolerance.MODERATE:
                        self.signature.risk_tolerance = RiskTolerance.CONSERVATIVE
                elif risk > 0.7:
                    if self.signature.risk_tolerance == RiskTolerance.CONSERVATIVE:
                        self.signature.risk_tolerance = RiskTolerance.MODERATE
                    elif self.signature.risk_tolerance == RiskTolerance.MODERATE:
                        self.signature.risk_tolerance = RiskTolerance.BOLD
                break

        self.signature.update_confidence(1)

    def observe_explanation_preference(self, depth: ExplanationDepth) -> None:
        """观察用户对解释深度的偏好。"""
        # 滑动平均: 70% 旧 + 30% 新
        if depth != self.signature.explanation_depth:
            self.signature.explanation_depth = depth
        self.signature.update_confidence(1)

    def observe_interaction_style(self, style: InteractionStyle) -> None:
        """观察交互风格。"""
        if style != self.signature.interaction_style:
            self.signature.interaction_style = style
        self.signature.update_confidence(1)

    def observe_domain_interest(
        self, domain: str, interaction_count: int = 1,
    ) -> None:
        """观察用户在特定领域的兴趣。"""
        existing = None
        for dp in self.signature.domain_priorities:
            if dp.domain == domain:
                existing = dp
                break

        if existing:
            existing.observation_count += interaction_count
            existing.confidence = min(0.95, existing.observation_count / (existing.observation_count + 10))
        else:
            self.signature.domain_priorities.append(
                DomainPriority(
                    domain=domain,
                    weight=0.5,
                    confidence=0.1,
                    observation_count=interaction_count,
                )
            )

        self.signature.update_confidence(1)

    def observe_speed_preference(self, speed_over_accuracy: float) -> None:
        """观察速度vs精度偏好。"""
        old = self.signature.speed_over_accuracy
        # 滑动平均
        self.signature.speed_over_accuracy = 0.7 * old + 0.3 * speed_over_accuracy
        self.signature.update_confidence(1)

    def get_personalized_options_count(self) -> int:
        """基于特征推荐方案数量。"""
        base = self.signature.preference_for_options
        if self.signature.risk_tolerance == RiskTolerance.CONSERVATIVE:
            base += 1  # 风险规避者想看更多选择
        if self.signature.speed_over_accuracy > 0.7:
            base = max(2, base - 1)  # 速度快者少选项
        return base

    def get_explanation_style(self) -> dict:
        """获取当前推荐解释风格。"""
        return {
            "depth": self.signature.explanation_depth.value,
            "formality": self.signature.formality,
        }

    @property
    def is_personalized(self) -> bool:
        return self.signature.is_reliable


__all__ = ["CognitiveSignatureEngine"]
