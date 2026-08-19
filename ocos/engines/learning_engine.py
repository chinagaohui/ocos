"""
LearningEngine — 学习能力引擎。

Phase 19 — 第七个能力引擎。

职责:
1. 接收训练样本 + 可选基础模型
2. 调用 learn_fn(模型, 样本) 更新模型
3. 记录学习轨迹（LearningTrace）
4. 支持多种策略（有监督 / 强化 / 模式发现 / 迁移）

使用者注入 learn_fn(model, examples) → LearningModel
"""

from __future__ import annotations

import uuid
from typing import Any, Callable

from ocos.events.event_bus import EventBus
from ocos.kernel.abi import Event, EventType
from ocos.runtime.context_manager import WorkingMemory
from ocos.models.learning import (
    LearningStrategy, LearningExample, LearningModel, LearningTrace,
)
from ocos.models.process import TransformProcess, ProcessType

from ocos.logging import get_logger

logger = get_logger(__name__)

# 学习函数签名: (current_model | None, examples, strategy) → LearningModel
LearnFn = Callable[
    [LearningModel | None, list[LearningExample], LearningStrategy],
    LearningModel,
]


class RuntimeResult:
    """学习引擎的通用结果类。"""
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


class LearningEngine:
    """学习引擎——领域无关的经验学习。"""

    def __init__(
        self,
        event_bus: EventBus,
        working_memory: WorkingMemory,
    ):
        self._event_bus = event_bus
        self._working_memory = working_memory
        self._models: dict[str, LearningModel] = {}
        self._traces: dict[str, LearningTrace] = {}
        logger.debug("__init__ completed", component="learning_engine")

    # ── 核心学习 ──────────────────────────────────────────────────────

    def learn(
        self,
        examples: list[LearningExample],
        learn_fn: LearnFn,
        strategy: LearningStrategy = LearningStrategy.SUPERVISED,
        base_model: LearningModel | None = None,
    ) -> tuple[LearningModel, LearningTrace]:
        """执行学习，返回 (更新后模型, 学习轨迹)。"""
        logger.info("learn", extra=dict(
            strategy=strategy.value, example_count=len(examples),
        ))
        model = learn_fn(base_model, examples, strategy)
        self._models[model.model_id] = model

        trace = LearningTrace(
            trace_id=str(uuid.uuid4()),
            strategy=strategy,
            examples_count=len(examples),
            model=model,
            summary=f"{strategy.value}: {len(examples)} examples -> "
                    f"model_id={model.model_id[:8]}",
        )
        self._traces[trace.trace_id] = trace
        return model, trace

    # ── 增量更新 ──────────────────────────────────────────────────────

    def update(
        self,
        model_id: str,
        new_examples: list[LearningExample],
        learn_fn: LearnFn,
    ) -> tuple[LearningModel, LearningTrace] | None:
        """在已有模型上增量学习。"""
        base_model = self._models.get(model_id)
        if base_model is None:
            return None
        return self.learn(new_examples, learn_fn, base_model.strategy, base_model)

    # ── 执行接口 ──────────────────────────────────────────────────────

    def execute(
        self,
        process: TransformProcess,
        context: dict[str, Any] | None = None,
    ) -> RuntimeResult:
        """通过 ProcessRuntimeEngine 执行学习。"""
        logger.info("execute learning", extra=dict(
            process_id=process.process_id,
        ))
        if process.process_type != ProcessType.LEARNING.value:
            return RuntimeResult(
                success=False,
                process_id=process.process_id,
                trace_id="",
                message="Not a LEARNING process",
            )

        examples: list[LearningExample] | None = (context or {}).get("examples")
        learn_fn: LearnFn | None = (context or {}).get("learn_fn")

        if not examples:
            return RuntimeResult(
                success=False,
                process_id=process.process_id,
                trace_id="",
                message="No examples provided",
            )
        if learn_fn is None:
            return RuntimeResult(
                success=False,
                process_id=process.process_id,
                trace_id="",
                message="No learn_fn provided",
            )

        strategy = (context or {}).get("strategy", LearningStrategy.SUPERVISED)
        base_model_id = (context or {}).get("base_model_id")
        base_model = self._models.get(base_model_id) if base_model_id else None

        self._event_bus.publish(Event(
            event_type=EventType.INFORMATION_TRANSFORMATION_STARTED,
            payload={
                "process_id": process.process_id,
                "strategy": strategy.value if strategy else "supervised",
                "examples": len(examples),
                "source": "learning",
            },
        ))

        model, trace = self.learn(examples, learn_fn, strategy, base_model)

        self._event_bus.publish(Event(
            event_type=EventType.INFORMATION_TRANSFORMATION_COMPLETED,
            payload={
                "process_id": process.process_id,
                "trace_id": trace.trace_id,
                "model_id": model.model_id,
                "source": "learning",
            },
        ))

        return RuntimeResult(
            success=True,
            process_id=process.process_id,
            trace_id=trace.trace_id,
            message=f"Learning complete: {len(examples)} examples, "
                    f"model_id={model.model_id[:8]}",
        )

    # ── 模型与跟踪管理 ────────────────────────────────────────────────

    def get_model(self, model_id: str) -> LearningModel | None:
        return self._models.get(model_id)

    def list_models(self) -> list[LearningModel]:
        return list(self._models.values())

    def get_trace(self, trace_id: str) -> LearningTrace | None:
        return self._traces.get(trace_id)

    def list_traces(self) -> list[LearningTrace]:
        return list(self._traces.values())

    def clear(self) -> None:
        self._models.clear()
        self._traces.clear()

# ── Engine Manifest ──────────────────────────────────────────────────────────
from ocos.platform.engine_manifest import EngineManifest

__manifest__ = EngineManifest(
    engine_id="learning_engine",
    name="Learning Engine",
    version="1.0.0",
    engine_class="ocos.engines.learning_engine.LearningEngine",
    capabilities=['learning'],
    dependencies=[],
    singleton=True,
    auto_load=True,
)
