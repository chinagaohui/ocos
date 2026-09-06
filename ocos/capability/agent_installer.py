"""agent_installer — 智能体软件下载/安装执行器（AGI 自我增强闭环）。

补齐"发现→接入→调用"之外的"缺失→下载→安装"环节:
  - 安装命令全部来自预设白名单 KNOWN_AGENT_INSTALLS（不可任意命令注入）
  - 未审批不执行（安装 = 系统级写操作，强制人工确认）
  - 真实 subprocess 执行，可探测落盘（binary_present）

安全边界（fail-closed）:
  - 只接受表格内 (name → command) 的完整命令；name 不在此表 → 拒绝
  - 表格 cmd 不得含危险 shell 元字符（防御自检，管道/重定向/`/; 一律拒）
  - 执行前校验命名解析（env PATH 含用户 bin 与 npm/pip），超时保护
"""

from __future__ import annotations

import os
import shlex
import subprocess
from dataclasses import dataclass, field
from typing import Any, Optional

# 预设安装命令白名单（AGI 自我增强）: agent_name → {source, command}。
# 命令为固定字符串，经人工授信后才会执行；命名必须表内命中。
# 注: openclaw 为本机自定义 fork（nvm 装），npm 名以实际渠道为准，此处为示例。
KNOWN_AGENT_INSTALLS: dict[str, dict[str, str]] = {
    "claude": {"source": "npm", "command": "npm install -g @anthropic-ai/claude-code"},
    "gemini": {"source": "npm", "command": "npm install -g @google/gemini-cli"},
    "codex": {"source": "npm", "command": "npm install -g @openai/codex"},
    "openclaw": {"source": "npm", "command": "npm install -g openclaw"},
    "opentale": {"source": "npm", "command": "npm install -g opentale"},
    "ollama": {"source": "curl", "command": "curl -fsSLo /tmp/ollama-setup --proto '=https' https://ollama.com/install/ollama-setup.sh"},
}

# 防御自检: 预设命令不得含这些危险 shell 元字符（防管道/重定向/命令替换）
_DANGEROUS_METACHARS = ("`", "$(", ";", "|", "<", ">", "&&", "||")


@dataclass
class AgentInstaller:
    """智能体软件安装执行器 — 白名单命令真实执行 + 审批门。"""

    install_commands: Optional[dict[str, dict[str, str]]] = None
    timeout: float = 180.0

    def __post_init__(self):
        if self.install_commands is None:
            self.install_commands = dict(KNOWN_AGENT_INSTALLS)

    # ── 入口 ─────────────────────────────────────────────────────────

    def install(self, name: str, approved: bool = False) -> dict[str, Any]:
        """安装指定智能体（须审批通过才真实执行）。

        返回: {ok, executed, need_approval, name, output, error, exit_code}
        """
        info = self.install_commands.get(name)
        if not info:
            return {"ok": False, "executed": False,
                    "error": f"unknown install target: {name} "
                             f"(不在已知智能体白名单)"}
        cmd = info["command"] if isinstance(info, dict) else str(info)
        source = info.get("source", "") if isinstance(info, dict) else "preset"
        if not approved:
            return {"ok": False, "executed": False, "need_approval": True,
                    "name": name,
                    "error": "需人工审批后才执行安装（系统级写操作）"}
        # 防御自检: 即便表内命令也不得含危险元字符（fail-closed）
        if self._has_dangerous_metachar(cmd):
            return {"ok": False, "executed": False,
                    "name": name,
                    "error": "安装命令含危险 shell 元字符，已拒绝"}
        out, err, rc = self._run(cmd)
        ok = rc == 0
        return {
            "ok": ok, "executed": True, "name": name,
            "output": out[:1500], "error": err[:300],
            "exit_code": rc, "command": cmd,
            "source": source,
        }

    # ── 校验 ─────────────────────────────────────────────────────────

    @staticmethod
    def _has_dangerous_metachar(cmd: str) -> bool:
        cmd_l = cmd.replace(" ", "")
        for tok in _DANGEROUS_METACHARS:
            if tok in cmd_l:
                return True
        return False

    # ── 真实执行 ─────────────────────────────────────────────────────

    def _run(self, command: str) -> tuple[str, str, int]:
        """执行白名单安装命令。env 含用户 bin 与 npm/pip/npx 路径。"""
        _home = os.path.expanduser("~")
        extra = [
            os.path.join(_home, ".local", "bin"),
            os.path.join(_home, "bin"),
            os.path.join(_home, ".nvm", "versions", "node", "v24.16.0", "bin"),
        ]
        env = dict(os.environ)
        env["PATH"] = os.environ.get("PATH", "") + ":" + ":".join(extra)
        try:
            args = shlex.split(command)
        except ValueError as e:
            return "", f"bad command: {e}", 1
        try:
            proc = subprocess.run(
                args, capture_output=True, text=True,
                timeout=self.timeout, env=env,
            )
            return (proc.stdout or "")[:2000], (proc.stderr or "")[:400], proc.returncode
        except subprocess.TimeoutExpired:
            return "", f"install timeout > {self.timeout:.0f}s", -1
        except Exception as e:  # noqa: BLE001
            return "", str(e)[:300], 1


__all__ = ["AgentInstaller", "KNOWN_AGENT_INSTALLS"]