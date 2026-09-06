"""agent_discovery — 智能体软件自动分析（AGI 能力补全）。

打通"自动分析 → 接入 → 调用"链路的第 1/2 步:
  1. 确定性探查本机可用智能体软件（CLI: which + 版本探测；HTTP: 端点可达性）
  2. 产出 DiscoveredAgent 清单 → 供 AdapterManager 注册为可调用 Capability（接入）

第 3 步（真实调用）由 AdapterManager 真实适配器承担（见 adapter_manager.py）。

治理:
  - 纯确定性规则，无 LLM（延续"确定性优先"纪律）
  - 版本探测仅对 which 命中的命令执行，短超时，输出截断
  - HTTP 探测只读 GET；端点不可达 → available=False（诚实标注，不误报）
  - 手工配置走 config["agents"]（API 端点/CLI 路径），与自动发现叠加
"""

from __future__ import annotations

import shutil
import subprocess
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass(frozen=True)
class DiscoveredAgent:
    """探查到的智能体软件条目。"""

    name: str
    available: bool
    kind: str                  # "cli" | "http"
    cli_path: str = ""         # CLI 可执行文件绝对路径（kind=cli）
    version: str = ""          # 版本标识（探测输出截断）
    api_endpoint: str = ""     # HTTP API 端点（kind=http）
    probe_note: str = ""       # 探查说明（找到位置/不可用原因）
    capability_id: str = ""    # 注册为能力时的 ID（cap:<name>）
    installable: bool = False  # AGI 自我增强: 未安装但已知安装方式
    install_command: str = ""  # AGI 自我增强: 预设安装命令（AgentInstaller 白名单）


# 已知智能体安装方式映射（AGI 自我增强: 缺失 → 可安装）。
# 与 AgentInstaller.KNOWN_AGENT_INSTALLS 同源；此处为 discover 标注 installable
# 的元数据来源（install 命令来自白名单表，防任意命令注入）。
def known_install_command(name: str) -> str:
    """按智能体名查预设安装命令；未知返回空串（不可自动安装）。"""
    try:
        from ocos.capability.agent_installer import KNOWN_AGENT_INSTALLS
        return KNOWN_AGENT_INSTALLS.get(name, {}).get("command", "")
    except Exception:
        return ""


def default_agents_spec() -> list[dict[str, Any]]:
    """已知智能体软件探查清单（确定性，可被构造参数覆盖/扩展）。

    覆盖常见智能体软件 CLI 与本地 HTTP 服务；未安装的条目诚实标注
    available=False，不影响其他条目。
    """
    return [
        {"name": "openclaw", "kind": "cli",
         "cli_candidates": ["openclaw", "claw"],
         "version_flags": ["--version", "version"]},
        {"name": "codex", "kind": "cli",
         "cli_candidates": ["codex"],
         "version_flags": ["--version"]},
        {"name": "claude", "kind": "cli",
         "cli_candidates": ["claude"],
         "version_flags": ["--version"]},
        {"name": "opentale", "kind": "cli",
         "cli_candidates": ["opentale", "ln"],
         "version_flags": ["--version", "version"]},
        {"name": "gemini", "kind": "cli",
         "cli_candidates": ["gemini"],
         "version_flags": ["--version"]},
        {"name": "ollama", "kind": "http",
         "default_endpoint": "http://127.0.0.1:11434/api/version"},
    ]


