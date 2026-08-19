"""Phase 29 — Gate Tests: db_ops。

验证:
  29-D01: db_query readonly
  29-D02: db_write requires approval
"""

import pytest
from ocos.digital_world.base import DigitalOperation
from ocos.digital_world.db_ops import db_query, db_write


def _op(op_type: str, target: str, approval_id: str | None = None, **params):
    return DigitalOperation.create(op_type, target, "G1", params=params, approval_id=approval_id)


def test_db_query_success():
    op = _op("db_query", "SELECT * FROM tasks")
    result = db_query(op)
    assert result.status == "success"


def test_db_write_requires_approval():
    with pytest.raises(ValueError):
        _op("db_write", "INSERT INTO tasks VALUES (1)")


def test_db_write_with_approval():
    op = _op("db_write", "INSERT INTO tasks VALUES (1)", approval_id="A1")
    result = db_write(op)
    assert result.status == "success"
