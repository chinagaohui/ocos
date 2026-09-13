"""
Test suite for PredictionEngine.

Phase 19 — 预测引擎测试（最后一个能力引擎）。

覆盖:
1. 四种预测策略
2. 单/多结果预测
3. 置信度与置信区间
4. 边界条件（空输入、缺失参数）
5. trace 生命周期
6. ProcessRuntimeEngine 集成
"""

from __future__ import annotations

import pytest

from ocos.events.event_bus import EventBus
from ocos.runtime.context_manager import WorkingMemory
from ocos.runtime.process_runtime import ProcessRuntimeEngine
from ocos.models.process import TransformProcess, ProcessType, ProcessState
from typing import Any
from ocos.models.prediction import (
    PredictionStrategy, PredictionResult, PredictionTrace, ConfidenceInterval,
)
from ocos.engines.prediction_engine import PredictionEngine, PredictFn


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
    return PredictionEngine(event_bus, working_memory)


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


# ── 内置预测函数 ──────────────────────────────────────────────────

def _extrapolate_fn(
    input_data: dict[str, Any], strategy: PredictionStrategy,
) -> list[PredictionResult]:
    """趋势外推：假设线性增长。"""
    base = input_data.get("base", 100)
    return [
        PredictionResult(
            value=base * 1.1,
            confidence=0.85,
            label="next_period",
            interval=ConfidenceInterval(lower=base * 0.95, upper=base * 1.25),
        ),
        PredictionResult(
            value=base * 1.2,
            confidence=0.70,
            label="next_2_periods",
            interval=ConfidenceInterval(lower=base * 0.90, upper=base * 1.50),
        ),
    ]


def _regression_fn(
    input_data: dict[str, Any], strategy: PredictionStrategy,
) -> list[PredictionResult]:
    """简单回归。"""
    x = input_data.get("x", 0)
    slope = input_data.get("slope", 2.0)
    intercept = input_data.get("intercept", 1.0)
    y = slope * x + intercept
    return [
        PredictionResult(value=y, confidence=0.92, label="predicted_y"),
    ]


def _classification_fn(
    input_data: dict[str, Any], strategy: PredictionStrategy,
) -> list[PredictionResult]:
    """分类预测。"""
    features = input_data.get("features", [])
    return [
        PredictionResult(value="class_a", confidence=0.78, label=str(features)),
        PredictionResult(value="class_b", confidence=0.15, label=str(features)),
    ]


def _empty_fn(
    input_data: dict[str, Any], strategy: PredictionStrategy,
) -> list[PredictionResult]:
    """无预测结果。"""
    return []


# ═══════════════════════════════════════════════════════════════════════════════
# 1. 基本预测
# ═══════════════════════════════════════════════════════════════════════════════

class TestExtrapolation:
    """趋势外推。"""

    def test_two_predictions(self, engine):
        trace = engine.predict(
            {"base": 100}, _extrapolate_fn,
            strategy=PredictionStrategy.EXTRAPOLATION,
        )
        assert len(trace.predictions) == 2
        assert trace.predictions[0].value == pytest.approx(110.0)  # 100 * 1.1
        assert trace.predictions[1].value == pytest.approx(120.0)  # 100 * 1.2

    def test_confidence_interval(self, engine):
        trace = engine.predict(
            {"base": 100}, _extrapolate_fn,
        )
        p = trace.predictions[0]
        assert p.interval is not None
        assert p.interval.lower == 95.0
        assert p.interval.upper == 125.0
        assert p.interval.confidence_level == 0.95

    def test_summary(self, engine):
        trace = engine.predict(
            {"base": 100}, _extrapolate_fn,
            strategy=PredictionStrategy.EXTRAPOLATION,
        )
        assert "extrapolation" in trace.summary
        assert "2 predictions" in trace.summary


class TestRegression:
    """回归分析。"""

    def test_single_prediction(self, engine):
        trace = engine.predict(
            {"x": 5, "slope": 3.0, "intercept": 2.0},
            _regression_fn,
            strategy=PredictionStrategy.REGRESSION,
        )
        assert len(trace.predictions) == 1
        assert trace.predictions[0].value == pytest.approx(17.0)  # 3*5 + 2

    def test_high_confidence(self, engine):
        trace = engine.predict({"x": 10}, _regression_fn)
        assert trace.predictions[0].confidence == 0.92


