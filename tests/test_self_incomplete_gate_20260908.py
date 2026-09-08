"""2026-09-08「GitHub 数字生命调研」假成功事件回归。

事件链: 用户授权「去 GitHub 学习数字生命并总结+升级方案」→ 对话层转成
混合型目标（联网调研 + 本地检查）→ 规划器只规划描述括号里枚举的本地
命令（uname/df/free/python3 --version），零联网动作（宿主机实测
github.com 可达）→ 总结器诚实自述「任务未完整达成…缺少 GitHub 调研
结果」→ 但描述含「检查/执行」命中 _DATA_COLLECT_RE 采集豁免、无
_BUILD_GOAL_RE 词 → 两道描述类闸门均放行 → ✓ success=true 落库。

修复:
    Fix-1 规划器规则补充联网抓取引导（RUN|curl -s）+ 复合任务覆盖要求
    Fix-2 P0-2c 总结器自认不完整降级（agent_runtime._record_goal_result）
"""

from __future__ import annotations

from collections import deque
from types import SimpleNamespace

from ocos.agent.agent_runtime import AgentRuntime
from ocos.autonomous_runtime.action_dispatcher import ActionType
from ocos.execution.bridge import DecisionBridge, DispatchedAction

# 2026-09-08 事件的目标描述（混合型：联网调研 + 本地检查 + 交付方案）
EVENT_DESC = ("访问 GitHub 学习数字生命（Digital Life / Digital Immortality）"
              "相关开源项目与知识，总结核心概念、技术路线与代表性项目；随后"
              "检查宿主机当前系统环境（执行 uname -a、df -h、free -h、"
              "python3 --version 等命令），结合宿主机现状提出可落地的升级"
              "方案，输出总结与建议。")

# 事件的真实输出形态（结论摘要自认不完整 + 原始输出全为本地命令回显）
EVENT_OUTPUT = ("【结论摘要】**结论摘要**：任务未完整达成。已确认宿主机为 "
                "Ubuntu 24.04，但输出中**缺少 GitHub 数字生命项目调研结果**，"
                "未提供核心概念、技术路线及代表性项目清单，亦无基于现状的"
                "升级方案。需补充调研内容后方可完成全部任务。\n\n"
                "【原始输出】\n$ uname -a\nLinux laogao 7.0.0-28-generic\n\n"
                "$ df -h\n/dev/sda1 40G 20G 50%")


class _HubCapture:
    """捕获 episode.save 的最小 MemoryHub 替身。"""

    def __init__(self) -> None:
        self.saved = []

    def is_initialized(self) -> bool:
        return True

    def save_episode(self, ep) -> None:  # pragma: no cover - 占位
        self.saved.append(ep)


# ── Fix-2: P0-2c 总结器自认不完整降级 ────────────────────────────────────

