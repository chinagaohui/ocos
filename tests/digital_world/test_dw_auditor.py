"""Phase 29 — Gate Tests: OperationAuditor。

验证:
  29-AU01: audit trail complete
  29-AU02: find by requester
  29-AU03: find by status
"""

from ocos.digital_world.base import DigitalOperation, OperationResult
from ocos.digital_world.auditor import OperationAuditor


def test_audit_trail_complete():
    auditor = OperationAuditor()
    op1 = DigitalOperation.create("file_read", "/tmp/a.txt", "G1")
    op2 = DigitalOperation.create("file_read", "/tmp/b.txt", "G2")
    auditor.record(op1, OperationResult.success(op1.op_id, "ok"))
    auditor.record(op2, OperationResult.failure(op2.op_id, "err"))
    assert len(auditor) == 2
    assert len(auditor.trail) == 2


def test_find_by_requester():
    auditor = OperationAuditor()
    op1 = DigitalOperation.create("file_read", "/tmp/a.txt", "G1")
    op2 = DigitalOperation.create("file_read", "/tmp/b.txt", "G2")
    auditor.record(op1, OperationResult.success(op1.op_id, "ok"))
    auditor.record(op2, OperationResult.success(op2.op_id, "ok"))
    g1_records = auditor.find_by_requester("G1")
    assert len(g1_records) == 1
    assert g1_records[0].requester == "G1"


def test_find_by_status():
    auditor = OperationAuditor()
    op1 = DigitalOperation.create("file_read", "/tmp/a.txt", "G1")
    op2 = DigitalOperation.create("file_read", "/tmp/b.txt", "G1")
    auditor.record(op1, OperationResult.success(op1.op_id, "ok"))
    auditor.record(op2, OperationResult.failure(op2.op_id, "err"))
    successes = auditor.find_by_status("success")
    failures = auditor.find_by_status("failure")
    assert len(successes) == 1
    assert len(failures) == 1
