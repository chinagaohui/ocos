"""Phase N: OrchestrationEngine 单元测试。"""

import time
from unittest.mock import MagicMock, patch

import pytest

from ocos.orchestration.engine import (
    OrchestrationEngine,
    OrchestrationState,
    OrchestrationMetrics,
    create_orchestration_engine,
)
from ocos.agent_orchestration.registry import AgentRegistry, AgentDescriptor
from ocos.planning.models import Task, Plan, TaskStatus


def create_test_task(task_id: str = "task-1", agent_type: str = "researcher") -> Task:
    """创建测试任务。"""
    return Task.create(
        goal_id="goal-test",
        description=f"Test task {task_id}",
        task_type="execute",
        agent_type=agent_type,
    )


class TestOrchestrationMetrics:
    """OrchestrationMetrics 测试。"""

    def test_initial_state(self):
        metrics = OrchestrationMetrics()
        assert metrics.total_tasks_executed == 0
        assert metrics.total_tasks_completed == 0
        assert metrics.success_rate == 0.0
        assert metrics.uptime_seconds == 0.0

    def test_record_execution_success(self):
        metrics = OrchestrationMetrics()
        metrics.started_at = time.time() - 1.0

        for i in range(5):
            metrics.record_execution(10.0, success=True)

        assert metrics.total_tasks_executed == 5
        assert metrics.total_tasks_completed == 5
        assert metrics.total_tasks_failed == 0
        assert metrics.success_rate == 1.0
        assert metrics.avg_execution_time_ms == 10.0

    def test_record_execution_failure(self):
        metrics = OrchestrationMetrics()
        metrics.record_execution(5.0, success=False)
        metrics.record_execution(8.0, success=True)
        metrics.record_execution(12.0, success=False)

        assert metrics.total_tasks_executed == 3
        assert metrics.total_tasks_completed == 1
        assert metrics.total_tasks_failed == 2
        assert metrics.success_rate == pytest.approx(0.333, abs=0.01)
        assert metrics.avg_execution_time_ms == pytest.approx(8.33, abs=0.1)

    def test_uptime_calculation(self):
        metrics = OrchestrationMetrics()
        metrics.started_at = time.time() - 10.0
        assert metrics.uptime_seconds == pytest.approx(10.0, abs=0.5)


class TestOrchestrationEngine:
    """OrchestrationEngine 核心功能测试。"""

    def test_create_engine(self):
        engine = OrchestrationEngine()
        assert engine.state == OrchestrationState.IDLE
        assert engine.registry is not None

    def test_start_stop(self):
        engine = OrchestrationEngine()
        engine.start()
        assert engine.state == OrchestrationState.RUNNING
        engine.stop()
        assert engine.state == OrchestrationState.STOPPED

    def test_pause_resume(self):
        engine = OrchestrationEngine()
        engine.start()
        engine.pause()
        assert engine.state == OrchestrationState.PAUSED
        engine.resume()
        assert engine.state == OrchestrationState.RUNNING
        engine.stop()

    def test_submit_task(self):
        engine = OrchestrationEngine()
        task = create_test_task()
        result = engine.submit_task(task)
        assert result is True

    def test_process_tick_empty(self):
        engine = OrchestrationEngine()
        engine.start()
        result = engine.process_tick(1)
        assert result["tasks_processed"] == 0
        assert result["collaborations_started"] == 0
        engine.stop()

    def test_hooks(self):
        engine = OrchestrationEngine()
        tick_calls = []

        def on_tick(tick_id):
            tick_calls.append(tick_id)

        engine.on_tick(on_tick)

        engine.start()
        engine.process_tick(1)
        engine.stop()

        assert len(tick_calls) == 1
        assert tick_calls[0] == 1

    def test_get_status(self):
        engine = OrchestrationEngine()
        engine.start()
        status = engine.get_status()
        assert status["state"] == "RUNNING"
        assert "metrics" in status
        assert "pending_tasks" in status
        engine.stop()


class TestFactory:
    """工厂函数测试。"""

    def test_create_orchestration_engine(self):
        engine = create_orchestration_engine(max_pending_tasks=50)
        assert isinstance(engine, OrchestrationEngine)
        assert engine._max_pending_tasks == 50
