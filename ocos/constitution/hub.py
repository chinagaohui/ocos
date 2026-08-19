"""ConstitutionHub — 三层宪法统一执行入口。

Phase 21: 聚合 StaticConstitution + BehavioralConstitution + GoalOriginEnforcer。
提供 check_decision() / check_action() / check_promotion() 统一接口。

设计约束：
- 只做聚合和调用，不改变各检查器内部逻辑
- 所有结果以 behavioral.ConstitutionResult（完整版）返回
"""

from __future__ import annotations

import logging
from typing import Any

from ocos.constitution.behavioral import (
    BehavioralConstitution,
    ConstitutionResult as BehavioralResult,
)
from ocos.goal.enforcer import GoalOriginEnforcer, ConstitutionResult as EnforcerResult
from ocos.kernel.goal_types import Goal

logger = logging.getLogger(__name__)

# ── Re-export: Hub 统一使用 BehavioralResult ──────────────────────────
ConstitutionResult = BehavioralResult


class ConstitutionHub:
    """三层宪法统一入口。

    聚合:
      - Static Constitution (kernel 层 24 条规则) — 导入/层/模块检查
      - Behavioral Constitution — 行为级运行时风险
      - Goal Origin Enforcer — Goal 来源权限

    Usage:
        hub = ConstitutionHub(phase=21)
        result = hub.check_decision(decision, context)
        if not result.allowed:
            raise ConstitutionViolation(result.violations)
    """

    def __init__(self, phase: int = 21) -> None:
        self._phase = phase
        self._behavioral = BehavioralConstitution()
        self._goal_enforcer = GoalOriginEnforcer(current_phase=phase)

    # ── Public API ────────────────────────────────────────────────────────

    def check_decision(
        self,
        decision: Any,
        context: dict[str, Any] | None = None,
    ) -> ConstitutionResult:
        """检查一个 Decision 是否符合三层宪法。

        Args:
            decision: Decision 对象（需含 action 属性）
            context: 决策上下文

        Returns:
            ConstitutionResult（aggregated）
        """
        ctx = context or {}
        violations: list[str] = []

        # 1. Behavioral Constitution
        b_result = self._behavioral.check_decision(decision, ctx)
        violations.extend(b_result.violations)

        return ConstitutionResult(
            allowed=len(violations) == 0,
            requires_approval=b_result.requires_approval,
            requires_human_approval=b_result.requires_human_approval,
            requires_audit=b_result.requires_audit,
            violations=violations,
            check_time_us=b_result.check_time_us,
        )

    def check_action(
        self,
        action: str,
        context: dict[str, Any] | None = None,
    ) -> ConstitutionResult:
        """检查一个 Action 字符串是否合法。

        Shortcut: 构造最小 Decision 对象，调用 check_decision。
        """
        ctx = context or {}
        decision = _FakeDecision(action=action)
        return self.check_decision(decision, ctx)

    def check_promotion(
        self,
        old_goal: Goal,
        new_goal: Goal,
        context: dict[str, Any] | None = None,
    ) -> ConstitutionResult:
        """检查 Goal 修改是否合法（严禁权限提升）。

        Delegates to GoalOriginEnforcer.verify_modification.
        """
        ctx = context or {}
        e_result = self._goal_enforcer.verify_modification(old_goal, new_goal)

        violations: list[str] = list(e_result.violations)
        if e_result.allowed and ctx.get("require_human_approval"):
            return ConstitutionResult(
                allowed=False,
                requires_human_approval=True,
                violations=["Goal promotion requires human approval"],
                check_time_us=e_result.check_time_us,
            )

        return ConstitutionResult(
            allowed=e_result.allowed,
            violations=violations,
            check_time_us=e_result.check_time_us,
        )

    def verify_goal_creation(
        self,
        goal: Goal,
        creator_context: dict[str, Any] | None = None,
    ) -> ConstitutionResult:
        """验证 Goal 创建是否合法。

        Delegates to GoalOriginEnforcer.verify_creation.
        """
        e_result = self._goal_enforcer.verify_creation(goal, creator_context or {})
        return ConstitutionResult(
            allowed=e_result.allowed,
            violations=list(e_result.violations),
            check_time_us=e_result.check_time_us,
        )

    # ── 查询 ──────────────────────────────────────────────────────────────

    @property
    def phase(self) -> int:
        return self._phase

    def update_phase(self, phase: int) -> None:
        """更新当前 Phase（隔离级别）。"""
        self._phase = phase
        self._goal_enforcer = GoalOriginEnforcer(current_phase=phase)
        logger.info("ConstitutionHub phase updated to %d", phase)


# ── Aux ────────────────────────────────────────────────────────────────


class _FakeDecision:
    """最小 Decision 对象，仅持有 action 字符串。"""

    __slots__ = ("action",)

    def __init__(self, action: str) -> None:
        self.action = action
