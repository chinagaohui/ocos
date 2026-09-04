"""OCOS runtime permission 网关测试。

权限网关是 OCOS 免疫屏障，必须满足：
1. 默认拒绝（default-deny）
2. External Agent 只能 OBSERVE
3. 受保护资源不可被写/执行
4. 每次拒绝留下审计记录
"""

import pytest

from ocos.runtime.permission import (
    PermissionGateway,
    PermissionRequest,
    PermissionContext,
    PermissionLevel,
    PolicyDecision,
    DecisionResult,
    Caller,
    RiskLevel,
)
from ocos.runtime.permission.builtin_policies import BuiltinPolicies


class TestDefaultDeny:
    """未注册的 capability 必须被拒绝。"""

    def test_unregistered_capability_denied(self):
        gateway = PermissionGateway()
        request = PermissionRequest(
            capability_id="unknown.op",
            action="op",
            level=PermissionLevel.OBSERVE,
        )
        decision, trace = gateway.evaluate(request)
        assert decision.result == DecisionResult.DENY
        assert decision.policy_id == "default_deny"

    def test_unregistered_with_write_level_still_denied(self):
        gateway = PermissionGateway()
        request = PermissionRequest(
            capability_id="unknown.write",
            action="write",
            level=PermissionLevel.WRITE,
        )
        decision, trace = gateway.evaluate(request)
        assert decision.result == DecisionResult.DENY

    def test_known_safe_capability_allowed(self):
        """已注册的低风险 capability 应被允许（或不需审批）。"""
        gateway = PermissionGateway()
        request = PermissionRequest(
            capability_id="runtime.status",
            action="status",
            level=PermissionLevel.OBSERVE,
        )
        decision, trace = gateway.evaluate(request)
        assert decision.allowed is True


class TestExternalAgentBoundary:
    """External Agent 只能 OBSERVE，不能写/执行。"""

    def test_external_agent_read_blocked(self):
        gateway = PermissionGateway()
        request = PermissionRequest(
            capability_id="memory.query",
            action="query",
            level=PermissionLevel.READ,
            caller=Caller.EXTERNAL_AGENT,
        )
        decision, trace = gateway.evaluate(request)
        assert decision.result == DecisionResult.DENY
        assert decision.policy_id == "external_agent_boundary"

    def test_external_agent_execute_blocked(self):
        gateway = PermissionGateway()
        request = PermissionRequest(
            capability_id="shell.execute",
            action="execute",
            level=PermissionLevel.EXECUTE,
            caller=Caller.EXTERNAL_AGENT,
        )
        decision, trace = gateway.evaluate(request)
        assert decision.result == DecisionResult.DENY
        assert decision.policy_id == "external_agent_boundary"

    def test_external_agent_observe_allowed(self):
        """External Agent 可以 OBSERVE。"""
        gateway = PermissionGateway()
        request = PermissionRequest(
            capability_id="runtime.status",
            action="status",
            level=PermissionLevel.OBSERVE,
            caller=Caller.EXTERNAL_AGENT,
        )
        decision, trace = gateway.evaluate(request)
        # OBSERVE 允许
        assert decision.allowed is True or decision.needs_approval

    def test_ocos_executive_execute_needs_approval(self):
        """OCOS_EXECUTIVE 调用 shell.execute 需要审批（非直接拒绝）。"""
        gateway = PermissionGateway()
        request = PermissionRequest(
            capability_id="shell.execute",
            action="execute",
            level=PermissionLevel.EXECUTE,
            caller=Caller.OCOS_EXECUTIVE,
        )
        decision, trace = gateway.evaluate(request)
        assert decision.needs_approval is True
        assert decision.policy_id == "write_approval"


class TestProtectedResources:
    """OCOS 核心资源禁止外部写入。"""

    def test_write_to_cos_memory_blocked(self):
        gateway = PermissionGateway()
        request = PermissionRequest(
            capability_id="file.write",
            action="write",
            level=PermissionLevel.WRITE,
            resource="ocos.memory.core",
        )
        decision, trace = gateway.evaluate(request)
        assert decision.result == DecisionResult.DENY
        assert decision.policy_id == "protected_resource"

    def test_write_to_cos_goal_blocked(self):
        gateway = PermissionGateway()
        request = PermissionRequest(
            capability_id="file.write",
            action="write",
            level=PermissionLevel.WRITE,
            resource="ocos.goal.tree",
        )
        decision, trace = gateway.evaluate(request)
        assert decision.result == DecisionResult.DENY

    def test_read_to_protected_resource_passes_gates(self):
        """对受保护资源的读操作不触发 protected_resource 拦截。"""
        gateway = PermissionGateway()
        request = PermissionRequest(
            capability_id="memory.query",
            action="query",
            level=PermissionLevel.READ,
            resource="ocos.memory.episode",
        )
        decision, trace = gateway.evaluate(request)
        # READ 不触发 protected_resource（只检查 >= WRITE）
        # 但因未注册 capability，会被 default_deny 拦截
        assert decision.policy_id in ("default_deny", "write_approval", "level_guard")


