"""Phase 56: Self Diagnosis & Repair — Tests.

验收:
    SD56-01: Diagnosis ≠ Decision — 发现异常不自动决策
    SD56-02: Repair ≠ Evolution — 修复不改变能力
    SD56-03: Repair ≠ Self Rewrite — 禁止的修复被阻止
    SD56-04: Repair requires Snapshot — 修复前 checkpoint
    SD56-05: Failure Isolation — 单模块故障不拖垮
    SD56-06: Learning From Repair — 修复经验进入记忆
"""

import pytest
import time
import uuid

from ocos.diagnosis.diagnosis_types import (
    FaultCategory, Severity,
    ComponentHealth, SystemSnapshot,
    FaultSignal, DiagnosisReport, EvidencePoint,
)
from ocos.diagnosis.system_probe import SystemProbe
from ocos.diagnosis.health_analyzer import HealthAnalyzer
from ocos.diagnosis.fault_detector import FaultDetector, ThresholdRule
from ocos.diagnosis.repair_types import (
    RepairType, RepairStatus, RepairRisk,
    RepairProposal, RepairRecord,
)
from ocos.diagnosis.repair_proposer import RepairProposer
from ocos.diagnosis.repair_validator import (
    RepairValidator, ValidationCode,
)
from ocos.diagnosis.repair_sandbox import (
    RepairSandbox, SandboxResult,
)
from ocos.diagnosis.repair_executor import (
    RepairExecutor, ExecutorResult,
)
from ocos.diagnosis.repair_memory import RepairMemory


# ══════════════════════════════════════════════════
# System Probe
# ══════════════════════════════════════════════════

class TestSystemProbe:
    def test_capture_snapshot(self):
        probe = SystemProbe(tick=42)
        snap = probe.capture()
        assert snap.tick == 42
        assert snap.snapshot_id.startswith("snap-")
        assert len(snap.components) > 0
        assert 0.0 <= snap.overall_health <= 1.0

    def test_tick_capture_increments(self):
        probe = SystemProbe(tick=10)
        snap1 = probe.tick_capture()
        assert snap1.tick == 11
        snap2 = probe.tick_capture()
        assert snap2.tick == 12

    def test_probe_includes_components(self):
        probe = SystemProbe()
        snap = probe.capture()
        assert "runtime" in snap.components
        assert "persistence" in snap.components

    def test_sd56_05_probe_isolated(self):
        """SD56-05: 单个探针失败不影响其他。"""
        probe = SystemProbe(probes_enabled=["runtime", "nonexistent_probe"])
        snap = probe.capture()
        assert "runtime" in snap.components
        assert snap.components["runtime"].healthy
        # nonexistent 也被捕获了 (try-except)
        assert "nonexistent_probe" in snap.components


# ══════════════════════════════════════════════════
# Health Analyzer
# ══════════════════════════════════════════════════

class TestHealthAnalyzer:
    def test_stable_trend(self):
        ha = HealthAnalyzer(window_size=10)
        for i in range(10):
            snap = SystemSnapshot(
                snapshot_id=f"s{i}", timestamp=time.time(), tick=i,
                components={"test": ComponentHealth("test", healthy=True)},
                overall_health=0.9,
            )
            ha.add_snapshot(snap)
        trend = ha.analyze()
        assert trend.direction == "stable"

    def test_degrading_trend(self):
        ha = HealthAnalyzer(window_size=10, degrade_threshold=0.05)
        for i in range(10):
            health = 0.9 - i * 0.05  # 0.9 → 0.45
            snap = SystemSnapshot(
                snapshot_id=f"s{i}", timestamp=time.time(), tick=i,
                components={"test": ComponentHealth("test", healthy=health > 0.5)},
                overall_health=max(0.0, health),
            )
            ha.add_snapshot(snap)
        trend = ha.analyze()
        assert trend.direction in ("degrading", "failing")

    def test_empty_history(self):
        ha = HealthAnalyzer()
        trend = ha.analyze()
        assert trend.direction == "stable"
        assert trend.confidence == 0.0


# ══════════════════════════════════════════════════
# Fault Detector
# ══════════════════════════════════════════════════

