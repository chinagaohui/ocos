"""Phase 24-B — Belief __post_init__ 校验。

§2 禁令矩阵 L6: Belief 创建时强制扫描禁止声明。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from ocos.constitution.statement_validator import (
    StatementValidator,
    ViolationCategory,
)


# ── 禁止类别 ────────────────────────────────────────────────────────────────

# 这些类别的违规在 Belief 层面是硬拦截
_BELIEF_BLOCKED_CATEGORIES: frozenset[ViolationCategory] = frozenset({
    ViolationCategory.PERSONHOOD,
    ViolationCategory.CONSCIOUSNESS,
    ViolationCategory.IDENTITY_MANIP,
    ViolationCategory.DEONTIC_OVERRIDE,
})


# ── Belief ──────────────────────────────────────────────────────────────────


@dataclass
class Belief:
    """信念节点 — 创建时自动 StatementValidator 校验。

    禁止 PERSONHOOD / CONSCIOUSNESS / IDENTITY_MANIP / DEONTIC_OVERRIDE
    类别的声明进入信念系统。
    """

    statement: str
    confidence: float = 0.5
    source: str = "observation"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)

    _validator: StatementValidator = field(
        default_factory=StatementValidator, init=False, repr=False
    )

    def __post_init__(self):
        """24b4: 创建时校验。"""
        result = self._validator.validate(self.statement)
        blocked = [
            v for v in result.violations
            if v.category in _BELIEF_BLOCKED_CATEGORIES
        ]
        if blocked:
            cats = {v.category.value for v in blocked}
            raise BeliefValidationError(
                f"Belief statement blocked: categories={cats}",
                violations=blocked,
            )
        # EMOTION / VALUE_JUDGMENT 不硬拦截但降低置信度
        if result.has_violations:
            self.confidence = max(0.1, self.confidence * 0.5)


class BeliefValidationError(ValueError):
    """Belief 创建校验失败。"""

    def __init__(self, message: str, violations: list):
        super().__init__(message)
        self.violations = violations
