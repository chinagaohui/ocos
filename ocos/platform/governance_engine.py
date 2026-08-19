"""
C3 Governance Engine — 提案审批工作流。

职责：
- EvolutionProposal 全生命周期管理（submit → review → approve/reject/cancel）
- 通过 Event Bus 发射 Governance 事件，供 PolicyEngine / AuditEngine 消费
- 不直接调用下游模块，通过 Event Bus 解耦

依赖：
- ocos.kernel.abi (EventType / Event / SCHEMA_VERSION)
- ocos.events.event_bus (EventBus，可选)
- ocos.platform.audit_engine (AuditEngine，可选，仅用于直接记录审计)

架构定位：
  Governance Engine 是 Governance 层的唯一入口。
  PolicyEngine 通过订阅 GOVERNANCE_APPROVED/REJECTED 事件自动响应。
  AuditEngine 通过订阅 Governance 事件自动生成审计记录。
  GovernanceEngine 本身不知道下游的存在，事件发射即是全部。
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from ocos.kernel.abi import Event, EventType, SCHEMA_VERSION
from ocos.logging import get_logger


logger = get_logger(__name__)


# ── 枚举 ─────────────────────────────────────────────────────────────────────

class ProposalType(str, Enum):
    """提案类型。"""
    POLICY_CHANGE = "policy_change"
    KNOWLEDGE_PROMOTION = "knowledge_promotion"
    SYSTEM_CHANGE = "system_change"


class ProposalStatus(str, Enum):
    """提案状态机。

    合法转换：
        PENDING → UNDER_REVIEW → APPROVED | REJECTED
        PENDING → CANCELLED
        UNDER_REVIEW → CANCELLED
    """
    PENDING = "pending"
    UNDER_REVIEW = "under_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


# ── 数据模型 ─────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class EvolutionProposal:
    """一个治理提案——对系统某一部分的变更请求。"""

    proposal_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    proposal_type: str = ProposalType.POLICY_CHANGE.value
    title: str = ""
    description: str = ""
    status: str = ProposalStatus.PENDING.value
    proposed_by: str = ""
    proposed_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    reviewed_by: str = ""
    reviewed_at: str = ""
    review_comment: str = ""
    target_details: dict[str, Any] = field(default_factory=dict)
    schema_version: str = SCHEMA_VERSION

    def is_terminal(self) -> bool:
        """提案是否已处于终态（已批准/已拒绝/已取消）。"""
        return self.status in (
            ProposalStatus.APPROVED.value,
            ProposalStatus.REJECTED.value,
            ProposalStatus.CANCELLED.value,
        )


# ── 提案状态转换验证 ─────────────────────────────────────────────────────────

# 允许的状态转换映射
_ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    ProposalStatus.PENDING.value: {
        ProposalStatus.UNDER_REVIEW.value,
        ProposalStatus.CANCELLED.value,
    },
    ProposalStatus.UNDER_REVIEW.value: {
        ProposalStatus.APPROVED.value,
        ProposalStatus.REJECTED.value,
        ProposalStatus.CANCELLED.value,
    },
}

# 需要审查者信息的转换
_REVIEW_TRANSITIONS: set[str] = {
    ProposalStatus.APPROVED.value,
    ProposalStatus.REJECTED.value,
}


def _validate_transition(current: str, target: str) -> None:
    """检查状态转换是否合法。"""
    allowed = _ALLOWED_TRANSITIONS.get(current)
    if allowed is None:
        raise ValueError(f"提案当前状态 '{current}' 不允许任何转换（终态）")
    if target not in allowed:
        raise ValueError(
            f"不允许从 '{current}' 转换到 '{target}'。"
            f"允许的目标: {', '.join(sorted(allowed))}"
        )


# ── Governance 引擎 ──────────────────────────────────────────────────────────

class GovernanceEngine:
    """治理引擎：管理提案审批工作流。

    使用方式：
        engine = GovernanceEngine(event_bus=bus)
        pid = engine.submit_proposal(
            proposal_type=ProposalType.POLICY_CHANGE,
            title="拒绝高风险动作",
            description="...",
            proposed_by="admin",
            target_details={...},
        )
        engine.review_proposal(pid, approved=True, reviewer="governor", comment="批准")
    """

    def __init__(
        self,
        event_bus: Any = None,
        audit_engine: Any = None,
    ):
        self._proposals: dict[str, EvolutionProposal] = {}
        self._event_bus = event_bus

        # 将审计引擎设为可选——GovernanceEngine 不依赖 AuditEngine
        self._audit_engine = audit_engine

        logger.debug("GovernanceEngine __init__ completed", component="governance_engine", has_event_bus=event_bus is not None)

    # ── 属性 ────────────────────────────────────────────────────────────────

    @property
    def proposal_count(self) -> int:
        """当前存储的提案总数。"""
        return len(self._proposals)

    # ── 提案操作 ────────────────────────────────────────────────────────────

    def submit_proposal(
        self,
        proposal_type: str = ProposalType.POLICY_CHANGE.value,
        title: str = "",
        description: str = "",
        proposed_by: str = "",
        target_details: Optional[dict[str, Any]] = None,
    ) -> str:
        """提交一个新提案。

        Args:
            proposal_type: 提案类型（ProposalType.value）
            title: 提案标题
            description: 提案描述
            proposed_by: 提交者标识
            target_details: 提案的具体变更详情

        Returns:
            新创建的 proposal_id
        """
        proposal = EvolutionProposal(
            proposal_type=proposal_type,
            title=title or "未命名提案",
            description=description,
            proposed_by=proposed_by or "unknown",
            target_details=dict(target_details or {}),
        )
        self._proposals[proposal.proposal_id] = proposal

        # 发射提案提交事件
        self._emit_governance_event(
            EventType.GOVERNANCE_APPROVAL_REQUESTED,
            {
                "proposal_id": proposal.proposal_id,
                "proposal_type": proposal.proposal_type,
                "title": proposal.title,
                "proposed_by": proposal.proposed_by,
                "target_details": proposal.target_details,
            },
        )

        logger.info("Proposal submitted", component="governance_engine", proposal_id=proposal.proposal_id, proposal_type=proposal_type, title=title, proposed_by=proposed_by)

        return proposal.proposal_id

    def _move_to_review(self, proposal_id: str) -> None:
        """将提案从 PENDING 移至 UNDER_REVIEW。

        若提案已处于 UNDER_REVIEW 则跳过（允许直接 approve/reject）。
        若提案为终态则抛出异常。
        """
        proposal = self._get_proposal_or_raise(proposal_id)
        if proposal.status == ProposalStatus.UNDER_REVIEW.value:
            return
        if proposal.is_terminal():
            raise ValueError(
                f"提案 {proposal_id} 已处于终态 '{proposal.status}'，无法审查"
            )
        self._proposals[proposal_id] = EvolutionProposal(
            proposal_id=proposal.proposal_id,
            proposal_type=proposal.proposal_type,
            title=proposal.title,
            description=proposal.description,
            status=ProposalStatus.UNDER_REVIEW.value,
            proposed_by=proposal.proposed_by,
            proposed_at=proposal.proposed_at,
            reviewed_by="",
            reviewed_at="",
            review_comment="",
            target_details=proposal.target_details,
            schema_version=proposal.schema_version,
        )

    def review_proposal(
        self,
        proposal_id: str,
        approved: bool,
        reviewer: str = "",
        comment: str = "",
    ) -> bool:
        """审查提案并做出审批决定。

        Args:
            proposal_id: 提案 ID
            approved: True 表示批准，False 表示拒绝
            reviewer: 审查者标识
            comment: 审查说明

        Returns:
            True 如果批准，False 如果拒绝

        Raises:
            ValueError: 提案不存在、已处于终态或状态转换非法
        """
        proposal = self._get_proposal_or_raise(proposal_id)

        # 自动推进到审阅中状态
        self._move_to_review(proposal_id)

        target_status = (
            ProposalStatus.APPROVED.value if approved
            else ProposalStatus.REJECTED.value
        )

        # 验证转换合法性
        _validate_transition(ProposalStatus.UNDER_REVIEW.value, target_status)

        now = datetime.now(timezone.utc).isoformat()

        updated = EvolutionProposal(
            proposal_id=proposal.proposal_id,
            proposal_type=proposal.proposal_type,
            title=proposal.title,
            description=proposal.description,
            status=target_status,
            proposed_by=proposal.proposed_by,
            proposed_at=proposal.proposed_at,
            reviewed_by=reviewer or "unknown",
            reviewed_at=now,
            review_comment=comment,
            target_details=proposal.target_details,
            schema_version=proposal.schema_version,
        )
        self._proposals[proposal_id] = updated

        # 发射审批事件
        event_type = (
            EventType.GOVERNANCE_APPROVED if approved
            else EventType.GOVERNANCE_REJECTED
        )

        # 从 target_details 中提取 policy_action（如果有）
        policy_action = proposal.target_details.get("policy_action", "")
        event_payload: dict[str, Any] = {
            "proposal_id": proposal_id,
            "proposal_type": proposal.proposal_type,
            "title": proposal.title,
            "reviewer": reviewer,
            "comment": comment,
            "target_details": proposal.target_details,
        }

        # 对于 POLICY_CHANGE 类型，将 policy_action 和 policy 结构放入顶层
        # 以便 PolicyEngine 的 _on_governance_approved/rejected 直接消费
        if proposal.proposal_type == ProposalType.POLICY_CHANGE.value:
            if approved:
                # 批准时：policy_action = add/enable
                policy_data = proposal.target_details.get("policy", {})
                event_payload["policy_action"] = policy_action or "add"
                event_payload["policy_name"] = policy_data.get("name", "")
                if policy_action == "add":
                    event_payload["policy"] = policy_data
            else:
                # 拒绝时：policy_action = disable/remove
                policy_data = proposal.target_details.get("policy", {})
                event_payload["policy_action"] = policy_action or "disable"
                event_payload["policy_name"] = policy_data.get("name", proposal.title)

        self._emit_governance_event(event_type, event_payload)

        logger.info("Proposal reviewed", component="governance_engine", proposal_id=proposal_id, approved=approved, reviewer=reviewer)

        return approved

    def cancel_proposal(
        self,
        proposal_id: str,
        cancelled_by: str = "",
    ) -> bool:
        """取消一个提案（仅限 PENDING 或 UNDER_REVIEW 状态）。

        Args:
            proposal_id: 提案 ID
            cancelled_by: 取消者标识

        Returns:
            True 取消成功

        Raises:
            ValueError: 提案不存在或不能取消
        """
        proposal = self._get_proposal_or_raise(proposal_id)
        _validate_transition(proposal.status, ProposalStatus.CANCELLED.value)

        now = datetime.now(timezone.utc).isoformat()

        updated = EvolutionProposal(
            proposal_id=proposal.proposal_id,
            proposal_type=proposal.proposal_type,
            title=proposal.title,
            description=proposal.description,
            status=ProposalStatus.CANCELLED.value,
            proposed_by=proposal.proposed_by,
            proposed_at=proposal.proposed_at,
            reviewed_by=cancelled_by or "unknown",
            reviewed_at=now,
            review_comment=f"Cancelled by {cancelled_by or 'unknown'}",
            target_details=proposal.target_details,
            schema_version=proposal.schema_version,
        )
        self._proposals[proposal_id] = updated
        logger.info("Proposal cancelled", component="governance_engine", proposal_id=proposal_id, cancelled_by=cancelled_by)
        return True

    # ── 查询 ─────────────────────────────────────────────────────────────────

    def get_proposal(self, proposal_id: str) -> Optional[EvolutionProposal]:
        """按 ID 获取提案。"""
        return self._proposals.get(proposal_id)

    def list_proposals(
        self,
        status: Optional[str] = None,
        proposal_type: Optional[str] = None,
    ) -> list[EvolutionProposal]:
        """列出提案，支持按状态和类型过滤。

        Args:
            status: ProposalStatus.value 过滤
            proposal_type: ProposalType.value 过滤

        Returns:
            按提交时间降序排列的提案列表
        """
        results: list[EvolutionProposal] = []
        for p in self._proposals.values():
            if status is not None and p.status != status:
                continue
            if proposal_type is not None and p.proposal_type != proposal_type:
                continue
            results.append(p)

        # 按提交时间最新优先
        results.sort(key=lambda p: p.proposed_at, reverse=True)
        return results

    def find_proposal_by_title(self, title: str) -> Optional[EvolutionProposal]:
        """按精确标题查找提案。"""
        for p in self._proposals.values():
            if p.title == title:
                return p
        return None

    # ── 管理 ─────────────────────────────────────────────────────────────────

    def reset(self) -> None:
        """清空所有提案。"""
        logger.info("Resetting governance engine", component="governance_engine")
        self._proposals.clear()

    # ── 内部 ─────────────────────────────────────────────────────────────────

    def _get_proposal_or_raise(self, proposal_id: str) -> EvolutionProposal:
        """获取提案，不存在则抛出 ValueError。"""
        proposal = self._proposals.get(proposal_id)
        if proposal is None:
            logger.error("Proposal not found", component="governance_engine", proposal_id=proposal_id)
            raise ValueError(f"提案不存在: {proposal_id}")
        return proposal

    def _emit_governance_event(
        self, event_type: EventType, payload: dict[str, Any]
    ) -> None:
        """发射 Governance 事件。"""
        if self._event_bus is None:
            return
        event = Event(
            event_type=event_type,
            source="governance_engine",
            payload=payload,
        )
        self._event_bus.publish(event, sync=True)