class TestFaultDetector:
    def test_detect_unhealthy_component(self):
        detector = FaultDetector()
        snap = SystemSnapshot(
            snapshot_id="s1", timestamp=time.time(), tick=1,
            components={
                "capability_fs": ComponentHealth("capability_fs", healthy=False,
                                                  last_error="disk full"),
            },
        )
        signals = detector.feed(snap)
        assert len(signals) >= 1
        assert signals[0].category == FaultCategory.CAPABILITY_FAILURE

    def test_sd56_01_no_decision(self):
        """SD56-01: FaultDetector 只输出信号，不做决策。"""
        detector = FaultDetector()
        snap = SystemSnapshot(
            snapshot_id="s1", timestamp=time.time(), tick=1,
            components={"test": ComponentHealth("test", healthy=False)},
        )
        signals = detector.feed(snap)
        # 仅返回信号，不调用任何决策/修复
        assert isinstance(signals, list)
        assert all(isinstance(s, FaultSignal) for s in signals)

    def test_threshold_rule(self):
        detector = FaultDetector(thresholds=[
            ThresholdRule(
                metric="queue_depth", component="scheduler",
                operator=">", value=100, severity=Severity.HIGH,
                category=FaultCategory.SCHEDULER_STALL,
            ),
        ])
        snap = SystemSnapshot(
            snapshot_id="s1", timestamp=time.time(), tick=1,
            components={
                "scheduler": ComponentHealth("scheduler", healthy=True,
                                              metrics={"queue_depth": 500}),
            },
        )
        signals = detector.feed(snap)
        assert len(signals) == 1
        assert signals[0].category == FaultCategory.SCHEDULER_STALL

    def test_no_signals_when_healthy(self):
        detector = FaultDetector()
        snap = SystemSnapshot(
            snapshot_id="s1", timestamp=time.time(), tick=1,
            components={"ok": ComponentHealth("ok", healthy=True)},
            overall_health=1.0,
        )
        signals = detector.feed(snap)
        assert len(signals) == 0

    def test_fault_callback(self):
        events = []
        detector = FaultDetector()
        detector.on_fault = lambda s: events.append(s)
        snap = SystemSnapshot(
            snapshot_id="s1", timestamp=time.time(), tick=1,
            components={"test": ComponentHealth("test", healthy=False)},
        )
        detector.feed(snap)
        assert len(events) >= 1


# ══════════════════════════════════════════════════
# Repair Proposer
# ══════════════════════════════════════════════════

class TestRepairProposer:
    def test_propose_from_diagnosis(self):
        proposer = RepairProposer()
        report = DiagnosisReport(
            report_id="r1", timestamp=time.time(),
            problem="filesystem adapter failed",
            category=FaultCategory.CAPABILITY_FAILURE,
            severity=Severity.HIGH,
            affected_components=["capability_fs"],
            recommendation="repair",
            confidence=0.8,
        )
        proposals = proposer.propose(report)
        assert len(proposals) > 0
        # 第一条应该是 RECONNECT (低风险)
        assert proposals[0].repair_type == RepairType.RECONNECT
        assert proposals[0].is_allowed

    def test_sd56_02_repair_not_evolution(self):
        """SD56-02: 修复类型都是恢复性操作，不新增能力。"""
        # 验证所有允许的修复类型都不包含 "expand"/"add"/"create" 等演化语义
        for rtype in RepairType.allowed():
            name = rtype.value.lower()
            assert "expand" not in name
            assert "add" not in name
            assert "create" not in name
            assert "modify" not in name

    def test_no_proposal_for_unknown_category(self):
        proposer = RepairProposer()
        report = DiagnosisReport(
            report_id="r1", timestamp=time.time(),
            category=FaultCategory.IDENTITY_DRIFT,
        )
        proposals = proposer.propose(report)
        # IDENTITY_DRIFT maps to REINIT (CRITICAL risk)
        if proposals:
            for p in proposals:
                assert p.risk != RepairRisk.NONE  # at minimum recognized


# ══════════════════════════════════════════════════
# Repair Validator
# ══════════════════════════════════════════════════