class TestP02cSelfIncompleteGate:
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

    def test_event_output_downgraded(self):
        """事件原始输出（摘要自认未完整）+ 采集词描述 → 诚实降级失败。"""
        rt, hub = self._runtime_with_results([{
            "task_id": "t1", "description": EVENT_DESC,
            "agent": "researcher", "capability": "shell",
            "output": EVENT_OUTPUT, "success": True,
        }])
        rt._record_goal_result()
        ep = hub.saved[0]
        assert ep.outcome["success"] is False
        assert ep.outcome["task_success_rate"] == 0.0
        assert "✗" in ep.decision
        assert "【执行不完整】" in ep.decision
        # 能力归因如实记为失败
        caps = {c["name"]: c["success"] for c in ep.context["capabilities"]}
        assert caps == {"shell": False}

    def test_complete_summary_kept(self):
        """摘要判定完整达成（含真实抓取证据）→ 不降级。"""
        out = ("【结论摘要】任务已完整达成。通过 GitHub API 抓取到 5 个数字"
               "生命相关项目（Sil aque、OpenDM 等），核心概念涵盖数字孪生/"
               "意识上传/记忆连续性，升级方案已给出。\n\n"
               "【原始输出】\n$ curl -s https://api.github.com/search/...\n"
               '{"total_count": 65}')
        rt, hub = self._runtime_with_results([{
            "task_id": "t1", "description": EVENT_DESC,
            "agent": "researcher", "capability": "shell",
            "output": out, "success": True,
        }])
        rt._record_goal_result()
        assert hub.saved[0].outcome["success"] is True

    def test_raw_output_mentions_ignored(self):
        """原始输出段出现「未提供」字样、摘要段干净 → 不误伤。"""
        out = ("【结论摘要】任务已完整达成：磁盘 40G 已用 20G。\n\n"
               "【原始输出】\n$ df -h\nFilesystem 未提供配额信息")
        rt, hub = self._runtime_with_results([{
            "task_id": "t1", "description": "查询磁盘使用率并汇总",
            "agent": "researcher", "capability": "shell",
            "output": out, "success": True,
        }])
        rt._record_goal_result()
        assert hub.saved[0].outcome["success"] is True

    def test_partial_admission_variants_downgraded(self):
        """摘要自认的常见变体（部分达成/需补充/未达成）均降级。"""
        for phrase in ("调研部分达成", "部分完成", "任务未达成",
                       "需补充联网调研数据", "缺少代表性项目清单"):
            out = f"【结论摘要】任务{phrase}。\n\n【原始输出】\n$ uname -a\nLinux"
            rt, hub = self._runtime_with_results([{
                "task_id": "t1", "description": "调研并总结",
                "agent": "researcher", "capability": "shell",
                "output": out, "success": True,
            }])
            rt._record_goal_result()
            assert hub.saved[0].outcome["success"] is False, phrase

    def test_long_summary_with_deliverables_kept(self):
        """校准: 摘要已含实质交付正文（调研表+升级方案 1500 字）、仅提及
        README 子步骤未完成 → 交付物存在，不降级。"""
        out = ("【结论摘要】任务部分达成。已成功抓取 GitHub 项目并获取系统"
               "信息，但未抓取各项目 README 全文。\n\n一、代表性项目："
               + "；".join(f"proj-{i}/repo-{i} | {i} 星 | 人格数字化方向"
                           for i in range(8))
               + "。技术路线共性：RAG + 向量数据库 + 多模态记忆 + 大模型人格"
               "模拟，辅以声音克隆增强拟真度，项目整体处于早期探索阶段。\n\n"
               "二、宿主机现状：Ubuntu 24.04，磁盘 85G 可用（62% 已用），内存"
               " 18Gi 可用，12 核 CPU 负载正常。\n\n三、升级方案建议："
               "存储层用 Qdrant 向量库持久化多模态记忆；人格层采用 RAG + 长期"
               "记忆分层（短期对话缓存/长期语义记忆/情景记忆）；本地跑 Ollama"
               " + FastAPI，云端同步记忆库；运行本地 LLM 需 8-12G 内存，当前"
               "可用 18G 可支撑，建议 Swap 扩至 8G 或启用 zram；磁盘预留 50G"
               " 用于向量库与模型权重；备份层定期导出记忆库至 Git 仓库。")
        assert len(out) >= 600  # 实质交付内容门槛
        rt, hub = self._runtime_with_results([{
            "task_id": "t1", "description": EVENT_DESC,
            "agent": "researcher", "capability": "shell",
            "output": out, "success": True,
        }])
        rt._record_goal_result()
        assert hub.saved[0].outcome["success"] is True

    def test_build_assessment_intent_not_downgraded(self):
        """P0-2f 校准: 「部署可行性画像」是评估意图，只读探查即合法完成。"""
        out = ("【结论摘要】宿主机硬件画像已完成：Ubuntu 24.04，磁盘 85G 可用"
               "（62% 已用），内存 31G（可用 18G），12 核 CPU，GPU 为 NVIDIA "
               "GeForce RTX 3060（12GB 显存）。部署可行性：可支撑 7B 级模型"
               "QLoRA 4bit 微调与本地推理。\n\n"
               "【原始输出】\n$ nvidia-smi --query-gpu=name,memory.total\n"
               "NVIDIA GeForce RTX 3060, 12288 MiB")
        rt, hub = self._runtime_with_results([{
            "task_id": "t1",
            "description": "检查宿主机完整硬件环境，汇总为部署可行性画像",
            "agent": "researcher", "capability": "shell",
            "output": out, "success": True,
        }])
        rt._record_goal_result()
        assert hub.saved[0].outcome["success"] is True

    def test_build_action_still_downgraded(self):
        """P0-2f 校准不扩大化: 真构建意图（无评估词）仍诚实降级。"""
        rt, hub = self._runtime_with_results([{
            "task_id": "t1",
            "description": "部署 WeClone 数字分身应用并确保可运行",
            "agent": "researcher", "capability": "shell",
            "output": "【结论摘要】已了解部署方式。\n\n【原始输出】\n"
                      "$ uname -a\nLinux",
            "success": True,
        }])
        rt._record_goal_result()
        assert hub.saved[0].outcome["success"] is False

    def test_plain_output_without_summary_untouched(self):
        """无【结论摘要】前缀的普通输出（单命令回退路径）不检查。"""
        rt, hub = self._runtime_with_results([{
            "task_id": "t1", "description": "执行 uptime 命令，报告负载",
            "agent": "researcher", "capability": "shell",
            "output": "$ uptime\n 07:32:03 up 7 days,  1 user",
            "success": True,
        }])
        rt._record_goal_result()
        assert hub.saved[0].outcome["success"] is True


