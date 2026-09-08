"""Agent Discovery + 真实外部适配器测试（AGI 能力补全）。

验证:
  - 自动分析: 确定性探查本机智能体软件（CLI which/version + HTTP 探测）
  - 接入: 发现的软件可注册为可调用能力（cap:<name>）
  - 调用: EXTERNAL_AGENT/HTTP adapter 真实执行（不再是 "[Agent] response to:" 假串）
  - 安全: CLI 调用拒绝 shell 元字符
"""

from __future__ import annotations

import time
import threading
import http.server
import functools
from dataclasses import dataclass

import pytest


# ── 本地临时 HTTP 服务（供 HTTP adapter 真实请求）──────────────────────────


class _Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        body = b'{"ok": true, "agent": "fake-http-agent"}'
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


@pytest.fixture
def local_http_server():
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()
    server.server_close()


# ── 测试: 自动分析（discovery）───────────────────────────────────────────


class TestAgentDiscovery:
    def _discovery(self, spec, config=None, timeout=5.0):
        from ocos.capability.agent_discovery import AgentDiscovery
        return AgentDiscovery(agents_spec=spec, config=config, timeout=timeout)

    def test_discovers_real_cli(self):
        """真实存在的命令 → available=True 且 version 探测到真实标识。"""
        spec = [{
            "name": "fake-agent", "kind": "cli",
            "cli_candidates": ["python3"],
            "version_flags": ["--version"],
        }]
        agents = self._discovery(spec).discover()
        hit = next((a for a in agents if a.name == "fake-agent"), None)
        assert hit is not None
        assert hit.available is True
        assert hit.kind == "cli"
        assert hit.cli_path  # 真实路径
        assert "Python" in hit.version  # 真实版本输出

    def test_unavailable_cli_not_false_positive(self):
        """不存在的命令 → available=False，不误报、不抛。"""
        spec = [{
            "name": "no-such-agent-xyz", "kind": "cli",
            "cli_candidates": ["no-such-agent-xyz"],
            "version_flags": ["--version"],
        }]
        agents = self._discovery(spec).discover()
        hit = next(a for a in agents if a.name == "no-such-agent-xyz")
        assert hit.available is False
        assert hit.cli_path == ""
        assert "not found" in hit.probe_note.lower() or hit.probe_note

    def test_config_agents_section_applied(self):
        """config['agents'] 手工配置（HTTP endpoint）→ 识别为 HTTP 能力。"""
        endpoint = "http://127.0.0.1:9999/api"
        config = {"agents": {"my-agent": {"api": endpoint}}}
        spec = [{
            "name": "my-agent", "kind": "http",
            "config_key": "my-agent",
        }]
        agents = self._discovery(spec, config=config).discover()
        hit = next(a for a in agents if a.name == "my-agent")
        assert hit is not None
        assert hit.kind == "http"
        assert hit.api_endpoint == endpoint
        assert hit.capability_id == "cap:my-agent"

    def test_report_human_readable(self):
        """report() 输出人类可读清单（含 available/缺失标注）。"""
        spec = [{
            "name": "fake-agent", "kind": "cli",
            "cli_candidates": ["python3"], "version_flags": ["--version"],
        }]
        d = self._discovery(spec)
        agents = d.discover()
        report = d.report()
        assert "fake-agent" in report
        assert "available" in report.lower() or "✓" in report


# ── 测试: 接入 + 调用（真实适配器）──────────────────────────────────────


