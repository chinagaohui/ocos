"""Phase 36: Executive Attention Binding -- tests."""

import pytest
from unittest.mock import MagicMock

from ocos.contracts.attention_abi import (
    AttentionReport,
    AttentionRecommendation,
    DecisionDigest,
    DecisionType,
    AttentionDecision,
    ALLOW_PLANNING,
    DEFER_PLANNING,
    EXECUTION_ALLOW,
    EXECUTION_BLOCK_ATTENTION,
)


class TestAB01_ReportABI:
    def test_report_defaults(self):
        r = AttentionReport()
        assert r.mode == "IDLE"
        assert r.fatigue == 0.0
        assert r.recommendation.suppress_planning is False

    def test_recommendation_idle(self):
        rec = AttentionRecommendation()
        assert rec.suppress_planning is False
        assert rec.ready_for_new_goal is True
        assert rec.is_idle is True

    def test_decision_digest(self):
        d = DecisionDigest(event_id="ev1", decision="ACCEPTED")
        assert d.event_id == "ev1"

    def test_constants(self):
        assert ALLOW_PLANNING == "ALLOW_PLANNING"
        assert DEFER_PLANNING == "DEFER_PLANNING"
        assert EXECUTION_ALLOW == "EXECUTION_ALLOW"
        assert EXECUTION_BLOCK_ATTENTION == "EXECUTION_BLOCK_ATTENTION"


class TestAB02_EmitReport:
    def test_emit_idle(self):
        from ocos.capability.attention import CognitiveAttentionController
        c = CognitiveAttentionController()
        r = c.emit_report(tick_id="t1")
        assert r.mode == "IDLE"
        assert r.recommendation.is_idle is True

    def test_emit_fatigue_suppresses(self):
        from ocos.capability.attention import CognitiveAttentionController
        c = CognitiveAttentionController()
        c._fatigue = 0.95
        r = c.emit_report(tick_id="t2")
        assert r.fatigue > 0.9
        assert r.recommendation.suppress_planning is True

    def test_emit_with_decisions(self):
        from ocos.capability.attention import CognitiveAttentionController
        c = CognitiveAttentionController()
        d1 = AttentionDecision(event_id="e1", decision=DecisionType.ACCEPTED)
        r = c.emit_report(tick_id="t3", last_decisions_raw=[d1])
        assert len(r.last_decisions) >= 1
        assert r.last_decisions[0].event_id == "e1"


class TestAB03_GoalMaintenance:
    def test_empty_goals(self):
        from ocos.agent.agent_runtime import AgentRuntime
        rt = AgentRuntime.__new__(AgentRuntime)
        gs = MagicMock()
        gs.load_active.return_value = []
        rt._goal_store = gs
        rt._attention_report = AttentionReport()
        result = rt._tick_step_goal_maintenance()
        assert result["active_total"] == 0

    def test_deprioritize(self):
        from ocos.agent.agent_runtime import AgentRuntime
        rt = AgentRuntime.__new__(AgentRuntime)
        gs = MagicMock()
        gs.load_active.return_value = [
            {"id": "g1", "priority": 5, "description": "A", "status": "ACTIVE"},
            {"id": "g2", "priority": 8, "description": "B", "status": "ACTIVE"},
        ]
        rt._goal_store = gs
        report = AttentionReport()
        report.recommendation.deprioritize_goals = ["g2"]
        rt._attention_report = report
        result = rt._tick_step_goal_maintenance()
        assert result["skipped_by_attention"] == 1

    def test_depth_limit(self):
        from ocos.agent.agent_runtime import AgentRuntime
        rt = AgentRuntime.__new__(AgentRuntime)
        goals = [{"id": f"g{i}", "priority": i, "status": "ACTIVE"} for i in range(10)]
        gs = MagicMock()
        gs.load_active.return_value = goals
        rt._goal_store = gs
        report = AttentionReport()
        report.recommendation.suggested_maintenance_depth = 2
        rt._attention_report = report
        result = rt._tick_step_goal_maintenance()
        assert result["maintained"] == 2


