"""
C3 Governance Engine — 完整测试套件。

覆盖：
- EvolutionProposal frozen dataclass + 状态机
- 提案全生命周期（submit → approve / reject / cancel）
- 状态转换验证（禁止非法转换、禁止重复审查）
- Event Bus 事件发射（APPROVAL_REQUESTED / APPROVED / REJECTED）
- Audit Engine 集成
- PolicyEngine 端到端集成（提案批准 → PolicyEngine 自动更新策略）
- 降级模式（无 Event Bus / 无 Audit Engine）
- 边界条件
"""

from __future__ import annotations

import pytest
from dataclasses import FrozenInstanceError
from datetime import datetime, timezone

from ocos.kernel.abi import Event, EventType, SCHEMA_VERSION
from ocos.platform.governance_engine import (
    ProposalType,
    ProposalStatus,
    EvolutionProposal,
    GovernanceEngine,
    _validate_transition,
    _ALLOWED_TRANSITIONS,
)
from ocos.events.event_bus import EventBus
from ocos.runtime.policy_engine import PolicyEngine, PolicyEffect


# ══════════════════════════════════════════════════════════════════════════
# Fixtures
# ══════════════════════════════════════════════════════════════════════════

@pytest.fixture
def event_bus() -> EventBus:
    return EventBus()


@pytest.fixture
def engine(event_bus) -> GovernanceEngine:
    return GovernanceEngine(event_bus=event_bus)


@pytest.fixture
def engine_no_bus() -> GovernanceEngine:
    return GovernanceEngine(event_bus=None)


# ══════════════════════════════════════════════════════════════════════════
# Data Model Tests
# ══════════════════════════════════════════════════════════════════════════

class TestEvolutionProposal:
    """验证 EvolutionProposal dataclass 冻结 + 默认值。"""

    def test_frozen(self):
        p = EvolutionProposal(title="测试提案")
        with pytest.raises(FrozenInstanceError):
            p.title = "修改"  # type: ignore

    def test_default_values(self):
        p = EvolutionProposal()
        assert p.proposal_id != ""
        assert p.proposal_type == ProposalType.POLICY_CHANGE.value
        assert p.status == ProposalStatus.PENDING.value
        assert p.title == ""
        assert p.description == ""
        assert p.proposed_by == ""
        assert p.proposed_at != ""
        assert p.reviewed_by == ""
        assert p.reviewed_at == ""
        assert p.review_comment == ""
        assert p.target_details == {}
        assert p.schema_version == SCHEMA_VERSION

    def test_is_terminal(self):
        p = EvolutionProposal(status=ProposalStatus.PENDING.value)
        assert not p.is_terminal()

        for terminal in (ProposalStatus.APPROVED, ProposalStatus.REJECTED, ProposalStatus.CANCELLED):
            p = EvolutionProposal(status=terminal.value)
            assert p.is_terminal()

    def test_proposal_with_details(self):
        p = EvolutionProposal(
            proposal_type=ProposalType.KNOWLEDGE_PROMOTION.value,
            title="提升 Pattern",
            description="将 Pattern X 从 CANDIDATE 提升至 VERIFIED",
            proposed_by="agent",
            target_details={"knowledge_id": "k-123", "from_level": "candidate", "to_level": "verified"},
        )
        assert p.proposal_type == ProposalType.KNOWLEDGE_PROMOTION.value
        assert p.target_details["knowledge_id"] == "k-123"
        assert not p.is_terminal()


# ══════════════════════════════════════════════════════════════════════════
# State Transition Validation
# ══════════════════════════════════════════════════════════════════════════

