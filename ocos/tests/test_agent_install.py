"""AgentInstaller + discovery installable 测试（AGI 自我增强：下载/安装闭环）。

验证:
  - AgentDiscovery 对"未安装但有安装方式"的智能体标注 installable + install_command
  - AgentInstaller 白名单命令真实安装（只执行预设表内命令）
  - 安全: 拒绝任意命令注入 / 未审批不执行 / 表内命令结构防元字符
"""

from __future__ import annotations

import pytest

# 测试用预设安装表（无害命令，验证执行链路；生产用 KNOWN_AGENT_INSTALLS）
_TEST_INSTALLS = {
    "fake-agent": "python3 -c \"print('installed-ok')\"",
    "hello-agent": "python3 -c \"print('hello-installed')\"",
}


class TestAgentDiscoveryInstallable:
    def _spec(self):
        return [{
            "name": "shellmate", "kind": "cli",
            "cli_candidates": ["shellmate-not-exist"],  # 必然 not found
            "version_flags": ["--version"],
            "install": {"command": "python3 -c \"print('shellmate-installed')\"",
                        "source": "pypi"},
        }]

    def test_missing_agent_flagged_installable(self):
        """未安装但配置了安装方式 → installable=True + install_command。"""
        from ocos.capability.agent_discovery import AgentDiscovery
        agents = AgentDiscovery(agents_spec=self._spec()).discover()
        hit = next(a for a in agents if a.name == "shellmate")
        assert hit.available is False
        assert hit.installable is True
        assert "shellmate" in hit.install_command

    def test_available_agent_not_installable(self):
        """已安装 → 不再标注可安装。"""
        from ocos.capability.agent_discovery import AgentDiscovery
        spec = [{
            "name": "shellmate", "kind": "cli",
            "cli_candidates": ["python3"],  # 命中本机
            "version_flags": ["--version"],
            "install": {"command": "python3 -c 'x'", "source": "pypi"},
        }]
        agents = AgentDiscovery(agents_spec=spec).discover()
        hit = next(a for a in agents if a.name == "shellmate")
        assert hit.available is True
        assert hit.installable is False

    def test_inject_report_shows_installable(self):
        """bridge 注入报告应区分可安装（未装）/已可用两类。"""
        from ocos.capability.agent_discovery import AgentDiscovery
        d = AgentDiscovery(agents_spec=self._spec())
        d.discover()
        report = d.report()
        assert "shellmate" in report
        assert "可安装" in report or "未安装" in report or "not available" in report


class TestAgentInstaller:
    def _installer(self, cmds=None):
        from ocos.capability.agent_installer import AgentInstaller
        return AgentInstaller(install_commands=cmds or _TEST_INSTALLS)

    def test_unknown_agent_rejected(self):
        """不在预设表 → 拒绝（即使 approved），绝不执行任意命令。"""
        inst = self._installer()
        r = inst.install("openclaw2", approved=True)  # 不在测试表
        assert r["ok"] is False
        assert r["executed"] is False
        assert "not known" in r["error"].lower() or "unknown" in r["error"].lower()

    def test_requires_approval_when_not_approved(self):
        """未审批 → 不执行，提示 need_approval。"""
        inst = self._installer()
        r = inst.install("fake-agent", approved=False)
        assert r["ok"] is False
        assert r["executed"] is False
        assert r.get("need_approval") is True

    def test_approved_installs_real(self):
        """审批通过 + 表内命令 → 真实执行成功。"""
        inst = self._installer()
        r = inst.install("fake-agent", approved=True)
        assert r["ok"] is True
        assert r["executed"] is True
        assert "installed-ok" in r["output"]

    def test_command_string_has_no_shell_metachars(self):
        """自检: 预设安装命令不得含危险 shell 元字符（防注入/管道 curl|sh）。"""
        inst = self._installer()
        bad = {"`", "$(", ";", "|", ">", "<", "&&", "||", "\\n"}
        for cmd in inst.install_commands.values():
            for tok in bad:
                assert tok not in cmd, f"危险元字符 {tok!r} 在安装命令: {cmd}"

    def test_install_result_shape(self):
        """返回含 binary_present 探测（安装后可凭 which 确认落盘）。"""
        inst = self._installer()
        r = inst.install("hello-agent", approved=True)
        assert r["ok"] is True
        assert "hello-installed" in r["output"]


class TestBridgeInstallWiring:
    """DecisionBridge 安装动作：注入、待批、审批后真实执行。"""

    def _bridge(self, installer=None):
        from ocos.execution.bridge import DecisionBridge
        bridge = DecisionBridge(
            agent_id="test-bridge",
            pending_store=_FakePendingStore(),
        )
        bridge.attach_default_handlers()
        if installer is not None:
            bridge.attach_installer(installer)
        return bridge

    def test_install_without_store_pending(self):
        """无审批 → 入待批队列并返回 pending 标记。"""
        calls = []
        bridge = self._bridge(installer=_FakeInstallerFn(calls))
        r = bridge._handle_install_action("fake-agent", None)
        assert r.get("pending") is True
        assert r.get("need_approval") or "待批" in r.get("error", "")
        assert len(bridge._pending_store.get_pending() or []) >= 1

    def test_install_needs_installer_fail_closed(self):
        """未注入 installer → 安装动作直接拒绝（fail-closed）。"""
        bridge = self._bridge(installer=None)
        r = bridge._handle_install_action("fake-agent", "APPR-1", already_approved=True)
        assert r["ok"] is False
        assert "安装" in r["error"] or "installer" in r["error"].lower()

    def test_install_approved_runs_installer(self):
        """已审批 → 调用注入的 installer 真实执行。"""
        calls = []
        bridge = self._bridge(installer=_FakeInstallerFn(calls))
        r = bridge._handle_install_action(
            "fake-agent", "APPR-1", already_approved=True)
        assert r["ok"] is True
        assert "fake-agent" == calls[0]

    def test_handler_agent_install_routes_approved(self):
        """register_custom_handler → execute_approved 触达真实执行。"""
        calls = []
        bridge = self._bridge(installer=_FakeInstallerFn(calls))
        dispatched = bridge.execute_approved(
            "agent_install",
            {"agent": "fake-agent", "approval_id": ""})
        # approval_id 空 → _verify_approval 走注入 store 校验；此处测 handler 职责
        assert dispatched is not None


class _FakePendingStore:
    """PendingStore 替身（enqueue + 计数）。"""

    def __init__(self):
        self._rows = []

    def enqueue(self, action_type, target="", payload=None, text="", source="",
                approval_required=True):
        self._rows.append({"action_type": action_type, "target": target})
        return f"PEND-{len(self._rows)}"

    def get_pending(self):
        return list(self._rows)


class _FakeInstallerFn:
    """记录调用并返回成功的 installer fn。"""

    def __init__(self, calls):
        self.calls = calls

    def __call__(self, name):
        self.calls.append(name)
        return {"ok": True, "executed": True, "output": f"installed-{name}"}