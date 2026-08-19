"""
Test suite for PlanningEngine.

Phase 19 — 规划引擎测试。

覆盖:
1. 所有 6 种规划策略
2. PlanningTrace 生命周期
3. 自定义策略处理器
4. ProcessRuntimeEngine 集成
5. 边界与错误处理
"""

from __future__ import annotations

import pytest

from ocos.events.event_bus import EventBus
from ocos.runtime.context_manager import WorkingMemory
from ocos.runtime.goal_runtime import GoalRuntimeEngine
from ocos.runtime.decision_runtime import DecisionRuntimeEngine
from ocos.runtime.execution_runtime import ExecutionRuntimeEngine
from ocos.runtime.process_runtime import ProcessRuntimeEngine
from ocos.models.process import TransformProcess, ProcessState, ProcessType, ProcessStep
from ocos.models.planning import PlanningStrategy, PlanningTrace, PlanningStep, PlanStatus
from ocos.engines.planning_engine import PlanningEngine, register_planning_strategy
from ocos.kernel.abi import DecisionStatus
from ocos.models.execution import ExecutionStatus


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
def planning_engine(event_bus, working_memory):
    return PlanningEngine(event_bus, working_memory)


@pytest.fixture
def process_engine(event_bus, working_memory):
    eng = ProcessRuntimeEngine(event_bus, working_memory)
    yield eng
    eng.unsubscribe_all()


@pytest.fixture
def goal_engine(event_bus, working_memory):
    eng = GoalRuntimeEngine(event_bus, working_memory)
    yield eng
    eng.unsubscribe_all()


@pytest.fixture
def decision_engine(event_bus, working_memory):
    eng = DecisionRuntimeEngine(event_bus, working_memory)
    yield eng
    eng.unsubscribe_all()


@pytest.fixture
def execution_engine(event_bus, working_memory):
    eng = ExecutionRuntimeEngine(event_bus, working_memory)
    yield eng
    eng.unsubscribe_all()


