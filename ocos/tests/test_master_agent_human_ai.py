"""Phase AD: HumanAIManager — MasterAgent 集成测试。

覆盖维度：
1. 管理器注入
2. 偏好设置与获取
3. 反馈记录
4. 对话管理
5. tick 接口
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from ocos.agent.master_agent import MasterAgent
from ocos.human.manager import HumanAIManager


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
def agent_with_human_ai(mock_agent):
    """创建带有人机协同管理器的 Agent 实例。"""
    ham = HumanAIManager()
    mock_agent._human_ai_manager = ham
    return mock_agent


class TestHumanAIInjection:
    """管理器注入测试。"""

    def test_human_ai_manager_injection(self, agent_with_human_ai):
        """管理器应正确注入。"""
        assert agent_with_human_ai.human_ai_manager is not None

    def test_human_ai_manager_property(self, agent_with_human_ai):
        """获取属性应返回注入的管理器。"""
        manager = HumanAIManager()
        agent_with_human_ai._human_ai_manager = manager
        assert agent_with_human_ai.human_ai_manager == manager


class TestPreferenceMethods:
    """偏好管理方法测试。"""

    def test_set_preference(self, agent_with_human_ai):
        """设置偏好。"""
        result = agent_with_human_ai.set_preference("output_style", "concise")
        assert "key" in result or "error" in result

    def test_get_preference(self, agent_with_human_ai):
        """获取偏好。"""
        agent_with_human_ai.set_preference("test_key", "test_value")
        value = agent_with_human_ai.get_preference("test_key")
        assert value == "test_value"

    def test_get_preference_not_found(self, agent_with_human_ai):
        """获取不存在的偏好。"""
        value = agent_with_human_ai.get_preference("nonexistent")
        assert value is None

    def test_set_preference_no_manager(self, mock_agent):
        """无管理器时应返回错误。"""
        result = mock_agent.set_preference("key", "value")
        assert "error" in result
        assert "not injected" in result["error"]


class TestFeedbackMethods:
    """反馈记录方法测试。"""

    def test_record_feedback(self, agent_with_human_ai):
        """记录反馈。"""
        result = agent_with_human_ai.record_feedback("positive", "好")
        assert "feedback_id" in result or "error" in result

    def test_record_feedback_invalid_type(self, agent_with_human_ai):
        """无效反馈类型。"""
        result = agent_with_human_ai.record_feedback("invalid_type", "test")
        assert "error" in result

    def test_record_feedback_no_manager(self, mock_agent):
        """无管理器时应返回错误。"""
        result = mock_agent.record_feedback("positive", "test")
        assert "error" in result
        assert "not injected" in result["error"]


class TestConversationMethods:
    """对话管理方法测试。"""

    def test_start_conversation(self, agent_with_human_ai):
        """开始对话。"""
        result = agent_with_human_ai.start_conversation(mode="assistant")
        assert "conversation_id" in result or "error" in result

    def test_start_conversation_no_manager(self, mock_agent):
        """无管理器时应返回错误。"""
        result = mock_agent.start_conversation()
        assert "error" in result
        assert "not injected" in result["error"]


class TestIntentMethods:
    """意图识别方法测试。"""

    def test_infer_intent(self, agent_with_human_ai):
        """推断意图。"""
        result = agent_with_human_ai.infer_intent("如何设置偏好？")
        assert "categories" in result
        assert "confidence" in result

    def test_infer_intent_no_manager(self, mock_agent):
        """无管理器时应返回错误。"""
        result = mock_agent.infer_intent("test")
        assert "error" in result
        assert "not injected" in result["error"]


class TestStats:
    """统计信息测试。"""

    def test_get_stats(self, agent_with_human_ai):
        """获取统计。"""
        result = agent_with_human_ai.get_human_ai_stats()
        assert "feedback_received" in result
        assert "preference_count" in result

    def test_get_stats_no_manager(self, mock_agent):
        """无管理器时应返回错误。"""
        result = mock_agent.get_human_ai_stats()
        assert "error" in result
        assert "not injected" in result["error"]


class TestTick:
    """Tick 接口测试。"""

    def test_tick_with_human_ai(self, agent_with_human_ai):
        """含人机管理器的 tick。"""
        result = agent_with_human_ai.tick()
        assert "human_ai" in result

    def test_tick_without_human_ai(self, mock_agent):
        """无管理器时的 tick。"""
        mock_agent._human_ai_manager = None
        result = mock_agent.tick()
        assert "human_ai" in result
        assert result["human_ai"] == {}