class TestClassification:
    """分类预测。"""

    def test_two_classes(self, engine):
        trace = engine.predict(
            {"features": [1, 2, 3]},
            _classification_fn,
            strategy=PredictionStrategy.CLASSIFICATION,
        )
        assert len(trace.predictions) == 2
        assert trace.predictions[0].value == "class_a"

    def test_strategy_recorded(self, engine):
        trace = engine.predict(
            {"features": []}, _classification_fn,
            strategy=PredictionStrategy.CLASSIFICATION,
        )
        assert trace.strategy == PredictionStrategy.CLASSIFICATION


class TestEnsemble:
    """集成方法。"""

    def test_ensemble_strategy(self, engine):
        trace = engine.predict(
            {"base": 200}, _extrapolate_fn,
            strategy=PredictionStrategy.ENSEMBLE,
        )
        assert trace.strategy == PredictionStrategy.ENSEMBLE


# ═══════════════════════════════════════════════════════════════════════════════
# 2. 边界与错误处理
# ═══════════════════════════════════════════════════════════════════════════════

class TestEdgeCases:
    """边界条件。"""

    def test_empty_predictions(self, engine):
        trace = engine.predict({"x": 1}, _empty_fn)
        assert len(trace.predictions) == 0
        assert "0 predictions" in trace.summary

    def test_wrong_process_type(self, engine):
        p = TransformProcess(
            process_id="p-wt",
            process_type=ProcessType.LEARNING,
        )
        result = engine.execute(p)
        assert not result.success
        assert "Not a REASONING" in result.message

    def test_missing_input_data(self, engine):
        p = _make_process("p-mi")
        result = engine.execute(p, context={})
        assert not result.success
        assert "No input_data" in result.message

    def test_missing_predict_fn(self, engine):
        p = _make_process("p-mf")
        result = engine.execute(
            p, context={"input_data": {"x": 1}},
        )
        assert not result.success
        assert "No predict_fn" in result.message


# ═══════════════════════════════════════════════════════════════════════════════
# 3. 跟踪管理
# ═══════════════════════════════════════════════════════════════════════════════

class TestTraceLifecycle:
    """PredictionTrace 生命周期。"""

    def test_get_trace(self, engine):
        trace = engine.predict({"x": 1}, _extrapolate_fn)
        fetched = engine.get_trace(trace.trace_id)
        assert fetched is trace

    def test_list_traces(self, engine):
        engine.predict({"x": 1}, _extrapolate_fn)
        engine.predict({"x": 2}, _regression_fn)
        assert len(engine.list_traces()) == 2

    def test_clear_traces(self, engine):
        engine.predict({"x": 1}, _extrapolate_fn)
        engine.clear_traces()
        assert len(engine.list_traces()) == 0

    def test_trace_has_strategy(self, engine):
        trace = engine.predict(
            {"x": 1}, _extrapolate_fn,
            strategy=PredictionStrategy.REGRESSION,
        )
        assert trace.strategy == PredictionStrategy.REGRESSION


# ═══════════════════════════════════════════════════════════════════════════════
# 4. ProcessRuntimeEngine 集成
# ═══════════════════════════════════════════════════════════════════════════════

class TestRuntimeIntegration:
    """与 ProcessRuntimeEngine 协作。"""

    def test_execute_prediction(self, process_engine, engine):
        pr = process_engine.create_process(process_type=ProcessType.REASONING)
        process_engine.start_process(pr.process_id)
        p = process_engine.get_process(pr.process_id)

        result = engine.execute(p, context={
            "input_data": {"base": 100},
            "predict_fn": _extrapolate_fn,
        })

        assert result.success
        assert "2 results" in result.message
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
            "input_data": {"x": 5, "slope": 3.0, "intercept": 2.0},
            "predict_fn": _regression_fn,
            "strategy": PredictionStrategy.REGRESSION,
        })

        assert result.success
        assert "regression" in result.message
