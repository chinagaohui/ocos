"""
SimulationEngine — 模拟能力引擎。

Phase 19 — 第六个能力引擎。

职责:
1. 接收 SimulationScenario 和步进函数 step_fn
2. 按策略向前推进模拟
3. 记录每一步的状态和增量
4. 产生 SimulationTrace

run() 使用领域无关的 step_fn(state, params, step_num) → delta
使用者注入模拟逻辑，引擎负责框架执行。
"""

from __future__ import annotations

import uuid
from typing import Any, Callable

from ocos.events.event_bus import EventBus
from ocos.kernel.abi import Event, EventType
from ocos.runtime.context_manager import WorkingMemory
from ocos.models.simulation import (
    SimulationStrategy,
    SimulationScenario,
    SimulationStep,
    SimulationTrace,
)
from ocos.models.process import TransformProcess, ProcessType

from ocos.logging import get_logger

logger = get_logger(__name__)

# 步进函数签名: (current_state, params, step_number) → delta
StepFn = Callable[[dict[str, Any], dict[str, Any], int], dict[str, Any]]


class RuntimeResult:
    """模拟引擎的通用结果类。"""
    def __init__(
        self,
        success: bool,
        message: str,
        trace_id: str = "",
        process_id: str = "",
    ):
        self.success = success
        self.message = message
        self.trace_id = trace_id
        self.process_id = process_id

    def __repr__(self) -> str:
        return (f"RuntimeResult(success={self.success}, "
                f"process_id={self.process_id!r}, message={self.message!r})")