def _make_process(
    process_id: str,
    strategy: str | None = None,
    input_addrs: tuple[str, ...] | None = None,
) -> TransformProcess:
    """Helper: 创建一个 PLANNING Process。"""
    metadata = {"strategy": strategy} if strategy else {}
    return TransformProcess(
        process_id=process_id,
        process_type=ProcessType.PLANNING,
        input_addresses=input_addrs or (),
        metadata=metadata,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# 1. 规划策略
# ═══════════════════════════════════════════════════════════════════════════════

class TestPlanningStrategies:
    """验证所有规划策略。"""

    def test_top_down(self, planning_engine):
        """自顶向下分解。"""
        p = _make_process("p-td", strategy="top_down")
        result = planning_engine.execute(p)
        assert result.success
        assert result.step_count == 4
        trace = planning_engine.get_trace(result.trace_id)
        assert trace.strategy == PlanningStrategy.TOP_DOWN

    def test_bottom_up(self, planning_engine):
        """自底向上组合。"""
        p = _make_process("p-bu", strategy="bottom_up")
        result = planning_engine.execute(p)
        assert result.success
        assert result.step_count == 3
        trace = planning_engine.get_trace(result.trace_id)
        assert trace.strategy == PlanningStrategy.BOTTOM_UP

    def test_means_end(self, planning_engine):
        """手段-目的分析。"""
        p = _make_process("p-me", strategy="means_end")
        result = planning_engine.execute(p)
        assert result.success
        assert result.step_count == 5
        trace = planning_engine.get_trace(result.trace_id)
        assert trace.strategy == PlanningStrategy.MEANS_END

    def test_case_based(self, planning_engine):
        """基于案例的规划。"""
        p = _make_process("p-cb", strategy="case_based")
        result = planning_engine.execute(p)
        assert result.success
        assert result.step_count == 3
        trace = planning_engine.get_trace(result.trace_id)
        assert trace.strategy == PlanningStrategy.CASE_BASED

    def test_iterative(self, planning_engine):
        """迭代细化。"""
        p = _make_process("p-it", strategy="iterative")
        result = planning_engine.execute(p)
        assert result.success
        assert result.step_count == 3
        trace = planning_engine.get_trace(result.trace_id)
        assert trace.strategy == PlanningStrategy.ITERATIVE

    def test_parallel(self, planning_engine):
        """并行分解。"""
        p = _make_process("p-pl", strategy="parallel")
        result = planning_engine.execute(p)
        assert result.success
        assert result.step_count == 4
        trace = planning_engine.get_trace(result.trace_id)
        assert trace.strategy == PlanningStrategy.PARALLEL

    def test_default_strategy(self, planning_engine):
        """未指定策略时默认 TOP_DOWN。"""
        p = _make_process("p-def")
        result = planning_engine.execute(p)
        assert result.success
        trace = planning_engine.get_trace(result.trace_id)
        assert trace.strategy == PlanningStrategy.TOP_DOWN

    def test_steps_have_dependencies(self, planning_engine):
        """步骤有正确的依赖关系。"""
        p = _make_process("p-dep")
        result = planning_engine.execute(p)
        trace = planning_engine.get_trace(result.trace_id)
        steps = trace.steps
        for i in range(1, len(steps)):
            assert len(steps[i].depends_on) > 0
        assert len(steps[0].depends_on) == 0  # 第一步无依赖

    def test_total_effort_calculated(self, planning_engine):
        """总工作量正确计算。"""
        p = _make_process("p-eff")
        result = planning_engine.execute(p)
        trace = planning_engine.get_trace(result.trace_id)
        expected = sum(s.estimated_effort for s in trace.steps)
        assert trace.total_effort == expected


# ═══════════════════════════════════════════════════════════════════════════════
# 2. PlanningTrace 生命周期
# ═══════════════════════════════════════════════════════════════════════════════

class TestPlanningTraceLifecycle:
    """验证 PlanningTrace 的创建、存储、查询。"""

    def test_storage_and_retrieval(self, planning_engine):
        p = _make_process("p-tr1")
        result = planning_engine.execute(p)
        assert result.trace_id
        trace = planning_engine.get_trace(result.trace_id)
        assert trace is not None
        assert trace.process_id == "p-tr1"

    def test_list_traces(self, planning_engine):
        for i in range(3):
            planning_engine.execute(_make_process(f"p-lst-{i}"))
        assert len(planning_engine.list_traces()) == 3

    def test_clear_traces(self, planning_engine):
        planning_engine.execute(_make_process("p-clr"))
        assert len(planning_engine.list_traces()) == 1
        planning_engine.clear_traces()
        assert len(planning_engine.list_traces()) == 0

    def test_trace_goal_address(self, planning_engine):
        p = _make_process("p-ga", input_addrs=("addr:goal:1",))
        result = planning_engine.execute(p, inputs={"goal": "完成分析"})
        trace = planning_engine.get_trace(result.trace_id)
        assert "addr:goal:1" in trace.goal_address
        assert len(trace.output_addresses) == len(trace.steps)


# ═══════════════════════════════════════════════════════════════════════════════
# 3. 自定义策略处理器
# ═══════════════════════════════════════════════════════════════════════════════

class TestCustomStrategy:
    """自定义规划策略处理器。"""

    def test_custom_strategy_invoked(self, planning_engine):
        called = []

        def my_handler(inputs: list, context: dict) -> list[PlanningStep]:
            called.append(True)
            return [PlanningStep(description="custom step")]

        register_planning_strategy(PlanningStrategy.ITERATIVE, my_handler)
        p = _make_process("p-cs", strategy="iterative")
        result = planning_engine.execute(p)
        assert result.success
        assert called == [True]


# ═══════════════════════════════════════════════════════════════════════════════
# 4. ProcessRuntimeEngine 集成
# ═══════════════════════════════════════════════════════════════════════════════

class TestProcessPlanningIntegration:
    """验证 PlanningEngine 与 ProcessRuntimeEngine 的协作。"""

    def test_process_engine_creates_planning_process(self, process_engine):
        pr = process_engine.create_process(
            process_type=ProcessType.PLANNING,
        )
        assert pr.success
        p = process_engine.get_process(pr.process_id)
        assert p.process_type == ProcessType.PLANNING.value

    def test_planning_engine_executes_process(self, process_engine, planning_engine):
        pr = process_engine.create_process(
            process_type=ProcessType.PLANNING,
        )
        process_engine.start_process(pr.process_id)
        p = process_engine.get_process(pr.process_id)
        result = planning_engine.execute(p)
        assert result.success
        assert result.process_id == pr.process_id
        process_engine.complete_process(pr.process_id)
        p_final = process_engine.get_process(pr.process_id)
        assert p_final.process_state == ProcessState.COMPLETED.value

    def test_e2e_goal_to_planning(self, goal_engine, decision_engine, execution_engine,
                                   process_engine, planning_engine):
        """端到端：Goal → Decision → Execution → Process(PLANNING) + PlanningEngine。"""
        gr = goal_engine.set_goal(description="规划系统架构", priority=9)
        dr = decision_engine.form_decision(goal_id=gr.goal_id, selected_option="使用自顶向下规划")
        decision_engine.transition_decision(dr.decision_id, DecisionStatus.COMMITTED)
        er = execution_engine.schedule_execution(decision_id=dr.decision_id)
        execution_engine.start_execution(er.execution_id)
        execution_engine.transition_execution(er.execution_id, ExecutionStatus.SUCCEEDED)

        pr = process_engine.create_process(
            process_type=ProcessType.PLANNING,
        )
        process_engine.start_process(pr.process_id)
        p = process_engine.get_process(pr.process_id)
        result = planning_engine.execute(p)
        assert result.success
        process_engine.complete_process(pr.process_id)

        assert goal_engine.get_goal(gr.goal_id) is not None
        assert decision_engine.get_decision(dr.decision_id) is not None
        assert planning_engine.get_trace(result.trace_id) is not None
        p_final = process_engine.get_process(pr.process_id)
        assert p_final.process_state == ProcessState.COMPLETED.value


# ═══════════════════════════════════════════════════════════════════════════════
# 5. 边界与错误处理
# ═══════════════════════════════════════════════════════════════════════════════

class TestEdgeCases:
    """边界条件和错误处理。"""

    def test_wrong_process_type(self, planning_engine):
        p = TransformProcess(
            process_id="p-wrong",
            process_type=ProcessType.REASONING,
        )
        result = planning_engine.execute(p)
        assert not result.success
        assert "Not a PLANNING process" in result.message

    def test_override_strategy(self, planning_engine):
        """运行时覆盖策略。"""
        p = _make_process("p-ov", strategy="top_down")
        result = planning_engine.execute(p, strategy="parallel")
        trace = planning_engine.get_trace(result.trace_id)
        assert trace.strategy == PlanningStrategy.PARALLEL

    def test_unknown_strategy(self, planning_engine):
        """未知策略应抛出 ValueError。"""
        p = _make_process("p-uk")
        with pytest.raises(ValueError):
            planning_engine.execute(p, strategy="unknown_strategy")
