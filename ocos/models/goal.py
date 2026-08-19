"""Goal Model — Phase 17.2 Theory → Code Alignment.

对应 GOAL_THEORY v1.0（冻结）:
- Invariant 1: Goal 只回答 What，不回答 How
- Invariant 2: Goal 生命周期长于任何 Decision
- Invariant 3: Goal 可以产生多个 Decision（一对多）
"""

from __future__ import annotations

import logging
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


# ── Enum: GoalStatus ────────────────────────────────────────────────


class GoalStatus(str, Enum):
    """Goal 的生命周期状态。

    对应 GOAL_THEORY v1.0 §4:
    Created → Active ↔ Paused → Completed | Failed | Cancelled | Superseded | Expired

    设计原则：
    - 使用 str Enum，保持与现有 `status="active"` 用法向后兼容
    - 8 种状态中 6 种为终止态，仅 (Active ↔ Paused) 为可逆
    """

    CREATED = "created"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"          # 替代旧值 "abandoned"
    CANCELLED = "cancelled"
    SUPERSEDED = "superseded"
    EXPIRED = "expired"

    @property
    def is_terminal(self) -> bool:
        """是否为终止态。"""
        return self in (
            GoalStatus.COMPLETED,
            GoalStatus.FAILED,
            GoalStatus.CANCELLED,
            GoalStatus.SUPERSEDED,
            GoalStatus.EXPIRED,
        )

    @property
    def is_active(self) -> bool:
        """是否为活跃态（可驱动 Decision）。"""
        return self in (GoalStatus.CREATED, GoalStatus.ACTIVE)

    def can_transition_to(self, target: GoalStatus) -> bool:
        """检查从当前状态到目标状态的转移是否合法。"""
        result = target in _VALID_TRANSITIONS.get(self, set())
        logger.debug("GoalStatus %s → %s: %s", self.value, target.value, result)
        return result

    @staticmethod
    def validate(value: str) -> bool:
        """检查字符串是否为合法的 GoalStatus 值。"""
        result = value in _VALID_STATUS_VALUES
        if not result:
            logger.warning("Invalid GoalStatus value: %s", value)
        return result


# ── 状态转移表 ─────────────────────────────────────────────────────

_VALID_STATUS_VALUES = {s.value for s in GoalStatus}

_VALID_TRANSITIONS: dict[GoalStatus, set[GoalStatus]] = {
    GoalStatus.CREATED: {GoalStatus.ACTIVE, GoalStatus.CANCELLED},
    GoalStatus.ACTIVE: {
        GoalStatus.PAUSED,
        GoalStatus.COMPLETED,
        GoalStatus.FAILED,
        GoalStatus.CANCELLED,
        GoalStatus.SUPERSEDED,
        GoalStatus.EXPIRED,
    },
    GoalStatus.PAUSED: {GoalStatus.ACTIVE, GoalStatus.CANCELLED, GoalStatus.SUPERSEDED},
    GoalStatus.COMPLETED: set(),       # terminal
    GoalStatus.FAILED: set(),           # terminal
    GoalStatus.CANCELLED: set(),        # terminal
    GoalStatus.SUPERSEDED: set(),       # terminal
    GoalStatus.EXPIRED: set(),          # terminal
}
