"""Phase 29 — Gate Tests: file_ops。

验证:
  29-F01: file_read within limits
  29-F02: file_read large file truncated
  29-F03: file_read nonexistent → failure
  29-F04: file_write with approval
  29-F05: file_delete protected path
"""

import os
import tempfile
import pytest
from ocos.digital_world.base import DigitalOperation
from ocos.digital_world.file_ops import file_read, file_write, file_delete


def _op(op_type: str, target: str, approval_id: str | None = None, **params):
    return DigitalOperation.create(op_type, target, "G1", params=params, approval_id=approval_id)


# ── 29-F01: file_read within limits ───────────────────────────────

def test_file_read_success():
    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".txt") as f:
        f.write("hello world")
        path = f.name
    try:
        op = _op("file_read", path)
        result = file_read(op)
        assert result.status == "success"
        assert "hello world" in (result.output or "")
    finally:
        os.unlink(path)


# ── 29-F02: file_read truncated ───────────────────────────────────

def test_file_read_truncated():
    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".txt") as f:
        f.write("X" * 5000)
        path = f.name
    try:
        op = _op("file_read", path)
        result = file_read(op)
        assert result.status == "success"
        assert "[TRUNCATED]" in (result.output or "")
    finally:
        os.unlink(path)


# ── 29-F03: file_read nonexistent ─────────────────────────────────

def test_file_read_nonexistent():
    op = _op("file_read", "/tmp/__nonexistent_file_xyz__")
    result = file_read(op)
    assert result.status == "failure"


# ── 29-F04: file_write with approval ──────────────────────────────

def test_file_write_success():
    path = "/tmp/test_dw_write.txt"
    try:
        op = _op("file_write", path, approval_id="A1", content="test content")
        result = file_write(op)
        assert result.status == "success"
        assert os.path.exists(path)
    finally:
        if os.path.exists(path):
            os.unlink(path)


# ── 29-F05: file_delete protected ─────────────────────────────────

def test_file_delete_protected():
    op = _op("file_delete", "/etc/passwd", approval_id="A1")
    result = file_delete(op)
    assert result.status == "rejected"


def test_file_write_protected():
    op = _op("file_write", "/etc/passwd", approval_id="A1", content="x")
    result = file_write(op)
    assert result.status == "rejected"
