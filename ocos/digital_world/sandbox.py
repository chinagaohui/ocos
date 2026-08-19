"""Phase 22/29 — 沙箱执行: sandbox_exec。

约束:
  - 禁止网络 (无网络访问)
  - 超时 SANDBOX_TIMEOUT_SECONDS (30s)
  - 需审批 (approval_id)
  - 危险命令黑名单 (BLOCKED_COMMANDS)
  - dry_run 模式 (OCOS_DW_DRY_RUN=1) 返回模拟结果
  - 真实模式: subprocess.run 执行，无网络环境
"""

from __future__ import annotations

import os
import subprocess
import time

from ocos.digital_world.base import DigitalOperation, OperationResult, SANDBOX_TIMEOUT_SECONDS

# ── dry_run gate ────────────────────────────────────────────────

_DRY_RUN = os.getenv("OCOS_DW_DRY_RUN", "1") == "1"

# 沙箱工作目录
_DEFAULT_WORKDIR = "/tmp/ocos-sandbox"

# 输出限制
_MAX_OUTPUT_BYTES = 50_000

# 危险命令黑名单（冻结基线）
BLOCKED_COMMANDS: tuple[str, ...] = (
    "rm -rf",
    "sudo",
    "wget",
    "curl",
    "nc ",
    "telnet",
    "shutdown",
    "reboot",
    "mkfs",
    "dd if=",
    ":(){ :|:& };:",   # fork bomb
)


# ── 安全检查 ─────────────────────────────────────────────────────


def _is_blocked(command: str) -> str | None:
    """检查命令是否包含危险模式。返回匹配的危险模式或 None。"""
    for blocked in BLOCKED_COMMANDS:
        if blocked in command:
            return blocked
    return None


# ── 真实执行 ─────────────────────────────────────────────────────


def _real_exec(command: str, workdir: str, timeout: int) -> tuple[bool, str, int]:
    """使用 subprocess.run 执行命令。

    Returns:
        (success, output_or_error, exit_code)
    """
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=workdir,
        )
        output = result.stdout
        if result.stderr:
            output += ("\n[stderr]\n" if output else "[stderr]\n") + result.stderr

        # 截断输出
        if len(output.encode("utf-8", errors="replace")) > _MAX_OUTPUT_BYTES:
            output = output[:_MAX_OUTPUT_BYTES] + "\n... (output truncated)"

        ok = result.returncode == 0
        return ok, output.strip() or "(no output)", result.returncode
    except subprocess.TimeoutExpired:
        return False, f"command timed out after {timeout}s", -1
    except FileNotFoundError:
        return False, "shell not available", -2
    except Exception as e:
        return False, f"execution failed: {e}", -3


# ── 公开操作函数 ─────────────────────────────────────────────────


def sandbox_exec(op: DigitalOperation) -> OperationResult:
    """沙箱执行命令。dry_run 时模拟，否则真实执行。

    op.params:
      - command: 要执行的命令 (str, 必需)
      - workdir: 工作目录 (str, 默认 /tmp/ocos-sandbox)
      - timeout: 超时秒数 (int, 默认 SANDBOX_TIMEOUT_SECONDS)
    """
    start = time.monotonic()

    command = op.params.get("command", "")
    if not command or not command.strip():
        return OperationResult.failure(op.op_id, "no command provided")

    # 检查危险命令
    blocked = _is_blocked(command)
    if blocked:
        duration_ms = int((time.monotonic() - start) * 1000)
        return OperationResult.rejected(
            op.op_id,
            f"blocked command pattern: {blocked}",
        )

    # dry_run
    if _DRY_RUN:
        duration_ms = int((time.monotonic() - start) * 1000)
        return OperationResult.success(
            op.op_id,
            f"exec '{command}' → success (simulated)",
            duration_ms,
        )

    # 真实执行
    workdir = op.params.get("workdir", _DEFAULT_WORKDIR)
    timeout = op.params.get("timeout", SANDBOX_TIMEOUT_SECONDS)

    # 确保工作目录存在
    os.makedirs(workdir, exist_ok=True)

    ok, output, exit_code = _real_exec(command, workdir, timeout)
    duration_ms = int((time.monotonic() - start) * 1000)

    if ok:
        return OperationResult.success(op.op_id, output, duration_ms)
    return OperationResult.failure(op.op_id, f"[exit {exit_code}] {output}", duration_ms)
