"""Phase 33: ResidentRuntime daemon — lifecycle + goal processing."""
import time
import pytest
from unittest.mock import MagicMock


def _make_agent():
    agent = MagicMock()
    agent.state.status.name = "IDLE"
    agent.attention = MagicMock()
    agent.attention.update = MagicMock()
    agent.attention.current_focus = "none"
    agent.goal_stack = MagicMock()
    agent.goal_stack.get_active_count.return_value = 0
    return agent


class TestPhase33Daemon:
    """ResidentRuntime daemon lifecycle tests."""

    def test_start_stop_lifecycle(self):
        from ocos.daemon import ResidentRuntime, DaemonState
        rt = ResidentRuntime(_make_agent(), db_path=":memory:", tick_interval=0.1, max_cycles=10)
        assert rt.state == DaemonState.STOPPED

        rt.start()
        time.sleep(0.3)
        assert rt.state == DaemonState.RUNNING

        rt.stop(timeout=2.0)
        assert rt.state == DaemonState.STOPPED

    def test_daemon_runs_ticks(self):
        from ocos.daemon import ResidentRuntime
        rt = ResidentRuntime(_make_agent(), db_path=":memory:", tick_interval=0.1, max_cycles=100)
        rt.start()
        time.sleep(0.6)
        assert rt.cycle_count >= 3  # at least 3 ticks in 0.6s with 0.1s interval
        rt.stop(timeout=2.0)

    def test_submit_goal_while_running(self):
        from ocos.daemon import ResidentRuntime
        rt = ResidentRuntime(_make_agent(), db_path=":memory:", tick_interval=0.1, max_cycles=100)
        rt.start()
        time.sleep(0.2)

        n = rt.submit_goal("测试目标", domain="development")
        assert n == 1
        time.sleep(0.5)

        status = rt.get_status()
        rt.stop(timeout=2.0)

    def test_goal_processed_count(self):
        from ocos.daemon import ResidentRuntime
        rt = ResidentRuntime(_make_agent(), db_path=":memory:", tick_interval=0.1, max_cycles=100)
        rt.start()
        rt.submit_goal("g1", domain="development")
        rt.submit_goal("g2", domain="research")
        time.sleep(0.8)

        # goals should be processed (popped from queue, UserGoal created)
        assert rt._goal_processed == 2
        assert len(rt._goal_queue) == 0
        rt.stop(timeout=2.0)

    def test_stop_clears_cycles(self):
        from ocos.daemon import ResidentRuntime
        rt = ResidentRuntime(_make_agent(), db_path=":memory:", tick_interval=0.05, max_cycles=100)
        rt.start()
        time.sleep(0.4)
        cycles_before = rt.cycle_count
        rt.stop(timeout=2.0)
        cycles_after = rt.cycle_count
        # cycles should not increase after stop
        assert cycles_after == cycles_before

    def test_resume_after_restart(self):
        from ocos.daemon import ResidentRuntime
        rt = ResidentRuntime(_make_agent(), db_path=":memory:", tick_interval=0.05, max_cycles=100)
        rt.start()
        time.sleep(0.2)
        cycles1 = rt.cycle_count
        rt.stop(timeout=2.0)

        rt.start()
        time.sleep(0.2)
        cycles2 = rt.cycle_count
        rt.stop(timeout=2.0)
        # after restart, cycles count starts fresh
        assert cycles2 > 0
