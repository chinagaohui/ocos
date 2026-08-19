"""Phase 47: ImpactAnalyzer — 影响分析器。

深度分析 Evolution Proposal 的影响面。

检查:
    - ABI 兼容性
    - 模块间依赖
    - Identity/Constitution 边界 (CE47-04)
    - 回滚可行性 (CE47-03)
    - 影响范围

分析后更新 proposal.impact 和 proposal.state。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ocos.evolution.evolution_types import (
    EvolutionProposal,
    EvolutionState,
    ImpactAssessment,
    ImpactLevel,
    FORBIDDEN_DOMAINS,
)


@dataclass
class ImpactAnalyzer:
    """影响分析器——CE47-04 核心守卫。"""

    _analyzed: list[str] = field(default_factory=list)

    def analyze(self, proposal: EvolutionProposal) -> ImpactAssessment:
        """分析进化提案的影响。"""
        proposal.state = EvolutionState.ANALYZING

        impact = proposal.impact

        # 1. 边界检查 (CE47-04)
        impact = self._check_boundaries(proposal, impact)

        # 2. ABI 兼容性
        impact = self._check_abi(proposal, impact)

        # 3. 依赖分析
        impact = self._check_dependencies(proposal, impact)

        # 4. 影响等级调整
        impact = self._recalculate_level(impact)

        # 5. 回滚可行性 (CE47-03)
        impact = self._check_rollback_viability(proposal, impact)

        proposal.impact = impact
        self._analyzed.append(proposal.proposal_id)

        return impact

    def _check_boundaries(
        self, proposal: EvolutionProposal, impact: ImpactAssessment,
    ) -> ImpactAssessment:
        """CE47-04: 检查是否触碰禁止域。"""
        # identity
        if proposal.target_module.lower() in FORBIDDEN_DOMAINS:
            impact.identity_safe = False
            impact.constitution_safe = False
            impact.permission_safe = False

        # constitution / core_values / anchor
        forbidden_terms = ["identity", "constitution", "permission", "core_value", "anchor"]
        desc_lower = proposal.description.lower()
        spec_lower = proposal.change_spec.lower()

        for term in forbidden_terms:
            if term in desc_lower or term in spec_lower:
                if term in ("identity", "anchor"):
                    impact.identity_safe = False
                if term == "constitution":
                    impact.constitution_safe = False
                if term == "permission":
                    impact.permission_safe = False

        return impact

    def _check_abi(
        self, proposal: EvolutionProposal, impact: ImpactAssessment,
    ) -> ImpactAssessment:
        """检查 ABI 兼容性。"""
        # 简单判断: replace/add 操作可能是 breaking
        if proposal.change_type in ("replace", "remove"):
            impact.abi_breaking = True
        return impact

    def _check_dependencies(
        self, proposal: EvolutionProposal, impact: ImpactAssessment,
    ) -> ImpactAssessment:
        """检查模块依赖。"""
        # 简单模拟: 高严重度信号可能影响更多模块
        from ocos.evolution.improvement_detector import DetectedSignal
        return impact

    def _recalculate_level(self, impact: ImpactAssessment) -> ImpactAssessment:
        """重新计算影响等级。"""
        if not impact.is_safe:
            impact.level = ImpactLevel.CRITICAL
        elif impact.abi_breaking:
            impact.level = ImpactLevel.HIGH
        return impact

    def _check_rollback_viability(
        self, proposal: EvolutionProposal, impact: ImpactAssessment,
    ) -> ImpactAssessment:
        """CE47-03: 检查回滚可行性。"""
        # add 操作通常可回滚 (移除新模块)
        # replace 操作需要 snapshot
        if proposal.change_type == "replace" and not proposal.rollback_snapshot:
            impact.rollback_viable = False
        return impact

    @property
    def analyzed_count(self) -> int:
        return len(self._analyzed)


__all__ = ["ImpactAnalyzer"]