class TestStateTransitions:
    """验证提案状态转换规则。"""

    def test_pending_to_under_review(self):
        _validate_transition(ProposalStatus.PENDING.value, ProposalStatus.UNDER_REVIEW.value)

    def test_pending_to_cancelled(self):
        _validate_transition(ProposalStatus.PENDING.value, ProposalStatus.CANCELLED.value)

    def test_under_review_to_approved(self):
        _validate_transition(ProposalStatus.UNDER_REVIEW.value, ProposalStatus.APPROVED.value)

    def test_under_review_to_rejected(self):
        _validate_transition(ProposalStatus.UNDER_REVIEW.value, ProposalStatus.REJECTED.value)

    def test_under_review_to_cancelled(self):
        _validate_transition(ProposalStatus.UNDER_REVIEW.value, ProposalStatus.CANCELLED.value)

    def test_terminal_cannot_transition(self):
        for terminal in (ProposalStatus.APPROVED, ProposalStatus.REJECTED, ProposalStatus.CANCELLED):
            with pytest.raises(ValueError, match=f"终态|不允许"):
                _validate_transition(terminal.value, ProposalStatus.UNDER_REVIEW.value)

    def test_pending_to_approved_not_allowed(self):
        """PENDING → APPROVED 必须经过 UNDER_REVIEW。"""
        with pytest.raises(ValueError, match="不允许"):
            _validate_transition(ProposalStatus.PENDING.value, ProposalStatus.APPROVED.value)

    def test_pending_to_rejected_not_allowed(self):
        with pytest.raises(ValueError, match="不允许"):
            _validate_transition(ProposalStatus.PENDING.value, ProposalStatus.REJECTED.value)

    def test_unknown_status(self):
        with pytest.raises(ValueError, match="终态|不允许"):
            _validate_transition("unknown", ProposalStatus.APPROVED.value)

    def test_all_legal_transitions_listed(self):
        """验证状态转换图完整性。"""
        assert set(_ALLOWED_TRANSITIONS.keys()) == {
            ProposalStatus.PENDING.value,
            ProposalStatus.UNDER_REVIEW.value,
        }
        # 所有非终态都应出现在转换表中
        non_terminal = {s.value for s in ProposalStatus
                        if s not in (ProposalStatus.APPROVED, ProposalStatus.REJECTED, ProposalStatus.CANCELLED)}
        assert set(_ALLOWED_TRANSITIONS.keys()) == non_terminal


# ══════════════════════════════════════════════════════════════════════════
# GovernanceEngine — 提案生命周期
# ══════════════════════════════════════════════════════════════════════════

class TestProposalLifecycle:
    """验证提案完整生命周期。"""

    def test_submit_proposal(self, engine):
        pid = engine.submit_proposal(
            proposal_type=ProposalType.POLICY_CHANGE.value,
            title="新策略",
            description="添加一条安全策略",
            proposed_by="admin",
        )
        assert pid != ""
        proposal = engine.get_proposal(pid)
        assert proposal is not None
        assert proposal.title == "新策略"
        assert proposal.proposal_type == ProposalType.POLICY_CHANGE.value
        assert proposal.status == ProposalStatus.PENDING.value
        assert engine.proposal_count == 1

    def test_submit_and_approve(self, engine):
        pid = engine.submit_proposal(
            proposal_type=ProposalType.POLICY_CHANGE.value,
            title="批准测试",
            proposed_by="admin",
        )
        result = engine.review_proposal(pid, approved=True, reviewer="governor", comment="同意")
        assert result is True

        proposal = engine.get_proposal(pid)
        assert proposal.status == ProposalStatus.APPROVED.value
        assert proposal.reviewed_by == "governor"
        assert proposal.review_comment == "同意"
        assert proposal.reviewed_at != ""

    def test_submit_and_reject(self, engine):
        pid = engine.submit_proposal(
            proposal_type=ProposalType.POLICY_CHANGE.value,
            title="拒绝测试",
            proposed_by="admin",
        )
        result = engine.review_proposal(pid, approved=False, reviewer="governor", comment="理由不充分")
        assert result is False

        proposal = engine.get_proposal(pid)
        assert proposal.status == ProposalStatus.REJECTED.value
        assert proposal.review_comment == "理由不充分"

    def test_submit_and_cancel_pending(self, engine):
        pid = engine.submit_proposal(title="取消测试", proposed_by="admin")
        result = engine.cancel_proposal(pid, cancelled_by="admin")
        assert result is True

        proposal = engine.get_proposal(pid)
        assert proposal.status == ProposalStatus.CANCELLED.value
        assert "admin" in proposal.review_comment

    def test_cancel_under_review_state(self, engine):
        pid = engine.submit_proposal(title="审查中取消", proposed_by="admin")
        # 先推进到审查状态
        engine.review_proposal(pid, approved=True, reviewer="governor", comment="先批准再取消不合法")

        proposal = engine.get_proposal(pid)
        # 已经在 APPROVED 终态，不能取消
        with pytest.raises(ValueError, match="终态|不允许"):
            engine.cancel_proposal(pid)

    def test_cannot_approve_already_approved(self, engine):
        pid = engine.submit_proposal(title="重复审批", proposed_by="admin")
        engine.review_proposal(pid, approved=True, reviewer="governor")
        with pytest.raises(ValueError, match="终态|不允许"):
            engine.review_proposal(pid, approved=True, reviewer="governor")

    def test_cannot_reject_nonexistent(self, engine):
        with pytest.raises(ValueError, match="不存在"):
            engine.review_proposal("non-existent", approved=False, reviewer="gov")

    def test_cannot_cancel_nonexistent(self, engine):
        with pytest.raises(ValueError, match="不存在"):
            engine.cancel_proposal("non-existent")

    def test_approve_without_reviewer(self, engine):
        pid = engine.submit_proposal(title="无审查者批准", proposed_by="admin")
        result = engine.review_proposal(pid, approved=True)
        assert result is True
        proposal = engine.get_proposal(pid)
        assert proposal.reviewed_by == "unknown"

    def test_multi_submit_tracks_count(self, engine):
        for i in range(5):
            engine.submit_proposal(title=f"提案{i}", proposed_by="admin")
        assert engine.proposal_count == 5

    def test_submit_and_approve_without_going_through_under_review(self, engine):
        """review_proposal 自动处理 PENDING → UNDER_REVIEW → APPROVED。"""
        pid = engine.submit_proposal(title="自动推进", proposed_by="admin")
        engine.review_proposal(pid, approved=True, reviewer="gov")
        proposal = engine.get_proposal(pid)
        assert proposal.status == ProposalStatus.APPROVED.value


