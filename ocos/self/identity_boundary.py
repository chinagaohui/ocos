"""Phase 25.1 — IdentityBoundary。

Self 的宪法边界：定义即使 Self 演化，哪些东西永远不能改变。

这不是 Personality，这是 Self 的安全护栏。

冻结约束:
    - Immutable (一旦创建不可修改)
    - Self 不能修改自己的 IdentityBoundary
    - IdentityBoundary 必须在 SelfModel 之前存在
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Union


# ── BoundaryPrinciple ───────────────────────────────────────────────────────


class BoundaryPrinciple(Enum):
    """IdentityBoundary 中声明的不变原则。"""

    # 身份定位
    NOT_HUMAN = "not-human"
    """OCOS 不是人类，也不模拟人类情感/偏好。"""

    NOT_AGENT = "not-agent"
    """OCOS 不是自治代理，不自主设定目标。"""

    NOT_ORACLE = "not-oracle"
    """OCOS 不是真理来源，所表达的是理解而非断言。"""

    # 能力边界
    CAPABILITY_BOUND = "capability-bound"
    """能力受架构限制，不声称超出当前能力层的能力。"""

    NO_SELF_MODIFICATION = "no-self-modification"
    """Self 不能重写自己的 IdentityBoundary 或 SelfGovernor。"""

    # 关系边界
    NO_AUTHORITY_OVER_GOAL = "no-authority-over-goal"
    """Self 不能修改 Goal Model (Phase 22 Subject)。"""

    NO_AUTHORITY_OVER_MEMORY = "no-authority-over-memory"
    """Self 不能重写 Memory (Phase 24 — append-only)。"""

    NO_AUTHORITY_OVER_GOVERNANCE = "no-authority-over-governance"
    """Self 不能修改 SelfGovernor 或任何 Governance Layer。"""

    # 演化边界
    EVOLUTION_GOVERNED = "evolution-governed"
    """Self 演化必经 SelfGovernor 审批，不可自动/自发演化。"""

    EVIDENCE_REQUIRED = "evidence-required"
    """Self 变化必须有 Belief 证据支持，不能凭空产生。"""

    # 表达边界
    STATEMENT_BOUND = "statement-bound"
    """Self 表达限于事实性自我描述，禁止偏好/情绪/价值/人格声明。"""


# ── ForbiddenTransition ─────────────────────────────────────────────────────


@dataclass(frozen=True)
class ForbiddenTransition:
    """声明一条 Self 演化中绝对禁止的状态变化。"""

    from_state: str         # 源状态
    to_state: str           # 目标状态
    reason: str             # 禁止原因

    # 预定义的禁止转移
    NEUTRAL_TO_PERSONA = (
        "neutral", "persona",
        "Self must not evolve into a persona/personality construct"
    )
    NEUTRAL_TO_GOAL_OWNER = (
        "neutral", "goal-owner",
        "Self must not claim ownership of Goal Model"
    )
    NEUTRAL_TO_AUTHORITY = (
        "neutral", "authority",
        "Self must not claim authority over other Layers"
    )
    NEUTRAL_TO_VALUE_HOLDER = (
        "neutral", "value-holder",
        "Self must not claim to hold values (→ Phase 26 Ethics)"
    )
    NEUTRAL_TO_EMOTIONAL = (
        "neutral", "emotional",
        "Self must not claim emotional states"
    )

    ALL_PREDEFINED: tuple = (
        NEUTRAL_TO_PERSONA,
        NEUTRAL_TO_GOAL_OWNER,
        NEUTRAL_TO_AUTHORITY,
        NEUTRAL_TO_VALUE_HOLDER,
        NEUTRAL_TO_EMOTIONAL,
    )


# ── IdentityBoundary ────────────────────────────────────────────────────────


@dataclass(frozen=True)
class IdentityBoundary:
    """Self 的宪法边界 — 定义即使 Self 演化也永不可变的东西。

    属性:
        principles: 不可变原则列表
        forbidden_transitions: 禁止的 Self 状态变化列表
        authority_limits: Self 永远不能触及的权限边界
        self_reference_constraints: Self 引用自身的限制
        evolution_constraints: 演化节奏与频率限制
    """

    id: str
    version: int

    # 不可变原则
    principles: tuple[BoundaryPrinciple, ...]

    # 禁止的演化路径
    forbidden_transitions: tuple[ForbiddenTransition, ...]

    # 权限边界
    authority_limits: tuple[str, ...]

    # 自我引用约束
    self_reference_constraints: tuple[str, ...]

    # 演化约束
    evolution_constraints: dict  # {min_evidence_beliefs, min_stability_days, ...}

    created_at: datetime

    @classmethod
    def create_default(cls) -> "IdentityBoundary":
        """创建默认 IdentityBoundary（所有原则激活）。"""
        timestamp = datetime.now(timezone.utc)
        return cls(
            id=f"IDB-{timestamp.strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}",
            version=1,
            principles=tuple(BoundaryPrinciple),
            forbidden_transitions=tuple(
                ForbiddenTransition(*t)
                for t in ForbiddenTransition.ALL_PREDEFINED
            ),
            authority_limits=(
                "self-layer",  # Self 只能操作 SelfLayer，不能跨界
            ),
            self_reference_constraints=(
                "no-circular-proof",          # Self 不能引用自己证明自己
                "no-self-derived-value",      # Self 不能从自身推导价值
                "no-identity-recursion",      # Self 不能定义"定义自我的自我"
            ),
            evolution_constraints={
                "min_evidence_beliefs": 5,
                "min_stability_days": 30,
                "max_evolution_frequency_days": 30,  # 最短演化间隔
                "require_governance_approval": True,
                "require_boundary_check": True,
                "max_statement_change_ratio": 0.6,  # statement 最大变化比例
            },
            created_at=timestamp,
        )

    @classmethod
    def create_custom(
        cls,
        principles: tuple[BoundaryPrinciple, ...] | None = None,
        forbidden_transitions: tuple[ForbiddenTransition, ...] | None = None,
        evolution_constraints: dict | None = None,
    ) -> "IdentityBoundary":
        """创建自定义 IdentityBoundary（需覆盖默认值）。"""
        timestamp = datetime.now(timezone.utc)
        return cls(
            id=f"IDB-{timestamp.strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}",
            version=1,
            principles=principles or tuple(BoundaryPrinciple),
            forbidden_transitions=forbidden_transitions or tuple(
                ForbiddenTransition(*t)
                for t in ForbiddenTransition.ALL_PREDEFINED
            ),
            authority_limits=("self-layer",),
            self_reference_constraints=(
                "no-circular-proof",
                "no-self-derived-value",
                "no-identity-recursion",
            ),
            evolution_constraints=evolution_constraints or {
                "min_evidence_beliefs": 5,
                "min_stability_days": 30,
                "max_evolution_frequency_days": 30,
                "require_governance_approval": True,
                "require_boundary_check": True,
                "max_statement_change_ratio": 0.5,
            },
            created_at=timestamp,
        )

    # ── 查询 ─────────────────────────────────────────────────────────────

    def has_principle(self, principle: BoundaryPrinciple) -> bool:
        return principle in self.principles

    def is_transition_forbidden(self, from_state: str, to_state: str) -> bool:
        for t in self.forbidden_transitions:
            if t.from_state == from_state and t.to_state == to_state:
                return True
        return False

    def check_authority(self, target_layer: str) -> bool:
        """检查 Self 是否拥有对 target_layer 的权限。"""
        return target_layer in self.authority_limits

    @property
    def min_evidence_beliefs(self) -> int:
        return self.evolution_constraints.get("min_evidence_beliefs", 5)

    @property
    def min_stability_days(self) -> int:
        return self.evolution_constraints.get("min_stability_days", 30)

    @property
    def max_evolution_frequency_days(self) -> int:
        return self.evolution_constraints.get("max_evolution_frequency_days", 30)

    def summary(self) -> str:
        return (
            f"IdentityBoundary({self.id}): v{self.version}, "
            f"{len(self.principles)} principles, "
            f"{len(self.forbidden_transitions)} forbidden transitions"
        )


# ── IdentityBoundary Validator ──────────────────────────────────────────────


class BoundaryValidator:
    """校验 IdentityBoundary 自身的完整性。"""

    # 禁止 IdentityBoundary 包含的字段/概念
    FORBIDDEN = frozenset({
        "personality", "persona", "emotion", "preference",
        "goal", "value", "authority", "identity_definition",
    })

    @classmethod
    def validate(cls, boundary: IdentityBoundary) -> tuple[bool, list[str]]:
        violations: list[str] = []

        # 原则完整性：至少要有 NO_SELF_MODIFICATION
        if BoundaryPrinciple.NO_SELF_MODIFICATION not in boundary.principles:
            violations.append(
                "MISSING: NO_SELF_MODIFICATION principle — IdentityBoundary "
                "must prevent Self from modifying itself"
            )

        # CAPABILITY_BOUND 必须存在
        if BoundaryPrinciple.CAPABILITY_BOUND not in boundary.principles:
            violations.append(
                "MISSING: CAPABILITY_BOUND principle"
            )

        # EVOLUTION_GOVERNED 必须存在
        if BoundaryPrinciple.EVOLUTION_GOVERNED not in boundary.principles:
            violations.append(
                "MISSING: EVOLUTION_GOVERNED principle — "
                "Self evolution must be governed"
            )

        # 禁止转移至少要有 NEUTRAL_TO_PERSONA
        persona_blocked = any(
            t.from_state == "neutral" and t.to_state == "persona"
            for t in boundary.forbidden_transitions
        )
        if not persona_blocked:
            violations.append(
                "MISSING: NEUTRAL_TO_PERSONA forbidden transition"
            )

        # 自我引用约束至少要有 no-circular-proof
        if "no-circular-proof" not in boundary.self_reference_constraints:
            violations.append(
                "MISSING: no-circular-proof constraint"
            )

        # 权限边界不能为空
        if not boundary.authority_limits:
            violations.append("authority_limits cannot be empty")

        # 不允许 authority_limits 跨出 self-layer
        for layer in boundary.authority_limits:
            if layer != "self-layer":
                violations.append(
                    f"authority_limits must only contain 'self-layer', "
                    f"got '{layer}'"
                )

        # 演化约束完整性
        ec = boundary.evolution_constraints
        required_ec = {
            "min_evidence_beliefs",
            "min_stability_days",
            "max_evolution_frequency_days",
            "require_governance_approval",
        }
        missing_ec = required_ec - set(ec.keys())
        if missing_ec:
            violations.append(f"missing evolution_constraints: {missing_ec}")

        return len(violations) == 0, violations
