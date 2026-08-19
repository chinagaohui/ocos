"""Phase 22-E: search_ops + sandbox_ops 测试 (22e3)。

验证:
  - search_ops: URL 白名单拦截/放行
  - sandbox_ops: BLOCKED_COMMANDS 拦截生效
  - sandbox_ops: 白名单命令可执行
"""
import pytest

from ocos.operations.search_ops import (
    SearchOps,
    SearchQuery,
    SearchResult,
    is_url_allowed,
    API_WHITELIST,
)
from ocos.operations.sandbox_ops import (
    SandboxOps,
    SandboxCommand,
    SandboxResult,
    BLOCKED_COMMANDS,
    ALLOWED_COMMANDS,
)


# ── search_ops: URL 白名单 ─────────────────────────────────────────────


class TestUrlAllowed:
    """URL 白名单检查。"""

    def test_allowed_duckduckgo(self):
        assert is_url_allowed("https://api.duckduckgo.com") is True

    def test_allowed_wikipedia(self):
        assert is_url_allowed("https://en.wikipedia.org/wiki/Python") is True

    def test_blocked_random_url(self):
        assert is_url_allowed("https://evil.example.com/hack") is False

    def test_blocked_localhost_not_in_list(self):
        assert is_url_allowed("http://evil.localhost") is False

    def test_allowed_ollama(self):
        assert is_url_allowed("http://localhost:11434/api/generate") is True

    def test_blocked_internal_ip(self):
        assert is_url_allowed("http://10.0.0.1/admin") is False

    def test_allowed_openai_subdomain(self):
        """openai.com 后缀应放行。"""
        from ocos.operations.search_ops import DOMAIN_SUFFIX_WHITELIST
        if "openai.com" in DOMAIN_SUFFIX_WHITELIST:
            assert is_url_allowed("https://api.openai.com/v1/chat") is True


class TestSearchOps:
    """SearchOps 白名单 + 代理。"""

    def test_block_non_whitelist_url(self):
        """非白名单 URL 被拦截。"""
        ops = SearchOps(strict=True)
        result = ops.search(SearchQuery(
            query="test", url="https://evil.example.com"
        ))
        assert result.success is False
        assert "not in allowed" in (result.error or "")

    def test_audit_log_records(self):
        """每次搜索记录审计日志。"""
        ops = SearchOps(strict=True)
        ops.search(SearchQuery(query="test", url="https://evil.example.com"))
        assert len(ops.audit_log) >= 1
        assert ops.audit_log[-1].allowed is False

    def test_get_history(self):
        """get_history 返回审计记录。"""
        ops = SearchOps(strict=True)
        ops.search(SearchQuery(query="q1", url="https://evil.example.com"))
        ops.search(SearchQuery(query="q2", url="https://bad.example.com"))
        history = ops.get_history(limit=5)
        assert len(history) == 2

    def test_clear_history(self):
        """clear_history 清空审计日志。"""
        ops = SearchOps(strict=True)
        ops.search(SearchQuery(query="t", url="https://evil.example.com"))
        ops.clear_history()
        assert len(ops.audit_log) == 0


# ── sandbox_ops: 命令黑白名单 ────────────────────────────────────────


class TestSandboxBlocked:
    """BLOCKED_COMMANDS 拦截测试。"""

    def test_block_rm_rf(self):
        sandbox = SandboxOps(strict=True)
        result = sandbox.execute(SandboxCommand(command="rm -rf /tmp/test"))
        assert result.blocked is True
        assert result.success is False

    def test_block_shutdown(self):
        sandbox = SandboxOps(strict=True)
        result = sandbox.execute(SandboxCommand(command="shutdown now"))
        assert result.blocked is True

    def test_block_reboot(self):
        sandbox = SandboxOps(strict=True)
        result = sandbox.execute(SandboxCommand(command="reboot -f"))
        assert result.blocked is True

    def test_block_python_subprocess(self):
        sandbox = SandboxOps(strict=True)
        result = sandbox.execute(SandboxCommand(command="os.system('whoami')"))
        assert result.blocked is True

    def test_block_eval(self):
        sandbox = SandboxOps(strict=True)
        result = sandbox.execute(SandboxCommand(command="eval echo test"))
        assert result.blocked is True

    def test_block_exec_function(self):
        sandbox = SandboxOps(strict=True)
        result = sandbox.execute(SandboxCommand(command="exec(open('file'))"))
        assert result.blocked is True


class TestSandboxAllowed:
    """ALLOWED_COMMANDS 白名单测试。"""

    def test_allowed_echo(self):
        """echo 应在白名单中且可执行。"""
        sandbox = SandboxOps(strict=True)
        result = sandbox.execute(SandboxCommand(
            command="echo hello",
            workdir="/home/laogao/Documents/trae_projects/ocos",
        ))
        assert result.blocked is False
        assert result.success is True
        assert "hello" in result.stdout

    def test_allowed_whoami(self):
        sandbox = SandboxOps(strict=True)
        result = sandbox.execute(SandboxCommand(
            command="whoami",
            workdir="/home/laogao/Documents/trae_projects/ocos",
        ))
        assert result.blocked is False
        assert result.success is True

    def test_allowed_ls(self):
        sandbox = SandboxOps(strict=True)
        result = sandbox.execute(SandboxCommand(
            command="ls /home/laogao/Documents/trae_projects/ocos",
            workdir="/home/laogao/Documents/trae_projects/ocos",
        ))
        assert result.blocked is False

    def test_not_in_whitelist_blocked_strict(self):
        """非白名单命令在 strict 模式下被拦截。"""
        sandbox = SandboxOps(strict=True)
        result = sandbox.execute(SandboxCommand(
            command="ping -c 1 127.0.0.1",
            workdir="/home/laogao/Documents/trae_projects/ocos",
        ))
        assert result.blocked is True


class TestSandboxAudit:
    """沙盒审计日志。"""

    def test_audit_records_blocked(self):
        sandbox = SandboxOps(strict=True)
        sandbox.execute(SandboxCommand(command="rm -rf /"))
        assert len(sandbox.audit_log) >= 1
        assert sandbox.audit_log[-1].allowed is False

    def test_audit_records_allowed(self):
        sandbox = SandboxOps(strict=True)
        sandbox.execute(SandboxCommand(
            command="echo test",
            workdir="/home/laogao/Documents/trae_projects/ocos",
        ))
        assert len(sandbox.audit_log) >= 1
        assert sandbox.audit_log[-1].allowed is True

    def test_get_history(self):
        sandbox = SandboxOps(strict=True)
        sandbox.execute(SandboxCommand(command="echo a", workdir="/home/laogao/Documents/trae_projects/ocos"))
        sandbox.execute(SandboxCommand(command="echo b", workdir="/home/laogao/Documents/trae_projects/ocos"))
        history = sandbox.get_history(limit=5)
        assert len(history) == 2

    def test_clear_history(self):
        sandbox = SandboxOps(strict=True)
        sandbox.execute(SandboxCommand(command="echo a", workdir="/home/laogao/Documents/trae_projects/ocos"))
        sandbox.clear_history()
        assert len(sandbox.audit_log) == 0
