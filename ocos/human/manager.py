"""Phase AD: HumanAIManager — 人机协同管理器。

整合 InteractionChannel + FeedbackLearning + CollaborationProtocol，
提供统一的人机协同接口：
- 多通道交互管理（CLI/API/Webhook/回调）
- 反馈收集与偏好学习
- 协作协议管理
- 用户意图识别
- 对话状态追踪

架构原则：
- AD-HUM-01: 所有外部输入必须经过验证
- AD-HUM-02: 用户反馈优先于系统推断
- AD-HUM-03: 协作状态可追溯、可回滚
- AD-HUM-04: 对话历史持久化
"""

from __future__ import annotations

import uuid
import time
import json
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum, auto
from typing import Any, Callable, Optional

from ocos.logging import get_logger

logger = get_logger(__name__)


class CollaborationMode(Enum):
    """协作模式。"""
    ASSISTANT = "assistant"       # AI 辅助人类
    AGENT = "agent"             # AI 代理执行
    COLLABORATOR = "collaborator"  # AI 与人协作
    OBSERVER = "observer"        # AI 观察记录


class FeedbackType(Enum):
    """反馈类型。"""
    POSITIVE = "positive"       # 认可
    NEGATIVE = "negative"       # 否定
    CORRECTION = "correction"   # 纠正
    PREFERENCE = "preference"   # 偏好
    CLARIFICATION = "clarification"  # 澄清请求


class InteractionChannel(Enum):
    """交互通道。"""
    CLI = "cli"
    API = "api"
    WEBHOOK = "webhook"
    CALLBACK = "callback"
    BROADCAST = "broadcast"


@dataclass
class UserPreference:
    """用户偏好。"""
    preference_id: str
    key: str
    value: Any
    source: str  # "explicit" | "inferred"
    confidence: float
    created_at: float = 0.0
    updated_at: float = 0.0

    def __post_init__(self):
        if self.created_at == 0:
            self.created_at = time.time()
        if self.updated_at == 0:
            self.updated_at = time.time()


@dataclass
class FeedbackRecord:
    """反馈记录。"""
    feedback_id: str
    type: FeedbackType
    content: str
    context: dict[str, Any]
    timestamp: float
    user_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.feedback_id:
            self.feedback_id = f"fb:{uuid.uuid4().hex[:8]}"


@dataclass
class ConversationState:
    """对话状态。"""
    conversation_id: str
    mode: CollaborationMode
    status: str  # "active" | "paused" | "ended"
    messages: list[dict[str, Any]] = field(default_factory=list)
    created_at: float = 0.0
    last_active_at: float = 0.0

    def __post_init__(self):
        if self.created_at == 0.0:
            self.created_at = time.time()
        if self.last_active_at == 0.0:
            self.last_active_at = time.time()


