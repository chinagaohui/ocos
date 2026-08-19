"""Phase 47: EvolutionProposer — 进化提案生成器。

将检测信号转化为结构化 EvolutionProposal。

边界 CE47-02: Proposal ≠ Execution
    提案生成后必须经过 Analysis → Sandbox → Approval 链路。
    不能直接执行。

禁止域 (CE47-04):
    - identity
    - constitution
    - permission_model
    - core_values
    - anchor
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ocos.evolution.evolution_types import (
    EvolutionProposal,
    EvolutionState,
    EvolutionTrigger,
    EvolutionDomain,
    FORBIDDEN_DOMAINS,
    ImpactAssessment,
)
from ocos.evolution.improvement_detector import DetectedSignal


@dataclass
class EvolutionProposer:
    """进化提案生成器。

    信号 → 提案。不执行。
    """

    _proposals: list[EvolutionProposal] = field(default_factory=list)
    _counter: int = 0

    def propose(
        self, signal: DetectedSignal, description: str = "",
    ) -> EvolutionProposal:
        """根据检测信号生成进化提案。"""
        self._counter += 1
        proposal_id = f"evol:{signal.source_tick}:{self._counter}"

        # 根据信号类型确定领域
        domain = self._map_domain(signal.trigger)

        # 边界检查: 不允许进入禁止域
        if domain.value in FORBIDDEN_DOMAINS:
            domain = EvolutionDomain.PARAMETER  # 降级为参数调整

        # 构建影响评估
        impact = self._build_initial_impact(domain, signal)

        # 构建提案
        proposal = EvolutionProposal(
            proposal_id=proposal_id,
            trigger=signal.trigger,
            source_tick=signal.source_tick,
            domain=domain,
            description=description or signal.description,
            rationale=self._build_rationale(signal),
            evidence=[signal.description],
            target_module=signal.source_module,
            change_type=self._map_change_type(signal.trigger),
            change_spec=f"Adapt {signal.source_module} to resolve: {signal.description[:100]}",
            state=EvolutionState.DRAFTING,
            impact=impact,
        )

        self._proposals.append(proposal)
        return proposal

    def _map_domain(self, trigger: EvolutionTrigger) -> EvolutionDomain:
        mapping = {
            EvolutionTrigger.HEALTH_ALERT: EvolutionDomain.PARAMETER,
            EvolutionTrigger.EXPERIENCE_PATTERN: EvolutionDomain.LEARNING_STRATEGY,
            EvolutionTrigger.PERFORMANCE_DEGRADATION: EvolutionDomain.CAPABILITY,
            EvolutionTrigger.CAPABILITY_GAP: EvolutionDomain.CAPABILITY,
            EvolutionTrigger.DECISION_CONSISTENCY_DRIFT: EvolutionDomain.ATTENTION_POLICY,
            EvolutionTrigger.WORLD_MODEL_CONFLICT: EvolutionDomain.KNOWLEDGE_STRUCTURE,
            EvolutionTrigger.MANUAL_PROPOSAL: EvolutionDomain.PARAMETER,
        }
        return mapping.get(trigger, EvolutionDomain.PARAMETER)

    def _build_rationale(self, signal: DetectedSignal) -> str:
        return (
            f"Signal from {signal.source_module}: {signal.metric_name}={signal.metric_value:.2f} "
            f"(threshold={signal.threshold:.2f}, severity={signal.severity:.2f}). "
            f"Trigger: {signal.trigger.value}."
        )

    def _build_initial_impact(self, domain: EvolutionDomain, signal: DetectedSignal) -> ImpactAssessment:
        from ocos.evolution.evolution_types import ImpactLevel
        level = ImpactLevel.LOW
        if signal.severity > 0.8:
            level = ImpactLevel.HIGH
        elif signal.severity > 0.5:
            level = ImpactLevel.MODERATE

        return ImpactAssessment(
            domain=domain,
            level=level,
            affected_modules=[signal.source_module],
            abi_breaking=False,
            identity_safe=True,
            constitution_safe=True,
            permission_safe=True,
            rollback_viable=True,
        )

    def _map_change_type(self, trigger: EvolutionTrigger) -> str:
        mapping = {
            EvolutionTrigger.HEALTH_ALERT: "optimize",
            EvolutionTrigger.EXPERIENCE_PATTERN: "modify",
            EvolutionTrigger.PERFORMANCE_DEGRADATION: "optimize",
            EvolutionTrigger.CAPABILITY_GAP: "add",
            EvolutionTrigger.DECISION_CONSISTENCY_DRIFT: "modify",
            EvolutionTrigger.WORLD_MODEL_CONFLICT: "modify",
            EvolutionTrigger.MANUAL_PROPOSAL: "modify",
        }
        return mapping.get(trigger, "modify")

    @property
    def pending_proposals(self) -> list[EvolutionProposal]:
        return [
            p for p in self._proposals
            if p.state in (EvolutionState.DRAFTING, EvolutionState.ANALYZING,
                           EvolutionState.SANDBOXING, EvolutionState.APPROVED)
        ]

    @property
    def history(self) -> list[EvolutionProposal]:
        return self._proposals


__all__ = ["EvolutionProposer"]
