"""AGI 修复: 未安装智能体误判 + 核心工具误配防御。

背景: opentale 的 cli_candidates 曾含 "ln"，which 永远命中
/usr/bin/ln（coreutils）→ ① 未安装的 opentale 被误判 available=True；
② /usr/bin/ln 被动态放行进沙盒；③ 保真闸门强制 RUN|opentale（命令名
不存在）→ 127 失败循环。三层修复各对应一条测试。
"""
from ocos.capability.agent_discovery import AgentDiscovery
from ocos.execution.bridge import DecisionBridge


class TestCoreToolBlacklist:
    def test_default_spec_has_no_ln_candidate(self):
        spec = next(s for s in AgentDiscovery().specs
                    if s["name"] == "opentale")
        assert "ln" not in spec.get("cli_candidates", [])

    def test_core_tool_candidate_skipped(self):
        # 恶意/错误 spec: 把 cat 列为某智能体候选 — 应被黑名单跳过，
        # 该智能体保持未安装（available=False）而不是顶替成 coreutils
        spec = [{"name": "fake-agent", "kind": "cli",
                 "cli_candidates": ["cat"],
                 "version_flags": ["--version"]}]
        d = AgentDiscovery(agents_spec=spec)
        result = d.discover()
        assert result[0].available is False

    def test_real_agent_still_discovered(self):
        # 回归: 真实存在的 CLI（ln 不在候选里）仍正常发现
        spec = [{"name": "python3", "kind": "cli",
                 "cli_candidates": ["python3"],
                 "version_flags": ["--version"]}]
        d = AgentDiscovery(agents_spec=spec)
        result = d.discover()
        assert result[0].available is True

    def test_uninstalled_agent_honest(self):
        # opentale 未安装（本机无此命令）→ available=False（诚实标注）
        d = AgentDiscovery()
        result = {a.name: a for a in d.discover()}
        assert result["opentale"].available is False


class TestAgentInvokeName:
    def _bridge(self):
        return DecisionBridge()

    def test_invoke_name_matches_when_consistent(self):
        a = {"name": "openclaw", "cli_path": "/home/u/.local/bin/openclaw"}
        assert self._bridge()._agent_invoke(a) == "openclaw"

    def test_invoke_name_falls_back_to_path_when_mismatch(self):
        # name↔命令名错位（opentale 误配 ln 的时代）: RUN|opentale 必 127，
        # 绝对路径保证可执行
        a = {"name": "opentale", "cli_path": "/usr/bin/ln"}
        assert self._bridge()._agent_invoke(a) == "/usr/bin/ln"

    def test_forced_call_uses_invoke_name(self):
        bridge = self._bridge()
        bridge.attach_agent_source(lambda desc: [
            {"name": "opentale", "available": True, "kind": "cli",
             "cli_path": "/usr/bin/ln"}])
        forced = bridge._agent_forced_call("请调用 opentale 分析")
        assert forced == "/usr/bin/ln"

    def test_forced_call_skips_unavailable(self):
        # 修复核心: 未安装智能体不再被保真闸门强制调用（127 死循环根因）
        bridge = self._bridge()
        bridge.attach_agent_source(lambda desc: [
            {"name": "opentale", "available": False, "kind": "cli",
             "cli_path": ""}])
        assert bridge._agent_forced_call("请调用 opentale 分析") == ""

    def test_hint_uses_invoke_name(self):
        bridge = self._bridge()
        bridge.attach_agent_source(lambda desc: [
            {"name": "opentale", "available": True, "kind": "cli",
             "cli_path": "/usr/bin/ln"}])
        hint = bridge._agent_hint("请调用 opentale 分析")
        assert "RUN|/usr/bin/ln" in hint
