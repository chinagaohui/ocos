"""Phase 51: OCOS v1.0 System Integration Audit.

不建新器官。验证 Phase 39-50 的 12 层是否真正组成了个人认知操作系统。

审计维度:
    1. Architecture Map — 12 层能力矩阵
    2. Integration Tracer — 8 条关键跨层链路追踪
    3. Boundary Checker — 10 条核心原则边界验证
    4. Gap Analyzer — 10 个已知能力缺口
    5. Task Simulator — 10 个端到端任务
    6. Audit Report — Markdown 报告生成

边界:
    AU51-01: Audit ≠ Modification
    AU51-02: Trace ≠ Execution
    AU51-03: Report ≠ Prescription
    AU51-04: Gap ≠ Blocker
"""

from ocos.audit.audit_types import (
    LayerStatus, ConnectionStatus,
    LayerSpec, CapabilityMatrix,
    TraceHop, IntegrationTrace,
    ViolationSeverity, BoundaryViolation,
    GapReport, TaskStep, TaskSimulation, AuditReport,
)
from ocos.audit.architecture_map import ArchitectureMap
from ocos.audit.integration_tracer import IntegrationTracer
from ocos.audit.boundary_checker import BoundaryChecker
from ocos.audit.gap_analyzer import GapAnalyzer
from ocos.audit.task_simulator import TaskSimulator
from ocos.audit.audit_report import AuditReportGenerator


def run_full_audit() -> AuditReport:
    """运行完整 OCOS v1.0 系统集成审计。"""
    generator = AuditReportGenerator()
    return generator.generate()


def audit_report_markdown() -> str:
    """生成 Markdown 审计报告。"""
    generator = AuditReportGenerator()
    generator.generate()
    return generator.markdown_report()


__all__ = [
    "LayerStatus", "ConnectionStatus",
    "LayerSpec", "CapabilityMatrix",
    "TraceHop", "IntegrationTrace",
    "ViolationSeverity", "BoundaryViolation",
    "GapReport", "TaskStep", "TaskSimulation", "AuditReport",
    "ArchitectureMap", "IntegrationTracer",
    "BoundaryChecker", "GapAnalyzer", "TaskSimulator",
    "AuditReportGenerator",
    "run_full_audit", "audit_report_markdown",
]
