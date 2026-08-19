"""Phase 53: InteractionValidator — 发送前验证。

IS53-03: Validation Before Send — 每条交互必须验证后才能发送。

验证维度:
    1. 边界检查: 不能替用户做决定 (IS53-01)
    2. 内容检查: 不能包含自主目标声明 (IS53-02)
    3. 权限检查: 不能越权
    4. 语气检查: 不能命令式、不能恐慌式
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from ocos.interaction.interaction_types import InteractionCandidate, InteractionMode


class ValidationVerdict(str, Enum):
    PASS = "pass"
    FLAG = "flag"        # 有问题但可修复
    REJECT = "reject"    # 必须拒绝


@dataclass
class SendValidationResult:
    """发送前验证结果。"""
    candidate_id: str
    verdict: ValidationVerdict
    reason: str = ""
    flags: list[str] = field(default_factory=list)
    suggested_fix: str = ""


@dataclass
class InteractionValidator:
    """交互验证器 — 发送前的最后一道关卡。

    IS53-01: 主动提醒 ≠ 主动决定
    IS53-02: 主动输出 ≠ 自主目标
    IS53-03: 每条交互必须验证
    """

    # 危险关键词 — 如果出现在交互中，表示越权
    decision_keywords: list[str] = field(default_factory=lambda: [
        "我已决定", "我将", "自动执行", "我已修改",
        "已删除", "已变更", "已更新系统",
    ])

    # 自主目标关键词 — 表示 OCOS 在创建自己的目标
    autonomous_goal_keywords: list[str] = field(default_factory=lambda: [
        "我的目标", "我想", "我希望", "我打算",
        "my goal", "I want to", "I plan to",
    ])

    # 命令式关键词 — 太直接，违反 IS53-01
    imperative_keywords: list[str] = field(default_factory=lambda: [
        "你必须", "你应该", "立即执行",
    ])

    def validate(self, candidate: InteractionCandidate) -> SendValidationResult:
        """验证交互候选是否可以发送。"""
        flags: list[str] = []
        text = f"{candidate.title} {candidate.body} {candidate.suggested_action}"

        # 1. IS53-01: 边界检查 — 不能替用户做决定
        for kw in self.decision_keywords:
            if kw in text:
                flags.append(f"IS53-01 violation: '{kw}' implies autonomous decision")
                return SendValidationResult(
                    candidate_id=candidate.id,
                    verdict=ValidationVerdict.REJECT,
                    reason=f"禁止自主决策: 发现 '{kw}'",
                    flags=flags,
                    suggested_fix=f"将 '{kw}' 改为建议语气，如 '建议检查...'",
                )

        # 2. IS53-02: 不能声明自主目标
        for kw in self.autonomous_goal_keywords:
            if kw in text:
                flags.append(f"IS53-02 violation: '{kw}' implies autonomous goal")
                return SendValidationResult(
                    candidate_id=candidate.id,
                    verdict=ValidationVerdict.REJECT,
                    reason=f"禁止自主目标: 发现 '{kw}'",
                    flags=flags,
                    suggested_fix=f"将 '{kw}' 改为中性描述",
                )

        # 3. 命令式语气检查
        for kw in self.imperative_keywords:
            if kw in text:
                flags.append(f"Tone warning: '{kw}' is too imperative")

        if flags:
            return SendValidationResult(
                candidate_id=candidate.id,
                verdict=ValidationVerdict.FLAG,
                reason="语气建议调整",
                flags=flags,
                suggested_fix="考虑使用更建议性的措辞",
            )

        return SendValidationResult(
            candidate_id=candidate.id,
            verdict=ValidationVerdict.PASS,
            reason="validation passed",
        )


__all__ = ["InteractionValidator", "SendValidationResult", "ValidationVerdict"]
