"""Phase 45: CapabilityRouter — 能力路由器。

将执行请求路由到正确的 Adapter。

输入: ExecutionRequest
输出: 路由到 Adapter → Permission → External Agent
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ocos.capability.capability_types import (
    Capability, ExecutorKind, ExecutionRequest, ExecutionStatus, RawResult,
)
from ocos.capability.capability_registry import CapabilityRegistry


@dataclass
class CapabilityRouter:
    """能力路由器。

    根据 Capability 的 executor_kind 路由到对应 Adapter。
    """

    registry: CapabilityRegistry = field(default_factory=CapabilityRegistry)

    # 执行回调注册表：executor_kind → callable
    _adapters: dict[str, object] = field(default_factory=dict)

    def set_registry(self, registry: CapabilityRegistry) -> None:
        """共享注册表——使 Router 与 Selector 使用同一 Registry。"""
        self.registry = registry

    def register_adapter(self, kind: ExecutorKind, adapter_fn: object) -> None:
        """注册一个执行适配器。"""
        self._adapters[kind.value] = adapter_fn

    def route(self, request: ExecutionRequest) -> RawResult:
        """路由执行请求到适配器 → 返回原始结果。"""

        cap = self.registry.get(request.capability_id)
        if cap is None:
            return RawResult(
                request_id=request.request_id,
                capability_id=request.capability_id,
                status=ExecutionStatus.CAPABILITY_UNAVAILABLE,
                error_message=f"Capability not found: {request.capability_id}",
                tick_id=request.tick_id,
            )

        if not cap.is_callable:
            return RawResult(
                request_id=request.request_id,
                capability_id=request.capability_id,
                status=ExecutionStatus.CAPABILITY_UNAVAILABLE,
                error_message=f"Capability not callable: {cap.state.value}",
                tick_id=request.tick_id,
            )

        kind = cap.executor_kind.value
        adapter = self._adapters.get(kind)

        if adapter is None:
            # 无适配器时的模拟执行（开发/测试中）
            return self._default_route(request, cap)
        # 实际适配器调用
        result = adapter(request)  # type: ignore
        return result  # type: ignore

    def _default_route(
        self, request: ExecutionRequest, cap: Capability,
    ) -> RawResult:
        """默认路由——模拟执行结果。"""
        return RawResult(
            request_id=request.request_id,
            capability_id=request.capability_id,
            raw_output=f"[{cap.name}] executed: {request.input_payload[:200]}",
            status=ExecutionStatus.SUCCESS,
            tick_id=request.tick_id,
        )


__all__ = ["CapabilityRouter"]
