"""R4-A: DecisionBridge 定向测试 — 自治决策 → 真实任务执行铰链。

覆盖:
  1. 装配: capability_reality 发现并注册为 dispatcher handlers
  2. AUTO 动作 (HEALTH_CHECK / CONSOLIDATE_MEMORY) 真实执行 + 审计落库
  3. ASK 动作 (WRITE_CHAPTER) 停在待批, 不执行
  4. PermissionGuard 语义双检 (拒绝 → deny)
  5. DAG 任务: 只读 analyze/verify → 真实执行; create/modify/execute → 待批
  6. 空决策 → idle (不误触发)
"""

import json
import os
import tempfile
import uuid
from pathlib import Path

import pytest

from ocos.autonomous_runtime.action_dispatcher import ActionDispatcher, ActionType
from ocos.execution.bridge import (
    AUTO_ACTIONS,
    ASK_ACTIONS,
    ActionVerdict,
    BridgeReport,
    DecisionBridge,
)
from ocos.agent_orchestration.audit import ExecutionAudit
from ocos.planning.models import Task


# ── fixtures ────────────────────────────────────────────────────────────

@pytest.fixture
def bridge():
    """真实装配: AdapterDiscovery 发现 + dispatcher + audit (tmp 隔离)。"""
    audit = ExecutionAudit()
    b = DecisionBridge(audit=audit)
    b.attach_default_handlers()
    return b


def _core_loop_result(text: str) -> dict:
    """构造 step 7 core_loop 的决策输出 (action_result.based_on.thought)。"""
    return {
        "status": "completed",
        "action_result": {
            "based_on": {"message": text},
            "result": {"engine": "cognitive"},
        },
    }


# ── 1. 装配 ────────────────────────────────────────────────────────────

class TestAssembly:
    def test_attach_discovers_capabilities(self, bridge):
        assert bridge._registry is not None
        assert bridge._registry.count() > 0
        assert bridge._registry.has("filesystem")

    def test_attach_registers_handlers(self, bridge):
        for at in (ActionType.HEALTH_CHECK, ActionType.CONSOLIDATE_MEMORY,
                   ActionType.REFLECT, ActionType.FEEDBACK_PROCESS):
            assert at in bridge.dispatcher._handlers, f"{at.name} handler missing"

    def test_risk_lists_cover_action_types(self):
        known = {a for a in ActionType}
        assert AUTO_ACTIONS | ASK_ACTIONS == known, "风险分级表必须覆盖全部 ActionType"


# ── 2. AUTO 真实执行 ───────────────────────────────────────────────────

class TestAutoExecution:
    def test_health_check_executes_and_audits(self, bridge):
        report = bridge.process(_core_loop_result("running health check on system"))
        summary = report.summary()
        assert summary["total"] == 1
        assert "HEALTH_CHECK" in summary["executed"]
        # 审计落库
        completed = [r for r in bridge.audit_records
                     if getattr(r, "status", "") == "completed"]
        assert completed, "AUTO 动作必须有 completed 审计记录"

    def test_consolidate_writes_real_file(self, bridge, tmp_path):
        bridge._exec_path = lambda kind: str(tmp_path / f"{kind}-{uuid.uuid4().hex[:6]}.json")
        report = bridge.process(_core_loop_result("please consolidate memory now"))
        assert "CONSOLIDATE_MEMORY" in report.summary()["executed"]
        files = list(tmp_path.glob("consolidation-*.json"))
        assert files, "consolidation 必须真实写文件"
        payload = json.loads(files[0].read_text(encoding="utf-8"))
        assert payload["kind"] == "consolidation"

    def test_reflect_writes_real_file(self, bridge, tmp_path):
        bridge._exec_path = lambda kind: str(tmp_path / f"{kind}-{uuid.uuid4().hex[:6]}.json")
        bridge.process(_core_loop_result("reflect on today's observations"))
        assert list(tmp_path.glob("reflection-*.json")), "reflection 必须真实写文件"

    def test_auto_verdict_reason(self, bridge):
        report = bridge.process(_core_loop_result("health check"))
        v = report.verdicts[0]
        assert v.verdict == "auto"
        assert "low-risk" in v.reason


