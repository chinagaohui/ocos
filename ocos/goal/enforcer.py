"""GoalOriginEnforcer — 强制执行 GOAL ORIGIN MODEL v1.0。

根据当前系统所处的 Phase，拦截非法的 Goal 创建和权限提升。

核心规则:
  1. Goal cannot increase its own authority
  2. origin_level 不可修改
  3. Phase 21: 只允许 SYSTEM
  4. Phase 22-24: SYSTEM + HUMAN，禁止 SELF
  5. HUMAN Goal 创建需 human_authorized 上下文
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ocos.kernel.goal_types import Goal, GoalAuthority, GoalOriginLevel


@dataclass
class ConstitutionResult:
    """宪法检查结果。"""
    allowed: bool = True
    violations: list[str] = field(default_factory=list)
    check_time_us: int = 0


class GoalOriginEnforcer:
    """Goal Origin 权限强制执行器。

    检查:
    - Goal 创建时的 origin_level 是否合法
    - Goal 修改时是否尝试权限提升
    - origin_level 不可跨 Phase 越界
    """

    def __init__(self, current_phase: int = 21):
        self._current_phase = current_phase

    @property
    def current_phase(self) -> int:
        return self._current_phase

    # ── 创建校验 ────────────────────────────────────────────────────

    def verify_creation(
        self,
        goal: Goal,
        creator_context: dict[str, Any] | None = None,
    ) -> ConstitutionResult:
        """验证 Goal 创建是否合法。

        Phase 隔离:
          - Phase 21: 只允许 SYSTEM
          - Phase 22-24: SYSTEM + HUMAN
          - Phase 25+: 全部三种

        Level 1 (HUMAN) 要求 human_authorized 上下文。
        """
        ctx = creator_context or {}
        origin = goal.origin_level

        # Phase 21 隔离
        if self._current_phase == 21 and origin != GoalOriginLevel.SYSTEM:
            return ConstitutionResult(
                allowed=False,
                violations=[
                    f"Phase 21 Isolation: Only SYSTEM goals allowed. "
                    f"Got {origin.value}."
                ],
            )

        # Phase 22-24 禁止 SELF
        if 22 <= self._current_phase <= 24 and origin == GoalOriginLevel.SELF:
            return ConstitutionResult(
                allowed=False,
                violations=[
                    f"Phase {self._current_phase} Isolation: "
                    "SELF-directed goals require Phase 25+."
                ],
            )

        # Level 1 (HUMAN) 需要人类授权
        if origin == GoalOriginLevel.HUMAN:
            if not ctx.get("human_authorized"):
                return ConstitutionResult(
                    allowed=False,
                    violations=[
                        "Level 1 (HUMAN) Goal creation requires "
                        "human_authorized context."
                    ],
                )

        return ConstitutionResult(allowed=True)

    # ── 修改校验 ────────────────────────────────────────────────────

    def verify_modification(
        self,
        old_goal: Goal,
        new_goal: Goal,
    ) -> ConstitutionResult:
        """验证 Goal 修改，严禁权限提升。

        规则:
          1. origin_level 不可更改
          2. authority 不可升级
          3. 非 AUTONOMOUS 不可变为 AUTONOMOUS
        """
        # 规则 1: origin_level 不可变
        if old_goal.origin_level != new_goal.origin_level:
            return ConstitutionResult(
                allowed=False,
                violations=[
                    "Forbidden: Goal origin_level cannot be changed "
                    f"from {old_goal.origin_level.value} "
                    f"to {new_goal.origin_level.value}."
                ],
            )

        # 规则 2: authority 不可提升
        if (
            old_goal.authority != GoalAuthority.AUTONOMOUS
            and new_goal.authority == GoalAuthority.AUTONOMOUS
        ):
            return ConstitutionResult(
                allowed=False,
                violations=[
                    "Forbidden: Goal cannot increase its own "
                    "authority to AUTONOMOUS."
                ],
            )

        return ConstitutionResult(allowed=True)