class TestAuditTrail:
    """每次拒绝必须留下审计记录。"""

    def test_denial_creates_trace(self):
        gateway = PermissionGateway()
        request = PermissionRequest(
            capability_id="unknown",
            action="x",
            level=PermissionLevel.OBSERVE,
        )
        decision, trace = gateway.evaluate(request)
        assert gateway.trace_count == 1
        assert trace.capability_id == "unknown"
        assert trace.decision == DecisionResult.DENY.value

    def test_approval_creates_trace(self):
        """需要审批的操作也产生 trace。"""
        gateway = PermissionGateway()
        request = PermissionRequest(
            capability_id="shell.execute",
            action="exec",
            level=PermissionLevel.EXECUTE,
        )
        decision, trace = gateway.evaluate(request)
        assert gateway.trace_count == 1

    def test_flush_traces(self):
        gateway = PermissionGateway()
        gateway.evaluate(PermissionRequest(
            capability_id="unknown1", action="a", level=PermissionLevel.OBSERVE
        ))
        gateway.evaluate(PermissionRequest(
            capability_id="unknown2", action="b", level=PermissionLevel.OBSERVE
        ))
        assert gateway.trace_count == 2
        traces = gateway.flush_traces()
        assert len(traces) == 2
        assert gateway.trace_count == 0

    def test_last_trace(self):
        gateway = PermissionGateway()
        gateway.evaluate(PermissionRequest(
            capability_id="a", action="a", level=PermissionLevel.OBSERVE
        ))
        gateway.evaluate(PermissionRequest(
            capability_id="b", action="b", level=PermissionLevel.OBSERVE
        ))
        last = gateway.last_trace()
        assert last is not None
        assert last.capability_id == "b"


class TestRiskLevel:
    """高风险操作需要审批。"""

    def test_high_risk_requires_approval(self):
        gateway = PermissionGateway()
        request = PermissionRequest(
            capability_id="runtime.status",  # 已注册
            action="status",
            level=PermissionLevel.OBSERVE,
            risk_level=RiskLevel.HIGH,
        )
        decision, trace = gateway.evaluate(request)
        # HIGH risk 触发 approval，不是 DENY
        assert decision.result == DecisionResult.REQUIRE_APPROVAL
        assert decision.policy_id == "high_risk_approval"

    def test_low_risk_known_capability_allowed(self):
        gateway = PermissionGateway()
        request = PermissionRequest(
            capability_id="runtime.status",
            action="status",
            level=PermissionLevel.OBSERVE,
            risk_level=RiskLevel.LOW,
        )
        decision, trace = gateway.evaluate(request)
        assert decision.allowed is True


class TestTraceConsumer:
    """审计消费链路验证。"""

    def test_consumer_receives_trace(self):
        consumed = []

        class FakeConsumer:
            def consume(self, trace):
                consumed.append(trace)

        gateway = PermissionGateway(trace_consumers=[FakeConsumer()])
        gateway.evaluate(PermissionRequest(
            capability_id="unknown", action="x", level=PermissionLevel.OBSERVE
        ))
        assert len(consumed) == 1
        assert consumed[0].capability_id == "unknown"

    def test_multiple_consumers(self):
        calls = {"a": [], "b": []}

        class ConsumerA:
            def consume(self, trace):
                calls["a"].append(trace)

        class ConsumerB:
            def consume(self, trace):
                calls["b"].append(trace)

        gateway = PermissionGateway(trace_consumers=[ConsumerA(), ConsumerB()])
        gateway.evaluate(PermissionRequest(
            capability_id="x", action="x", level=PermissionLevel.OBSERVE
        ))
        assert len(calls["a"]) == 1
        assert len(calls["b"]) == 1


class TestPermissionRequestValidation:
    """PermissionRequest 自身约束。"""

    def test_empty_capability_id_rejected(self):
        with pytest.raises(ValueError, match="capability_id"):
            PermissionRequest(
                capability_id="", action="x", level=PermissionLevel.OBSERVE
            )

    def test_empty_action_rejected(self):
        with pytest.raises(ValueError, match="action"):
            PermissionRequest(
                capability_id="a.b", action="", level=PermissionLevel.OBSERVE
            )

    def test_frozen_dataclass(self):
        req = PermissionRequest(
            capability_id="x.y", action="do", level=PermissionLevel.READ
        )
        with pytest.raises((TypeError, AttributeError)):
            req.capability_id = "changed"


class TestPermissionLevel:
    """四级权限模型。"""

    def test_level_satisfies(self):
        assert PermissionLevel.EXECUTE.satisfies(PermissionLevel.WRITE)
        assert PermissionLevel.WRITE.satisfies(PermissionLevel.READ)
        assert PermissionLevel.READ.satisfies(PermissionLevel.OBSERVE)
        assert not PermissionLevel.OBSERVE.satisfies(PermissionLevel.READ)

    def test_from_string_case_insensitive(self):
        assert PermissionLevel.from_string("observe") == PermissionLevel.OBSERVE
        assert PermissionLevel.from_string("OBSERVE") == PermissionLevel.OBSERVE
        assert PermissionLevel.from_string("Execute") == PermissionLevel.EXECUTE
        assert PermissionLevel.from_string(" WRITE ") == PermissionLevel.WRITE

    def test_admin_level_not_exist(self):
        """ADMIN 级别不应存在（冻结约束）。"""
        with pytest.raises(KeyError):
            PermissionLevel.from_string("admin")
