"""Phase 62b: AgentPool — 测试套件。

覆盖:
    - AgentPool 创建与配置
    - execute_sync 空列表 / 单任务 / 多任务
    - execute_sync 并发执行顺序保持
    - 超时处理
    - 失败 fallback
    - PoolResult / PoolStats
    - max_concurrent 验证
"""

import pytest
from unittest.mock import MagicMock
from ocos.agent_orchestration.agent_pool import (
    AgentPool,
    PoolResult,
    PoolStats,
)
from ocos.agent_orchestration.contract import ExecutionContract


# ── Helpers ──────────────────────────────────────────────────────────────────


def make_contract(task_id: str, agent_id: str = "writer", timeout: int = 10) -> ExecutionContract:
    """创建最小可用的 ExecutionContract。"""
    return ExecutionContract.create(
        task_id=task_id,
        agent_id=agent_id,
        timeout_seconds=timeout,
    )


class TestPoolResult:
    """PoolResult 测试。"""

    def test_success_result(self):
        r = PoolResult(task_id="t1", success=True, output="done")
        assert r.task_id == "t1"
        assert r.success is True
        assert r.output == "done"
        assert r.error is None
        assert not r.timeout

    def test_failure_result(self):
        r = PoolResult(task_id="t2", success=False, error="boom")
        assert not r.success
        assert r.error == "boom"

    def test_timeout_result(self):
        r = PoolResult.timeout_result("t3", 30)
        assert not r.success
        assert r.timeout is True
        assert "Timed out" in (r.error or "")

    def test_exception_result(self):
        r = PoolResult.exception_result("t4", ValueError("bad"), elapsed_ms=100)
        assert not r.success
        assert "bad" in (r.error or "")
        assert r.elapsed_ms == 100


class TestPoolStats:
    """PoolStats 测试。"""

    def test_defaults(self):
        s = PoolStats()
        assert s.tasks_submitted == 0
        assert s.success_rate == 1.0

    def test_success_rate(self):
        s = PoolStats(tasks_submitted=10, tasks_succeeded=7, tasks_failed=3)
        assert s.success_rate == 0.7


class TestAgentPool:
    """AgentPool 核心测试。"""

    def test_create_with_defaults(self):
        pool = AgentPool()
        assert pool.max_concurrent == 3
        assert pool.execution_timeout == 0.0

    def test_create_custom(self):
        pool = AgentPool(max_concurrent=8, execution_timeout=60.0)
        assert pool.max_concurrent == 8
        assert pool.execution_timeout == 60.0

    def test_create_invalid(self):
        with pytest.raises(ValueError, match="must be >= 1"):
            AgentPool(max_concurrent=0)

    def test_execute_sync_empty(self):
        pool = AgentPool()
        results = pool.execute_sync([])
        assert results == []

    def test_execute_sync_single_success(self):
        pool = AgentPool()
        contract = make_contract("task-1")
        pool.executor = MagicMock()
        pool.executor.execute.return_value = (True, "result-1", None)

        results = pool.execute_sync([contract])

        assert len(results) == 1
        assert results[0].task_id == "task-1"
        assert results[0].success is True
        assert results[0].output == "result-1"
        assert pool.stats.tasks_succeeded == 1
        pool.executor.execute.assert_called_once()

    def test_execute_sync_single_failure(self):
        pool = AgentPool()
        contract = make_contract("task-fail")
        pool.executor = MagicMock()
        pool.executor.execute.return_value = (False, "", "exec error")

        results = pool.execute_sync([contract])

        assert len(results) == 1
        assert not results[0].success
        assert results[0].error == "exec error"
        assert pool.stats.tasks_failed == 1

    def test_execute_sync_multiple_mixed(self):
        pool = AgentPool()
        contracts = [make_contract(f"task-{i}") for i in range(3)]

        call_count = [0]

        def side_effect(contract):
            call_count[0] += 1
            # contract.contract_id is auto-generated, use task_id
            if contract.task_id == "task-1":
                return False, "", "error!"
            return True, f"output-{contract.task_id}", None

        pool.executor = MagicMock()
        pool.executor.execute.side_effect = side_effect

        results = pool.execute_sync(contracts)

        assert len(results) == 3
        assert call_count[0] == 3

        succeeded = [r for r in results if r.success]
        failed = [r for r in results if not r.success]
        assert len(succeeded) == 2
        assert len(failed) == 1

        # 结果顺序保持
        assert results[0].task_id == "task-0"
        assert results[1].task_id == "task-1"
        assert results[2].task_id == "task-2"

    def test_execute_sync_exception_handling(self):
        pool = AgentPool()
        contract = make_contract("task-exc")
        pool.executor = MagicMock()
        pool.executor.execute.side_effect = RuntimeError("crash!")

        results = pool.execute_sync([contract])

        assert len(results) == 1
        assert not results[0].success
        assert "crash!" in (results[0].error or "")
        assert pool.stats.tasks_failed == 1

    def test_max_concurrent_reached(self):
        pool = AgentPool(max_concurrent=2)
        contracts = [make_contract(f"task-{i}") for i in range(5)]
        pool.executor = MagicMock()
        pool.executor.execute.return_value = (True, "ok", None)

        pool.execute_sync(contracts)

        assert pool.stats.max_concurrent_reached is True

    def test_stats_reset(self):
        pool = AgentPool()
        contract = make_contract("t1")
        pool.executor = MagicMock()
        pool.executor.execute.return_value = (True, "ok", None)

        pool.execute_sync([contract])

        assert pool.stats.tasks_submitted == 1

        pool.reset_stats()
        assert pool.stats.tasks_submitted == 0
        assert pool.stats.success_rate == 1.0

    def test_executor_created_lazily(self):
        pool = AgentPool()
        assert pool.executor is None

        # Trigger lazy creation via _get_executor
        ex = pool._get_executor()
        assert pool.executor is not None
        assert pool._executor_created is True

    def test_can_inject_executor(self):
        pool = AgentPool()
        fake_executor = MagicMock()
        fake_executor.execute.return_value = (True, "injected", None)
        pool.executor = fake_executor

        results = pool.execute_sync([make_contract("t1")])
        assert results[0].output == "injected"
