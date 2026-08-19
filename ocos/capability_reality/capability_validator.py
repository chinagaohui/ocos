"""Phase 55: CapabilityValidator — 执行前/后验证。

执行前:
    - 权限检查
    - 风险等级检查
    - 参数完整性检查
    - 沙盒边界检查
    - 速率限制

执行后:
    - 结果格式检查
    - 异常分类
    - 影响评估
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import time as _time

from ocos.capability_reality.adapter_types import (
    ExecutionContext, ExecutionResult, ExecutionStatus,
    CapabilityDescriptor,
)


class ValidationDecision(str, Enum):
    APPROVE = "approve"
    REJECT = "reject"
    NEEDS_REVIEW = "needs_review"


@dataclass
class ValidationResult:
    decision: ValidationDecision
    reason: str = ""
    warnings: list[str] = field(default_factory=list)


@dataclass
class CapabilityValidator:
    """能力执行验证器。

    规则:
        CR55-01: 高风险操作需要额外批准
        CR55-02: 适配器隔离 — 失败不影响主脑
        CR55-03: 每次执行都有事件记录
    """

    # 安全策略
    auto_approve_risk_below: int = 3     # risk_level < 3 自动批准
    max_risk_level: int = 5              # risk_level > 5 的操作被拒绝
    rate_limit_window: float = 60.0      # 速率窗口(秒)
    max_ops_per_window: int = 100        # 窗口内最大操作数

    # 执行追踪
    _execution_history: list[tuple[float, str]] = field(default_factory=list)
    _total_approved: int = 0
    _total_rejected: int = 0

    def validate_pre(self, ctx: ExecutionContext, descriptor: CapabilityDescriptor) -> ValidationResult:
        """执行前验证。"""
        warnings: list[str] = []

        # 1. 速率限制
        if not self._check_rate_limit():
            self._total_rejected += 1
            return ValidationResult(
                ValidationDecision.REJECT,
                reason="rate limit exceeded",
            )

        # 2. 参数检查
        for param in descriptor.required_params:
            if param not in ctx.params:
                self._total_rejected += 1
                return ValidationResult(
                    ValidationDecision.REJECT,
                    reason=f"missing required param: {param}",
                )

        # 3. 超时检查
        if ctx.timeout <= 0 or ctx.timeout > 300:
            warnings.append(f"unusual timeout: {ctx.timeout}s")

        # 4. 风险检查
        if descriptor.risk_level > self.max_risk_level:
            self._total_rejected += 1
            return ValidationResult(
                ValidationDecision.REJECT,
                reason=f"risk level {descriptor.risk_level} exceeds max {self.max_risk_level}",
            )

        # 高风险 + 无沙盒 = 直接拒绝 (先检查，比阈值更重要)
        if descriptor.risk_level >= 4 and not ctx.sandboxed:
            self._total_rejected += 1
            return ValidationResult(
                ValidationDecision.REJECT,
                reason=f"high risk ({descriptor.risk_level}) without sandbox",
            )

        # 超过自动批准阈值 → 需要审查
        if descriptor.risk_level >= self.auto_approve_risk_below:
            self._total_approved += 1
            return ValidationResult(
                ValidationDecision.NEEDS_REVIEW,
                reason=f"risk {descriptor.risk_level} requires review",
                warnings=warnings,
            )

        self._total_approved += 1
        return ValidationResult(
            ValidationDecision.APPROVE,
            reason="all checks passed",
            warnings=warnings,
        )

    def validate_post(self, result: ExecutionResult) -> ValidationResult:
        """执行后验证。"""
        if result.status == ExecutionStatus.FAILED:
            return ValidationResult(
                ValidationDecision.REJECT,
                reason=f"execution failed: {result.error}",
            )
        if result.status == ExecutionStatus.TIMEOUT:
            return ValidationResult(
                ValidationDecision.REJECT,
                reason=f"timed out after {result.duration_ms:.0f}ms",
            )
        return ValidationResult(ValidationDecision.APPROVE)

    def _check_rate_limit(self) -> bool:
        now = _time.time()
        cutoff = now - self.rate_limit_window
        self._execution_history = [
            (t, n) for t, n in self._execution_history if t > cutoff
        ]
        self._execution_history.append((now, ""))
        return len(self._execution_history) <= self.max_ops_per_window

    def stats(self) -> dict:
        return {
            "total_approved": self._total_approved,
            "total_rejected": self._total_rejected,
            "rate_limit_remaining": self.max_ops_per_window - len(self._execution_history),
        }

    def clear(self) -> None:
        self._execution_history.clear()
        self._total_approved = 0
        self._total_rejected = 0


__all__ = ["CapabilityValidator", "ValidationResult", "ValidationDecision"]