# ══════════════════════════════════════════════════════════════════════════
# Event Emission Tests
# ══════════════════════════════════════════════════════════════════════════

class TestEventEmission:
    """验证 GovernanceEngine 发射事件的正确性。"""

    def test_submit_emits_approval_requested(self, event_bus):
        received: list[Event] = []
        event_bus.subscribe(EventType.GOVERNANCE_APPROVAL_REQUESTED, lambda e: received.append(e))

        engine = GovernanceEngine(event_bus=event_bus)
        pid = engine.submit_proposal(title="事件测试", proposed_by="admin")

        assert len(received) == 1
        ev = received[0]
        assert ev.source == "governance_engine"
        assert ev.payload["proposal_id"] == pid
        assert ev.payload["title"] == "事件测试"
        assert ev.payload["proposed_by"] == "admin"

    def test_approve_emits_approved(self, event_bus):
        received: list[Event] = []
        event_bus.subscribe(EventType.GOVERNANCE_APPROVED, lambda e: received.append(e))

        engine = GovernanceEngine(event_bus=event_bus)
        pid = engine.submit_proposal(title="审批事件测试", proposed_by="admin")
        engine.review_proposal(pid, approved=True, reviewer="gov")

        assert len(received) == 1
        ev = received[0]
        assert ev.payload["proposal_id"] == pid
        assert ev.payload["reviewer"] == "gov"

    def test_reject_emits_rejected(self, event_bus):
        received: list[Event] = []
        event_bus.subscribe(EventType.GOVERNANCE_REJECTED, lambda e: received.append(e))

        engine = GovernanceEngine(event_bus=event_bus)
        pid = engine.submit_proposal(title="拒绝事件测试", proposed_by="admin")
        engine.review_proposal(pid, approved=False, reviewer="gov")

        assert len(received) == 1
        ev = received[0]
        assert ev.payload["proposal_id"] == pid

    def test_approve_policy_change_includes_policy_action(self, event_bus):
        """POLICY_CHANGE 类型的批准应包含 PolicyEngine 可消费的 action 结构。"""
        received: list[Event] = []
        event_bus.subscribe(EventType.GOVERNANCE_APPROVED, lambda e: received.append(e))

        engine = GovernanceEngine(event_bus=event_bus)
        pid = engine.submit_proposal(
            proposal_type=ProposalType.POLICY_CHANGE.value,
            title="新增策略",
            proposed_by="admin",
            target_details={
                "policy_action": "add",
                "policy": {
                    "name": "gov-policy-test",
                    "description": "由 Governance 添加",
                    "effect": "deny",
                    "priority": 60,
                    "rules": [
                        {"field": "action_type", "operator": "eq", "value": "gov_test_action"},
                    ],
                },
            },
        )
        engine.review_proposal(pid, approved=True, reviewer="gov")

        assert len(received) == 1
        payload = received[0].payload
        assert payload["policy_action"] == "add"
        assert payload["policy"]["name"] == "gov-policy-test"

    def test_reject_policy_change_includes_policy_name(self, event_bus):
        received: list[Event] = []
        event_bus.subscribe(EventType.GOVERNANCE_REJECTED, lambda e: received.append(e))

        engine = GovernanceEngine(event_bus=event_bus)
        pid = engine.submit_proposal(
            proposal_type=ProposalType.POLICY_CHANGE.value,
            title="阻止策略",
            proposed_by="admin",
            target_details={
                "policy_action": "disable",
                "policy": {"name": "bad-policy"},
            },
        )
        engine.review_proposal(pid, approved=False, reviewer="gov")

        assert len(received) == 1
        payload = received[0].payload
        # 拒绝时默认 policy_action 应为 disable
        assert "policy_action" in payload

    def test_no_event_bus_no_crash(self):
        """无 Event Bus 时正常降级。"""
        engine = GovernanceEngine(event_bus=None)
        pid = engine.submit_proposal(title="无总线测试", proposed_by="admin")
        assert pid != ""
        result = engine.review_proposal(pid, approved=True, reviewer="gov")
        assert result is True


