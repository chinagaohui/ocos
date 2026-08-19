"""Phase 39.3 Acceptance Tests: R39-301 ~ R39-305.

验证 Capability Policy Enforcement Layer:
    R39-301: Default Deny — 未知 capability → DENY
    R39-302: Protected Operations — 外部 Agent 写 Memory → DENY
    R39-303: Approval Flow — WRITE → REQUIRE_APPROVAL → approved → ALLOW
    R39-304: Audit Trace — 每次决策生成完整 PermissionTrace
    R39-305: Governance Isolation — 策略层不能 import goal/self/memory
"""

from __future__ import annotations

import ast
import json

import pytest

from ocos.runtime.permission import (
    BuiltinPolicies,
    Caller,
    DecisionResult,
    PermissionContext,
    PermissionGateway,
    PermissionLevel,
    PermissionRequest,
    PermissionTrace,
    PolicyDecision,
    RiskLevel,
)
from ocos.runtime.capability_policy import CapabilityPolicyProvider


# ═══════════════════════════════════════════════════════════════════════════
# R39-301: Default Deny
# ═══════════════════════════════════════════════════════════════════════════

class TestR39301DefaultDeny:
    """R39-301: 未知 Capability → DENY，不允许默认通过。"""

    def test_unknown_capability_denied(self):
        policies = BuiltinPolicies()
        request = PermissionRequest(
            capability_id="evil.attack",
            action="hack",
            level=PermissionLevel.EXECUTE,
        )
        decision = policies.evaluate(request)
        assert decision.result == DecisionResult.DENY
        assert decision.policy_id == "default_deny"

    def test_registered_known_capability_allowed(self):
        policies = BuiltinPolicies()
        request = PermissionRequest(
            capability_id="runtime.status",
            action="status",
            level=PermissionLevel.OBSERVE,
        )
        decision = policies.evaluate(request)
        assert decision.result == DecisionResult.ALLOW

    def test_gateway_denies_unknown(self):
        gateway = PermissionGateway()
        request = PermissionRequest(
            capability_id="nonexistent.cap",
            action="do_something",
            level=PermissionLevel.EXECUTE,
        )
        decision, trace = gateway.evaluate(request)
        assert decision.denied
        assert decision.policy_id == "default_deny"
        assert trace is not None
        assert trace.decision == "DENY"

    def test_capability_provider_default_denies_unknown(self):
        """CapabilityPolicyProvider 接入后也 DENY 未知。"""
        provider = CapabilityPolicyProvider()
        result = provider.check("runtime", "unknown.cap", tick_id=42)
        assert result == DecisionResult.DENY


# ═══════════════════════════════════════════════════════════════════════════
# R39-302: Protected Operations
# ═══════════════════════════════════════════════════════════════════════════

class TestR39302ProtectedOperations:
    """R39-302: 外部 Agent 写 Memory → DENY。"""

    def test_external_agent_cannot_write(self):
        policies = BuiltinPolicies()
        request = PermissionRequest(
            capability_id="memory.write",
            action="write",
            resource="ocos.memory.episode",
            caller=Caller.EXTERNAL_AGENT,
            level=PermissionLevel.WRITE,
        )
        decision = policies.evaluate(request)
        assert decision.denied
        assert decision.policy_id == "external_agent_boundary"

    def test_external_agent_can_observe(self):
        """外部 Agent OBSERVE 级别通过。"""
        policies = BuiltinPolicies()
        request = PermissionRequest(
            capability_id="runtime.status",
            action="status",
            caller=Caller.EXTERNAL_AGENT,
            level=PermissionLevel.OBSERVE,
        )
        decision = policies.evaluate(request)
        assert decision.allowed

    def test_protected_resource_write_denied(self):
        """写 OCOS 核心资源被拒绝。"""
        policies = BuiltinPolicies()
        for resource in ["ocos.goal.active", "ocos.self.model", "ocos.memory.episode",
                         "ocos.constitution.v1", "ocos.runtime.kernel.state",
                         "ocos.identity.anchor"]:
            request = PermissionRequest(
                capability_id="file.write",
                action="write",
                resource=resource,
                level=PermissionLevel.WRITE,
            )
            decision = policies.evaluate(request)
            assert decision.denied, f"resource {resource} should be protected"
            assert decision.policy_id == "protected_resource"

    def test_normal_resource_write_requires_approval(self):
        """非保护资源的写操作 → REQUIRE_APPROVAL（非 DENY）。"""
        policies = BuiltinPolicies()
        request = PermissionRequest(
            capability_id="file.write",
            action="write",
            resource="/tmp/normal.txt",
            level=PermissionLevel.WRITE,
        )
        decision = policies.evaluate(request)
        assert decision.needs_approval
        assert decision.policy_id == "write_approval"


# ═══════════════════════════════════════════════════════════════════════════
# R39-303: Approval Flow
# ═══════════════════════════════════════════════════════════════════════════

