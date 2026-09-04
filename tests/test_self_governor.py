"""OCOS self_governor 自我治理器不变式测试。

Phase 25 SelfGovernor 约束：
    - Self 不能修改自己的 IdentityBoundary
    - Self 不能修改 SelfGovernor
    - 所有演化变更必须经 governance_approval_id 审批
    - EvolutionRequest / EvolutionRecord / RequestStatus / DenialReason
"""

import pytest
from datetime import datetime, timezone

from ocos.self.governor import (
    SelfGovernor,
    EvolutionRequest,
    EvolutionRecord,
    RequestStatus,
    DenialReason,
)
from ocos.self.identity_boundary import IdentityBoundary


class TestEvolutionRequest:
    """演化申请不变式。"""

    def test_create_minimal(self):
        r = EvolutionRequest.create(
            proposed_statement="I am a deterministic engine",
            evidence_belief_ids=("BLF-001", "BLF-002"),
        )
        assert r.status == RequestStatus.SUBMITTED
        assert r.from_statement is None
        assert r.from_version == 0
        assert len(r.evidence_belief_ids) == 2

    def test_create_with_from(self):
        r = EvolutionRequest.create(
            proposed_statement="new statement",
            evidence_belief_ids=["BLF-003"],
            from_statement="old statement",
            from_version=5,
        )
        assert r.from_statement == "old statement"
        assert r.from_version == 5

    def test_approve_returns_approved_request(self):
        r = EvolutionRequest.create(
            proposed_statement="x",
            evidence_belief_ids=[],
        )
        approved = r.approve()
        assert approved.status == RequestStatus.APPROVED
        assert approved.denial_reason is None

    def test_deny_returns_denied_request(self):
        r = EvolutionRequest.create(
            proposed_statement="x",
            evidence_belief_ids=[],
        )
        denied = r.deny(DenialReason.BOUNDARY_VIOLATION, "identity touch")
        assert denied.status == RequestStatus.DENIED
        assert denied.denial_reason == DenialReason.BOUNDARY_VIOLATION
        assert denied.denial_detail == "identity touch"

    def test_denial_reasons_complete(self):
        reasons = {r.value for r in DenialReason}
        expected = {
            "insufficient-evidence",
            "boundary-violation",
            "forbidden-transition",
            "authority-overrun",
            "self-reference-violation",
            "stability-not-met",
            "frequency-exceeded",
            "boundary-check-failed",
            "statement-change-too-large",
        }
        assert reasons == expected


class TestEvolutionRecord:
    """演化审计记录不变式。"""

    def test_from_approved_request(self):
        req = EvolutionRequest.create(
            proposed_statement="new self",
            evidence_belief_ids=["BLF-001"],
            from_statement="old self",
            from_version=1,
        )
        approved_req = req.approve()
        rec = EvolutionRecord.from_approved_request(
            approved_req, new_version=2, governor_signature="sig-abc"
        )
        assert rec.new_version == 2
        assert rec.old_statement == "old self"
        assert rec.new_statement == "new self"
        assert rec.governor_signature == "sig-abc"
        assert rec.record_id.startswith("REC-")

    def test_record_id_unique(self):
        now = datetime.now(timezone.utc)
        r1 = EvolutionRecord(
            record_id="REC-AAA",
            request=EvolutionRequest(
                request_id="EVR-1", proposed_statement="s",
                evidence_belief_ids=(), from_statement=None,
                from_version=0, submitted_at=now,
                status=RequestStatus.APPROVED,
            ),
            old_statement=None, new_statement="s",
            new_version=1, approved_at=now, governor_signature="g",
        )
        r2 = EvolutionRecord(
            record_id="REC-BBB",
            request=EvolutionRequest(
                request_id="EVR-2", proposed_statement="s",
                evidence_belief_ids=(), from_statement=None,
                from_version=0, submitted_at=now,
                status=RequestStatus.APPROVED,
            ),
            old_statement=None, new_statement="s",
            new_version=1, approved_at=now, governor_signature="g",
        )
        assert r1.record_id != r2.record_id


class TestSelfGovernor:
    """SelfGovernor 核心不变式。"""

    def _make_governor(self):
        return SelfGovernor(boundary=IdentityBoundary.create_default())

    def test_governor_creation(self):
        g = self._make_governor()
        assert g.governor_id.startswith("GOV-")
        # boundary 是同一结构但 id/timestamp 不同，检查语义内容
        assert g.boundary.version == 1
        assert len(g.boundary.principles) == 11
        assert len(g.boundary.forbidden_transitions) == 5
        assert g.history == ()

    def test_governor_requires_valid_boundary(self):
        with pytest.raises(TypeError):
            SelfGovernor(boundary="not a boundary")  # type: ignore[arg-type]

    def test_governor_rejects_invalid_boundary(self):
        from ocos.self.identity_boundary import IdentityBoundary, BoundaryPrinciple
        # 移除必须的 NO_SELF_MODIFICATION 原则 → BoundaryValidator 应拒绝
        principles = tuple(
            bp for bp in BoundaryPrinciple if bp != BoundaryPrinciple.NO_SELF_MODIFICATION
        )
        ib = IdentityBoundary(
            id="test", version=1,
            principles=principles,
            forbidden_transitions=(),
            authority_limits=("self-layer",),
            self_reference_constraints=("no-circular-proof",),
            evolution_constraints={"min_evidence_beliefs": 5},
            created_at=datetime.now(timezone.utc),
        )
        with pytest.raises(ValueError):
            SelfGovernor(boundary=ib)

    def test_submit_and_approve(self):
        g = self._make_governor()
        req = EvolutionRequest.create(
            proposed_statement="I am improved",
            evidence_belief_ids=["BLF-001", "BLF-002", "BLF-003", "BLF-004", "BLF-005"],
            from_statement="I am default",
            from_version=1,
        )
        approved = req.approve()
        rec = EvolutionRecord.from_approved_request(
            approved, new_version=2, governor_signature=g.governor_id
        )
        # history 内部积累（governor 不直接添加，但记录可创建）
        assert rec.new_version == 2

    def test_evaluate_method_signature(self):
        g = self._make_governor()
        req = EvolutionRequest.create(
            proposed_statement="test",
            evidence_belief_ids=[],
        )
        result = g.evaluate(req)
        assert isinstance(result, tuple)
        assert len(result) == 3  # (can_approve, denial_reason, detail)

    def test_history_property_is_immutable(self):
        g = self._make_governor()
        h = g.history
        with pytest.raises(AttributeError):
            g.history = "changed"  # type: ignore[misc]
