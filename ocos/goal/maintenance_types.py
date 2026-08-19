"""Phase 39.6: Maintenance Types — 目标健康监控与维护事件。

核心区分:
    Goal ≠ Task       — Maintenance 管理 Goal，Planner 管理 Task
    Maintenance ≠ Desire   — 不自动生成目标，只监控已有目标
    Maintenance ≠ Decider  — 不修改/删除/改变优先级，只检测状态并上报

GoalHealth 是 Maintenance 的判定输出，流经:
    Goal → Monitor.evaluate() → GoalHealth state
    → MaintenanceEvent → EventBus → Attention Candidate
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


# ═══════════════════════════════════════════════════════════════════════════
# GoalHealth — 目标健康状态
# ═══════════════════════════════════════════════════════════════════════════

class GoalHealth(str, Enum):
    """目标健康状态。

    ACTIVE     — 持续进展中（正常）
    WARNING    — 进展放缓，需关注
    STALLED    — 长期无进展，需重新关注
    BLOCKED    — 被阻塞，依赖未满足
    COMPLETED  — 已完成（可归档）
    INACTIVE   — 用户暂停/取消（不产生 MaintenanceEvent）
    """

    ACTIVE = "active"
    WARNING = "warning"
    STALLED = "stalled"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    INACTIVE = "inactive"

    @property
    def needs_attention(self) -> bool:
        """是否需要 Attention 介入。"""
        return self in (GoalHealth.WARNING, GoalHealth.STALLED, GoalHealth.BLOCKED)

    @property
    def severity(self) -> float:
        """严重程度 0.0~1.0。"""
        return {
            GoalHealth.ACTIVE: 0.0,
            GoalHealth.WARNING: 0.4,
            GoalHealth.STALLED: 0.7,
            GoalHealth.BLOCKED: 0.9,
            GoalHealth.COMPLETED: 0.0,
            GoalHealth.INACTIVE: 0.0,
        }[self]


# ═══════════════════════════════════════════════════════════════════════════
# MaintenanceEvent — 维护事件（非 Action）
# ═══════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class MaintenanceEvent:
    """目标维护事件 — 输出给 EventBus，不是 Action。

    流向: Maintenance Engine → EventBus → Attention CandidateCollector

    字段:
        goal_id:      关联的 Goal ID
        health:       目标健康状态
        severity:     严重程度 (0.0~1.0)
        tick_id:      产生事件的 tick
        reason:       判定原因（人类可读）
        progress_tag:  进度标签（可选，如 "50%", "3 days no action"）
    """

    goal_id: str
    health: GoalHealth
    severity: float
    tick_id: int
    reason: str = ""
    progress_tag: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "goal_id": self.goal_id,
            "health": self.health.value,
            "severity": self.severity,
            "tick_id": self.tick_id,
            "reason": self.reason,
            "progress_tag": self.progress_tag,
        }


# ═══════════════════════════════════════════════════════════════════════════
# GoalHealthSnapshot — 单次健康评估结果
# ═══════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class GoalHealthSnapshot:
    """单次健康评估的完整结果。

    可序列化为 dict，用于:
        - 事件序列化
        - Checkpoint (attention_focus 字段)
        - 审计追踪
    """

    goal_id: str
    health: GoalHealth
    last_progress_tick: int
    attention_age: int  # ticks since last focused
    progress_score: float = 0.0
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "goal_id": self.goal_id,
            "health": self.health.value,
            "last_progress_tick": self.last_progress_tick,
            "attention_age": self.attention_age,
            "progress_score": self.progress_score,
            "warnings": list(self.warnings),
        }
