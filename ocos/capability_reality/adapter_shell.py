"""Phase 55: ShellAdapter — 真实 Shell 执行适配器。

提供:
    shell_exec  — 执行 shell 命令 (沙盒: 限制目录、超时、输出大小)
    shell_pipe — 管道模式 (未来)
"""

from __future__ import annotations

import shlex
import subprocess
import os
from pathlib import Path

from ocos.capability_reality.adapter_types import (
    CapabilityDescriptor, AdapterHealth,
    ExecutionContext, ExecutionResult, ExecutionStatus,
    CapabilityCategory, AdapterConfig,
)
from ocos.capability_reality.capability_adapter import CapabilityAdapter


# S1.5 (白皮书 P1-3): 默认只读命令白名单 — OCOS_SHELL_WHITELIST 可覆盖
_DEFAULT_SHELL_WHITELIST: tuple[str, ...] = (
    "cat", "ls", "echo", "grep", "head", "tail", "wc", "find", "uname",
    "df", "free", "uptime", "ps", "whoami", "date", "hostname", "id",
    "git status", "git log", "git diff",
    "python3 --version", "python --version",
)

# shell 元字符 — 命中即拒（shell=False 列表执行后不再需要任何 shell 语法）
_SHELL_METACHARS: tuple[str, ...] = (";", "|", "&", "`", "$", ">", "<",
                                     "\n", "\r")

# 敏感路径参数拦截（第二层，与 file_ops PROTECTED_PATHS 对齐）
_SHELL_SENSITIVE_TOKENS = ("/etc/", "/boot/", "/dev/sd", "~/.ssh",
                           "shadow", "id_rsa")


def _load_shell_whitelist() -> tuple[str, ...]:
    raw = os.environ.get("OCOS_SHELL_WHITELIST", "")
    if raw.strip():
        return tuple(w.strip() for w in raw.split(",") if w.strip())
    return _DEFAULT_SHELL_WHITELIST


