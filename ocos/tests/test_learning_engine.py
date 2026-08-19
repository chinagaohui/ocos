"""
Test suite for LearningEngine.

Phase 19 — 学习引擎测试。

覆盖:
1. 基本学习（有监督、强化）
2. 增量更新
3. 模型与跟踪管理
4. 边界（空样本、缺失 learn_fn）
5. ProcessRuntimeEngine 集成
"""

from __future__ import annotations

import pytest

from ocos.events.event_bus import EventBus
from ocos.runtime.context_manager import WorkingMemory
from ocos.runtime.process_runtime import ProcessRuntimeEngine
from ocos.models.process import TransformProcess, ProcessType, ProcessState
from ocos.models.learning import (
    LearningStrategy, LearningExample, LearningModel, LearningTrace,
)
from ocos.engines.learning_engine import LearningEngine, LearnFn


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
    return LearningEngine(event_bus, working_memory)


@pytest.fixture
def process_engine(event_bus, working_memory):
    eng = ProcessRuntimeEngine(event_bus, working_memory)
    yield eng
    eng.unsubscribe_all()


def _make_process(process_id: str) -> TransformProcess:
    return TransformProcess(
        process_id=process_id,
        process_type=ProcessType.LEARNING,
    )


# ── 内置学习函数 ──────────────────────────────────────────────────────

def _supervised_learn(
    model: LearningModel | None,
    examples: list[LearningExample],
    strategy: LearningStrategy,
) -> LearningModel:
    """有监督：从样本统计频率。"""
    counts: dict[str, int] = {}
    for ex in examples:
        k = str(ex.output_data.get("label", "?"))
        counts[k] = counts.get(k, 0) + 1

    # 合并已有参数
    params = dict(model.parameters) if model else {}
    for k, v in counts.items():
        params[k] = params.get(k, 0) + v

    total = sum(params.values())
    accuracy = max(v / total for v in params.values()) if total > 0 else 0.0

    return LearningModel(
        strategy=strategy,
        parameters=params,
        accuracy=accuracy,
    )


def _reinforcement_learn(
    model: LearningModel | None,
    examples: list[LearningExample],
    strategy: LearningStrategy,
) -> LearningModel:
    """强化：累计奖励。"""
    total_reward = sum(ex.reward or 0.0 for ex in examples)
    params = dict(model.parameters) if model else {}
    params["cumulative_reward"] = params.get("cumulative_reward", 0.0) + total_reward
    params["episodes"] = params.get("episodes", 0) + len(examples)
    return LearningModel(strategy=strategy, parameters=params)


def _pattern_discovery_learn(
    model: LearningModel | None,
    examples: list[LearningExample],
    strategy: LearningStrategy,
) -> LearningModel:
    """模式发现：提取输入特征。"""
    features: set[str] = set()
    for ex in examples:
        features.update(ex.input_data.keys())
    rules = tuple({"feature": f} for f in sorted(features))
    return LearningModel(strategy=strategy, rules=rules)


# ═══════════════════════════════════════════════════════════════════════════════
# 1. 基本学习
# ═══════════════════════════════════════════════════════════════════════════════

class TestSupervisedLearning:
    """有监督学习。"""

    def test_simple_classification(self, engine):
        examples = [
            LearningExample(input_data={"x": 1}, output_data={"label": "A"}),
            LearningExample(input_data={"x": 2}, output_data={"label": "A"}),
            LearningExample(input_data={"x": 3}, output_data={"label": "B"}),
        ]
        model, trace = engine.learn(examples, _supervised_learn)
        assert model.parameters.get("A") == 2
        assert model.parameters.get("B") == 1
        assert model.accuracy is not None and model.accuracy > 0

    def test_trace_contains_examples_count(self, engine):
        examples = [
            LearningExample(input_data={"x": 1}, output_data={"label": "A"}),
        ]
        _, trace = engine.learn(examples, _supervised_learn)
        assert trace.examples_count == 1
        assert trace.model is not None


class TestReinforcementLearning:
    """强化学习。"""

    def test_reward_accumulation(self, engine):
        examples = [
            LearningExample(input_data={"a": 1}, reward=1.0),
            LearningExample(input_data={"a": 2}, reward=0.5),
            LearningExample(input_data={"a": 3}, reward=0.0),
        ]
        model, _ = engine.learn(examples, _reinforcement_learn,
                                strategy=LearningStrategy.REINFORCEMENT)
        assert model.parameters["cumulative_reward"] == 1.5
        assert model.parameters["episodes"] == 3


class TestPatternDiscovery:
    """模式发现。"""

    def test_feature_extraction(self, engine):
        examples = [
            LearningExample(input_data={"temperature": 25, "humidity": 80}),
            LearningExample(input_data={"temperature": 30, "wind": 15}),
        ]
        model, _ = engine.learn(examples, _pattern_discovery_learn,
                                strategy=LearningStrategy.PATTERN_DISCOVERY)
        feature_names = [r["feature"] for r in model.rules]
        assert "temperature" in feature_names
        assert "humidity" in feature_names
        assert "wind" in feature_names
        assert len(feature_names) == 3


