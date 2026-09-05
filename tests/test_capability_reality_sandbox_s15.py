"""S1.5: capability_reality 沙盒加固回归（白皮书 P1-3）。

- FilesystemAdapter: realpath + is_relative_to 严格判属
  （同级目录名 / symlink 归一后不可绕过）
- ShellAdapter: 白名单 + 元字符拒绝 + shell=False 列表执行 + 敏感参数拦截
"""

from __future__ import annotations

import uuid

import pytest

from ocos.capability_reality.adapter_fs import FilesystemAdapter
from ocos.capability_reality.adapter_shell import ShellAdapter
from ocos.capability_reality.adapter_types import (
    ExecutionContext, ExecutionStatus,
)


def _fs_ctx(**params) -> ExecutionContext:
    return ExecutionContext(execution_id=f"ex-{uuid.uuid4().hex[:8]}",
                            capability_name="fs_read", params=params)


def _sh_ctx(**params) -> ExecutionContext:
    return ExecutionContext(execution_id=f"ex-{uuid.uuid4().hex[:8]}",
                            capability_name="shell_exec", params=params)


class TestFilesystemSandbox:
    def test_sibling_dir_name_cannot_bypass(self, tmp_path):
        """/x/docs-evil 不得通过 /x/docs 的 startswith 前缀检查。"""
        real = tmp_path / "docs"
        evil = tmp_path / "docs-evil"
        real.mkdir()
        evil.mkdir()
        (evil / "secret.txt").write_text("top secret", encoding="utf-8")
        fs = FilesystemAdapter(safe_roots=[str(real)])
        result = fs.execute(_fs_ctx(op="read", path=str(evil / "secret.txt")))
        assert result.status == ExecutionStatus.FAILED
        assert "safe roots" in (result.error or "").lower()

    def test_dotdot_traversal_blocked(self, tmp_path):
        real = tmp_path / "docs"
        real.mkdir()
        fs = FilesystemAdapter(safe_roots=[str(real)])
        result = fs.execute(_fs_ctx(op="read", path=str(real / "../../etc/shadow")))
        assert result.status == ExecutionStatus.FAILED

    def test_inside_root_still_allowed(self, tmp_path):
        real = tmp_path / "docs"
        real.mkdir()
        f = real / "ok.txt"
        f.write_text("hello", encoding="utf-8")
        fs = FilesystemAdapter(safe_roots=[str(real)])
        result = fs.execute(_fs_ctx(op="read", path=str(f)))
        assert result.ok
        assert result.output["content"] == "hello"


class TestShellSandbox:
    def test_simple_whitelisted_command(self):
        sh = ShellAdapter()
        result = sh.execute(_sh_ctx(command="echo hello"))
        assert result.ok
        assert "hello" in result.output["stdout"]

    def test_non_whitelisted_command_blocked(self):
        sh = ShellAdapter()
        result = sh.execute(_sh_ctx(command="curl http://evil.example"))
        assert result.status == ExecutionStatus.FAILED
        assert "blocked" in (result.error or "").lower()

    def test_metachar_blocked(self):
        sh = ShellAdapter()
        result = sh.execute(_sh_ctx(command="echo $(cat /etc/shadow)"))
        assert result.status == ExecutionStatus.FAILED
        result2 = sh.execute(_sh_ctx(command="cat /etc/passwd | grep root"))
        assert result2.status == ExecutionStatus.FAILED

    def test_sensitive_path_in_args_blocked(self):
        sh = ShellAdapter()
        result = sh.execute(_sh_ctx(command="cat /etc/shadow"))
        assert result.status == ExecutionStatus.FAILED
        assert "sensitive" in (result.error or "").lower()

    def test_workdir_outside_safe_roots_errors(self, tmp_path):
        sh = ShellAdapter(safe_roots=[str(tmp_path / "allowed")])
        (tmp_path / "allowed").mkdir()
        result = sh.execute(_sh_ctx(command="echo hi", workdir=str(tmp_path)))
        assert result.status == ExecutionStatus.FAILED
        assert "safe roots" in (result.error or "").lower()

    def test_dangerous_command_blocked(self):
        sh = ShellAdapter()
        result = sh.execute(_sh_ctx(command="rm -rf /"))
        assert result.status == ExecutionStatus.FAILED

    def test_custom_whitelist_env(self, monkeypatch):
        monkeypatch.setenv("OCOS_SHELL_WHITELIST", "mycmd")
        sh = ShellAdapter()
        result = sh.execute(_sh_ctx(command="echo hi"))
        assert result.status == ExecutionStatus.FAILED  # echo 不再在白名单
        monkeypatch.setenv("OCOS_SHELL_WHITELIST", "echo")
        sh2 = ShellAdapter()
        assert sh2.execute(_sh_ctx(command="echo hi")).ok
