"""Phase AD: HumanAIManager 单元测试。

覆盖维度（10 类，30 个测试）：
1. 初始化配置
2. 偏好管理
3. 反馈记录与学习
4. 对话管理
5. 通道管理
6. 回调管理
7. 意图识别
8. 统计信息
9. 边界约束
10. 端到端流程
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock

from ocos.human.manager import (
    HumanAIManager,
    UserPreference,
    FeedbackRecord,
    ConversationState,
    CollaborationMode,
    FeedbackType,
    InteractionChannel,
)


# =========================================================================
# 1. 初始化配置
# =========================================================================

class TestInitialization:
    """管理器初始化测试。"""

    def test_default_initialization(self):
        """默认初始化应创建空状态。"""
        mgr = HumanAIManager()

        assert mgr.get_all_preferences() == {}
        assert mgr.get_feedback_history() == []
        assert mgr.list_conversations() == []
        assert mgr.list_channels() == []

        stats = mgr.get_stats()
        assert stats["preference_count"] == 0
        assert stats["feedback_count"] == 0

    def test_custom_configuration(self):
        """自定义配置应正确设置。"""
        mgr = HumanAIManager(
            max_preferences=20,
            max_feedback_history=500,
            max_conversations=10,
            default_mode=CollaborationMode.COLLABORATOR,
        )

        assert mgr._max_preferences == 20
        assert mgr._max_feedback_history == 500
        assert mgr._default_mode == CollaborationMode.COLLABORATOR

    def test_context_manager(self):
        """上下文管理器应正确关闭。"""
        with HumanAIManager() as mgr:
            mgr.set_preference("test_key", "test_value")
            assert len(mgr.get_all_preferences()) == 1

        # 关闭后应为空
        assert len(mgr.get_all_preferences()) == 0


# =========================================================================
# 2. 偏好管理
# =========================================================================

class TestPreferenceManagement:
    """偏好管理测试。"""

    def test_set_preference(self):
        """设置用户偏好。"""
        mgr = HumanAIManager()

        pref = mgr.set_preference("output_style", "concise", source="explicit")

        assert pref is not None
        assert pref.key == "output_style"
        assert pref.value == "concise"
        assert pref.source == "explicit"

    def test_get_preference(self):
        """获取偏好值。"""
        mgr = HumanAIManager()
        mgr.set_preference("frequency", "daily")

        value = mgr.get_preference("frequency")
        assert value == "daily"

    def test_get_preference_not_found(self):
        """获取不存在的偏好应返回 None。"""
        mgr = HumanAIManager()
        value = mgr.get_preference("nonexistent")
        assert value is None

    def test_update_existing_preference(self):
        """更新现有偏好。"""
        mgr = HumanAIManager()
        mgr.set_preference("style", "formal")

        # 再次设置相同 key
        pref = mgr.set_preference("style", "casual")

        assert pref.value == "casual"
        assert mgr.get_preference("style") == "casual"

    def test_remove_preference(self):
        """删除偏好。"""
        mgr = HumanAIManager()
        mgr.set_preference("test_key", "test_value")

        result = mgr.remove_preference("test_key")
        assert result is True
        assert mgr.get_preference("test_key") is None

    def test_remove_nonexistent_preference(self):
        """删除不存在的偏好。"""
        mgr = HumanAIManager()
        result = mgr.remove_preference("nonexistent")
        assert result is False

    def test_max_preferences_limit(self):
        """偏好数量上限约束。"""
        mgr = HumanAIManager(max_preferences=2)

        mgr.set_preference("key1", "value1")
        mgr.set_preference("key2", "value2")

        result = mgr.set_preference("key3", "value3")
        assert result is None
        assert len(mgr.get_all_preferences()) == 2


# =========================================================================
# 3. 反馈记录与学习
# =========================================================================

class TestFeedbackManagement:
    """反馈管理测试。"""

    def test_record_feedback(self):
        """记录用户反馈。"""
        mgr = HumanAIManager()

        feedback = mgr.record_feedback(
            FeedbackType.POSITIVE,
            "这个输出很好",
            context={"task": "writing"},
        )

        assert feedback.type == FeedbackType.POSITIVE
        assert feedback.content == "这个输出很好"
        assert feedback.context["task"] == "writing"

    def test_get_feedback_history(self):
        """获取反馈历史。"""
        mgr = HumanAIManager()

        mgr.record_feedback(FeedbackType.POSITIVE, "好")
        mgr.record_feedback(FeedbackType.NEGATIVE, "不好")
        mgr.record_feedback(FeedbackType.CORRECTION, "更正")

        history = mgr.get_feedback_history()
        assert len(history) == 3

    def test_filter_feedback_by_type(self):
        """按类型过滤反馈。"""
        mgr = HumanAIManager()

        mgr.record_feedback(FeedbackType.POSITIVE, "好")
        mgr.record_feedback(FeedbackType.NEGATIVE, "不好")
        mgr.record_feedback(FeedbackType.POSITIVE, "很好")

        positive = mgr.get_feedback_history(feedback_type=FeedbackType.POSITIVE)
        assert len(positive) == 2
        assert all(f.type == FeedbackType.POSITIVE for f in positive)

    def test_limit_feedback_history(self):
        """反馈历史长度限制。"""
        mgr = HumanAIManager(max_feedback_history=5)

        for i in range(10):
            mgr.record_feedback(FeedbackType.POSITIVE, f"feedback_{i}")

        history = mgr.get_feedback_history()
        assert len(history) <= 5

    def test_learn_from_positive_feedback(self):
        """从正面反馈学习。"""
        mgr = HumanAIManager()

        feedback = mgr.record_feedback(FeedbackType.POSITIVE, "风格很好")
        result = mgr.learn_from_feedback(feedback)

        assert result["learned"] is True
        assert "reinforcement" in result["adjustments"]

    def test_learn_from_preference_feedback(self):
        """从偏好反馈学习。"""
        mgr = HumanAIManager()

        import json
        pref_data = json.dumps({"key": "output_style", "value": "detailed"})
        feedback = mgr.record_feedback(
            FeedbackType.PREFERENCE,
            pref_data,
        )
        result = mgr.learn_from_feedback(feedback)

        assert result["learned"] is True
        assert mgr.get_preference("output_style") == "detailed"


# =========================================================================
# 4. 对话管理
# =========================================================================

class TestConversationManagement:
    """对话管理测试。"""

    def test_start_conversation(self):
        """开始对话。"""
        mgr = HumanAIManager()

        conv = mgr.start_conversation(mode=CollaborationMode.ASSISTANT)

        assert conv is not None
        assert conv.mode == CollaborationMode.ASSISTANT
        assert conv.status == "active"

    def test_end_conversation(self):
        """结束对话。"""
        mgr = HumanAIManager()
        conv = mgr.start_conversation()

        result = mgr.end_conversation(conv.conversation_id)
        assert result is True
        assert conv.status == "ended"

    def test_add_message(self):
        """添加消息。"""
        mgr = HumanAIManager()
        conv = mgr.start_conversation()

        message = mgr.add_message(conv.conversation_id, "user", "你好")

        assert message is not None
        assert message["sender"] == "user"
        assert message["content"] == "你好"
        assert len(conv.messages) == 1

    def test_add_message_to_inactive_conversation(self):
        """向非活跃对话添加消息。"""
        mgr = HumanAIManager()
        conv = mgr.start_conversation()
        mgr.end_conversation(conv.conversation_id)

        message = mgr.add_message(conv.conversation_id, "user", "你好")
        assert message is None

    def test_max_conversations_limit(self):
        """对话数量上限约束。"""
        mgr = HumanAIManager(max_conversations=2)

        mgr.start_conversation()
        mgr.start_conversation()

        result = mgr.start_conversation()
        assert result is None
        assert len(mgr.list_conversations()) == 2


# =========================================================================
# 5. 通道管理
# =========================================================================

class TestChannelManagement:
    """通道管理测试。"""

    def test_register_channel(self):
        """注册交互通道。"""
        mgr = HumanAIManager()

        def handler(recipient, content, priority):
            pass

        result = mgr.register_channel("test-channel", InteractionChannel.CLI, handler)
        assert result is True
        assert "test-channel" in mgr.list_channels()

    def test_unregister_channel(self):
        """注销交互通道。"""
        mgr = HumanAIManager()
        mgr.register_channel("test", InteractionChannel.CLI, lambda r, c, p: None)

        result = mgr.unregister_channel("test")
        assert result is True
        assert "test" not in mgr.list_channels()

    def test_send_message(self):
        """发送消息。"""
        mgr = HumanAIManager()
        sent_messages = []

        def handler(recipient, content, priority):
            sent_messages.append((recipient, content, priority))

        mgr.register_channel("test", InteractionChannel.CALLBACK, handler)
        result = mgr.send_message("test", "user1", "hello")

        assert result is True
        assert len(sent_messages) == 1
        assert sent_messages[0] == ("user1", "hello", "normal")

    def test_send_to_unknown_channel(self):
        """发送到未知通道。"""
        mgr = HumanAIManager()
        result = mgr.send_message("unknown", "user", "hello")
        assert result is False


# =========================================================================
# 6. 回调管理
# =========================================================================

class TestCallbackManagement:
    """回调管理测试。"""

    def test_register_callback(self):
        """注册事件回调。"""
        mgr = HumanAIManager()

        def callback(data):
            return "handled"

        cb_id = mgr.register_callback("user_input", callback)
        assert cb_id.startswith("cb:")

    def test_trigger_event(self):
        """触发事件。"""
        mgr = HumanAIManager()
        results = []

        def callback(data):
            results.append(data)
            return "ok"

        mgr.register_callback("test_event", callback)
        triggered = mgr.trigger_event("test_event", {"key": "value"})

        assert len(triggered) == 1
        assert triggered[0] == "ok"
        assert len(results) == 1

    def test_unregister_callback(self):
        """注销回调。"""
        mgr = HumanAIManager()

        def callback(data):
            pass

        cb_id = mgr.register_callback("event", callback)
        result = mgr.unregister_callback(cb_id)
        assert result is True


# =========================================================================
# 7. 意图识别
# =========================================================================

class TestIntentInference:
    """意图识别测试。"""

    def test_question_intent(self):
        """识别提问意图。"""
        mgr = HumanAIManager()
        result = mgr.infer_intent("如何设置偏好？")

        assert "question" in result["categories"]
        assert result["suggested_action"] == "provide_help"
        assert result["confidence"] > 0

    def test_positive_feedback_intent(self):
        """识别正面反馈意图。"""
        mgr = HumanAIManager()
        result = mgr.infer_intent("这个很好用，谢谢！")

        assert "positive_feedback" in result["categories"]
        assert result["suggested_action"] == "acknowledge"

    def test_negative_feedback_intent(self):
        """识别负面反馈意图。"""
        mgr = HumanAIManager()
        result = mgr.infer_intent("这个不对，应该是另一种方式")

        assert "negative_feedback" in result["categories"]
        assert result["suggested_action"] == "correct"

    def test_preference_intent(self):
        """识别偏好表达意图。"""
        mgr = HumanAIManager()
        result = mgr.infer_intent("我喜欢简洁的输出风格")

        assert "preference" in result["categories"]
        assert result["suggested_action"] == "query_preference"

    def test_unknown_intent(self):
        """无法识别的意图。"""
        mgr = HumanAIManager()
        result = mgr.infer_intent(" random text without keywords ")

        assert result["confidence"] == 0.0
        assert result["categories"] == []


# =========================================================================
# 8. 统计信息
# =========================================================================

class TestStatistics:
    """统计信息测试。"""

    def test_get_stats(self):
        """获取统计信息。"""
        mgr = HumanAIManager()

        stats = mgr.get_stats()

        assert "feedback_received" in stats
        assert "preferences_learned" in stats
        assert "conversations_started" in stats
        assert "messages_exchanged" in stats

    def test_stats_after_operations(self):
        """操作后的统计。"""
        mgr = HumanAIManager()

        mgr.set_preference("key", "value")
        mgr.record_feedback(FeedbackType.POSITIVE, "good")
        conv = mgr.start_conversation()
        mgr.add_message(conv.conversation_id, "user", "hi")

        stats = mgr.get_stats()

        assert stats["preferences_learned"] >= 1
        assert stats["feedback_received"] >= 1
        assert stats["conversations_started"] >= 1
        assert stats["messages_exchanged"] >= 1

    def test_reset_stats(self):
        """重置统计。"""
        mgr = HumanAIManager()
        mgr.set_preference("key", "value")
        mgr.reset_stats()

        stats = mgr.get_stats()
        assert stats["feedback_received"] == 0
        assert stats["preferences_learned"] == 0


# =========================================================================
# 9. 边界约束
# =========================================================================

class TestBoundaryConstraints:
    """边界约束测试。"""

    def test_max_preferences_limit(self):
        """偏好数量上限约束。"""
        mgr = HumanAIManager(max_preferences=3)

        for i in range(3):
            mgr.set_preference(f"key{i}", f"value{i}")

        result = mgr.set_preference("key3", "value3")
        assert result is None

    def test_max_feedback_history_limit(self):
        """反馈历史长度上限约束。"""
        mgr = HumanAIManager(max_feedback_history=5)

        for i in range(10):
            mgr.record_feedback(FeedbackType.POSITIVE, f"fb_{i}")

        history = mgr.get_feedback_history()
        assert len(history) <= 5

    def test_max_conversations_limit(self):
        """对话数量上限约束。"""
        mgr = HumanAIManager(max_conversations=2)

        mgr.start_conversation()
        mgr.start_conversation()

        result = mgr.start_conversation()
        assert result is None


# =========================================================================
# 10. 端到端流程
# =========================================================================

class TestEndToEnd:
    """端到端完整流程测试。"""

    def test_full_collaboration_workflow(self):
        """完整人机协同工作流。"""
        mgr = HumanAIManager()

        # 1. 开始对话
        conv = mgr.start_conversation(mode=CollaborationMode.COLLABORATOR)
        assert conv is not None

        # 2. 用户发送消息
        msg1 = mgr.add_message(conv.conversation_id, "user", "帮我写一段代码")
        assert msg1 is not None

        # 3. AI 回复
        msg2 = mgr.add_message(conv.conversation_id, "ai", "好的，我来帮你...")
        assert msg2 is not None

        # 4. 用户给出反馈
        feedback = mgr.record_feedback(
            FeedbackType.POSITIVE,
            "这个代码风格很好",
            context={"conversation_id": conv.conversation_id},
        )

        # 5. 从反馈学习
        result = mgr.learn_from_feedback(feedback)
        assert result["learned"] is True

        # 6. 设置偏好
        mgr.set_preference("preferred_style", "clean_code", source="inferred")

        # 7. 验证偏好
        assert mgr.get_preference("preferred_style") == "clean_code"

        # 8. 结束对话
        mgr.end_conversation(conv.conversation_id)
        assert conv.status == "ended"

        # 9. 获取统计
        stats = mgr.get_stats()
        assert stats["messages_exchanged"] == 2
        assert stats["feedback_received"] == 1


# =========================================================================
# 错误处理
# =========================================================================

class TestErrorHandling:
    """错误处理测试。"""

    def test_end_nonexistent_conversation(self):
        """结束不存在的对话。"""
        mgr = HumanAIManager()
        result = mgr.end_conversation("conv:nonexistent")
        assert result is False

    def test_add_message_to_nonexistent_conversation(self):
        """向不存在的对话添加消息。"""
        mgr = HumanAIManager()
        result = mgr.add_message("conv:nonexistent", "user", "hello")
        assert result is None

    def test_send_to_nonexistent_channel(self):
        """发送到不存在的通道。"""
        mgr = HumanAIManager()
        result = mgr.send_message("unknown", "user", "hello")
        assert result is False
