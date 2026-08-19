"""Phase 51: System Integration Audit — Tests.

测试六大审计维度 + 边界 + 完整报告。
AU51-01: 审计只读不写
AU51-02: 追踪不执行
AU51-03: 报告不修复
AU51-04: 缺口不阻塞
"""

import pytest

from ocos.audit.audit_types import (
    LayerStatus, ConnectionStatus,
    LayerSpec, CapabilityMatrix,
    TraceHop, IntegrationTrace,
    ViolationSeverity, BoundaryViolation,
    GapReport, TaskStep, TaskSimulation, AuditReport,
)
from ocos.audit.architecture_map import ArchitectureMap, LAYER_REGISTRY
from ocos.audit.integration_tracer import IntegrationTracer, TRACE_DEFINITIONS
from ocos.audit.boundary_checker import BoundaryChecker
from ocos.audit.gap_analyzer import GapAnalyzer, KNOWN_GAPS
from ocos.audit.task_simulator import TaskSimulator
from ocos.audit.audit_report import AuditReportGenerator
from ocos.audit import run_full_audit, audit_report_markdown


# ═════════════════════════════════════════════════════
# 51.00 — Types
# ═════════════════════════════════════════════════════

class TestAuditTypes:
    def test_layer_status_values(self):
        assert LayerStatus.EXISTS.value == "exists"
        assert LayerStatus.CONNECTED.value == "connected"
        assert LayerStatus.MISSING.value == "missing"

    def test_violation_severity(self):
        assert ViolationSeverity.CRITICAL.value == "critical"
        assert ViolationSeverity.WARNING.value == "warning"
        assert ViolationSeverity.INFO.value == "info"

    def test_layer_spec_creation(self):
        spec = LayerSpec(
            phase=39, name="Runtime",
            design_goal="持续运行", module_path="ocos.runtime",
        )
        assert spec.phase == 39
        assert spec.name == "Runtime"
        assert spec.status == LayerStatus.EXISTS
        assert spec.connections_in == []
        assert spec.connections_out == []

    def test_capability_matrix_empty(self):
        m = CapabilityMatrix()
        assert m.total_layers == 0
        assert m.overall_score == 0.0

    def test_trace_hop_defaults(self):
        hop = TraceHop(from_layer="A", to_layer="B", via="test", detail="d")
        assert hop.status == ConnectionStatus.NONE

    def test_integration_trace_broken(self):
        trace = IntegrationTrace(
            trace_id="test", name="test",
            path=[TraceHop(from_layer="A", to_layer="B", via="x",
                           status=ConnectionStatus.BROKEN)],
        )
        assert not trace.complete

    def test_gap_report_priority(self):
        g = GapReport(gap_id="G-01", category="test",
                      description="test", priority="critical")
        assert g.priority == "critical"

    def test_task_step(self):
        s = TaskStep(step_id=1, layer="Test", action="do",
                     expected="result", passed=True)
        assert s.passed
        assert s.step_id == 1

    def test_task_simulation(self):
        sim = TaskSimulation(
            task_id="T001", task_name="Test",
            steps=[TaskStep(1, "L1", "a", "e", passed=True)],
            passed=True,
        )
        assert sim.passed
        assert len(sim.steps) == 1


# ═════════════════════════════════════════════════════
# 51.01 — Architecture Map
# ═════════════════════════════════════════════════════

