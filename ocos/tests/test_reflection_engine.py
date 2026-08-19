"""
Test suite for ReflectionEngine.

Phase 19 — 反思引擎测试。

覆盖:
1. 四种反思策略（CRITICAL, COMPARATIVE, CAUSAL, META）
2. 不同反思对象（process, trace, outcome）
3. 边界条件（空洞见、缺失参数）
4. trace 生命周期
5. ProcessRuntimeEngine 集成
"""

from __future__ import annotations

import pytest

from ocos.events.event_bus import EventBus
from ocos.runtime.context_manager import WorkingMemory
from ocos.runtime.process_runtime import ProcessRuntimeEngine
from ocos.models.process import TransformProcess, ProcessType, ProcessState
from ocos.models.reflection import (
    ReflectionStrategy, ReflectionInsight, ReflectionTrace,
)
from ocos.engines.reflection_engine import ReflectionEngine, ReflectFn


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
    return ReflectionEngine(event_bus, working_memory)


@pytest.fixture
def process_engine(event_bus, working_memory):
    eng = ProcessRuntimeEngine(event_bus, working_memory)
    yield eng
    eng.unsubscribe_all()


def _make_process(process_id: str) -> TransformProcess:
    return TransformProcess(
        process_id=process_id,
        process_type=ProcessType.REASONING,
    )


# ── 内置反思函数 ──────────────────────────────────────────────────────

def _critical_reflect(
    subject_type: str, subject_id: str, strategy: ReflectionStrategy,
) -> list[ReflectionInsight]:
    """批判性反思。"""
    return [
        ReflectionInsight(
            category="error",
            description="Missing validation in step 3",
            evidence=f"subject_id={subject_id}",
            severity="warning",
            recommendation="Add input validation before step 3",
        ),
        ReflectionInsight(
            category="improvement",
            description="Consider parallel execution",
            evidence="Steps 1-3 are independent",
            severity="info",
            recommendation="Parallelize steps 1-3",
        ),
    ]


def _comparative_reflect(
    subject_type: str, subject_id: str, strategy: ReflectionStrategy,
) -> list[ReflectionInsight]:
    """比较反思。"""
    return [
        ReflectionInsight(
            category="deviation",
            description="Actual result 85% vs expected 90%",
            evidence=f"subject_id={subject_id}",
            severity="warning",
            recommendation="Tune parameters for +5% accuracy",
        ),
    ]


def _empty_reflect(
    subject_type: str, subject_id: str, strategy: ReflectionStrategy,
) -> list[ReflectionInsight]:
    """无洞见。"""
    return []


# ═══════════════════════════════════════════════════════════════════════════════
# 1. 基本反思
# ═══════════════════════════════════════════════════════════════════════════════

class TestCriticalReflection:
    """批判性反思。"""

    def test_two_insights(self, engine):
        trace = engine.reflect(
            "process", "p-123", _critical_reflect,
            strategy=ReflectionStrategy.CRITICAL,
        )
        assert len(trace.insights) == 2
        assert trace.insights[0].category == "error"
        assert trace.insights[1].category == "improvement"

    def test_subject_recorded(self, engine):
        trace = engine.reflect(
            "trace", "t-abc", _critical_reflect,
        )
        assert trace.subject_type == "trace"
        assert trace.subject_id == "t-abc"


class TestComparativeReflection:
    """比较反思。"""

    def test_one_insight(self, engine):
        trace = engine.reflect(
            "outcome", "o-456", _comparative_reflect,
            strategy=ReflectionStrategy.COMPARATIVE,
        )
        assert len(trace.insights) == 1
        assert trace.insights[0].category == "deviation"


class TestCausalReflection:
    """因果反思。"""

    def test_causal_strategy(self, engine):
        trace = engine.reflect(
            "process", "p-789", _critical_reflect,
            strategy=ReflectionStrategy.CAUSAL,
        )
        assert trace.strategy == ReflectionStrategy.CAUSAL


class TestMetaReflection:
    """元反思。"""

    def test_meta_strategy(self, engine):
        trace = engine.reflect(
            "reflection", "r-meta", _critical_reflect,
            strategy=ReflectionStrategy.META,
        )
        assert trace.strategy == ReflectionStrategy.META


