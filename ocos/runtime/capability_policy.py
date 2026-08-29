"""Phase 39.3: CapabilityPolicyProvider — 策略提供者（接入 PermissionGateway）。

继承 39.1 占位接口，39.3 接入实际 PermissionGateway。
保持向后兼容的 check() 方法 — 供 RuntimeKernel 使用。

Design (Phase 38 freeze):
    - PolicyProvider 不属于 Runtime，属于 Governance Layer
    - Runtime 通过此接口查询"当前是否允许某操作"
    - 39.1: 默认 ALLOW → 39.3: 接入 BuiltinPolicies
"""

from __future__ import annotations

from .permission import (
    BuiltinPolicies,
    PermissionContext,
    PermissionGateway,
    PermissionRequest,
    PermissionLevel,
    Caller,
)
from .permission.policy_decision import DecisionResult


class CapabilityPolicyProvider:
    """策略提供者 — Runtime ↔ Governance 桥梁。

    39.3: 接入 PermissionGateway + BuiltinPolicies。
    保持兼容 check(actor, action) → PolicyDecision。

    用法:
        provider = CapabilityPolicyProvider()
        decision = provider.check("runtime", "file.write")
        if decision == DecisionResult.ALLOW:
            ...
    """

    def __init__(self, gateway: PermissionGateway | None = None):
        self._gateway = gateway or PermissionGateway()

    def check(
        self,
        actor: str,
        action: str,
        resource: str | None = None,
        tick_id: int = 0,
        **kwargs,
    ) -> DecisionResult:
        """查询当前策略。

        Args:
            actor: 请求方 (runtime / attention / goal_maintenance / agent)
            action: 操作 (e.g. 'file.write', 'agent.invoke')
            resource: 目标资源路径
            tick_id: 当前 tick

        Returns:
            DecisionResult.ALLOW / DENY / REQUIRE_APPROVAL
        """
        # 映射 actor → Caller
        caller_map = {
            "external_agent": Caller.EXTERNAL_AGENT,
            "maintenance": Caller.MAINTENANCE,
        }
        caller = caller_map.get(actor, Caller.OCOS_EXECUTIVE)

        # 推断操作级别
        from .permission.builtin_policies import BuiltinPolicies
        level = BuiltinPolicies.REGISTERED_CAPABILITIES.get(
            action, PermissionLevel.OBSERVE
        )

        request = PermissionRequest(
            capability_id=action,
            action=action,
            resource=resource,
            caller=caller,
            level=level,
        )
        context = PermissionContext(tick_id=tick_id)

        decision, _trace = self._gateway.evaluate(request, context)
        return decision.result

    def is_allowed(self, actor: str, action: str, **kwargs) -> bool:
        """便捷方法：是否允许此操作。"""
        return self.check(actor, action, **kwargs) == DecisionResult.ALLOW

    @property
    def gateway(self) -> PermissionGateway:
        return self._gateway
