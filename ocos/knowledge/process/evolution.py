"""
M3 Knowledge Evolution — 知识演进提案 + 审批流程。

EvolutionProposal 定义了知识的变更提议流程，包括：
- 变更类型：EDIT / MERGE / DEPRECATE / SPLIT / ELEVATE
- 提案生命周期：DRAFT → REVIEW → APPROVED → APPLIED / REJECTED
- 审批来源追踪
"""

from __future__ import annotations

import logging
import dataclasses
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from ocos.knowledge.store.lifecycle import KnowledgeLifecycle
from ocos.knowledge.store.ontology import KnowledgeLevel, KnowledgeStatus, KnowledgeUnit
from ocos.knowledge.store.registry import KnowledgeRegistry
from ocos.knowledge.process.validator import KnowledgeValidator, ValidationSeverity
from ocos.knowledge.process.promotion_rules import PromotionRuleEngine

logger = logging.getLogger(__name__)


# ── 提案类型 ──────────────────────────────────────────────────────────


class EvolutionChangeType(str, Enum):
    """知识演进变更类型。"""
    EDIT = "edit"           # 编辑现有知识内容
    MERGE = "merge"         # 合并多个知识单元
    DEPRECATE = "deprecate" # 废弃知识单元
    SPLIT = "split"         # 拆分知识单元
    ELEVATE = "elevate"     # 提升层级


class EvolutionProposalStatus(str, Enum):
    """提案生命周期状态。"""
    DRAFT = "draft"
    REVIEW = "review"
    APPROVED = "approved"
    APPLIED = "applied"
    REJECTED = "rejected"


# ── 提案模型 ──────────────────────────────────────────────────────────


@dataclass(frozen=True)
class EvolutionProposal:
    """
    知识演进提案。

    Attributes:
        proposal_id: 提案唯一标识
        change_type: 变更类型
        target_ids: 目标知识单元 ID 列表
        owner: 发起者
        description: 变更说明
        reason: 变更理由
        new_payload: 变更后的 payload (适用于 EDIT / MERGE / SPLIT)
        new_level: 变更后的层级 (适用于 ELEVATE)
        status: 提案状态
        created_at: 创建时间
        reviewed_at: 审批时间
        reviewed_by: 审批人
        rejection_reason: 拒绝理由
        applied_at: 执行时间
    """
    proposal_id: str
    change_type: EvolutionChangeType
    target_ids: tuple[str, ...]
    owner: str
    description: str
    reason: str
    new_payload: dict[str, Any] | None = None
    new_level: KnowledgeLevel | None = None
    status: EvolutionProposalStatus = EvolutionProposalStatus.DRAFT
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    reviewed_at: datetime | None = None
    reviewed_by: str | None = None
    rejection_reason: str | None = None
    applied_at: datetime | None = None


# ── 演进管理器 ──────────────────────────────────────────────────────────


