"""OCOS audit/audit_types 测试。"""

import pytest
from ocos.audit.audit_types import (
    LayerStatus,
    ConnectionStatus,
    LayerSpec,
    CapabilityMatrix,
    TraceHop,
    IntegrationTrace,
    AuditReport,
    BoundaryViolation,
    GapReport,
    ViolationSeverity,
    TaskSimulation,
    TaskStep,
)


class TestLayerStatus:
    def test_values(self):
        assert LayerStatus.EXISTS.value == "exists"
        assert LayerStatus.TESTED.value == "tested"
        assert LayerStatus.CONNECTED.value == "connected"
        assert LayerStatus.VERIFIED.value == "verified"
        assert LayerStatus.MISSING.value == "missing"


class TestConnectionStatus:
    def test_values(self):
        assert ConnectionStatus.NONE.value == "none"
        assert ConnectionStatus.IMPORTABLE.value == "importable"
        assert ConnectionStatus.WIRED.value == "wired"
        assert ConnectionStatus.TRACED.value == "traced"
        assert ConnectionStatus.BROKEN.value == "broken"


class TestLayerSpec:
    def test_defaults(self):
        spec = LayerSpec()
        assert spec.phase == 0
        assert spec.name == ""
        assert spec.design_goal == ""
        assert spec.module_path == ""
        assert spec.status == LayerStatus.EXISTS
        assert spec.connections_in == []
        assert spec.connections_out == []

    def test_custom(self):
        spec = LayerSpec(
            phase=51,
            name="Runtime",
            design_goal="认知循环核心",
            module_path="ocos.runtime",
            connections_in=["kernel"],
            connections_out=["agent"],
        )
        assert spec.phase == 51
        assert spec.connections_in == ["kernel"]


class TestCapabilityMatrix:
    def test_empty_matrix(self):
        matrix = CapabilityMatrix()
        assert matrix.layers == []
        assert matrix.total_layers == 0
        assert matrix.overall_score == 0.0

    def test_counts(self):
        matrix = CapabilityMatrix(
            layers=[
                LayerSpec(phase=10, name="Kernel", status=LayerStatus.VERIFIED),
                LayerSpec(phase=20, name="Memory", status=LayerStatus.CONNECTED),
                LayerSpec(phase=30, name="Goal", status=LayerStatus.MISSING),
            ],
            total_layers=3,
            existing_count=2,
            connected_count=2,
            verified_count=1,
            missing_count=1,
        )
        assert matrix.existing_count == 2
        assert matrix.missing_count == 1


class TestTraceHop:
    def test_defaults(self):
        hop = TraceHop()
        assert hop.from_layer == ""
        assert hop.to_layer == ""
        assert hop.via == ""
        assert hop.status == ConnectionStatus.NONE
        assert hop.detail == ""

    def test_custom(self):
        hop = TraceHop(
            from_layer="kernel",
            to_layer="runtime",
            via="EventBus.publish",
            status=ConnectionStatus.WIRED,
            detail="Direct import",
        )
        assert hop.from_layer == "kernel"
        assert hop.status == ConnectionStatus.WIRED


class TestIntegrationTrace:
    def test_empty_trace(self):
        trace = IntegrationTrace()
        assert trace.trace_id == ""
        assert trace.path == []

    def test_with_hops(self):
        trace = IntegrationTrace(
            trace_id="t1",
            name="Kernel -> Runtime",
            path=[
                TraceHop(from_layer="kernel", to_layer="runtime", status=ConnectionStatus.WIRED),
            ],
        )
        assert trace.trace_id == "t1"
        assert len(trace.path) == 1


class TestAuditReport:
    def test_empty_report(self):
        report = AuditReport()
        assert report.version == "1.0.0"
        assert report.capability_matrix.layers == []
        assert report.integration_traces == []

    def test_with_content(self):
        report = AuditReport(
            version="2.0.0",
            audit_date="2026-09-05",
            overall_grade="PASS",
            summary="System integration complete",
        )
        assert report.version == "2.0.0"
        assert report.overall_grade == "PASS"
        assert report.summary == "System integration complete"


class TestViolationSeverity:
    def test_values(self):
        assert ViolationSeverity.INFO.value == "info"
        assert ViolationSeverity.WARNING.value == "warning"
        assert ViolationSeverity.CRITICAL.value == "critical"


class TestBoundaryViolation:
    def test_defaults(self):
        v = BoundaryViolation()
        assert v.boundary == ""
        assert v.layer == ""
        assert v.description == ""
        assert v.severity == ViolationSeverity.INFO
        assert v.evidence == ""

    def test_custom(self):
        v = BoundaryViolation(
            boundary="import_barrier",
            layer="agent",
            description="Unauthorized import detected",
            severity=ViolationSeverity.CRITICAL,
            evidence="import ocos.kernel from ocos.agent",
        )
        assert v.boundary == "import_barrier"
        assert v.severity == ViolationSeverity.CRITICAL


class TestGapReport:
    def test_defaults(self):
        g = GapReport()
        assert g.gap_id == ""
        assert g.category == ""
        assert g.description == ""
        assert g.priority == "low"

    def test_custom(self):
        g = GapReport(
            gap_id="G001",
            category="attention",
            description="Missing scoring engine",
            impact="High",
            suggested_phase="39.5",
            priority="high",
        )
        assert g.gap_id == "G001"
        assert g.category == "attention"
        assert g.priority == "high"


class TestTaskSimulation:
    def test_defaults(self):
        ts = TaskSimulation()
        assert ts.task_id == ""
        assert ts.steps == []
        assert ts.passed is False

    def test_with_steps(self):
        ts = TaskSimulation(
            task_id="T001",
            task_name="Kernel integration test",
            steps=[
                TaskStep(
                    step_id=1,
                    layer="kernel",
                    action="publish event",
                    expected="received",
                    passed=True,
                ),
            ],
        )
        assert ts.task_id == "T001"
        assert len(ts.steps) == 1
        assert ts.steps[0].passed is True