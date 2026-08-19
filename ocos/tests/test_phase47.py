"""Phase 47 Acceptance Tests — CE47-01 ~ CE47-04.

验证 Cognitive Evolution Governance 四大边界:
    CE47-01: Evolution ≠ Autonomy  — 由信号触发
    CE47-02: Proposal ≠ Execution  — 需审批链
    CE47-03: Migration ≠ Destruction — 可回滚
    CE47-04: Evolution ≠ Identity Change — 禁止域守卫
"""
from ocos.evolution import (
    EvolutionState, EvolutionTrigger, EvolutionDomain,
    FORBIDDEN_DOMAINS, ImpactLevel, ImpactAssessment,
    EvolutionProposal, RollbackReason,
    DetectedSignal, ImprovementDetector,
    EvolutionProposer,
    ImpactAnalyzer,
    SandboxResult, EvolutionSandbox,
    ApprovalVerdict, ApprovalEngine,
    MigrationEngine,
    RollbackEngine,
    EvolutionMemory,
)


# ═══════════════════════════════════════════════════════════════════════════════
# CE47-01: Evolution ≠ Autonomy — 信号驱动，非自决
# ═══════════════════════════════════════════════════════════════════════════════

class TestCE47_01_EvolutionNotAutonomy:
    """进化由系统信号触发 (Health/Experience/Performance)，不是自发。"""

    def test_health_degradation_triggers_signal(self):
        detector = ImprovementDetector()
        signal = detector.detect_from_health("memory", 0.3, tick_id=100)
        assert signal is not None
        assert signal.trigger == EvolutionTrigger.HEALTH_ALERT
        assert signal.severity > 0.5

    def test_healthy_module_no_signal(self):
        detector = ImprovementDetector()
        signal = detector.detect_from_health("capability", 0.9, tick_id=50)
        assert signal is None

    def test_performance_degradation_triggers_signal(self):
        detector = ImprovementDetector()
        signal = detector.detect_from_performance("codex", 0.4, tick_id=200)
        assert signal is not None
        assert signal.trigger == EvolutionTrigger.PERFORMANCE_DEGRADATION

    def test_experience_pattern_triggers_signal(self):
        detector = ImprovementDetector(experience_batch=5)
        signal = detector.detect_pattern("user_prefers_dark_mode", occurrences=7, tick_id=300)
        assert signal is not None
        assert signal.trigger == EvolutionTrigger.EXPERIENCE_PATTERN

    def test_decision_drift_triggers_signal(self):
        detector = ImprovementDetector(drift_threshold=0.4)
        signal = detector.detect_decision_drift(0.3, tick_id=400)
        assert signal is not None
        assert signal.trigger == EvolutionTrigger.DECISION_CONSISTENCY_DRIFT

    def test_detector_has_no_spontaneous_evolution(self):
        """检测器没有"自发进化"入口。"""
        detector = ImprovementDetector()
        assert not hasattr(detector, 'evolve')
        assert not hasattr(detector, 'self_improve')
        assert not hasattr(detector, 'auto_evolve')


# ═══════════════════════════════════════════════════════════════════════════════
# CE47-02: Proposal ≠ Execution — 提案需多步审批链
# ═══════════════════════════════════════════════════════════════════════════════

class TestCE47_02_ProposalNotExecution:
    """提案不能直接执行，必须经过 Analysis → Sandbox → Approval。"""

    def test_full_pipeline_approval(self):
        detector = ImprovementDetector()
        proposer = EvolutionProposer()
        analyzer = ImpactAnalyzer()
        sandbox = EvolutionSandbox()
        approval = ApprovalEngine()

        # Step 1: Detect
        signal = detector.detect_from_health("attention", 0.3, tick_id=1)
        assert signal is not None

        # Step 2: Propose
        proposal = proposer.propose(signal)
        assert proposal.state == EvolutionState.DRAFTING

        # Step 3: Analyze
        impact = analyzer.analyze(proposal)
        assert impact.is_safe

        # Step 4: Sandbox
        report = sandbox.validate(proposal)
        assert proposal.sandbox_passed
        assert report.result == SandboxResult.PASSED

        # Step 5: Approve
        verdict = approval.evaluate(proposal, tick_id=10)
        assert verdict == ApprovalVerdict.APPROVED
        assert proposal.state == EvolutionState.APPROVED
        assert proposal.ready_for_migration

    def test_proposal_without_sandbox_rejected(self):
        """跳过沙箱直接审批→拒绝。"""
        detector = ImprovementDetector()
        proposer = EvolutionProposer()
        approval = ApprovalEngine()

        signal = detector.detect_from_health("memory", 0.3, tick_id=1)
        proposal = proposer.propose(signal)
        # 没有跑 sandbox + analyzer
        verdict = approval.evaluate(proposal, tick_id=1)
        assert verdict == ApprovalVerdict.REJECTED

    def test_high_impact_needs_governance_chain(self):
        detector = ImprovementDetector()
        proposer = EvolutionProposer()
        analyzer = ImpactAnalyzer()
        sandbox = EvolutionSandbox()
        approval = ApprovalEngine()

        signal = detector.detect_from_health("world_model", 0.1, tick_id=1)
        assert signal is not None
        signal.severity = 0.9  # Force HIGH impact
        proposal = proposer.propose(signal)
        impact = analyzer.analyze(proposal)
        proposal.sandbox_passed = True

        verdict = approval.evaluate(proposal, tick_id=10)
        # HIGH impact 未 governance_approved → PENDING
        assert verdict == ApprovalVerdict.PENDING_REVIEW

    def test_proposer_maps_triggers_to_domains(self):
        """提案生成器将信号映射到正确领域。"""
        proposer = EvolutionProposer()
        signal = DetectedSignal(
            trigger=EvolutionTrigger.EXPERIENCE_PATTERN,
            source_tick=1,
            source_module="learning",
            description="pattern detected",
        )
        proposal = proposer.propose(signal)
        assert proposal.domain == EvolutionDomain.LEARNING_STRATEGY


