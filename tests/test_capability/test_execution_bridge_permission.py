"""GAP-P0-3: ExecutionBridge 权限检查契约测试。

背景: execution_bridge._check_permission 曾固定 return True（allow-all 占位）。
修复: 注入 PermissionGateway 走 validate(); 无 gateway → fail-closed。
契约:
  1. 无 gateway → execute 返回 PERMISSION_DENIED（fail-closed，无 allow-all 兜底）
  2. 注入 gateway + 普通请求 → 放行（非 PERMISSION_DENIED）
  3. 注入 gateway + 命令注入 payload → PERMISSION_DENIED（网关拦截）
"""

from __future__ import annotations

from ocos.capability import ExecutionBridge, ExecutionRequest, ExecutionStatus
from ocos.capability.permission_gateway import PermissionGateway


def _req(payload: str = "") -> ExecutionRequest:
    return ExecutionRequest(
        request_id="req:perm", capability_id="cap:any",
        input_payload=payload, tick_id=1,
    )


def test_fail_closed_without_gateway() -> None:
    """契约 1: 未注入 gateway 时拒绝，而非 allow-all 兜底。"""
    bridge = ExecutionBridge()  # 无 gateway
    result = bridge.execute(_req())
    assert result.status == ExecutionStatus.PERMISSION_DENIED


def test_gateway_allows_normal_request() -> None:
    """契约 2: 注入 gateway 后普通请求进入执行路径（非 PERMISSION_DENIED）。"""
    bridge = ExecutionBridge(permission_gateway=PermissionGateway())
    result = bridge.execute(_req(payload="generate a report"))
    assert result.status != ExecutionStatus.PERMISSION_DENIED


def test_gateway_blocks_command_injection() -> None:
    """契约 3: 命令注入 payload 被网关拦截 → PERMISSION_DENIED。"""
    bridge = ExecutionBridge(permission_gateway=PermissionGateway())
    result = bridge.execute(_req(payload="run task; rm -rf /"))
    assert result.status == ExecutionStatus.PERMISSION_DENIED


def test_check_permission_true_with_gateway() -> None:
    """契约 4: _check_permission 内部——注入 gateway 时普通请求返回 True。"""
    bridge = ExecutionBridge(permission_gateway=PermissionGateway())
    assert bridge._check_permission(_req(payload="hello")) is True


def test_check_permission_false_without_gateway() -> None:
    """契约 5: _check_permission 内部——无 gateway 返回 False（fail-closed）。"""
    bridge = ExecutionBridge()
    assert bridge._check_permission(_req()) is False