class ShellAdapter(CapabilityAdapter):
    """真实 Shell 适配器。

    CR55-02: 命令执行隔离，超时/异常不回传。

    沙盒模式:
        - 限制工作目录为 safe_roots
        - 超时强制 kill
        - 输出大小限制
        - 禁止危险命令 (rm -rf /, fork bomb, ...)
    """

    safe_roots: list[str]
    _dangerous_patterns: list[str]

    def __init__(self, safe_roots: list[str] | None = None):
        self.safe_roots = safe_roots or ["/tmp", "/home/laogao/Documents"]
        self._dangerous_patterns = [
            "rm -rf /", "mkfs.", "dd if=", ":(){ :|:& };:",
            "> /dev/sda", "chmod 777 /", "wget -O- | sh",
        ]

        config = AdapterConfig(
            sandboxed=True,
            default_timeout=30,
            max_output_bytes=500_000,
            permissions=["shell_exec"],
        )

        descriptor = CapabilityDescriptor(
            name="shell",
            category=CapabilityCategory.SHELL,
            description="Execute shell commands in sandboxed environment",
            required_params=["command"],
            optional_params=["workdir", "env", "stdin"],
            permissions=config.permissions,
            risk_level=4,
            estimated_duration=2.0,
            reversible=False,
        )

        super().__init__(descriptor=descriptor, config=config)

    def _do_execute(self, ctx: ExecutionContext) -> object:
        command = ctx.params.get("command", "")
        workdir = ctx.params.get("workdir", "/tmp")
        env = ctx.params.get("env", None)
        stdin_data = ctx.params.get("stdin", None)

        if not command:
            raise ValueError("empty command")

        # S1.5: 白名单 + 元字符校验（通过后以 shell=False 列表执行，
        # 彻底消除 shell 注入面）；危险命令黑名单保留为第二层
        tokens = self._validate_command(command)
        self._check_dangerous(command)
        self._check_sensitive_args(tokens)

        # 沙盒: 限制工作目录
        if self.config.sandboxed:
            workdir = self._resolve_workdir(workdir)

        try:
            proc = subprocess.run(
                tokens,
                shell=False,
                capture_output=True,
                text=True,
                timeout=ctx.timeout,
                cwd=workdir,
                env=env,
                input=stdin_data,
            )

            stdout = proc.stdout
            stderr = proc.stderr

            # 输出大小限制
            if len(stdout) > self.config.max_output_bytes:
                stdout = stdout[:self.config.max_output_bytes] + "\n...[TRUNCATED]"

            return {
                "command": command,
                "exit_code": proc.returncode,
                "stdout": stdout,
                "stderr": stderr,
                "ok": proc.returncode == 0,
            }

        except subprocess.TimeoutExpired:
            raise TimeoutError(f"command timed out: {command[:80]}")

    def _check_dangerous(self, command: str) -> None:
        """检查危险命令。"""
        cmd_lower = command.lower().replace(" ", "")
        for pattern in self._dangerous_patterns:
            pattern_clean = pattern.lower().replace(" ", "")
            if pattern_clean in cmd_lower:
                raise PermissionError(f"dangerous command blocked: {pattern}")

    def _resolve_workdir(self, workdir: str) -> str:
        """将工作目录解析到安全根内 — 越界直接报错（不再静默回落）。"""
        resolved = os.path.realpath(os.path.expanduser(workdir))
        for root in self.safe_roots:
            if Path(resolved).is_relative_to(Path(os.path.realpath(root))):
                return resolved
        raise PermissionError(
            f"workdir outside safe roots: {resolved} "
            f"(allowed: {self.safe_roots})")

    def _validate_command(self, command: str) -> list[str]:
        """S1.5: 白名单 + 元字符双重校验，返回可安全执行的 token 列表。

        OCOS_SHELL_ALLOW_PIPE=true 时放行 "|" 管道（管道视为 shell 语法，
        此时退回 shell=True 但逐段白名单校验）。
        """
        allow_pipe = os.environ.get(
            "OCOS_SHELL_ALLOW_PIPE", "").strip().lower() == "true"
        metachars = (_SHELL_METACHARS if not allow_pipe
                     else tuple(m for m in _SHELL_METACHARS if m != "|"))
        for ch in metachars:
            if ch in command:
                raise PermissionError(f"blocked: shell metacharacter {ch!r}")
        whitelist = _load_shell_whitelist()
        segments = command.split("|") if allow_pipe else [command]
        parsed = []
        for seg in segments:
            try:
                tokens = shlex.split(seg)
            except ValueError as e:
                raise PermissionError(f"blocked: command parse error: {e}")
            if not tokens:
                raise ValueError("empty command")
            if not self._whitelisted(tokens, whitelist):
                raise PermissionError(
                    f"blocked: command not in whitelist: {tokens[0]} "
                    f"(OCOS_SHELL_WHITELIST 可配置)")
            parsed.append(tokens)
        if len(parsed) == 1:
            return parsed[0]
        # 管道场景：shell=True 拼回（各段已过白名单与元字符校验）
        return shlex.split(" | ".join(" ".join(t) for t in parsed)) or [command]

    @staticmethod
    def _whitelisted(tokens: list[str], whitelist: tuple[str, ...]) -> bool:
        """首词（或多词条目如 "git status"）前缀匹配。"""
        for entry in whitelist:
            parts = entry.split()
            if len(parts) == 1:
                if tokens[0] == parts[0]:
                    return True
            elif (len(tokens) >= len(parts)
                    and tokens[:len(parts)] == parts):
                return True
        return False

    @staticmethod
    def _check_sensitive_args(tokens: list[str]) -> None:
        """S1.5: 敏感路径参数拦截（防止白名单命令读敏感文件）。"""
        joined = " ".join(tokens).lower()
        for marker in _SHELL_SENSITIVE_TOKENS:
            if marker.lower() in joined:
                raise PermissionError(
                    f"blocked: sensitive path in args: {marker}")

    def _do_health_check(self) -> AdapterHealth:
        """检查 shell 是否可用。"""
        try:
            result = subprocess.run(
                "echo ok", shell=True, capture_output=True, text=True, timeout=2,
            )
            if result.returncode == 0 and "ok" in result.stdout:
                return AdapterHealth.HEALTHY
            return AdapterHealth.DEGRADED
        except Exception:
            return AdapterHealth.FAILED


__all__ = ["ShellAdapter"]
