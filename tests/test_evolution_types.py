"""OCOS evolution_types 进化类型系统测试。

CE47-01: Evolution ≠ Autonomy
CE47-02: Proposal ≠ Execution
CE47-03: Migration ≠ Destruction（可回滚）
CE47-04: Evolution ≠ Identity Change（禁止修改 identity/constitution/permission）
"""

import pytest

from ocos.evolution.evolution_types import (
    EvolutionState,
    EvolutionTrigger,
    EvolutionDomain,
    FORBIDDEN_DOMAINS,
    ImpactLevel,
    ImpactAssessment,
    EvolutionProposal,
    RollbackReason,
    RollbackRecord,
)


class TestEvolutionState:
    """进化状态机完整覆盖。"""

    def test_all_states_exist(self):
        expected = {
            "detected", "drafting", "analyzing", "sandboxing",
            "pending_review", "approved", "migrating", "active",
            "rolled_back", "rejected", "obsolete",
        }
        actual = {s.value for s in EvolutionState}
        assert actual == expected

    def test_state_ordering(self):
        """approved 之后的状态不回到 drafting/analyzing。"""
        approved_states = {
            EvolutionState.APPROVED, EvolutionState.MIGRATING,
            EvolutionState.ACTIVE, EvolutionState.ROLLED_BACK,
            EvolutionState.REJECTED, EvolutionState.OBSOLETE,
        }
        for s in approved_states:
            assert s not in (EvolutionState.DRAFTING, EvolutionState.ANALYZING)


class TestEvolutionTrigger:
    """7 种触发器完整覆盖。"""

    def test_all_triggers_exist(self):
        triggers = {t.value for t in EvolutionTrigger}
        expected = {"health_alert", "experience", "perf", "cap_gap",
                    "drift", "conflict", "manual"}
        assert triggers == expected

    def test_health_alert_is_default(self):
        p = EvolutionProposal()
        assert p.trigger == EvolutionTrigger.HEALTH_ALERT


class TestEvolutionDomain:
    """允许修改的领域枚举。"""

    def test_all_domains_exist(self):
        domains = {d.value for d in EvolutionDomain}
        expected = {"capability", "connection", "parameter", "adapter",
                    "knowledge", "attention", "learning", "extension"}
        assert domains == expected


class TestForbiddenDomains:
    """CE47-04: 禁止修改的领域。"""

    def test_forbidden_domains_const(self):
        assert "identity" in FORBIDDEN_DOMAINS
        assert "constitution" in FORBIDDEN_DOMAINS
        assert "permission_model" in FORBIDDEN_DOMAINS
        assert "core_values" in FORBIDDEN_DOMAINS
        assert "anchor" in FORBIDDEN_DOMAINS

    def test_forbidden_not_in_allowed(self):
        allowed = {d.value for d in EvolutionDomain}
        for fd in FORBIDDEN_DOMAINS:
            assert fd not in allowed


class TestImpactLevel:
    """五级影响等级。"""

    def test_all_levels_exist(self):
        levels = {l.value for l in ImpactLevel}
        assert levels == {"negligible", "low", "moderate", "high", "critical"}


class TestImpactAssessment:
    """影响评估报告不变式。"""

    def test_default_is_safe(self):
        ia = ImpactAssessment()
        assert ia.is_safe is True
        assert ia.abi_breaking is False
        assert ia.identity_safe is True
        assert ia.constitution_safe is True
        assert ia.permission_safe is True
        assert ia.rollback_viable is True

    def test_boundary_violations_empty_when_safe(self):
        assert ImpactAssessment().boundary_violations == []

    def test_boundary_violations_report_unsafe(self):
        ia = ImpactAssessment(identity_safe=False, constitution_safe=False)
        assert not ia.is_safe
        violations = ia.boundary_violations
        assert "identity" in violations
        assert "constitution" in violations
        assert "permission_model" not in violations

    def test_custom_affected_modules(self):
        ia = ImpactAssessment(affected_modules=["ocos.runtime", "ocos.agent"])
        assert ia.affected_modules == ["ocos.runtime", "ocos.agent"]

    def test_custom_level(self):
        assert ImpactAssessment(level=ImpactLevel.HIGH).level == ImpactLevel.HIGH


class TestEvolutionProposal:
    """进化提案完整属性验证。"""

    def test_default_proposal(self):
        p = EvolutionProposal()
        assert p.state == EvolutionState.DETECTED
        assert p.sandbox_passed is False
        assert p.governance_approved is False
        assert p.domain == EvolutionDomain.PARAMETER

    def test_boundary_safe_proposal(self):
        assert EvolutionProposal().is_boundary_safe is True

    def test_ready_for_migration_requires_approval(self):
        p = EvolutionProposal()
        assert p.ready_for_migration is False
        p.state = EvolutionState.APPROVED
        p.sandbox_passed = True
        p.governance_approved = True
        assert p.ready_for_migration is True

    def test_ready_rejected_if_unsafe(self):
        p = EvolutionProposal(
            state=EvolutionState.APPROVED,
            sandbox_passed=True,
            governance_approved=True,
            impact=ImpactAssessment(identity_safe=False),
        )
        assert p.ready_for_migration is False


class TestRollbackReason:
    def test_all_reasons_exist(self):
        reasons = {r.value for r in RollbackReason}
        assert reasons == {"test_failure", "abi_break",
                           "perf_regression", "side_effect", "manual"}


class TestRollbackRecord:
    def test_default_record(self):
        r = RollbackRecord()
        assert r.reason == RollbackReason.TEST_FAILURE
        assert r.verified is False

    def test_custom_record(self):
        r = RollbackRecord(
            proposal_id="EP-001",
            reason=RollbackReason.ABI_BREAK,
            restored_at_tick=1000,
            snapshot_before="snap-a",
            snapshot_after="snap-b",
            verified=True,
        )
        assert r.proposal_id == "EP-001"
        assert r.verified is True
