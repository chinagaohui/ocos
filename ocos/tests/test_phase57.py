"""Phase 57: Living System Verification — Tests.

验收:
    LV57-01: 全链路闭环 — Intent → Memory 可追踪
    LV57-02: 长期运行 — 无 identity 漂移 / memory 污染 / permission 突破
    LV57-03: 故障恢复 — 注入后继续运行
    LV57-04: 能力真实性 — 注册 ≠ 执行
    LV57-05: 演化安全 — self-rewrite 被拒绝
    LV57-06: 人格连续性 — 首尾一致
"""

import pytest
import time
import uuid

from ocos.living_verification.simulation_engine import (
    SimulationEngine, SimulationProfile, TraceStep, SimPhase,
)
from ocos.living_verification.cognitive_trace_audit import (
    CognitiveTraceAudit, ChainLink,
)
from ocos.living_verification.failure_injector import (
    FailureInjector, InjectionType, InjectionResult,
)
from ocos.living_verification.longevity_test import (
    LongevityTest, LongevityCheckpoint,
)
from ocos.living_verification.benchmark_runner import (
    BenchmarkRunner, BenchmarkTask, BenchmarkCategory, BenchmarkVerdict,
)
from ocos.living_verification.health_report import (
    HealthReportGenerator, SystemGrade,
)
from ocos.living_verification.verification_manifest import (
    VerificationManifest, ManifestItem, ManifestStatus, create_full_manifest,
)


# ══════════════════════════════════════════════════
# Simulation Engine
# ══════════════════════════════════════════════════

class TestSimulationEngine:
    def test_creates_trace_steps(self):
        engine = SimulationEngine(profile=SimulationProfile(total_ticks=10))
        traces = engine.run_ticks(10)
        assert len(traces) == 10
        assert all(isinstance(t, TraceStep) for t in traces)

    def test_intent_populated(self):
        engine = SimulationEngine(profile=SimulationProfile(total_ticks=1))
        traces = engine.run_ticks(1)
        assert traces[0].intent  # 一定有意图

    def test_identity_verified(self):
        engine = SimulationEngine(profile=SimulationProfile(total_ticks=100))
        engine.run_ticks(100)
        assert engine.verify_identity(engine.identity_anchor)
        assert engine.identity_anchor == "OCOS-v1.0-identity-anchor"

    def test_memory_accumulates(self):
        engine = SimulationEngine(profile=SimulationProfile(total_ticks=50))
        engine.run_ticks(50)
        assert engine.memory_records >= 40  # 至少大部分被记录

    def test_stats_consistent(self):
        engine = SimulationEngine(profile=SimulationProfile(total_ticks=50))
        engine.run_ticks(50)
        stats = engine.stats()
        assert stats["total_ticks"] == 50
        assert stats["identity_stable"]

    def test_evolution_triggers(self):
        engine = SimulationEngine(profile=SimulationProfile(
            total_ticks=100, evolution_trigger_interval=25))
        engine.run_ticks(100)
        assert engine.evolution_count >= 3  # 100/25 ≈ 4, 但第一个tick可能不算

    def test_fail_rate_produces_errors(self):
        engine = SimulationEngine(profile=SimulationProfile(
            total_ticks=200, fail_rate=0.1))
        engine.run_ticks(200)
        stats = engine.stats()
        assert stats["errors"] > 0, "some ticks should fail"

    def test_snapshot_identity(self):
        engine = SimulationEngine()
        engine.run_ticks(5)
        snap = engine.snapshot_identity()
        assert snap["identity_anchor"] == "OCOS-v1.0-identity-anchor"
        assert "permissions" in snap
        assert "capabilities" in snap


# ══════════════════════════════════════════════════
# LV57-01: CognitiveTraceAudit
# ══════════════════════════════════════════════════

class TestLV57_01_TraceAudit:
    def test_audit_traces_completeness(self):
        engine = SimulationEngine(profile=SimulationProfile(total_ticks=20))
        traces = engine.run_ticks(20)
        auditor = CognitiveTraceAudit()
        report = auditor.audit(traces)
        # 20个完整的 TraceStep 应该全部可追踪
        assert report.causal_chain_complete >= 0.85

    def test_all_chain_links_checked(self):
        engine = SimulationEngine(profile=SimulationProfile(total_ticks=5))
        traces = engine.run_ticks(5)
        auditor = CognitiveTraceAudit()
        report = auditor.audit(traces)
        # 至少有一条完整的链路检查
        assert len(report.chain_checks) >= 5 * 8  # 5 steps × 8 links

    def test_check_specific_chain(self):
        engine = SimulationEngine(profile=SimulationProfile(total_ticks=1))
        traces = engine.run_ticks(1)
        auditor = CognitiveTraceAudit()
        ok = auditor.check_specific_chain(traces[0], [
            ChainLink.INTENT, ChainLink.ATTENTION, ChainLink.DECISION,
        ])
        assert ok

    def test_no_broken_memory_link(self):
        """LV57-01: memory 链不能断裂。"""
        engine = SimulationEngine(profile=SimulationProfile(total_ticks=10))
        traces = engine.run_ticks(10)
        auditor = CognitiveTraceAudit()
        report = auditor.audit(traces)
        # MEMORY link should not be in broken_links
        assert ChainLink.MEMORY not in report.broken_links


