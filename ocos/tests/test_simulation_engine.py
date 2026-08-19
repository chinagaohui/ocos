"""
Test suite for SimulationEngine.

Phase 19 — 模拟引擎测试。

覆盖:
1. 模拟执行（WHAT_IF, TIME_SERIES, AGENT_BASED）
2. 蒙特卡洛多轮运行
3. 边界条件（空初始状态、0步、非线性步进函数）
4. trace 生命周期
5. ProcessRuntimeEngine 集成
"""

from __future__ import annotations

import pytest

from ocos.events.event_bus import EventBus
from ocos.runtime.context_manager import WorkingMemory
from ocos.runtime.process_runtime import ProcessRuntimeEngine
from ocos.models.process import TransformProcess, ProcessType, ProcessState
from ocos.models.simulation import (
    SimulationStrategy, SimulationScenario, SimulationStep, SimulationTrace,
)
from ocos.engines.simulation_engine import SimulationEngine, StepFn


# ═══════════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def event_bus():
    return EventBus()


@pytest.fixture
def working_memory(event_bus):
    return WorkingMemory(event_bus=event_bus)


@pytest.fixture
def engine(event_bus, working_memory):
    return SimulationEngine(event_bus, working_memory)


@pytest.fixture
def process_engine(event_bus, working_memory):
    eng = ProcessRuntimeEngine(event_bus, working_memory)
    yield eng
    eng.unsubscribe_all()


def _make_process(process_id: str) -> TransformProcess:
    return TransformProcess(
        process_id=process_id,
        process_type=ProcessType.SIMULATION,
    )


# 内置步进函数
def _count_step(state: dict, params: dict, step: int) -> dict:
    """每次计数值 +1。"""
    return {"count": state.get("count", 0) + 1}


def _growth_step(state: dict, params: dict, step: int) -> dict:
    """指数增长。"""
    rate = params.get("growth_rate", 0.1)
    val = state.get("value", 10)
    return {"value": val * (1 + rate)}


def _linear_step(state: dict, params: dict, step: int) -> dict:
    """线性增量——从 state 读累加值再加增量。"""
    inc = params.get("increment", 5)
    return {"total": state.get("total", 0) + inc}


# ═══════════════════════════════════════════════════════════════════════════════
# 1. 基本模拟（WHAT_IF）
# ═══════════════════════════════════════════════════════════════════════════════

class TestBasicSimulation:
    """基础 WHAT_IF 模拟。"""

    def test_simple_count(self, engine):
        scenario = SimulationScenario(
            strategy=SimulationStrategy.WHAT_IF,
            initial_state={"count": 0},
            steps=5,
        )
        trace = engine.run(scenario, _count_step)
        assert len(trace.steps) == 5
        assert trace.final_state["count"] == 5

    def test_linear_growth(self, engine):
        scenario = SimulationScenario(
            strategy=SimulationStrategy.WHAT_IF,
            initial_state={"total": 0},
            parameters={"increment": 10},
            steps=3,
        )
        trace = engine.run(scenario, _linear_step)
        assert trace.final_state["total"] == 30
        # delta 是累积值
        assert trace.steps[0].delta["total"] == 10
        assert trace.steps[1].delta["total"] == 20
        assert trace.steps[2].delta["total"] == 30

    def test_exponential_growth(self, engine):
        scenario = SimulationScenario(
            strategy=SimulationStrategy.WHAT_IF,
            initial_state={"value": 100},
            parameters={"growth_rate": 0.5},
            steps=4,
        )
        trace = engine.run(scenario, _growth_step)
        # 100 * 1.5^4 ≈ 506.25
        assert abs(trace.final_state["value"] - 506.25) < 0.01

    def test_trace_contains_scenario_id(self, engine):
        scenario = SimulationScenario(
            scenario_id="my-test",
            initial_state={"x": 0},
            steps=2,
        )
        trace = engine.run(scenario, _count_step)
        assert trace.scenario_id == "my-test"


# ═══════════════════════════════════════════════════════════════════════════════
# 2. 策略标签
# ═══════════════════════════════════════════════════════════════════════════════

class TestStrategyTags:
    """不同策略标签的模拟。"""

    def test_time_series(self, engine):
        scenario = SimulationScenario(
            strategy=SimulationStrategy.TIME_SERIES,
            initial_state={"temp": 20},
            parameters={"delta": -0.5},
            steps=10,
        )
        trace = engine.run(scenario, _linear_step)
        assert trace.strategy == SimulationStrategy.TIME_SERIES

    def test_agent_based(self, engine):
        scenario = SimulationScenario(
            strategy=SimulationStrategy.AGENT_BASED,
            initial_state={"agents": 5},
            steps=3,
        )
        trace = engine.run(scenario, _count_step)
        assert trace.strategy == SimulationStrategy.AGENT_BASED


