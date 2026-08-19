"""Phase 22-B — AsyncBridge: 异步→同步桥接 + PermissionGateway 集成。

职责:
  - 接管 Capability 线程生命周期（后台 Event Loop）
  - dispatch() 后第一件事：PermissionGateway.validate(contract)
  - BLOCKED 时抛 PermissionDeniedError
  - 日志记录每次派发
"""

from __future__ import annotations

import asyncio
import threading
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from ocos.capability.permission_gateway import (
    GatewayDecision,
    GatewayResult,
    PermissionDeniedError,
    PermissionGateway,
)
from ocos.logging import get_logger

logger = get_logger(__name__)


# ── DispatchResult ───────────────────────────────────────────────────────────


@dataclass
class DispatchResult:
    """一次派发的结果。"""
    contract_id: str = ""
    success: bool = False
    gateway_result: GatewayResult | None = None
    execution_result: Any = None
    error: str | None = None


# ── AsyncBridge ──────────────────────────────────────────────────────────────


@dataclass
class AsyncBridge:
    """异步 Capability 桥接器 + PermissionGateway 集成。

    用法:
        bridge = AsyncBridge(engine_bridge)
        result = bridge.dispatch(contract)
        if result.gateway_result.blocked:
            # 自动抛异常
            pass
    """

    engine_bridge: Any  # EngineBridge instance
    gateway: PermissionGateway = field(default_factory=PermissionGateway)
    lifecycle: Any = None  # Phase 24-C: AgentLifecycleManager（可选）
    _loop: asyncio.AbstractEventLoop | None = field(default=None, init=False)
    _thread: threading.Thread | None = field(default=None, init=False)
    _running: bool = field(default=False, init=False)

    def dispatch(
        self,
        contract: Any,  # ExecutionContract or dict-like
        context: dict[str, Any] | None = None,
    ) -> DispatchResult:
        """派发执行契约。

        流程: validate(contract) → ALLOWED? → execute → 返回结果
                           → BLOCKED? → PermissionDeniedError

        Args:
            contract: ExecutionContract 或带 agent_id/input_spec 的 dict
            context:  调用上下文

        Returns:
            DispatchResult
        """
        contract_id = getattr(contract, "contract_id", "unknown")

        # 1. PermissionGateway 验证
        gateway_result = self.gateway.validate(contract, context)
        if gateway_result.blocked:
            logger.warning(
                f"AsyncBridge: BLOCKED contract={contract_id}: "
                f"{gateway_result.violations}"
            )
            raise PermissionDeniedError(gateway_result)

        # 2. 提取执行参数
        agent_id = getattr(contract, "agent_id", "")
        input_spec = getattr(contract, "input_spec", {}) or {}

        # 3. 通过 EngineBridge 执行
        engine_name = agent_id
        if not engine_name:
            return DispatchResult(
                contract_id=contract_id,
                success=False,
                gateway_result=gateway_result,
                error="No agent_id/engine_name in contract",
            )

        try:
            # Phase 24-C: 生命周期管理
            lc = self.lifecycle
            handle = None
            if lc is not None:
                handle = lc.ensure_registered(engine_name)
                lc.transition(engine_name, "connecting")
                lc.transition(engine_name, "connected")
                lc.transition(engine_name, "ready")
                lc.transition(engine_name, "executing")

            # 传递字符串值以避免跨包导入 ProcessType
            result = self.engine_bridge.execute(
                engine_name=engine_name,
                process_type="planning",
                operation="execute",
                inputs=input_spec,
            )

            if lc is not None and handle is not None:
                handle.execution_count += 1
                handle.last_execution = __import__("datetime").datetime.now(
                    __import__("datetime").timezone.utc
                )
                lc.transition(engine_name, "idle")

            success = bool(result.get("success", False))
            logger.info(
                f"AsyncBridge: dispatched {contract_id} → "
                f"engine={engine_name} success={success}"
            )

            return DispatchResult(
                contract_id=contract_id,
                success=success,
                gateway_result=gateway_result,
                execution_result=result,
            )
        except Exception as e:
            if lc is not None:
                lc.transition(engine_name, "degraded")
            logger.error(f"AsyncBridge: dispatch failed for {contract_id}: {e}")
            return DispatchResult(
                contract_id=contract_id,
                success=False,
                gateway_result=gateway_result,
                error=str(e),
            )

    def start_background(self) -> None:
        """启动后台 Event Loop（在独立线程中运行）。"""
        if self._running:
            return
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(
            target=self._run_loop,
            name="ocos-capability-bridge",
            daemon=True,
        )
        self._running = True
        self._thread.start()
        logger.info("AsyncBridge: background loop started")

    def _run_loop(self) -> None:
        """后台线程的主循环。"""
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    def stop(self) -> None:
        """停止后台 Event Loop。"""
        if self._loop and self._running:
            self._loop.call_soon_threadsafe(self._loop.stop)
            self._running = False
            logger.info("AsyncBridge: stopped")
