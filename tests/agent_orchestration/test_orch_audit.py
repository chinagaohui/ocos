"""Phase 28 — Gate Tests: ExecutionAudit。

验证:
  28-A01: audit records created
  28-A02: audit trail complete
  28-A03: records filtered by contract
"""

import pytest
from ocos.agent_orchestration.audit import ExecutionAudit, ExecutionRecord


@pytest.fixture
def audit() -> ExecutionAudit:
    return ExecutionAudit()


# ── 28-A01: audit records created ────────────────────────────────

def test_log_start_creates_record(audit):
    r = audit.log_start("C1", "A1")
    assert r.record_id.startswith("AUDIT-")
    assert r.status == "started"
    assert len(audit) == 1


def test_log_complete_creates_record(audit):
    r = audit.log_complete("C1", "A1", "done")
    assert r.status == "completed"
    assert r.result_summary == "done"
    assert r.completed_at is not None


def test_log_failure_creates_record(audit):
    r = audit.log_failure("C1", "A1", "timeout", retry_count=2)
    assert r.status == "failed"
    assert r.error == "timeout"
    assert r.retry_count == 2


def test_log_timeout_creates_record(audit):
    r = audit.log_timeout("C1", "A1")
    assert r.status == "timed_out"


# ── 28-A02: audit trail complete ─────────────────────────────────

def test_audit_trail_complete(audit):
    audit.log_start("C1", "A1")
    audit.log_complete("C1", "A1", "ok")
    audit.log_start("C2", "A2")
    audit.log_failure("C2", "A2", "crash")
    assert len(audit.trail) == 4


# ── 28-A03: filter by contract ───────────────────────────────────

def test_get_records_for_contract(audit):
    audit.log_start("C1", "A1")
    audit.log_start("C2", "A2")
    audit.log_complete("C1", "A1", "ok")
    c1_records = audit.get_records_for_contract("C1")
    assert len(c1_records) == 2
    for r in c1_records:
        assert r.contract_id == "C1"
