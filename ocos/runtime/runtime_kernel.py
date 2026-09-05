"""Phase 39.2: RuntimeKernel — OCOS Resident Runtime (Pipeline-integrated)。

RuntimeKernel 是 OCOS 的心跳引擎。控制 Runtime 生命周期，驱动 Tick Pipeline，
但不拥有认知权限。

Phase 39.2 约束 (Governance Freeze):
    - ❌ 不允许 import: ocos.goal, ocos.agent, ocos.planning, ocos.self
    - ✅ 允许: tick, pipeline, checkpoint, recovery, lifecycle, capability_policy
    - ✅ 允许: ocos.kernel.goal_types (类型定义，非业务逻辑)
    - ✅ Pipeline 编排: 8 阶段固定顺序，每个 Tick 经过完整 Pipeline

接口:
    start() → boot → tick_loop → shutdown
    run()  → async 版本
    stop() → 请求关机

验收标准 (R39-001~005):
    - Runtime BOOT → Runtime ID created → State RUNNING
    - 60 ticks generated (no business behavior)
    - kill → checkpoint.json exists
    - restart → last_tick read → continue from tick+1
    - Governance isolation: no goal/agent imports
"""

from __future__ import annotations

import asyncio
import json
import signal
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

from .capability_policy import CapabilityPolicyProvider
from .checkpoint import CheckpointEngine
from .lifecycle import LifecycleManager
from .pipeline import TickPipeline
from .recovery_engine import RecoveryEngine
from .runtime_state import RuntimeState
from .tick import Tick, tick_id_generator