# ── 3. ASK 待批 ────────────────────────────────────────────────────────

class TestAskPending:
    def test_write_chapter_pending(self, bridge):
        report = bridge.process(_core_loop_result("write chapter 12 of the novel"))
        summary = report.summary()
        assert "WRITE_CHAPTER" in summary["pending"]
        assert bridge.pending_actions, "ASK 动作必须进入待批队列"
        assert bridge.pending_actions[0]["action_type"] == "WRITE_CHAPTER"
        # 不执行: 无真实产物
        assert not bridge.audit_records, "ASK 动作不得产生执行审计"

    def test_search_web_pending(self, bridge):
        report = bridge.process(_core_loop_result("search web for latest news"))
        assert "SEARCH_WEB" in report.summary()["pending"]

    def test_unknown_action_noop_auto(self, bridge):
        """未匹配文本 → dispatcher 回退 NOOP (无害, AUTO 执行, 零副作用);
        真正未分类的非 NOOP 动作类型才走 ask 兜底 (见 _adjudicate 末尾)。"""
        report = bridge.process(_core_loop_result("do something totally exotic"))
        summary = report.summary()
        assert summary["by_verdict"].get("auto", 0) == 1
        assert summary["executed"] == ["NOOP"]
        assert not bridge.pending_actions


# ── 4. PermissionGuard 双检 ────────────────────────────────────────────

class TestPermissionGuard:
    def test_deny_when_semantic_forbidden(self):
        class DenyGuard:
            def check(self, action, context):
                from ocos.interaction.base import ConstitutionResult
                return ConstitutionResult(allowed=False, violations=[f"{action} forbidden"])
        b = DecisionBridge(guard=DenyGuard())  # type: ignore[arg-type]
        b.attach_default_handlers()
        report = b.process(_core_loop_result("health check"))
        assert report.summary()["by_verdict"].get("deny", 0) == 1
        assert "permission denied" in report.verdicts[0].reason

    def test_allow_when_semantic_allowed(self, bridge):
        report = bridge.process(_core_loop_result("health check"))
        assert report.summary()["by_verdict"].get("deny", 0) == 0


# ── 5. DAG 任务 ────────────────────────────────────────────────────────

class TestDagTask:
    def _task(self, task_type: str, description: str):
        return Task.create(
            goal_id="GOAL-TEST",
            description=description,
            task_type=task_type,
            agent_type="data_processor",
        )

    def test_readonly_analyze_executes(self, bridge):
        task = self._task("analyze", "analyze files under /home/laogao/Documents")
        result = bridge.execute_dag_task(task)
        assert result["status"] == "completed"
        # 最特异路径优先: stat 的是 Documents 而非被前缀遮蔽的 home
        assert result["result"]["ok"] is True
        assert result["result"]["output"]["path"] == "/home/laogao/Documents"
        # 审计
        assert any(getattr(r, "status", "") == "completed" for r in bridge.audit_records)

    def test_readonly_verify_executes(self, bridge):
        task = self._task("verify", "verify existence of /tmp")
        result = bridge.execute_dag_task(task)
        assert result["status"] == "completed"

    def test_create_pending_approval(self, bridge):
        task = self._task("create", "create report.md under /tmp/reports")
        result = bridge.execute_dag_task(task)
        assert result["status"] == "pending_approval"
        assert "R4-B" in result["reason"]

    def test_modify_pending_approval(self, bridge):
        task = self._task("modify", "edit config file")
        assert bridge.execute_dag_task(task)["status"] == "pending_approval"

    def test_execute_pending_approval(self, bridge):
        task = self._task("execute", "run deployment script")
        assert bridge.execute_dag_task(task)["status"] == "pending_approval"

    def test_unmatched_falls_back_to_echo(self, bridge):
        task = self._task("analyze", "zzz no path hint anywhere")
        result = bridge.execute_dag_task(task)
        assert result["status"] == "echo_fallback"

    def test_executor_failure_reports_failed(self, bridge, monkeypatch):
        """执行器失败 → 诚实 failed (不伪装 completed, 不静默回退 echo)。"""
        task = self._task("verify", "verify existence of /tmp")
        monkeypatch.setattr(
            bridge, "_exec_fs",
            lambda op, path, content="": {"ok": False, "output": "", "error": "boom"})
        result = bridge.execute_dag_task(task)
        assert result["status"] == "failed"
        assert any(getattr(r, "status", "") == "failed" for r in bridge.audit_records)