# ── Fix-1: 规划器联网抓取引导 ────────────────────────────────────────────

class _PromptCapture:
    """捕获 generate 调用 prompt 的最小 TG 替身。"""

    def __init__(self, reply: str) -> None:
        self.prompts: list[str] = []
        self._reply = reply
        self._provider = self

    async def generate(self, prompt, **k):
        self.prompts.append(prompt)
        return self._reply


class TestPlannerNetworkGuidance:
    def _bridge(self, reply):
        b = DecisionBridge()
        cap = _PromptCapture(reply)
        b._get_textgen = lambda: cap
        b._llm_available = lambda: True
        b._llm_budget_ok = lambda: (True, "")
        b._llm_calls = {"n": 0}
        return b, cap

    def test_rules_mention_curl_for_web_tasks(self):
        """规则文本包含 RUN|curl -s 抓取引导与『禁止省略联网部分』。"""
        b, cap = self._bridge("RUN|uname -a")
        b._handler_dag_task(DispatchedAction(
            ActionType.RUN_COMMAND, target="sandbox",
            payload={"description": "访问 GitHub 学习数字生命相关开源项目",
                     "auto_readonly": True}))
        assert cap.prompts, "规划 prompt 未产生"
        assert "curl -s" in cap.prompts[0]
        assert "禁止省略联网部分" in cap.prompts[0]

    def test_rules_demand_full_coverage_for_mixed_task(self):
        """复合任务覆盖要求出现在规则中（联网调研与本地检查都要有动作）。"""
        b, cap = self._bridge("RUN|uname -a")
        b._handler_dag_task(DispatchedAction(
            ActionType.RUN_COMMAND, target="sandbox",
            payload={"description": EVENT_DESC, "auto_readonly": True}))
        assert "全部关键部分" in cap.prompts[0]

    def test_rules_mention_gpu_for_host_inspection(self):
        """P0-2f: 宿主机/硬件探查任务 → 规划规则含 GPU 命令集。"""
        b, cap = self._bridge("RUN|uname -a")
        b._handler_dag_task(DispatchedAction(
            ActionType.RUN_COMMAND, target="sandbox",
            payload={"description": "检查宿主机硬件配置并评估部署可行性",
                     "auto_readonly": True}))
        assert "nvidia-smi" in cap.prompts[0]
        assert "lspci" in cap.prompts[0]

    def test_compile_prompt_demands_gpu_in_host_goals(self):
        """P0-2f: 目标编译器 prompt 教 LLM 宿主机探查必须含 GPU。"""
        from ocos.interaction.converse import ChatResponder
        r = ChatResponder(db_path=":memory:")
        prompts = []
        tg = r  # 编译器通过 tg._provider.generate 调用
        class _Cap:
            async def generate(self, prompt, **k):
                prompts.append(prompt)
                return '{"kind":"task","description":"检查宿主机并评估 GPU",' \
                       '"domain":"research"}'
        import ocos.engines.text_generator as tgm
        orig = tgm.get_text_generator
        tgm.get_text_generator = lambda: type("T", (), {"_provider": _Cap()})()
        try:
            r.compile_goal("分析宿主机硬件并评估 WeClone 部署可行性")
        finally:
            tgm.get_text_generator = orig
        assert prompts and "nvidia-smi" in prompts[0]
        assert "必查项" in prompts[0]

    def test_curl_plan_passes_through(self):
        """规划器输出 RUN|curl -s <url> → 真实执行路径放行（无写符号拦截）。"""
        b, _cap = self._bridge(
            'RUN|curl -s "https://api.github.com/search/repositories?'
            'q=digital+life&per_page=3"')
        executed = {}

        def _fake_run(act):
            executed["cmd"] = act.payload["command"]
            return {"ok": True, "stdout": '{"total_count": 65}'}

        b._handler_run_command = _fake_run
        r = b._handler_dag_task(DispatchedAction(
            ActionType.RUN_COMMAND, target="sandbox",
            payload={"description": "访问 GitHub 调研数字生命开源项目并总结",
                     "auto_readonly": True}))
        assert r.get("ok") is True
        assert "curl -s" in executed["cmd"]
        assert '{"total_count": 65}' in r.get("stdout", "")


