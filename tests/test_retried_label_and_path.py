"""UX-J+ 生产测试暴露问题修复: 拦截重试标签错位 + 沙盒 PATH。"""
import os
from unittest.mock import patch

from ocos.autonomous_runtime.action_dispatcher import ActionType
from ocos.execution.bridge import DecisionBridge, DispatchedAction
from ocos.interaction.cli.commands.goal import infer_domain


def _run(bridge, command, auto_readonly=True):
    """驱动 _handler_dag_task: mock LLM 输出序列。

    第 1 次调用 = 任务规划（输出 RUN|<command>）；
    第 2 次调用 = 拦截重试转换（输出 RUN|openclaw --version）。
    """
    payload = {"description": f"执行 {command}"}
    if auto_readonly:
        payload["auto_readonly"] = True
    outputs = iter([f"RUN|{command}", "RUN|openclaw --version"])

    class _FakeProvider:
        async def generate(self, *a, **k):
            return next(outputs)

    class _FakeTG:
        _provider = _FakeProvider()

    bridge._get_textgen = lambda: _FakeTG()
    bridge._llm_available = lambda: True
    bridge._llm_budget_ok = lambda: (True, "")
    return bridge._handler_dag_task(
        DispatchedAction(ActionType.RUN_COMMAND, target="sandbox",
                         payload=payload))


class TestRetriedCommandLabel:
    """拦截→LLM 转换重试后，聚合标签必须用实际执行的命令。"""

    def test_label_follows_executed_command(self):
        b = DecisionBridge()

        def fake_handler(ns):
            cmd = ns.payload["command"]
            if cmd.startswith("curl"):
                return {"ok": False, "blocked": True,
                        "block_reason": "白名单外命令段: curl ..."}
            return {"ok": True, "blocked": False, "exit_code": 0,
                    "stdout": "OpenClaw 2026.8.1"}

        b._handler_run_command = fake_handler
        # LLM 把被拦的 curl 转换成 openclaw --version
        b._convert = lambda reason: "RUN|openclaw --version"
        r = _run(b, "curl -s http://127.0.0.1:11434/api/version")
        assert r.get("ok") is True
        # 修复点: 输出标签是实际执行的 openclaw，而不是原 curl 命令
        assert "$ openclaw --version" in r.get("stdout", "")
        assert "$ curl" not in r.get("stdout", "")

    def test_normal_command_label_unchanged(self):
        b = DecisionBridge()
        b._handler_run_command = lambda ns: {
            "ok": True, "blocked": False, "exit_code": 0,
            "stdout": "Linux"}
        b._convert = lambda reason: ""
        r = _run(b, "uname -s")
        assert "$ uname -s" in r.get("stdout", "")


class TestSandboxPath:
    def test_path_includes_usr_local_bin(self):
        # ollama 装于 /usr/local/bin，缺失导致沙盒 which ollama 落空
        from ocos.operations.sandbox_ops import SandboxCommand, SandboxOps
        os.makedirs("/tmp/ocos_sandbox2", exist_ok=True)
        r = SandboxOps(strict=True).execute(SandboxCommand(
            command="echo $PATH", workdir="/tmp/ocos_sandbox2", timeout=8))
        assert "/usr/local/bin" in (r.stdout or "")


class TestAnswerAction:
    """ANSWER| — 认知型任务直接给结论（不再被迫跑采集命令或判 failed）。"""

    def test_answer_returns_conclusion_as_ok(self):
        b = DecisionBridge()

        class _TG:
            class _provider:
                @staticmethod
                async def generate(*a, **k):
                    return ("ANSWER|**复盘总结：**\n"
                            "1. 宿主机探索：系统健康。\n"
                            "2. 方法论：先发现再调用。")

        b._get_textgen = lambda: _TG()
        b._llm_available = lambda: True
        b._llm_budget_ok = lambda: (True, "")
        r = b._handler_dag_task(DispatchedAction(
            ActionType.RUN_COMMAND, target="sandbox",
            payload={"description": "学习总结：复盘本轮目标",
                     "auto_readonly": True}))
        assert r.get("ok") is True
        # 多行 ANSWER 正文必须完整保留（此前只取首行丢正文）
        assert "复盘总结" in r.get("stdout", "")
        assert "先发现再调用" in r.get("stdout", "")


