"""
PlanningEngine — 规划能力引擎。

Phase 19 Capability Engines 的第二个能力引擎。

职责:
1. 执行规划操作（TOP_DOWN, BOTTOM_UP, MEANS_END, CASE_BASED 等）
2. 将 Goal 分解为有序的 PlanningStep
3. 产生 PlanningTrace 记录
4. 输出规划步骤到 output_addresses
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Callable

from ocos.kernel.abi import Event, EventType
from ocos.events.event_bus import EventBus
from ocos.models.process import TransformProcess, ProcessType
from ocos.models.planning import (
    PlanningStrategy,
    PlanStatus,
    PlanningStep,
    PlanningTrace,
)
from ocos.runtime.context_manager import WorkingMemory

from ocos.logging import get_logger

_SOURCE = "planning_engine"

logger = get_logger(__name__)


class RuntimeResult:
    """规划引擎的通用结果类。"""
    def __init__(
        self,
        success: bool,
        message: str,
        trace_id: str = "",
        process_id: str = "",
        step_count: int = 0,
        output_addresses: tuple[str, ...] = (),
    ):
        self.success = success
        self.message = message
        self.trace_id = trace_id
        self.process_id = process_id
        self.step_count = step_count
        self.output_addresses = output_addresses

    def __repr__(self) -> str:
        return (
            f"RuntimeResult(success={self.success}, trace_id={self.trace_id!r}, "
            f"process_id={self.process_id!r}, steps={self.step_count})"
        )


# ── 规划策略注册表 ──────────────────────────────────────────────────────────

_STRATEGY_HANDLERS: dict[PlanningStrategy, Callable] = {}


def register_planning_strategy(
    strategy: PlanningStrategy,
    handler: Callable[[list[str], dict[str, Any]], list[PlanningStep]],
) -> None:
    """注册自定义规划策略处理器。"""
    _STRATEGY_HANDLERS[strategy] = handler


# ═══════════════════════════════════════════════════════════════════════════════
# PlanningEngine
# ═══════════════════════════════════════════════════════════════════════════════

class PlanningEngine:
    """规划引擎 — 为 ProcessType.PLANNING 提供规划能力。"""

    def __init__(
        self,
        event_bus: EventBus,
        working_memory: WorkingMemory,
    ) -> None:
        self._event_bus = event_bus
        self._wm = working_memory
        self._traces: dict[str, PlanningTrace] = {}
        logger.debug("__init__ completed", component="planning_engine")

    def __repr__(self) -> str:
        return f"PlanningEngine(traces={len(self._traces)})"

    # ── 公共 API ─────────────────────────────────────────────────────────

    def execute(
        self,
        process: TransformProcess,
        strategy: str | None = None,
        inputs: dict[str, Any] | None = None,
    ) -> RuntimeResult:
        """基于 TransformProcess 执行规划。

        Args:
            process: 待执行的 PLANNING Process
            strategy: 规划策略（覆盖默认）
            inputs: 输入数据（Goal 描述、约束等）

        Returns:
            RuntimeResult 包含 trace_id 和输出地址
        """
        logger.info("execute planning", extra=dict(
            process_id=process.process_id, strategy=strategy,
        ))
        if process.process_type != ProcessType.PLANNING.value:
            return RuntimeResult(
                success=False,
                message=f"Not a PLANNING process: {process.process_type}",
                process_id=process.process_id,
            )

        # 确定规划策略
        strat = self._resolve_strategy(process, strategy)
        input_addrs = list(process.input_addresses)
        goal_addr = str(input_addrs[0]) if input_addrs else ""

        # 执行规划
        steps, total_effort, errors = self._execute_strategy(
            strat=strat,
            process=process,
            inputs=inputs,
        )

        # 输出地址
        output_addrs = [f"addr:plan:{uuid.uuid4().hex}" for _ in range(len(steps))]

        # 创建 trace
        trace = PlanningTrace(
            process_id=process.process_id,
            strategy=strat,
            steps=tuple(steps),
            total_effort=total_effort,
            goal_address=goal_addr,
            input_addresses=tuple(str(a) for a in input_addrs),
            output_addresses=tuple(output_addrs),
            error="; ".join(errors) if errors else "",
        )
        self._traces[trace.trace_id] = trace

        self._event_bus.publish(Event(
            event_type=EventType.INFORMATION_TRANSFORMATION_STARTED,
            payload={
                "process_id": process.process_id,
                "process_type": ProcessType.PLANNING.value,
                "input_addresses": list(input_addrs),
                "trace_id": trace.trace_id,
                "strategy": strat.value,
                "step_count": len(steps),
            },
            source=_SOURCE,
        ))

        return RuntimeResult(
            success=not errors,
            message=f"Planning complete: {len(steps)} steps with {strat.value} strategy"
                     + (f", errors: {errors}" if errors else ""),
            trace_id=trace.trace_id,
            process_id=process.process_id,
            step_count=len(steps),
            output_addresses=tuple(output_addrs),
        )

    def get_trace(self, trace_id: str) -> PlanningTrace | None:
        """获取规划轨迹。"""
        return self._traces.get(trace_id)

    def list_traces(self) -> list[PlanningTrace]:
        """列出所有规划轨迹。"""
        return list(self._traces.values())

    def clear_traces(self) -> None:
        """清空规划轨迹。"""
        self._traces.clear()

    # ── 内部方法 ─────────────────────────────────────────────────────────

    def _resolve_strategy(
        self,
        process: TransformProcess,
        override: str | None,
    ) -> PlanningStrategy:
        """确定规划策略。"""
        if override:
            return PlanningStrategy(override)
        if process.metadata and "strategy" in process.metadata:
            try:
                return PlanningStrategy(process.metadata["strategy"])
            except ValueError:
                pass
        return PlanningStrategy.TOP_DOWN

    def _execute_strategy(
        self,
        strat: PlanningStrategy,
        process: TransformProcess,
        inputs: dict[str, Any] | None,
    ) -> tuple[list[PlanningStep], int, list[str]]:
        """执行规划策略，返回 (steps, total_effort, errors)。"""
        # 检查自定义处理器
        if strat in _STRATEGY_HANDLERS:
            handler = _STRATEGY_HANDLERS[strat]
            try:
                steps = handler(
                    list(process.input_addresses),
                    inputs or {},
                )
                total_effort = sum(s.estimated_effort for s in steps)
                return steps, total_effort, []
            except Exception as e:
                return [], 0, [str(e)]

        # 内置规划策略
        return self._default_plan(strat, process, inputs)

    def _default_plan(
        self,
        strat: PlanningStrategy,
        process: TransformProcess,
        inputs: dict[str, Any] | None,
    ) -> tuple[list[PlanningStep], int, list[str]]:
        """默认规划逻辑。"""
        goal_desc = inputs.get("goal", "") if inputs else ""
        n_steps = {
            PlanningStrategy.TOP_DOWN: 4,
            PlanningStrategy.BOTTOM_UP: 3,
            PlanningStrategy.MEANS_END: 5,
            PlanningStrategy.CASE_BASED: 3,
            PlanningStrategy.ITERATIVE: 3,
            PlanningStrategy.PARALLEL: 4,
        }.get(strat, 3)

        steps: list[PlanningStep] = []
        for i in range(n_steps):
            steps.append(PlanningStep(
                description=f"[{strat.value}] Step {i+1}" + (f": {goal_desc}" if goal_desc else ""),
                depends_on=tuple(steps[j].step_id for j in range(i) if j < i),
                estimated_effort=(i + 1) * 10,
                status=PlanStatus.DRAFT,
            ))

        total_effort = sum(s.estimated_effort for s in steps)
        return steps, total_effort, []

# ── Engine Manifest ──────────────────────────────────────────────────────────
from ocos.platform.engine_manifest import EngineManifest

__manifest__ = EngineManifest(
    engine_id="planning_engine",
    name="Planning Engine",
    version="1.0.0",
    engine_class="ocos.engines.planning_engine.PlanningEngine",
    capabilities=['planning'],
    dependencies=[],
    singleton=True,
    auto_load=True,
)