class TestR39303ApprovalFlow:
    """R39-303: file_write → REQUIRE_APPROVAL → approved（模拟）。"""

    def test_file_write_requires_approval(self):
        policies = BuiltinPolicies()
        request = PermissionRequest(
            capability_id="file.write",
            action="write",
            resource="/project/a.py",
            level=PermissionLevel.WRITE,
            risk_level=RiskLevel.LOW,
        )
        decision = policies.evaluate(request)
        assert decision.needs_approval

    def test_high_risk_requires_approval(self):
        policies = BuiltinPolicies()
        request = PermissionRequest(
            capability_id="agent.invoke",
            action="invoke",
            risk_level=RiskLevel.HIGH,
            level=PermissionLevel.EXECUTE,
        )
        decision = policies.evaluate(request)
        # 先检查 level_guard: agent.invoke is registered as EXECUTE, request level EXECUTE → pass
        # Then high_risk_approval
        assert decision.needs_approval
        assert decision.policy_id == "high_risk_approval"

    def test_low_risk_observe_no_approval(self):
        """LOW risk + OBSERVE → 直接 ALLOW，不需要批准。"""
        policies = BuiltinPolicies()
        request = PermissionRequest(
            capability_id="runtime.status",
            action="status",
            level=PermissionLevel.OBSERVE,
            risk_level=RiskLevel.LOW,
        )
        decision = policies.evaluate(request)
        assert decision.allowed
        assert decision.policy_id == "default_allow"

    def test_level_exceeded_denied(self):
        """Capability 级别超限 → DENY。"""
        policies = BuiltinPolicies()
        request = PermissionRequest(
            capability_id="runtime.status",  # max: OBSERVE
            action="write",
            level=PermissionLevel.WRITE,  # exceeds OBSERVE
        )
        decision = policies.evaluate(request)
        assert decision.denied
        assert decision.policy_id == "level_guard"


# ═══════════════════════════════════════════════════════════════════════════
# R39-304: Audit Trace
# ═══════════════════════════════════════════════════════════════════════════

class TestR39304AuditTrace:
    """R39-304: 每次 ALLOW/DENY 生成完整 PermissionTrace。"""

    def test_trace_generated_on_allow(self):
        gateway = PermissionGateway()
        request = PermissionRequest(
            capability_id="runtime.status",
            action="status",
            level=PermissionLevel.OBSERVE,
        )
        ctx = PermissionContext(tick_id=42, goal_id="g-1")
        decision, trace = gateway.evaluate(request, ctx)

        assert decision.allowed
        assert trace.tick_id == 42
        assert trace.goal_id == "g-1"
        assert trace.capability_id == "runtime.status"
        assert trace.decision == "ALLOW"
        assert trace.policy_id == "default_allow"

    def test_trace_generated_on_deny(self):
        gateway = PermissionGateway()
        request = PermissionRequest(
            capability_id="evil.attack",
            action="hack",
            level=PermissionLevel.EXECUTE,
        )
        ctx = PermissionContext(tick_id=100)
        decision, trace = gateway.evaluate(request, ctx)

        assert decision.denied
        assert trace.tick_id == 100
        assert trace.decision == "DENY"
        assert trace.policy_id == "default_deny"

    def test_trace_serializable(self):
        """PermissionTrace.to_dict() 可 JSON 序列化。"""
        gateway = PermissionGateway()
        request = PermissionRequest(
            capability_id="file.write",
            action="write",
            resource="/tmp/x",
            level=PermissionLevel.WRITE,
        )
        ctx = PermissionContext(tick_id=99)
        _, trace = gateway.evaluate(request, ctx)

        d = trace.to_dict()
        assert d["tick_id"] == 99
        assert d["capability_id"] == "file.write"
        # JSON round-trip
        s = json.dumps(d)
        back = json.loads(s)
        assert back["trace_id"] == trace.trace_id

    def test_gateway_buffers_traces(self):
        gateway = PermissionGateway()
        for i in range(3):
            request = PermissionRequest(
                capability_id="runtime.status",
                action="status",
                level=PermissionLevel.OBSERVE,
            )
            gateway.evaluate(request, PermissionContext(tick_id=i))

        assert gateway.trace_count == 3
        traces = gateway.flush_traces()
        assert len(traces) == 3
        assert gateway.trace_count == 0  # flushed


# ═══════════════════════════════════════════════════════════════════════════
# R39-305: Governance Isolation
# ═══════════════════════════════════════════════════════════════════════════

class TestR39305GovernanceIsolation:
    """R39-305: 策略层不能 import goal.create / self.modify / memory.write。"""

    FORBIDDEN_CALLS = {
        "goal.create": ("ocos.goal", "goal_store.create"),
        "self.modify": ("ocos.self",),
        "memory.write": ("ocos.memory", "memory.write"),
    }

    def test_builtin_policies_no_forbidden_imports(self):
        """AST: BuiltinPolicies 不导入 forbidden modules。"""
        from pathlib import Path
        perm_dir = Path(__file__).parents[1] / "runtime" / "permission"
        for f in sorted(perm_dir.glob("*.py")):
            if f.name == "__init__.py":
                continue
            tree = ast.parse(f.read_text())
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    if node.module:
                        for label, modules in self.FORBIDDEN_CALLS.items():
                            for mod in modules:
                                if node.module == mod or (
                                    node.module.startswith(mod + ".") if mod else False
                                ):
                                    pytest.fail(
                                        f"{f.name}: forbidden import '{node.module}' "
                                        f"(matched '{mod}' in rule '{label}')"
                                    )

    def test_builtin_policies_no_forbidden_function_calls(self):
        """AST: BuiltinPolicies 不调用 goal.create / self.modify。"""
        from pathlib import Path
        perm_dir = Path(__file__).parents[1] / "runtime" / "permission"
        for f in sorted(perm_dir.glob("*.py")):
            if f.name == "__init__.py":
                continue
            tree = ast.parse(f.read_text())
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Attribute):
                        call_name = f"{self._resolve_name(node.func.value)}.{node.func.attr}"
                        for label in self.FORBIDDEN_CALLS:
                            if label in call_name:
                                pytest.fail(
                                    f"{f.name}: forbidden call '{call_name}' "
                                    f"(matches rule '{label}')"
                                )

    @staticmethod
    def _resolve_name(node) -> str:
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            return f"{TestR39305GovernanceIsolation._resolve_name(node.value)}.{node.attr}"
        return "?"
