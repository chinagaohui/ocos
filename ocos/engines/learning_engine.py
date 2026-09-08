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
    """学习引擎——领域无关的经验学习。

    L1 真实化: 快路径学习下沉 — 引擎自身可从 EpisodeStore 重放
    Episode → LearningExample → RuleBasedLearner（与 master_agent
    _fast_path_learning 同源语义），不再依赖编排层注入样本。
    治理纪律: 只写 LearningModel（内存模型），不产生 Action；
    Decision 唯一 Mutation Authority 未触碰。
    """

    def __init__(
        self,
        event_bus: EventBus,
        working_memory: WorkingMemory,
        memory_store: Any | None = None,
    ):
        self._event_bus = event_bus
        self._working_memory = working_memory
        self._models: dict[str, LearningModel] = {}
        self._traces: dict[str, LearningTrace] = {}
        # L1: 可选注入 — 快路径学习数据源
        self._memory_store = memory_store
        logger.debug("__init__ completed", component="learning_engine")

    # ── 核心学习 ──────────────────────────────────────────────────────

    def learn(
        self,
        examples: list[LearningExample],
        learn_fn: LearnFn | None = None,
        strategy: LearningStrategy = LearningStrategy.SUPERVISED,
        base_model: LearningModel | None = None,
    ) -> tuple[LearningModel, LearningTrace]:
        """执行学习，返回 (更新后模型, 学习轨迹)。

        learn_fn 为 None 时使用内置 RuleBasedLearner（与快路径同源）。
        """
        logger.info("learn", extra=dict(
            strategy=strategy.value, example_count=len(examples),
        ))
        if learn_fn is None:
            from ocos.learning.experience_learning import RuleBasedLearner
            learn_fn = RuleBasedLearner.learn_fn
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

    # ── L1 真实化: 快路径学习（Episode 重放）──────────────────────────

    def learn_from_episodes(
        self,
        batch_limit: int = 200,
        today_only: bool = True,
        base_model: LearningModel | None = None,
    ) -> dict[str, Any]:
        """快路径学习 — 重放 EpisodeStore 的 Episode 并训练规则模型。

        与 master_agent._fast_path_learning 同源语义（幂等由慢通路
        CONSOLIDATED 标记保证；本方法默认只重放 ACTIVE  episode）。

        Args:
            batch_limit: 重放窗口大小
            today_only: 仅重放今日 Episode（与快路径一致）
            base_model: 增量学习基础模型
        Returns:
            统计 dict（replayed/examples/lessons/rules/trace_id/accuracy），
            失败时含 error 键（诚实标注，不抛异常）。
        """
        stats: dict[str, Any] = {
            "fast_path": "learning_engine",
            "examples": 0,
            "lessons": 0,
            "rules": 0,
            "learning_engine": False,
        }
        if self._memory_store is None:
            stats["error"] = "memory_store unavailable"
            return stats
        try:
            from datetime import datetime, timezone
            from ocos.learning.experience_learning import (
                EpisodeExampleConverter,
                RuleBasedLearner,
            )

            episodes = self._memory_store.query_by_time(limit=batch_limit)
            if today_only:
                today_start = datetime.now(timezone.utc).replace(
                    hour=0, minute=0, second=0, microsecond=0)
                episodes = [
                    ep for ep in episodes
                    if getattr(ep, "created_at", None) is not None
                    and ep.created_at >= today_start
                    and ep.status.name != "CONSOLIDATED"
                ]
            if not episodes:
                stats["replayed"] = 0
                return stats

            examples, diagnoses, _ = EpisodeExampleConverter.convert_many(episodes)
            stats["replayed"] = len(episodes)
            stats["examples"] = len(examples)
            stats["lessons"] = len(diagnoses)
            if not examples:
                return stats

            model, trace = self.learn(
                examples=examples,
                learn_fn=RuleBasedLearner.learn_fn,
                strategy=LearningStrategy.SUPERVISED,
                base_model=base_model,
            )
            stats["models"] = 1
            stats["rules"] = len(model.rules)
            stats["trace_id"] = trace.trace_id
            stats["learning_engine"] = True
            stats["accuracy"] = model.accuracy
            stats["model_id"] = model.model_id
        except Exception as e:
            logger.warning("fast-path learning degraded: %s", e)
            stats["error"] = str(e)
        return stats

    # ── 增量更新 ──────────────────────────────────────────────────────

    def update(
        self,
        model_id: str,
        new_examples: list[LearningExample],
        learn_fn: LearnFn | None = None,
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

        # L1: 快路径 — 未注入样本时从 episode 历史重放学习
        if not examples and learn_fn is None:
            if self._memory_store is None:
                return RuntimeResult(
                    success=False,
                    process_id=process.process_id,
                    trace_id="",
                    message="No examples provided and no memory_store injected",
                )
            fast_stats = self.learn_from_episodes(
                batch_limit=(context or {}).get("batch_limit", 200),
                today_only=(context or {}).get("today_only", True),
            )
            if not fast_stats.get("learning_engine"):
                return RuntimeResult(
                    success=False,
                    process_id=process.process_id,
                    trace_id="",
                    message=f"Fast-path learning failed: {fast_stats.get('error') or 'no episodes'}",
                )
            return RuntimeResult(
                success=True,
                process_id=process.process_id,
                trace_id=fast_stats.get("trace_id", ""),
                message=f"Fast-path learning: replayed={fast_stats.get('replayed')}, "
                        f"examples={fast_stats.get('examples')}, "
                        f"rules={fast_stats.get('rules')}, "
                        f"model_id={str(fast_stats.get('model_id', ''))[:8]}",
            )

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