class TestAnswerGuard:
    """CHAT-ROUTE FIX (2026-09-07): ANSWER| 防幻觉闸门。

    执行类任务（描述含执行动词）不允许 LLM 用纯文字结论蒙混
    success=true——T3 写文件幻觉"验证成功"即此漏洞。
    """

    @staticmethod
    def _bridge_with_outputs(*outputs):
        b = DecisionBridge()
        seq = iter(outputs)

        class _TG:
            class _provider:
                @staticmethod
                async def generate(*a, **k):
                    return next(seq)

        b._get_textgen = lambda: _TG()
        b._llm_available = lambda: True
        b._llm_budget_ok = lambda: (True, "")
        return b

    def test_dropped_when_real_action_present(self):
        """ANSWER 与 RUN 共存 → 剔除 ANSWER，以真实动作为准。"""
        b = self._bridge_with_outputs(
            "ANSWER|文件已创建并验证成功\nRUN|echo hello")
        b._handler_run_command = lambda ns: {
            "ok": True, "blocked": False, "exit_code": 0, "stdout": "hello"}
        r = b._handler_dag_task(DispatchedAction(
            ActionType.RUN_COMMAND, target="sandbox",
            payload={"description": "执行 echo hello 验证",
                     "auto_readonly": True}))
        assert r.get("ok") is True
        assert "hello" in r.get("stdout", "")
        # 幻觉叙述不得混入执行结果
        assert "文件已创建" not in r.get("stdout", "")

    def test_exec_intent_answer_retried_to_real_run(self):
        """执行类任务纯 ANSWER → 带反馈重试一次转真实 RUN。"""
        b = self._bridge_with_outputs(
            "ANSWER|文件已创建，内容验证成功",   # 规划：幻觉
            "RUN|echo OCOS-ALIVE",              # 重试：真实动作
        )
        b._handler_run_command = lambda ns: {
            "ok": True, "blocked": False, "exit_code": 0,
            "stdout": "OCOS-ALIVE"}
        r = b._handler_dag_task(DispatchedAction(
            ActionType.RUN_COMMAND, target="sandbox",
            payload={"description": "在 /tmp 写入 ocos_test.txt 并验证内容",
                     "auto_readonly": True}))
        assert r.get("ok") is True
        assert "$ echo OCOS-ALIVE" in r.get("stdout", "")

    def test_exec_intent_persistent_answer_honest_fail(self):
        """执行类任务重试后仍 ANSWER → 诚实失败（ok=False），不再假成功。"""
        b = self._bridge_with_outputs(
            "ANSWER|已执行完成",
            "ANSWER|真的执行了",
        )
        r = b._handler_dag_task(DispatchedAction(
            ActionType.RUN_COMMAND, target="sandbox",
            payload={"description": "执行 cat /proc/loadavg 并报告",
                     "auto_readonly": True}))
        assert r.get("ok") is False
        assert r.get("honest_blocked") is True
        assert "幻觉" in r.get("error", "")

    def test_analysis_answer_still_allowed(self):
        """分析/复盘类任务纯 ANSWER 维持放行（UX-J+ 本意不回归）。"""
        b = self._bridge_with_outputs(
            "ANSWER|本轮目标执行成功率 100%，方法论有效。")
        r = b._handler_dag_task(DispatchedAction(
            ActionType.RUN_COMMAND, target="sandbox",
            payload={"description": "复盘分析今天的执行记录并总结",
                     "auto_readonly": True}))
        assert r.get("ok") is True
        assert "成功率" in r.get("stdout", "")


class TestDomainInferenceSmoke:
    def test_host_scan_goal(self):
        assert infer_domain(
            "探索宿主机现状：查看操作系统版本、内存容量").value == "analysis"
