"""Phase 62c: AgentPool 接入 AutonomousOrchestrator — 测试套件。

覆盖:
    - AutonomousOrchestrator 接受 AgentPool 注入
    - 无 pool 时保持原有行为（向后兼容）
    - 有 pool 时单 tick 完成全部任务（并行 dispatch）
    - _task_to_contract 转换正确
    - pool 失败场景
"""

import pytest
from unittest.mock import MagicMock
from ocos.agent_orchestration_autonomous import (
    AutonomousOrchestrator,
    OrchestrationPhase,
    OrchestrationTask,
)
from ocos.agent_orchestration.agent_pool import AgentPool, PoolResult


class TestAutonomousOrchestratorPoolIntegration:
    """AgentPool 集成测试。"""

    def test_orchestrator_accepts_pool(self):
        pool = AgentPool(max_concurrent=3)
        orch = AutonomousOrchestrator()
        orch._pool = pool
        assert orch._pool is pool

    def test_without_pool_uses_serial_dispatch(self):
        """无 pool 时保持原有行为：任务分步 dispatched→running→completed。"""
        orch = AutonomousOrchestrator()
        orch.submit_goal("test")

        # Tick 0: decompose + dispatch (tasks set to dispatched, then monitor sets to running)
        s0 = orch.tick()
        assert s0["phase"] in ("EXECUTING",)
        running = [t for t in orch._task_queue if t.status == "running"]
        assert len(running) == 3  # all 3 dispatched → running as monitor ticks

    def test_with_pool_single_tick_completion(self):
        """有 pool 时，单 tick 完成全部任务（无需等待 dispatched→running→completed）。"""
        pool = AgentPool(max_concurrent=3)
        pool.executor = MagicMock()
        pool.executor.execute.return_value = (True, "ok", None)

        orch = AutonomousOrchestrator()
        orch._pool = pool
        orch.submit_goal("test")

        # 第一 tick: decompose + dispatch via pool
        s = orch.tick()
        assert s["phase"] in ("COMPLETED", "MONITORING", "DECOMPOSING")
        # 任务应该已经完成
        assert orch.stats.total_tasks_completed == 3
        assert orch.stats.total_goals_processed == 1

    def test_with_pool_two_goals_fast_completion(self):
        """有 pool 时，两个 goal 在更少 tick 内完成。"""
        pool = AgentPool(max_concurrent=3)
        pool.executor = MagicMock()
        pool.executor.execute.return_value = (True, "ok", None)

        orch = AutonomousOrchestrator()
        orch._pool = pool
        orch.submit_goal("Goal-A")
        orch.submit_goal("Goal-B")

        for _ in range(10):
            s = orch.tick()
            if s["phase"] == "COMPLETED":
                break

        assert s["total_goals_processed"] == 2
        assert s["phase"] == "COMPLETED"
        assert orch.stats.total_tasks_completed == 6  # 3 per goal

    def test_pool_failure_handling(self):
        """Pool 返回失败结果时，应正确记录。"""
        pool = AgentPool(max_concurrent=3)
        pool.executor = MagicMock()

        # 第一个成功，第二个失败，第三个成功
        def side_effect(contract):
            if "execute" in contract.task_id:
                return False, "", "execution error"
            return True, "ok", None

        pool.executor.execute.side_effect = side_effect

        orch = AutonomousOrchestrator()
        orch._pool = pool
        orch.submit_goal("test")
        orch.tick()

        assert orch.stats.total_tasks_completed == 2  # analyze + review
        assert orch.stats.total_tasks_failed == 1  # execute
        # goal 未完成（因为 execute 任务失败，只有 2 个 completed）
        assert orch.stats.total_goals_processed == 0

    def test_task_to_contract(self):
        """_task_to_contract 生成正确的 ExecutionContract。"""
        orch = AutonomousOrchestrator()
        task = OrchestrationTask(
            task_id="goal-0-execute",
            parent_goal_id="goal-0",
            description="执行: 分析市场",
            agent_type="writer",
            priority=2,
        )
        contract = orch._task_to_contract(task)
        assert contract.task_id == "goal-0-execute"
        assert contract.agent_id == "writer"
        assert contract.timeout_seconds == 30
        assert "分析市场" in contract.input_spec["description"]

    def test_pool_results_mapped_correctly(self):
        """PoolResults 被正确映射到任务状态。"""
        pool = AgentPool(max_concurrent=3)
        pool.executor = MagicMock()
        pool.executor.execute.return_value = (True, "all done", None)

        orch = AutonomousOrchestrator()
        orch._pool = pool
        orch.submit_goal("test")
        orch.tick()

        # 所有任务都在 _completed_tasks 中
        assert len(orch._completed_tasks) == 3
        for task in orch._completed_tasks:
            assert task.status == "completed"
            assert task.completed_at > 0
            assert task.result_summary == "all done"

    def test_dispatch_via_pool_adds_events(self):
        """pool dispatch 产生正确的 event log。"""
        pool = AgentPool(max_concurrent=3)
        pool.executor = MagicMock()
        pool.executor.execute.return_value = (True, "ok", None)

        orch = AutonomousOrchestrator()
        orch._pool = pool
        orch.submit_goal("test")
        orch.tick()

        events = orch.drain_events()
        event_names = [e["event"] for e in events]
        assert "goal_submitted" in event_names
        assert "goal_decomposed" in event_names
        assert "task_completed" in event_names
        assert event_names.count("task_completed") == 3
        assert "goal_completed" in event_names
