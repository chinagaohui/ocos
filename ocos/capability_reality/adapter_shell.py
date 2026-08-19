"""Phase 55: ShellAdapter — 真实 Shell 执行适配器。

提供:
    shell_exec  — 执行 shell 命令 (沙盒: 限制目录、超时、输出大小)
    shell_pipe — 管道模式 (未来)
"""

from __future__ import annotations

import subprocess
import os

from ocos.capability_reality.adapter_types import (
    CapabilityDescriptor, AdapterHealth,
    ExecutionContext, ExecutionResult, ExecutionStatus,
    CapabilityCategory, AdapterConfig,
)
from ocos.capability_reality.capability_adapter import CapabilityAdapter


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

        # 危险命令检查
        self._check_dangerous(command)

        # 沙盒: 限制工作目录
        if self.config.sandboxed:
            workdir = self._resolve_workdir(workdir)
            cmd = f"cd {workdir} && {command}"
        else:
            cmd = command

        try:
            proc = subprocess.run(
                cmd,
                shell=True,
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
        """将工作目录解析到安全根内。"""
        resolved = os.path.abspath(os.path.expanduser(workdir))
        if not any(resolved.startswith(root) for root in self.safe_roots):
            # 使用第一个安全根作为默认
            resolved = self.safe_roots[0]
        return resolved

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