# ═══════════════════════════════════════════════════════════════════════════════
# 2. 增量更新
# ═══════════════════════════════════════════════════════════════════════════════

class TestIncrementalUpdate:
    """增量学习。"""

    def test_update_model(self, engine):
        examples1 = [
            LearningExample(input_data={"x": 1}, output_data={"label": "A"}),
        ]
        model1, _ = engine.learn(examples1, _supervised_learn)

        examples2 = [
            LearningExample(input_data={"x": 2}, output_data={"label": "B"}),
        ]
        result = engine.update(model1.model_id, examples2, _supervised_learn)
        assert result is not None
        model2, trace2 = result
        assert model2.model_id != model1.model_id
        assert model2.parameters.get("A") == 1
        assert model2.parameters.get("B") == 1

    def test_update_nonexistent_model(self, engine):
        examples = [LearningExample(input_data={"x": 1}, output_data={"label": "A"})]
        result = engine.update("no-such-model", examples, _supervised_learn)
        assert result is None


# ═══════════════════════════════════════════════════════════════════════════════
# 3. 模型与跟踪管理
# ═══════════════════════════════════════════════════════════════════════════════

class TestModelManagement:
    """模型生命周期。"""

    def test_get_model(self, engine):
        examples = [LearningExample(input_data={"x": 1}, output_data={"label": "A"})]
        model, _ = engine.learn(examples, _supervised_learn)
        assert engine.get_model(model.model_id) is model

    def test_list_models(self, engine):
        for _ in range(3):
            examples = [LearningExample(input_data={"x": 1}, output_data={"label": "A"})]
            engine.learn(examples, _supervised_learn)
        assert len(engine.list_models()) == 3

    def test_get_trace(self, engine):
        examples = [LearningExample(input_data={"x": 1}, output_data={"label": "A"})]
        _, trace = engine.learn(examples, _supervised_learn)
        assert engine.get_trace(trace.trace_id) is trace

    def test_clear_all(self, engine):
        examples = [LearningExample(input_data={"x": 1}, output_data={"label": "A"})]
        engine.learn(examples, _supervised_learn)
        engine.clear()
        assert len(engine.list_models()) == 0
        assert len(engine.list_traces()) == 0


# ═══════════════════════════════════════════════════════════════════════════════
# 4. 边界与错误处理
# ═══════════════════════════════════════════════════════════════════════════════

class TestEdgeCases:
    """边界条件。"""

    def test_empty_examples(self, engine):
        model, trace = engine.learn([], _supervised_learn)
        assert trace.examples_count == 0
        assert model.accuracy is not None

    def test_none_base_model(self, engine):
        examples = [LearningExample(input_data={"x": 1}, output_data={"label": "A"})]
        model, _ = engine.learn(examples, _supervised_learn, base_model=None)
        assert model is not None

    def test_wrong_process_type(self, engine):
        p = TransformProcess(
            process_id="p-wt",
            process_type=ProcessType.SIMULATION,
        )
        result = engine.execute(p)
        assert not result.success

    def test_missing_examples(self, engine):
        p = _make_process("p-me")
        result = engine.execute(p)
        assert not result.success
        assert "No examples" in result.message

    def test_missing_learn_fn(self, engine):
        p = _make_process("p-mf")
        examples = [LearningExample(input_data={"x": 1}, output_data={"label": "A"})]
        result = engine.execute(p, context={"examples": examples})
        assert not result.success
        assert "No learn_fn" in result.message


# ═══════════════════════════════════════════════════════════════════════════════
# 5. ProcessRuntimeEngine 集成
# ═══════════════════════════════════════════════════════════════════════════════

class TestRuntimeIntegration:
    """与 ProcessRuntimeEngine 协作。"""

    def test_execute_learning(self, process_engine, engine):
        pr = process_engine.create_process(process_type=ProcessType.LEARNING)
        process_engine.start_process(pr.process_id)
        p = process_engine.get_process(pr.process_id)

        examples = [
            LearningExample(input_data={"x": 1}, output_data={"label": "A"}),
        ]
        result = engine.execute(
            p,
            context={"examples": examples, "learn_fn": _supervised_learn},
        )
        assert result.success
        assert "Learning complete" in result.message
        assert result.trace_id

        process_engine.complete_process(pr.process_id)
        p_final = process_engine.get_process(pr.process_id)
        assert p_final.process_state == ProcessState.COMPLETED.value

    def test_process_type_creates(self, process_engine):
        pr = process_engine.create_process(process_type=ProcessType.LEARNING)
        assert pr.success
        p = process_engine.get_process(pr.process_id)
        assert p.process_type == ProcessType.LEARNING.value

    def test_execute_with_strategy(self, process_engine, engine):
        pr = process_engine.create_process(process_type=ProcessType.LEARNING)
        process_engine.start_process(pr.process_id)
        p = process_engine.get_process(pr.process_id)

        examples = [LearningExample(input_data={"a": 1}, reward=2.0)]
        result = engine.execute(
            p,
            context={
                "examples": examples,
                "learn_fn": _reinforcement_learn,
                "strategy": LearningStrategy.REINFORCEMENT,
            },
        )
        assert result.success
        assert "Learning complete" in result.message
