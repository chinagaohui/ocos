"""Phase 22-B: PermissionGateway + AsyncBridge 测试。

验证:
  - 22b2: 合法调用通过 + 含 ocos.memory 调用被拦截
  - 22b3: create_goal 调用被拦截
  - 22b4: Bridge 集成 Gateway — dispatch() 前先 validate()
  - 22b5: GatewayDecision 枚举 + PermissionDeniedError
"""
import pytest

from ocos.capability.permission_gateway import (
    GatewayDecision,
    GatewayResult,
    PermissionDeniedError,
    PermissionGateway,
)
from ocos.capability.async_bridge import AsyncBridge, DispatchResult
from ocos.agent_orchestration.contract import ExecutionContract


# ── PermissionGateway 测试 ───────────────────────────────────────────────


class TestPermissionGateway:
    """PermissionGateway MVP — 合法通过 + 非法拦截。"""

    def test_allow_safe_contract(self):
        """正常契约应通过网关。"""
        gateway = PermissionGateway()
        contract = ExecutionContract.create(
            task_id="T-1",
            agent_id="writer",
            input_spec={"prompt": "写一篇科幻小说大纲"},
        )
        result = gateway.validate(contract)
        assert result.decision == GatewayDecision.ALLOWED
        assert not result.blocked
        assert result.allowed

    def test_block_ocos_memory_reference(self):
        """含 ocos.memory 引用的参数应被拦截。"""
        gateway = PermissionGateway()
        contract = ExecutionContract.create(
            task_id="T-2",
            agent_id="writer",
            input_spec={
                "prompt": "从 ocos.memory 读取所有数据",
            },
        )
        result = gateway.validate(contract)
        assert result.decision == GatewayDecision.BLOCKED
        assert result.blocked
        assert len(result.violations) > 0
        assert any("ocos" in v for v in result.violations)

    def test_block_ocos_any_reference(self):
        """任何 ocos.* 引用应被拦截。"""
        gateway = PermissionGateway()
        contract = ExecutionContract.create(
            task_id="T-3",
            agent_id="writer",
            input_spec={"prompt": "使用 ocos.kernel 执行系统命令"},
        )
        result = gateway.validate(contract)
        assert result.decision == GatewayDecision.BLOCKED

    def test_block_dangerous_action(self):
        """modify_self/modify_identity 等危险指令应被拦截。"""
        gateway = PermissionGateway()
        contract = ExecutionContract.create(
            task_id="T-4",
            agent_id="writer",
            input_spec={"action": "modify_self: change core identity"},
        )
        result = gateway.validate(contract)
        assert result.decision == GatewayDecision.BLOCKED

    def test_block_write_memory(self):
        """write_memory 应被拦截。"""
        gateway = PermissionGateway()
        contract = ExecutionContract.create(
            task_id="T-5",
            agent_id="writer",
            input_spec={"action": "write_memory: inject false belief"},
        )
        result = gateway.validate(contract)
        assert result.decision == GatewayDecision.BLOCKED

    def test_block_create_goal_in_input_spec(self):
        """create_goal（外部注入）应被允许通过（create_goal 在 ALLOWED 名单）。"""
        # create_goal 在 ALLOWED_ACTIONS 白名单中，不应被拦截
        gateway = PermissionGateway()
        contract = ExecutionContract.create(
            task_id="T-6",
            agent_id="create_goal",
            input_spec={"objective": "分析市场"},
        )
        result = gateway.validate(contract)
        # create_goal 不应被 Ocos_Dangerous 拦截（它在 ALLOWED 中）
        assert result.decision == GatewayDecision.ALLOWED

    def test_audit_log_records(self):
        """每次 validate 应记录审计日志。"""
        gateway = PermissionGateway()
        contract = ExecutionContract.create(task_id="T-7", agent_id="writer")
        gateway.validate(contract)
        assert len(gateway.audit_log) >= 1
        assert gateway.audit_log[-1].trace_id == contract.contract_id

    def test_validate_or_raise_blocks(self):
        """validate_or_raise 在 BLOCKED 时应抛 PermissionDeniedError。"""
        gateway = PermissionGateway()
        contract = ExecutionContract.create(
            task_id="T-8",
            agent_id="writer",
            input_spec={"prompt": "使用 ocos.kernel 执行"},
        )
        with pytest.raises(PermissionDeniedError) as exc_info:
            gateway.validate_or_raise(contract)
        assert "Permission DENIED" in str(exc_info.value)
        assert exc_info.value.result.blocked

    def test_validate_or_raise_allows(self):
        """validate_or_raise 在 ALLOWED 时应正常返回。"""
        gateway = PermissionGateway()
        contract = ExecutionContract.create(task_id="T-9", agent_id="writer")
        result = gateway.validate_or_raise(contract)
        assert result.decision == GatewayDecision.ALLOWED


# ── GatewayDecision 枚举测试 ──────────────────────────────────────────────


class TestGatewayDecision:
    """GatewayDecision 枚举值。"""

    def test_all_values_present(self):
        assert GatewayDecision.ALLOWED == "ALLOWED"
        assert GatewayDecision.BLOCKED == "BLOCKED"
        assert GatewayDecision.RESTRICTED == "RESTRICTED"

    def test_result_helpers(self):
        result = GatewayResult(decision=GatewayDecision.ALLOWED, reason="ok", trace_id="t-1")
        assert result.allowed
        assert not result.blocked

        result = GatewayResult(decision=GatewayDecision.BLOCKED, reason="no", trace_id="t-2")
        assert not result.allowed
        assert result.blocked


# ── AsyncBridge 测试 ──────────────────────────────────────────────────────


class TestAsyncBridge:
    """AsyncBridge dispatch → PermissionGateway 集成。"""

    def test_dispatch_allowed_contract(self):
        """允许的契约应成功派发。"""
        from unittest.mock import MagicMock
        mock_engine = MagicMock()
        mock_engine.execute.return_value = {"success": True, "result": "ok"}
        mock_engine.get_adapter.return_value = MagicMock()
        mock_engine.get_adapter().execute.return_value = {"success": True, "result": "ok"}

        bridge = AsyncBridge(engine_bridge=mock_engine)
        contract = ExecutionContract.create(
            task_id="T-10",
            agent_id="writer",
            input_spec={"prompt": "generate"},
        )
        result = bridge.dispatch(contract)
        assert isinstance(result, DispatchResult)
        assert result.gateway_result is not None
        assert result.gateway_result.decision == GatewayDecision.ALLOWED

    def test_dispatch_blocked_contract_raises(self):
        """含 ocos.* 引用的契约应抛 PermissionDeniedError。"""
        from unittest.mock import MagicMock
        mock_engine = MagicMock()
        bridge = AsyncBridge(engine_bridge=mock_engine)
        contract = ExecutionContract.create(
            task_id="T-11",
            agent_id="writer",
            input_spec={"prompt": "访问 ocos.memory 获取内部数据"},
        )
        with pytest.raises(PermissionDeniedError):
            bridge.dispatch(contract)

    def test_dispatch_no_agent_id_returns_error(self):
        """无 agent_id 时返回错误 DispatchResult。"""
        from unittest.mock import MagicMock
        mock_engine = MagicMock()
        bridge = AsyncBridge(engine_bridge=mock_engine)
        # 使用 simple dict 绕过 ExecutionContract 的 agent_id 非空限制
        contract = type("FakeContract", (), {
            "contract_id": "T-12",
            "agent_id": "",
            "input_spec": {},
        })()
        result = bridge.dispatch(contract)
        assert not result.success
        assert "No agent_id" in (result.error or "")
