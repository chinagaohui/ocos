"""OCOS agent decision_loop/goal_stack/drift_detector 测试。"""

import pytest
from unittest.mock import MagicMock

from ocos.agent.decision_loop import DecisionLoop
from ocos.agent.goal_stack import GoalStack
from ocos.agent.goal_types import Goal, GoalLevel, GoalStatus
from ocos.agent.drift_detector import DriftDetector, DriftSeverity, DriftType


class TestDecisionLoop:
    @pytest.fixture
    def loop(self):
        agent = MagicMock()
        agent.observe.return_value = {"input": "test"}
        agent.think.return_value = {"thought": "thinking"}
        agent.decide.return_value = {"decision": "decided"}
        agent.act.return_value = {"action": "done"}
        agent.learn.return_value = {"learned": True}
        agent.reflect.return_value = None
        agent.intent.get_intent_type.return_value = "create"

        selector = MagicMock()
        selector.map.return_value = ["planner", "writer"]

        controller = MagicMock()
        controller.begin_cycle.return_value = None
        controller.record_phase.return_value = None
        controller.end_cycle.return_value = None
        controller.check_deadlock.return_value = False
        controller.is_blocked.return_value = False
        controller.cycle_count = 1
        controller.reset.return_value = None

        return DecisionLoop(agent, selector, controller)

    def test_execute_single(self, loop):
        result = loop.execute_single()
        assert result["status"] == "completed"
        assert result["intent"] == "create"

    def test_execute_n(self, loop):
        results = loop.execute_n(n=3)
        assert len(results) == 3
        for r in results:
            assert r["status"] == "completed"

    def test_get_history(self, loop):
        loop.execute_single()
        history = loop.get_history()
        assert len(history) > 0

    def test_reset(self, loop):
        loop.execute_single()
        loop.reset()
        assert loop.get_history() == []


class TestGoalStack:
    @pytest.fixture
    def stack(self):
        return GoalStack()

    def test_empty_stack(self, stack):
        assert stack.depth() == 0
        assert stack.peek() is None

    def test_push_and_peek(self, stack):
        goal = Goal(
            goal_id="g1",
            level=GoalLevel.TASK,
            description="Test goal",
            priority=0.5,
        )
        stack.push(goal)
        assert stack.depth() == 1
        peeked = stack.peek()
        assert peeked is not None
        assert peeked.goal_id == "g1"

    def test_push_pop(self, stack):
        goal1 = Goal(goal_id="g1", level=GoalLevel.TASK, description="G1", priority=0.5)
        goal2 = Goal(goal_id="g2", level=GoalLevel.SHORT, description="G2", priority=0.8)
        stack.push(goal1)
        stack.push(goal2)
        popped = stack.pop()
        assert popped is not None
        assert popped.goal_id == "g2"
        assert stack.depth() == 1

    def test_cancel_goal(self, stack):
        goal = Goal(goal_id="g1", level=GoalLevel.TASK, description="G1", priority=0.5)
        stack.push(goal)
        result = stack.cancel("g1")
        assert result is True
        # Cancel changes status but doesn't remove from stack
        assert stack.depth() == 1
        # Verify status changed
        active = stack.get_active()
        assert len(active) == 0  # No ACTIVE goals after cancel

    def test_cancel_nonexistent(self, stack):
        result = stack.cancel("nonexistent")
        assert result is False

    def test_get_active(self, stack):
        g1 = Goal(goal_id="g1", level=GoalLevel.TASK, description="G1", priority=0.5)
        g2 = Goal(goal_id="g2", level=GoalLevel.SHORT, description="G2", priority=0.8)
        stack.push(g1)
        stack.push(g2)
        active = stack.get_active()
        assert len(active) == 2

    def test_clear(self, stack):
        stack.push(Goal(goal_id="g1", level=GoalLevel.TASK, description="G1", priority=0.5))
        stack.clear()
        assert stack.depth() == 0

    def test_get_highest_priority(self, stack):
        g1 = Goal(goal_id="g1", level=GoalLevel.TASK, description="G1", priority=0.3)
        g2 = Goal(goal_id="g2", level=GoalLevel.SHORT, description="G2", priority=0.9)
        stack.push(g1)
        stack.push(g2)
        highest = stack.get_highest_priority()
        assert highest is not None
        assert highest.goal_id == "g2"


class TestDriftDetector:
    @pytest.fixture
    def detector(self):
        return DriftDetector()

    def test_no_drift_normal_scores(self, detector):
        alert = detector.check_goal_drift(alignment_score=0.8)
        assert alert is None

    def test_goal_drift_after_multiple_low_scores(self, detector):
        for i in range(5):
            alert = detector.check_goal_drift(alignment_score=0.1, goal_id=f"g{i}")
        assert alert is not None
        assert alert.drift_type == DriftType.PREFERENCE

    def test_capability_drift(self, detector):
        for _ in range(10):
            detector.record_capability_usage("cap_a")
        for _ in range(2):
            detector.record_capability_usage("cap_b")
        alert = detector.check_capability_drift()
        assert alert is not None
        assert alert.drift_type == DriftType.CAPABILITY

    def test_confidence_drift(self, detector):
        for _ in range(5):
            alert = detector.check_confidence_drift(calibration_delta=0.5)
        assert alert is not None
        assert alert.drift_type == DriftType.CONFIDENCE

    def test_check_all(self, detector):
        alerts = detector.check_all(
            alignment_score=0.1,
            calibration_delta=0.5,
        )
        assert isinstance(alerts, list)

    def test_get_status(self, detector):
        status = detector.get_status()
        assert "total_executions" in status
        assert "avg_alignment" in status

    def test_drift_severity_levels(self, detector):
        # Simulate many consecutive drifts to trigger CRITICAL
        for _ in range(10):
            alert = detector.check_goal_drift(alignment_score=0.05)
        assert alert is not None
        assert alert.severity == DriftSeverity.CRITICAL
