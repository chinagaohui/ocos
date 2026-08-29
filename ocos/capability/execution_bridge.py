"""Phase 45: ExecutionBridge — 执行桥。

连接 Capability Router → Permission Gateway → External Agent。

负责:
    - 权限检查（接入 Phase 39 PermissionGateway）
    - 执行调度
    - 超时控制
    - 错误处理

核心链路:
    Router → Permission Check → Adapter → Agent → Result
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

from ocos.capability.capability_types import (
    ExecutionRequest, ExecutionStatus, RawResult,
)
from ocos.capability.adapter_manager import AdapterManager
from ocos.capability.permission_gateway import (
    CallerIdentity, PermissionGateway,
)

logger = logging.getLogger("ocos.capability.execution_bridge")


@dataclass(frozen=True)
class _BridgeContract:
    """ExecutionRequest → PermissionGateway 兼容视图（桥内私有适配，不改 gateway）。"""

    contract_id: str
    agent_id: str
    action: str
    input_spec: dict


@dataclass
class ExecutionBridge:
    """执行桥——能力调用 → 权限 → 执行 → 结果。"""

    adapter: AdapterManager = field(default_factory=AdapterManager)
    permission_gateway: Optional[PermissionGateway] = None  # GAP-P0-3: 缺省 fail-closed

    def set_registry(self, registry: object) -> None:
        """共享注册表——使 Bridge 的 Router 与 Selector 使用同一 Registry。"""
        self.adapter.router.set_registry(registry)  # type: ignore

    def execute(self, request: ExecutionRequest) -> RawResult:
        """执行能力调用。

        完整路径:
            1. Permission Check → PermissionGateway.validate（缺 gateway 时 fail-closed）
            2. Adapter → 统一接口
            3. External Agent → 实际执行
            4. Result → RawResult
        """
        # Step 1: Permission check
        if not self._check_permission(request):
            return RawResult(
                request_id=request.request_id,
                capability_id=request.capability_id,
                status=ExecutionStatus.PERMISSION_DENIED,
                error_message="Permission denied",
                tick_id=request.tick_id,
            )

        # Step 2+3: Adapter → External Agent
        try:
            result = self.adapter.execute(request)
            return result
        except Exception as e:
            return RawResult(
                request_id=request.request_id,
                capability_id=request.capability_id,
                status=ExecutionStatus.FAILURE,
                error_message=str(e),
                tick_id=request.tick_id,
            )

    def _check_permission(self, request: ExecutionRequest) -> bool:
        """权限检查——GAP-P0-3: 接入 PermissionGateway.validate。

        无 gateway 配置 → fail-closed（拒绝 + 审计日志），不保留 allow-all 兜底。
        """
        if self.permission_gateway is None:
            logger.warning(
                "ExecutionBridge fail-closed: no permission_gateway configured "
                "(request_id=%s capability_id=%s)",
                request.request_id, request.capability_id,
            )
            return False
        contract = _BridgeContract(
            contract_id=request.request_id,
            agent_id=request.capability_id,
            action=request.capability_id,
            input_spec={
                "payload": request.input_payload,
                "context": request.context,
            },
        )
        result = self.permission_gateway.validate(
            contract,
            caller=CallerIdentity(
                caller_id="ocos.execution_bridge", source="internal",
            ),
        )
        return result.allowed

    def execute_batch(
        self, requests: list[ExecutionRequest],
    ) -> list[RawResult]:
        """批量执行——顺序执行多个能力调用。"""
        results: list[RawResult] = []
        for req in requests:
            results.append(self.execute(req))
        return results


__all__ = ["ExecutionBridge"]