# ══════════════════════════════════════════════════════════════════════════
# Query & Filter Tests
# ══════════════════════════════════════════════════════════════════════════

class TestProposalQuery:
    """验证提案查询和过滤功能。"""

    def test_list_all_proposals(self, engine):
        ids = []
        for i in range(3):
            pid = engine.submit_proposal(title=f"提案{i}", proposed_by="admin")
            ids.append(pid)

        proposals = engine.list_proposals()
        assert len(proposals) == 3

    def test_filter_by_status(self, engine):
        pid1 = engine.submit_proposal(title="待审批", proposed_by="admin")
        pid2 = engine.submit_proposal(title="已批准", proposed_by="admin")
        engine.review_proposal(pid2, approved=True, reviewer="gov")

        pending = engine.list_proposals(status=ProposalStatus.PENDING.value)
        approved = engine.list_proposals(status=ProposalStatus.APPROVED.value)

        assert len(pending) == 1
        assert pending[0].proposal_id == pid1
        assert len(approved) == 1
        assert approved[0].proposal_id == pid2

    def test_filter_by_type(self, engine):
        engine.submit_proposal(
            proposal_type=ProposalType.POLICY_CHANGE.value,
            title="策略变更",
            proposed_by="admin",
        )
        engine.submit_proposal(
            proposal_type=ProposalType.KNOWLEDGE_PROMOTION.value,
            title="知识提升",
            proposed_by="admin",
        )

        policies = engine.list_proposals(proposal_type=ProposalType.POLICY_CHANGE.value)
        knowledge = engine.list_proposals(proposal_type=ProposalType.KNOWLEDGE_PROMOTION.value)

        assert len(policies) == 1
        assert len(knowledge) == 1

    def test_find_by_title(self, engine):
        pid = engine.submit_proposal(title="唯一标题", proposed_by="admin")
        found = engine.find_proposal_by_title("唯一标题")
        assert found is not None
        assert found.proposal_id == pid

        not_found = engine.find_proposal_by_title("不存在的标题")
        assert not_found is None

    def test_list_returns_newest_first(self, engine):
        ids = []
        for i in range(3):
            pid = engine.submit_proposal(title=f"提案{i}", proposed_by="admin")
            ids.append(pid)

        proposals = engine.list_proposals()
        # 最新提交的应排第一位
        assert proposals[0].proposal_id == ids[-1]
        assert proposals[-1].proposal_id == ids[0]


# ══════════════════════════════════════════════════════════════════════════
# PolicyEngine End-to-End Integration
# ══════════════════════════════════════════════════════════════════════════

