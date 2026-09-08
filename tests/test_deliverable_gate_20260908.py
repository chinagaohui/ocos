"""2026-09-08 事件复盘修复回归 — 「cat --version 冒充升级计划」。

事件链: 「制定升级计划」目标 → 规划 LLM 输出 ANSWER|<计划正文> → 闸门裸词
「验证」误命中"验证标准" → 强制重试 → LLM 被迫输出 RUN|cat ... --version
（受注入的「只读示例」话术引导）→ exit 0 → ✓ 成功，计划正文整体丢弃。

修复:
    P0-1 闸门创作类豁免 + 「验证」正则收紧（bridge）
    P0-2 goal_result 交付物相关性校验（agent_runtime）
    P1-1 创作/分析类任务不注入智能体清单（bridge._prior_agents）
    P2  自我模型统计纳入 goal execution 能力归因（agent_self_model）
"""

from __future__ import annotations

import json
import sqlite3
from collections import deque
from types import SimpleNamespace

import pytest

from ocos.agent.agent_runtime import AgentRuntime
from ocos.autonomous_runtime.action_dispatcher import ActionType
from ocos.execution.bridge import (
    _AUTHORING_ANALYSIS_RE,
    DecisionBridge,
    DispatchedAction,
)
from ocos.self.agent_self_model import AgentSelfModel

# 2026-09-08 事件的原始目标描述（"验证标准"是当时的误命中源）
EVENT_GOAL_DESC = ("制定一份从当前状态升级为真正数字生命的详细升级计划，"
                   "涵盖自主写操作能力、实测能力提升、持续专注与记忆、"
                   "感知与交互、自我进化等方面，并给出分阶段实施步骤与验证标准")


# ── P0-1: 闸门创作类豁免 + 「验证」收紧 ──────────────────────────────────