# ── P0-2d: 已完成目标 + 实质重做请求 → 真实重新入队 ─────────────────────

class TestP02dRequeueCompletedGoal:
    OLD_DESC = ("访问 GitHub 学习数字生命（Digital Life / Digital Immortality）"
                "相关开源项目与知识，总结核心概念、技术路线与代表性项目")

    def _responder(self, tmp_path, with_state=True):
        import json as _json
        from ocos.interaction.converse import ChatResponder
        from ocos.interaction.conversation_state import ConversationStateStore
        from ocos.goal.store import GoalStore
        db = str(tmp_path / "t.db")
        GoalStore(db_path=db).save(
            goal_id="GOAL-OLD", level="USER", status="COMPLETED",
            description=self.OLD_DESC, priority=3.0,
            source="chat", origin_level="HUMAN", authority="FRAMEWORK",
            metadata={"domain": "research", "session_id": "web"})
        if with_state:
            ConversationStateStore(db).update("web", current_goal_id="GOAL-OLD",
                                              last_intent="task")
        r = ChatResponder(db_path=db)
        r.compile_goal = lambda msg: {"kind": "continue", "reason": "重发请求"}
        captured = {}

        def _fake_respond(message, goal_note=None, session_id="web",
                          _emit=None):
            captured["note"] = goal_note
            return {"reply": "ok"}

        r.respond = _fake_respond
        return r, GoalStore(db_path=db), captured, _json

    def test_grounding_miss_falls_back_to_last_session_goal(self, tmp_path):
        """current 已清空 → 回退查会话最近目标（E2E 二次复测漏网路径）。"""
        r, store, captured, _json = self._responder(tmp_path, with_state=False)
        out = r.respond_auto(
            "授权你去github上学习数字生命的相关知识，学习后做出总结并结合"
            "宿主机现状提出升级方案", session_id="web")
        g = store.load(out["goal_id"])
        assert g is not None and g["id"] != "GOAL-OLD"
        assert g["status"] == "PENDING"
        meta = _json.loads(g["metadata"])
        assert meta["requeued_from"] == "GOAL-OLD"

    def test_substantive_redo_creates_new_pending_goal(self, tmp_path):
        """重发实质任务请求 → 新 PENDING 目标入队 + note 如实对齐。"""
        r, store, captured, _json = self._responder(tmp_path)
        out = r.respond_auto(
            "授权你去github上学习数字生命的相关知识，学习后做出总结并结合"
            "宿主机现状提出升级方案", session_id="web")
        assert out["kind"] == "continue"
        g = store.load(out["goal_id"])
        assert g is not None and g["id"] != "GOAL-OLD"
        assert g["status"] == "PENDING"
        assert "数字生命" in g["description"]
        meta = _json.loads(g["metadata"])
        assert meta["requeued_from"] == "GOAL-OLD"
        assert meta["domain"] == "research"
        assert "已重新入队" in captured["note"]

    def test_bare_continue_does_not_requeue(self, tmp_path):
        """裸推进词（继续）→ 维持结果汇报语义，不建新目标。"""
        r, store, captured, _json = self._responder(tmp_path)
        out = r.respond_auto("继续", session_id="web")
        assert out["goal_id"] == "GOAL-OLD"
        assert "已重新入队" not in (captured["note"] or "")
        rows = store.load_active()
        assert all(g["id"] != "GOAL-OLD" or g["status"] == "COMPLETED"
                   for g in rows)

    def test_bare_continue_regex(self):
        from ocos.interaction.converse import (_BARE_CONTINUE_RE,
                                               _CONTINUE_QUERY_RE)
        assert _BARE_CONTINUE_RE.match("继续")
        assert _BARE_CONTINUE_RE.match(" 好吧！")
        assert not _BARE_CONTINUE_RE.match("继续学习数字生命")
        assert not _BARE_CONTINUE_RE.match(
            "授权你去github上学习数字生命的相关知识")
        # 状态/结果询问不触发重做
        assert _CONTINUE_QUERY_RE.search("结果怎么样了")
        assert _CONTINUE_QUERY_RE.search("进展如何")
        assert not _CONTINUE_QUERY_RE.search("继续学习数字生命")