class TestExternalAgentAdapterReal:
    def _make_manager(self, agents):
        from ocos.capability.adapter_manager import AdapterManager
        from ocos.capability.capability_types import (
            Capability, CapabilityState, CapabilityType, ExecutorKind,
        )
        mgr = AdapterManager()
        mgr.register_all_default()
        mgr.register_discovered(agents)
        for a in agents:
            mgr.router.registry.register(Capability(
                capability_id=a.capability_id,
                name=a.name,
                cap_type=CapabilityType.CUSTOM_AGENT,
                executor_kind=ExecutorKind.EXTERNAL_AGENT,
                provider=a.name,
                endpoint=a.cli_path or a.api_endpoint,
                state=CapabilityState.AVAILABLE,
            ))
        return mgr

    def test_cli_adapter_returns_real_output(self):
        """EXTERNAL_AGENT CLI 调用 → 返回真实子进程输出（非 stub 假串）。"""
        from ocos.capability.agent_discovery import DiscoveredAgent
        from ocos.capability.capability_types import ExecutionRequest

        agent = DiscoveredAgent(
            name="fake-agent", available=True, kind="cli",
            cli_path="/usr/bin/env",  # 占位；实际以 python3 探测为准
            version="", capability_id="cap:fake-agent",
        )
        # 用 python3 真实 CLI 验证执行链
        agent = DiscoveredAgent(
            name="fake-agent", available=True, kind="cli",
            cli_path="python3", version="3.x",
            capability_id="cap:fake-agent",
        )
        mgr = self._make_manager([agent])
        result = mgr.execute(ExecutionRequest(
            request_id="R-1", capability_id="cap:fake-agent",
            input_payload="--version",
        ))
        assert result.status.value == "success"
        assert "Python" in result.raw_output, result.raw_output
        assert result.raw_output != "[Agent] response to: --version"  # 非 stub

    def test_http_adapter_returns_real_response(self, local_http_server):
        """HTTP adapter → 真实 HTTP 请求并返回响应体。"""
        from ocos.capability.agent_discovery import DiscoveredAgent
        from ocos.capability.capability_types import ExecutionRequest

        agent = DiscoveredAgent(
            name="fake-http-agent", available=True, kind="http",
            api_endpoint=local_http_server, version="",
            capability_id="cap:fake-http-agent",
        )
        mgr = self._make_manager([agent])
        result = mgr.execute(ExecutionRequest(
            request_id="R-2", capability_id="cap:fake-http-agent",
            input_payload="/probe",
        ))
        assert result.status.value == "success"
        assert '"ok": true' in result.raw_output, result.raw_output

    def test_cli_rejects_shell_metachars(self):
        """安全: CLI 调用含 shell 元字符 → 拒绝（failure），不执行。"""
        from ocos.capability.agent_discovery import DiscoveredAgent
        from ocos.capability.capability_types import ExecutionRequest

        agent = DiscoveredAgent(
            name="fake-agent", available=True, kind="cli",
            cli_path="python3", version="3.x",
            capability_id="cap:fake-agent",
        )
        mgr = self._make_manager([agent])
        result = mgr.execute(ExecutionRequest(
            request_id="R-3", capability_id="cap:fake-agent",
            input_payload="--version; rm -rf /",
        ))
        assert result.status.value == "failure"
        assert "not allowed" in result.error_message.lower() or \
            "blocked" in result.error_message.lower()

    def test_unknown_capability_keeps_stub_fallback(self):
        """未注册/不可用的 capability_id → 保留旧 stub 语义（不崩）。"""
        from ocos.capability.capability_types import ExecutionRequest
        mgr = self._make_manager([])
        result = mgr.execute(ExecutionRequest(
            request_id="R-4", capability_id="cap:unknown",
            input_payload="hello",
        ))
        # 路由到 router._default_route 或 stub — 不抛异常
        assert result.status.value in ("success", "capability_unavailable")


# ── 测试: bridge 规划注入 + 沙盒动态放行（生产主路径）─────────────────────


