"""
ReflectionEngine — 反思能力引擎。

Phase 19 — 第八个能力引擎。

职责:
1. 对指定对象（过程/轨迹/结果）进行反思
2. 调用 reflect_fn 产出一组洞见
3. 记录反思轨迹（ReflectionTrace）

使用者注入 reflect_fn(subject_type, subject_id, strategy) → list[ReflectionInsight]
"""

from __future__ import annotations

import uuid
from typing import Any, Callable

from ocos.events.event_bus import EventBus
from ocos.kernel.abi import Event, EventType
from ocos.runtime.context_manager import WorkingMemory
from ocos.models.reflection import (
    ReflectionStrategy, ReflectionInsight, ReflectionTrace,
)
from ocos.models.process import TransformProcess, ProcessType

from ocos.logging import get_logger

logger = get_logger(__name__)

# 反思函数签名: (subject_type, subject_id, strategy) → list[ReflectionInsight]
ReflectFn = Callable[
    [str, str, ReflectionStrategy],
    list[ReflectionInsight],
]


class RuntimeResult:
    """反思引擎的通用结果类。"""
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


class ReflectionEngine:
    """反思引擎——对过去过程进行回顾分析。"""

    def __init__(
        self,
        event_bus: EventBus,
        working_memory: WorkingMemory,
    ):
        self._event_bus = event_bus
        self._working_memory = working_memory
        self._traces: dict[str, ReflectionTrace] = {}
        logger.debug("__init__ completed", component="reflection_engine")

    # ── 核心反思 ──────────────────────────────────────────────────────

    def reflect(
        self,
        subject_type: str,
        subject_id: str,
        reflect_fn: ReflectFn,
        strategy: ReflectionStrategy = ReflectionStrategy.CRITICAL,
    ) -> ReflectionTrace:
        """执行反思，返回轨迹。"""
        logger.info("reflect", extra=dict(
            subject_type=subject_type, subject_id=subject_id,
            strategy=strategy.value,
        ))
        insights = reflect_fn(subject_type, subject_id, strategy)

        trace = ReflectionTrace(
            trace_id=str(uuid.uuid4()),
            strategy=strategy,
            subject_type=subject_type,
            subject_id=subject_id,
            insights=tuple(insights),
            summary=f"{strategy.value}: {len(insights)} insights on {subject_type}({subject_id[:8]})",
        )
        self._traces[trace.trace_id] = trace
        return trace

    # ── 执行接口 ──────────────────────────────────────────────────────

    def execute(
        self,
        process: TransformProcess,
        context: dict[str, Any] | None = None,
    ) -> RuntimeResult:
        """通过 ProcessRuntimeEngine 执行反思。"""
        logger.info("execute reflection", extra=dict(
            process_id=process.process_id,
        ))
        if process.process_type != ProcessType.REASONING.value:
            return RuntimeResult(
                success=False,
                process_id=process.process_id,
                trace_id="",
                message="Not a REASONING process (Reflection reuses REASONING)",
            )

        subject_type: str | None = (context or {}).get("subject_type")
        subject_id: str | None = (context or {}).get("subject_id")
        reflect_fn: ReflectFn | None = (context or {}).get("reflect_fn")

        if not subject_type or not subject_id:
            return RuntimeResult(
                success=False,
                process_id=process.process_id,
                trace_id="",
                message="subject_type and subject_id required",
            )
        if reflect_fn is None:
            return RuntimeResult(
                success=False,
                process_id=process.process_id,
                trace_id="",
                message="No reflect_fn provided",
            )

        strategy = (context or {}).get("strategy", ReflectionStrategy.CRITICAL)

        self._event_bus.publish(Event(
            event_type=EventType.INFORMATION_TRANSFORMATION_STARTED,
            payload={
                "process_id": process.process_id,
                "strategy": strategy.value,
                "subject_type": subject_type,
                "subject_id": subject_id,
                "source": "reflection",
            },
        ))

        trace = self.reflect(subject_type, subject_id, reflect_fn, strategy)

        self._event_bus.publish(Event(
            event_type=EventType.INFORMATION_TRANSFORMATION_COMPLETED,
            payload={
                "process_id": process.process_id,
                "trace_id": trace.trace_id,
                "insight_count": len(trace.insights),
                "source": "reflection",
            },
        ))

        return RuntimeResult(
            success=True,
            process_id=process.process_id,
            trace_id=trace.trace_id,
            message=f"Reflection complete: {len(trace.insights)} insights on "
                    f"{subject_type}({subject_id[:8]})",
        )

    # ── 跟踪管理 ──────────────────────────────────────────────────────

    def get_trace(self, trace_id: str) -> ReflectionTrace | None:
        return self._traces.get(trace_id)

    def list_traces(self) -> list[ReflectionTrace]:
        return list(self._traces.values())

    def clear_traces(self) -> None:
        self._traces.clear()

# ── Engine Manifest ──────────────────────────────────────────────────────────
from ocos.platform.engine_manifest import EngineManifest

__manifest__ = EngineManifest(
    engine_id="reflection_engine",
    name="Reflection Engine",
    version="1.0.0",
    engine_class="ocos.engines.reflection_engine.ReflectionEngine",
    capabilities=['reflection'],
    dependencies=[],
    singleton=True,
    auto_load=True,
)
