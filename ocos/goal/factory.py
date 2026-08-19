"""GoalFactory — Goal 创建工厂。

Phase 21.02: Goal Persistence
Phase 22: Goal Origin Model v1.0 集成

宪法约束:
- 禁止动态创建 MISSION 级别的 Goal
- Phase 21: 只允许 SYSTEM origin_level
- Phase 22-24: SYSTEM + HUMAN，禁止 SELF
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from ocos.agent.goal_types import (
    Goal,
    GoalAuthority,
    GoalLevel,
    GoalOriginLevel,
    GoalStatus,
)


class ConstitutionViolationError(Exception):
    """宪法违规异常。"""
    pass


class GoalFactory:
    """Goal 创建工厂。

    约束:
    - MISSION 级别: 拒绝创建
    - Phase 21: 只允许 SYSTEM origin_level
    - HUMAN/SELF 在 Phase 21 被拒绝
    - origin_level 不可为 None，默认 SYSTEM
    """

    # 当前 Phase（可外部设置）
    _current_phase: int = 21

    @classmethod
    def set_phase(cls, phase: int) -> None:
        cls._current_phase = phase

    @staticmethod
    def create(
        level: GoalLevel,
        description: str = "",
        priority: float = 5.0,
        parent_id: Optional[str] = None,
        deadline: Optional[datetime] = None,
        origin_level: GoalOriginLevel = GoalOriginLevel.SYSTEM,
        authority: Optional[GoalAuthority] = None,
        current_phase: Optional[int] = None,
        **kwargs: Any,
    ) -> Goal:
        """创建 Goal。

        Args:
            level: GoalLevel 枚举
            description: 描述
            priority: 优先级 (1-10)
            parent_id: 父 Goal ID
            deadline: 截止时间
            origin_level: 来源层级（默认 SYSTEM）
            authority: 权限级别（默认从 origin_level 推导）
            current_phase: 覆盖 Phase 编号（None=使用类默认值）
            **kwargs: 额外字段

        Returns:
            创建的 Goal 实例

        Raises:
            ConstitutionViolationError: 违规创建
        """
        phase = current_phase if current_phase is not None else GoalFactory._current_phase

        # 规则 1: MISSION 禁止动态创建
        if level == GoalLevel.MISSION:
            raise ConstitutionViolationError(
                "Mission-level goals cannot be created dynamically. "
                "Mission must be loaded from Identity/Constitution at BOOT time."
            )

        # 规则 2: Phase 21 隔离 — 只允许 SYSTEM
        if phase == 21:
            if origin_level != GoalOriginLevel.SYSTEM:
                raise ConstitutionViolationError(
                    f"Phase 21 Isolation: Only SYSTEM goals allowed. "
                    f"Got {origin_level.value}."
                )

        # 规则 3: Phase 22-24 禁止 SELF
        if 22 <= phase <= 24:
            if origin_level == GoalOriginLevel.SELF:
                raise ConstitutionViolationError(
                    f"Phase {phase} Isolation: "
                    "SELF-directed goals require Phase 25+."
                )

        # 推导 authority
        if authority is None:
            if origin_level == GoalOriginLevel.SYSTEM:
                authority = GoalAuthority.AUTONOMOUS
            elif origin_level == GoalOriginLevel.HUMAN:
                authority = GoalAuthority.FRAMEWORK
            else:
                authority = GoalAuthority.PROPOSAL

        goal_id = f"g-{uuid.uuid4().hex[:8]}"

        return Goal(
            goal_id=goal_id,
            level=level,
            description=description,
            priority=priority,
            parent_id=parent_id,
            deadline=deadline,
            status=GoalStatus.PENDING,
            origin_level=origin_level,
            authority=authority,
        )