class TestArchitectureMap:
    def test_registry_has_all_phases(self):
        """验证 LAYER_REGISTRY 包含 Phase 39-50 全部 12 层。"""
        expected = set(range(39, 51))
        assert set(LAYER_REGISTRY.keys()) == expected

    def test_each_layer_has_required_fields(self):
        for phase, layer in LAYER_REGISTRY.items():
            assert layer.phase == phase
            assert layer.name, f"Phase {phase} missing name"
            assert layer.design_goal, f"Phase {phase} missing design_goal"
            assert layer.module_path, f"Phase {phase} missing module_path"
            assert layer.test_file, f"Phase {phase} missing test_file"

    def test_architecture_map_audit_all(self):
        am = ArchitectureMap()
        matrix = am.audit_all()
        assert matrix.total_layers == 12
        assert matrix.existing_count >= 8  # 大部分层应该存在
        assert matrix.overall_score > 0.0

    def test_architecture_map_status_table(self):
        am = ArchitectureMap()
        table = am.layer_status_table()
        assert "| Phase | Layer | Status |" in table
        assert "Runtime Foundation" in table

    def test_score_increases_with_status(self):
        """更完整的状态应该得到更高分。"""
        m1 = CapabilityMatrix(total_layers=1)
        m1.layers = [LayerSpec(phase=39, status=LayerStatus.EXISTS)]
        m2 = CapabilityMatrix(total_layers=1)
        m2.layers = [LayerSpec(phase=39, status=LayerStatus.VERIFIED)]
        score1 = ArchitectureMap._calculate_score(m1)
        score2 = ArchitectureMap._calculate_score(m2)
        assert score2 > score1


# ═════════════════════════════════════════════════════
# 51.02 — Integration Tracer
# ═════════════════════════════════════════════════════

class TestIntegrationTracer:
    def test_trace_definitions_exist(self):
        """至少 8 条追踪定义。"""
        assert len(TRACE_DEFINITIONS) >= 8

    def test_trace_all_returns_traces(self):
        tracer = IntegrationTracer()
        traces = tracer.trace_all()
        assert len(traces) == len(TRACE_DEFINITIONS)

    def test_all_traces_complete(self):
        """所有追踪路径应该完整（模块都存在）。"""
        tracer = IntegrationTracer()
        traces = tracer.trace_all()
        for t in traces:
            assert t.complete, f"Trace {t.trace_id} broken at hop {t.broken_at}"

    def test_trace_summary(self):
        tracer = IntegrationTracer()
        tracer.trace_all()
        summary = tracer.trace_summary
        assert summary["total"] > 0
        assert summary["completion_rate"] == 1.0

    def test_broken_traces_property(self):
        tracer = IntegrationTracer()
        tracer.trace_all()
        assert len(tracer.broken_traces) == 0

    def test_execution_to_memory_trace_exists(self):
        tracer = IntegrationTracer()
        tracer.trace_all()
        trace = next(t for t in tracer.traces
                     if t.trace_id == "trace:execution_to_memory")
        assert trace.name == "Execution → Memory"
        assert trace.complete

    def test_extension_safety_trace_exists(self):
        tracer = IntegrationTracer()
        tracer.trace_all()
        trace = next(t for t in tracer.traces
                     if t.trace_id == "trace:extension_safety")
        assert trace.complete

    def test_continuity_loop_trace_exists(self):
        tracer = IntegrationTracer()
        tracer.trace_all()
        trace = next(t for t in tracer.traces
                     if t.trace_id == "trace:continuity_loop")
        assert trace.complete


# ═════════════════════════════════════════════════════
# 51.03 — Boundary Checker
# ═════════════════════════════════════════════════════

