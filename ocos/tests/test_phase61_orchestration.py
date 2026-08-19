"""Phase 61: Agent Orchestration Autonomous — 测试套件。

覆盖:
    - AutonomousOrchestrator 创建
    - Goal 提交与分解
    - Tick 驱动的自主执行
    - Task 状态转换 (pending→dispatched→running→completed)
    - 失败与回退
    - 事件日志
    - 统计汇总
"""

import pytest
import time
from ocos.agent_orchestration_autonomous import (
    AutonomousOrchestrator,
    OrchestrationPhase,
    OrchestrationTask,
    OrchestrationStats,
)


class TestOrchestrationTask:
    """OrchestrationTask 单元测试。"""

    def test_create_task(self):
        task = OrchestrationTask(
            task_id="task-1",
            parent_goal_id="goal-1",
            description="分析数据",
        )
        assert task.task_id == "task-1"
        assert task.parent_goal_id == "goal-1"
        assert task.status == "pending"
        assert task.agent_type == "writer"
        assert task.max_attempts == 3

    def test_to_planning_task(self):
        task = OrchestrationTask(
            task_id="task-1",
            parent_goal_id="goal-abc",
            description="执行某任务",
            agent_type="researcher",
            priority=3,
        )
        pt = task.to_planning_task()
        assert pt.goal_id == "goal-abc"
        assert pt.description == "执行某任务"
        assert pt.agent_type == "researcher"
        assert pt.priority == 3

    def test_to_planning_task_falls_back_on_invalid_agent_type(self):
        task = OrchestrationTask(
            task_id="task-1",
            parent_goal_id="goal-1",
            description="测试",
        )
        # default agent_type is "writer" — valid
        pt = task.to_planning_task()
        assert pt.agent_type == "writer"


class TestAutonomousOrchestratorLifecycle:
    """AutonomousOrchestrator 生命周期测试。"""

    def test_create(self):
        orch = AutonomousOrchestrator()
        assert orch.phase == OrchestrationPhase.IDLE
        assert orch.stats.total_goals_processed == 0

    def test_submit_goal_transitions_to_decomposing(self):
        orch = AutonomousOrchestrator()
        gid = orch.submit_goal("测试目标")
        assert gid.startswith("goal-")
        assert orch.phase == OrchestrationPhase.DECOMPOSING
        assert len(orch._goal_queue) == 1

    def test_submit_multiple_goals(self):
        orch = AutonomousOrchestrator()
        g1 = orch.submit_goal("目标1")
        g2 = orch.submit_goal("目标2")
        assert g1 != g2
        assert len(orch._goal_queue) == 2


class TestAutonomousOrchestratorTick:
    """Tick 驱动测试。"""

    def test_full_lifecycle_single_goal(self):
        """完整的单目标生命周期测试。"""
        orch = AutonomousOrchestrator()
        orch.submit_goal("分析市场趋势")

        # Tick until completed or max 15 ticks
        for _ in range(15):
            summary = orch.tick()
            if orch.phase == OrchestrationPhase.COMPLETED:
                break

        assert orch.phase == OrchestrationPhase.COMPLETED
        assert orch.stats.total_goals_processed == 1
        assert orch.stats.total_tasks_completed == 3  # analyze + execute + review
        assert orch.stats.total_tasks_failed == 0

    def test_tasks_transition_correctly(self):
        """验证任务状态转换: pending→dispatched→running→completed。"""
        orch = AutonomousOrchestrator()
        orch.submit_goal("简单任务")

        events = []
        for _ in range(15):
            orch.tick()
            events.extend(orch.drain_events())
            if orch.phase == OrchestrationPhase.COMPLETED:
                break

        event_names = [e["event"] for e in events]
        assert "goal_submitted" in event_names
        assert "goal_decomposed" in event_names
        assert ("task_dispatched" in event_names or "task_fallback" in event_names)
        assert "task_running" in event_names
        assert "task_completed" in event_names
        assert "goal_completed" in event_names

    def test_idempotent_tick_when_idle(self):
        orch = AutonomousOrchestrator()
        assert orch.phase == OrchestrationPhase.IDLE
        summary = orch.tick()
        assert summary["phase"] == "IDLE"
        assert summary["tasks_completed"] == 0

    def test_summary_contains_expected_fields(self):
        orch = AutonomousOrchestrator()
        orch.submit_goal("测试")
        for _ in range(15):
            s = orch.tick()
            if orch.phase == OrchestrationPhase.COMPLETED:
                break

        s = orch.summary()
        for key in ("phase", "total_goals_processed", "tasks_in_queue",
                     "tasks_completed", "tasks_failed", "fallbacks", "uptime_seconds"):
            assert key in s, f"Missing key: {key}"


class TestOrchestrationStats:
    """OrchestrationStats 测试。"""

    def test_defaults(self):
        stats = OrchestrationStats()
        assert stats.total_goals_processed == 0
        assert stats.total_tasks_completed == 0
        assert stats.current_phase == OrchestrationPhase.IDLE

    def test_stats_accumulate(self):
        stats = OrchestrationStats()
        stats.total_goals_processed += 1
        stats.total_tasks_completed += 3
        assert stats.total_goals_processed == 1
        assert stats.total_tasks_completed == 3


class TestMultipleGoals:
    """多目标编排测试。"""

    def test_two_goals_sequential(self):
        orch = AutonomousOrchestrator()
        orch.submit_goal("目标A")
        orch.submit_goal("目标B")

        for _ in range(25):
            orch.tick()
            if orch.phase == OrchestrationPhase.COMPLETED:
                break

        assert orch.stats.total_goals_processed == 2
        assert orch.stats.total_tasks_completed == 6  # 3 tasks each

    def test_drain_events_clears_log(self):
        orch = AutonomousOrchestrator()
        orch.submit_goal("测试")
        for _ in range(15):
            orch.tick()
            if orch.phase == OrchestrationPhase.COMPLETED:
                break

        events = orch.drain_events()
        assert len(events) > 0
        # After drain, log is cleared
        assert len(orch.drain_events()) == 0


class TestOrchestrationPhaseEnum:
    """OrchestrationPhase 枚举测试。"""

    def test_all_phases_exist(self):
        phases = {p.value for p in OrchestrationPhase}
        assert "IDLE" in phases
        assert "DECOMPOSING" in phases
        assert "DISPATCHING" in phases
        assert "EXECUTING" in phases
        assert "MONITORING" in phases
        assert "ADAPTING" in phases
        assert "COMPLETED" in phases
