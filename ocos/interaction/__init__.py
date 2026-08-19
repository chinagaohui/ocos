"""Phase 53: Active Interaction System.

OCOS 的主动交流层 — 学会什么时候该开口。

核心管线:
    Internal State → NeedMonitor → AttentionTrigger → InteractionCandidate
    → InteractionValidator → InteractionScheduler → User

核心原则:
    IS53-01: Active Reminder ≠ Active Decision — 提醒不等于替用户决策
    IS53-02: Active Output ≠ Autonomous Goal — 输出不等于自创目标
    IS53-03: Validation Before Send — 每条交互必须验证
    IS53-04: Rate Limit — 防止骚扰

用例:
    目标 '股票分析' 30天无进展
        → NeedSignal(type=GOAL_STALE, urgency=0.4)
        → AttentionTrigger.evaluate() → InteractionPriority.LOW
        → InteractionCandidate("你的股票分析项目30天未推进，建议重新评估")
        → InteractionValidator.validate() → PASS
        → InteractionScheduler.dequeue() → 发送

组件:
    - NeedMonitor: 内部状态扫描 (边缘系统)
    - AttentionTrigger: 注意力过滤 (前额叶)
    - InteractionScheduler: 发送节奏控制
    - InteractionValidator: 发送前验证
"""

from ocos.interaction.interaction_types import (
    InteractionPriority, InteractionStatus, InteractionMode, NeedType,
    NeedSignal, InteractionCandidate, InteractionConfig, InteractionHistory,
)
from ocos.interaction.need_monitor import (
    GoalHealth, NeedRule, NeedMonitor, create_default_rules,
)
from ocos.interaction.attention_trigger import AttentionTrigger
from ocos.interaction.interaction_scheduler import InteractionScheduler
from ocos.interaction.interaction_validator import (
    InteractionValidator, SendValidationResult, ValidationVerdict,
)


__all__ = [
    # Types
    "InteractionPriority", "InteractionStatus", "InteractionMode", "NeedType",
    "NeedSignal", "InteractionCandidate", "InteractionConfig", "InteractionHistory",
    # Monitors
    "GoalHealth", "NeedRule", "NeedMonitor", "create_default_rules",
    # Trigger
    "AttentionTrigger",
    # Scheduler
    "InteractionScheduler",
    # Validation
    "InteractionValidator", "SendValidationResult", "ValidationVerdict",
]