class SimulationEngine:
    """模拟引擎——领域无关的情景推演。"""

    def __init__(
        self,
        event_bus: EventBus,
        working_memory: WorkingMemory,
    ):
        self._event_bus = event_bus
        self._working_memory = working_memory
        self._traces: dict[str, SimulationTrace] = {}
        logger.debug("__init__ completed", component="simulation_engine")

    # ── 核心模拟 ──────────────────────────────────────────────────────

    def run(
        self,
        scenario: SimulationScenario,
        step_fn: StepFn,
        context: dict[str, Any] | None = None,
    ) -> SimulationTrace:
        """执行模拟，返回完整轨迹。"""
        logger.info("run simulation", extra=dict(
            scenario_id=scenario.scenario_id, steps=scenario.steps,
        ))
        state = dict(scenario.initial_state)
        steps: list[SimulationStep] = []
        params = scenario.parameters

        for i in range(1, scenario.steps + 1):
            delta = step_fn(state, params, i)
            step = SimulationStep(
                step_number=i,
                state=dict(state),
                delta=dict(delta),
            )
            steps.append(step)
            # 应用 delta 推进状态
            state.update(delta)

        trace = SimulationTrace(
            trace_id=str(uuid.uuid4()),
            scenario_id=scenario.scenario_id,
            strategy=scenario.strategy,
            steps=tuple(steps),
            initial_state=dict(scenario.initial_state),
            parameters=dict(scenario.parameters),
            final_state=dict(state),
            summary=f"{scenario.strategy.value}: {scenario.steps} steps, "
                    f"final_state_keys={list(state.keys())}",
        )
        self._traces[trace.trace_id] = trace
        return trace

    # ── 多轮蒙特卡洛（L1 真实化: 真参数扰动）───────────────────────────

    def run_monte_carlo(
        self,
        base_scenario: SimulationScenario,
        step_fn: StepFn,
        num_runs: int = 5,
        context: dict[str, Any] | None = None,
        perturbation: dict[str, float] | None = None,
        seed: int | None = None,
    ) -> list[SimulationTrace]:
        """多次运行模拟（蒙特卡洛），每轮对数值参数做真实随机扰动。

        Args:
            perturbation: 参数名 → 相对扰动幅度（如 0.1 = ±10%）；
                          缺省对所有数值型参数施加 ±10% 扰动。
            seed: 随机种子（第 i 轮使用 seed+i），保证可复现。
        Returns:
            num_runs 条轨迹，每条 trace.parameters 为该轮扰动后的真实参数。
        """
        import random

        traces: list[SimulationTrace] = []
        default_jitter = 0.1
        for run_idx in range(num_runs):
            rng = random.Random(seed + run_idx if seed is not None else None)
            params = dict(base_scenario.parameters)
            for key, value in params.items():
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    jitter = (perturbation or {}).get(key, default_jitter)
                    params[key] = type(value)(
                        value * (1.0 + rng.uniform(-jitter, jitter)))
            scenario = dataclasses_replace(
                base_scenario,
                scenario_id=str(uuid.uuid4()),
                parameters=params,
            )
            trace = self.run(scenario, step_fn, context)
            traces.append(trace)
        return traces

    @staticmethod
    def aggregate_final_states(
        traces: list[SimulationTrace],
    ) -> dict[str, dict[str, float]]:
        """聚合多次运行的终态数值字段（mean/std/min/max）。

        仅聚合所有轮次均出现且均为数值的键。
        """
        import math

        stats: dict[str, dict[str, float]] = {}
        if not traces:
            return stats
        common_keys = set(traces[0].final_state)
        for t in traces[1:]:
            common_keys &= set(t.final_state)
        for key in sorted(common_keys):
            values = [
                t.final_state[key] for t in traces
                if isinstance(t.final_state[key], (int, float))
                and not isinstance(t.final_state[key], bool)
            ]
            if len(values) != len(traces):
                continue  # 存在非数值终态，不聚合该键
            mean = sum(values) / len(values)
            variance = sum((v - mean) ** 2 for v in values) / len(values)
            stats[key] = {
                "mean": round(mean, 6),
                "std": round(math.sqrt(variance), 6),
                "min": min(values),
                "max": max(values),
            }
        return stats

    # ── 执行接口 ──────────────────────────────────────────────────────

    def execute(
        self,
        process: TransformProcess,
        context: dict[str, Any] | None = None,
    ) -> RuntimeResult:
        """通过 ProcessRuntimeEngine 执行模拟。"""
        logger.info("execute simulation", extra=dict(
            process_id=process.process_id,
        ))
        if process.process_type != ProcessType.SIMULATION.value:
            return RuntimeResult(
                success=False,
                process_id=process.process_id,
                trace_id="",
                message="Not a SIMULATION process",
            )

        scenario: SimulationScenario | None = (context or {}).get("scenario")
        step_fn: StepFn | None = (context or {}).get("step_fn")

        if scenario is None:
            return RuntimeResult(
                success=False,
                process_id=process.process_id,
                trace_id="",
                message="No scenario provided",
            )
        if step_fn is None:
            return RuntimeResult(
                success=False,
                process_id=process.process_id,
                trace_id="",
                message="No step_fn provided",
            )

        self._event_bus.publish(Event(
            event_type=EventType.INFORMATION_TRANSFORMATION_STARTED,
            payload={
                "process_id": process.process_id,
                "scenario_id": scenario.scenario_id,
                "strategy": scenario.strategy.value,
                "source": "simulation",
            },
        ))

        trace = self.run(scenario, step_fn, context)

        self._event_bus.publish(Event(
            event_type=EventType.INFORMATION_TRANSFORMATION_COMPLETED,
            payload={
                "process_id": process.process_id,
                "trace_id": trace.trace_id,
                "steps": len(trace.steps),
                "source": "simulation",
            },
        ))

        return RuntimeResult(
            success=True,
            process_id=process.process_id,
            trace_id=trace.trace_id,
            message=f"Simulation complete: {len(trace.steps)} steps, "
                    f"final_state_keys={list(trace.final_state.keys())}",
        )

    # ── 跟踪管理 ──────────────────────────────────────────────────────

    def get_trace(self, trace_id: str) -> SimulationTrace | None:
        return self._traces.get(trace_id)

    def list_traces(self) -> list[SimulationTrace]:
        return list(self._traces.values())

    def clear_traces(self) -> None:
        self._traces.clear()


# 辅助函数
def dataclasses_replace(obj: Any, **changes: Any) -> Any:
    """替换 dataclass 字段。简化版 replace。"""
    import dataclasses
    return dataclasses.replace(obj, **changes)

# ── Engine Manifest ──────────────────────────────────────────────────────────
from ocos.platform.engine_manifest import EngineManifest

__manifest__ = EngineManifest(
    engine_id="simulation_engine",
    name="Simulation Engine",
    version="1.0.0",
    engine_class="ocos.engines.simulation_engine.SimulationEngine",
    capabilities=['simulation'],
    dependencies=[],
    singleton=True,
    auto_load=True,
)
