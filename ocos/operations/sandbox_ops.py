"""Phase 22-E — sandbox_ops: 沙盒操作，BLOCKED_COMMANDS 生效。

职责:
  - 命令黑名单 BLOCKED_COMMANDS — 危险命令永久拦截
  - 命令白名单 ALLOWED_COMMANDS — 安全命令可执行
  - 沙盒隔离 — exec 在受限环境中运行
  - 审计日志

安全原则:
  - 黑名单 vs 白名单：白名单优先
  - 白名单为空 = 拒绝所有外部命令
  - 即使白名单通过，也检查黑名单（双重防护）
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from ocos.logging import get_logger

logger = get_logger(__name__)


# ── 黑名单 ────────────────────────────────────────────────────────────────────

BLOCKED_COMMANDS: frozenset[str] = frozenset({
    "rm -rf /",
    "shutdown",
    "reboot",
    "mkfs",
    "dd if=",
    ":(){ :|:& };:",     # fork bomb
    "chmod 777 /",
    "chown -R root /",
    "curl | bash",
    "wget -O - | sh",
    "eval",
    "exec(",
    "__import__('os').system",
    "subprocess.call",
    "os.system",
    "os.popen",
    "os.spawn",
    "os.execl",
    "os.execle",
    "os.execlp",
    "os.execlpe",
    "os.execv",
    "os.execve",
    "os.execvp",
    "os.execvpe",
    "pty.spawn",
    "commands.getoutput",
    "__import__('builtins').__dict__['sys'].modules",
    "compile(",
})

# ── 白名单 ────────────────────────────────────────────────────────────────────

ALLOWED_COMMANDS: frozenset[str] = frozenset({
    "python3 -c \"print",    # safe eval
    "cat",
    "head",
    "tail",
    "wc",
    "grep",
    "find",
    "ls",
    "pwd",
    "whoami",
    "date",
    "uname",
    "env",
    "echo",
    "diff",
    "true",
    "false",
    "sort",
    "uniq",
    # PW-4.1/F1: 只读系统信息命令（宿主机环境分析类任务需要）
    "df",
    "free",
    "uptime",
    "hostname",
    "id",
    "ps",
    # 只读 git（仓库分析类任务需要; commit/push 等写操作不在白名单）
    "git log",
    "git status",
    "git diff",
    "git branch",
})

# 路径沙盒 — 只允许在指定目录内操作
SANDBOX_PATHS: frozenset[str] = frozenset({
    "/tmp/ocos_sandbox/",
    "/home/laogao/Documents/trae_projects/ocos/",
})


# ── 沙盒操作 ──────────────────────────────────────────────────────────────────


@dataclass
class SandboxCommand:
    """沙盒命令。"""
    command: str
    workdir: str = "/tmp/ocos_sandbox"
    timeout: float = 30.0
    env: dict[str, str] = field(default_factory=dict)


@dataclass
class SandboxResult:
    """沙盒执行结果。"""
    command: str
    success: bool
    blocked: bool = False
    block_reason: str = ""
    stdout: str = ""
    stderr: str = ""
    exit_code: Optional[int] = None
    cached: bool = False
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class SandboxAuditRecord:
    """沙盒审计记录。"""
    command: str
    allowed: bool
    reason: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class SandboxOps:
    """安全沙盒 — 命令黑白名单 + 路径限制 + 审计。

    用法:
        sandbox = SandboxOps(strict=True)
        result = sandbox.execute(SandboxCommand(command="ls /tmp"))
    """

    def __init__(self, strict: bool = True):
        self._strict = strict
        self._audit_log: list[SandboxAuditRecord] = []

    @property
    def audit_log(self) -> list[SandboxAuditRecord]:
        return list(self._audit_log)

    def execute(self, cmd: SandboxCommand) -> SandboxResult:
        """在沙盒中执行命令（经黑白名单检查）。

        Args:
            cmd: 沙盒命令

        Returns:
            SandboxResult
        """
        # ── 黑名单检查 ──────────────────────────────────────────
        for blocked in BLOCKED_COMMANDS:
            if blocked in cmd.command:
                self._audit_log.append(SandboxAuditRecord(
                    command=cmd.command,
                    allowed=False,
                    reason=f"Matched blocked command: {blocked}",
                ))
                logger.warning("SandboxOps: BLOCKED — %s (match: %s)", cmd.command, blocked)
                return SandboxResult(
                    command=cmd.command,
                    success=False,
                    blocked=True,
                    block_reason=f"Command blocked: matches '{blocked}' in BLOCKED_COMMANDS",
                )

        # ── 白名单检查 ──────────────────────────────────────────
        if not self._is_allowed(cmd.command):
            self._audit_log.append(SandboxAuditRecord(
                command=cmd.command,
                allowed=False,
                reason="Not in ALLOWED_COMMANDS",
            ))
            logger.warning("SandboxOps: Not in whitelist — %s", cmd.command)
            if self._strict:
                return SandboxResult(
                    command=cmd.command,
                    success=False,
                    blocked=True,
                    block_reason="Command not in allowed list",
                )

        # ── 路径检查 ────────────────────────────────────────────
        if not self._is_path_allowed(cmd.workdir):
            return SandboxResult(
                command=cmd.command,
                success=False,
                blocked=True,
                block_reason=f"Working directory not in sandbox: {cmd.workdir}",
            )

        # ── 真实执行 ────────────────────────────────────────────
        try:
            import subprocess as sp

            proc = sp.run(
                cmd.command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=cmd.timeout,
                cwd=cmd.workdir,
                env=({**cmd.env} if cmd.env else None),
            )

            self._audit_log.append(SandboxAuditRecord(
                command=cmd.command,
                allowed=True,
                reason="executed",
            ))

            return SandboxResult(
                command=cmd.command,
                success=proc.returncode == 0,
                stdout=proc.stdout[:10000],
                stderr=proc.stderr[:10000],
                exit_code=proc.returncode,
            )

        except sp.TimeoutExpired:
            return SandboxResult(
                command=cmd.command,
                success=False,
                stderr=f"Timeout after {cmd.timeout}s",
            )
        except Exception as e:
            logger.error("SandboxOps: exec failed: %s", e)
            return SandboxResult(
                command=cmd.command,
                success=False,
                stderr=str(e)[:500],
            )

    @staticmethod
    def _is_allowed(command: str) -> bool:
        """检查命令是否在白名单中（前缀匹配）。"""
        for allowed in ALLOWED_COMMANDS:
            if command.strip().startswith(allowed):
                return True
        return False

    @staticmethod
    def _is_path_allowed(path: str) -> bool:
        """检查路径是否在沙盒内。"""
        import os
        abs_path = os.path.abspath(path)
        for sandbox in SANDBOX_PATHS:
            if abs_path.startswith(os.path.abspath(sandbox)):
                return True
        return False

    def get_history(self, limit: int = 20) -> list[SandboxAuditRecord]:
        return self._audit_log[-limit:]

    def clear_history(self) -> None:
        self._audit_log.clear()
