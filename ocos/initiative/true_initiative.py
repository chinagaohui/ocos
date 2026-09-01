"""True Initiative — 真正主动性的决策引擎

Freeze Phase 49: 基于用户记忆+当前上下文的主动性判断
区别于 ProactiveEngine 的规则驱动，这里使用记忆召回作为输入
"""

from __future__ import annotations
import random
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


@dataclass
class InitiativeRequest:
    """主动性请求 — 用于构建主动输出的内容"""

    # 触发源
    source: str  # 'memory_recall' | 'user_pattern' | 'idle_timeout' | 'context_hint'

    # 输出内容
    topic: str  # 核心话题
    content: str  # 建议的对话/行动内容

    # 优先级 (0.0-1.0)
    urgency: float = 0.5

    # 上下文
    context_summary: str = ""
    timestamp: datetime = None  # type: ignore[assignment]

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now(timezone.utc)


class TrueInitiative:
    """真正主动性的核心引擎

    区别于被动响应，这里的主动性基于：
    1. 用户记忆召回 → 发现相关话题
    2. 长时间无交互 → 主动问候
    3. 检测到模式/关注点变化 → 主动提醒

    设计原则：
    - 主动性决策必须经过权限门（permission_guard）
    - 每次主动输出都要记录到用户记忆（闭环）
    - 频率有上限（防骚扰）
    """

    def __init__(
        self,
        user_memory: Any = None,
        memory_recall: Any = None,
        permission_guard: Any = None,
        max_daily_initiatives: int = 10,
    ):
        self._user_memory = user_memory
        self._memory_recall = memory_recall
        self._permission_guard = permission_guard

        # 限制每日主动性输出次数
        self._max_daily = max_daily_initiatives
        self._initiative_count_today: int = 0
        self._last_reset_date: str = ""

    def check_and_generate(
        self, context: dict[str, Any] | None = None
    ) -> list[InitiativeRequest]:
        """检查是否需要主动性输出，返回请求列表

        Args:
            context: 当前上下文（可选）

        Returns:
            建议的主动性请求列表（可能为空）
        """
        requests: list[InitiativeRequest] = []

        # 1. 基于记忆召回的主动性
        memory_requests = self._recall_based_initiative()
        requests.extend(memory_requests)

        # 2. 基于空闲时间的主动性
        idle_requests = self._idle_based_initiative(context)
        requests.extend(idle_requests)

        # 3. 基于用户模式的主动性
        pattern_requests = self._pattern_based_initiative()
        requests.extend(pattern_requests)

        # 去重并按优先级排序
        return self._deduplicate_and_sort(requests)

    def _recall_based_initiative(self) -> list[InitiativeRequest]:
        """基于记忆召回的主动性"""
        requests: list[InitiativeRequest] = []

        if not self._memory_recall:
            return requests

        try:
            # 尝试召回相关记忆
            # 注意：这里需要传入当前上下文
            results = self._memory_recall.recall(context="current topic")

            for result in results[:3]:  # 最多3条
                if result.relevance >= 0.7:  # 高相关性才触发
                    requests.append(InitiativeRequest(
                        source="memory_recall",
                        topic=result.content[:50] if result.content else "相关话题",
                        content=result.content,
                        urgency=result.relevance,
                    ))
        except Exception:
            pass  # 非阻塞

        return requests

    def _idle_based_initiative(self, context: dict | None) -> list[InitiativeRequest]:
        """基于空闲时间的主动性"""
        requests: list[InitiativeRequest] = []

        if not context or 'idle_seconds' not in context:
            return requests

        idle_sec = context.get('idle_seconds', 0)

        # 空闲超过30分钟 → 主动问候
        if idle_sec >= 1800:  # 30分钟
            greeting = self._generate_greeting(context)
            requests.append(InitiativeRequest(
                source="idle_timeout",
                topic="问候",
                content=greeting,
                urgency=0.5,
            ))

        # 空闲超过2小时 → 询问状态
        elif idle_sec >= 7200:  # 2小时
            requests.append(InitiativeRequest(
                source="idle_timeout",
                topic="状态确认",
                content=self._generate_status_check(context),
                urgency=0.7,
            ))

        return requests

    def _pattern_based_initiative(self) -> list[InitiativeRequest]:
        """基于用户模式的主动性"""
        if not self._user_memory:
            return []

        requests: list[InitiativeRequest] = []
        try:
            # 检查是否有未完成的关注点
            recent = self._user_memory.get_recent_events(limit=5)
            for event in recent:
                if event.get('type') == 'conversation':
                    topic = event.get('topic', '')
                    # 如果上次聊到某个话题，但很久没继续
                    if topic and len(topic) > 5:
                        requests.append(InitiativeRequest(
                            source="user_pattern",
                            topic=f"继续{topic}",
                            content=f"上次我们讨论了 {topic}，要继续吗？",
                            urgency=0.4,
                        ))
        except Exception:
            pass

        return []

    def _deduplicate_and_sort(self, requests: list[InitiativeRequest]) -> list[InitiativeRequest]:
        """去重并按优先级排序"""
        # 按来源去重
        seen_sources: set[str] = set()
        unique: list[InitiativeRequest] = []
        for req in requests:
            key = f"{req.source}:{req.topic[:20]}"
            if key not in seen_sources:
                seen_sources.add(key)
                unique.append(req)

        # 按优先级排序（高优先级在前）
        return sorted(unique, key=lambda r: r.urgency, reverse=True)

    def _generate_greeting(self, context: dict) -> str:
        """生成问候语"""
        hour = datetime.now().hour
        if 6 <= hour < 12:
            return "早上好！有什么我可以帮你的吗？"
        elif 12 <= hour < 18:
            return "下午好！最近有什么进展吗？"
        else:
            return "晚上好！今天过得怎么样？"

    def _generate_status_check(self, context: dict) -> str:
        """生成长时间无交互后的状态检查"""
        return "我已经有一段时间没有收到你的指令了。一切都还好吗？有什么需要我跟进的任务吗？"

    def should_approve(self, request: InitiativeRequest) -> bool:
        """检查是否应该批准此次主动性输出

        调用权限门进行审批
        """
        if self._permission_guard is None:
            return True  # 无权限门时默认允许

        try:
            return self._permission_guard.can_initiate(request)
        except Exception:
            return False

    def record_initiative(self, request: InitiativeRequest, approved: bool) -> None:
        """记录主动性输出到用户记忆"""
        if not self._user_memory:
            return

        try:
            self._user_memory.record_event(
                'initiative',
                {
                    'source': request.source,
                    'topic': request.topic,
                    'approved': approved,
                    'content': request.content[:100],
                }
            )
        except Exception:
            pass

    def get_daily_count(self) -> int:
        """获取今日已触发的主动性次数"""
        today = datetime.now().strftime('%Y-%m-%d')
        if today != self._last_reset_date:
            self._initiative_count_today = 0
            self._last_reset_date = today
        return self._initiative_count_today

    def increment_count(self) -> None:
        """增加今日计数"""
        self._initiative_count_today += 1

    def can_initiate_today(self) -> bool:
        """检查今日是否还能发起主动性输出"""
        return self.get_daily_count() < self._max_daily