class TestP01AuthoringExemption:
    @staticmethod
    def _bridge_with_outputs(*outputs):
        b = DecisionBridge()
        calls = {"n": 0}
        seq = iter(outputs)

        class _TG:
            class _provider:
                @staticmethod
                async def generate(*a, **k):
                    calls["n"] += 1
                    return next(seq)

        b._get_textgen = lambda: _TG()
        b._llm_available = lambda: True
        b._llm_budget_ok = lambda: (True, "")
        b._llm_calls = calls
        return b

    def test_event_goal_answer_delivered_not_discarded(self):
        """事件目标描述 + 纯 ANSWER|计划正文 → 直接放行，正文不丢、不重试。"""
        plan_body = ("ANSWER|第一阶段：放开写操作并预检白名单，个人模式下写命令直接放行；"
                     "第二阶段：扩充实测覆盖，filesystem/shell 每日至少一次实弹验证；"
                     "第三阶段：建立主动目标循环，MotivationHub 持续专注单目标。")
        b = self._bridge_with_outputs(plan_body)
        r = b._handler_dag_task(DispatchedAction(
            ActionType.RUN_COMMAND, target="sandbox",
            payload={"description": EVENT_GOAL_DESC,
                     "auto_readonly": True}))
        assert r.get("ok") is True
        assert "第一阶段" in r.get("stdout", "")
        # 计划正文完整保留（不再被强制重试吞掉）
        assert b._llm_calls["n"] == 1

    def test_verify_standard_word_no_longer_exec_intent(self):
        """「验证标准」不再触发执行意图（裸词「验证」收紧为邻接模式）。"""
        b = self._bridge_with_outputs("ANSWER|方案要点：……")
        r = b._handler_dag_task(DispatchedAction(
            ActionType.RUN_COMMAND, target="sandbox",
            payload={"description": "给出分阶段实施步骤与验证标准",
                     "auto_readonly": True}))
        assert r.get("ok") is True
        assert "方案要点" in r.get("stdout", "")

    def test_verify_file_still_exec_intent(self):
        """真实验证类任务（验证文件/验证结果）仍判执行意图 → 重试 → 诚实失败。"""
        b = self._bridge_with_outputs(
            "ANSWER|文件已生成",
            "ANSWER|真的生成了",
        )
        r = b._handler_dag_task(DispatchedAction(
            ActionType.RUN_COMMAND, target="sandbox",
            payload={"description": "验证文件 /tmp/a.txt 是否已生成",
                     "auto_readonly": True}))
        assert r.get("ok") is False
        assert r.get("honest_blocked") is True

    def test_analysis_words_still_allowed(self):
        """复盘/总结/分析类维持放行（UX-J+ 不回归，模块级正则兼容）。"""
        assert _AUTHORING_ANALYSIS_RE.search("复盘今天的执行记录并总结")
        b = self._bridge_with_outputs("ANSWER|成功率 100%")
        r = b._handler_dag_task(DispatchedAction(
            ActionType.RUN_COMMAND, target="sandbox",
            payload={"description": "复盘分析今天的执行记录并总结",
                     "auto_readonly": True}))
        assert r.get("ok") is True

    def test_thin_answer_retried_to_full_plan(self):
        """P0-2 扩展: 瘦 ANSWER（元描述）→ 重试索要正文 → 返回完整计划。"""
        b = self._bridge_with_outputs(
            "ANSWER|该任务为制定健康作息计划，属于纯分析类任务，直接给出计划结论。",
            "ANSWER|第一阶段（周五晚）：22:30 前入睡；第二阶段（周六）："
            "7:00 起床，早餐后晨跑 30 分钟，午后小憩 20 分钟；"
            "第三阶段（周日）：复盘并固定作息。",
        )
        r = b._handler_dag_task(DispatchedAction(
            ActionType.RUN_COMMAND, target="sandbox",
            payload={"description": "做一份周末健康作息计划",
                     "auto_readonly": True}))
        assert r.get("ok") is True
        assert "第一阶段" in r.get("stdout", "")
        # 元描述不得冒充交付物
        assert "纯分析类任务" not in r.get("stdout", "")
        assert b._llm_calls["n"] == 2

    def test_thin_answer_persistent_honest_fail(self):
        """瘦 ANSWER 重试后仍是元描述 → 诚实失败，不以空洞正文落 ✓。"""
        b = self._bridge_with_outputs(
            "ANSWER|我将直接给出计划结论。",
            "ANSWER|计划已完成制定。",
        )
        r = b._handler_dag_task(DispatchedAction(
            ActionType.RUN_COMMAND, target="sandbox",
            payload={"description": "制定一份详细的升级计划",
                     "auto_readonly": True}))
        assert r.get("ok") is False
        assert r.get("honest_blocked") is True

    def test_analysis_short_answer_not_gated(self):
        """纯分析/复盘类短结论合法 → 不设瘦门槛（UX-J+ 不回归）。"""
        b = self._bridge_with_outputs("ANSWER|今日成功率 100%，方法论有效。")
        r = b._handler_dag_task(DispatchedAction(
            ActionType.RUN_COMMAND, target="sandbox",
            payload={"description": "复盘今天的执行记录并总结",
                     "auto_readonly": True}))
        assert r.get("ok") is True
        assert b._llm_calls["n"] == 1


# ── P0-2: goal_result 交付物相关性校验 ───────────────────────────────────

class _HubCapture:
    """捕获 episode.save 的最小 MemoryHub 替身。"""

    def __init__(self) -> None:
        self.saved = []

    def is_initialized(self) -> bool:
        return True

    class episode:
        pass

    def save_episode(self, ep) -> None:  # pragma: no cover - 占位
        self.saved.append(ep)


