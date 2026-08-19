"""
Test suite for DecisionMakingEngine.

Phase 19 — 决策生成引擎测试。

覆盖:
1. 所有 6 种决策策略（SCORING, RANKING, MAJORITY, SATISFICING, OPPORTUNITY_COST, PARETO）
2. DecisionMakingTrace 生命周期
3. 自定义策略处理器
4. DecisionRuntimeEngine + DecisionMakingEngine 集成
5. E2E 端到端集成
6. 边界与错误处理
"""

from __future__ import annotations

import pytest

from ocos.events.event_bus import EventBus
from ocos.runtime.context_manager import WorkingMemory
from ocos.runtime.goal_runtime import GoalRuntimeEngine
from ocos.runtime.decision_runtime import DecisionRuntimeEngine
from ocos.runtime.execution_runtime import ExecutionRuntimeEngine
from ocos.runtime.process_runtime import ProcessRuntimeEngine
from ocos.models.process import TransformProcess, ProcessType, ProcessState
from ocos.models.decision_making import DecisionStrategy, DecisionOption, DecisionMakingTrace
from ocos.engines.decision_making_engine import (
    DecisionMakingEngine,
    register_decision_strategy,
)
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
def de_engine(event_bus, working_memory):
    return DecisionMakingEngine(event_bus, working_memory)


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
def decision_lifecycle(event_bus, working_memory):
    eng = DecisionRuntimeEngine(event_bus, working_memory)
    yield eng
    eng.unsubscribe_all()


@pytest.fixture
def execution_engine(event_bus, working_memory):
    eng = ExecutionRuntimeEngine(event_bus, working_memory)
    yield eng
    eng.unsubscribe_all()


DEFAULT_OPTIONS = [
    {"label": "高风险高回报", "scores": {"quality": 9, "cost": 1, "risk": 8}},
    {"label": "平衡方案", "scores": {"quality": 6, "cost": 7, "risk": 2}},
    {"label": "保守方案", "scores": {"quality": 4, "cost": 9, "risk": 1}},
]