class TestAB05_ExecutionCheck:
    def test_normal(self):
        from ocos.agent.agent_runtime import AgentRuntime
        rt = AgentRuntime.__new__(AgentRuntime)
        rt.controller = MagicMock()
        rt.controller.get_stats.return_value = {}
        rt.controller.is_blocked.return_value = False
        rt._attention_report = AttentionReport()
        result = rt._tick_step_execution_check()
        assert result["attention_allowed"] is True

    def test_fatigue_block(self):
        from ocos.agent.agent_runtime import AgentRuntime
        rt = AgentRuntime.__new__(AgentRuntime)
        rt.controller = MagicMock()
        rt.controller.get_stats.return_value = {}
        report = AttentionReport()
        report.fatigue = 0.95
        rt._attention_report = report
        result = rt._tick_step_execution_check()
        assert result["attention_allowed"] is False
        assert "ATTENTION_RESOURCE_UNAVAILABLE" in result["attention_block_reason"]

    def test_no_state_mutation(self):
        from ocos.agent.agent_runtime import AgentRuntime
        rt = AgentRuntime.__new__(AgentRuntime)
        rt.controller = MagicMock()
        rt.controller.get_stats.return_value = {}
        rt.controller.is_blocked.return_value = False
        report = AttentionReport()
        report.fatigue = 0.95
        rt._attention_report = report
        rt._tick_step_execution_check()
        rt.controller.set_blocked.assert_not_called()


class TestAB08_PlanningTrigger:
    def test_attention_suppress(self):
        from ocos.agent.agent_runtime import AgentRuntime
        rt = AgentRuntime.__new__(AgentRuntime)
        rt._active_dag = None
        rt._goal_store = None
        report = AttentionReport()
        report.recommendation.suppress_planning = True
        rt._attention_report = report
        result = rt._tick_step_planning_trigger()
        assert result["gated"] is True
        assert result["reason"] == "attention_suppress"

    def test_resource_gate(self):
        from ocos.agent.agent_runtime import AgentRuntime
        rt = AgentRuntime.__new__(AgentRuntime)
        rt._active_dag = MagicMock()
        rt._attention_report = AttentionReport()
        result = rt._tick_step_planning_trigger()
        assert result["gated"] is True
        assert result["reason"] == "resource_saturated"


class TestAB11_Boundary:
    def test_planning_constants(self):
        assert ALLOW_PLANNING == "ALLOW_PLANNING"
        assert DEFER_PLANNING == "DEFER_PLANNING"
        rec = AttentionRecommendation()
        assert not hasattr(rec, "create_plan")
        assert not hasattr(rec, "modify_plan")


class TestAB12_Serialization:
    def test_max_one_per_tick(self):
        from ocos.agent.agent_runtime import AgentRuntime
        rt = AgentRuntime.__new__(AgentRuntime)
        rt._active_dag = None
        rt._attention_report = AttentionReport()
        gs = MagicMock()
        p1, p2, p3 = MagicMock(), MagicMock(), MagicMock()
        for p in (p1, p2, p3):
            s = MagicMock()
            s.name = "PENDING"
            type(p).status = s
        gs.load_active.return_value = [p1, p2, p3]
        rt._goal_store = gs
        result = rt._tick_step_planning_trigger()
        assert result["pending_total"] == 3


class TestAB13_FullFlow:
    def test_full_flow(self):
        from ocos.agent.agent_runtime import AgentRuntime
        from ocos.capability.attention import CognitiveAttentionController
        rt = AgentRuntime.__new__(AgentRuntime)
        rt.controller = MagicMock()
        rt.controller.get_stats.return_value = {}
        rt.controller.is_blocked.return_value = False
        rt._active_dag = None
        ctrl = CognitiveAttentionController()
        rt._attention_report = ctrl.emit_report(tick_id="flow")
        gs = MagicMock()
        gs.load_active.return_value = [
            {"id": "g1", "priority": 5, "description": "X", "status": "ACTIVE"},
        ]
        rt._goal_store = gs
        r4 = rt._tick_step_goal_maintenance()
        assert r4["step"] == 4
        r5 = rt._tick_step_execution_check()
        assert r5["attention_allowed"] is True
        r6 = rt._tick_step_planning_trigger()
        assert r6["step"] == 6

    def test_high_fatigue_full_suppression(self):
        from ocos.agent.agent_runtime import AgentRuntime
        from ocos.capability.attention import CognitiveAttentionController
        rt = AgentRuntime.__new__(AgentRuntime)
        rt.controller = MagicMock()
        rt.controller.get_stats.return_value = {}
        rt.controller.is_blocked.return_value = False
        rt._active_dag = None
        ctrl = CognitiveAttentionController()
        ctrl._fatigue = 0.95
        rt._attention_report = ctrl.emit_report(tick_id="fatigue")
        r5 = rt._tick_step_execution_check()
        assert r5["attention_allowed"] is False
        r6 = rt._tick_step_planning_trigger()
        assert r6["gated"] is True
