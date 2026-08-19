"""Phase 47: ApprovalEngine — 进化审批引擎。

治理层审批。复用 Phase 44 Extension Governance 的审批模式。

审批流程:
    1. 检查沙箱通过
    2. 检查影响分析 (is_boundary_safe)
    3. 检查审批链
    4. 批准/拒绝

边界 CE47-02: Proposal ≠ Execution — 只有通过审批链的提案才能进入迁移。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from ocos.evolution.evolution_types import (
    EvolutionProposal,
    EvolutionState,
    ImpactLevel,
)


class ApprovalVerdict(Enum):
    APPROVED = "approved"
    REJECTED = "rejected"
    PENDING_REVIEW = "pending_review"


@dataclass
class ApprovalRecord:
    """审批记录。"""
    proposal_id: str = ""
    verdict: ApprovalVerdict = ApprovalVerdict.PENDING_REVIEW
    reason: str = ""
    tick: int = 0
    reviewer: str = "governance"


@dataclass
class ApprovalEngine:
    """进化审批引擎。

    审批链检查:
        1. 沙箱必须通过
        2. 边界必须安全 (CE47-04)
        3. 影响等级决定审批严格度
        4. 审批链完成 → 写入 approval_record
    """

    _records: list[ApprovalRecord] = field(default_factory=list)

    def evaluate(self, proposal: EvolutionProposal, tick_id: int) -> ApprovalVerdict:
        """评估进化提案是否可以通过。"""

        # Gate 1: 沙箱通过
        if not proposal.sandbox_passed:
            self._record(
                proposal.proposal_id, ApprovalVerdict.REJECTED,
                "Sandbox not passed", tick_id,
            )
            proposal.state = EvolutionState.REJECTED
            return ApprovalVerdict.REJECTED

        # Gate 2: 边界安全 (CE47-04)
        if not proposal.is_boundary_safe:
            violations = proposal.impact.boundary_violations
            self._record(
                proposal.proposal_id, ApprovalVerdict.REJECTED,
                f"Boundary violation: {violations}", tick_id,
            )
            proposal.state = EvolutionState.REJECTED
            return ApprovalVerdict.REJECTED

        # Gate 3: 影响等级检查
        if proposal.impact.level == ImpactLevel.CRITICAL:
            self._record(
                proposal.proposal_id, ApprovalVerdict.REJECTED,
                "CRITICAL impact requires manual review", tick_id,
            )
            proposal.state = EvolutionState.REJECTED
            return ApprovalVerdict.REJECTED

        if proposal.impact.level == ImpactLevel.HIGH:
            # HIGH impact 需要额外的审批链
            if not proposal.governance_approved:
                self._record(
                    proposal.proposal_id, ApprovalVerdict.PENDING_REVIEW,
                    "HIGH impact: requires governance chain approval", tick_id,
                )
                return ApprovalVerdict.PENDING_REVIEW

        # Gate 4: CHANGE TYPE 合法性
        if proposal.change_type not in ("add", "modify", "optimize", "replace"):
            self._record(
                proposal.proposal_id, ApprovalVerdict.REJECTED,
                f"Invalid change_type: {proposal.change_type}", tick_id,
            )
            proposal.state = EvolutionState.REJECTED
            return ApprovalVerdict.REJECTED

        # Gate 5 (U5.2): 安全预检通过 → 一律转人工批准（PENDING_REVIEW）
        # 老高硬约束：Evolution Proposal → Manual Approval → Decision → Authorized Apply
        # 禁止 Cognition→自动批准→自动进化；Capability ≠ Authority, Proposal ≠ Decision
        proposal.state = EvolutionState.PENDING_REVIEW
        self._record(
            proposal.proposal_id, ApprovalVerdict.PENDING_REVIEW,
            "U5.2: 安全预检通过，等待人工批准", tick_id,
        )
        return ApprovalVerdict.PENDING_REVIEW

    def manual_approve(self, proposal, approver: str, tick_id: int = 0) -> ApprovalVerdict:
        """U5.2: 人工批准（唯一 APPROVED 路径——Manual Approval 保留人为权威边界）。

        仅当提案处于 PENDING_REVIEW 且通过安全预检时才可批准。
        """
        from ocos.opentale_bridge.ocos_activation import activate
        activate("I5_evolution_approval")
        if proposal.state != EvolutionState.PENDING_REVIEW:
            self._record(proposal.proposal_id, ApprovalVerdict.REJECTED,
                         f"非待审状态无法批准: {proposal.state}", tick_id)
            return ApprovalVerdict.REJECTED
        if not proposal.sandbox_passed or not proposal.is_boundary_safe:
            self._record(proposal.proposal_id, ApprovalVerdict.REJECTED,
                         "安全预检未通过，禁止人工批准", tick_id)
            return ApprovalVerdict.REJECTED
        if not approver or approver.strip() == "":
            self._record(proposal.proposal_id, ApprovalVerdict.REJECTED,
                         "批准人必须显式指定（不可匿名批准）", tick_id)
            return ApprovalVerdict.REJECTED
        proposal.state = EvolutionState.APPROVED
        proposal.governance_approved = True
        proposal.approved_by = f"manual:{approver}"

        self._record(
            proposal.proposal_id, ApprovalVerdict.APPROVED,
            f"U5.2 人工批准 by {approver}", tick_id,
        )
        return ApprovalVerdict.APPROVED

    def _record(
        self, proposal_id: str, verdict: ApprovalVerdict,
        reason: str, tick: int,
    ) -> None:
        self._records.append(ApprovalRecord(
            proposal_id=proposal_id, verdict=verdict, reason=reason, tick=tick,
        ))

    @property
    def recent_approvals(self) -> list[ApprovalRecord]:
        return self._records[-20:]


__all__ = ["ApprovalVerdict", "ApprovalRecord", "ApprovalEngine"]
