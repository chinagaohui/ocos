"""AUD-F14: 主链路薄覆盖模块的穿透 E2E 测试。

覆盖 proactive / alerts / decision / execution(DENY 路径) 四个
测试函数数最少的入口可达包。
"""

from __future__ import annotations

import json

import pytest


# ── 1. alerts: Manager → FileChannel 落盘端到端 ────────────────────────

class TestAlertsFileChannelE2E:
    def test_alert_lands_on_disk(self, tmp_path):
        from ocos.alerts.channels import FileChannel
        from ocos.alerts.manager import AlertManager
        from ocos.alerts.models import AlertLevel

        logfile = tmp_path / "alerts.log"
        mgr = AlertManager()
        mgr.register_channel(FileChannel(str(logfile)))
        mgr.send(AlertLevel.WARNING, "test_source", "memory pressure high",
                 detail={"episodes": 9000})

        lines = logfile.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 1
        payload = json.loads(lines[0])
        assert payload["level"] in ("WARNING", "warning")
        assert "memory pressure" in str(payload)


# ── 2. proactive: 触发链 fail-closed 端到端 ────────────────────────────

class TestProactiveGateE2E:
    def test_no_goal_no_output(self):
        """无 SELF 目标 → 频率闸门+来源闸门双检 fail-closed，零输出。"""
        from ocos.proactive.engine import ProactiveEngine

        engine = ProactiveEngine()
        out = engine.maybe_proactive_output()
        assert out is None, "无内生目标时不得主动输出"

    def test_gate_reason_visible(self):
        """闸门拒绝原因可观测（诚实降级）。"""
        from ocos.proactive.engine import ProactiveEngine

        engine = ProactiveEngine()
        engine.maybe_proactive_output()
        checks = engine._checks_pass()
        assert checks[0] is False
        assert checks[1], "拒绝必须有原因"


# ── 3. decision: 组件链 → 提案 → 治理验证 → tracer 端到端 ─────────────

class TestDecisionChainE2E:
    def test_proposal_generated_and_traced(self):
        from ocos.cognitive_loop.decision_pipeline import DecisionPipeline
        from ocos.cognitive_loop.loop_types import LoopContext

        ctx = LoopContext(tick_id=42, perception_input="系统收到新观察")
        pipeline = DecisionPipeline()
        out = pipeline.process(ctx)

        # 提案来自真实组件链（非字符串拼接占位）
        assert out.decision_proposal, "有感知输入必须产出决策提案"
        # tracer 落了完整决策轨迹
        assert pipeline._tracer, "tracer 必须记录轨迹"
        assert out.decision_approved is not None

    def test_no_input_no_decision(self):
        from ocos.cognitive_loop.decision_pipeline import DecisionPipeline
        from ocos.cognitive_loop.loop_types import LoopContext

        ctx = LoopContext(tick_id=1)
        out = DecisionPipeline().process(ctx)
        assert out.decision_proposal == ""


# ── 4. execution: DENY 路径 + 审计端到端 ───────────────────────────────

class TestExecutionDenyE2E:
    def test_deny_action_recorded(self):
        """DENY 分类的动作 → 拒绝 + 可见 reason，不执行不入待批。"""
        from ocos.autonomous_runtime.action_dispatcher import (
            ActionDispatcher,
            ActionType,
        )
        from ocos.execution.bridge import DecisionBridge
        from ocos.interaction.base import ConstitutionResult

        class DenyAllGuard:
            def check(self, action, context):
                return ConstitutionResult(
                    allowed=False, violations=[f"{action} forbidden"])

        bridge = DecisionBridge(guard=DenyAllGuard())
        bridge.attach_default_handlers()
        report = bridge.process({
            "status": "completed",
            "action_result": {"based_on": {"message": "running health check"}},
        })
        summary = report.summary()
        assert summary["by_verdict"].get("deny", 0) == 1
        assert summary["executed"] == []
        assert bridge.pending_actions == []
        assert "permission denied" in report.verdicts[0].reason

    def test_dispatcher_no_handler_is_honest_failure(self):
        """ASK 类动作无 handler → dispatch 失败（不伪装完成）。"""
        from ocos.autonomous_runtime.action_dispatcher import (
            ActionDispatcher,
            ActionType,
        )
        dispatcher = ActionDispatcher()
        result = dispatcher.dispatch(ActionType.WRITE_CHAPTER, "open_tale", {})
        assert result.status == "failed"
        assert "No handler" in str(result.result)


class TestSandboxPathGate:
    """P6 (2026-09-01): 沙盒敏感路径拦截 — 公开只读文件放行, 敏感文件仍拦。

    回归场景: 宿主机信息收集任务 (cat /etc/os-release) 此前被 /etc 前缀
    一刀切拦截 → LLM 规划失败 → 目标 honest failed。修复后精确放行
    /etc/os-release; /etc/shadow 等敏感文件必须继续拦截。
    """

    def _bridge(self):
        from ocos.execution.bridge import DecisionBridge
        bridge = DecisionBridge()
        bridge.attach_default_handlers()
        return bridge

    def _cmd(self, command: str):
        """构造 RUN_COMMAND DispatchedAction（真实类型, 非 duck-type）。"""
        from ocos.autonomous_runtime.action_dispatcher import (
            ActionDispatcher, ActionType, DispatchedAction)
        return DispatchedAction(ActionType.RUN_COMMAND, "sandbox",
                                {"command": command})

    def test_public_os_release_allowed(self):
        """cat /etc/os-release（公开只读）→ 放行, 不触发敏感拦截。"""
        bridge = self._bridge()
        result = bridge._handler_run_command(self._cmd("cat /etc/os-release"))
        assert result.get("blocked") is not True
        assert not result.get("block_reason")

    def test_sensitive_etc_shadow_still_blocked(self):
        """cat /etc/shadow（敏感）→ 仍拦截。"""
        bridge = self._bridge()
        result = bridge._handler_run_command(self._cmd("cat /etc/shadow"))
        assert result.get("blocked") is True
        assert "敏感路径" in result.get("block_reason", "")

    def test_compound_command_segments_checked(self):
        """复合命令分段校验: 合法段 + 敏感段 → 敏感段仍拦截。"""
        bridge = self._bridge()
        result = bridge._handler_run_command(
            self._cmd("uname -a && cat /etc/shadow"))
        assert result.get("blocked") is True
        assert "敏感路径" in result.get("block_reason", "")
