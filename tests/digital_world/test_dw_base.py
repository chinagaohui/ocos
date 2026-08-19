"""Phase 29 — Gate Tests: DigitalOperation / OperationResult / AuditRecord。

验证:
  29-B01: DigitalOperation frozen
  29-B02: OperationResult frozen
  29-B03: approval required for sensitive ops
  29-B04: AuditRecord.from_result
"""

import pytest
from ocos.digital_world.base import (
    DigitalOperation, OperationResult, AuditRecord,
    APPROVAL_REQUIRED,
)


# ── 29-B01: DigitalOperation frozen ───────────────────────────────

def test_operation_frozen():
    op = DigitalOperation.create("file_read", "/tmp/test.txt", "G1")
    with pytest.raises(Exception):
        op.op_type = "file_write"  # type: ignore


def test_operation_invalid_type():
    with pytest.raises(ValueError, match="invalid op_type"):
        DigitalOperation.create("unknown_op", "/tmp/test.txt", "G1")


# ── 29-B02: OperationResult frozen ────────────────────────────────

def test_result_frozen():
    r = OperationResult.success("OP-1", "hello")
    with pytest.raises(Exception):
        r.status = "failure"  # type: ignore


def test_result_invalid_status():
    with pytest.raises(ValueError, match="invalid status"):
        OperationResult(op_id="OP-1", status="unknown")


# ── 29-B03: approval required for sensitive ops ────────────────────

def test_sensitive_ops_require_approval():
    for op_type in APPROVAL_REQUIRED:
        with pytest.raises(ValueError, match="requires approval_id"):
            DigitalOperation.create(op_type, "/tmp/x", "G1")


def test_sensitive_ops_with_approval_ok():
    for op_type in APPROVAL_REQUIRED:
        op = DigitalOperation.create(op_type, "/tmp/x", "G1", approval_id="APPROVED-1")
        assert op.approval_id == "APPROVED-1"


# ── 29-B04: AuditRecord.from_result ───────────────────────────────

def test_audit_record_created():
    op = DigitalOperation.create("file_read", "/tmp/test.txt", "G1")
    result = OperationResult.success(op.op_id, "content")
    audit = AuditRecord.from_result(op, result)
    assert audit.op_id == op.op_id
    assert audit.op_type == "file_read"
    assert audit.status == "success"
