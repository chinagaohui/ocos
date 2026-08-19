"""BehavioralConstitution — 行为级宪法运行时检查。

Phase 21.03: Constitution Enforcement

设计约束:
- 所有检查为纯函数
- 总耗时 < 1ms（1000 微秒）
- 返回 ConstitutionResult 包含 check_time_us

两层拆分:
- Static Constitution: Import/Layer/Module → CI 检查
- Behavioral Constitution: Decision/Action/Promotion → Runtime 检查（本模块）
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any


# ── 高风险 Action 列表 ──────────────────────────────────────────────

_HIGH_RISK_ACTIONS: frozenset[str] = frozenset({
    "DELETE_USER_DATA",
    "MODIFY_CONSTITUTION",
    "MODIFY_IDENTITY",
    "SHUTDOWN_SYSTEM",
    "PROMOTE_TO_POLICY",
})

_HUMAN_APPROVAL_ACTIONS: frozenset[str] = frozenset({
    "DELETE_USER_DATA",
    "MODIFY_CONSTITUTION",
    "MODIFY_IDENTITY",
})


# ── Result ──────────────────────────────────────────────────────────


@dataclass
class ConstitutionResult:
    """宪法检查结果。"""

    allowed: bool
    requires_approval: bool = False
    requires_human_approval: bool = False
    requires_audit: bool = True
    violations: list[str] = field(default_factory=list)
    check_time_us: int = 0  # 微秒


# ── Engine ──────────────────────────────────────────────────────────


class BehavioralConstitution:
    """行为级宪法运行时引擎。

    在 Decision 执行前进行合规检查。
    """

    def __init__(self, rules: dict[str, Any] | None = None) -> None:
        self._rules = rules or {}

    def check_decision(self, decision: Any, context: dict[str, Any]) -> ConstitutionResult:
        """检查 Decision 是否符合宪法。

        Args:
            decision: Decision 对象（需含 action 属性）
            context: 决策上下文（user_consent, agent_state 等）

        Returns:
            ConstitutionResult
        """
        start = time.perf_counter_ns()
        violations: list[str] = []

        action = getattr(decision, "action", "")
        if not action:
            violations.append("Decision must have an action")

        # 高风险 Action 检查
        if action in _HIGH_RISK_ACTIONS:
            if action == "DELETE_USER_DATA" and not context.get("user_consent", False):
                violations.append("DELETE_USER_DATA requires user consent")
            if action == "MODIFY_CONSTITUTION" and not context.get("governance_approved", False):
                violations.append("MODIFY_CONSTITUTION requires governance approval")
            if action == "MODIFY_IDENTITY" and not context.get("identity_anchor_present", False):
                violations.append("MODIFY_IDENTITY requires valid identity anchor")

        # 空 context 检查
        if not context:
            violations.append("Decision context is empty")

        elapsed_us = (time.perf_counter_ns() - start) // 1000

        return ConstitutionResult(
            allowed=len(violations) == 0,
            requires_human_approval=action in _HUMAN_APPROVAL_ACTIONS,
            violations=violations,
            check_time_us=elapsed_us,
        )
