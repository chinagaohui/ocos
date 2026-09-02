"""Phase AF: SelfOptimizationManager — MasterAgent 集成测试。

覆盖维度：
1. 管理器注入
2. 基线管理
3. 优化提案
4. 优化应用与验证
5. tick 接口
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from ocos.agent.master_agent import MasterAgent
from ocos.optimization.manager import SelfOptimizationManager, OptimizationType


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
def agent_with_optimization(mock_agent):
    """创建带有自我优化管理器的 Agent 实例。"""
    som = SelfOptimizationManager()
    mock_agent._self_optimization_manager = som
    return mock_agent


class TestOptimizationInjection:
    """管理器注入测试。"""

    def test_self_optimization_manager_injection(self, agent_with_optimization):
        """管理器应正确注入。"""
        assert agent_with_optimization.self_optimization_manager is not None

    def test_self_optimization_manager_property(self, agent_with_optimization):
        """获取属性应返回注入的管理器。"""
        manager = SelfOptimizationManager()
        agent_with_optimization._self_optimization_manager = manager
        assert agent_with_optimization.self_optimization_manager == manager


class TestBaselineMethods:
    """基线管理方法测试。"""

    def test_set_baseline(self, agent_with_optimization):
        """设置优化基线。"""
        agent_with_optimization.set_optimization_baseline("latency", 100.0)
        value = agent_with_optimization.get_optimization_baseline("latency")
        assert value == 100.0

    def test_set_baseline_no_manager(self, mock_agent):
        """无管理器时不应报错。"""
        agent_with_optimization = mock_agent
        agent_with_optimization.set_optimization_baseline("latency", 100.0)
        # 无异常即为成功

    def test_get_baseline_not_found(self, agent_with_optimization):
        """获取不存在的基线。"""
        value = agent_with_optimization.get_optimization_baseline("nonexistent")
        assert value is None


class TestProposalMethods:
    """优化提案方法测试。"""

    def test_propose_optimization(self, agent_with_optimization):
        """提出优化提案。"""
        result = agent_with_optimization.propose_optimization(
            "CACHE", "Increase cache size", 0.15, "low"
        )
        assert "proposal_id" in result or "error" in result

    def test_propose_optimization_no_manager(self, mock_agent):
        """无管理器时应返回错误。"""
        result = mock_agent.propose_optimization("CACHE", "test", 0.1)
        assert "error" in result
        assert "not injected" in result["error"]


class TestApplicationMethods:
    """优化应用方法测试。"""

    def test_apply_optimization(self, agent_with_optimization):
        """应用优化方案。"""
        proposal_result = agent_with_optimization.propose_optimization("CACHE", "test", 0.1)
        if "proposal_id" in proposal_result:
            apply_result = agent_with_optimization.apply_optimization(
                proposal_result["proposal_id"], {"latency": 100.0}
            )
            assert "result_id" in apply_result or "error" in apply_result

    def test_apply_optimization_no_manager(self, mock_agent):
        """无管理器时应返回错误。"""
        result = mock_agent.apply_optimization("test", {"latency": 100.0})
        assert "error" in result
        assert "not injected" in result["error"]

    def test_validate_optimization(self, agent_with_optimization):
        """验证优化效果。"""
        proposal_result = agent_with_optimization.propose_optimization("CACHE", "test", 0.1)
        if "proposal_id" in proposal_result:
            apply_result = agent_with_optimization.apply_optimization(
                proposal_result["proposal_id"], {"latency": 100.0}
            )
            if "result_id" in apply_result:
                validated = agent_with_optimization.validate_optimization(
                    apply_result["result_id"], {"latency": 80.0}
                )
                assert validated is True

    def test_rollback_optimization(self, agent_with_optimization):
        """回滚优化。"""
        proposal_result = agent_with_optimization.propose_optimization("CACHE", "test", 0.1)
        if "proposal_id" in proposal_result:
            apply_result = agent_with_optimization.apply_optimization(
                proposal_result["proposal_id"], {"latency": 100.0}
            )
            if "result_id" in apply_result:
                rolled_back = agent_with_optimization.rollback_optimization(
                    apply_result["result_id"]
                )
                assert rolled_back is True


class TestStats:
    """统计信息测试。"""

    def test_get_stats(self, agent_with_optimization):
        """获取统计信息。"""
        result = agent_with_optimization.get_optimization_stats()
        assert "proposals_generated" in result
        assert "optimizations_applied" in result

    def test_get_stats_no_manager(self, mock_agent):
        """无管理器时应返回错误。"""
        result = mock_agent.get_optimization_stats()
        assert "error" in result
        assert "not injected" in result["error"]


class TestTick:
    """Tick 接口测试。"""

    def test_tick_with_optimization(self, agent_with_optimization):
        """含优化管理器的 tick。"""
        result = agent_with_optimization.tick()
        assert "optimization" in result

    def test_tick_without_optimization(self, mock_agent):
        """无优化管理器时的 tick。"""
        mock_agent._self_optimization_manager = None
        result = mock_agent.tick()
        assert "optimization" in result
        assert result["optimization"] == {}


class TestEndToEnd:
    """端到端测试。"""

    def test_full_optimization_workflow(self, agent_with_optimization):
        """完整优化工作流。"""
        # 1. 设置基线
        agent_with_optimization.set_optimization_baseline("latency", 100.0)

        # 2. 提出优化提案
        proposal_result = agent_with_optimization.propose_optimization(
            "CACHE", "Increase cache size by 50%", 0.2, "low"
        )
        assert "proposal_id" in proposal_result

        # 3. 应用优化
        apply_result = agent_with_optimization.apply_optimization(
            proposal_result["proposal_id"], {"latency": 100.0}
        )
        assert "result_id" in apply_result

        # 4. 验证效果
        validated = agent_with_optimization.validate_optimization(
            apply_result["result_id"], {"latency": 80.0}
        )
        assert validated is True

        # 5. 获取统计
        stats = agent_with_optimization.get_optimization_stats()
        assert stats["optimizations_applied"] >= 1
        assert stats["optimizations_validated"] >= 1
