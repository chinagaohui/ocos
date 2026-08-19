"""
Test suite for GoalArbitrationEngine.

Phase 19 — 目标仲裁引擎测试。

覆盖:
1. 所有 4 种仲裁策略（PRIORITY, WEIGHTED, EMERGENCY, RESOURCE_AWARE）
2. 自定义仲裁器
3. 空候选边界
4. trace 生命周期
5. ProcessRuntimeEngine 集成
"""

from __future__ import annotations

import pytest

from ocos.events.event_bus import EventBus
from ocos.runtime.context_manager import WorkingMemory
from ocos.runtime.process_runtime import ProcessRuntimeEngine
from ocos.models.process import TransformProcess, ProcessType, ProcessState
from ocos.models.goal_arbitration import (
    ArbitrationStrategy, GoalCandidate, ArbitrationResult, GoalArbitrationTrace,
)
from ocos.engines.goal_arbitration_engine import GoalArbitrationEngine


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
    return GoalArbitrationEngine(event_bus, working_memory)


@pytest.fixture
def process_engine(event_bus, working_memory):
    eng = ProcessRuntimeEngine(event_bus, working_memory)
    yield eng
    eng.unsubscribe_all()


def _make_process(process_id: str) -> TransformProcess:
    return TransformProcess(
        process_id=process_id,
        process_type=ProcessType.ARBITRATION,
    )


SAMPLE_CANDIDATES = [
    GoalCandidate(goal_id="g1", label="Critical bugfix", priority=1,
                  urgency=0.9, resource_cost=3.0, weight=10.0),
    GoalCandidate(goal_id="g2", label="Feature A", priority=3,
                  urgency=0.3, resource_cost=5.0, weight=5.0),
    GoalCandidate(goal_id="g3", label="Refactor", priority=5,
                  urgency=0.1, resource_cost=8.0, weight=2.0),
    GoalCandidate(goal_id="g4", label="Documentation", priority=4,
                  urgency=0.2, resource_cost=2.0, weight=3.0),
]


# ═══════════════════════════════════════════════════════════════════════════════
# 1. 四种仲裁策略
# ═══════════════════════════════════════════════════════════════════════════════

class TestArbitrationStrategies:
    """每种策略的行为验证。"""

    def test_priority_strategy(self, engine):
        """低 priority 值 = 高优先级。"""
        best, trace = engine.arbitrate(SAMPLE_CANDIDATES, ArbitrationStrategy.PRIORITY)
        assert best.goal_id == "g1"  # priority=1

    def test_weighted_strategy(self, engine):
        """高 weight 且低 resource_cost 胜出。"""
        best, trace = engine.arbitrate(SAMPLE_CANDIDATES, ArbitrationStrategy.WEIGHTED)
        assert best.goal_id == "g1"  # 10.0 * (1 - 3.0 * 0.1) = 7.0

    def test_emergency_strategy(self, engine):
        """高 urgency 胜出。"""
        best, trace = engine.arbitrate(SAMPLE_CANDIDATES, ArbitrationStrategy.EMERGENCY)
        assert best.goal_id == "g1"  # urgency=0.9

    def test_resource_aware_strategy(self, engine):
        """低 resource_cost + 低 priority 组合最佳。"""
        best, trace = engine.arbitrate(SAMPLE_CANDIDATES, ArbitrationStrategy.RESOURCE_AWARE)
        # g4: 4 / (1+2) = 1.33, g1: 1/4=0.25, g2: 3/6=0.5, g3: 5/9=0.56
        # 最低分胜出 → g1 (0.25)
        assert best.goal_id == "g1"

    def test_priority_rankings(self, engine):
        """PRIORITY 策略的排序正确性。"""
        _, trace = engine.arbitrate(SAMPLE_CANDIDATES, ArbitrationStrategy.PRIORITY)
        for r in trace.candidates:
            if r.goal_id == "g1":
                assert r.rank == 0
            elif r.goal_id == "g2":
                assert r.rank == 1
            elif r.goal_id == "g4":
                assert r.rank == 2
            elif r.goal_id == "g3":
                assert r.rank == 3


# ═══════════════════════════════════════════════════════════════════════════════
# 2. 自定义仲裁器
# ═══════════════════════════════════════════════════════════════════════════════

class TestCustomArbitrator:
    """自定义仲裁器注册与调用。"""

    def test_custom_arbitrator(self, engine):
        called = []

        def my_arb(candidates, ctx):
            called.append(True)
            return [
                ArbitrationResult(
                    candidate_id=c.goal_id + "_result",
                    goal_id=c.goal_id, label=c.label,
                    selected=True, rank=i, score=1.0,
                    reason="Custom arbitrator",
                )
                for i, c in enumerate(candidates)
            ]

        engine._arbitrators[ArbitrationStrategy.PRIORITY] = my_arb
        best, trace = engine.arbitrate(SAMPLE_CANDIDATES, ArbitrationStrategy.PRIORITY)
        assert called == [True]
        assert best.reason == "Custom arbitrator"