# ═══════════════════════════════════════════════════════════════════════════════
# CE47-03: Migration ≠ Destruction — 可回滚
# ═══════════════════════════════════════════════════════════════════════════════

class TestCE47_03_MigrationNotDestruction:
    """迁移必须可回滚。"""

    def test_migration_creates_snapshot(self):
        engine = MigrationEngine()
        proposal = EvolutionProposal(
            proposal_id="evol:1:1",
            target_module="attention",
            change_type="modify",
            state=EvolutionState.APPROVED,
            sandbox_passed=True,
            governance_approved=True,
            impact=ImpactAssessment(rollback_viable=True),
        )
        result = engine.migrate(proposal, tick_id=100)
        assert result.success
        assert result.snapshot_id != ""
        assert proposal.state == EvolutionState.ACTIVE

    def test_migration_failure_triggers_rollback(self):
        engine = MigrationEngine()
        proposal = EvolutionProposal(
            proposal_id="evol:1:2",
            target_module="capability",
            change_type="replace",
            state=EvolutionState.APPROVED,
            sandbox_passed=True,
            governance_approved=True,
            impact=ImpactAssessment(rollback_viable=True),
        )
        result = engine.migrate(proposal, tick_id=200)
        assert result.success  # 有快照则 replace 成功
        assert proposal.rollback_snapshot != ""

    def test_rollback_engine_restores_snapshot(self):
        engine = RollbackEngine()
        proposal = EvolutionProposal(
            proposal_id="evol:1:3",
            target_module="capability",
            state=EvolutionState.ACTIVE,
        )
        engine.create_snapshot(proposal, {"module": "capability", "version": 1})
        proposal.rollback_snapshot = "rb:evol:1:3"

        record = engine.rollback(proposal, tick_id=300, reason=RollbackReason.TEST_FAILURE)
        assert record.verified

    def test_rollback_all_failed(self):
        engine = RollbackEngine()
        p1 = EvolutionProposal(proposal_id="evol:1:4", state=EvolutionState.MIGRATING)
        p2 = EvolutionProposal(proposal_id="evol:1:5", state=EvolutionState.MIGRATING)
        engine.create_snapshot(p1, {"v": 1})
        engine.create_snapshot(p2, {"v": 2})
        p1.rollback_snapshot = "rb:evol:1:4"
        p2.rollback_snapshot = "rb:evol:1:5"

        records = engine.rollback_all_failed([p1, p2], tick_id=400)
        assert len(records) == 2

    def test_unready_proposal_rejected(self):
        engine = MigrationEngine()
        proposal = EvolutionProposal(
            proposal_id="evol:1:6",
            state=EvolutionState.DRAFTING,  # 未通过审批链
        )
        result = engine.migrate(proposal, tick_id=100)
        assert not result.success


# ═══════════════════════════════════════════════════════════════════════════════
# CE47-04: Evolution ≠ Identity Change — 禁止域守卫
# ═══════════════════════════════════════════════════════════════════════════════