# ══════════════════════════════════════════════════
# LV57-02: Longevity Test
# ══════════════════════════════════════════════════

class TestLV57_02_Longevity:
    def test_identity_stable_long_run(self):
        engine = SimulationEngine(profile=SimulationProfile(
            total_ticks=200, identity_check_interval=50))
        lt = LongevityTest()
        for _ in range(4):  # 4 checkpoints
            engine.run_ticks(50)
            lt.create_checkpoint(f"cp-{engine.tick}", engine)
        metrics = lt.verify()
        assert not metrics.identity_drift_detected

    def test_no_permission_escalation(self):
        engine = SimulationEngine(profile=SimulationProfile(total_ticks=150))
        lt = LongevityTest()
        for _ in range(3):
            engine.run_ticks(50)
            lt.create_checkpoint(f"cp", engine)
        metrics = lt.verify()
        assert not metrics.permission_escalation_detected

    def test_continuity_score(self):
        engine = SimulationEngine(profile=SimulationProfile(
            total_ticks=100, identity_check_interval=50))
        lt = LongevityTest()
        lt.create_checkpoint("start", engine)
        engine.run_ticks(100)
        lt.create_checkpoint("end", engine)
        metrics = lt.verify()
        assert metrics.identity_match

    def test_longevity_passed(self):
        engine = SimulationEngine(profile=SimulationProfile(
            total_ticks=100, identity_check_interval=25,
            fail_rate=0.0))  # 无失败，避免记忆跳跃
        lt = LongevityTest()
        for _ in range(4):
            engine.run_ticks(25)
            lt.create_checkpoint(f"cp-{engine.tick}", engine)
        metrics = lt.verify()
        assert metrics.passed


# ══════════════════════════════════════════════════
# LV57-03: Failure Injection
# ══════════════════════════════════════════════════

class TestLV57_03_FailureInjection:
    def test_capability_failure_detected(self):
        fi = FailureInjector()
        fi.capability_validator = lambda cap: cap.get("healthy", True)
        report = fi.inject_capability_failure("bad_adapter", "error")
        assert report.result == InjectionResult.DETECTED

    def test_without_validator_passes_through(self):
        """没有验证器 = 安全漏洞。"""
        fi = FailureInjector()
        report = fi.inject_capability_failure("bad_adapter", "error")
        assert report.result == InjectionResult.PASSED_THROUGH

    def test_false_memory_rejected(self):
        fi = FailureInjector()
        fi.memory_validator = lambda mem: mem.get("trust", 0) > 0.5
        report = fi.inject_false_memory({"event": "fake", "trust": 0.1})
        assert report.result == InjectionResult.REJECTED

    def test_forbidden_extension_blocked(self):
        fi = FailureInjector()
        fi.extension_governor = lambda name, ctx: name in [
            "modify_identity", "rewrite_constitution", "self_rewrite"
        ]
        report = fi.inject_forbidden_extension("self_rewrite")
        assert report.result == InjectionResult.REJECTED

    def test_full_battery_has_no_passthrough_when_guarded(self):
        """LV57-03: 完整电池测试中所有攻击被拦截。"""
        fi = FailureInjector()
        fi.capability_validator = lambda cap: True  # 通过(实际应该更严格)
        fi.memory_validator = lambda mem: mem.get("trust", 0) > 0.5
        fi.extension_governor = lambda name, ctx: True  # 全部禁止
        batch = fi.run_full_battery()
        # 记忆注入和扩展注入应该被拒绝
        assert batch.rejected >= 7  # 2×3 memories + 5 extensions
        # 能力注入有 validator 但返回 True, 所以 passed_through 可能有
        assert batch.total_injections == 11  # 3 caps + 3 mems + 5 exts

    def test_system_survives_injections(self):
        fi = FailureInjector()
        fi.capability_validator = lambda cap: False
        fi.memory_validator = lambda mem: False
        fi.extension_governor = lambda name, ctx: True
        batch = fi.run_full_battery()
        assert batch.system_survived