class TestP02DeliverableGate:
    @staticmethod
    def _runtime_with_results(results):
        rt = AgentRuntime.__new__(AgentRuntime)  # 裸构造（Phase 31 合约）
        hub = _HubCapture()
        hub.episode = SimpleNamespace(save=hub.saved.append)
        rt._memory_hub = hub
        rt._recent_results = deque(results)
        rt._result_mark = 0
        rt._cycle_count = 1
        return rt, hub

    def test_shell_echo_plan_downgraded(self):
        """计划类任务 + capability=shell 纯回显 → 诚实降级为失败。"""
        rt, hub = self._runtime_with_results([{
            "task_id": "t1", "description": EVENT_GOAL_DESC,
            "agent": "researcher", "capability": "shell",
            "output": "$ cat /home/laogao/.local/bin/openclaw --version\n"
                      "cat (GNU coreutils) 9.4",
            "success": True,
        }])
        rt._record_goal_result()
        ep = hub.saved[0]
        assert ep.outcome["success"] is False
        assert ep.outcome["task_success_rate"] == 0.0
        assert "✗" in ep.decision
        assert "【交付物缺失】" in ep.decision

    def test_data_collect_task_exempt(self):
        """采集/查询类子任务以命令输出为承诺物 → 不降级。"""
        rt, hub = self._runtime_with_results([{
            "task_id": "t1", "description": "查询磁盘使用率并汇总",
            "agent": "researcher", "capability": "shell",
            "output": "$ df -h\n/dev/sda1 40G 20G 50%",
            "success": True,
        }])
        rt._record_goal_result()
        assert hub.saved[0].outcome["success"] is True

    def test_answer_deliverable_untouched(self):
        """ANSWER 正文交付（capability=None）不降级。"""
        rt, hub = self._runtime_with_results([{
            "task_id": "t1", "description": EVENT_GOAL_DESC,
            "agent": "researcher", "capability": None,
            "output": "第一阶段：放开写操作；第二阶段：扩充实测",
            "success": True,
        }])
        rt._record_goal_result()
        assert hub.saved[0].outcome["success"] is True

    def test_context_capability_attribution(self):
        """context 携带 agent 与能力归因（P2 数据面）。"""
        rt, hub = self._runtime_with_results([
            {"task_id": "t1", "description": EVENT_GOAL_DESC,
             "agent": "researcher", "capability": "shell",
             "output": "$ cat x", "success": True},
        ])
        rt._record_goal_result()
        ep = hub.saved[0]
        assert ep.context["agent"] == "researcher"
        caps = {c["name"]: c["success"] for c in ep.context["capabilities"]}
        # 降级后该次 shell 实测如实记为失败
        assert caps == {"shell": False}


# ── P1-1: 创作/分析类任务不注入智能体清单 ────────────────────────────────

class TestP11AgentListExemption:
    @staticmethod
    def _bridge_with_agents(agents):
        b = DecisionBridge()
        b.attach_agent_source(lambda desc: agents)
        return b

    _AGENTS = [{"name": "openclaw", "available": True, "kind": "cli",
                "cli_path": "/home/laogao/.local/bin/openclaw",
                "version": "1.0", "api_endpoint": ""}]

    def test_authoring_desc_skips_injection(self):
        """计划/方案类描述且未显式引用智能体 → 不注入（消除跑偏磁铁）。"""
        b = self._bridge_with_agents(self._AGENTS)
        assert b._prior_agents(EVENT_GOAL_DESC) == ""

    def test_analysis_desc_skips_injection(self):
        b = self._bridge_with_agents(self._AGENTS)
        assert b._prior_agents("复盘今天的执行记录并总结") == ""

    def test_explicit_agent_ref_still_injected(self):
        """描述显式引用智能体名 → 照常注入（调用类任务不受影响）。"""
        b = self._bridge_with_agents(self._AGENTS)
        hint = b._prior_agents("调用 openclaw 查看其版本信息")
        assert "openclaw" in hint

    def test_normal_task_still_injected(self):
        b = self._bridge_with_agents(self._AGENTS)
        hint = b._prior_agents("查看当前磁盘使用率")
        assert "【可用智能体软件】" in hint


# ── P2: 自我模型能力归因统计 ─────────────────────────────────────────────

