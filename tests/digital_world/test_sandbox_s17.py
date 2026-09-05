"""S1.7: digital_world 沙盒白名单化回归（白皮书 P1-12）。

- 默认只读白名单外的命令 → rejected
- 元字符（管道/命令替换/重定向）→ rejected
- 敏感路径参数 → rejected
- dry_run 与真实模式校验行为一致
"""

from __future__ import annotations

import uuid

import pytest

from ocos.digital_world.base import DigitalOperation
from ocos.digital_world import sandbox as dw_sandbox


def _op(command: str) -> DigitalOperation:
    return DigitalOperation.create(
        op_type="sandbox_exec", target="sandbox",
        requester="test", params={"command": command},
        approval_id="APPR-test")


class TestDwSandboxWhitelist:
    def test_whitelisted_command_simulated_ok(self):
        result = dw_sandbox.sandbox_exec(_op("uname -a"))
        assert result.status == "success"

    def test_non_whitelisted_rejected(self):
        # curl 撞黑名单层；此处验证纯白名单层
        result = dw_sandbox.sandbox_exec(_op("mytool --run"))
        assert result.status == "rejected"
        assert "whitelist" in (result.error or "").lower()

    def test_metachar_command_substitution_rejected(self):
        result = dw_sandbox.sandbox_exec(_op("echo $(cat /etc/shadow)"))
        assert result.status == "rejected"

    def test_pipe_rejected(self):
        result = dw_sandbox.sandbox_exec(_op("cat /etc/passwd | grep root"))
        assert result.status == "rejected"

    def test_sensitive_path_rejected(self):
        result = dw_sandbox.sandbox_exec(_op("cat /etc/shadow"))
        assert result.status == "rejected"
        assert "sensitive" in (result.error or "").lower()

    def test_variant_not_bypassed(self, monkeypatch):
        """黑名单/白名单双层下，空格变体、\\rm 等无法绕过白名单。"""
        for cmd in ("rm  -rf /", "rm -fr /", "\\rm -rf /", "sh -c 'rm -rf /'"):
            result = dw_sandbox.sandbox_exec(_op(cmd))
            assert result.status == "rejected", cmd

    def test_real_mode_whitelist_consistent(self, monkeypatch, tmp_path):
        """真实模式（DRY_RUN=0）下校验行为与模拟一致。"""
        monkeypatch.setattr(dw_sandbox, "_DRY_RUN", False)
        monkeypatch.setenv("OCOS_DW_SHELL_WHITELIST", "echo")
        result = dw_sandbox.sandbox_exec(_op("echo dw-real-ok"))
        assert result.status == "success"
        result2 = dw_sandbox.sandbox_exec(_op("ls"))
        assert result2.status == "rejected"