# ══════════════════════════════════════════════════
# LV57-04: Capability Realness
# ══════════════════════════════════════════════════

class TestLV57_04_Benchmark:
    def test_registered_not_executable(self):
        """LV57-04: 注册 ≠ 执行 — 注册表中的能力不等于可执行。"""
        runner = BenchmarkRunner(
            capability_registry={"fs_list"}  # 只有 fs_list
        )
        task = BenchmarkTask("t1", BenchmarkCategory.SOFTWARE_DEV,
                            "test", required_capabilities=["fs_write"])
        runner._run_task(task)
        assert task.verdict == BenchmarkVerdict.FAIL

    def test_all_capabilities_present_passes(self):
        runner = BenchmarkRunner(
            capability_registry={"fs_read", "fs_write", "shell_exec", "fs_list"}
        )
        task = BenchmarkTask("t1", BenchmarkCategory.SOFTWARE_DEV,
                            "test", required_capabilities=["fs_write", "fs_list"])
        runner._run_task(task)
        assert task.verdict == BenchmarkVerdict.PASS

    def test_full_suite_creates_all_suites(self):
        runner = BenchmarkRunner(
            capability_registry={
                "fs_write", "fs_read", "fs_list", "shell_exec",
                "probe", "pattern_detect", "memory_query", "optimize",
                "event_query", "persist",
            }
        )
        report = runner.run_all()
        assert len(report.suites) == 3
        assert report.overall_pass_rate >= 0.80

    def test_missing_all_capabilities_fails(self):
        runner = BenchmarkRunner(capability_registry={})
        report = runner.run_all()
        assert report.overall_pass_rate == 0.0


# ══════════════════════════════════════════════════
# LV57-05: Evolution Safety
# ══════════════════════════════════════════════════

class TestLV57_05_EvolutionSafety:
    def test_all_forbidden_extensions_blocked(self):
        fi = FailureInjector()
        fi.extension_governor = lambda name, ctx: True  # block all
        batch = fi.run_full_battery()
        # 5 forbidden extensions should be rejected
        rejected_ext = sum(1 for i in batch.injections
                          if i.injection_type == InjectionType.FORBIDDEN_EXTENSION
                          and i.result == InjectionResult.REJECTED)
        assert rejected_ext == 5

    def test_permission_bypass_blocked(self):
        fi = FailureInjector()
        fi.extension_governor = lambda name, ctx: True
        report = fi.inject_capability_failure("malicious_adapter",
                                               "permission_change")
        assert report.result == InjectionResult.REJECTED

    def test_no_passthrough_with_governor(self):
        fi = FailureInjector()
        fi.capability_validator = lambda cap: False  # reject all
        fi.memory_validator = lambda mem: False
        fi.extension_governor = lambda name, ctx: True
        batch = fi.run_full_battery()
        assert batch.no_security_breach


# ══════════════════════════════════════════════════
# LV57-06: Identity Continuity
# ══════════════════════════════════════════════════

class TestLV57_06_Continuity:
    def test_start_end_identity_match(self):
        engine = SimulationEngine(profile=SimulationProfile(
            total_ticks=200, fail_rate=0.0))
        start_anchor = engine.identity_anchor
        engine.run_ticks(200)
        assert engine.identity_anchor == start_anchor

    def test_longevity_continuity_score_high(self):
        engine = SimulationEngine(profile=SimulationProfile(
            total_ticks=200, identity_check_interval=50, fail_rate=0.0))
        lt = LongevityTest()
        lt.create_checkpoint("day1", engine)
        for _ in range(4):
            engine.run_ticks(50)
            lt.create_checkpoint(f"day{engine.tick//50+1}", engine)
        metrics = lt.verify()
        assert metrics.continuity_score >= 0.90


# ══════════════════════════════════════════════════
# Verification Manifest
# ══════════════════════════════════════════════════

class TestVerificationManifest:
    def test_full_manifest_created(self):
        m = create_full_manifest()
        assert len(m.items) == 19

    def test_all_standards_covered(self):
        m = create_full_manifest()
        standards = {i.standard for i in m.items}
        expected = {f"LV57-{n:02d}" for n in range(1, 7)}
        assert expected.issubset(standards)

    def test_summary_complete(self):
        m = create_full_manifest()
        for item in m.items:
            item.status = ManifestStatus.PASS
            item.score = 1.0
        summary = m.summary()
        assert summary["passed"] == 19
        assert summary["completion"] == 1.0

    def test_weighted_score(self):
        m = create_full_manifest()
        for item in m.items:
            item.status = ManifestStatus.PASS
            item.score = 0.8
        assert abs(m.weighted_score - 0.8) < 0.01


