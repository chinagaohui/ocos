"""Phase 51: goal exec 直接执行器测试 (绕过认领的同步执行)。

验收:
    E1: LLM 分解描述 → 多条命令 (解析 RUN| 行)
    E2: 每条命令经沙盒执行 → ExecResult 结构
    E3: 写命令被沙盒拦截 (rm/echo> 等)
    E4: 分解失败 → 单命令回退
    E5: 汇总统计正确
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from ocos.execution.goal_executor import (  # noqa: E402
    ExecResult,
    GoalDirectExecutor,
    GoalExecReport,
)


class _FakeBridge:
    """假 bridge: 记录调用, 沙盒由测试控制。"""

    def __init__(self, allowed: set[str] | None = None,
                 llm_available: bool = True,
                 decompose_lines: list[str] | None = None) -> None:
        self._allowed = allowed or {"uname", "free", "df", "cat"}
        self._llm_ok = llm_available
        self._decompose_lines = decompose_lines or ["RUN|uname -a", "RUN|free -h"]
        self.executed: list[str] = []
        self._llm_calls_today = 0
        self._llm_calls_date = ""
        self._textgen = None

    def _llm_available(self) -> bool:
        return self._llm_ok

    def _llm_budget_ok(self) -> tuple[bool, str]:
        return True, ""

    def _get_textgen(self):
        class _FakeTG:
            class _provider:
                @staticmethod
                async def generate(prompt: str, **kw) -> str:
                    return "\n".join(kw.get("_lines", []))
        tg = _FakeTG()
        # 注入分解行 — 简单方案: 从桥接对象取
        tg._provider.generate = self._fake_generate
        return tg

    async def _fake_generate(self, prompt: str, **kw) -> str:
        return "\n".join(self._decompose_lines)

    def _handler_run_command(self, action: Any) -> dict:
        cmd = (action.payload or {}).get("command", "")
        self.executed.append(cmd)
        head = cmd.split()[0] if cmd.split() else ""
        if head in self._allowed:
            return {"ok": True, "blocked": False, "exit_code": 0,
                    "stdout": f"out:{cmd}", "stderr": ""}
        return {"ok": False, "blocked": True,
                "block_reason": f"白名单外命令段: {head}"}


# ── E1: 分解 ──────────────────────────────────────────────────────


class TestDecompose:
    def test_parse_run_lines(self):
        ex = GoalDirectExecutor(_FakeBridge(decompose_lines=[
            "RUN|uname -a", "RUN|free -h", "RUN|df -h"]))
        cmds = ex.decompose("查系统")
        assert cmds == ["uname -a", "free -h", "df -h"]

    def test_none_aborts_collection(self):
        """NONE 行 = LLM 判定整体不可执行 → 放弃全部 (含已解析 RUN)。"""
        ex = GoalDirectExecutor(_FakeBridge(decompose_lines=[
            "RUN|uname -a", "NONE|无法只读达成"]))
        assert ex.decompose("查系统") == []

    def test_none_returns_empty(self):
        ex = GoalDirectExecutor(_FakeBridge(decompose_lines=["NONE|无法执行"]))
        assert ex.decompose("查系统") == []

    def test_llm_unavailable_empty(self):
        ex = GoalDirectExecutor(_FakeBridge(llm_available=False))
        assert ex.decompose("查系统") == []

    def test_cap_max(self):
        lines = [f"RUN|uname {i}" for i in range(20)]
        ex = GoalDirectExecutor(_FakeBridge(decompose_lines=lines))
        cmds = ex.decompose("查系统")
        assert len(cmds) <= 12

    def test_fence_stripped(self):
        ex = GoalDirectExecutor(_FakeBridge(decompose_lines=[
            "```", "RUN|uname -a", "```"]))
        assert ex.decompose("x") == ["uname -a"]


# ── E2/E3: 沙盒执行 ──────────────────────────────────────────────


class TestExecute:
    def test_allowed_command_runs(self):
        ex = GoalDirectExecutor(_FakeBridge())
        r = ex.execute_command("uname -a")
        assert r.ok and not r.blocked
        assert "out:uname -a" in r.stdout

    def test_forbidden_command_blocked(self):
        ex = GoalDirectExecutor(_FakeBridge())
        r = ex.execute_command("rm -rf /")
        assert not r.ok and r.blocked
        assert "白名单" in r.block_reason

    def test_write_operator_blocked(self):
        ex = GoalDirectExecutor(_FakeBridge())
        r = ex.execute_command("echo hack > /etc/passwd")
        assert r.blocked

    def test_exec_result_defaults(self):
        r = ExecResult()
        assert r.ok is False and r.exit_code == -1


# ── E4/E5: 完整流程 ──────────────────────────────────────────────


class TestExecuteGoal:
    def test_full_report(self):
        ex = GoalDirectExecutor(_FakeBridge(decompose_lines=[
            "RUN|uname -a", "RUN|rm -rf /", "RUN|free -h"]))
        rep = ex.execute_goal("查系统")
        assert len(rep.commands) == 3
        ok = [c for c in rep.commands if c.ok]
        blocked = [c for c in rep.commands if c.blocked]
        assert len(ok) == 2 and len(blocked) == 1
        assert rep.summary == "2/3 命令成功, 1 被沙盒拦截"
        assert rep.started_at and rep.finished_at

    def test_single_command_fallback(self):
        """分解失败 (NONE) → 整段描述当单命令 (UX-I 语义)。"""
        ex = GoalDirectExecutor(_FakeBridge(decompose_lines=["NONE|无法"]))
        rep = ex.execute_goal("uname -a")
        # 回退后 "uname -a" 走沙盒 → uname 在白名单 → 成功
        assert rep.commands and rep.commands[0].command == "uname -a"
        assert rep.commands[0].ok

    def test_report_to_dict(self):
        ex = GoalDirectExecutor(_FakeBridge(decompose_lines=["RUN|df -h"]))
        rep = ex.execute_goal("查磁盘")
        d = rep.to_dict()
        assert d["goal_text"] == "查磁盘"
        assert len(d["commands"]) == 1
        assert d["commands"][0]["command"] == "df -h"
