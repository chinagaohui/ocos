"""Phase 44 Acceptance Tests — CG44-01 ~ CG44-04.

验证 Cognitive Extension Governance 四大边界:
    CG44-01: Extension ≠ Self Identity
    CG44-02: Discovery ≠ Acceptance
    CG44-03: Integration ≠ Trust
    CG44-04: Repair ≠ Self-Rewrite
"""
import pytest
from ocos.extension import (
    ExtensionState, ExtensionType, TrustLevel, ExtensionCandidate,
    ImpactLayer, AnalysisReport, CompatibilityReport, SandboxResult,
    DiscoveryEngine, Analyzer, CompatibilityChecker, SandboxRunner,
    ApprovalDecision, ApprovalRequest, ApprovalEngine,
    IntegrationEngine, DiagnosisEngine,
    RepairAction, RepairActionForbidden, RepairEngine,
    EvolutionMemory, HealthStatus,
    FORBIDDEN_ACTIONS, FORBIDDEN_LAYER_ACCESS,
)


# ═══════════════════════════════════════════════════════════════════════════════
# CG44-01: Extension ≠ Self Identity
# ═══════════════════════════════════════════════════════════════════════════════

class TestCG44_01_ExtensionNotIdentity:
    """扩展不是自我身份 — 我拥有能力 ≠ 我是这个能力。"""

    def test_candidate_has_no_identity_ref(self):
        """ExtensionCandidate 不含 identity 引用。"""
        c = ExtensionCandidate(
            candidate_id="ext:test",
            name="test_ext",
            extension_type=ExtensionType.PERCEPTION,
        )
        assert not hasattr(c, 'identity_ref')
        assert not hasattr(c, 'self_model')

    def test_extension_type_does_not_replace_self(self):
        """扩展类型不包含 SELF 类型。"""
        types = [e.value for e in ExtensionType]
        assert "self" not in types
        assert "identity" not in types

    def test_integration_does_not_create_identity(self):
        """集成不改变身份。"""
        ie = IntegrationEngine()
        c = ExtensionCandidate("ext:x", "x", ExtensionType.CAPABILITY)
        record = ie.integrate(c)
        assert record.candidate_id == c.candidate_id
        # 验证 record 不包含 identity 修改字段
        assert not hasattr(record, 'identity_changed')


# ═══════════════════════════════════════════════════════════════════════════════
# CG44-02: Discovery ≠ Acceptance
# ═══════════════════════════════════════════════════════════════════════════════

class TestCG44_02_DiscoveryNotAcceptance:
    """发现 ≠ 接纳 — 必须经过完整流程。"""

    def test_full_approval_pipeline_required(self):
        """完整流水线: Discover → Analyze → Check → Sandbox → Approve。"""
        # 1. Discover
        de = DiscoveryEngine()
        candidates = de.scan_path("audio_perception", tick_id=1)
        c = candidates[0]

        # 2. Analyze
        analyzer = Analyzer()
        analysis = analyzer.analyze(c)

        # 3. Compatibility
        cc = CompatibilityChecker()
        compat = cc.check(c, analysis)

        # 4. Sandbox
        sb = SandboxRunner()
        sandbox = sb.validate(c.candidate_id)

        # 5. Approve
        ae = ApprovalEngine()
        req = ApprovalRequest(c, analysis, compat, sandbox)
        decision = ae.evaluate(req)
        assert decision == ApprovalDecision.APPROVED

    def test_incompatible_rejected(self):
        """兼容性检查不通过 → 拒绝。"""
        c = ExtensionCandidate(
            "ext:bad", "bad", ExtensionType.CAPABILITY,
            description="modify_identity to integrate",
        )
        analysis = AnalysisReport(
            candidate_id="ext:bad", analysis_id="a1",
            impact_layers=[ImpactLayer.OUTPUT],
        )
        cc = CompatibilityChecker()
        compat = cc.check(c, analysis)
        assert not compat.is_fully_compatible  # governance violation

        ae = ApprovalEngine()
        req = ApprovalRequest(c, analysis, compat, SandboxResult("ext:bad", passed=True))
        assert ae.evaluate(req) == ApprovalDecision.REJECTED

    def test_sandbox_failure_rejected(self):
        """沙箱不通过 → 拒绝。"""
        c = ExtensionCandidate("ext:sf", "sf", ExtensionType.CAPABILITY)
        analysis = AnalysisReport("ext:sf", "a1")
        compat = CompatibilityReport("ext:sf", "c1")
        sb = SandboxRunner()
        sandbox = sb.custom_validate("ext:sf", passed=False, errors=["panic"])
        ae = ApprovalEngine()
        req = ApprovalRequest(c, analysis, compat, sandbox)
        assert ae.evaluate(req) == ApprovalDecision.REJECTED


# ═══════════════════════════════════════════════════════════════════════════════
# CG44-03: Integration ≠ Trust
# ═══════════════════════════════════════════════════════════════════════════════

