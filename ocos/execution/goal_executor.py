"""ocos goal exec — 直接执行器 (Phase 51: 绕过认领的同步执行).

背景 (生产测试发现 2026-09-04):
  daemon 认领链 (goal create → tick 认领 → TaskDecomposer 模板 → LLM 单命令)
  有架构断点: TaskDecomposer 忽略 goal 文本, 按 domain 模板产出
  "收集数据/分析数据/生成报告" 空壳任务; 且单任务只转一条白名单命令。

本模块: CLI 直接执行 — goal 描述 → LLM 分解为多条只读命令 → 逐条经
DecisionBridge 沙盒真实执行 → 汇总返回。完全绕开 daemon 认领与模板分解。

治理:
  - 不动内核: 不改 agent_runtime/daemon/tick; 纯新增 CLI 入口
  - 复用 DecisionBridge._handler_run_command (白名单+敏感路径+strict 沙盒)
  - LLM 只负责"描述→命令序列"转换, 不直接执行; 每条命令仍过沙盒闸门
  - 只读命令集 (与 bridge prompt 一致), 写操作拒绝
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from ocos.logging import get_logger

logger = get_logger(__name__)

# 与 bridge UX-F1 白名单一致的只读命令前缀 (由 SandboxOps 最终裁决)
MAX_COMMANDS = 12
COMMAND_TIMEOUT = 30.0


@dataclass
class ExecResult:
    """单条命令执行结果。"""

    command: str = ""
    ok: bool = False
    blocked: bool = False
    stdout: str = ""
    stderr: str = ""
    exit_code: int = -1
    block_reason: str = ""


@dataclass
class GoalExecReport:
    """整体执行报告。"""

    goal_text: str = ""
    commands: list[ExecResult] = field(default_factory=list)
    started_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    finished_at: str = ""
    summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "goal_text": self.goal_text,
            "commands": [{
                "command": c.command,
                "ok": c.ok,
                "blocked": c.blocked,
                "exit_code": c.exit_code,
                "stdout": c.stdout[:500],
                "stderr": c.stderr[:200],
                "block_reason": c.block_reason,
            } for c in self.commands],
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "summary": self.summary,
        }


class GoalDirectExecutor:
    """直接执行器 — 描述 → LLM 分解 → 沙盒逐条执行。"""

    def __init__(self, bridge: Any = None) -> None:
        self._bridge = bridge or self._build_bridge()

    # ── 装配 ──────────────────────────────────────────────────────

    def _build_bridge(self) -> Any:
        """构建带真实沙盒 handlers 的 DecisionBridge (与 daemon 同款闸门)。"""
        from ocos.execution.bridge import DecisionBridge
        bridge = DecisionBridge(agent_id="goal-exec")
        bridge.attach_default_handlers()
        return bridge

    # ── LLM 分解 ──────────────────────────────────────────────────

    def decompose(self, goal_text: str) -> list[str]:
        """LLM: goal 描述 → 只读命令序列。

        返回命令列表; LLM 失败/不可用 → [] (调用方诚实降级)。
        """
        bridge = self._bridge
        if not self._llm_available():
            logger.warning("GoalDirectExecutor: LLM 不可用, 无法分解描述")
            return []
        budget_ok, reason = bridge._llm_budget_ok()
        if not budget_ok:
            logger.warning("GoalDirectExecutor: %s", reason)
            return []

        prompt = (
            f"用户目标: {goal_text}\n\n"
            "把上述目标拆解为**若干条可直接执行的只读 shell 命令**。\n"
            "要求:\n"
            "1. 每行一条命令, 严格格式 RUN|<命令>\n"
            f"2. 只允许只读信息命令, 优先: uname/hostnamectl/lscpu/lsblk/free/df/uptime/"
            f"ps/ip/cat /etc/os-release/ls/date/whoami/ping -c 4/who/curl -sI\n"
            "3. 禁止写操作 (rm/mv/mkdir/echo >/tee/编辑/安装/删除)\n"
            "4. 最多 8 条, 按信息类别组织: 系统/CPU/内存/磁盘/网络/进程\n"
            "5. 若目标无法用只读命令达成, 只输出 NONE|<原因>\n"
            "不要输出任何解释或其他格式。"
        )
        try:
            # 复用 bridge 的代理清理 + textgen
            tg = self._bridge._get_textgen()
            raw = asyncio.run(tg._provider.generate(
                prompt,
                system_prompt="你是 OCOS 的命令分解器。只输出 RUN|<命令> 行。",
                temperature=0.1, max_tokens=2000))
        except Exception as e:
            logger.warning("GoalDirectExecutor: LLM decompose failed: %s", e)
            return []

        commands: list[str] = []
        for line in raw.strip().splitlines():
            line = line.strip()
            # 剥 code fence
            if line.startswith("```"):
                continue
            if line.startswith("RUN|"):
                cmd = line[4:].strip()
                if cmd:
                    commands.append(cmd)
            elif line.startswith("NONE|"):
                logger.info("GoalDirectExecutor: LLM 判定不可执行: %s", line[5:].strip())
                return []
        return commands[:MAX_COMMANDS]

    def _llm_available(self) -> bool:
        return bool(self._bridge._llm_available())

    # ── 执行 ──────────────────────────────────────────────────────

    def execute_command(self, command: str) -> ExecResult:
        """单条命令经沙盒执行 (strict, 白名单闸门)。"""
        from types import SimpleNamespace
        res = ExecResult(command=command)
        result = self._bridge._handler_run_command(
            SimpleNamespace(payload={"command": command}))
        res.ok = bool(result.get("ok"))
        res.blocked = bool(result.get("blocked"))
        res.stdout = result.get("stdout", "")
        res.stderr = result.get("stderr", "")
        res.exit_code = int(result.get("exit_code", -1))
        res.block_reason = result.get("block_reason", "") or result.get("error", "")
        return res

    def execute_goal(self, goal_text: str,
                     fallback_single: bool = True) -> GoalExecReport:
        """完整流程: 分解 → 逐条执行 → 汇总。

        fallback_single: LLM 分解失败时, 尝试把整段描述作为单命令
        (兼容 chat 路径 UX-I 语义) — 仍经沙盒裁决。
        """
        report = GoalExecReport(goal_text=goal_text)

        commands = self.decompose(goal_text)
        if not commands and fallback_single:
            logger.info("GoalDirectExecutor: 分解为空 → 单命令回退")
            commands = [goal_text]

        for cmd in commands:
            r = self.execute_command(cmd)
            report.commands.append(r)

        ok_count = sum(1 for c in report.commands if c.ok)
        blocked_count = sum(1 for c in report.commands if c.blocked)
        report.finished_at = datetime.now(timezone.utc).isoformat()
        report.summary = (
            f"{ok_count}/{len(report.commands)} 命令成功"
            + (f", {blocked_count} 被沙盒拦截" if blocked_count else ""))
        return report

    # ── 落库 (可选) ───────────────────────────────────────────────

    def persist_result(self, goal_id: str, report: GoalExecReport) -> None:
        """把执行摘要写回 goal.result_json (goal 存在时)。"""
        try:
            db_path = os.environ.get("OCOS_DB_PATH",
                                     os.path.expanduser("~/.ocos/ocos.db"))
            import sqlite3
            con = sqlite3.connect(db_path)
            con.execute(
                "UPDATE goal SET status='COMPLETED', result_json=? WHERE goal_id=?",
                (json.dumps(report.to_dict(), ensure_ascii=False)[:4000], goal_id))
            con.commit()
            con.close()
        except Exception as e:
            logger.warning("GoalDirectExecutor: persist failed: %s", e)
