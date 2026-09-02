"""Phase AB: DistributedCognitionManager — MasterAgent 集成测试。

覆盖维度：
1. 管理器注入
2. 实例注册与注销
3. 心跳与健康检查
4. 任务提交与分发
5. 任务完成与失败
6. 统计信息
7. tick 接口
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock

from ocos.agent.master_agent import MasterAgent
from ocos.distributed.manager import DistributedCognitionManager, InstanceState


@pytest.fixture
def mock_agent():
    """创建带有模拟依赖的 Agent 实例。"""
    mock_identity = MagicMock()
    mock_goal_stack = MagicMock()
    mock_intent = MagicMock()
    mock_attention = MagicMock()
    mock_working_memory = MagicMock()
    mock_capability_manager = MagicMock()
    mock_execution_manager = MagicMock()

    return MasterAgent(
        agent_id="test-agent",
        identity=mock_identity,
        goal_stack=mock_goal_stack,
        intent=mock_intent,
        attention=mock_attention,
        working_memory=mock_working_memory,
        capability_manager=mock_capability_manager,
        execution_manager=mock_execution_manager,
    )


@pytest.fixture
def agent_with_distributed(mock_agent):
    """创建带有分布式管理器的 Agent 实例。"""
    dm = DistributedCognitionManager()
    mock_agent._distributed_manager = dm
    return mock_agent


# =========================================================================
# 1. 管理器注入测试
# =========================================================================

class TestInjection:
    """注入测试。"""

    def test_inject_distributed_manager(self, mock_agent):
        """注入分布式管理器。"""
        dm = DistributedCognitionManager()
        mock_agent._distributed_manager = dm
        assert mock_agent.distributed_manager == dm

    def test_missing_distributed_manager(self, mock_agent):
        """未注入时应返回 None。"""
        assert mock_agent.distributed_manager is None


# =========================================================================
# 2. 实例管理
# =========================================================================

class TestInstanceManagement:
    """实例管理测试。"""

    def test_register_instance(self, agent_with_distributed):
        """注册认知实例。"""
        result = agent_with_distributed.register_cognition_instance(
            "inst-1", "localhost", 8080,
        )
        assert "instance_id" in result
        assert result["instance_id"] == "inst-1"

    def test_register_without_manager(self, mock_agent):
        """未注入时注册应返回错误。"""
        result = mock_agent.register_cognition_instance("inst-1", "localhost", 8080)
        assert "error" in result

    def test_deregister_instance(self, agent_with_distributed):
        """注销认知实例。"""
        agent_with_distributed.register_cognition_instance("inst-1", "localhost", 8080)
        result = agent_with_distributed.deregister_cognition_instance("inst-1")
        assert result is True

    def test_heartbeat(self, agent_with_distributed):
        """更新心跳。"""
        agent_with_distributed.register_cognition_instance("inst-1", "localhost", 8080)
        result = agent_with_distributed.heartbeat_instance("inst-1")
        assert result is True


# =========================================================================
# 3. 任务管理
# =========================================================================

class TestTaskManagement:
    """任务管理测试。"""

    def test_submit_task(self, agent_with_distributed):
        """提交任务。"""
        result = agent_with_distributed.submit_distributed_task(
            "cognitive", {"input": "test"},
        )
        assert "task_id" in result
        assert result["status"] == "pending"

    def test_submit_without_manager(self, mock_agent):
        """未注入时提交任务应返回错误。"""
        result = mock_agent.submit_distributed_task("test", {})
        assert "error" in result

    def test_complete_task(self, agent_with_distributed):
        """完成任务。"""
        result = agent_with_distributed.submit_distributed_task("test", {})
        task_id = result["task_id"]

        # 需要手动分发到活跃状态
        task = next((t for t in agent_with_distributed._distributed_manager._pending_tasks
                     if t.task_id == task_id), None)
        if task:
            agent_with_distributed._distributed_manager._active_tasks[task_id] = task
            agent_with_distributed._distributed_manager._pending_tasks.remove(task)

        result = agent_with_distributed.complete_distributed_task(task_id, {"ok": True})
        assert result is True

    def test_fail_task(self, agent_with_distributed):
        """标记任务失败。"""
        result = agent_with_distributed.submit_distributed_task("test", {})
        task_id = result["task_id"]

        task = next((t for t in agent_with_distributed._distributed_manager._pending_tasks
                     if t.task_id == task_id), None)
        if task:
            agent_with_distributed._distributed_manager._active_tasks[task_id] = task
            agent_with_distributed._distributed_manager._pending_tasks.remove(task)

        result = agent_with_distributed.fail_distributed_task(task_id, "error")
        assert result is True


# =========================================================================
# 4. 统计信息
# =========================================================================

class TestStatistics:
    """统计信息测试。"""

    def test_get_stats(self, agent_with_distributed):
        """获取统计信息。"""
        stats = agent_with_distributed.get_distributed_stats()
        assert "instance_count" in stats
        assert "tasks_submitted" in stats

    def test_get_stats_without_manager(self, mock_agent):
        """未注入时返回错误。"""
        stats = mock_agent.get_distributed_stats()
        assert "error" in stats

    def test_get_healthy_instances(self, agent_with_distributed):
        """获取健康实例。"""
        agent_with_distributed.register_cognition_instance("inst-1", "localhost", 8080)
        agent_with_distributed.heartbeat_instance("inst-1")

        instances = agent_with_distributed.get_healthy_instances()
        assert len(instances) == 1
        assert instances[0]["instance_id"] == "inst-1"


# =========================================================================
# 5. 健康检查
# =========================================================================

class TestHealth:
    """健康检查测试。"""

    def test_check_health(self, agent_with_distributed):
        """检查分布式健康。"""
        unhealthy = agent_with_distributed.check_distributed_health()
        assert isinstance(unhealthy, list)


# =========================================================================
# 6. Tick 接口
# =========================================================================

class TestTick:
    """主循环 tick 测试。"""

    def test_tick_with_distributed(self, agent_with_distributed):
        """有分布式管理器时的 tick。"""
        result = agent_with_distributed.tick()
        assert "distributed" in result
        assert "evolutions" in result

    def test_tick_without_distributed(self, mock_agent):
        """无分布式管理器时的 tick。"""
        result = mock_agent.tick()
        assert result["distributed"] == {}


# =========================================================================
# 端到端测试
# =========================================================================

class TestEndToEnd:
    """端到端完整流程测试。"""

    def test_full_distributed_workflow(self, agent_with_distributed):
        """完整分布式工作流。"""
        # 1. 注册实例
        r1 = agent_with_distributed.register_cognition_instance("inst-1", "localhost", 8080)
        r2 = agent_with_distributed.register_cognition_instance("inst-2", "localhost", 8081)
        assert r1["instance_id"] == "inst-1"
        assert r2["instance_id"] == "inst-2"

        # 2. 心跳
        agent_with_distributed.heartbeat_instance("inst-1")
        agent_with_distributed.heartbeat_instance("inst-2")

        # 3. 提交任务
        task1 = agent_with_distributed.submit_distributed_task("cognitive", {"data": "test1"})
        task2 = agent_with_distributed.submit_distributed_task("cognitive", {"data": "test2"})
        assert task1["task_id"].startswith("task:")
        assert task2["task_id"].startswith("task:")

        # 4. 获取统计
        stats = agent_with_distributed.get_distributed_stats()
        assert stats["tasks_submitted"] == 2
        assert stats["instance_count"] == 2

        # 5. 获取健康实例
        instances = agent_with_distributed.get_healthy_instances()
        assert len(instances) == 2

        # 6. tick
        result = agent_with_distributed.tick()
        assert "distributed" in result