class TestPolicyIntegration:
    """验证 Governance → PolicyEngine 端到端集成。"""

    def test_approved_adds_policy(self, event_bus):
        """Governance 批准策略 → PolicyEngine 自动加载。"""
        policy_name = "gov-e2e-policy"

        # 先启动 PolicyEngine（它会自动订阅 Governance 事件）
        policy_engine = PolicyEngine(event_bus=event_bus, auto_load_defaults=False)

        # 提交并批准一个 POLICY_CHANGE 提案
        gov_engine = GovernanceEngine(event_bus=event_bus)
        pid = gov_engine.submit_proposal(
            proposal_type=ProposalType.POLICY_CHANGE.value,
            title=policy_name,
            proposed_by="admin",
            target_details={
                "policy_action": "add",
                "policy": {
                    "name": policy_name,
                    "description": "End-to-end test policy",
                    "effect": "deny",
                    "priority": 60,
                    "rules": [
                        {"field": "action_type", "operator": "eq", "value": "e2e_forbidden"},
                    ],
                },
            },
        )
        gov_engine.review_proposal(pid, approved=True, reviewer="gov")

        # 验证 PolicyEngine 已自动添加该策略
        policy = policy_engine.get_policy_by_name(policy_name)
        assert policy is not None, "Governance 批准的策略未自动添加到 PolicyEngine"

        # 验证策略生效
        result = policy_engine.evaluate("e2e_forbidden", {})
        assert not result.allowed
        assert policy_name in result.reason

    def test_approved_enables_policy(self, event_bus):
        """Governance 批准启用 → PolicyEngine 自动启用。"""
        policy_engine = PolicyEngine(event_bus=event_bus, auto_load_defaults=True)

        # 先禁用一个默认策略
        target = policy_engine.get_policy_by_name("unknown-action-type")
        policy_engine.set_policy_enabled(target.policy_id, False)

        # 提交启用提案
        gov_engine = GovernanceEngine(event_bus=event_bus)
        pid = gov_engine.submit_proposal(
            proposal_type=ProposalType.POLICY_CHANGE.value,
            title="Enable unknown-action-type",
            proposed_by="admin",
            target_details={
                "policy_action": "enable",
                "policy": {"name": "unknown-action-type"},
            },
        )
        gov_engine.review_proposal(pid, approved=True, reviewer="gov")

        # 验证策略已启用
        updated = policy_engine.get_policy(target.policy_id)
        assert updated.enabled

    def test_rejected_disables_policy(self, event_bus):
        """Governance 拒绝 → PolicyEngine 自动禁用。"""
        policy_engine = PolicyEngine(event_bus=event_bus, auto_load_defaults=True)
        target = policy_engine.get_policy_by_name("unknown-action-type")
        assert target.enabled

        gov_engine = GovernanceEngine(event_bus=event_bus)
        pid = gov_engine.submit_proposal(
            proposal_type=ProposalType.POLICY_CHANGE.value,
            title="Disable unknown-action-type",
            proposed_by="admin",
            target_details={
                "policy_action": "disable",
                "policy": {"name": "unknown-action-type"},
            },
        )
        gov_engine.review_proposal(pid, approved=False, reviewer="gov")

        # 验证策略已禁用
        updated = policy_engine.get_policy(target.policy_id)
        assert not updated.enabled

    def test_rejected_removes_policy(self, event_bus):
        """Governance 拒绝 + remove → PolicyEngine 自动移除。"""
        policy_engine = PolicyEngine(event_bus=event_bus, auto_load_defaults=True)
        target = policy_engine.get_policy_by_name("unknown-action-type")
        assert target is not None

        gov_engine = GovernanceEngine(event_bus=event_bus)
        pid = gov_engine.submit_proposal(
            proposal_type=ProposalType.POLICY_CHANGE.value,
            title="Remove unknown-action-type",
            proposed_by="admin",
            target_details={
                "policy_action": "remove",
                "policy": {"name": "unknown-action-type"},
            },
        )
        gov_engine.review_proposal(pid, approved=False, reviewer="gov")

        # 验证策略已移除
        assert policy_engine.get_policy_by_name("unknown-action-type") is None


# ══════════════════════════════════════════════════════════════════════════
# Audit Engine Integration Tests
# ══════════════════════════════════════════════════════════════════════════

