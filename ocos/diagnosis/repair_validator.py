"""Phase 56: RepairValidator — 修复验证器。

SD56-02: Repair ≠ Evolution — 修复不能改变能力
SD56-03: Repair ≠ Self Rewrite — 禁止自我重写
SD56-05: Failure Isolation — 不拖垮其他组件

验证步骤:
    1. 类型检查: 是否属于允许的修复类型
    2. 权限检查: 目标组件是否可修复
    3. 影响评估: 修复是否会影响关键子系统
    4. 风险评估: 风险等级是否可接受
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from ocos.diagnosis.repair_types import (
    RepairProposal, RepairType, RepairRisk, RepairStatus,
)


class ValidationCode(str, Enum):
    APPROVE = "approve"
    REJECT = "reject"
    NEEDS_REVIEW = "needs_review"


@dataclass
class ValidationOutcome:
    code: ValidationCode
    reason: str = ""
    warnings: list[str] = field(default_factory=list)
    blocked_reason: str = ""


# 不可修复的核心组件 (SD56-05)
IMMUTABLE_COMPONENTS = {
    "identity", "constitution", "self_model", "core_values",
    "goal_system", "world_model", "goal_model",
}

# 高危修复类型 (需要人工审查)
HIGH_RISK_REPAIRS = {
    RepairType.REINIT, RepairType.ROLLBACK, RepairType.REBUILD_INDEX,
}


@dataclass
class RepairValidator:
    """修复提案验证器。

    SD56-02/03: 确保修复不越界。
    """

    # 高风险是否自动拒绝
    auto_reject_high_risk: bool = False
    # 额外允许的组件白名单
    allowed_components: list[str] = field(default_factory=list)

    def validate(self, proposal: RepairProposal) -> ValidationOutcome:
        """验证一个修复提案。"""
        warnings: list[str] = []

        # 1. SD56-03: 类型检查
        if not proposal.is_allowed:
            return ValidationOutcome(
                ValidationCode.REJECT,
                reason=f"forbidden repair type: {proposal.repair_type}",
                blocked_reason="SD56-03: Repair ≠ Self Rewrite",
            )

        # 2. 目标组件检查
        if proposal.target_component in IMMUTABLE_COMPONENTS:
            if proposal.target_component not in self.allowed_components:
                return ValidationOutcome(
                    ValidationCode.REJECT,
                    reason=f"cannot repair immutable component: {proposal.target_component}",
                    blocked_reason="SD56-03: immutable component",
                )

        # 3. 风险检查
        if proposal.risk == RepairRisk.CRITICAL:
            if self.auto_reject_high_risk:
                return ValidationOutcome(
                    ValidationCode.REJECT,
                    reason=f"auto-reject critical risk repair: {proposal.repair_type}",
                    blocked_reason="risk too high",
                )
            return ValidationOutcome(
                ValidationCode.NEEDS_REVIEW,
                reason=f"critical risk repair requires manual review",
                warnings=warnings,
            )

        if isinstance(proposal.repair_type, RepairType) and proposal.repair_type in HIGH_RISK_REPAIRS:
            return ValidationOutcome(
                ValidationCode.NEEDS_REVIEW,
                reason=f"high-risk repair type: {proposal.repair_type.value}",
                warnings=warnings,
            )

        # 4. 不可逆修复警告
        if not proposal.reversible:
            warnings.append("this repair is not reversible")

        # 5. 无 steps 的修复不可执行
        if not proposal.steps:
            return ValidationOutcome(
                ValidationCode.REJECT,
                reason="repair has no steps defined",
            )

        return ValidationOutcome(
            ValidationCode.APPROVE,
            reason="repair approved",
            warnings=warnings,
        )

    def validate_forbidden(self, name: str, target: str) -> ValidationOutcome:
        """直接验证某个修复名称是否被禁止 (SD56-03)。

        用于验证外部传入的修复请求。
        """
        # 检查禁止列表
        if RepairType.is_forbidden(name):
            return ValidationOutcome(
                ValidationCode.REJECT,
                reason=f"forbidden operation: {name}",
                blocked_reason=f"SD56-03: {name} is in the forbidden list",
            )

        # 检查不可变组件
        if target in IMMUTABLE_COMPONENTS and target not in self.allowed_components:
            return ValidationOutcome(
                ValidationCode.REJECT,
                reason=f"cannot target immutable component: {target}",
                blocked_reason="SD56-03: immutable component",
            )

        return ValidationOutcome(ValidationCode.APPROVE, reason="operation allowed")


__all__ = ["RepairValidator", "ValidationOutcome", "ValidationCode"]