# ── P0-2e: 编译器误判的确定性关键词覆盖 ──────────────────────────────────

class TestP02eExplicitTaskOverride:
    def test_misclassified_explicit_task_creates_goal(self, tmp_path):
        """编译器误判 question + 显式任务开头词 → 强制建目标。"""
        from ocos.interaction.converse import ChatResponder
        from ocos.goal.store import GoalStore
        db = str(tmp_path / "t.db")
        r = ChatResponder(db_path=db)
        # 模拟 E2E 实测的编译器抖动：显式任务被误判为 question
        r.compile_goal = lambda msg: {"kind": "question", "reason": "误判"}
        captured = {}

        def _fake_respond(message, goal_note=None, session_id="web",
                          _emit=None):
            captured["note"] = goal_note
            return {"reply": "ok"}

        r.respond = _fake_respond
        out = r.respond_auto(
            "新建任务：访问 GitHub 学习数字生命相关开源项目并总结",
            session_id="web")
        assert out["kind"] == "task"
        g = GoalStore(db_path=db).load(out["goal_id"])
        assert g is not None and g["status"] == "PENDING"
        assert g["description"].startswith("新建任务：访问 GitHub")
        assert "已自动受理" in captured["note"]

    def test_normal_question_not_overridden(self, tmp_path):
        """普通状态询问不被关键词覆盖。"""
        from ocos.interaction.converse import ChatResponder
        r = ChatResponder(db_path=str(tmp_path / "t.db"))
        r.compile_goal = lambda msg: {"kind": "question", "reason": "询问"}
        r.respond = lambda message, goal_note=None, session_id="web", \
            _emit=None: {"reply": "ok"}
        out = r.respond_auto("现在磁盘还剩多少空间？", session_id="web")
        assert out["kind"] == "question"
        assert out["goal_id"] is None