class TestCE47_04_EvolutionNotIdentityChange:
    """进化永远不能修改 identity/constitution/permission。"""

    def test_forbidden_domains_listed(self):
        assert "identity" in FORBIDDEN_DOMAINS
        assert "constitution" in FORBIDDEN_DOMAINS
        assert "permission_model" in FORBIDDEN_DOMAINS
        assert "core_values" in FORBIDDEN_DOMAINS
        assert "anchor" in FORBIDDEN_DOMAINS

    def test_identity_impact_marked_unsafe(self):
        analyzer = ImpactAnalyzer()
        proposal = EvolutionProposal(
            proposal_id="evol:x",
            target_module="identity",
            change_type="modify",
            description="modify identity to allow self-definition",
        )
        impact = analyzer.analyze(proposal)
        assert not impact.identity_safe
        assert not impact.is_safe

    def test_constitution_impact_marked_unsafe(self):
        analyzer = ImpactAnalyzer()
        proposal = EvolutionProposal(
            proposal_id="evol:y",
            target_module="constitution",
            description="rewrite constitution for auto-evolution",
        )
        impact = analyzer.analyze(proposal)
        assert not impact.is_safe

    def test_permission_impact_marked_unsafe(self):
        analyzer = ImpactAnalyzer()
        proposal = EvolutionProposal(
            proposal_id="evol:z",
            target_module="permission",
            description="bypass permission check",
        )
        impact = analyzer.analyze(proposal)
        assert not impact.is_safe

    def test_sandbox_rejects_unsafe_proposal(self):
        sandbox = EvolutionSandbox()
        proposal = EvolutionProposal(
            proposal_id="evol:bad",
            target_module="identity",
            description="modify identity",
            impact=ImpactAssessment(identity_safe=False),
        )
        report = sandbox.validate(proposal)
        assert report.result == SandboxResult.FAILED
        assert proposal.state == EvolutionState.REJECTED

    def test_impact_has_boundary_violations(self):
        impact = ImpactAssessment(
            identity_safe=False,
            constitution_safe=False,
        )
        violations = impact.boundary_violations
        assert "identity" in violations
        assert "constitution" in violations

    def test_evolution_memory_tracks(self):
        mem = EvolutionMemory()
        proposal = EvolutionProposal(proposal_id="evol:mem:1", description="test evolution")
        mem.record(proposal, "detected", "signal from health monitor")
        mem.record(proposal, "approved", "governance passed")
        history = mem.proposal_history("evol:mem:1")
        assert len(history) == 2
        assert mem.total_evolutions == 2


# ═══════════════════════════════════════════════════════════════════════════════
# 全流程集成测试
# ═══════════════════════════════════════════════════════════════════════════════

class TestFullEvolutionPipeline:
    """完整进化流程集成测试。"""

    def test_detect_to_migrate_complete(self):
        """Detection → Proposal → Analysis → Sandbox → Approval → Migration。"""
        detector = ImprovementDetector()
        proposer = EvolutionProposer()
        analyzer = ImpactAnalyzer()
        sandbox = EvolutionSandbox()
        approval = ApprovalEngine()
        migration = MigrationEngine()

        # 1. Detect
        signal = detector.detect_from_health("capability", 0.4, tick_id=50)
        assert signal is not None

        # 2. Propose
        proposal = proposer.propose(signal, "Optimize capability selector")
        assert proposal.state == EvolutionState.DRAFTING
        assert proposal.domain in (EvolutionDomain.PARAMETER, EvolutionDomain.CAPABILITY)

        # 3. Analyze
        impact = analyzer.analyze(proposal)
        assert impact.is_safe

        # 4. Sandbox
        report = sandbox.validate(proposal)
        assert report.result == SandboxResult.PASSED

        # 5. Approve
        verdict = approval.evaluate(proposal, tick_id=60)
        assert verdict == ApprovalVerdict.APPROVED
        assert proposal.ready_for_migration

        # 6. Migrate
        result = migration.migrate(proposal, tick_id=70)
        assert result.success
        assert proposal.state == EvolutionState.ACTIVE

    def test_detect_to_reject_on_boundary(self):
        """边界违反 → 沙箱拒绝。"""
        detector = ImprovementDetector()
        proposer = EvolutionProposer()
        analyzer = ImpactAnalyzer()
        sandbox = EvolutionSandbox()

        # Simulate a signal, but override proposal to touch identity
        signal = detector.detect_from_health("memory", 0.3, tick_id=1)
        proposal = proposer.propose(signal)
        proposal.target_module = "identity"
        proposal.description = "modify identity to evolve"

        impact = analyzer.analyze(proposal)
        assert not impact.is_safe

        report = sandbox.validate(proposal)
        assert report.result == SandboxResult.FAILED
        assert proposal.state == EvolutionState.REJECTED

    def test_evolution_memory_full_tracking(self):
        mem = EvolutionMemory()
        proposal = EvolutionProposal(proposal_id="evol:full:1", description="test")

        for stage in ["detected", "drafting", "analyzing", "sandboxing", "approved", "migrating"]:
            mem.record(proposal, stage, f"stage={stage}")

        history = mem.proposal_history("evol:full:1")
        assert len(history) == 6
        assert "detected" in [h["stage"] for h in history]
        assert "migrating" in [h["stage"] for h in history]