class EvolutionManager:
    """
    知识演进管理器。

    管理提案的创建、审批和执行。
    提供了提案审批流程，与 KnowledgeLifecycle、PromotionRuleEngine 和
    KnowledgeValidator 协同工作。
    """

    def __init__(
        self,
        registry: KnowledgeRegistry,
        lifecycle: KnowledgeLifecycle,
        validator: KnowledgeValidator,
        promotion: PromotionRuleEngine | None = None,
    ):
        self._registry = registry
        self._lifecycle = lifecycle
        self._validator = validator
        self._promotion = promotion
        self._proposals: dict[str, EvolutionProposal] = {}
        self._next_id: int = 1
        # 签名验证规则：owner 必须是可写权限持有者
        self._approval_required: bool = True

    @property
    def approval_required(self) -> bool:
        return self._approval_required

    def set_approval_required(self, value: bool) -> None:
        """设置是否需要审批 (用于测试环境)。"""
        self._approval_required = value

    # ── 提案创建 ──────────────────────────────────────────────────────

    def create_proposal(
        self,
        change_type: EvolutionChangeType,
        target_ids: list[str],
        owner: str,
        description: str,
        reason: str,
        new_payload: dict[str, Any] | None = None,
        new_level: KnowledgeLevel | None = None,
    ) -> tuple[bool, str | EvolutionProposal]:
        """
        创建知识演进提案。

        Returns:
            (ok, result) 其中 result 为提案对象或错误消息
        """
        # 验证目标存在且有写入权限
        for tid in target_ids:
            entry = self._registry.get(tid, requestor=owner)
            if entry is None:
                logger.warning("create_proposal failed: target %s not found (owner=%s)", tid, owner)
                return False, f"目标知识单元 '{tid}' 不存在或无权访问"
            if not self._registry.check_write(owner, entry.unit.level):
                logger.warning("create_proposal failed: %s no write access to %s", owner, tid)
                return False, f"'{owner}' 对 '{tid}' 没有写入权限"

        # ELEVATE 类型需要 new_level
        if change_type == EvolutionChangeType.ELEVATE and new_level is None:
            logger.warning("create_proposal failed: ELEVATE without new_level")
            return False, "ELEVATE 类型需要指定 new_level"

        proposal = EvolutionProposal(
            proposal_id=f"EP-{self._next_id:04d}",
            change_type=change_type,
            target_ids=tuple(target_ids),
            owner=owner,
            description=description,
            reason=reason,
            new_payload=new_payload,
            new_level=new_level,
        )
        self._proposals[proposal.proposal_id] = proposal
        self._next_id += 1
        logger.info("create_proposal: %s type=%s owner=%s targets=%s",
                    proposal.proposal_id, change_type.value, owner, target_ids)

        # 如果不需要审批，自动进入 REVIEW 状态
        if not self._approval_required:
            return self._auto_approve(proposal)

        return True, proposal

    def _auto_approve(self, proposal: EvolutionProposal) -> tuple[bool, str | EvolutionProposal]:
        """自动审批并执行。"""
        logger.info("_auto_approve: %s", proposal.proposal_id)
        ok, result = self._approve(proposal.proposal_id, proposal.owner)
        if not ok:
            return False, result
        return self._apply(proposal.proposal_id, proposal.owner)

    # ── 审批流程 ──────────────────────────────────────────────────────

    def submit_review(self, proposal_id: str) -> tuple[bool, str]:
        """提交提案进入 REVIEW 状态。"""
        prop = self._proposals.get(proposal_id)
        if prop is None:
            logger.warning("submit_review failed: %s not found", proposal_id)
            return False, f"提案 '{proposal_id}' 不存在"
        if prop.status != EvolutionProposalStatus.DRAFT:
            logger.warning("submit_review failed: %s status=%s (expected DRAFT)",
                          proposal_id, prop.status.value)
            return False, f"提案当前状态为 {prop.status.value}，仅 DRAFT 可提交审核"
        self._proposals[proposal_id] = dataclasses.replace(
            prop, status=EvolutionProposalStatus.REVIEW
        )
        logger.info("submit_review: %s -> REVIEW", proposal_id)
        return True, "已提交审核"

    def approve(self, proposal_id: str, reviewer: str) -> tuple[bool, str]:
        """审批通过提案。"""
        if self._approval_required:
            # 检查审核者是否为 governance 或 proposal.owner
            prop = self._proposals.get(proposal_id)
            if prop is None:
                logger.warning("approve failed: %s not found", proposal_id)
                return False, f"提案 '{proposal_id}' 不存在"
            if reviewer != prop.owner and not self._registry.check_write(reviewer, KnowledgeLevel.PRINCIPLE):
                logger.warning("approve denied: %s not authorized (proposal=%s)", reviewer, proposal_id)
                return False, (
                    f"'{reviewer}' 无审批权限，仅 originator 或 PRINCIPLE 级写入者可审批"
                )
        return self._approve(proposal_id, reviewer)

    def _approve(self, proposal_id: str, reviewer: str) -> tuple[bool, str]:
        """内部审批逻辑。"""
        prop = self._proposals.get(proposal_id)
        if prop is None:
            logger.warning("_approve failed: %s not found", proposal_id)
            return False, f"提案 '{proposal_id}' 不存在"
        if prop.status != EvolutionProposalStatus.REVIEW and self._approval_required:
            logger.warning("_approve failed: %s status=%s (expected REVIEW)",
                          proposal_id, prop.status.value)
            return False, f"提案状态为 {prop.status.value}，仅 REVIEW 可审批"
        if prop.status == EvolutionProposalStatus.DRAFT and not self._approval_required:
            pass  # auto-approve mode 允许从 DRAFT 直接批准

        self._proposals[proposal_id] = dataclasses.replace(
            prop,
            status=EvolutionProposalStatus.APPROVED,
            reviewed_at=datetime.now(timezone.utc),
            reviewed_by=reviewer,
        )
        logger.info("_approve: %s approved by %s", proposal_id, reviewer)
        return True, f"已批准 (by {reviewer})"

    def reject(
        self, proposal_id: str, reviewer: str, reason: str
    ) -> tuple[bool, str]:
        """驳回提案。"""
        prop = self._proposals.get(proposal_id)
        if prop is None:
            logger.warning("reject failed: %s not found", proposal_id)
            return False, f"提案 '{proposal_id}' 不存在"
        if prop.status != EvolutionProposalStatus.REVIEW:
            logger.warning("reject failed: %s status=%s (expected REVIEW)",
                          proposal_id, prop.status.value)
            return False, f"提案状态为 {prop.status.value}，仅 REVIEW 可驳回"
        self._proposals[proposal_id] = dataclasses.replace(
            prop,
            status=EvolutionProposalStatus.REJECTED,
            reviewed_at=datetime.now(timezone.utc),
            reviewed_by=reviewer,
            rejection_reason=reason,
        )
        logger.info("reject: %s rejected by %s reason=%s", proposal_id, reviewer, reason)
        return True, f"已驳回 (by {reviewer}): {reason}"

    # ── 提案执行 ──────────────────────────────────────────────────────

    def apply(self, proposal_id: str, executor: str) -> tuple[bool, str]:
        """执行已批准的提案。"""
        prop = self._proposals.get(proposal_id)
        if prop is None:
            logger.warning("apply failed: %s not found", proposal_id)
            return False, f"提案 '{proposal_id}' 不存在"
        if prop.status != EvolutionProposalStatus.APPROVED:
            logger.warning("apply failed: %s status=%s (expected APPROVED)",
                          proposal_id, prop.status.value)
            return False, f"提案状态为 {prop.status.value}，仅 APPROVED 可执行"
        return self._apply(proposal_id, executor)

    def _apply(self, proposal_id: str, executor: str) -> tuple[bool, str]:
        """内部执行逻辑。"""
        prop = self._proposals.get(proposal_id)
        if prop is None:
            return False, f"提案 '{proposal_id}' 不存在"

        change_type = prop.change_type
        target_ids = list(prop.target_ids)
        logger.info("_apply: %s type=%s executor=%s targets=%s",
                    proposal_id, change_type.value, executor, target_ids)

        try:
            if change_type == EvolutionChangeType.EDIT:
                ok, msg = self._apply_edit(prop)
            elif change_type == EvolutionChangeType.MERGE:
                ok, msg = self._apply_merge(prop)
            elif change_type == EvolutionChangeType.DEPRECATE:
                ok, msg = self._apply_deprecate(prop)
            elif change_type == EvolutionChangeType.SPLIT:
                ok, msg = self._apply_split(prop)
            elif change_type == EvolutionChangeType.ELEVATE:
                ok, msg = self._apply_elevate(prop)
            else:
                logger.error("_apply: unsupported change_type=%s", change_type.value)
                return False, f"不支持的变更类型: {change_type.value}"

            if not ok:
                logger.warning("_apply execution failed: %s msg=%s", proposal_id, msg)
                return False, msg

            self._proposals[proposal_id] = dataclasses.replace(
                prop,
                status=EvolutionProposalStatus.APPLIED,
                applied_at=datetime.now(timezone.utc),
            )
            logger.info("_apply done: %s -> %s", proposal_id, msg)
            return True, f"提案 '{proposal_id}' 已执行: {msg}"

        except Exception as e:
            logger.exception("_apply exception: proposal=%s", proposal_id)
            return False, f"提案执行异常: {e}"

    def _apply_edit(self, prop: EvolutionProposal) -> tuple[bool, str]:
        """执行 EDIT 提案。"""
        if prop.new_payload is None:
            logger.warning("_apply_edit failed: no new_payload (proposal=%s)", prop.proposal_id)
            return False, "EDIT 提案需要 new_payload"
        target_id = prop.target_ids[0]
        entry = self._registry.get(target_id, requestor=prop.owner)
        if entry is None:
            logger.warning("_apply_edit failed: target %s not found", target_id)
            return False, f"目标 '{target_id}' 不存在"
        old_unit = entry.unit

        # 验证新 payload
        new_unit = KnowledgeUnit(
            unit_id=old_unit.unit_id,
            level=old_unit.level,
            status=old_unit.status,
            content=prop.new_payload,
            parent_id=old_unit.parent_id,
        )
        report = self._validator.validate(new_unit)
        if report.has_errors:
            errors = "; ".join(e.message for e in report.errors)
            logger.warning("_apply_edit validation failed: %s errors=%s", target_id, errors)
            return False, f"校验失败: {errors}"

        ok, msg = self._registry.update(
            target_id, prop.owner, content=prop.new_payload
        )
        if not ok:
            logger.warning("_apply_edit update failed: %s msg=%s", target_id, msg)
            return False, f"更新失败: {msg}"

        # 记录版本变更
        self._lifecycle.change_status(
            new_unit.unit_id, old_unit.status, prop.owner,
            reason=f"EDIT proposal applied: {prop.description}",
        )
        logger.info("_apply_edit ok: %s", target_id)
        return True, f"已更新 '{target_id}'"

    def _apply_merge(self, prop: EvolutionProposal) -> tuple[bool, str]:
        """执行 MERGE 提案。"""
        if not prop.new_payload:
            logger.warning("_apply_merge failed: no new_payload (proposal=%s)", prop.proposal_id)
            return False, "MERGE 提案需要 new_payload 作为合并后内容"

        target_ids = list(prop.target_ids)
        if len(target_ids) < 2:
            logger.warning("_apply_merge failed: need >= 2 targets, got %d", len(target_ids))
            return False, "MERGE 至少需要 2 个目标"

        # 收集所有目标，确认存在
        entries = []
        for tid in target_ids:
            entry = self._registry.get(tid, requestor=prop.owner)
            if entry is None:
                logger.warning("_apply_merge failed: target %s not found", tid)
                return False, f"目标 '{tid}' 不存在或无权访问"
            entries.append(entry)

        # 合并后使用第一个目标的层级
        first = entries[0]
        import uuid
        merged_unit = KnowledgeUnit(
            unit_id=uuid.uuid4().hex,
            level=first.unit.level,
            status=KnowledgeStatus.CANDIDATE,
            content=prop.new_payload,
        )

        # 注册合并后的新单元
        ok, msg = self._registry.register(
            merged_unit, owner=prop.owner, scope=first.scope,
        )
        if not ok:
            logger.warning("_apply_merge register failed: %s", msg)
            return False, f"合并注册失败: {msg}"

        # 废弃原目标
        for tid in target_ids:
            entry = self._registry.get(tid, requestor=prop.owner)
            if entry:
                self._lifecycle.change_status(
                    entry.unit.unit_id, KnowledgeStatus.DEPRECATED, prop.owner,
                    reason=f"merged into {merged_unit.unit_id} via {prop.proposal_id}",
                )

        logger.info("_apply_merge ok: merged %d -> %s", len(target_ids), merged_unit.unit_id)
        return True, f"已合并 {len(target_ids)} 个单元为 '{merged_unit.unit_id}'"

    def _apply_deprecate(self, prop: EvolutionProposal) -> tuple[bool, str]:
        """执行 DEPRECATE 提案。"""
        target_id = prop.target_ids[0]
        entry = self._registry.get(target_id, requestor=prop.owner)
        if entry is None:
            logger.warning("_apply_deprecate failed: target %s not found", target_id)
            return False, f"目标 '{target_id}' 不存在"

        ok, msg = self._lifecycle.change_status(
            entry.unit.unit_id,
            KnowledgeStatus.DEPRECATED,
            changed_by=prop.owner,
            reason=prop.reason,
        )
        if not ok:
            logger.warning("_apply_deprecate failed: %s msg=%s", target_id, msg)
            return False, f"废弃失败: {msg}"
        logger.info("_apply_deprecate ok: %s", target_id)
        return True, f"'{target_id}' 已标记为 DEPRECATED"

    def _apply_split(self, prop: EvolutionProposal) -> tuple[bool, str]:
        """执行 SPLIT 提案。"""
        if not prop.new_payload or "parts" not in prop.new_payload:
            logger.warning("_apply_split failed: missing parts in new_payload")
            return False, "SPLIT 提案需要 new_payload['parts'] 列表"

        target_id = prop.target_ids[0]
        entry = self._registry.get(target_id, requestor=prop.owner)
        if entry is None:
            logger.warning("_apply_split failed: target %s not found", target_id)
            return False, f"目标 '{target_id}' 不存在"

        parts: list[dict] = prop.new_payload["parts"]
        if len(parts) < 2:
            logger.warning("_apply_split failed: need >= 2 parts, got %d", len(parts))
            return False, "SPLIT 至少需要 2 个部件"

        import uuid
        split_ids: list[str] = []
        for i, part in enumerate(parts):
            part_unit = KnowledgeUnit(
                unit_id=uuid.uuid4().hex,
                level=entry.unit.level,
                status=KnowledgeStatus.CANDIDATE,
                content=part.get("content", {}),
            )
            ok, msg = self._registry.register(
                part_unit, owner=prop.owner, scope=entry.scope,
            )
            if not ok:
                # 回滚已注册的
                for sid in split_ids:
                    self._registry.remove(sid, prop.owner)
                logger.warning("_apply_split rollback: part %d register failed: %s", i + 1, msg)
                return False, f"拆分部件 {i+1} 注册失败: {msg}"
            split_ids.append(part_unit.unit_id)

        # 废弃原目标
        self._lifecycle.change_status(
            entry.unit.unit_id,
            KnowledgeStatus.DEPRECATED,
            changed_by=prop.owner,
            reason=f"split into {len(parts)} parts via {prop.proposal_id}",
        )

        logger.info("_apply_split ok: %s -> %d parts: %s", target_id, len(parts), split_ids)
        return True, f"已拆分为 {len(parts)} 个单元: {split_ids}"

    def _apply_elevate(self, prop: EvolutionProposal) -> tuple[bool, str]:
        """执行 ELEVATE 提案。"""
        if prop.new_level is None:
            logger.warning("_apply_elevate failed: no new_level")
            return False, "ELEVATE 提案需要指定 new_level"

        target_id = prop.target_ids[0]
        entry = self._registry.get(target_id, requestor=prop.owner)
        if entry is None:
            logger.warning("_apply_elevate failed: target %s not found", target_id)
            return False, f"目标 '{target_id}' 不存在"

        unit = entry.unit
        if self._promotion:
            ok, errors = self._promotion.can_promote(
                unit, prop.new_level, prop.owner
            )
            if not ok:
                logger.warning("_apply_elevate can_promote failed: %s", "; ".join(errors))
                return False, f"提升校验不通过: {'; '.join(errors)}"

            # 创建提升后的新单元
            import uuid
            elevated_unit = KnowledgeUnit(
                unit_id=uuid.uuid4().hex,
                level=prop.new_level,
                status=KnowledgeStatus.CANDIDATE,
                content=unit.content,
                parent_id=unit.unit_id,
            )

            ok, msg = self._registry.register(
                elevated_unit,
                owner=prop.owner,
                scope=entry.scope,
            )
            if not ok:
                logger.warning("_apply_elevate register failed: %s", msg)
                return False, f"提升注册失败: {msg}"
        else:
            logger.error("_apply_elevate failed: no PromotionRuleEngine configured")
            return False, "未配置 PromotionRuleEngine"

        logger.info("_apply_elevate ok: %s -> %s (%s)", target_id, elevated_unit.unit_id, prop.new_level.value)
        return True, f"'{target_id}' 已提升至 {prop.new_level.value}，新建 '{elevated_unit.unit_id}'"

    # ── 查询 ──────────────────────────────────────────────────────────

    def get_proposal(self, proposal_id: str) -> EvolutionProposal | None:
        """获取提案。"""
        return self._proposals.get(proposal_id)

    def list_proposals(
        self,
        owner: str | None = None,
        status: EvolutionProposalStatus | None = None,
        change_type: EvolutionChangeType | None = None,
    ) -> list[EvolutionProposal]:
        """按条件列出提案。"""
        results = list(self._proposals.values())
        if owner:
            results = [p for p in results if p.owner == owner]
        if status:
            results = [p for p in results if p.status == status]
        if change_type:
            results = [p for p in results if p.change_type == change_type]
        filtered = sorted(results, key=lambda p: p.created_at, reverse=True)
        logger.debug("list_proposals: total=%d filtered=%d", len(self._proposals), len(filtered))
        return filtered

    def count_by_status(self) -> dict[str, int]:
        """按状态统计提案数量。"""
        counts: dict[str, int] = {}
        for p in self._proposals.values():
            counts[p.status.value] = counts.get(p.status.value, 0) + 1
        logger.debug("count_by_status: %s", counts)
        return counts
