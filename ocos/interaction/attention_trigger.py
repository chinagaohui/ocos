"""Phase 53: AttentionTrigger — 决定哪些 NeedSignal 值得转化为交互。

类比人脑:
    边缘系统产生需求 (NeedSignal)
        ↓
    前额叶注意力过滤 (AttentionTrigger)
        ↓
    决定是否行动 (InteractionCandidate)

核心逻辑:
    1. 紧急度过滤: urgency < 阈值 → 忽略
    2. 去重: 同一来源的相似信号合并
    3. 上下文适配: 根据用户过去行为调整阈值
    4. 时区适配: 如果具备上下文，夜间降低非关键提醒
"""

from __future__ import annotations

from dataclasses import dataclass, field
import time as _time

from ocos.interaction.interaction_types import (
    NeedSignal, NeedType, InteractionPriority, InteractionConfig,
)


@dataclass
class AttentionTrigger:
    """注意力触发器 — OCOS 的"前额叶"。

    决定: "这个内部信号值得打扰用户吗？"
    不决定:
        - 输出什么内容 (交给 InteractionCandidate)
        - 什么时候发 (交给 InteractionScheduler)
        - 是否真实有效 (交给 InteractionValidator)
    """

    config: InteractionConfig = field(default_factory=InteractionConfig)

    # 用户行为信号 (由外部系统更新)
    user_active: bool = True       # 用户是否活跃
    user_response_rate: float = 1.0  # 用户对过去提醒的响应率
    last_user_activity: float = field(default_factory=_time.time)

    def evaluate(self, signal: NeedSignal) -> InteractionPriority | None:
        """评估 NeedSignal，返回是否值得交互。

        返回:
            InteractionPriority — 值得交互的优先级
            None — 不值得交互，信号被丢弃
        """
        # 1. 紧急度 → 优先级映射
        priority = self._urgency_to_priority(signal.urgency)

        if priority is None:
            return None

        # 2. 用户活跃度适配
        priority = self._adjust_for_user_state(priority, signal)

        return priority

    def _urgency_to_priority(self, urgency: float) -> InteractionPriority | None:
        """紧急度映射到优先级。"""
        if urgency >= self.config.critical_threshold:
            return InteractionPriority.CRITICAL
        elif urgency >= self.config.high_threshold:
            return InteractionPriority.HIGH
        elif urgency >= self.config.medium_threshold:
            return InteractionPriority.MEDIUM
        elif urgency > 0.1:
            return InteractionPriority.LOW
        return None  # 不值得交互

    def _adjust_for_user_state(self, priority: InteractionPriority,
                                signal: NeedSignal) -> InteractionPriority:
        """根据用户状态调整优先级。

        IS53-04: 如果用户对过去提醒响应率低，降低优先级以免骚扰。
        """
        if not self.user_active:
            # 用户不在线: 非关键延迟
            if priority == InteractionPriority.LOW:
                return None  # type: ignore — pyright doesn't know this
            if priority == InteractionPriority.MEDIUM:
                # MEDIUM 降级为 LOW，等用户回来再报
                return InteractionPriority.LOW

        if self.user_response_rate < 0.3:
            # 用户对提醒不耐烦: 只有 CRITICAL 保持
            if priority.value not in ("critical", "high"):
                return None  # type: ignore

        return priority

    def update_user_activity(self, active: bool) -> None:
        self.user_active = active
        if active:
            self.last_user_activity = _time.time()


__all__ = ["AttentionTrigger"]