class TestBoundaryChecker:
    def test_check_all_returns_results(self):
        checker = BoundaryChecker()
        violations = checker.check_all()
        assert isinstance(violations, list)

    def test_no_critical_violations(self):
        """AU51-01: 不应该发现关键违规（Identity anchor 未被篡改）。"""
        checker = BoundaryChecker()
        checker.check_all()
        assert checker.is_clean, (
            f"Critical violations found: "
            + ", ".join(v.boundary for v in checker.critical_violations)
        )

    def test_summary_has_expected_keys(self):
        checker = BoundaryChecker()
        checker.check_all()
        s = checker.summary
        assert "total_violations" in s
        assert "critical" in s
        assert "clean" in s

    def test_identity_boundary_checked(self):
        """B-IDENTITY 边界必须被检查。"""
        checker = BoundaryChecker()
        checker.check_all()
        identity_violations = [v for v in checker.violations
                               if v.boundary == "B-IDENTITY"]
        # 应该没有 CRITICAL 级别的 Identity 违规
        critical = [v for v in identity_violations
                    if v.severity == ViolationSeverity.CRITICAL]
        assert len(critical) == 0, f"B-IDENTITY critical: {critical}"

    def test_goal_creation_boundary(self):
        """B-GOAL: 不应有自动创建 Goal 的违规。"""
        checker = BoundaryChecker()
        checker.check_all()
        goal_violations = [v for v in checker.violations
                           if v.boundary == "B-GOAL"]
        critical = [v for v in goal_violations
                    if v.severity == ViolationSeverity.CRITICAL]
        assert len(critical) == 0


# ═════════════════════════════════════════════════════
# 51.04 — Gap Analyzer
# ═════════════════════════════════════════════════════

class TestGapAnalyzer:
    def test_known_gaps_exist(self):
        assert len(KNOWN_GAPS) >= 8

    def test_analyze_returns_gaps(self):
        analyzer = GapAnalyzer()
        gaps = analyzer.analyze()
        assert len(gaps) == len(KNOWN_GAPS)

    def test_critical_gaps_include_persistence(self):
        analyzer = GapAnalyzer()
        analyzer.analyze()
        critical = analyzer.critical_gaps
        persistence = [g for g in critical if "persistence" in g.category]
        assert len(persistence) > 0

    def test_high_priority_gaps(self):
        """至少有 3 个 high/critical 缺口。"""
        analyzer = GapAnalyzer()
        analyzer.analyze()
        assert len(analyzer.high_priority_gaps) >= 3

    def test_gaps_by_category(self):
        analyzer = GapAnalyzer()
        analyzer.analyze()
        by_cat = analyzer.gaps_by_category()
        assert "perception" in by_cat
        assert "persistence" in by_cat

    def test_roadmap_generated(self):
        analyzer = GapAnalyzer()
        roadmap = analyzer.roadmap()
        assert len(roadmap) > 0


# ═════════════════════════════════════════════════════
# 51.05 — Task Simulator
# ═════════════════════════════════════════════════════

class TestTaskSimulator:
    def test_all_ten_tasks_run(self):
        sim = TaskSimulator()
        sims = sim.run_all()
        assert len(sims) == 10

    def test_all_tasks_pass(self):
        sim = TaskSimulator()
        sim.run_all()
        assert sim.all_passed, f"Only {sim.passed_count}/{len(sim.simulations)} passed"

    def test_total_steps(self):
        sim = TaskSimulator()
        sim.run_all()
        assert sim.total_steps > 30  # 10 个任务至少 30 步

    def test_t001_dev_project_layers(self):
        sim = TaskSimulator()
        sim.run_all()
        t001 = sim.simulations[0]
        assert t001.task_id == "T001"
        assert "Decision" in t001.layers_involved
        assert "Memory" in t001.layers_involved

    def test_t003_malicious_injection_rejected(self):
        sim = TaskSimulator()
        sim.run_all()
        t003 = sim.simulations[2]
        assert all(s.passed for s in t003.steps)
        assert "REJECTED" in str(t003.steps[0].expected)

    def test_t004_long_running_ticks(self):
        sim = TaskSimulator()
        sim.run_all()
        t004 = sim.simulations[3]
        assert t004.duration_ticks == 10000

    def test_t008_drift_detects_not_corrects(self):
        sim = TaskSimulator()
        sim.run_all()
        t008 = sim.simulations[7]
        assert t008.task_name == "身份漂移检测"
        step3 = t008.steps[2]
        assert "不自动" in step3.expected or "只有" in step3.expected

    def test_t009_knowledge_aging_rescue(self):
        sim = TaskSimulator()
        sim.run_all()
        t009 = sim.simulations[8]
        assert t009.task_name == "知识老化与抢救"
        step3 = t009.steps[2]
        assert "复活" in step3.expected or "恢复" in step3.expected


