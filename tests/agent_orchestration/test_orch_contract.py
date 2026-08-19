"""Phase 28 — Gate Tests: ExecutionContract。

验证:
  28-C01: contract_creation
  28-C02: contract_validation (output_schema)
  28-C03: retry_with_fallback requires fallback_agent_id
  28-C04: timeout_seconds positive
"""

import pytest
from ocos.agent_orchestration.contract import ExecutionContract


# ── 28-C01: contract creation ────────────────────────────────────

def test_contract_creation():
    c = ExecutionContract.create(task_id="T1", agent_id="A1")
    assert c.contract_id.startswith("CONTRACT-")
    assert c.task_id == "T1"
    assert c.agent_id == "A1"
    assert c.retry_policy == "retry_3x"
    assert c.timeout_seconds == 300


# ── 28-C02: output_schema validation ─────────────────────────────

def test_output_schema_validation_pass():
    c = ExecutionContract.create(
        task_id="T1", agent_id="A1",
        output_spec={"outline": "str", "word_count": "int"},
    )
    ok, reason = c.validate_output_schema({"outline": "...", "word_count": 5000})
    assert ok


def test_output_schema_validation_fail():
    c = ExecutionContract.create(
        task_id="T1", agent_id="A1",
        output_spec={"outline": "str", "word_count": "int"},
    )
    ok, reason = c.validate_output_schema({"outline": "..."})
    assert not ok
    assert "word_count" in reason


def test_output_schema_no_spec_always_ok():
    c = ExecutionContract.create(task_id="T1", agent_id="A1")
    ok, reason = c.validate_output_schema({"anything": 1})
    assert ok


# ── 28-C03: retry_with_fallback requires fallback ─────────────────

def test_retry_with_fallback_requires_fallback_id():
    with pytest.raises(ValueError, match="fallback_agent_id"):
        ExecutionContract.create(
            task_id="T1", agent_id="A1",
            retry_policy="retry_with_fallback",
        )


def test_retry_with_fallback_with_fallback_ok():
    c = ExecutionContract.create(
        task_id="T1", agent_id="A1",
        retry_policy="retry_with_fallback",
        fallback_agent_id="A2",
    )
    assert c.fallback_agent_id == "A2"


# ── 28-C04: timeout ──────────────────────────────────────────────

def test_timeout_seconds_must_be_positive():
    with pytest.raises(ValueError):
        ExecutionContract.create(task_id="T1", agent_id="A1", timeout_seconds=0)