# ── 5b. AgentRuntime 接线契约 ──────────────────────────────────────────

class TestRuntimeWiring:
    """step 7 与 DecisionBridge 的接线: 裸实例兼容 + 状态诚实透传。"""

    def _bare_rt(self, dag):
        from ocos.agent.agent_runtime import AgentRuntime
        rt = AgentRuntime.__new__(AgentRuntime)
        rt._active_dag = dag
        rt._dag_cursor = 0
        rt._dag_total = len(dag.tasks)
        rt._task_statuses = {}
        rt._recent_results = []
        return rt  # 故意不设 _decision_bridge — 验证裸实例兼容 (Phase 31 合约)

    def _dag(self, task_type: str, description: str):
        from ocos.planning.models import TaskDAG
        dag = TaskDAG()
        task = Task.create(goal_id="GOAL-TEST", description=description,
                           task_type=task_type, agent_type="data_processor")
        dag.add_task(task)
        return dag, task.id

    def test_bare_instance_falls_back_to_echo(self):
        """裸实例无 _decision_bridge 属性 → AttributeError 不再被吞, 走 EchoAgent。"""
        dag, tid = self._dag("verify", "review the design doc for gaps")
        rt = self._bare_rt(dag)
        rt._tick_step_core_loop()
        assert rt._task_statuses.get(tid) == "completed"
        assert rt._recent_results[0]["success"] is True

    def test_failed_status_passthrough(self, bridge, monkeypatch):
        """bridge 返回 failed → step 7 如实标 failed (不折算成 pending_approval)。"""
        dag, tid = self._dag("verify", "verify existence of /tmp")
        rt = self._bare_rt(dag)
        rt.attach_decision_bridge(bridge)
        monkeypatch.setattr(
            bridge, "_exec_fs",
            lambda op, path, content="": {"ok": False, "output": "", "error": "boom"})
        rt._tick_step_core_loop()
        assert rt._task_statuses.get(tid) == "failed"
        assert rt._recent_results[0]["success"] is False

    def test_attach_decision_bridge_public(self, bridge):
        """公开装配入口 — factory 不再需要捅私有属性。"""
        rt = self._bare_rt(self._dag("analyze", "x")[0])
        rt.attach_decision_bridge(bridge)
        assert rt._decision_bridge is bridge


# ── 6. 边界 ────────────────────────────────────────────────────────────

class TestEdgeCases:
    def test_empty_decision_idle(self, bridge):
        report = bridge.process({})
        assert report.summary()["total"] == 0

    def test_no_action_result_idle(self, bridge):
        report = bridge.process({"status": "completed"})
        assert report.summary()["total"] == 0

    def test_based_on_str_direct(self, bridge):
        report = bridge.process({"based_on": "health check"})
        assert "HEALTH_CHECK" in report.summary()["executed"]

    def test_recent_reports_accumulate(self, bridge):
        bridge.process(_core_loop_result("health check"))
        bridge.process(_core_loop_result("health check"))
        assert len(bridge.recent_reports) == 2


# ── 7. 集成: build_execution_bridge 装配 ───────────────────────────────

class TestFactoryIntegration:
    def test_build_execution_bridge_attaches(self):
        from ocos.daemon.factory import build_execution_bridge
        from ocos.agent.agent_runtime import AgentRuntime

        agent = AgentRuntime.__new__(AgentRuntime)  # 免构造, 仅验证 attach 语义
        agent._decision_bridge = None
        bridge = build_execution_bridge(agent)
        assert agent._decision_bridge is bridge
        assert bridge._registry is not None
