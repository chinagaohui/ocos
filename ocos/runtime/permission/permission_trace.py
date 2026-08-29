"""Phase 39.3: Permission Trace — 审计链原子记录。

每次 ALLOW/DENY/REQUIRE_APPROVAL 决策必须生成 PermissionTrace。
与 ExecutionTrace、MemoryTrace 共同形成 Cognitive Audit Trail。

审计链可回答:
    "为什么 OCOS 调用了 Photoshop？"
    → Tick 48391, Goal 'image_optimize', Capability 'image_edit',
      Decision ALLOW, Policy 'user_authorized_tool'
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field

from .policy_decision import DecisionResult, PolicyDecision
from .permission_request import PermissionContext, PermissionRequest


@dataclass(frozen=True)
class PermissionTrace:
    """权限审计记录 — 不可变。

    Fields:
        trace_id:       审计记录唯一 ID
        timestamp:      决策时间 (epoch float)
        request:        请求快照 (PermissionRequest 关键字段)
        context:        认知上下文快照
        decision:       判定结果 (ALLOW/DENY/REQUIRE_APPROVAL)
        reason:         判定理由
        policy_id:      触发判定的策略 ID
    """

    trace_id: str
    timestamp: float
    capability_id: str
    action: str
    resource: str | None
    caller: str
    risk_level: str
    decision: str  # DecisionResult value
    reason: str
    policy_id: str
    tick_id: int
    goal_id: str | None = None

    @classmethod
    def record(
        cls,
        request: PermissionRequest,
        context: PermissionContext,
        decision: PolicyDecision,
    ) -> PermissionTrace:
        """从请求+上下文+决策创建审计记录。"""
        return cls(
            trace_id=str(uuid.uuid4()),
            timestamp=time.time(),
            capability_id=request.capability_id,
            action=request.action,
            resource=request.resource,
            caller=request.caller.value,
            risk_level=request.risk_level.value,
            decision=decision.result.value,
            reason=decision.reason,
            policy_id=decision.policy_id,
            tick_id=context.tick_id,
            goal_id=context.goal_id,
        )

    def to_dict(self) -> dict:
        return {
            "trace_id": self.trace_id,
            "timestamp": self.timestamp,
            "capability_id": self.capability_id,
            "action": self.action,
            "resource": self.resource,
            "caller": self.caller,
            "risk_level": self.risk_level,
            "decision": self.decision,
            "reason": self.reason,
            "policy_id": self.policy_id,
            "tick_id": self.tick_id,
            "goal_id": self.goal_id,
        }
