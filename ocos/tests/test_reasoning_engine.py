"""
Test suite for ReasoningEngine.

Phase 19 — Capability Engines 的第一个引擎测试。

覆盖:
1. 推理操作：全部 8 种 InferenceOperation
2. ReasoningTrace 生命周期
3. ProcessRuntimeEngine + ReasoningEngine 集成
4. 自定义推理处理器
5. 边界：空前提、错误 ProcessType
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
from ocos.models.reasoning import (
    InferenceOperation,
    ReasoningStep,
    ReasoningTrace,
)
from ocos.engines.reasoning_engine import ReasoningEngine, register_inference_handler
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
def reasoning_engine(event_bus, working_memory):
    return ReasoningEngine(event_bus, working_memory)


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
    process_type: ProcessType = ProcessType.REASONING,
    operations: list[str] | None = None,
    input_addrs: tuple[str, ...] | None = None,
) -> TransformProcess:
    """Helper: 创建一个 TransformProcess。"""
    steps = (
        tuple(ProcessStep(step_id=f"s{i}", operation=op) for i, op in enumerate(operations))
        if operations
        else ()
    )
    return TransformProcess(
        process_id=process_id,
        process_type=process_type,
        input_addresses=input_addrs or (),
        steps=steps,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# 1. 推理操作
# ═══════════════════════════════════════════════════════════════════════════════

class TestInferenceOperations:
    """验证所有推理操作类型的执行。"""

    def test_deduction(self, reasoning_engine):
        """演绎推理：从一般到特殊。"""
        p = _make_process("p-ded", operations=["deduction"])
        result = reasoning_engine.execute(p)
        assert result.success
        assert result.steps == 1

        trace = reasoning_engine.get_trace(result.trace_id)
        assert trace is not None
        assert trace.process_id == "p-ded"
        assert len(trace.steps) == 1
        assert trace.steps[0].operation == InferenceOperation.DEDUCTION.value
        assert 0.9 <= trace.steps[0].confidence <= 1.0

    def test_induction(self, reasoning_engine):
        """归纳推理：从特殊到一般。"""
        p = _make_process("p-ind", operations=["induction"])
        result = reasoning_engine.execute(p)
        assert result.success
        trace = reasoning_engine.get_trace(result.trace_id)
        assert trace.steps[0].operation == InferenceOperation.INDUCTION.value

    def test_abduction(self, reasoning_engine):
        """溯因推理：从结果到原因。"""
        p = _make_process("p-abd", operations=["abduction"])
        result = reasoning_engine.execute(p)
        assert result.success
        trace = reasoning_engine.get_trace(result.trace_id)
        assert trace.steps[0].operation == InferenceOperation.ABDUCTION.value

    def test_analogy(self, reasoning_engine):
        """类比推理：从相似到相似。"""
        p = _make_process("p-ana", operations=["analogy"])
        result = reasoning_engine.execute(p)
        assert result.success

    def test_analysis(self, reasoning_engine):
        """分析：分解为子问题。"""
        p = _make_process("p-als", operations=["analysis"])
        result = reasoning_engine.execute(p)
        assert result.success

    def test_synthesis(self, reasoning_engine):
        """综合：组合为整体。"""
        p = _make_process("p-syn", operations=["synthesis"])
        result = reasoning_engine.execute(p)
        assert result.success

    def test_comparison(self, reasoning_engine):
        """比较：差异与相似。"""
        p = _make_process("p-cmp", operations=["comparison"])
        result = reasoning_engine.execute(p)
        assert result.success

    def test_evaluation(self, reasoning_engine):
        """评估：价值判断。"""
        p = _make_process("p-evl", operations=["evaluation"])
        result = reasoning_engine.execute(p)
        assert result.success

    def test_multi_step_reasoning(self, reasoning_engine):
        """多步推理链。"""
        p = _make_process(
            "p-chain",
            operations=["analysis", "synthesis", "evaluation"],
            input_addrs=("addr:obs:raw",),
        )
        result = reasoning_engine.execute(p)
        assert result.success
        assert result.steps == 3
        trace = reasoning_engine.get_trace(result.trace_id)
        assert len(trace.steps) == 3
        assert trace.steps[0].operation == InferenceOperation.ANALYSIS.value
        assert trace.steps[1].operation == InferenceOperation.SYNTHESIS.value
        assert trace.steps[2].operation == InferenceOperation.EVALUATION.value

    def test_default_to_deduction(self, reasoning_engine):
        """Process 没有 steps 时默认使用演绎。"""
        p = _make_process("p-default")
        result = reasoning_engine.execute(p)
        assert result.success
        trace = reasoning_engine.get_trace(result.trace_id)
        assert trace.steps[0].operation == InferenceOperation.DEDUCTION.value


# ═══════════════════════════════════════════════════════════════════════════════
# 2. ReasoningTrace 生命周期
# ═══════════════════════════════════════════════════════════════════════════════

class TestReasoningTraceLifecycle:
    """验证 ReasoningTrace 的创建、存储、查询。"""

    def test_trace_storage_and_retrieval(self, reasoning_engine):
        """存储和检索推理轨迹。"""
        p = _make_process("p-trace-1", operations=["deduction"])
        result = reasoning_engine.execute(p)
        assert result.trace_id
        trace = reasoning_engine.get_trace(result.trace_id)
        assert trace is not None
        assert trace.process_id == "p-trace-1"

    def test_list_traces(self, reasoning_engine):
        """列出所有轨迹。"""
        for i in range(3):
            reasoning_engine.execute(_make_process(f"p-list-{i}"))
        assert len(reasoning_engine.list_traces()) == 3

    def test_clear_traces(self, reasoning_engine):
        """清空轨迹。"""
        reasoning_engine.execute(_make_process("p-clear"))
        assert len(reasoning_engine.list_traces()) == 1
        reasoning_engine.clear_traces()
        assert len(reasoning_engine.list_traces()) == 0

    def test_trace_output_addresses(self, reasoning_engine):
        """轨迹包含输出地址。"""
        p = _make_process("p-addr", operations=["deduction", "analysis"])
        result = reasoning_engine.execute(p)
        trace = reasoning_engine.get_trace(result.trace_id)
        assert len(trace.output_addresses) == 2
        for addr in trace.output_addresses:
            assert addr.startswith("addr:reasoning:")


# ═══════════════════════════════════════════════════════════════════════════════
# 3. 自定义推理处理器
# ═══════════════════════════════════════════════════════════════════════════════

class TestCustomInferenceHandler:
    """自定义推理操作处理器。"""

    def test_custom_handler_invoked(self, reasoning_engine):
        """注册的自定义处理器被正确调用。"""
        called = []

        def my_handler(inputs: list, context: dict) -> list:
            called.append(True)
            return ["result:custom"]

        register_inference_handler(InferenceOperation.ANALOGY, my_handler)

        p = _make_process("p-custom", operations=["analogy"])
        result = reasoning_engine.execute(p, premises={"inputs": ["test"]})
        assert result.success
        assert called == [True]


# ═══════════════════════════════════════════════════════════════════════════════
# 4. ProcessRuntimeEngine + ReasoningEngine 集成
# ═══════════════════════════════════════════════════════════════════════════════

class TestProcessReasoningIntegration:
    """验证 ReasoningEngine 与 ProcessRuntimeEngine 的协作。"""

    def test_process_engine_creates_reasoning_process(self, process_engine):
        """ProcessRuntimeEngine 创建 REASONING Process。"""
        pr = process_engine.create_process(
            process_type=ProcessType.REASONING,
            confidence=0.9,
        )
        assert pr.success
        p = process_engine.get_process(pr.process_id)
        assert p.process_type == ProcessType.REASONING.value

    def test_reasoning_engine_executes_process(self, process_engine, reasoning_engine):
        """ReasoningEngine 执行由 ProcessRuntimeEngine 创建的 Process。"""
        pr = process_engine.create_process(
            process_type=ProcessType.REASONING,
            steps=(ProcessStep(step_id="s1", operation="deduction"),),
        )
        process_engine.start_process(pr.process_id)
        p = process_engine.get_process(pr.process_id)
        result = reasoning_engine.execute(p)
        assert result.success
        assert result.process_id == pr.process_id

        process_engine.complete_process(pr.process_id)
        p_final = process_engine.get_process(pr.process_id)
        assert p_final.process_state == ProcessState.COMPLETED.value

    def test_e2e_goal_to_reasoning(self, goal_engine, decision_engine, execution_engine,
                                    process_engine, reasoning_engine):
        """端到端：Goal → Decision → Execution → Process(REASONING) + ReasoningEngine。"""
        gr = goal_engine.set_goal(description="分析季度数据", priority=8)
        dr = decision_engine.form_decision(goal_id=gr.goal_id, selected_option="使用演绎推理")
        decision_engine.transition_decision(dr.decision_id, DecisionStatus.COMMITTED)

        er = execution_engine.schedule_execution(decision_id=dr.decision_id)
        execution_engine.start_execution(er.execution_id)
        execution_engine.transition_execution(er.execution_id, ExecutionStatus.SUCCEEDED)

        pr = process_engine.create_process(
            process_type=ProcessType.REASONING,
            steps=(ProcessStep(step_id="s1", operation="deduction"),),
        )
        process_engine.start_process(pr.process_id)
        p = process_engine.get_process(pr.process_id)
        result = reasoning_engine.execute(p)
        assert result.success

        process_engine.complete_process(pr.process_id)

        assert goal_engine.get_goal(gr.goal_id) is not None
        assert decision_engine.get_decision(dr.decision_id) is not None
        assert execution_engine.get_execution(er.execution_id) is not None
        p_final = process_engine.get_process(pr.process_id)
        assert p_final.process_state == ProcessState.COMPLETED.value
        assert reasoning_engine.get_trace(result.trace_id) is not None


# ═══════════════════════════════════════════════════════════════════════════════
# 5. 边界与错误处理
# ═══════════════════════════════════════════════════════════════════════════════

class TestEdgeCases:
    """边界条件和错误处理。"""

    def test_wrong_process_type(self, reasoning_engine):
        """非 REASONING 类型的 Process 应被拒绝。"""
        p = TransformProcess(
            process_id="p-wrong",
            process_type=ProcessType.PLANNING,
        )
        result = reasoning_engine.execute(p)
        assert not result.success
        assert "Not a REASONING process" in result.message

    def test_empty_steps_uses_default(self, reasoning_engine):
        """无 steps 的 Process 使用默认推理（演绎）。"""
        p = _make_process("p-empty")
        result = reasoning_engine.execute(p)
        assert result.success
        assert result.steps == 1