# ═══════════════════════════════════════════════════════════════════════════════
# 2. 边界与错误处理
# ═══════════════════════════════════════════════════════════════════════════════

class TestEdgeCases:
    """边界条件。"""

    def test_empty_insights(self, engine):
        trace = engine.reflect("process", "p-empty", _empty_reflect)
        assert len(trace.insights) == 0
        assert "0 insights" in trace.summary

    def test_wrong_process_type(self, engine):
        p = TransformProcess(
            process_id="p-wt",
            process_type=ProcessType.LEARNING,
        )
        result = engine.execute(p)
        assert not result.success
        assert "Not a REASONING" in result.message

    def test_missing_subject(self, engine):
        p = _make_process("p-ms")
        result = engine.execute(p, context={})
        assert not result.success
        assert "subject_type" in result.message

    def test_missing_reflect_fn(self, engine):
        p = _make_process("p-mf")
        result = engine.execute(
            p, context={"subject_type": "process", "subject_id": "p-1"},
        )
        assert not result.success
        assert "No reflect_fn" in result.message

    def test_summary_format(self, engine):
        trace = engine.reflect("process", "p-123", _critical_reflect)
        assert "critical" in trace.summary
        assert "2 insights" in trace.summary
        assert "process" in trace.summary


# ═══════════════════════════════════════════════════════════════════════════════
# 3. 跟踪管理
# ═══════════════════════════════════════════════════════════════════════════════

class TestTraceLifecycle:
    """ReflectionTrace 生命周期。"""

    def test_get_trace(self, engine):
        trace = engine.reflect("process", "p-1", _critical_reflect)
        fetched = engine.get_trace(trace.trace_id)
        assert fetched is trace

    def test_list_traces(self, engine):
        engine.reflect("process", "p-1", _critical_reflect)
        engine.reflect("process", "p-2", _comparative_reflect)
        assert len(engine.list_traces()) == 2

    def test_clear_traces(self, engine):
        engine.reflect("process", "p-1", _critical_reflect)
        engine.clear_traces()
        assert len(engine.list_traces()) == 0

    def test_trace_has_strategy(self, engine):
        trace = engine.reflect(
            "process", "p-1", _critical_reflect,
            strategy=ReflectionStrategy.CAUSAL,
        )
        assert trace.strategy == ReflectionStrategy.CAUSAL


# ═══════════════════════════════════════════════════════════════════════════════
# 4. ProcessRuntimeEngine 集成
# ═══════════════════════════════════════════════════════════════════════════════

class TestRuntimeIntegration:
    """与 ProcessRuntimeEngine 协作。"""

    def test_execute_reflection(self, process_engine, engine):
        pr = process_engine.create_process(process_type=ProcessType.REASONING)
        process_engine.start_process(pr.process_id)
        p = process_engine.get_process(pr.process_id)

        result = engine.execute(p, context={
            "subject_type": "process",
            "subject_id": "p-123",
            "reflect_fn": _critical_reflect,
        })

        assert result.success
        assert "2 insights" in result.message
        assert result.trace_id

        process_engine.complete_process(pr.process_id)
        p_final = process_engine.get_process(pr.process_id)
        assert p_final.process_state == ProcessState.COMPLETED.value

    def test_process_type_creates(self, process_engine):
        pr = process_engine.create_process(process_type=ProcessType.REASONING)
        assert pr.success
        p = process_engine.get_process(pr.process_id)
        assert p.process_type == ProcessType.REASONING.value

    def test_execute_with_strategy(self, process_engine, engine):
        pr = process_engine.create_process(process_type=ProcessType.REASONING)
        process_engine.start_process(pr.process_id)
        p = process_engine.get_process(pr.process_id)

        result = engine.execute(p, context={
            "subject_type": "process",
            "subject_id": "p-456",
            "reflect_fn": _comparative_reflect,
            "strategy": ReflectionStrategy.COMPARATIVE,
        })

        assert result.success
        assert "1 insights" in result.message
