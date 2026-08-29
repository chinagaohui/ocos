"""Phase 39.3: Permission Decision — 权限判定原子结果。

PolicyDecision 是 PermissionGateway 的唯一输出。每个决策不可变，
包含判定理由和审计标记。

Governance: Policy 不决定做什么，只决定能不能做。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class DecisionResult(str, Enum):
    """权限判定结果。

    ALLOW            — 允许执行
    DENY             — 禁止执行（不可上诉）
    REQUIRE_APPROVAL — 需要用户批准（Proposal 模式，对应 Phase 38 §Proposal≠Goal）
    """

    ALLOW = "ALLOW"
    DENY = "DENY"
    REQUIRE_APPROVAL = "REQUIRE_APPROVAL"


@dataclass(frozen=True)
class PolicyDecision:
    """权限策略判定原子结果。

    每个 Capability 请求经过 Policy 评估后返回此对象。
    不可变性保证审计链可追溯。

    Fields:
        result: ALLOW / DENY / REQUIRE_APPROVAL
        reason: 判定理由（人类可读 + 机器可审计）
        policy_id: 触发判定的策略 ID（用于审计追溯）
        audit_required: 是否强制写入 PermissionTrace
        metadata: 附加审计信息（capability、resource 等）
    """

    result: DecisionResult
    reason: str
    policy_id: str = "default"
    audit_required: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def allowed(self) -> bool:
        return self.result == DecisionResult.ALLOW

    @property
    def denied(self) -> bool:
        return self.result == DecisionResult.DENY

    @property
    def needs_approval(self) -> bool:
        return self.result == DecisionResult.REQUIRE_APPROVAL

    @classmethod
    def allow(cls, reason: str = "", policy_id: str = "default", **meta) -> PolicyDecision:
        return cls(result=DecisionResult.ALLOW, reason=reason,
                   policy_id=policy_id, metadata=dict(meta))

    @classmethod
    def deny(cls, reason: str = "", policy_id: str = "default", **meta) -> PolicyDecision:
        return cls(result=DecisionResult.DENY, reason=reason,
                   policy_id=policy_id, metadata=dict(meta))

    @classmethod
    def require_approval(cls, reason: str = "", policy_id: str = "default", **meta) -> PolicyDecision:
        return cls(result=DecisionResult.REQUIRE_APPROVAL, reason=reason,
                   policy_id=policy_id, metadata=dict(meta))