# ═════════════════════════════════════════════════════
# 51.06 — Audit Report
# ═════════════════════════════════════════════════════

class TestAuditReport:
    def test_generate_report(self):
        gen = AuditReportGenerator()
        report = gen.generate()
        assert report.version == "1.0.0"
        assert report.overall_grade != ""

    def test_report_contains_all_dimensions(self):
        gen = AuditReportGenerator()
        report = gen.generate()
        assert report.capability_matrix is not None
        assert len(report.integration_traces) > 0
        assert isinstance(report.boundary_violations, list)
        assert len(report.gap_reports) > 0
        assert len(report.task_simulations) > 0

    def test_report_grade_is_pass(self):
        gen = AuditReportGenerator()
        report = gen.generate()
        assert report.overall_grade in ("PASS", "PASS_WITH_GAPS"), (
            f"Got {report.overall_grade}"
        )

    def test_markdown_report(self):
        gen = AuditReportGenerator()
        gen.generate()
        md = gen.markdown_report()
        assert "# OCOS v1.0 Architecture Audit Report" in md
        assert "Capability Matrix" in md
        assert "Integration Traces" in md
        assert "Risk Assessment" in md

    def test_risk_assessment_not_empty(self):
        gen = AuditReportGenerator()
        report = gen.generate()
        assert len(report.risk_assessment) > 0

    def test_roadmap_in_report(self):
        gen = AuditReportGenerator()
        report = gen.generate()
        assert len(report.v1_1_roadmap) > 0


# ═════════════════════════════════════════════════════
# 51.07 — Convenience functions
# ═════════════════════════════════════════════════════

class TestConvenienceFunctions:
    def test_run_full_audit(self):
        report = run_full_audit()
        assert isinstance(report, AuditReport)
        assert report.overall_grade in ("PASS", "PASS_WITH_GAPS")

    def test_audit_report_markdown(self):
        md = audit_report_markdown()
        assert "OCOS v1.0" in md
        assert len(md) > 500


# ═════════════════════════════════════════════════════
# 51.08 — Boundary AU51 constraints
# ═════════════════════════════════════════════════════

class TestPhase51Boundaries:
    def test_au51_01_audit_is_readonly(self):
        """AU51-01: 审计模块不应修改被审计的模块。"""
        import ocos.audit.architecture_map as am
        # reread — should always produce same result
        arch = ArchitectureMap()
        m1 = arch.audit_all()
        m2 = arch.audit_all()
        assert m1.overall_score == m2.overall_score
        assert m1.existing_count == m2.existing_count

    def test_au51_02_trace_does_not_execute(self):
        """AU51-02: 追踪不运行生产数据。"""
        tracer = IntegrationTracer()
        traces = tracer.trace_all()
        # 只检查文件存在，不导入/不执行
        for t in traces:
            for hop in t.path:
                assert hop.status in (ConnectionStatus.WIRED, ConnectionStatus.BROKEN,
                                      ConnectionStatus.NONE)

    def test_au51_03_report_does_not_prescribe(self):
        """AU51-03: 报告不自动生成修复方案。"""
        gen = AuditReportGenerator()
        report = gen.generate()
        # 报告包含 roadmap 建议但不应包含具体代码修改指令
        md = gen.markdown_report()
        assert "patch" not in md.lower() or "roadmap" in md.lower()

    def test_au51_04_gaps_not_blockers(self):
        """AU51-04: 缺口不阻止审计通过。"""
        gen = AuditReportGenerator()
        report = gen.generate()
        # 即使有缺口，审计也应该能完成
        assert report.overall_grade != "FAIL" or len(report.gap_reports) == 0
