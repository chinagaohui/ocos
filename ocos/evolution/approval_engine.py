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
from enum import Enum as enum_Enum

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

    ③ 受约束自主（2026-08-20，老高授权）：低风险域进化可自动批准（auto:governed），
    高风险/权威域强制人工（manual），永禁域拒绝（FORBIDDEN）。Authority 边界：
      Capability ≠ Authority / Proposal ≠ Decision / 自动批准 ≠ 无边界自主。
    """

    # 可自主域（低风险内部优化；受约束条件见 _auto_eligible）
    AUTO_GOVERNED_DOMAINS = ("parameter", "connection", "adapter", "knowledge")
    # 强制人工域（能力/策略/扩展——影响认知行为或能力面）
    MANUAL_DOMAINS = ("capability", "attention", "learning", "extension")
    # 永远禁止（对齐 FORBIDDEN_DOMAINS）
    FORBIDDEN_DOMAINS = ("identity", "constitution", "permission_model", "core_values", "anchor")

    _records: list[ApprovalRecord] = field(default_factory=list)

    def _auto_eligible(self, proposal) -> tuple[bool, str]:
        """受约束自主判定：全部满足才可自动批准（否则人工/拒绝）。"""
        domain = str(getattr(proposal, "domain", "") or "")
        if isinstance(domain, enum_Enum):
            domain = domain.value
        impact = getattr(proposal, "impact", None)
        _lv = getattr(impact, "level", "") if impact else ""
        level = _lv.value if isinstance(_lv, enum_Enum) else str(_lv or "")
        ch = proposal.change_type
        # 永禁域 → 拒绝（非人工）
        if domain in self.FORBIDDEN_DOMAINS:
            return False, f"FORBIDDEN domain: {domain}"
        # 强制人工域 → 人工
        if domain in self.MANUAL_DOMAINS:
            return False, f"MANUAL domain: {domain}"
        # 条件：自主域 + 低影响 + 受控变更 + 沙箱/边界/可回滚
        if domain not in self.AUTO_GOVERNED_DOMAINS:
            return False, f"非自主域: {domain}"
        if level not in ("negligible", "low"):
            return False, f"影响等级过高: {level}"
        if ch not in ("optimize", "add"):
            return False, f"变更类型受控: {ch}"
        if not proposal.sandbox_passed:
            return False, "sandbox 未通过"
        if not proposal.is_boundary_safe:
            return False, "边界不安全"
        if not getattr(impact, "rollback_viable", False):
            return False, "不可回滚（自主进化必须可回滚）"
        return True, "受约束自主条件满足"

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

        # Gate 5 (③ 受约束自主, 2026-08-20)：安全预检通过 →
        #   低风险自主域（parameter/connection/adapter/knowledge + LOW + optimize/add
        #   + sandbox + 边界安全 + 可回滚）→ 自动批准（auto:governed）
        #   否则 → PENDING_REVIEW（人工）；永禁域已在 Gate 2 前拒绝
        auto_ok, reason = self._auto_eligible(proposal)
        if auto_ok:
            proposal.state = EvolutionState.APPROVED
            proposal.governance_approved = True
            proposal.approved_by = "auto:governed"
            self._record(
                proposal.proposal_id, ApprovalVerdict.APPROVED,
                f"③ 受约束自主批准: {reason}", tick_id,
            )
            return ApprovalVerdict.APPROVED
        if reason.startswith("FORBIDDEN"):
            proposal.state = EvolutionState.REJECTED
            self._record(proposal.proposal_id, ApprovalVerdict.REJECTED, reason, tick_id)
            return ApprovalVerdict.REJECTED
        # 非自主/高影响/不可回滚 → 人工
        proposal.state = EvolutionState.PENDING_REVIEW
        self._record(
            proposal.proposal_id, ApprovalVerdict.PENDING_REVIEW,
            f"等待人工批准: {reason}", tick_id,
        )
        return ApprovalVerdict.PENDING_REVIEW

    def manual_approve(self, proposal, approver: str, tick_id: int = 0) -> ApprovalVerdict:
        """U5.2: 人工批准（唯一 APPROVED 路径——Manual Approval 保留人为权威边界）。

        仅当提案处于 PENDING_REVIEW 且通过安全预检时才可批准。
        """
        # U5.2 修正（2026-08-19）：不依赖 opentale_bridge 激活设施（import 规则）；
        # I5 激活观测改由调用方（CLI/外部入口）负责
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