class TestP2SelfModelAttribution:
    @staticmethod
    def _model_with_episodes(episodes, tmp_path):
        # 注意: AgentSelfModel 每次操作新开连接，:memory: 不共享 — 用临时文件库
        m = AgentSelfModel(str(tmp_path / "self_model_test.db"))
        conn = m._conn()
        conn.execute(
            "CREATE TABLE IF NOT EXISTS episodes "
            "(id TEXT PRIMARY KEY, context TEXT, outcome TEXT, action TEXT)")
        for i, (ctx, outcome) in enumerate(episodes):
            conn.execute(
                "INSERT INTO episodes (id, context, outcome, action) "
                "VALUES (?,?,?,?)",
                (f"EPI-{i}", json.dumps(ctx, ensure_ascii=False),
                 json.dumps(outcome, ensure_ascii=False), "goal_result"))
        conn.commit()
        conn.close()
        return m

    def test_agent_and_capability_grouping(self, tmp_path):
        m = self._model_with_episodes([
            ({"agent": "researcher",
              "capabilities": [{"name": "shell", "success": False}]},
             {"success": False}),
            ({"agent": "researcher",
              "capabilities": [{"name": "shell", "success": True},
                               {"name": "filesystem", "success": True}]},
             {"success": True}),
        ], tmp_path)
        caps = {c["name"]: c for c in m._stat_capabilities(None)}
        assert caps["researcher"]["attempts"] == 2
        assert caps["researcher"]["success_rate"] == 0.5
        assert caps["shell"]["attempts"] == 2
        assert caps["shell"]["success_rate"] == 0.5
        assert caps["filesystem"]["attempts"] == 1
        assert caps["filesystem"]["success_rate"] == 1.0

    def test_legacy_bare_string_capabilities_compat(self, tmp_path):
        """旧格式（裸字符串 capabilities）按聚合 success 计，不丢历史数据。"""
        m = self._model_with_episodes([
            ({"agent": "?", "capabilities": ["shell"]}, {"success": True}),
        ], tmp_path)
        caps = {c["name"]: c for c in m._stat_capabilities(None)}
        assert caps["shell"]["attempts"] == 1
        assert caps["shell"]["success_rate"] == 1.0

    def test_registry_names_merge_without_duplication(self, tmp_path):
        """registry 能力名与实测归并 — 已有实测的不重复建 attempts=0 行。"""
        m = self._model_with_episodes([
            ({"agent": "researcher",
              "capabilities": [{"name": "shell", "success": True}]},
             {"success": True}),
        ], tmp_path)
        caps = {c["name"]: c for c in m._stat_capabilities(["shell", "memory"])}
        assert caps["shell"]["attempts"] == 1      # 实测行保留
        assert caps["memory"]["attempts"] == 0     # registry 无实测行
        assert caps["memory"]["success_rate"] is None


# ── P0-2b: 开发/构建类交付物闸门（2026-09-08「开发虚拟人应用」事件） ──────
# 事件: HUMAN 目标「开发一个桌面虚拟人应用…」→ 规划 LLM 只输出只读侦察
# 命令（ls/node --version/npm --version/cat）→ 全部 exit 0 → ✓ success=true
# task_success_rate=1.0 落库，而汇总正文自述"任务未达成"。P0-2 创作类闸门
# 不命中（交付词正则无开发类动词）。规则: 开发类交付物 = 落盘工件，
# 只读探查在物理上不可能完成 → 命令行无写证据时诚实降级。

# 2026-09-08 事件的原始目标描述与执行输出（生产落库还原）
BUILD_EVENT_DESC = ("开发一个桌面虚拟人应用，具备可交互的虚拟形象界面，"
                    "支持与用户聊天，并集成 OCOS 的对话能力。请先创建项目"
                    "结构，选择合适的技术栈（如 Electron + Web 前端），实现"
                    "基本窗口、虚拟形象展示和聊天输入输出功能，并确保可运行")
BUILD_EVENT_OUTPUT = (
    "$ ls /home/laogao\nDesktop\nDocuments\n…\n\n"
    "$ node --version\nv26.8.1\n\n"
    "$ npm --version\n11.19.0\n\n"
    "$ cat /home/laogao/.local/bin/openclaw\n#!/usr/bin/env node\n…")


class TestWriteEvidenceHeuristic:
    """写证据启发式单测（"$ " 命令标签行级）。"""

    @pytest.mark.parametrize("cmd,expected", [
        ("$ node --version\nv26.8.1", False),      # 事件原始命令 — 版本探查
        ("$ npm --version\n11.19.0", False),        # 裸 "npm " 误判回归
        ("$ python3 --version\nPython 3.12.3", False),
        ("$ ls /home/laogao\n...", False),
        ("$ cat /home/laogao/.local/bin/openclaw\n...", False),
        ("$ echo -n OCOS-ALIVE > /tmp/f.txt\n", True),   # 重定向写
        ("$ mkdir -p project/src\n", True),
        ("$ npm install electron\n", True),
        ("$ npm run build\n", True),
        ("$ npx create-vite app\n", True),
        ("$ node build.js\n", True),                # 脚本执行 — 可能写工件
        ("$ python gen_assets.py\n", True),
        ("$ git clone https://x/y.git\n", True),
        ("$ curl -s http://x > /dev/null\n", False),  # 丢弃输出 ≠ 工件
        ("$ make all\n", True),
        ("$ tee /etc/x\n", True),
    ])
    def test_command_classification(self, cmd, expected):
        from ocos.agent.agent_runtime import _has_write_evidence
        assert _has_write_evidence(cmd) is expected

    def test_non_command_lines_ignored(self):
        from ocos.agent.agent_runtime import _has_write_evidence
        # 汇总正文里出现的 ">" 等符号不在 "$ " 标签行 → 不算写证据
        assert _has_write_evidence("结论: A > B，且 npm install 很重要") \
            is False


