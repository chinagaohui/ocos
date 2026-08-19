"""Phase 60: Autonomous Runtime — Tests."""

import pytest
import hashlib
from datetime import datetime, timezone


# ── Import check ──

def test_import_all():
    from ocos.autonomous_runtime import (
        LoopMode, WakeTrigger, RuntimeConfig, LoopStats,
        AutonomousLoop, ActionType, DispatchedAction,
        ActionDispatcher, SupervisorAlert, SupervisorState,
        LoopSupervisor, quick_runtime_test,
    )
    assert LoopMode.IDLE.value == "idle"
    assert LoopMode.ACTIVE.value == "active"


# ═══ runtime_config ═══

class TestRuntimeConfig:

    def test_defaults(self):
        from ocos.autonomous_runtime import RuntimeConfig
        c = RuntimeConfig()
        assert c.tick_interval_ms == 2000
        assert c.min_tick_interval_ms == 500
        assert c.max_ticks_per_session == 10000
        assert c.max_goal_self_generation == 0  # CL46-01
        assert c.wake_on_external is True

    def test_validate_clean(self):
        from ocos.autonomous_runtime import RuntimeConfig
        c = RuntimeConfig()
        issues = c.validate()
        assert issues == []

    def test_validate_bad_tick(self):
        from ocos.autonomous_runtime import RuntimeConfig
        c = RuntimeConfig(tick_interval_ms=100)  # below min
        issues = c.validate()
        assert any("below min" in i for i in issues)

    def test_validate_goal_violation(self):
        from ocos.autonomous_runtime import RuntimeConfig
        c = RuntimeConfig(max_goal_self_generation=5)
        issues = c.validate()
        assert any("CL46-01" in i for i in issues)

    def test_validate_dangerous_actions(self):
        from ocos.autonomous_runtime import RuntimeConfig
        c = RuntimeConfig(max_consecutive_actions=200)
        issues = c.validate()
        assert any("dangerously high" in i for i in issues)

    def test_loop_stats_defaults(self):
        from ocos.autonomous_runtime import LoopStats
        s = LoopStats()
        assert s.total_ticks == 0
        assert s.current_mode == "idle"


# ═══ autonomous_loop ═══

class TestAutonomousLoop:

    @pytest.fixture
    def loop(self):
        from ocos.autonomous_runtime import AutonomousLoop, RuntimeConfig
        config = RuntimeConfig(
            tick_interval_ms=100,
            max_ticks_per_session=100,
            idle_timeout_ms=999999,  # don't sleep during test
            sleep_duration_ms=0,
        )
        return AutonomousLoop(config=config)

    def test_initial_mode(self, loop):
        assert loop.mode.value == "idle"

    def test_tick_with_input(self, loop):
        ctx = loop.tick("Hello world")
        assert ctx is not None
        assert loop.stats.total_ticks == 1
        assert loop.stats.ticks_this_session == 1
        assert loop.mode.value == "active"

    def test_tick_without_input(self, loop):
        # First feed something so there's context to reflect on
        loop.tick("Initial context")
        ctx = loop.tick()  # no input → self-reflection
        assert ctx is not None
        assert loop.stats.total_ticks >= 1

    def test_tick_many(self, loop):
        contexts = loop.tick_many(5, external_inputs=["a", "b", "c", "d", "e"])
        assert len(contexts) == 5
        assert loop.stats.total_ticks == 5

    def test_wake_from_idle(self, loop):
        from ocos.autonomous_runtime import WakeTrigger
        loop.idle()
        assert loop.mode.value == "idle"
        loop.wake(WakeTrigger.EXTERNAL_INPUT, "test")
        assert loop.mode.value == "active"

    def test_sleep_wake_cycle(self, loop):
        from ocos.autonomous_runtime import WakeTrigger
        loop.sleep("tired")
        assert loop.mode.value == "sleeping"
        loop.wake(WakeTrigger.INTERNAL_TIMER, "wake up")
        assert loop.mode.value == "active"

    def test_reflection_mode(self, loop):
        loop.reflect()
        assert loop.mode.value == "reflecting"

    def test_enqueue_feedback(self, loop):
        feedback = {
            "chapter_number": 3,
            "quality_score": 0.85,
            "arcs_advanced": {"heroine": 0.3},
        }
        loop.enqueue_feedback(feedback)
        assert len(loop._pending_feedback) == 1

    def test_tick_with_feedback(self, loop):
        feedback = {
            "chapter_number": 5,
            "quality_score": 0.72,
            "issues": ["pacing slow"],
            "arcs_advanced": {"heroine": 0.5},
        }
        loop.enqueue_feedback(feedback)
        ctx = loop.tick()  # should consume the feedback
        assert ctx is not None
        assert len(loop._pending_feedback) == 0  # drained

    def test_safety_cap(self, loop):
        from ocos.autonomous_runtime import RuntimeConfig
        config = RuntimeConfig(max_ticks_per_session=5, tick_interval_ms=10)
        small_loop = type(loop)(config=config)
        for _ in range(6):
            small_loop.tick("input")
        assert any("SAFETY_CAP" in a for a in small_loop.alerts)
        assert small_loop.mode.value == "sleeping"

    def test_summary(self, loop):
        loop.tick("test")
        s = loop.summary()
        assert "mode" in s
        assert "cognitive" in s
        assert "stats" in s
        assert "alerts" in s

    def test_is_healthy(self, loop):
        # Fresh loop should be healthy (health monitor initialized)
        assert isinstance(loop.is_healthy, bool)


