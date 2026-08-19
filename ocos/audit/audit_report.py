"""Phase 51: AuditReport — 审计报告生成器。

汇总所有审计维度，生成结构化报告:

    - Architecture Map
    - Capability Matrix
    - Integration Graph
    - Boundary Verification
    - Gap Report
    - Task Simulation Results
    - Risk Assessment
    - V1.1 Roadmap

AU51-03: Report ≠ Prescription — 报告发现，不自动修复。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ocos.audit.audit_types import (
    AuditReport, CapabilityMatrix,
    IntegrationTrace, BoundaryViolation, GapReport, TaskSimulation,
)
from ocos.audit.architecture_map import ArchitectureMap
from ocos.audit.integration_tracer import IntegrationTracer
from ocos.audit.boundary_checker import BoundaryChecker
from ocos.audit.gap_analyzer import GapAnalyzer
from ocos.audit.task_simulator import TaskSimulator


@dataclass
class AuditReportGenerator:
    """完整审计报告生成器。

    运行全部六个审计维度，生成最终报告。
    """

    report: AuditReport = field(default_factory=AuditReport)

    def generate(self) -> AuditReport:
        """运行完整审计。"""
        # 1. Architecture Map
        arch = ArchitectureMap()
        matrix = arch.audit_all()

        # 2. Integration Tracer
        tracer = IntegrationTracer()
        traces = tracer.trace_all(_matrix=matrix)

        # 3. Boundary Checker
        boundary = BoundaryChecker()
        violations = boundary.check_all()

        # 4. Gap Analyzer
        gap_analyzer = GapAnalyzer()
        gaps = gap_analyzer.analyze()

        # 5. Task Simulator
        simulator = TaskSimulator()
        simulations = simulator.run_all()

        # 6. Calculate grade
        grade = self._calculate_grade(matrix, traces, violations, gaps, simulations)

        self.report = AuditReport(
            version="1.0.0",
            audit_date="2026-07-26",
            capability_matrix=matrix,
            integration_traces=traces,
            boundary_violations=violations,
            gap_reports=gaps,
            task_simulations=simulations,
            overall_grade=grade,
            risk_assessment=self._assess_risk(violations, gaps),
            v1_1_roadmap=gap_analyzer.roadmap(),
            summary=self._generate_summary(matrix, traces, violations, gaps, simulations),
        )
        return self.report

    def _calculate_grade(
        self,
        matrix: CapabilityMatrix,
        traces: list[IntegrationTrace],
        violations: list[BoundaryViolation],
        gaps: list[GapReport],
        simulations: list[TaskSimulation],
    ) -> str:
        score = 0.0
        total = 5.0

        # 架构完整性 (权重 1)
        score += matrix.overall_score

        # 集成追踪 (权重 1)
        if traces:
            complete = sum(1 for t in traces if t.complete)
            score += complete / len(traces)

        # 边界验证 (权重 1)
        critical = [v for v in violations
                    if v.severity.value == "critical"]
        score += 1.0 if len(critical) == 0 else 0.0

        # 缺口 (权重 1)
        critical_gaps = [g for g in gaps if g.priority == "critical"]
        score += 1.0 if len(critical_gaps) == 0 else 0.5

        # 任务模拟 (权重 1)
        if simulations:
            passed = sum(1 for s in simulations if s.passed)
            score += passed / len(simulations)

        final = score / total
        if final >= 0.9:
            return "PASS"
        elif final >= 0.7:
            return "PASS_WITH_GAPS"
        return "FAIL"

    def _assess_risk(
        self, violations: list[BoundaryViolation], gaps: list[GapReport],
    ) -> str:
        critical_v = [v for v in violations
                      if v.severity.value == "critical"]
        critical_g = [g for g in gaps if g.priority == "critical"]

        risks: list[str] = []
        if critical_v:
            risks.append(f"{len(critical_v)} critical boundary violation(s)")
        if critical_g:
            risks.append(f"{len(critical_g)} critical gap(s)")

        if not risks:
            return "No critical risks detected. OCOS v1.0 architecture is intact."

        return "Risks identified: " + "; ".join(risks) + ". Address before v1.1."

    def _generate_summary(
        self,
        matrix: CapabilityMatrix,
        traces: list[IntegrationTrace],
        violations: list[BoundaryViolation],
        gaps: list[GapReport],
        simulations: list[TaskSimulation],
    ) -> str:
        lines = [
            "═══ OCOS v1.0 Architecture Audit Summary ═══",
            "",
            f"Architecture: {matrix.existing_count}/{matrix.total_layers} layers exist "
            f"(score: {matrix.overall_score})",
            f"Integration: {sum(1 for t in traces if t.complete)}/{len(traces)} traces complete",
            f"Boundaries: {len(violations)} violations ({len([v for v in violations if v.severity.value == 'critical'])} critical)",
            f"Gaps: {len(gaps)} identified ({len([g for g in gaps if g.priority == 'critical'])} critical)",
            f"Tasks: {sum(1 for s in simulations if s.passed)}/{len(simulations)} simulations passed",
            f"Grade: {self.report.overall_grade}",
        ]
        return "\n".join(lines)

    def markdown_report(self) -> str:
        """生成完整 Markdown 审计报告。"""
        r = self.report
        m = r.capability_matrix

        md = [
            "# OCOS v1.0 Architecture Audit Report",
            f"**Date**: {r.audit_date}",
            f"**Overall Grade**: {r.overall_grade}",
            "",
            "## 1. Architecture Map",
            "",
            f"- **Layers**: {m.total_layers}",
            f"- **Existing**: {m.existing_count}",
            f"- **Connected**: {m.connected_count}",
            f"- **Verified**: {m.verified_count}",
            f"- **Missing**: {m.missing_count}",
            f"- **Score**: {m.overall_score}",
            "",
            "## 2. Capability Matrix",
            "",
            "| Phase | Layer | Status | Design Goal |",
            "|-------|-------|--------|-------------|",
        ]
        for layer in sorted(m.layers, key=lambda l: l.phase):
            md.append(f"| {layer.phase} | {layer.name} | {layer.status.value} | {layer.design_goal} |")

        md.extend([
            "",
            "## 3. Integration Traces",
            "",
        ])
        for t in r.integration_traces:
            status = "PASS" if t.complete else f"BROKEN at hop {t.broken_at}"
            md.append(f"- **{t.name}**: {status} ({t.hop_count} hops)")

        md.extend([
            "",
            "## 4. Boundary Verification",
            "",
        ])
        if not r.boundary_violations:
            md.append("- No boundary violations detected.")
        else:
            for v in r.boundary_violations:
                md.append(f"- [{v.severity.value.upper()}] {v.boundary}: {v.description}")

        md.extend([
            "",
            "## 5. Gap Report",
            "",
        ])
        for g in r.gap_reports:
            md.append(f"- [{g.priority.upper()}] {g.gap_id}: {g.description}")

        md.extend([
            "",
            "## 6. Task Simulations",
            "",
            f"- **Passed**: {sum(1 for s in r.task_simulations if s.passed)}/{len(r.task_simulations)}",
        ])
        for s in r.task_simulations:
            status = "PASS" if s.passed else "FAIL"
            layers = ", ".join(s.layers_involved)
            md.append(f"- {status} {s.task_id} {s.task_name} ({len(s.steps)} steps, layers: {layers})")

        md.extend([
            "",
            "## 7. Risk Assessment",
            "",
            r.risk_assessment,
            "",
            "## 8. V1.1 Roadmap",
            "",
        ])
        for item in r.v1_1_roadmap:
            md.append(f"- {item}")

        return "\n".join(md)


__all__ = ["AuditReportGenerator"]
