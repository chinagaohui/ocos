"""Phase 39.3: Builtin Policies — 默认安全策略规则。

冻结规则:
    1. Default-Deny: 未知 Capability → DENY
    2. Protected Operations: 外部 Agent 不能写 OCOS 核心
    3. Capability Level Guard: 操作级别不能超过 Capability 注册级别
    4. External Agent Boundary: EXTERNAL_AGENT 只能 OBSERVE

Governance:
    - 所有策略必须返回 PolicyDecision
    - 策略不能 import ocos.goal, ocos.self, ocos.memory (防止循环)
"""

from __future__ import annotations

from .permission_level import OPERATION_LEVELS, PermissionLevel
from .permission_request import Caller, PermissionRequest, RiskLevel
from .policy_decision import PolicyDecision


class BuiltinPolicies:
    """内置权限策略 — 规则评估引擎。

    按优先级顺序评估，第一个匹配的 Policy 返回结果。
    39.3: 纯规则引擎，不做 ML 风险模型。
    """

    # ── 受保护资源前缀 ──
    PROTECTED_RESOURCES = (
        "ocos.goal", "ocos.self", "ocos.memory", "ocos.constitution",
        "ocos.runtime.kernel", "ocos.identity",
    )

    # ── Capability 注册表 ──
    # 键: capability_id → 允许的最大 PermissionLevel
    REGISTERED_CAPABILITIES: dict[str, PermissionLevel] = {
        # L0: 内部自省
        "runtime.status": PermissionLevel.OBSERVE,
        "goal.list": PermissionLevel.OBSERVE,
        "memory.query": PermissionLevel.OBSERVE,
        "attention.snapshot": PermissionLevel.OBSERVE,
        # L1: 外部读取
        "file.read": PermissionLevel.READ,
        "web.get": PermissionLevel.READ,
        "database.query": PermissionLevel.READ,
        # L2: 外部写入 (39.3: REQUIRE_APPROVAL by default)
        "file.write": PermissionLevel.WRITE,
        "database.insert": PermissionLevel.WRITE,
        # L3: 执行动作 (39.3: REQUIRE_APPROVAL by default)
        "shell.execute": PermissionLevel.EXECUTE,
        "agent.invoke": PermissionLevel.EXECUTE,
        "tool.execute": PermissionLevel.EXECUTE,
    }

    def evaluate(self, request: PermissionRequest) -> PolicyDecision:
        """按优先级评估请求。

        优先级:
            1. External Agent Boundary (最高)
            2. Protected Resources
            3. Unregistered Capability (Default-Deny)
            4. Capability Level Guard
            5. Risk-level Approval
            6. Default ALLOW (known, safe capability)
        """
        # 1. External Agent Boundary
        decision = self._check_external_agent_boundary(request)
        if decision:
            return decision

        # 2. Protected Resources
        decision = self._check_protected_resources(request)
        if decision:
            return decision

        # 3. Unregistered Capability → Default-Deny
        decision = self._check_registered(request)
        if decision:
            return decision

        # 4. Capability Level Guard
        decision = self._check_level(request)
        if decision:
            return decision

        # 5. Risk-level Approval
        decision = self._check_risk_approval(request)
        if decision:
            return decision

        # 6. Default: ALLOW (known, safe capability)
        return PolicyDecision.allow(
            reason=f"known capability: {request.capability_id}",
            policy_id="default_allow",
        )

    # ── 策略检查 ──

    def _check_external_agent_boundary(self, request: PermissionRequest) -> PolicyDecision | None:
        """外部 Agent 只能 OBSERVE，不能写/执行。"""
        if request.caller == Caller.EXTERNAL_AGENT:
            if request.level > PermissionLevel.OBSERVE:
                return PolicyDecision.deny(
                    reason="EXTERNAL_AGENT cannot perform write/execute operations",
                    policy_id="external_agent_boundary",
                )
        return None

    def _check_protected_resources(self, request: PermissionRequest) -> PolicyDecision | None:
        """保护 OCOS 核心资源不被外部写入。"""
        if request.resource and request.level >= PermissionLevel.WRITE:
            for prefix in self.PROTECTED_RESOURCES:
                if request.resource.startswith(prefix):
                    return PolicyDecision.deny(
                        reason=f"protected resource '{request.resource}' matches '{prefix}'",
                        policy_id="protected_resource",
                    )
        return None

    def _check_registered(self, request: PermissionRequest) -> PolicyDecision | None:
        """未知 Capability → Default-Deny。"""
        if request.capability_id not in self.REGISTERED_CAPABILITIES:
            return PolicyDecision.deny(
                reason=f"unregistered capability: {request.capability_id}",
                policy_id="default_deny",
            )
        return None

    def _check_level(self, request: PermissionRequest) -> PolicyDecision | None:
        """Capability 级别不能超过注册级别。"""
        max_level = self.REGISTERED_CAPABILITIES.get(request.capability_id)
        if max_level is not None and request.level > max_level:
            return PolicyDecision.deny(
                reason=f"capability '{request.capability_id}' max level {max_level.name} < "
                       f"requested {request.level.name}",
                policy_id="level_guard",
            )
        return None

    def _check_risk_approval(self, request: PermissionRequest) -> PolicyDecision | None:
        """高风险或写操作需要用户批准。"""
        # HIGH risk → REQUIRE_APPROVAL
        if request.risk_level == RiskLevel.HIGH:
            return PolicyDecision.require_approval(
                reason=f"HIGH risk operation: {request.capability_id}",
                policy_id="high_risk_approval",
            )
        # L2+ 写操作默认需要批准
        if request.level >= PermissionLevel.WRITE:
            return PolicyDecision.require_approval(
                reason=f"write/execute operation requires approval: {request.capability_id}",
                policy_id="write_approval",
            )
        return None