# ═══════════════════════════════════════════════════════════════════════════════
# 3. 蒙特卡洛多轮运行
# ═══════════════════════════════════════════════════════════════════════════════

class TestMonteCarlo:
    """多轮模拟。"""

    def test_multiple_runs(self, engine):
        scenario = SimulationScenario(
            initial_state={"total": 0},
            parameters={"increment": 5},
            steps=2,
        )
        traces = engine.run_monte_carlo(scenario, _linear_step, num_runs=3)
        assert len(traces) == 3
        for trace in traces:
            assert trace.final_state["total"] == 10

    def test_each_run_unique_trace(self, engine):
        scenario = SimulationScenario(
            initial_state={"x": 0},
            steps=1,
        )
        traces = engine.run_monte_carlo(scenario, _count_step, num_runs=2)
        assert traces[0].trace_id != traces[1].trace_id


# ═══════════════════════════════════════════════════════════════════════════════
# 4. 边界与错误处理
# ═════════════──────────────────────────────────────────────────────────────────

class TestEdgeCases:
    """边界条件。"""

    def test_zero_steps(self, engine):
        scenario = SimulationScenario(
            initial_state={"x": 10},
            steps=0,
        )
        trace = engine.run(scenario, _count_step)
        assert len(trace.steps) == 0
        assert trace.final_state == {"x": 10}

    def test_empty_initial_state(self, engine):
        scenario = SimulationScenario(steps=3)
        trace = engine.run(scenario, _count_step)
        assert trace.final_state["count"] == 3

    def test_non_linear_step_fn(self, engine):
        """步进函数可根据 step_num 做不同事。"""
        def conditional_step(state, params, step):
            if step == 1:
                return {"val": 100}
            elif step == 2:
                return {"val": 200}
            return {"val": 0}

        scenario = SimulationScenario(steps=3)
        trace = engine.run(scenario, conditional_step)
        assert trace.steps[0].delta["val"] == 100
        assert trace.steps[1].delta["val"] == 200
        assert trace.steps[2].delta["val"] == 0

    def test_wrong_process_type(self, engine):
        p = TransformProcess(
            process_id="p-wt",
            process_type=ProcessType.REASONING,
        )
        result = engine.execute(p)
        assert not result.success

    def test_missing_scenario(self, engine):
        p = _make_process("p-ms")
        result = engine.execute(p)
        assert not result.success
        assert "No scenario" in result.message

    def test_missing_step_fn(self, engine):
        p = _make_process("p-mf")
        scenario = SimulationScenario(steps=1)
        result = engine.execute(p, context={"scenario": scenario})
        assert not result.success
        assert "No step_fn" in result.message


# ═══════════════════════════════════════════════════════════════════════════════
# 5. 跟踪管理
# ═════════════════─────────────────────────────────────────────────────────────

class TestTraceLifecycle:
    """SimulationTrace 生命周期。"""

    def test_trace_stored(self, engine):
        scenario = SimulationScenario(steps=2)
        trace = engine.run(scenario, _count_step)
        fetched = engine.get_trace(trace.trace_id)
        assert fetched is trace

    def test_list_traces(self, engine):
        engine.run(SimulationScenario(steps=1), _count_step)
        engine.run(SimulationScenario(steps=2), _count_step)
        assert len(engine.list_traces()) == 2

    def test_clear_traces(self, engine):
        engine.run(SimulationScenario(steps=1), _count_step)
        engine.clear_traces()
        assert len(engine.list_traces()) == 0

    def test_summary_contains_strategy(self, engine):
        scenario = SimulationScenario(strategy=SimulationStrategy.TIME_SERIES, steps=3)
        trace = engine.run(scenario, _count_step)
        assert "time_series" in trace.summary


# ═══════════════════════════════════════════════════════════════════════════════
# 6. ProcessRuntimeEngine 集成
# ═══════════════════════════════════════════════════════════════════════════════

class TestRuntimeIntegration:
    """与 ProcessRuntimeEngine 的协作。"""

    def test_execute_simulation(self, process_engine, engine):
        pr = process_engine.create_process(process_type=ProcessType.SIMULATION)
        process_engine.start_process(pr.process_id)
        p = process_engine.get_process(pr.process_id)
        scenario = SimulationScenario(steps=3)
        result = engine.execute(
            p, context={"scenario": scenario, "step_fn": _count_step},
        )
        assert result.success
        assert "3 steps" in result.message
        process_engine.complete_process(pr.process_id)
        p_final = process_engine.get_process(pr.process_id)
        assert p_final.process_state == ProcessState.COMPLETED.value

    def test_process_type_creates(self, process_engine):
        pr = process_engine.create_process(process_type=ProcessType.SIMULATION)
        assert pr.success
        p = process_engine.get_process(pr.process_id)
        assert p.process_type == ProcessType.SIMULATION.value