class TestBridgeAgentWiring:
    """DecisionBridge 注入可用智能体清单 + 动态放行已发现 CLI。"""

    def _bridge(self, agents):
        from ocos.execution.bridge import DecisionBridge

        bridge = DecisionBridge(agent_id="test-bridge")
        source = lambda _desc, _as=agents: _as  # noqa: E731
        bridge.attach_agent_source(source)
        # 与 daemon.factory 装配语义一致: 放行 CLI 绝对路径 + 命令名
        clis = {a["cli_path"] for a in agents if a.get("kind") == "cli"}
        clis |= {a["name"] for a in agents if a.get("kind") == "cli"}
        bridge.attach_agent_clis(clis)
        return bridge

    def _agent(self, name="python3", available=True):
        import shutil
        path = shutil.which("python3") or "/usr/bin/python3"
        return {"name": name, "available": available, "kind": "cli",
                "cli_path": path, "version": "3.x", "api_endpoint": ""}

    def test_prior_agents_injects_list(self):
        """_prior_agents 输出【可用智能体软件】清单（含路径、版本与执行引导）。"""
        bridge = self._bridge([self._agent()])
        block = bridge._prior_agents("调用 python3 执行任务")
        assert "【可用智能体软件】" in block
        assert "python3" in block
        assert "CLI" in block
        assert "可直接执行" in block  # 明确 RUN| 行可直接调用的引导
        assert "python3 --version" in block

    def test_discovered_cli_runs_in_sandbox(self):
        """已发现 CLI → 沙盒动态放行并真实执行（非白名单外拦截）。"""
        from types import SimpleNamespace
        bridge = self._bridge([self._agent()])
        result = bridge._handler_run_command(
            SimpleNamespace(payload={"command": "python3 --version"}))
        assert result.get("ok") is True, result
        assert "Python" in result.get("stdout", ""), result

    def test_undiscovered_command_still_blocked(self):
        """未发现的命令 → 仍被白名单拦截（不放宽既有边界）。

        D-UI (2026-09-07) 边界更新: 只读 curl GET 探针经 _is_readonly_curl
        有意放行（原样例 curl http://… 已入白名单），wget 及 curl 写操作
        （-X POST/-d/-o 等）仍被拦（见 tests/test_webui_fixes.py）。
        """
        from types import SimpleNamespace
        bridge = self._bridge([self._agent()])
        result = bridge._handler_run_command(
            SimpleNamespace(payload={"command": "wget http://evil.example"}))
        assert result.get("blocked") is True, result

    def test_no_agent_source_no_injection(self):
        """未注入 agent_source → _prior_agents 返回空（基线路径不变）。"""
        from ocos.execution.bridge import DecisionBridge
        bridge = DecisionBridge(agent_id="test-bridge")
        assert bridge._prior_agents("随便什么任务") == ""

    def test_agent_hint_forces_direct_call(self):
        """描述命中已发现智能体 → 输出强制直接调用指令（抑制漂移）。

        L1+ 诚实语义: fixture 制造 name↔cli_path 错位（codex 名 +
        python3 路径），hint 必须引用真实可执行路径而非编造命令名。
        """
        import shutil
        bridge = self._bridge([self._agent(name="codex")])
        hint = bridge._agent_hint("运行 codex --version 获取版本号")
        assert "【智能体调用强制指令】" in hint
        assert "RUN|" in hint
        assert (shutil.which("python3") or "/usr/bin/python3") in hint
        assert "不要改用 uname/df" in hint

    def test_agent_hint_empty_without_match(self):
        """描述未引用任何已发现智能体 → 无强制指令。"""
        bridge = self._bridge([self._agent(name="codex")])
        assert bridge._agent_hint("查看磁盘使用情况") == ""

    def test_agent_hint_skips_python3(self):
        """python3 视为通用运行时，不触发强制调用指令。"""
        bridge = self._bridge([self._agent(name="python3")])
        assert bridge._agent_hint("运行 python3 脚本") == ""

    def test_agent_forced_call_returns_name(self):
        """描述命中已发现可用 CLI 智能体 → 返回可执行调用（保真闸门用）。

        name↔命令错位时诚实返回 cli_path 绝对路径（与 _agent_invoke 一致）。
        """
        import shutil
        bridge = self._bridge([self._agent(name="codex")])
        assert bridge._agent_forced_call("运行 codex --version") == (
            shutil.which("python3") or "/usr/bin/python3")

    def test_agent_forced_call_empty_without_match(self):
        """未命中 / python3 / 不可用 → 不干预。"""
        bridge = self._bridge([self._agent(name="codex")])
        assert bridge._agent_forced_call("查看磁盘使用情况") == ""
        bridge2 = self._bridge([self._agent(name="python3")])
        assert bridge2._agent_forced_call("运行 python3 脚本") == ""
        bridge3 = self._bridge([self._agent(name="codex", available=False)])
        assert bridge3._agent_forced_call("运行 codex --version") == ""