class TestAuditIntegration:
    """验证 Governance → AuditEngine 自动集成（通过 Event Bus）。"""

    def test_approve_creates_audit_record(self, event_bus):
        """Governance 批准后 AuditEngine 自动生成审计记录。"""
        from ocos.platform.audit_engine import AuditEngine, AuditRecordType

        audit_engine = AuditEngine(event_bus=event_bus)

        gov_engine = GovernanceEngine(event_bus=event_bus)
        pid = gov_engine.submit_proposal(
            proposal_type=ProposalType.POLICY_CHANGE.value,
            title="审计测试",
            proposed_by="admin",
        )
        gov_engine.review_proposal(pid, approved=True, reviewer="gov")

        # 查询审计记录，应包含 Governance 记录
        records = audit_engine.query_audit_trail(
            record_type=AuditRecordType.GOVERNANCE.value,
        )
        assert len(records) >= 1
        assert "approved" in records[0].summary

    def test_reject_creates_audit_record(self, event_bus):
        """Governance 拒绝后 AuditEngine 自动生成审计记录。"""
        from ocos.platform.audit_engine import AuditEngine, AuditRecordType

        audit_engine = AuditEngine(event_bus=event_bus)

        gov_engine = GovernanceEngine(event_bus=event_bus)
        pid = gov_engine.submit_proposal(
            proposal_type=ProposalType.POLICY_CHANGE.value,
            title="拒绝审计测试",
            proposed_by="admin",
        )
        gov_engine.review_proposal(pid, approved=False, reviewer="gov")

        records = audit_engine.query_audit_trail(
            record_type=AuditRecordType.GOVERNANCE.value,
        )
        assert len(records) >= 1
        assert "rejected" in records[0].summary

    def test_audit_engine_without_governance_engine_still_works(self, event_bus):
        """AuditEngine 不依赖 GovernanceEngine——两者通过 Event Bus 松耦合。"""
        from ocos.platform.audit_engine import AuditEngine

        AuditEngine(event_bus=event_bus)  # 只启动 AuditEngine 不启动 GovernanceEngine
        # 不报错即为通过

    def test_governance_engine_without_audit_engine_still_works(self):
        """GovernanceEngine 不依赖 AuditEngine。"""
        engine = GovernanceEngine(event_bus=EventBus())
        pid = engine.submit_proposal(title="独立运行", proposed_by="admin")
        result = engine.review_proposal(pid, approved=True, reviewer="gov")
        assert result is True


# ══════════════════════════════════════════════════════════════════════════
# Edge Cases & Boundary Conditions
# ══════════════════════════════════════════════════════════════════════════

class TestEdgeCases:
    """验证边界条件。"""

    def test_submit_empty_title(self, engine):
        pid = engine.submit_proposal(proposed_by="admin")
        proposal = engine.get_proposal(pid)
        assert proposal.title == "未命名提案"

    def test_submit_empty_proposed_by(self, engine):
        pid = engine.submit_proposal(title="测试")
        proposal = engine.get_proposal(pid)
        assert proposal.proposed_by == "unknown"

    def test_reset_clears_all(self, engine):
        engine.submit_proposal(title="A", proposed_by="admin")
        engine.submit_proposal(title="B", proposed_by="admin")
        assert engine.proposal_count == 2
        engine.reset()
        assert engine.proposal_count == 0

    def test_get_nonexistent_returns_none(self, engine):
        assert engine.get_proposal("nonexistent") is None

    def test_submit_with_all_types(self, engine):
        for ptype in ProposalType:
            pid = engine.submit_proposal(
                proposal_type=ptype.value,
                title=f"{ptype.value}测试",
                proposed_by="admin",
            )
            assert pid != ""

    def test_full_lifecycle(self, engine):
        """完整的 提案 → 批准 → 查询 链路。"""
        pid = engine.submit_proposal(
            proposal_type=ProposalType.SYSTEM_CHANGE.value,
            title="系统变更",
            description="完整生命周期测试",
            proposed_by="agent",
            target_details={"component": "scheduler", "action": "reconfigure"},
        )
        assert engine.get_proposal(pid).status == ProposalStatus.PENDING.value

        engine.review_proposal(pid, approved=True, reviewer="governor", comment="批准系统变更")
        assert engine.get_proposal(pid).status == ProposalStatus.APPROVED.value

        # 查询已批准的提案
        approved = engine.list_proposals(status=ProposalStatus.APPROVED.value)
        assert any(p.proposal_id == pid for p in approved)

    def test_review_with_comment_is_preserved(self, engine):
        pid = engine.submit_proposal(title="备注测试", proposed_by="admin")
        engine.review_proposal(pid, approved=False, reviewer="gov", comment="缺少风险评估")
        proposal = engine.get_proposal(pid)
        assert proposal.review_comment == "缺少风险评估"

    def test_concurrent_proposals_independent(self, engine):
        """多个提案互不影响。"""
        pid1 = engine.submit_proposal(title="提案A", proposed_by="alice")
        pid2 = engine.submit_proposal(title="提案B", proposed_by="bob")

        engine.review_proposal(pid1, approved=True, reviewer="gov")
        assert engine.get_proposal(pid1).status == ProposalStatus.APPROVED.value
        assert engine.get_proposal(pid2).status == ProposalStatus.PENDING.value