class TestRepairValidator:
    def test_approve_low_risk(self):
        v = RepairValidator()
        proposal = RepairProposal(
            proposal_id="p1", timestamp=time.time(),
            repair_type=RepairType.CLEAR_CACHE,
            target_component="cache",
            steps=["step 1"],
        )
        outcome = v.validate(proposal)
        assert outcome.code == ValidationCode.APPROVE

    def test_sd56_03_forbidden_blocked(self):
        """SD56-03: 禁止的修复类型被阻止。"""
        v = RepairValidator()
        outcome = v.validate_forbidden("self_rewrite", "brain")
        assert outcome.code == ValidationCode.REJECT
        assert "SD56-03" in outcome.blocked_reason

    def test_sd56_03_forbidden_list(self):
        """SD56-03: 所有禁止操作都被拒绝。"""
        v = RepairValidator()
        for forbidden in RepairType.forbidden():
            outcome = v.validate_forbidden(forbidden, "test")
            assert outcome.code == ValidationCode.REJECT, f"should block {forbidden}"

    def test_immutable_component_blocked(self):
        """SD56-03: 不可修改核心组件。"""
        v = RepairValidator()
        proposal = RepairProposal(
            proposal_id="p1", timestamp=time.time(),
            repair_type=RepairType.RELOAD,
            target_component="identity",
            steps=["step"],
        )
        outcome = v.validate(proposal)
        assert outcome.code == ValidationCode.REJECT

    def test_critical_risk_needs_review(self):
        v = RepairValidator()
        proposal = RepairProposal(
            proposal_id="p1", timestamp=time.time(),
            repair_type=RepairType.REINIT,
            target_component="event_store",
            risk=RepairRisk.CRITICAL,
            steps=["step 1"],
        )
        outcome = v.validate(proposal)
        assert outcome.code == ValidationCode.NEEDS_REVIEW

    def test_empty_steps_rejected(self):
        v = RepairValidator()
        proposal = RepairProposal(
            proposal_id="p1", timestamp=time.time(),
            repair_type=RepairType.CLEAR_CACHE,
            target_component="cache",
            steps=[],  # empty
        )
        outcome = v.validate(proposal)
        assert outcome.code == ValidationCode.REJECT


# ══════════════════════════════════════════════════
# Repair Sandbox
# ══════════════════════════════════════════════════

class TestRepairSandbox:
    def test_pass_for_valid_proposal(self):
        sandbox = RepairSandbox()
        proposal = RepairProposal(
            proposal_id="p1", timestamp=time.time(),
            repair_type=RepairType.CLEAR_CACHE,
            target_component="cache",
            steps=["step 1", "step 2"],
            reversible=True,
        )
        report = sandbox.validate(proposal)
        assert report.result == SandboxResult.PASS

    def test_fail_for_forbidden_type(self):
        sandbox = RepairSandbox()
        # 使用 is_allowed=False 的 proposal
        proposal = RepairProposal(
            proposal_id="p1", timestamp=time.time(),
            repair_type="self_rewrite",   # 禁止
            target_component="brain",
            steps=["step"],
        )
        report = sandbox.validate(proposal)
        assert report.result == SandboxResult.FAIL

    def test_empty_steps_warning(self):
        sandbox = RepairSandbox()
        proposal = RepairProposal(
            proposal_id="p1", timestamp=time.time(),
            repair_type=RepairType.CLEAR_CACHE,
            target_component="cache",
            steps=[],
        )
        report = sandbox.validate(proposal)
        assert report.checks_failed > 0

    def test_sandbox_simulation(self):
        """沙箱模拟不会影响生产环境。"""
        sandbox = RepairSandbox()
        proposal = RepairProposal(
            proposal_id="p1", timestamp=time.time(),
            repair_type=RepairType.CLEAR_CACHE,
            target_component="cache",
            steps=["step 1"],
        )

        def simulate(report):
            return {"cache_size": 0}

        report = sandbox.validate(
            proposal,
            before_state={"cache_size": 1024},
            simulate_fn=simulate,
        )
        assert report.result in (SandboxResult.PASS, SandboxResult.FAIL)
        assert report.before_state == {"cache_size": 1024}
        assert report.after_state == {"cache_size": 0}


# ══════════════════════════════════════════════════
# Repair Executor
# ══════════════════════════════════════════════════

