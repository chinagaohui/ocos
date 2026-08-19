"""
PredictionEngine — 预测能力引擎。

Phase 19 — 第九个（最后）能力引擎。

职责:
1. 接收输入数据和可选模型
2. 调用 predict_fn 进行预测
3. 返回预测结果（含置信度）
4. 记录预测轨迹（PredictionTrace）

遵循 4 不堆叠原则：复用 ProcessType.REASONING。

使用者注入 predict_fn(input_data, strategy) → list[PredictionResult]
"""

from __future__ import annotations

import uuid
from typing import Any, Callable

from ocos.events.event_bus import EventBus
from ocos.kernel.abi import Event, EventType
from ocos.runtime.context_manager import WorkingMemory
from ocos.models.prediction import (
    PredictionStrategy, PredictionResult, PredictionTrace,
)
from ocos.models.process import TransformProcess, ProcessType

from ocos.logging import get_logger

logger = get_logger(__name__)

# 预测函数签名: (input_data, strategy) → list[PredictionResult]
PredictFn = Callable[
    [dict[str, Any], PredictionStrategy],
    list[PredictionResult],
]


class RuntimeResult:
    """预测引擎的通用结果类。"""
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


class PredictionEngine:
    """预测引擎——基于数据的未来状态推断。"""

    def __init__(
        self,
        event_bus: EventBus,
        working_memory: WorkingMemory,
    ):
        self._event_bus = event_bus
        self._working_memory = working_memory
        self._traces: dict[str, PredictionTrace] = {}
        logger.debug("__init__ completed", component="prediction_engine")

    # ── 核心预测 ──────────────────────────────────────────────────────

    def predict(
        self,
        input_data: dict[str, Any],
        predict_fn: PredictFn,
        strategy: PredictionStrategy = PredictionStrategy.EXTRAPOLATION,
    ) -> PredictionTrace:
        """执行预测，返回轨迹。"""
        logger.info("predict", extra=dict(
            strategy=strategy.value,
            input_keys=list(input_data.keys()),
        ))
        results = predict_fn(input_data, strategy)

        trace = PredictionTrace(
            trace_id=str(uuid.uuid4()),
            strategy=strategy,
            input_summary=f"keys={list(input_data.keys())}",
            predictions=tuple(results),
            summary=f"{strategy.value}: {len(results)} predictions",
        )
        self._traces[trace.trace_id] = trace
        return trace

    # ── 执行接口 ──────────────────────────────────────────────────────

    def execute(
        self,
        process: TransformProcess,
        context: dict[str, Any] | None = None,
    ) -> RuntimeResult:
        """通过 ProcessRuntimeEngine 执行预测。"""
        logger.info("execute prediction", extra=dict(
            process_id=process.process_id,
        ))
        if process.process_type != ProcessType.REASONING.value:
            return RuntimeResult(
                success=False,
                process_id=process.process_id,
                trace_id="",
                message="Not a REASONING process (Prediction reuses REASONING)",
            )

        input_data: dict | None = (context or {}).get("input_data")
        predict_fn: PredictFn | None = (context or {}).get("predict_fn")

        if not input_data:
            return RuntimeResult(
                success=False,
                process_id=process.process_id,
                trace_id="",
                message="No input_data provided",
            )
        if predict_fn is None:
            return RuntimeResult(
                success=False,
                process_id=process.process_id,
                trace_id="",
                message="No predict_fn provided",
            )

        strategy = (context or {}).get("strategy", PredictionStrategy.EXTRAPOLATION)

        self._event_bus.publish(Event(
            event_type=EventType.INFORMATION_TRANSFORMATION_STARTED,
            payload={
                "process_id": process.process_id,
                "strategy": strategy.value,
                "input_keys": list(input_data.keys()),
                "source": "prediction",
            },
        ))

        trace = self.predict(input_data, predict_fn, strategy)

        self._event_bus.publish(Event(
            event_type=EventType.INFORMATION_TRANSFORMATION_COMPLETED,
            payload={
                "process_id": process.process_id,
                "trace_id": trace.trace_id,
                "prediction_count": len(trace.predictions),
                "source": "prediction",
            },
        ))

        return RuntimeResult(
            success=True,
            process_id=process.process_id,
            trace_id=trace.trace_id,
            message=f"Prediction complete: {len(trace.predictions)} results "
                    f"using {strategy.value}",
        )

    # ── 跟踪管理 ──────────────────────────────────────────────────────

    def get_trace(self, trace_id: str) -> PredictionTrace | None:
        return self._traces.get(trace_id)

    def list_traces(self) -> list[PredictionTrace]:
        return list(self._traces.values())

    def clear_traces(self) -> None:
        self._traces.clear()

# ── Engine Manifest ──────────────────────────────────────────────────────────
from ocos.platform.engine_manifest import EngineManifest

__manifest__ = EngineManifest(
    engine_id="prediction_engine",
    name="Prediction Engine",
    version="1.0.0",
    engine_class="ocos.engines.prediction_engine.PredictionEngine",
    capabilities=['prediction'],
    dependencies=[],
    singleton=True,
    auto_load=True,
)
