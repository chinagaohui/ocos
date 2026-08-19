"""Phase 53: Active Interaction System — Types.

OCOS 的主动交流层。

核心原则:
    IS53-01: Active Reminder ≠ Active Decision — 提醒不等于替用户决策
    IS53-02: Active Output ≠ Autonomous Goal — 输出不等于自创目标
    IS53-03: Validation Before Send — 每条交互必须验证
    IS53-04: Rate Limit — 防止骚扰

交互模型:
    内部状态变化 → NeedMonitor → Attention → InteractionCandidate → 验证 → 用户
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class InteractionPriority(str, Enum):
    """交互优先级。类似 human:
        CRITICAL: 房子着火了 → 必须马上说
        HIGH: 有异常 → 应该提醒
        MEDIUM: 观察到变化 → 可以提
        LOW: 周期性报告 → 顺便聊
    """
    CRITICAL = "critical"  # 系统异常、安全风险
    HIGH = "high"          # 目标停滞、重要变化
    MEDIUM = "medium"      # 观察报告、进度更新
    LOW = "low"            # 周期性汇报、可选更新


class InteractionStatus(str, Enum):
    """交互生命周期。"""
    DRAFT = "draft"            # 刚生成，未提交
    PENDING = "pending"        # 等待发送
    SENT = "sent"              # 已发给用户
    ACKNOWLEDGED = "acknowledged"  # 用户已读/已回
    IGNORED = "ignored"        # 超时未回应
    WITHDRAWN = "withdrawn"    # 条件消失，主动撤回


class InteractionMode(str, Enum):
    """交互模式。"""
    REMINDER = "reminder"        # 提醒 (目标停滞)
    ALERT = "alert"             # 警报 (异常/风险)
    OBSERVATION = "observation"  # 观察报告 (发现变化)
    QUESTION = "question"       # 提问 (需要用户决策)
    REPORT = "report"           # 周期性报告


class NeedType(str, Enum):
    """触发交互的内部需要类型。"""
    GOAL_STALE = "goal_stale"        # 目标停滞 (如: 30天无进展)
    ANOMALY_DETECTED = "anomaly"     # 异常检测
    WISDOM_APPLICABLE = "wisdom"     # 过去的智慧可以应用
    HEALTH_WARNING = "health"        # 自身健康告警
    PATTERN_RECOGNIZED = "pattern"   # 识别到模式
    TIME_BASED = "time"              # 时间触发 (每日汇报等)


@dataclass
class NeedSignal:
    """内部需要信号 — 触发交互的原始驱动力。

    类似人脑:
        边缘系统产生需求 → 前额叶决定是否行动 → 运动皮层执行。
    """
    need_type: NeedType
    source: str = ""               # 触发来源 (goal_id, module_name)
    description: str = ""          # 需求描述
    urgency: float = 0.0           # 0.0-1.0，紧急程度
    context: dict = field(default_factory=dict)
    timestamp: float = field(default_factory=__import__("time").time)

    @property
    def is_urgent(self) -> bool:
        return self.urgency >= 0.7


@dataclass
class InteractionCandidate:
    """交互候选 — 一个潜在的主动交互。

    关键边界:
        IS53-01: 这是提醒，不是替用户做决定。
        IS53-02: 这是建议，不是 OCOS 自己的目标。
    """
    id: str = ""
    mode: InteractionMode = InteractionMode.OBSERVATION
    priority: InteractionPriority = InteractionPriority.MEDIUM

    # 触发源
    need: NeedSignal | None = None

    # 交互内容
    title: str = ""                           # 一句话标题
    body: str = ""                            # 详细内容
    suggested_action: str = ""                # 建议行动 (不是决定!)
    relevant_data: dict = field(default_factory=dict)  # 相关数据

    # 状态
    status: InteractionStatus = InteractionStatus.DRAFT
    created_at: float = field(default_factory=__import__("time").time)
    expires_at: float = 0.0                   # 过期时间，0=不过期

    # 反馈
    acknowledged_at: float = 0.0
    user_response: str = ""

    # 元数据
    metadata: dict = field(default_factory=dict)

    def is_expired(self, now: float | None = None) -> bool:
        if self.expires_at <= 0:
            return False
        t = now if now is not None else __import__("time").time()
        return t > self.expires_at

    def acknowledge(self, response: str = "") -> None:
        self.status = InteractionStatus.ACKNOWLEDGED
        self.acknowledged_at = __import__("time").time()
        self.user_response = response

    def ignore(self) -> None:
        self.status = InteractionStatus.IGNORED

    def withdraw(self, reason: str = "") -> None:
        self.status = InteractionStatus.WITHDRAWN
        self.metadata["withdraw_reason"] = reason

    def mark_sent(self) -> None:
        self.status = InteractionStatus.SENT


@dataclass
class InteractionConfig:
    """交互系统配置。"""
    # 速率限制
    max_interactions_per_hour: int = 5
    max_critical_per_hour: int = 2
    cooldown_seconds: int = 120  # 两次交互间最小间隔

    # 自动撤回
    auto_withdraw_seconds: int = 3600  # 1小时后自动撤回未读消息

    # 优先级阈值
    critical_threshold: float = 0.8
    high_threshold: float = 0.6
    medium_threshold: float = 0.3

    # 去重窗口
    dedup_seconds: int = 600  # 10分钟内同类提醒去重


@dataclass
class InteractionHistory:
    """交互历史记录。"""
    total_sent: int = 0
    total_acknowledged: int = 0
    total_ignored: int = 0
    total_withdrawn: int = 0
    last_sent_at: float = 0.0

    @property
    def acknowledge_rate(self) -> float:
        if self.total_sent == 0:
            return 1.0
        return self.total_acknowledged / self.total_sent


__all__ = [
    "InteractionPriority", "InteractionStatus", "InteractionMode", "NeedType",
    "NeedSignal", "InteractionCandidate", "InteractionConfig", "InteractionHistory",
]
