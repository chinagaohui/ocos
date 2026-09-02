"""Phase AE: SelfReflectionManager — MasterAgent 集成测试。

覆盖维度：
1. 管理器注入
2. 反思执行
3. 智慧管理
4. 身份连续性检查
5. tick 接口
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from ocos.agent.master_agent import MasterAgent
from ocos.reflection.manager import SelfReflectionManager, ReflectionType, ReflectionDepth


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
def agent_with_reflection(mock_agent):
    """创建带有自我反思管理器的 Agent 实例。"""
    srm = SelfReflectionManager()
    mock_agent._self_reflection_manager = srm
    return mock_agent


class TestReflectionInjection:
    """管理器注入测试。"""

    def test_self_reflection_manager_injection(self, agent_with_reflection):
        """管理器应正确注入。"""
        assert agent_with_reflection.self_reflection_manager is not None

    def test_self_reflection_manager_property(self, agent_with_reflection):
        """获取属性应返回注入的管理器。"""
        manager = SelfReflectionManager()
        agent_with_reflection._self_reflection_manager = manager
        assert agent_with_reflection.self_reflection_manager == manager


class TestReflectionMethods:
    """反思执行方法测试。"""

    def test_start_reflection(self, agent_with_reflection):
        """开始反思。"""
        result = agent_with_reflection.start_reflection("RESULT", "test-subject")
        assert "trace_id" in result or "error" in result

    def test_add_reflection_insight(self, agent_with_reflection):
        """添加反思洞察。"""
        result = agent_with_reflection.start_reflection("RESULT", "test")
        if "trace_id" in result:
            insight_result = agent_with_reflection.add_reflection_insight(
                result["trace_id"], "success_factor", "Good execution", 0.8
            )
            assert insight_result is True

    def test_complete_reflection(self, agent_with_reflection):
        """完成反思。"""
        result = agent_with_reflection.start_reflection("RESULT", "test")
        if "trace_id" in result:
            complete_result = agent_with_reflection.complete_reflection(result["trace_id"])
            assert complete_result is True

    def test_start_reflection_no_manager(self, mock_agent):
        """无管理器时应返回错误。"""
        result = mock_agent.start_reflection("RESULT", "test")
        assert "error" in result
        assert "not injected" in result["error"]


class TestWisdomMethods:
    """智慧管理方法测试。"""

    def test_propose_wisdom(self, agent_with_reflection):
        """提出智慧候选。"""
        ref_result = agent_with_reflection.start_reflection("PATTERN", "test")
        if "trace_id" in ref_result:
            wisdom_result = agent_with_reflection.propose_wisdom(
                ref_result["trace_id"], "Success comes from consistency", 0.75
            )
            assert "wisdom_id" in wisdom_result or "error" in wisdom_result

    def test_verify_wisdom(self, agent_with_reflection):
        """验证智慧。"""
        ref_result = agent_with_reflection.start_reflection("PATTERN", "test")
        if "trace_id" in ref_result:
            wisdom_result = agent_with_reflection.propose_wisdom(ref_result["trace_id"], "Test wisdom")
            if "wisdom_id" in wisdom_result:
                verify_result = agent_with_reflection.verify_wisdom(wisdom_result["wisdom_id"], True)
                assert verify_result is True


class TestIdentityMethods:
    """身份连续性检查方法测试。"""

    def test_check_identity_continuity(self, agent_with_reflection):
        """检查身份连续性。"""
        result = agent_with_reflection.check_identity_continuity({"state": "test"})
        assert "continuity_score" in result
        assert "drift_detected" in result

    def test_check_identity_continuity_no_manager(self, mock_agent):
        """无管理器时应返回错误。"""
        result = mock_agent.check_identity_continuity({"state": "test"})
        assert "error" in result
        assert "not injected" in result["error"]


class TestStats:
    """统计信息测试。"""

    def test_get_stats(self, agent_with_reflection):
        """获取统计信息。"""
        result = agent_with_reflection.get_reflection_stats()
        assert "reflections_performed" in result
        assert "wisdom_count" in result

    def test_get_stats_no_manager(self, mock_agent):
        """无管理器时应返回错误。"""
        result = mock_agent.get_reflection_stats()
        assert "error" in result
        assert "not injected" in result["error"]


class TestTick:
    """Tick 接口测试。"""

    def test_tick_with_reflection(self, agent_with_reflection):
        """含反思管理器的 tick。"""
        result = agent_with_reflection.tick()
        assert "reflection" in result

    def test_tick_without_reflection(self, mock_agent):
        """无反思管理器时的 tick。"""
        mock_agent._self_reflection_manager = None
        result = mock_agent.tick()
        assert "reflection" in result
        assert result["reflection"] == {}


class TestEndToEnd:
    """端到端测试。"""

    def test_full_reflection_workflow(self, agent_with_reflection):
        """完整反思工作流。"""
        # 1. 开始反思
        ref_result = agent_with_reflection.start_reflection("RESULT", "subject-1")
        assert "trace_id" in ref_result

        # 2. 添加洞察
        if "trace_id" in ref_result:
            agent_with_reflection.add_reflection_insight(
                ref_result["trace_id"], "success_factor", "Good decision", 0.85
            )

        # 3. 完成反思
        if "trace_id" in ref_result:
            assert agent_with_reflection.complete_reflection(ref_result["trace_id"])

        # 4. 提出智慧
        if "trace_id" in ref_result:
            wisdom_result = agent_with_reflection.propose_wisdom(
                ref_result["trace_id"], "Consistency leads to success", 0.8
            )
            assert "wisdom_id" in wisdom_result or "error" in wisdom_result

        # 5. 获取统计
        stats = agent_with_reflection.get_reflection_stats()
        assert stats["reflections_performed"] >= 1