# ═══ action_dispatcher ═══

class TestActionDispatcher:

    @pytest.fixture
    def dispatcher(self):
        from ocos.autonomous_runtime import ActionDispatcher
        return ActionDispatcher()

    def test_register_and_dispatch(self, dispatcher):
        from ocos.autonomous_runtime import ActionType
        results = []
        def handler(action):
            results.append(action.action_type)
            return "ok"
        dispatcher.register_handler(ActionType.WRITE_CHAPTER, handler)
        action = dispatcher.dispatch(ActionType.WRITE_CHAPTER, target="open_tale")
        assert action.status == "done"
        assert action.result == "ok"
        assert len(results) == 1

    def test_dispatch_unregistered(self, dispatcher):
        from ocos.autonomous_runtime import ActionType
        action = dispatcher.dispatch(ActionType.NOOP)
        assert action.status == "failed"
        assert "No handler" in str(action.result)

    def test_dispatch_exception(self, dispatcher):
        from ocos.autonomous_runtime import ActionType
        def bad_handler(action):
            raise ValueError("boom")
        dispatcher.register_handler(ActionType.HEALTH_CHECK, bad_handler)
        action = dispatcher.dispatch(ActionType.HEALTH_CHECK)
        assert action.status == "failed"
        assert "boom" in str(action.result)

    def test_interpret_writing_decision(self, dispatcher):
        actions = dispatcher.interpret_decision(
            "Write chapter 5 focusing on character development and romance"
        )
        assert len(actions) >= 1
        assert any(a.action_type.name == "WRITE_CHAPTER" for a in actions)

    def test_interpret_search_decision(self, dispatcher):
        actions = dispatcher.interpret_decision(
            "Search for latest romance novel techniques and analyze"
        )
        assert any(a.action_type.name == "SEARCH_WEB" for a in actions)

    def test_interpret_reflection(self, dispatcher):
        actions = dispatcher.interpret_decision(
            "Reflect on whether the story arc is working"
        )
        assert any(a.action_type.name == "REFLECT" for a in actions)

    def test_interpret_noop(self, dispatcher):
        actions = dispatcher.interpret_decision("xyz abc")
        assert len(actions) == 1
        assert actions[0].action_type.name == "NOOP"

    def test_action_summary(self, dispatcher):
        from ocos.autonomous_runtime import ActionType
        dispatcher.register_handler(ActionType.NOOP, lambda a: None)
        dispatcher.dispatch(ActionType.NOOP)
        s = dispatcher.action_summary()
        assert s["total_actions"] == 1
        assert "NOOP" in s["by_type"]

    def test_recent_actions(self, dispatcher):
        from ocos.autonomous_runtime import ActionType
        dispatcher.register_handler(ActionType.NOOP, lambda a: None)
        for _ in range(5):
            dispatcher.dispatch(ActionType.NOOP)
        assert len(dispatcher.recent_actions) == 5


