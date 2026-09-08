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
    "lscpu",
    "ip addr",
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


def sandbox_disabled() -> bool:
    """沙盒白名单总开关（2026-09-07，个人使用模式）。

    OCOS_SANDBOX_DISABLED=true/1/yes/on（env 或 ~/.ocos/config.json）→
    跳过白名单/只读校验/路径沙盒，命令直接放行。
    仍保留 BLOCKED_COMMANDS 灾难黑名单（rm -rf /、shutdown、fork bomb
    等）— 这是防 LLM 自毁的最后防线，与白名单功能无关。
    配置走 OCOSConfig（env > config.json > 默认），默认关闭 = 沙盒全开。
    """
    from ocos.config import get_str
    return get_str("OCOS_SANDBOX_DISABLED", "").strip().lower() in {
        "1", "true", "yes", "on",
    }


# ── 只读 curl 校验（D-UI 修复 2026-09-07）────────────────────────────────────
# 背景: 白名单此前无任何 HTTP 探测工具，"检查页面响应状态"类自检任务
# 规划出 curl 即被拦 → 重试 NONE → 归因误判终态。curl 不做前缀放行
# （`curl -s` 仍可携带 -X POST/-d 写请求），改为令牌级只读校验:
# 仅放行 GET/HEAD 探针语义，任何写/上传/输出重定向/代理/自定义头均拒绝。

# curl 写操作 / 高危 flag（拒绝）— 数据发送、上传、落盘、配置注入、代理
_CURL_REJECT_FLAGS: frozenset[str] = frozenset({
    "-d", "--data", "--data-raw", "--data-binary", "--data-urlencode",
    "-f", "-F", "--form", "--form-string",
    "-t", "-T", "--upload-file",
    "-O", "--remote-name", "--remote-header-name", "-J",
    "-c", "--cookie-jar", "-D", "--dump-header",
    "-K", "--config",
    "-H", "--header",          # 可注入伪造鉴权头 → 拒绝
    "-x", "--proxy",           # 经代理外发/暴露 → 拒绝
    "--trace", "--trace-ascii",  # 落盘 trace 文件
})

# curl 允许的请求方法（-X/--request 后跟 GET/HEAD 才放行）
_CURL_SAFE_METHODS: frozenset[str] = frozenset({"GET", "HEAD"})

# shell 控制操作符（经 punctuation_chars 解析后单独成 token；quoted 内容不受影响）
_SHELL_OPERATORS: frozenset[str] = frozenset({
    "|", "||", ";", ";;", "&", "&&", "<", ">", ">>", "|&", "<<", ">>>",
})


def _is_readonly_curl(command: str) -> bool:
    """curl 只读探针校验 — 仅放行 GET/HEAD，写操作一律拒绝。

    语法错误（引号不闭合等）→ False（诚实拒绝，不做宽松猜测）。
    """
    import shlex
    try:
        lex = shlex.shlex(command, posix=True,
                          punctuation_chars="()<>|&;")
        lex.whitespace_split = True
        tokens = list(lex)
    except ValueError:
        return False
    if not tokens or tokens[0] != "curl":
        return False
    i = 0
    n = len(tokens)
    while i < n:
        tok = tokens[i]
        if tok in _SHELL_OPERATORS:
            return False
        if tok in _CURL_REJECT_FLAGS:
            return False
        if tok in ("-o", "--output"):
            # 唯一放行目标: /dev/null（状态码探针惯用法）
            nxt = tokens[i + 1] if i + 1 < n else ""
            if nxt != "/dev/null":
                return False
            i += 2
            continue
        if tok in ("-X", "--request"):
            method = (tokens[i + 1].upper() if i + 1 < n else "")
            if method not in _CURL_SAFE_METHODS:
                return False
            i += 2
            continue
        i += 1
    return True


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

    AGI 能力补全: extra_allow 提供实例级动态放行前缀集（已发现智能体软件
    CLI），在固定 ALLOWED_COMMANDS 之外按需扩展；默认空集 = 行为不变。
    """

    def __init__(self, strict: bool = True,
                 extra_allow: Optional[frozenset] = None):
        self._strict = strict
        self._extra_allow: frozenset = extra_allow or frozenset()
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
        if sandbox_disabled():
            # 个人使用模式: 白名单/路径沙盒整体关闭，命令直接放行
            # （灾难黑名单已在上方检查完毕，仍然生效）。
            self._audit_log.append(SandboxAuditRecord(
                command=cmd.command,
                allowed=True,
                reason="sandbox disabled (OCOS_SANDBOX_DISABLED)",
            ))
        elif not self._is_allowed(cmd.command, self._extra_allow):
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
        if not sandbox_disabled() and not self._is_path_allowed(cmd.workdir):
            return SandboxResult(
                command=cmd.command,
                success=False,
                blocked=True,
                block_reason=f"Working directory not in sandbox: {cmd.workdir}",
            )

        # ── 真实执行 ────────────────────────────────────────────
        try:
            import os as _os
            import subprocess as sp

            # stack-smashing 根治 (FIX-RUNTIME-1): 给子进程最小安全环境,
            # 不再 env=None 全继承调用方进程的巨型变量集(如 daemon 的几十个
            # ICUBE_* 长变量)。"/bin/sh -c"(dash) 在解析超大/异常环境变量时
            # 触发 glibc __stack_chk_fail → SIGABRT("stack smashing detected"),
            # 偶发导致命令执行崩溃。最小环境既消除该栈压力, 也顺带避免向沙箱
            # 子进程泄漏宿主内部变量(沙箱更严格)。调用方 cmd.env 可追加/覆盖。
            # AGI 能力补全: PATH 追加用户级 bin（~/.local/bin）— 智能体软件
            # CLI（codex/opentale 等）常装于用户目录而非 /usr/bin；不加则
            # 已放行的智能体命令解析失败（codex: not found, exit 127）。
            _user_bins = [
                _os.path.join(_os.path.expanduser("~"), ".local", "bin"),
                _os.path.join(_os.path.expanduser("~"), "bin"),
            ]
            base_env = {
                # UX-J+ 实测修复: 补 /usr/local/bin — ollama 等装于此，
                # 缺失导致沙盒内 which ollama 落空而宿主直跑正常
                "PATH": "/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:"
                        + ":".join(_user_bins),
                "LANG": "C.UTF-8",
                "HOME": _os.path.expanduser("~"),
            }
            if cmd.env:
                base_env.update(cmd.env)

            proc = sp.run(
                cmd.command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=cmd.timeout,
                cwd=cmd.workdir,
                env=base_env,
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
    def _is_allowed(command: str,
                    extra_allow: Optional[frozenset] = None) -> bool:
        """检查命令是否在白名单中（前缀匹配）。

        AGI 能力补全: extra_allow 为实例级动态放行前缀（已发现智能体 CLI），
        默认 None → 行为与固定 ALLOWED_COMMANDS 完全一致。
        D-UI (2026-09-07): curl 走专用只读校验（不走前缀匹配）——仅放行
        GET/HEAD 探针，写操作/代理/自定义头/落盘一律拒绝。
        2026-09-07: OCOS_SANDBOX_DISABLED=true → 白名单整体关闭，直接放行。
        """
        if sandbox_disabled():
            return True
        if command.strip().startswith("curl"):
            return _is_readonly_curl(command)
        for allowed in ALLOWED_COMMANDS:
            if command.strip().startswith(allowed):
                return True
        for allowed in (extra_allow or frozenset()):
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
