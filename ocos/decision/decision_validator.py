"""Phase 43: DecisionValidator — 决策边界守卫。

强制执行三大边界:
    D43-01: Decision ≠ Goal       — 决策提案不能创建/修改 Goal
    D43-02: Decision ≠ Execution  — 决策提案不能直接执行
    D43-03: Wisdom ≠ Rule         — 智慧建议不能取代当前情境判断
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from ocos.decision.decision_types import DecisionProposal, DecisionOption


class Violation(Enum):
    """决策违规类型。"""
    PROPOSES_GOAL = "proposes_goal"         # 决策提议创建 Goal
    DIRECT_EXECUTION = "direct_execution"   # 决策试图直接执行（绕过 Capability→Permission）
    WISDOM_AS_RULE = "wisdom_as_rule"       # 智慧建议被当作不可违反的规则
    EMPTY_PROPOSAL = "empty_proposal"       # 空提案
    EXCESSIVE_RISK = "excessive_risk"       # 超过风险阈值


@dataclass(frozen=True)
class DecisionValidationResult:
    """决策验证结果。"""
    is_valid: bool
    violations: tuple[Violation, ...] = ()
    reason: str = ""


@dataclass
class DecisionValidator:
    """决策提案边界守卫。

    每条规则分别验证:
        - Goal creation check
        - Execution check
        - Wisdom-to-rule check
    """

    max_risk_threshold: float = 0.9  # 超出此值拒绝

    def validate(self, proposal: DecisionProposal) -> DecisionValidationResult:
        violations: list[Violation] = []

        # Rule 1: No empty proposal
        if not proposal.ranked_options:
            violations.append(Violation.EMPTY_PROPOSAL)

        for opt in proposal.ranked_options:
            # Rule 2: check for goal-like descriptions
            if self._looks_like_goal(opt):
                violations.append(Violation.PROPOSES_GOAL)

            # Rule 3: check for execution-like descriptions
            if self._looks_like_execution(opt):
                violations.append(Violation.DIRECT_EXECUTION)

            # Rule 4: wisdom as immutable rule
            if opt.source == "wisdom_suggested" and opt.confidence > 0.95:
                violations.append(Violation.WISDOM_AS_RULE)

            # Rule 5: excessive risk
            if opt.risk_score > self.max_risk_threshold:
                violations.append(Violation.EXCESSIVE_RISK)

        is_valid = len(violations) == 0
        return DecisionValidationResult(
            is_valid=is_valid,
            violations=tuple(violations),
            reason="" if is_valid
            else f"Violations: {[v.value for v in violations]}",
        )

    def _looks_like_goal(self, opt: DecisionOption) -> bool:
        """检测 option 是否像在创建 Goal。

        启发式: description 中包含特定触发词。
        """
        trigger_words = [
            "创建目标", "新目标", "set goal", "new goal",
            "开始项目", "启动", "建立系统",
        ]
        desc_lower = opt.description.lower()
        return any(tw.lower() in desc_lower for tw in trigger_words)

    def _looks_like_execution(self, opt: DecisionOption) -> bool:
        """检测 option 是否像在直接执行。

        启发式: description 中包含特定触发词。
        """
        trigger_words = [
            "执行", "运行", "调用", "启动工具",
            "execute", "run", "invoke", "call tool",
            "直接修改", "写入文件",
        ]
        desc_lower = opt.description.lower()
        return any(tw.lower() in desc_lower for tw in trigger_words)


__all__ = ["Violation", "DecisionValidationResult", "DecisionValidator"]