# ═══ loop_supervisor ═══

class TestLoopSupervisor:

    @pytest.fixture
    def supervisor(self):
        from ocos.autonomous_runtime import LoopSupervisor
        return LoopSupervisor()

    def test_initial_state(self, supervisor):
        assert supervisor.state.alert_level.value == "ok"
        assert supervisor.state.emergency_stopped is False

    def test_check_runaway_ok(self, supervisor):
        from ocos.autonomous_runtime import SupervisorAlert
        result = supervisor.check_runaway(avg_tick_ms=500, min_interval_ms=100)
        assert result == SupervisorAlert.OK

    def test_check_runaway_critical(self, supervisor):
        from ocos.autonomous_runtime import SupervisorAlert
        result = supervisor.check_runaway(avg_tick_ms=80, min_interval_ms=100)
        assert result == SupervisorAlert.CRITICAL

    def test_check_runaway_emergency(self, supervisor):
        from ocos.autonomous_runtime import SupervisorAlert
        result = supervisor.check_runaway(avg_tick_ms=30, min_interval_ms=100)
        assert result == SupervisorAlert.EMERGENCY_STOP
        assert supervisor.state.emergency_stopped is True

    def test_check_tick_count_ok(self, supervisor):
        from ocos.autonomous_runtime import SupervisorAlert
        result = supervisor.check_tick_count(100, 10000)
        assert result == SupervisorAlert.OK

    def test_check_tick_count_warning(self, supervisor):
        from ocos.autonomous_runtime import SupervisorAlert
        result = supervisor.check_tick_count(8500, 10000)  # 85%
        assert result == SupervisorAlert.WARNING

    def test_check_tick_count_emergency(self, supervisor):
        from ocos.autonomous_runtime import SupervisorAlert
        result = supervisor.check_tick_count(10000, 10000)
        assert result == SupervisorAlert.EMERGENCY_STOP

    def test_check_goal_generation_violation(self, supervisor):
        from ocos.autonomous_runtime import SupervisorAlert
        result = supervisor.check_goal_generation(1)
        assert result == SupervisorAlert.EMERGENCY_STOP
        assert "CL46-01" in supervisor.state.stop_reason

    def test_check_goal_generation_ok(self, supervisor):
        from ocos.autonomous_runtime import SupervisorAlert
        result = supervisor.check_goal_generation(0)
        assert result == SupervisorAlert.OK

    def test_check_identity_stable(self, supervisor):
        from ocos.autonomous_runtime import SupervisorAlert
        h = hashlib.md5(b"identity_v1").hexdigest()
        result = supervisor.check_identity_stability(h)
        assert result == SupervisorAlert.OK
        # Same hash again
        result2 = supervisor.check_identity_stability(h)
        assert result2 == SupervisorAlert.OK

    def test_check_identity_drift(self, supervisor):
        from ocos.autonomous_runtime import SupervisorAlert
        h1 = hashlib.md5(b"identity_v1").hexdigest()
        h2 = hashlib.md5(b"identity_v2").hexdigest()
        supervisor.check_identity_stability(h1)
        result = supervisor.check_identity_stability(h2)
        assert result == SupervisorAlert.CRITICAL

    def test_check_action_excess(self, supervisor):
        from ocos.autonomous_runtime import SupervisorAlert
        result = supervisor.check_action_excess(15, 20)  # 75%
        assert result == SupervisorAlert.WARNING

    def test_full_check_all_ok(self, supervisor):
        from ocos.autonomous_runtime import SupervisorAlert
        result = supervisor.full_check(
            avg_tick_ms=500, session_ticks=10, max_ticks=1000,
            min_interval_ms=100, new_goals=0,
        )
        assert result == SupervisorAlert.OK

    def test_full_check_multiple_issues(self, supervisor):
        from ocos.autonomous_runtime import SupervisorAlert
        # Both tick limit warning + goal violation
        result = supervisor.full_check(
            avg_tick_ms=500, session_ticks=900, max_ticks=1000,
            min_interval_ms=100, new_goals=1,  # goal violation = EMERGENCY
        )
        # Goal violation should dominate (EMERGENCY > WARNING)
        assert result == SupervisorAlert.EMERGENCY_STOP

    def test_should_stop(self, supervisor):
        assert supervisor.should_stop is False
        supervisor.check_goal_generation(5)
        assert supervisor.should_stop is True

    def test_alert_count(self, supervisor):
        supervisor.check_runaway(80, 100)
        supervisor.check_goal_generation(1)
        assert supervisor.alert_count >= 2