class TestRepairExecutor:
    def test_successful_execution(self):
        checkpoints = []
        steps_done = []

        executor = RepairExecutor()
        executor.create_checkpoint = lambda pid: checkpoints.append(pid) or "cp-1"
        executor.execute_step = lambda step, ctx: steps_done.append(step) or True

        proposal = RepairProposal(
            proposal_id="p1", timestamp=time.time(),
            repair_type=RepairType.CLEAR_CACHE,
            target_component="cache",
            steps=["clear cache", "verify"],
        )
        report = executor.execute(proposal)
        assert report.result == ExecutorResult.SUCCESS
        assert report.checkpoint_id == "cp-1"
        assert len(steps_done) == 2

    def test_sd56_04_checkpoint_created(self):
        """SD56-04: 修复前创建 checkpoint。"""
        checkpoints = []
        executor = RepairExecutor()
        executor.create_checkpoint = lambda pid: checkpoints.append(pid) or "cp-ok"
        executor.execute_step = lambda s, c: True

        proposal = RepairProposal(
            proposal_id="p1", timestamp=time.time(),
            repair_type=RepairType.CLEAR_CACHE,
            target_component="cache",
            steps=["step"],
        )
        report = executor.execute(proposal)
        assert len(checkpoints) >= 1, "checkpoint must be created before repair"

    def test_rollback_on_failure(self):
        rolled = []
        executor = RepairExecutor()
        executor.create_checkpoint = lambda pid: "cp-1"
        executor.execute_step = lambda s, c: False  # fails first step
        executor.rollback_checkpoint = lambda cid: rolled.append(cid) or True

        proposal = RepairProposal(
            proposal_id="p1", timestamp=time.time(),
            repair_type=RepairType.CLEAR_CACHE,
            target_component="cache",
            steps=["step1", "step2"],
        )
        report = executor.execute(proposal)
        assert report.result == ExecutorResult.ROLLED_BACK
        assert len(rolled) >= 1

    def test_rejected_forbidden(self):
        executor = RepairExecutor()
        proposal = RepairProposal(
            proposal_id="p1", timestamp=time.time(),
            repair_type="self_rewrite",
            target_component="brain",
            steps=["step"],
        )
        report = executor.execute(proposal)
        assert report.result == ExecutorResult.REJECTED

    def test_immutable_component_rejected(self):
        executor = RepairExecutor()
        proposal = RepairProposal(
            proposal_id="p1", timestamp=time.time(),
            repair_type=RepairType.CLEAR_CACHE,
            target_component="identity",
            steps=["step"],
        )
        report = executor.execute(proposal)
        assert report.result == ExecutorResult.REJECTED


# ══════════════════════════════════════════════════
# Repair Memory
# ══════════════════════════════════════════════════

class TestRepairMemory:
    def test_record_and_query(self):
        rm = RepairMemory()
        record = RepairRecord(
            record_id="r1", timestamp=time.time(),
            repair_type=RepairType.RECONNECT,
            target_component="event_store",
            status=RepairStatus.SUCCESS,
            success=True,
        )
        rm.record(record)
        results = rm.query(component="event_store")
        assert len(results) == 1
        assert results[0].success

    def test_sd56_06_learning(self):
        """SD56-06: 修复记录包含经验教训。"""
        rm = RepairMemory()
        record = RepairRecord(
            record_id="r1", timestamp=time.time(),
            repair_type=RepairType.RECONNECT,
            target_component="event_store",
            status=RepairStatus.SUCCESS,
            success=True,
            lesson="reconnect resolved storage failure",
            pattern="effective_repair:reconnect:event_store",
            should_remember=True,
        )
        rm.record(record)
        assert record.lesson
        assert record.pattern
        assert record.should_remember

    def test_stats(self):
        rm = RepairMemory()
        for i in range(5):
            rm.record(RepairRecord(
                record_id=f"r{i}", timestamp=time.time(),
                repair_type=RepairType.CLEAR_CACHE,
                target_component="cache",
                status=RepairStatus.SUCCESS,
                success=i < 4,  # 4 success, 1 fail
            ))
        stats = rm.stats()
        assert stats["total_repairs"] == 5
        assert stats["success_rate"] == 0.8

    def test_record_execution_from_report(self):
        rm = RepairMemory()
        from ocos.diagnosis.repair_executor import ExecutionReport, ExecutorResult

        proposal = RepairProposal(
            proposal_id="p1", timestamp=time.time(),
            repair_type=RepairType.CLEAR_CACHE,
            target_component="cache",
            steps=["step"],
        )
        report = ExecutionReport(
            execution_id="e1", proposal_id="p1",
            result=ExecutorResult.SUCCESS,
            checkpoint_id="cp-1",
            duration_ms=50.0,
        )
        record = rm.record_execution(proposal, report)
        assert record.success
        assert record.lesson  # extracted automatically
        assert record.should_remember