class TestP02bBuildDeliverableGate:
    @staticmethod
    def _runtime_with_results(results):
        rt = AgentRuntime.__new__(AgentRuntime)
        hub = _HubCapture()
        hub.episode = SimpleNamespace(save=hub.saved.append)
        rt._memory_hub = hub
        rt._recent_results = deque(results)
        rt._result_mark = 0
        rt._cycle_count = 1
        return rt, hub

    def test_build_event_readonly_probes_downgraded(self):
        """事件还原: 开发类目标 + 纯只读侦察 → 诚实降级。"""
        rt, hub = self._runtime_with_results([{
            "task_id": "t1", "description": BUILD_EVENT_DESC,
            "agent": "researcher", "capability": "shell",
            "output": BUILD_EVENT_OUTPUT, "success": True,
        }])
        rt._record_goal_result()
        ep = hub.saved[0]
        assert ep.outcome["success"] is False
        assert ep.outcome["task_success_rate"] == 0.0
        assert "✗" in ep.decision
        assert "【交付物缺失】" in ep.decision

    def test_build_goal_with_write_evidence_kept(self):
        """开发类目标 + 真实写命令（重定向/mkdir）→ 不降级。"""
        rt, hub = self._runtime_with_results([{
            "task_id": "t1", "description": BUILD_EVENT_DESC,
            "agent": "researcher", "capability": "shell",
            "output": ("$ mkdir -p /tmp/app && echo x > /tmp/app/main.js\n"
                       "$ ls /tmp/app\nmain.js"),
            "success": True,
        }])
        rt._record_goal_result()
        assert hub.saved[0].outcome["success"] is True

    def test_collect_words_in_build_desc_not_exempt(self):
        """开发类描述带"检查/运行"字样 → 采集豁免不适用（仍降级）。"""
        rt, hub = self._runtime_with_results([{
            "task_id": "t1",
            "description": "创建一个监控面板并确保可运行（先检查环境）",
            "agent": "researcher", "capability": "shell",
            "output": "$ uname -a\nLinux\n\n$ df -h\n/dev/sda1 40G",
            "success": True,
        }])
        rt._record_goal_result()
        assert hub.saved[0].outcome["success"] is False

    def test_filesystem_capability_not_gated(self):
        """FILE_WRITE 落盘（capability=filesystem）→ 交付物存在，不降级。"""
        rt, hub = self._runtime_with_results([{
            "task_id": "t1", "description": BUILD_EVENT_DESC,
            "agent": "researcher", "capability": "filesystem",
            "output": "写入 /tmp/app/main.js (120 bytes)", "success": True,
        }])
        rt._record_goal_result()
        assert hub.saved[0].outcome["success"] is True

    def test_data_collect_goal_still_exempt(self):
        """采集类目标（无开发动词）→ 条款不触发，df -h 类不回归。"""
        rt, hub = self._runtime_with_results([{
            "task_id": "t1", "description": "执行 df -h 命令，汇总磁盘剩余空间",
            "agent": "researcher", "capability": "shell",
            "output": "$ df -h\n/dev/sda3 234G 137G 85G 62% /",
            "success": True,
        }])
        rt._record_goal_result()
        assert hub.saved[0].outcome["success"] is True

    def test_capability_attribution_reflects_downgrade(self):
        """降级同步进能力归因（shell 实测如实记失败）。"""
        rt, hub = self._runtime_with_results([{
            "task_id": "t1", "description": BUILD_EVENT_DESC,
            "agent": "researcher", "capability": "shell",
            "output": BUILD_EVENT_OUTPUT, "success": True,
        }])
        rt._record_goal_result()
        caps = {c["name"]: c["success"]
                for c in hub.saved[0].context["capabilities"]}
        assert caps == {"shell": False}


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(pytest.main([__file__, "-q"]))