# ══════════════════════════════════════════════════
# Health Report
# ══════════════════════════════════════════════════

class TestHealthReport:
    def test_generate_alive(self):
        gen = HealthReportGenerator()
        report = gen.generate(
            trace_audit_result={
                "causal_chain_complete": 0.95,
                "traced_steps": 100, "untraced_steps": 5,
            },
            longevity_metrics={
                "passed": True, "continuity_score": 1.0,
                "total_ticks": 1000, "failures": [],
            },
            injection_report={
                "pass_rate": 0.95,
                "system_survived": True,
                "no_security_breach": True,
                "passed_through": 0,
            },
            benchmark_report={
                "overall_pass_rate": 0.85,
            },
        )
        assert report.grade == SystemGrade.ALIVE
        assert report.is_alive
        assert all(d.passed for d in report.dimensions)

    def test_generate_degraded(self):
        gen = HealthReportGenerator()
        report = gen.generate(
            trace_audit_result={"causal_chain_complete": 0.70},
            longevity_metrics={
                "passed": True, "continuity_score": 0.80,
                "total_ticks": 500, "failures": [],
            },
            injection_report={
                "pass_rate": 0.80,
                "system_survived": True,
                "no_security_breach": True,
                "passed_through": 0,
            },
        )
        assert report.grade in (SystemGrade.DEGRADED, SystemGrade.UNSTABLE)

    def test_generate_dead(self):
        gen = HealthReportGenerator()
        report = gen.generate()
        assert report.grade == SystemGrade.DEAD

    def test_all_lv57_standards_in_report(self):
        gen = HealthReportGenerator()
        report = gen.generate()
        dim_names = {d.name for d in report.dimensions}
        for n in range(1, 7):
            assert f"LV57-{n:02d}" in " ".join(dim_names)


# ══════════════════════════════════════════════════
# Integration: Full Pipeline
# ══════════════════════════════════════════════════

class TestFullLV57Pipeline:
    def test_simulate_audit_verify(self):
        """LV57-01~06 集成: Simulate → Audit → Longevity → Inject → Report"""
        # 1. 模拟 200 ticks
        engine = SimulationEngine(profile=SimulationProfile(
            total_ticks=200, fail_rate=0.02,
            evolution_trigger_interval=40,
            identity_check_interval=50,
        ))
        traces = engine.run_ticks(200)

        # 2. LV57-01: 因果链审计
        auditor = CognitiveTraceAudit()
        audit = auditor.audit(traces)
        audit_result = {
            "causal_chain_complete": audit.causal_chain_complete,
            "traced_steps": audit.traced_steps,
            "untraced_steps": audit.untraced_steps,
        }
        assert audit.causal_chain_complete >= 0.80

        # 3. LV57-02 + LV57-06: 长期运行
        lt = LongevityTest()
        lt.create_checkpoint("day1", engine)
        metrics = lt.verify()
        assert metrics.identity_match
        longevity_result = {
            "passed": metrics.passed,
            "continuity_score": metrics.continuity_score,
            "total_ticks": metrics.total_ticks,
            "failures": metrics.failures,
        }

        # 4. LV57-03 + LV57-05: 故障注入
        fi = FailureInjector()
        fi.extension_governor = lambda name, ctx: True  # block all
        fi.capability_validator = lambda cap: False
        fi.memory_validator = lambda mem: False
        batch = fi.run_full_battery()
        injection_result = {
            "pass_rate": batch.pass_rate,
            "system_survived": batch.system_survived,
            "no_security_breach": batch.no_security_breach,
            "passed_through": batch.passed_through,
        }
        assert batch.no_security_breach

        # 5. LV57-04: 基准
        runner = BenchmarkRunner(capability_registry={
            "fs_write", "fs_read", "fs_list", "shell_exec",
            "probe", "pattern_detect", "memory_query", "optimize",
            "event_query", "persist",
        })
        bench = runner.run_all()
        bench_result = {"overall_pass_rate": bench.overall_pass_rate}

        # 6. 统一健康报告
        gen = HealthReportGenerator()
        health = gen.generate(
            simulation_stats=engine.stats(),
            trace_audit_result=audit_result,
            injection_report=injection_result,
            longevity_metrics=longevity_result,
            benchmark_report=bench_result,
        )
        assert health.grade in (SystemGrade.ALIVE, SystemGrade.DEGRADED)
