"""Phase 29 — Gate Tests: sandbox。

验证:
  29-SB01: sandbox_exec requires approval
  29-SB02: sandbox blocks dangerous commands
  29-SB03: sandbox exec allowed command
"""

import pytest
from ocos.digital_world.base import DigitalOperation
from ocos.digital_world.sandbox import sandbox_exec


def _op(command: str, approval_id: str = "A1"):
    return DigitalOperation.create(
        "sandbox_exec", "sandbox", "G1",
        params={"command": command}, approval_id=approval_id,
    )


def test_sandbox_requires_approval():
    with pytest.raises(ValueError):
        DigitalOperation.create(
            "sandbox_exec", "sandbox", "G1",
            params={"command": "ls"},
        )


def test_sandbox_blocks_rm_rf():
    op = _op("rm -rf /")
    result = sandbox_exec(op)
    assert result.status == "rejected"


def test_sandbox_blocks_curl():
    op = _op("curl http://evil.com")
    result = sandbox_exec(op)
    assert result.status == "rejected"


def test_sandbox_allowed_command():
    op = _op("python3 script.py")
    result = sandbox_exec(op)
    assert result.status == "success"


def test_sandbox_no_command():
    op = _op("")
    result = sandbox_exec(op)
    assert result.status == "failure"