class RuntimeKernel:
    """OCOS 最小 Resident Runtime — Phase 39.1 心跳引擎。

    用法:
        kernel = RuntimeKernel()
        kernel.start()          # BOOT → RUNNING
        kernel.tick_loop(60)    # 跑 60 个 tick
        kernel.shutdown()       # checkpoint + shutdown

    或:
        kernel = RuntimeKernel()
        asyncio.run(kernel.run(60))
    """

    def __init__(
        self,
        runtime_id: str | None = None,
        checkpoint_dir: str | Path | None = None,
    ):
        # S2.7 (白皮书 P2): 恢复数据（快照/事件/账本/审批）默认落
        # ~/.ocos/recovery/（持久目录），替换原 /tmp/ocos_checkpoints
        # ——/tmp 重启即失，恢复子系统形同虚设。OCOS_RECOVERY_DIR 可覆盖。
        import os as _os
        from pathlib import Path as _Path
        if checkpoint_dir is None:
            checkpoint_dir = _os.environ.get(
                "OCOS_RECOVERY_DIR",
                str(_Path.home() / ".ocos" / "recovery"))
        checkpoint_dir = _Path(checkpoint_dir)
        checkpoint_dir.mkdir(parents=True, exist_ok=True)
        self._runtime_id = runtime_id or str(uuid.uuid4())
        self._checkpoint_engine = CheckpointEngine(checkpoint_dir)
        self._recovery_engine = RecoveryEngine(
            self._checkpoint_engine, self._runtime_id,
            data_dir=checkpoint_dir if checkpoint_dir else Path("ocos_data"),
        )
        self._lifecycle = LifecycleManager()
        self._policy = CapabilityPolicyProvider()
        self._pipeline = TickPipeline()  # 39.2: stage orchestration
        self._tick_gen = None  # initialized after recovery
        self._last_tick_id = 0
        self._tick_count = 0

    # ── agent driver (39.3 / P1-C: 循环收敛) ──

    def attach_agent_driver(self, driver: Optional[Callable[[int], dict[str, Any]]]) -> None:
        """注入 Agent 业务驱动（透传 Pipeline）。

        P1-C 收敛: RuntimeKernel.tick_loop 成为唯一认知循环宿主，
        每 tick 经 driver 驱动 AgentRuntime.tick()。注入式设计保持
        Governance 冻结 — Kernel 不 import ocos.agent（R39-203）。
        """
        self._pipeline.attach_agent_driver(driver)

    @property
    def last_agent_result(self) -> Optional[dict[str, Any]]:
        """最近一次 agent driver 执行结果（未 attach 时为 None）。"""
        return self._pipeline.last_agent_result

    # ── properties ──

    @property
    def runtime_id(self) -> str:
        return self._runtime_id

    @property
    def state(self) -> RuntimeState:
        return self._lifecycle.state

    @property
    def last_tick_id(self) -> int:
        return self._last_tick_id

    @property
    def tick_count(self) -> int:
        return self._tick_count

    # ── lifecycle ──

    def start(self) -> str:
        """启动 Runtime: recovery → boot → RUNNING。

        Returns: runtime_id
        """
        # Phase 39.1 recovery: 检查 checkpoint
        result = self._recovery_engine.attempt_recovery()

        if result.recovered:
            self._last_tick_id = result.last_tick_id

        # Init tick generator (从恢复后的 tick 开始)
        self._tick_gen = tick_id_generator(start=result.next_tick_id)

        # BOOT → RUNNING
        self._lifecycle.boot()

        return self._runtime_id

    def stop(self):
        """请求正常关机。"""
        self._lifecycle.request_shutdown()

    def shutdown(self, checkpoint: bool = True):
        """执行关机: checkpoint → SHUTDOWN。

        Args:
            checkpoint: 是否在关机前创建 checkpoint (默认 True)
        """
        if checkpoint and self._last_tick_id > 0:
            self._recovery_engine.create_checkpoint(
                tick_id=self._last_tick_id,
                state=self._lifecycle.state,
            )

        self._lifecycle.shutdown()

    # ── tick loop ──

    def tick_loop(self, max_ticks: int | None = None, interval: float = 0.0):
        """同步 Tick 循环 (Phase 39.1: 无业务行为)。

        max_ticks 为**本次调用**内执行的 tick 上限（局部计数），
        支持 daemon 每轮 tick_loop(max_ticks=1) 的多次调用模式
        （P1-C 循环收敛：外层节奏由调用方控制）。
        """
        executed = 0
        while self._lifecycle.state == RuntimeState.RUNNING:
            if max_ticks is not None and executed >= max_ticks:
                break

            self._execute_tick()
            executed += 1

            if self._lifecycle.shutdown_requested:
                break

            if interval > 0:
                time.sleep(interval)

    async def run(self, max_ticks: int | None = None, interval: float = 0.0):
        """Async Tick 循环。"""
        self.start()
        try:
            while self._lifecycle.state == RuntimeState.RUNNING:
                if max_ticks is not None and self._tick_count >= max_ticks:
                    break

                self._execute_tick()

                if self._lifecycle.shutdown_requested:
                    break

                if interval > 0:
                    await asyncio.sleep(interval)
        finally:
            self.shutdown()

    def _execute_tick(self) -> Tick:
        """执行单个 tick (39.2: 通过 Pipeline 编排)。

        Pipeline 固定 8 阶段顺序，每个阶段返回新的 TickContext。
        Checkpoint 决策由 Pipeline Stage ⑧ 返回。
        """
        if self._tick_gen is None:
            raise RuntimeError("Runtime not started. Call start() first.")
        tick_id = next(self._tick_gen)

        # 39.2: Pipeline 编排
        ctx = self._pipeline.execute_tick(
            tick_id=tick_id,
            runtime_state=self._lifecycle.state.value,
        )

        tick = Tick(
            tick_id=tick_id,
            timestamp=datetime.now(timezone.utc),
            state=self._lifecycle.state.value,
            checkpoint_id=None,
        )
        self._last_tick_id = tick_id
        self._tick_count += 1

        # 39.2: Pipeline 决定 checkpoint
        if ctx.checkpoint_decision:
            record = self._recovery_engine.create_checkpoint(
                tick_id=tick_id,
                state=self._lifecycle.state,
            )
            object.__setattr__(tick, "checkpoint_id", str(record.tick_id))

        return tick
