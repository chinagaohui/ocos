"""S2.10: Audit 规则字段补齐回归（白皮书 P2）。

核查结论：Rule2 依赖的 governance_audit_id 与 Rule5 依赖的
related_halt_audit_id 在当前代码库中均无真实写入点（后者要求的
recover/reset 类 SYSTEM 事件在 kernel.abi.EventType 中不存在）——
两条规则移出默认集（虚假阴性/单向规则），检查函数保留供链接设计
落地后复用。
"""

from __future__ import annotations

from ocos.kernel.abi import EventType
from ocos.platform.audit_models import (
    AuditRecord, AuditRecordType,
)
from ocos.platform.audit_rule_engine import (
    AuditRuleEngine, _check_emergency_recovery,
    _check_permission_consistency, load_default_audit_rules,
)


def _system_record(audit_id: str, event_type: str,
                   details: dict | None = None) -> AuditRecord:
    return AuditRecord(
        audit_id=audit_id,
        record_type=AuditRecordType.SYSTEM.value,
        source="probe",
        timestamp="2026-09-05T00:00:00+00:00",
        summary=f"system {event_type}",
        related_trace_ids=(),
        related_event_ids=(),
        details={"event_type": event_type, **(details or {})},
    )


class TestRule5CheckFunction:
    """直接验证检查函数逻辑（默认集外，字段填齐后行为正确）。"""

    def test_halt_without_recovery_fires(self):
        halt = _system_record("AUD-halt", EventType.EMERGENCY_HALT.value)
        findings = _check_emergency_recovery([halt])
        assert len(findings) == 1
        assert findings[0].rule_id == "audit_rule_emergency_recovery"

    def test_halt_with_recovery_reference_clean(self):
        """恢复记录携带 related_halt_audit_id → 无 finding（字段回填后
        的预期行为）。"""
        halt = _system_record("AUD-halt", EventType.EMERGENCY_HALT.value)
        recover = _system_record(
            "AUD-recover", "system.recovered",  # 假想的未来事件类型
            {"related_halt_audit_id": "AUD-halt"})
        findings = _check_emergency_recovery([halt, recover])
        assert findings == []


class TestRule2CheckFunction:
    def test_rejected_governance_with_execution_fires(self):
        gov = AuditRecord(
            audit_id="AUD-gov", record_type=AuditRecordType.GOVERNANCE.value,
            source="p", timestamp="t", summary="g",
            related_trace_ids=(), related_event_ids=(),
            details={"outcome": "rejected"})
        decision = AuditRecord(
            audit_id="AUD-dec", record_type=AuditRecordType.DECISION.value,
            source="p", timestamp="t", summary="d",
            related_trace_ids=(), related_event_ids=(),
            details={"governance_audit_id": "AUD-gov"})
        findings = _check_permission_consistency([gov, decision])
        assert len(findings) == 1


class TestDefaultRuleSet:
    def test_rule2_rule5_not_in_defaults(self):
        re_ = AuditRuleEngine()
        re_.reset()
        load_default_audit_rules(re_)
        assert "audit_rule_permission_consistency" not in re_.rules
        assert "audit_rule_emergency_recovery" not in re_.rules

    def test_remaining_three_rules_registered(self):
        re_ = AuditRuleEngine()
        re_.reset()
        load_default_audit_rules(re_)
        assert len(re_.rules) == 3