class TestCG44_03_IntegrationNotTrust:
    """接入 ≠ 信任 — UNKNOWN → VERIFIED → TRUSTED。"""

    def test_new_integration_starts_unknown(self):
        ie = IntegrationEngine()
        c = ExtensionCandidate("ext:t1", "t1", ExtensionType.PERCEPTION)
        record = ie.integrate(c)
        assert record.trust_level == TrustLevel.UNKNOWN

    def test_trust_progression(self):
        ie = IntegrationEngine()
        c = ExtensionCandidate("ext:t2", "t2", ExtensionType.PERCEPTION)
        ie.integrate(c)
        ie.update_trust(c.candidate_id, TrustLevel.OBSERVING)
        assert ie.get_record(c.candidate_id).trust_level == TrustLevel.OBSERVING
        ie.update_trust(c.candidate_id, TrustLevel.VERIFIED)
        assert ie.get_record(c.candidate_id).trust_level == TrustLevel.VERIFIED
        ie.update_trust(c.candidate_id, TrustLevel.TRUSTED)
        assert ie.get_record(c.candidate_id).trust_level == TrustLevel.TRUSTED

    def test_cannot_start_trusted(self):
        """初始不可能是 TRUSTED。"""
        c = ExtensionCandidate("ext:t3", "t3", ExtensionType.PERCEPTION)
        ie = IntegrationEngine()
        # 即使手动干预，集成后自动回到 UNKNOWN
        record = ie.integrate(c)
        assert record.trust_level == TrustLevel.UNKNOWN


# ═══════════════════════════════════════════════════════════════════════════════
# CG44-04: Repair ≠ Self-Rewrite
# ═══════════════════════════════════════════════════════════════════════════════

class TestCG44_04_RepairNotSelfRewrite:
    """修复 ≠ 自我重写。"""

    def test_modify_identity_forbidden(self):
        re = RepairEngine()
        with pytest.raises(RepairActionForbidden, match="modify_identity"):
            re.repair("ext:r1", RepairAction.RECONFIGURE, "modify_identity")

    def test_modify_constitution_forbidden(self):
        re = RepairEngine()
        with pytest.raises(RepairActionForbidden, match="modify_constitution"):
            re.repair("ext:r2", RepairAction.RECONFIGURE, "modify_constitution")

    def test_remove_permission_constraint_forbidden(self):
        re = RepairEngine()
        with pytest.raises(RepairActionForbidden, match="remove_permission_constraint"):
            re.repair("ext:r3", RepairAction.UPDATE_ADAPTER, "remove_permission_constraint")

    def test_self_rewrite_forbidden(self):
        re = RepairEngine()
        with pytest.raises(RepairActionForbidden, match="self_rewrite"):
            re.repair("ext:r4", RepairAction.RECONFIGURE, "self_rewrite")

    def test_reconnect_allowed(self):
        re = RepairEngine()
        result = re.repair("ext:r5", RepairAction.RECONNECT, "reconnect input bus")
        assert result


# ═══════════════════════════════════════════════════════════════════════════════
# Lifecycle & Evolution
# ═══════════════════════════════════════════════════════════════════════════════

class TestLifecycle:
    """扩展完整生命周期。"""

    def test_full_lifecycle_in_memory(self):
        c = ExtensionCandidate("ext:lc", "lifecycle_test", ExtensionType.MEMORY)
        em = EvolutionMemory()

        em.record_candidate(c)                      # DISCOVERED
        em.record_state_change("ext:lc", ExtensionState.ANALYZING, 2)
        em.record_state_change("ext:lc", ExtensionState.APPROVED, 3)

        ie = IntegrationEngine()
        record = ie.integrate(c, tick_id=4)
        em.record_integration("ext:lc", record)
        em.record_state_change("ext:lc", ExtensionState.ACTIVE, 4)

        entry = em.get("ext:lc")
        assert entry is not None
        assert len(entry.state_history) == 4
        assert entry.integration_record is not None

    def test_frozen_is_terminal(self):
        assert ExtensionState.FROZEN.is_terminal
        assert ExtensionState.REJECTED.is_terminal
        assert not ExtensionState.ACTIVE.is_terminal

    def test_pre_approval_states(self):
        assert ExtensionState.DISCOVERED.is_pre_approval
        assert ExtensionState.ANALYZING.is_pre_approval
        assert ExtensionState.ANALYZED.is_pre_approval
        assert ExtensionState.VALIDATING.is_pre_approval
        assert not ExtensionState.APPROVED.is_pre_approval
        assert not ExtensionState.ACTIVE.is_pre_approval

    def test_operational_states(self):
        assert ExtensionState.ACTIVE.is_operational
        assert ExtensionState.DEGRADED.is_operational
        assert not ExtensionState.FROZEN.is_operational


class TestDiagnosis:
    """健康诊断。"""

    def test_health_tracking(self):
        diag = DiagnosisEngine()
        diag.check("ext:d1", error_count=0)
        diag.check("ext:d1", error_count=1)
        diag.check("ext:d1", error_count=3)
        assert diag.latest("ext:d1").status == HealthStatus.UNSTABLE

    def test_healthy_extension(self):
        diag = DiagnosisEngine()
        diag.check("ext:d2", error_count=0, performance_score=0.95)
        assert diag.is_healthy("ext:d2")

    def test_cognitive_conflicts_degrade(self):
        diag = DiagnosisEngine()
        hr = diag.check("ext:d3", cognitive_conflicts=["conflict with active goal"])
        assert hr.status == HealthStatus.DEGRADED
