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
import shlex
import subprocess
import time

from ocos.digital_world.base import DigitalOperation, OperationResult, SANDBOX_TIMEOUT_SECONDS

# ── dry_run gate ────────────────────────────────────────────────

_DRY_RUN = os.getenv("OCOS_DW_DRY_RUN", "1") == "1"

# 沙箱工作目录
_DEFAULT_WORKDIR = "/tmp/ocos-sandbox"

# 输出限制
_MAX_OUTPUT_BYTES = 50_000

# S1.7 (白皮书 P1-12): 默认只读白名单 — 黑名单仅作第二层兜底。
# OCOS_DW_SHELL_WHITELIST 可覆盖（逗号分隔命令前缀）。
_DEFAULT_DW_WHITELIST: tuple[str, ...] = (
    "cat", "ls", "echo", "grep", "head", "tail", "wc", "find", "uname",
    "df", "free", "uptime", "ps", "whoami", "date", "hostname", "id",
)

# shell 元字符 — 命中即拒（默认路径 shell=False 列表执行，无需 shell 语法）
_DW_METACHARS: tuple[str, ...] = (";", "|", "&", "`", "$", ">", "<",
                                  "\n", "\r")

_DW_SENSITIVE_TOKENS = ("/etc/", "/boot/", "/dev/sd", "~/.ssh",
                        "shadow", "id_rsa")


def _load_dw_whitelist() -> tuple[str, ...]:
    raw = os.environ.get("OCOS_DW_SHELL_WHITELIST", "")
    if raw.strip():
        return tuple(w.strip() for w in raw.split(",") if w.strip())
    return _DEFAULT_DW_WHITELIST


def _validate_dw_command(command: str) -> list[str]:
    """S1.7: 白名单 + 元字符 + 敏感路径三重校验，返回安全 token 列表。"""
    metachars = _DW_METACHARS
    for ch in metachars:
        if ch in command:
            raise PermissionError(f"blocked command metacharacter: {ch!r}")
    tokens = shlex.split(command)
    if not tokens:
        raise ValueError("empty command")
    whitelist = _load_dw_whitelist()
    if tokens[0] not in {w.split()[0] for w in whitelist}:
        raise PermissionError(
            f"blocked: command not in whitelist: {tokens[0]} "
            f"(OCOS_DW_SHELL_WHITELIST 可配置)")
    joined = " ".join(tokens).lower()
    for marker in _DW_SENSITIVE_TOKENS:
        if marker.lower() in joined:
            raise PermissionError(f"blocked: sensitive path: {marker}")
    return tokens

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


def _real_exec(command: "str | list[str]", workdir: str,
               timeout: int) -> tuple[bool, str, int]:
    """使用 subprocess.run 执行命令。

    S1.7: sandbox_exec 校验路径传入 token 列表（shell=False）；
    保留 str 入口兼容（内部测试/直调，仍 shell=True）。

    Returns:
        (success, output_or_error, exit_code)
    """
    use_shell = isinstance(command, str)
    try:
        result = subprocess.run(
            command,
            shell=use_shell,
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

    # S1.7: 白名单 + 元字符 + 敏感路径校验（dry_run 与真实模式一致，
    # 让模拟结果如实反映"该命令会被拒"）
    try:
        tokens = _validate_dw_command(command)
    except (PermissionError, ValueError) as e:
        duration_ms = int((time.monotonic() - start) * 1000)
        return OperationResult.rejected(op.op_id, str(e))

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

    ok, output, exit_code = _real_exec(tokens, workdir, timeout)
    duration_ms = int((time.monotonic() - start) * 1000)

    if ok:
        return OperationResult.success(op.op_id, output, duration_ms)
    return OperationResult.failure(op.op_id, f"[exit {exit_code}] {output}", duration_ms)
