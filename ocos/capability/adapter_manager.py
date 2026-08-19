"""Phase 45: AdapterManager — 适配器管理器。

统一不同外部能力接口到 OCOS ABI。

例如:
    Codex API → Capability ABI → OCOS
    OpenClaw API → Capability ABI → OCOS
    HTTP Service → Capability ABI → OCOS

边界 CNS45-03: 外部 Agent 是能力提供者，不是认知主体。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ocos.capability.capability_types import (
    Capability, ExecutorKind, ExecutionRequest, ExecutionStatus, RawResult,
)
from ocos.capability.capability_router import CapabilityRouter


@dataclass
class AdapterManager:
    """适配器管理器。

    为每种 ExecutorKind 提供标准化适配器。

    OCOS ABI (统一调用接口):
        Input:  ExecutionRequest
        Output: RawResult
    """

    router: CapabilityRouter = field(default_factory=CapabilityRouter)

    def register_all_default(self) -> None:
        """注册所有默认适配器。"""
        self.router.register_adapter(
            ExecutorKind.EXTERNAL_AGENT, self._external_agent_adapter,
        )
        self.router.register_adapter(
            ExecutorKind.HTTP_SERVICE, self._http_adapter,
        )
        self.router.register_adapter(
            ExecutorKind.LOCAL_FUNCTION, self._local_adapter,
        )
        self.router.register_adapter(
            ExecutorKind.SUBPROCESS, self._local_adapter,
        )

    @staticmethod
    def _external_agent_adapter(request: ExecutionRequest) -> RawResult:
        """外部 Agent 适配器——将请求转为外部调用。

        注意 CNS45-03: 外部 Agent 永远是 Capability Provider，不是认知主体。
        """
        # 实际生产中此处调用 Codex/OpenClaw/OpenTale API
        return RawResult(
            request_id=request.request_id,
            capability_id=request.capability_id,
            raw_output=f"[Agent] response to: {request.input_payload[:200]}",
            status=ExecutionStatus.SUCCESS,
        )

    @staticmethod
    def _http_adapter(request: ExecutionRequest) -> RawResult:
        """HTTP API 适配器。"""
        return RawResult(
            request_id=request.request_id,
            capability_id=request.capability_id,
            raw_output=f"[HTTP] response to: {request.input_payload[:200]}",
            status=ExecutionStatus.SUCCESS,
        )

    @staticmethod
    def _local_adapter(request: ExecutionRequest) -> RawResult:
        """本地函数/子进程适配器。"""
        return RawResult(
            request_id=request.request_id,
            capability_id=request.capability_id,
            raw_output=f"[Local] executed: {request.input_payload[:200]}",
            status=ExecutionStatus.SUCCESS,
        )

    def execute(self, request: ExecutionRequest) -> RawResult:
        """通过适配器执行能力调用。"""
        return self.router.route(request)


__all__ = ["AdapterManager"]