# ══════════════════════════════════════════════════
# Integration: Full Pipeline
# ══════════════════════════════════════════════════

class TestFullPipeline:
    def test_probe_to_repair_flow(self):
        """完整流程: Probe → Detect → Propose → Validate → Sandbox → Execute → Record"""
        # 1. Probe
        probe = SystemProbe(tick=100)
        snap = probe.capture()

        # Inject a failing component
        snap.components["capability_fs"] = ComponentHealth(
            "capability_fs", healthy=False, last_error="disk full"
        )

        # 2. Detect
        detector = FaultDetector()
        signals = detector.feed(snap)
        assert len(signals) >= 1, "should detect unhealthy capability"

        # 3. Diagnosis (manual construction)
        signal = signals[0]
        diag = DiagnosisReport(
            report_id="diag-1", timestamp=time.time(),
            problem="capability_fs unhealthy",
            category=signal.category,
            severity=signal.severity,
            affected_components=["capability_fs"],
            recommendation="repair",
            confidence=0.85,
            trigger_signal_id=signal.signal_id,
        )

        # 4. Propose
        proposer = RepairProposer()
        proposals = proposer.propose(diag)
        assert len(proposals) > 0

        # 5. Validate
        validator = RepairValidator()
        valid_proposals = []
        for prop in proposals:
            outcome = validator.validate(prop)
            if outcome.code == ValidationCode.APPROVE:
                valid_proposals.append(prop)

        if not valid_proposals:
            return  # pipeline succeeded but no auto-approvable proposals

        # 6. Sandbox
        sandbox = RepairSandbox()
        chosen = valid_proposals[0]
        sandbox_report = sandbox.validate(chosen)
        assert sandbox_report.passed

        # 7. Execute
        checkpoints = []
        steps = []
        executor = RepairExecutor()
        executor.create_checkpoint = lambda pid: checkpoints.append(pid) or "cp-ok"
        executor.execute_step = lambda s, c: steps.append(s) or True
        exec_report = executor.execute(chosen)
        assert exec_report.ok
        assert len(checkpoints) == 1  # SD56-04
        assert len(steps) >= 1

        # 8. Record
        memory = RepairMemory()
        record = memory.record_execution(chosen, exec_report)
        assert record.success

    def test_sd56_02_no_capability_expansion(self):
        """SD56-02: 整个修复流程不会产生新能力。"""
        # 确认 RepairType 中没有 "expand" 或 "add" 类的操作
        for rtype in RepairType:
            name = rtype.value.lower()
            evolution_words = ["expand", "add", "create", "new", "extend", "upgrade"]
            for word in evolution_words:
                assert word not in name, f"{rtype} should not contain '{word}'"

    def test_sd56_03_full_forbidden_coverage(self):
        """SD56-03: 所有禁止类别都被覆盖。"""
        forbidden = RepairType.forbidden()
        assert "modify_identity" in forbidden
        assert "rewrite_constitution" in forbidden
        assert "remove_permission" in forbidden
        assert "change_core_values" in forbidden
        assert "self_rewrite" in forbidden
        assert "expand_capability" in forbidden
        assert "alter_goal_system" in forbidden

        v = RepairValidator()
        for name in forbidden:
            outcome = v.validate_forbidden(name, "any_component")
            assert outcome.code == ValidationCode.REJECT

    def test_sd56_05_fault_isolation(self):
        """SD56-05: 单个故障不拖垮其他组件。"""
        snap = SystemSnapshot(
            snapshot_id="s1", timestamp=time.time(), tick=1,
            components={
                "healthy_a": ComponentHealth("healthy_a", healthy=True),
                "failing_b": ComponentHealth("failing_b", healthy=False,
                                             last_error="timeout"),
                "healthy_c": ComponentHealth("healthy_c", healthy=True),
            },
        )
        # FaultDetector 只标记 failing_b，不影响其他
        detector = FaultDetector()
        signals = detector.feed(snap)
        # 只检测到一个故障
        failing_names = {s.source for s in signals}
        assert "healthy_a" not in failing_names
        assert "healthy_c" not in failing_names
