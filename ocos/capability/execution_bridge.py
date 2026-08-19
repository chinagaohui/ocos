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

from dataclasses import dataclass, field

from ocos.capability.capability_types import (
    ExecutionRequest, ExecutionStatus, RawResult,
)
from ocos.capability.adapter_manager import AdapterManager


@dataclass
class ExecutionBridge:
    """执行桥——能力调用 → 权限 → 执行 → 结果。"""

    adapter: AdapterManager = field(default_factory=AdapterManager)

    def set_registry(self, registry: object) -> None:
        """共享注册表——使 Bridge 的 Router 与 Selector 使用同一 Registry。"""
        self.adapter.router.set_registry(registry)  # type: ignore

    def execute(self, request: ExecutionRequest) -> RawResult:
        """执行能力调用。

        完整路径:
            1. Permission Check → 如有 Phase 39 PermissionGateway 则检查
            2. Adapter → 统一接口
            3. External Agent → 实际执行
            4. Result → RawResult

        目前无实际 PermissionGateway 注入，默认为允许。
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
        """权限检查——可接入 Phase 39 PermissionGateway。"""
        # 未来接入: from ocos.permission import PermissionGateway
        # 当前默认允许所有注册能力
        return True

    def execute_batch(
        self, requests: list[ExecutionRequest],
    ) -> list[RawResult]:
        """批量执行——顺序执行多个能力调用。"""
        results: list[RawResult] = []
        for req in requests:
            results.append(self.execute(req))
        return results


__all__ = ["ExecutionBridge"]