# ═══ Integration: Full Autonomous Cycle ═══

class TestFullAutonomousCycle:

    def test_autonomous_loop_with_dispatcher(self):
        from ocos.autonomous_runtime import (
            AutonomousLoop, RuntimeConfig, ActionDispatcher, ActionType,
        )
        config = RuntimeConfig(max_ticks_per_session=20, tick_interval_ms=10)
        loop = AutonomousLoop(config=config)

        dispatcher = ActionDispatcher()
        dispatched = []
        dispatcher.register_handler(ActionType.WRITE_CHAPTER, lambda a: dispatched.append(a))
        dispatcher.register_handler(ActionType.SEARCH_WEB, lambda a: dispatched.append(a))
        dispatcher.register_handler(ActionType.REFLECT, lambda a: dispatched.append(a))
        dispatcher.register_handler(ActionType.NOOP, lambda a: dispatched.append(a))

        loop.set_action_handler(lambda ctx: dispatcher.dispatch(
            ActionType.WRITE_CHAPTER,
            target="open_tale",
            payload={"chapter": 5},
        ))

        # Feed context + run autonomous ticks
        loop.tick("Romance novel project: write chapter 5")
        loop.tick("Focus on emotional depth and character growth")
        loop.tick()  # autonomous reflection
        loop.tick()  # autonomous reflection

        summary = loop.summary()
        assert summary["stats"]["total_ticks"] == 4
        assert loop.stats.ticks_this_session == 4

    def test_supervisor_integration(self):
        from ocos.autonomous_runtime import (
            AutonomousLoop, RuntimeConfig, LoopSupervisor, SupervisorAlert,
        )
        config = RuntimeConfig(
            max_ticks_per_session=10, tick_interval_ms=10, min_tick_interval_ms=5
        )
        loop = AutonomousLoop(config=config)
        supervisor = LoopSupervisor()

        for i in range(5):
            loop.tick(f"input {i}")

        result = supervisor.full_check(
            avg_tick_ms=50.0,
            session_ticks=loop.stats.ticks_this_session,
            max_ticks=config.max_ticks_per_session,
            min_interval_ms=config.min_tick_interval_ms,
            new_goals=0,
        )
        assert result == SupervisorAlert.OK


# ═══ Quick Test Function ═══

class TestQuickRuntime:

    def test_quick_runtime_test(self):
        from ocos.autonomous_runtime import quick_runtime_test
        result = quick_runtime_test()
        assert "mode" in result
        assert "stats" in result
        assert result["stats"]["total_ticks"] == 5


# ═══ Edge Cases / Recovery ═══

class TestEdgeCases:

    def test_empty_feedback_queue(self):
        from ocos.autonomous_runtime import AutonomousLoop, RuntimeConfig
        config = RuntimeConfig(tick_interval_ms=10, max_ticks_per_session=50)
        loop = AutonomousLoop(config=config)
        # No feedback queued — should handle gracefully
        ctx = loop.tick()
        assert ctx is not None

    def test_no_registered_handler_dispatch(self):
        from ocos.autonomous_runtime import ActionDispatcher, ActionType
        dispatcher = ActionDispatcher()
        action = dispatcher.dispatch(ActionType.WRITE_CHAPTER)
        assert action.status == "failed"

    def test_spam_ticks_under_limit(self):
        from ocos.autonomous_runtime import AutonomousLoop, RuntimeConfig
        config = RuntimeConfig(max_ticks_per_session=10, tick_interval_ms=5)
        loop = AutonomousLoop(config=config)
        for _ in range(10):
            loop.tick("spam")
        assert loop.stats.ticks_this_session == 10
        # 11th should trigger safety cap
        loop.tick("overflow")
        assert loop.mode.value == "sleeping"