# ═══════════════════════════════════════════════════════════════════════════════
# 3. 边界与错误处理
# ═══════════════════════════════════════════════════════════════════════════════

class TestEdgeCases:
    """边界条件。"""

    def test_empty_candidates_raises(self, engine):
        """execute 检查空候选。"""
        p = _make_process("p-ec")
        result = engine.execute(p, context={"candidates": []})
        assert not result.success
        assert "No candidates" in result.message

    def test_wrong_process_type(self, engine):
        p = TransformProcess(
            process_id="p-wt",
            process_type=ProcessType.REASONING,
        )
        result = engine.execute(p, context={"candidates": SAMPLE_CANDIDATES})
        assert not result.success

    def test_single_candidate(self, engine):
        """单一候选自动选定。"""
        best, trace = engine.arbitrate(
            [SAMPLE_CANDIDATES[0]], ArbitrationStrategy.PRIORITY,
        )
        assert best.goal_id == "g1"
        assert best.selected
        assert len(trace.selected_ids) == 1

    def test_candidates_with_ties(self, engine):
        """相同优先级的候选。"""
        ties = [
            GoalCandidate(goal_id="a", label="A", priority=1),
            GoalCandidate(goal_id="b", label="B", priority=1),
        ]
        best, trace = engine.arbitrate(ties, ArbitrationStrategy.PRIORITY)
        assert best.goal_id in ("a", "b")
        assert len(trace.selected_ids) == 1


# ═══════════════════════════════════════════════════════════════════════════════
# 4. 跟踪管理
# ═══════════════════════════════════════════════════════════════════════════════

class TestTraceLifecycle:
    """ArbitrationTrace 的创建和清理。"""

    def test_trace_created(self, engine):
        best, trace = engine.arbitrate(SAMPLE_CANDIDATES, ArbitrationStrategy.PRIORITY)
        assert trace.trace_id
        assert len(trace.candidates) == 4
        assert trace.selected_ids == ("g1",)
        assert len(trace.suspended_ids) == 3

    def test_list_traces(self, engine):
        engine.arbitrate(SAMPLE_CANDIDATES, ArbitrationStrategy.PRIORITY)
        engine.arbitrate(SAMPLE_CANDIDATES, ArbitrationStrategy.EMERGENCY)
        assert len(engine.list_traces()) == 2

    def test_get_trace(self, engine):
        _, trace = engine.arbitrate(SAMPLE_CANDIDATES, ArbitrationStrategy.PRIORITY)
        fetched = engine.get_trace(trace.trace_id)
        assert fetched is trace

    def test_clear_traces(self, engine):
        engine.arbitrate(SAMPLE_CANDIDATES, ArbitrationStrategy.PRIORITY)
        engine.clear_traces()
        assert len(engine.list_traces()) == 0

    def test_summary(self, engine):
        _, trace = engine.arbitrate(SAMPLE_CANDIDATES, ArbitrationStrategy.WEIGHTED)
        assert "selected 1" in trace.summary
        assert "suspended 3" in trace.summary


# ═══════════════════════════════════════════════════════════════════════════════
# 5. ProcessRuntimeEngine 集成
# ═══════════════════════════════════════════════════════════════════════════════

class TestRuntimeIntegration:
    """与 ProcessRuntimeEngine 的协作。"""

    def test_execute_via_process_engine(self, process_engine, engine):
        pr = process_engine.create_process(process_type=ProcessType.ARBITRATION)
        process_engine.start_process(pr.process_id)
        p = process_engine.get_process(pr.process_id)
        result = engine.execute(
            p, context={"candidates": SAMPLE_CANDIDATES, "strategy": "priority"},
        )
        assert result.success
        assert "g1" in result.message
        process_engine.complete_process(pr.process_id)
        p_final = process_engine.get_process(pr.process_id)
        assert p_final.process_state == ProcessState.COMPLETED.value

    def test_execute_strategy_from_context(self, process_engine, engine):
        pr = process_engine.create_process(process_type=ProcessType.ARBITRATION)
        process_engine.start_process(pr.process_id)
        p = process_engine.get_process(pr.process_id)
        result = engine.execute(
            p, context={"candidates": SAMPLE_CANDIDATES, "strategy": "emergency"},
        )
        assert result.success

    def test_process_creates_arbitration(self, process_engine):
        pr = process_engine.create_process(process_type=ProcessType.ARBITRATION)
        assert pr.success
        p = process_engine.get_process(pr.process_id)
        assert p.process_type == ProcessType.ARBITRATION.value