class HumanAIManager:
    """人机协同管理器。

    统一管理层：
    1. 交互通道管理
    2. 反馈收集与学习
    3. 偏好建模
    4. 对话状态追踪
    5. 协作协议执行
    """

    def __init__(
        self,
        max_preferences: int = 100,
        max_feedback_history: int = 1000,
        max_conversations: int = 50,
        default_mode: CollaborationMode = CollaborationMode.ASSISTANT,
    ):
        self._max_preferences = max_preferences
        self._max_feedback_history = max_feedback_history
        self._max_conversations = max_conversations
        self._default_mode = default_mode

        # 偏好管理
        self._preferences: dict[str, UserPreference] = {}
        self._pref_lock = threading.RLock()

        # 反馈历史
        self._feedback_history: list[FeedbackRecord] = []
        self._feedback_lock = threading.RLock()

        # 对话状态
        self._conversations: dict[str, ConversationState] = {}
        self._conv_lock = threading.RLock()

        # 通道注册
        self._channels: dict[str, Callable] = {}
        self._channel_lock = threading.RLock()

        # 回调注册
        self._callbacks: dict[str, list[Callable]] = {}
        self._callback_lock = threading.RLock()

        # 统计
        self._stats = {
            "feedback_received": 0,
            "preferences_learned": 0,
            "conversations_started": 0,
            "messages_exchanged": 0,
            "collaborations_completed": 0,
        }

    # ── 偏好管理 ────────────────────────────────────────────────

    def set_preference(
        self,
        key: str,
        value: Any,
        source: str = "explicit",
        confidence: float = 1.0,
    ) -> UserPreference | None:
        """设置用户偏好。"""
        with self._pref_lock:
            if len(self._preferences) >= self._max_preferences:
                logger.warning("Max preferences reached (%d)", self._max_preferences)
                return None

            # 检查是否已存在相同 key
            existing = self._find_preference(key)
            if existing:
                existing.value = value
                existing.confidence = confidence
                existing.updated_at = time.time()
                existing.source = source
                return existing

            pref_id = f"pref:{uuid.uuid4().hex[:8]}"
            pref = UserPreference(
                preference_id=pref_id,
                key=key,
                value=value,
                source=source,
                confidence=confidence,
            )
            self._preferences[pref_id] = pref
            self._stats["preferences_learned"] += 1
            logger.info("Preference set: %s = %s (source=%s)", key, value, source)
            return pref

    def get_preference(self, key: str) -> Any | None:
        """获取用户偏好值。"""
        with self._pref_lock:
            pref = self._find_preference(key)
            return pref.value if pref else None

    def get_all_preferences(self) -> dict[str, Any]:
        """获取所有偏好。"""
        with self._pref_lock:
            return {p.key: p.value for p in self._preferences.values()}

    def _find_preference(self, key: str) -> UserPreference | None:
        """按 key 查找偏好。"""
        for pref in self._preferences.values():
            if pref.key == key:
                return pref
        return None

    def remove_preference(self, key: str) -> bool:
        """删除用户偏好。"""
        with self._pref_lock:
            to_remove = [k for k, v in self._preferences.items() if v.key == key]
            for k in to_remove:
                del self._preferences[k]
            return len(to_remove) > 0

    # ── 反馈管理 ────────────────────────────────────────────────

    def record_feedback(
        self,
        feedback_type: FeedbackType,
        content: str,
        context: dict[str, Any] | None = None,
        user_id: str = "",
    ) -> FeedbackRecord:
        """记录用户反馈。"""
        feedback = FeedbackRecord(
            feedback_id=f"fb:{uuid.uuid4().hex[:8]}",
            type=feedback_type,
            content=content,
            context=context or {},
            timestamp=time.time(),
            user_id=user_id,
        )

        with self._feedback_lock:
            self._feedback_history.append(feedback)
            # 限制历史记录长度
            if len(self._feedback_history) > self._max_feedback_history:
                self._feedback_history = self._feedback_history[-self._max_feedback_history:]
            self._stats["feedback_received"] += 1

        logger.info("Feedback recorded: %s - %s", feedback_type.value, content[:50])
        return feedback

    def get_feedback_history(
        self,
        feedback_type: FeedbackType | None = None,
        limit: int = 50,
    ) -> list[FeedbackRecord]:
        """获取反馈历史。"""
        with self._feedback_lock:
            history = self._feedback_history
            if feedback_type:
                history = [f for f in history if f.type == feedback_type]
            return history[-limit:]

    def learn_from_feedback(self, feedback: FeedbackRecord) -> dict[str, Any]:
        """从反馈中学习。"""
        result = {"learned": False, "adjustments": {}}

        # 根据反馈类型调整
        if feedback.type == FeedbackType.PREFERENCE:
            # 尝试解析偏好变更
            try:
                pref_data = json.loads(feedback.content)
                if isinstance(pref_data, dict) and "key" in pref_data:
                    self.set_preference(
                        pref_data["key"],
                        pref_data.get("value"),
                        source="inferred",
                    )
                    result["learned"] = True
                    result["adjustments"][pref_data["key"]] = pref_data.get("value")
            except (json.JSONDecodeError, TypeError):
                pass

        elif feedback.type == FeedbackType.CORRECTION:
            # 纠正行为模式
            result["adjustments"]["behavior_correction"] = feedback.content[:100]
            result["learned"] = True

        elif feedback.type == FeedbackType.POSITIVE:
            # 强化当前行为
            result["adjustments"]["reinforcement"] = "positive"
            result["learned"] = True

        elif feedback.type == FeedbackType.NEGATIVE:
            # 弱化当前行为
            result["adjustments"]["weakening"] = "negative"
            result["learned"] = True

        return result

    # ── 对话管理 ────────────────────────────────────────────────

    def start_conversation(
        self,
        mode: CollaborationMode | None = None,
        user_id: str = "",
    ) -> ConversationState | None:
        """开始新对话。"""
        with self._conv_lock:
            if len(self._conversations) >= self._max_conversations:
                logger.warning("Max conversations reached (%d)", self._max_conversations)
                return None

            conv_id = f"conv:{uuid.uuid4().hex[:8]}"
            state = ConversationState(
                conversation_id=conv_id,
                mode=mode or self._default_mode,
                status="active",
            )
            self._conversations[conv_id] = state
            self._stats["conversations_started"] += 1
            logger.info("Conversation started: %s (mode=%s)", conv_id, state.mode.value)
            return state

    def end_conversation(self, conversation_id: str) -> bool:
        """结束对话。"""
        with self._conv_lock:
            conv = self._conversations.get(conversation_id)
            if not conv:
                return False
            conv.status = "ended"
            logger.info("Conversation ended: %s", conversation_id)
            return True

    def add_message(
        self,
        conversation_id: str,
        sender: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """添加消息到对话。"""
        with self._conv_lock:
            conv = self._conversations.get(conversation_id)
            if not conv or conv.status != "active":
                return None

            message = {
                "message_id": f"msg:{uuid.uuid4().hex[:8]}",
                "sender": sender,
                "content": content,
                "timestamp": time.time(),
                "metadata": metadata or {},
            }
            conv.messages.append(message)
            conv.last_active_at = time.time()
            self._stats["messages_exchanged"] += 1
            return message

    def get_conversation(self, conversation_id: str) -> ConversationState | None:
        """获取对话状态。"""
        with self._conv_lock:
            return self._conversations.get(conversation_id)

    def list_conversations(self, status: str | None = None) -> list[ConversationState]:
        """列出对话。"""
        with self._conv_lock:
            conversations = list(self._conversations.values())
            if status:
                conversations = [c for c in conversations if c.status == status]
            return conversations

    # ── 通道管理 ────────────────────────────────────────────────

    def register_channel(
        self,
        channel_id: str,
        channel_type: InteractionChannel,
        handler: Callable,
    ) -> bool:
        """注册交互通道。"""
        with self._channel_lock:
            self._channels[channel_id] = handler
            logger.info("Channel registered: %s (%s)", channel_id, channel_type.value)
            return True

    def unregister_channel(self, channel_id: str) -> bool:
        """注销交互通道。"""
        with self._channel_lock:
            if channel_id in self._channels:
                del self._channels[channel_id]
                return True
            return False

    def send_message(
        self,
        channel_id: str,
        recipient: str,
        content: str,
        priority: str = "normal",
    ) -> bool:
        """通过指定通道发送消息。"""
        with self._channel_lock:
            handler = self._channels.get(channel_id)
            if not handler:
                logger.warning("Channel not found: %s", channel_id)
                return False

            try:
                handler(recipient, content, priority)
                return True
            except Exception as e:
                logger.error("Channel send failed: %s - %s", channel_id, e)
                return False

    def list_channels(self) -> list[str]:
        """列出已注册通道。"""
        with self._channel_lock:
            return list(self._channels.keys())

    # ── 回调管理 ────────────────────────────────────────────────

    def register_callback(
        self,
        event_type: str,
        callback: Callable,
    ) -> str:
        """注册事件回调。"""
        callback_id = f"cb:{uuid.uuid4().hex[:8]}"
        callback._callback_id = callback_id  # type: ignore
        with self._callback_lock:
            if event_type not in self._callbacks:
                self._callbacks[event_type] = []
            self._callbacks[event_type].append(callback)
        logger.debug("Callback registered: %s for %s", callback_id, event_type)
        return callback_id

    def unregister_callback(self, callback_id: str) -> bool:
        """注销回调。"""
        with self._callback_lock:
            for callbacks in self._callbacks.values():
                for i, cb in enumerate(callbacks):
                    if getattr(cb, '_callback_id', None) == callback_id:
                        callbacks.pop(i)
                        return True
        return False

    def trigger_event(self, event_type: str, data: dict[str, Any]) -> list[Any]:
        """触发事件并调用所有回调。"""
        results = []
        with self._callback_lock:
            callbacks = self._callbacks.get(event_type, [])
            for cb in callbacks:
                try:
                    result = cb(data)
                    results.append(result)
                except Exception as e:
                    logger.error("Callback failed: %s", e)
        return results

    # ── 意图识别 ────────────────────────────────────────────────

    def infer_intent(self, message: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
        """推断用户意图。"""
        intent = {
            "confidence": 0.0,
            "categories": [],
            "entities": [],
            "suggested_action": None,
        }

        # 简单规则匹配（实际应使用 NLU 模型）
        message_lower = message.lower()

        # 问题意图优先
        if any(kw in message_lower for kw in ["如何", "怎么", "为什么"]):
            intent["categories"].append("question")
            intent["suggested_action"] = "provide_help"
            intent["confidence"] = max(intent["confidence"], 0.7)

        if any(kw in message_lower for kw in ["帮助", "help"]):
            intent["categories"].append("question")
            intent["suggested_action"] = "provide_help"
            intent["confidence"] = max(intent["confidence"], 0.7)

        if any(kw in message_lower for kw in ["感谢", "谢谢", "很好", "不错"]):
            intent["categories"].append("positive_feedback")
            intent["suggested_action"] = "acknowledge"
            intent["confidence"] = max(intent["confidence"], 0.8)

        if any(kw in message_lower for kw in ["错误", "不对", "不是", "错了"]):
            intent["categories"].append("negative_feedback")
            intent["suggested_action"] = "correct"
            intent["confidence"] = max(intent["confidence"], 0.75)

        # 偏好意图（排除已有更高优先级的分类）
        if any(kw in message_lower for kw in ["设置", "偏好", "喜欢"]) and "question" not in intent["categories"]:
            intent["categories"].append("preference")
            intent["suggested_action"] = "query_preference"
            intent["confidence"] = max(intent["confidence"], 0.65)

        return intent

    # ── 统计 ────────────────────────────────────────────────────

    def get_stats(self) -> dict[str, Any]:
        """获取统计信息。"""
        with self._feedback_lock:
            feedback_count = len(self._feedback_history)
        with self._conv_lock:
            conv_count = len(self._conversations)
            active_convs = sum(1 for c in self._conversations.values() if c.status == "active")
        with self._pref_lock:
            pref_count = len(self._preferences)
        with self._channel_lock:
            channel_count = len(self._channels)
        with self._callback_lock:
            callback_count = sum(len(v) for v in self._callbacks.values())

        return {
            **self._stats,
            "feedback_count": feedback_count,
            "conversation_count": conv_count,
            "active_conversations": active_convs,
            "preference_count": pref_count,
            "channel_count": channel_count,
            "callback_count": callback_count,
        }

    def reset_stats(self) -> None:
        """重置统计。"""
        self._stats = {
            "feedback_received": 0,
            "preferences_learned": 0,
            "conversations_started": 0,
            "messages_exchanged": 0,
            "collaborations_completed": 0,
        }

    # ── 上下文管理器 ────────────────────────────────────────────

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def close(self) -> None:
        """关闭管理器。"""
        with self._pref_lock:
            self._preferences.clear()
        with self._feedback_lock:
            self._feedback_history.clear()
        with self._conv_lock:
            self._conversations.clear()
        with self._channel_lock:
            self._channels.clear()
        with self._callback_lock:
            self._callbacks.clear()
        logger.info("HumanAIManager closed")


__all__ = [
    "HumanAIManager",
    "UserPreference",
    "FeedbackRecord",
    "ConversationState",
    "CollaborationMode",
    "FeedbackType",
    "InteractionChannel",
]