class AgentDiscovery:
    """智能体软件自动分析器 — 确定性探查本机可用智能体软件。"""

    def __init__(
        self,
        agents_spec: Optional[list[dict[str, Any]]] = None,
        config: Optional[dict[str, Any]] = None,
        timeout: float = 3.0,
    ) -> None:
        self.specs = agents_spec if agents_spec is not None else default_agents_spec()
        self.config = config or {}
        self.timeout = timeout
        self._results: list[DiscoveredAgent] = []

    # ── 入口 ─────────────────────────────────────────────────────────

    def discover(self) -> list[DiscoveredAgent]:
        """运行全部探查规则，返回发现清单（幂等，每次全量刷新）。"""
        cfg_agents = self.config.get("agents", {}) or {}
        agents: list[DiscoveredAgent] = []
        for spec in self.specs:
            cfg = {}
            if isinstance(cfg_agents, dict):
                cfg = cfg_agents.get(spec.get("config_key", spec["name"]), {}) or {}
            if not isinstance(cfg, dict):
                cfg = {}
            kind = spec.get("kind", "cli")
            if kind == "cli":
                agents.append(self._probe_cli(spec, cfg))
            elif kind == "http":
                agents.append(self._probe_http(spec, cfg))
            else:
                agents.append(DiscoveredAgent(
                    name=spec["name"], available=False, kind=str(kind),
                    probe_note=f"unknown kind: {kind}",
                    capability_id=f"cap:{spec['name']}"))
        self._results = agents
        return agents

    def report(self) -> str:
        """人类可读探查报告（对话/日志可观测）。"""
        lines = ["智能体软件探查报告:"]
        if not self._results:
            lines.append("  （未运行探查）")
        for a in self._results:
            if a.available and a.kind == "cli":
                ver = f" — {a.version[:40]}" if a.version else ""
                lines.append(f"  ✓ {a.name} (CLI) {a.cli_path}{ver}")
            elif a.available and a.kind == "http":
                lines.append(f"  ✓ {a.name} (HTTP) {a.api_endpoint}")
            else:
                note = a.probe_note or "not available"
                if a.installable:
                    note += f" — 可安装（{a.install_command[:40]}...）"
                lines.append(f"  ✗ {a.name} — {note}")
        return "\n".join(lines)

    @property
    def available(self) -> list[DiscoveredAgent]:
        return [a for a in self._results if a.available]

    # ── CLI 探查 ─────────────────────────────────────────────────────

    def _probe_cli(self, spec: dict[str, Any],
                   cfg: dict[str, Any]) -> DiscoveredAgent:
        name = spec["name"]
        # 手工配置优先：config["agents"][key]["cli"] 指定路径
        candidates = []
        cli_cfg = cfg.get("cli")
        if cli_cfg:
            candidates.append(cli_cfg)
        candidates.extend(spec.get("cli_candidates", []))
        flags = spec.get("version_flags", ["--version"])

        for cand in candidates:
            path = shutil.which(cand)
            if not path:
                continue
            version = self._read_version(path, flags)
            return DiscoveredAgent(
                name=name, available=True, kind="cli",
                cli_path=path, version=version,
                probe_note=f"found at {path}",
                capability_id=f"cap:{name}")

        # CLI 未命中但配置了 API → 按 HTTP 能力接入
        api = cfg.get("api")
        if api:
            return self._http_entry(name, api)
        # AGI 自我增强: 未安装 → 标注是否可自动安装。安装命令来源:
        # 1) spec["install"]["command"]（扩展清单自带）；2) 缺省查预设白名单表
        cmd = ""
        _inst = spec.get("install")
        if isinstance(_inst, dict) and _inst.get("command"):
            cmd = str(_inst["command"])
        if not cmd:
            cmd = known_install_command(name)
        return DiscoveredAgent(
            name=name, available=False, kind="cli",
            probe_note=("command not found in PATH"
                        + ("（可安装）" if cmd else "")),
            capability_id=f"cap:{name}",
            installable=bool(cmd), install_command=cmd)

    def _read_version(self, path: str, flags: list[str]) -> str:
        """执行 <cli> <flag> 读取版本标识（只读、短超时、截断）。"""
        for flag in flags:
            try:
                r = subprocess.run(
                    [path, flag], capture_output=True, text=True,
                    timeout=self.timeout,
                )
                out = (r.stdout or r.stderr or "").strip()
                if out:
                    return out[:120]
            except Exception:
                continue
        return ""

    # ── HTTP 探查 ────────────────────────────────────────────────────

    def _probe_http(self, spec: dict[str, Any],
                    cfg: dict[str, Any]) -> DiscoveredAgent:
        name = spec["name"]
        endpoint = cfg.get("api") or spec.get("default_endpoint", "")
        if not endpoint:
            return DiscoveredAgent(
                name=name, available=False, kind="http",
                probe_note="no api endpoint configured",
                capability_id=f"cap:{name}")
        return self._http_entry(name, endpoint)

    def _http_entry(self, name: str, endpoint: str) -> DiscoveredAgent:
        ok = self._probe_endpoint(endpoint)
        return DiscoveredAgent(
            name=name, available=ok, kind="http",
            api_endpoint=endpoint,
            probe_note="endpoint reachable" if ok else "endpoint unreachable",
            capability_id=f"cap:{name}")

    def _probe_endpoint(self, endpoint: str) -> bool:
        """只读 GET 探测端点可达性（<500 视为可达）。"""
        try:
            with urllib.request.urlopen(endpoint, timeout=self.timeout) as resp:  # noqa: S310 (本地服务探测)
                return resp.status < 500
        except Exception:
            return False


__all__ = ["AgentDiscovery", "DiscoveredAgent", "default_agents_spec"]