def _make_process(
    process_id: str,
    strategy: str | None = None,
) -> TransformProcess:
    metadata = {"strategy": strategy} if strategy else {}
    return TransformProcess(
        process_id=process_id,
        process_type=ProcessType.DECISION,
        metadata=metadata,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# 1. 决策策略
# ═══════════════════════════════════════════════════════════════════════════════

class TestDecisionStrategies:
    """验证所有决策策略。"""

    def test_scoring(self, de_engine):
        p = _make_process("d-sc", strategy="scoring")
        result = de_engine.execute(p, options_data=DEFAULT_OPTIONS,
                                    context={"weights": {"quality": 1.0, "cost": 0.5, "risk": 0.3}})
        assert result.success
        trace = de_engine.get_trace(result.trace_id)
        assert trace.strategy == DecisionStrategy.SCORING

    def test_ranking(self, de_engine):
        p = _make_process("d-rk", strategy="ranking")
        result = de_engine.execute(p, options_data=DEFAULT_OPTIONS)
        assert result.success
        trace = de_engine.get_trace(result.trace_id)
        assert trace.strategy == DecisionStrategy.RANKING
        # 排名后应有 rank 字段
        for opt in trace.options:
            assert opt.rank > 0

    def test_majority(self, de_engine):
        p = _make_process("d-mj", strategy="majority")
        result = de_engine.execute(p, options_data=DEFAULT_OPTIONS)
        assert result.success

    def test_satisficing(self, de_engine):
        p = _make_process("d-sf", strategy="satisficing")
        result = de_engine.execute(p, options_data=DEFAULT_OPTIONS,
                                    context={"threshold": 5.0})
        assert result.success
        trace = de_engine.get_trace(result.trace_id)
        assert trace.selected_option_id

    def test_opportunity_cost(self, de_engine):
        p = _make_process("d-oc", strategy="opportunity_cost")
        result = de_engine.execute(p, options_data=DEFAULT_OPTIONS)
        assert result.success

    def test_pareto(self, de_engine):
        p = _make_process("d-po", strategy="pareto")
        result = de_engine.execute(p, options_data=DEFAULT_OPTIONS)
        assert result.success

    def test_default_strategy(self, de_engine):
        p = _make_process("d-def")
        result = de_engine.execute(p)
        assert result.success
        trace = de_engine.get_trace(result.trace_id)
        assert trace.strategy == DecisionStrategy.SCORING

    def test_selected_option_marked(self, de_engine):
        p = _make_process("d-sel")
        result = de_engine.execute(p, options_data=DEFAULT_OPTIONS)
        trace = de_engine.get_trace(result.trace_id)
        selected = [o for o in trace.options if o.is_selected]
        assert len(selected) == 1
        assert selected[0].option_id == trace.selected_option_id

    def test_rationale_generated(self, de_engine):
        p = _make_process("d-ra")
        result = de_engine.execute(p, options_data=DEFAULT_OPTIONS)
        trace = de_engine.get_trace(result.trace_id)
        assert trace.rationale
        assert "selected" in trace.rationale.lower()


# ═══════════════════════════════════════════════════════════════════════════════
# 2. DecisionMakingTrace 生命周期
# ═══════════════════════════════════════════════════════════════════════════════

class TestTraceLifecycle:
    """验证 DecisionMakingTrace 的存储与查询。"""

    def test_storage_and_retrieval(self, de_engine):
        p = _make_process("d-tr1")
        result = de_engine.execute(p, options_data=DEFAULT_OPTIONS)
        trace = de_engine.get_trace(result.trace_id)
        assert trace is not None
        assert trace.process_id == "d-tr1"

    def test_list_traces(self, de_engine):
        for i in range(3):
            de_engine.execute(_make_process(f"d-lst-{i}"))
        assert len(de_engine.list_traces()) == 3

    def test_clear_traces(self, de_engine):
        de_engine.execute(_make_process("d-clr"))
        de_engine.clear_traces()
        assert len(de_engine.list_traces()) == 0

    def test_error_trace(self, de_engine):
        """不应有错误的正常流程。"""
        p = _make_process("d-err")
        result = de_engine.execute(p, options_data=DEFAULT_OPTIONS)
        assert result.success
        trace = de_engine.get_trace(result.trace_id)
        assert trace.error == ""


# ═══════════════════════════════════════════════════════════════════════════════
# 3. 自定义策略处理器
# ═══════════════════════════════════════════════════════════════════════════════

class TestCustomStrategy:
    """自定义决策策略处理器。"""

    def test_custom_strategy_invoked(self, de_engine):
        def my_handler(
            opts_data: list[dict], ctx: dict
        ) -> tuple[list[DecisionOption], str]:
            opts = [DecisionOption(label=d.get("label", "")) for d in opts_data]
            return opts, opts[0].option_id

        register_decision_strategy(DecisionStrategy.MAJORITY, my_handler)
        p = _make_process("d-cs", strategy="majority")
        result = de_engine.execute(p, options_data=DEFAULT_OPTIONS)
        assert result.success
        trace = de_engine.get_trace(result.trace_id)
        assert trace.rationale.startswith("Custom")


# ═══════════════════════════════════════════════════════════════════════════════
# 4. ProcessRuntimeEngine + DecisionRuntimeEngine 集成
# ═══════════════════════════════════════════════════════════════════════════════

class TestRuntimeIntegration:
    """验证 DecisionMakingEngine 与 Runtime engine 的协作。"""

    def test_process_engine_creates_decision_process(self, process_engine):
        pr = process_engine.create_process(process_type=ProcessType.DECISION)
        assert pr.success
        p = process_engine.get_process(pr.process_id)
        assert p.process_type == ProcessType.DECISION.value

    def test_decision_engine_executes_process(self, process_engine, de_engine):
        pr = process_engine.create_process(process_type=ProcessType.DECISION)
        process_engine.start_process(pr.process_id)
        p = process_engine.get_process(pr.process_id)
        result = de_engine.execute(p, options_data=DEFAULT_OPTIONS)
        assert result.success
        process_engine.complete_process(pr.process_id)
        p_final = process_engine.get_process(pr.process_id)
        assert p_final.process_state == ProcessState.COMPLETED.value

    def test_e2e_goal_to_decision_making(self, goal_engine, decision_lifecycle,
                                          execution_engine, process_engine, de_engine):
        """端到端：Goal → Decision(生命周期) → Execution
                → Process(DECISION) + DecisionMakingEngine。"""
        gr = goal_engine.set_goal(description="选择最优架构方案", priority=8)
        dr = decision_lifecycle.form_decision(
            goal_id=gr.goal_id, selected_option="初步选择"
        )
        decision_lifecycle.transition_decision(dr.decision_id, DecisionStatus.COMMITTED)
        er = execution_engine.schedule_execution(decision_id=dr.decision_id)
        execution_engine.start_execution(er.execution_id)
        execution_engine.transition_execution(er.execution_id, ExecutionStatus.SUCCEEDED)

        pr = process_engine.create_process(process_type=ProcessType.DECISION)
        process_engine.start_process(pr.process_id)
        p = process_engine.get_process(pr.process_id)
        result = de_engine.execute(p, options_data=DEFAULT_OPTIONS)
        assert result.success
        process_engine.complete_process(pr.process_id)

        assert de_engine.get_trace(result.trace_id) is not None
        assert result.selected_option_id


# ═══════════════════════════════════════════════════════════════════════════════
# 5. 边界与错误处理
# ═══════════════════════════════════════════════════════════════════════════════

class TestEdgeCases:
    """边界条件和错误处理。"""

    def test_wrong_process_type(self, de_engine):
        p = TransformProcess(
            process_id="d-wrong",
            process_type=ProcessType.REASONING,
        )
        result = de_engine.execute(p)
        assert not result.success
        assert "Not a DECISION process" in result.message

    def test_override_strategy(self, de_engine):
        p = _make_process("d-ov", strategy="scoring")
        result = de_engine.execute(p, strategy="pareto", options_data=DEFAULT_OPTIONS)
        trace = de_engine.get_trace(result.trace_id)
        assert trace.strategy == DecisionStrategy.PARETO

    def test_unknown_strategy(self, de_engine):
        p = _make_process("d-uk")
        with pytest.raises(ValueError):
            de_engine.execute(p, strategy="unknown")

    def test_empty_options(self, de_engine):
        p = _make_process("d-em")
        result = de_engine.execute(p, options_data=[])
        assert result.success  # defaults to 3 default options

    def test_make_decision_helper(self, de_engine):
        """验证 make_decision 便利函数。"""
        from ocos.engines.decision_making_engine import make_decision
        p = _make_process("d-hlp")
        result = make_decision(de_engine, p, options=DEFAULT_OPTIONS)
        assert result.success
