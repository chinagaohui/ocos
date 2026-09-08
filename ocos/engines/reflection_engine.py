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
    """反思引擎——对过去过程进行回顾分析。

    L1 真实化: 支持内置 lesson 反思器 — 直接从 EpisodeStore 的
    lesson 管道（source='lesson'）与失败 Episode（FailureDiagnoser 归因）
    生成洞见，无需调用方注入 reflect_fn。
    """

    def __init__(
        self,
        event_bus: EventBus,
        working_memory: WorkingMemory,
        memory_store: Any | None = None,
    ):
        self._event_bus = event_bus
        self._working_memory = working_memory
        self._traces: dict[str, ReflectionTrace] = {}
        # L1: 可选注入 — 提供 lesson 管道数据源
        self._memory_store = memory_store
        logger.debug("__init__ completed", component="reflection_engine")

    # ── 核心反思 ──────────────────────────────────────────────────────

    def reflect(
        self,
        subject_type: str,
        subject_id: str,
        reflect_fn: ReflectFn | None,
        strategy: ReflectionStrategy = ReflectionStrategy.CRITICAL,
    ) -> ReflectionTrace:
        """执行反思，返回轨迹。

        reflect_fn 为 None 时使用内置 lesson 反思器（需要 memory_store）。
        """
        logger.info("reflect", extra=dict(
            subject_type=subject_type, subject_id=subject_id,
            strategy=strategy.value,
        ))
        if reflect_fn is None:
            if self._memory_store is None:
                raise ValueError(
                    "reflect_fn is None and no memory_store injected — "
                    "无法执行真实反思")
            reflect_fn = self._lesson_reflect
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

    # ── L1 真实化: 内置 lesson 管道反思器 ─────────────────────────────

    def _lesson_reflect(
        self,
        subject_type: str,
        subject_id: str,
        strategy: ReflectionStrategy,
    ) -> list[ReflectionInsight]:
        """从真实记忆管道生成反思洞见（确定性，无 LLM）。

        数据源:
          1. lesson episodes（source='lesson'，LessonsLearned 合成产物）
          2. 失败 Episode → FailureDiagnoser 结构化归因 → 失败原因分布

        反思器自身失败时降级为单条诚实标注洞见，不抛异常。
        """
        try:
            return self._lesson_reflect_real(subject_type, subject_id, strategy)
        except Exception as e:
            logger.warning("lesson reflection unavailable, degraded: %s", e)
            return [ReflectionInsight(
                category="错误",
                description=f"[degraded:reflection] lesson 管道不可用: {e}",
                evidence="",
                severity="warning",
                recommendation="检查 EpisodeStore 初始化与 lesson 数据源",
            )]

    def _lesson_reflect_real(
        self,
        subject_type: str,
        subject_id: str,
        strategy: ReflectionStrategy,
    ) -> list[ReflectionInsight]:
        insights: list[ReflectionInsight] = []
        store = self._memory_store
        if store is None:
            raise RuntimeError("memory_store unavailable")

        # 1. 合成教训（lesson 管道）
        lessons = store.query_by_source("lesson", limit=20)
        for ep in lessons:
            context = getattr(ep, "context", None) or {}
            tags = list(getattr(ep, "tags", None) or [])
            category = (
                context.get("lesson_type", "") if isinstance(context, dict) else ""
            ) or (tags[1] if len(tags) > 1 else "") or "模式"
            outcome = getattr(ep, "outcome", None) or {}
            predicted = outcome.get("predicted", "") if isinstance(outcome, dict) else ""
            decision = getattr(ep, "decision", "") or ""
            action = getattr(ep, "action", "") or ""
            if not decision:
                continue
            insights.append(ReflectionInsight(
                category=category,
                description=decision,
                evidence=str(getattr(ep, "id", "")),
                severity="info",
                recommendation=action or predicted,
                metadata={
                    "source": "lesson",
                    "condition": getattr(ep, "condition", "") or "",
                    "confidence": outcome.get("confidence", "")
                    if isinstance(outcome, dict) else "",
                },
            ))

        # 2. 失败 Episode → 结构化归因（P5.1: failure_lesson 统计管道）
        from ocos.learning.experience_learning import FailureDiagnoser

        episodes = store.query_by_time(limit=100)
        cause_stats: dict[str, dict[str, Any]] = {}
        success_count = 0
        failure_count = 0
        for ep in episodes:
            outcome = getattr(ep, "outcome", None)
            success = outcome.get("success") if isinstance(outcome, dict) else None
            if success is True:
                success_count += 1
                continue
            if success is not False:
                continue
            failure_count += 1
            diag = FailureDiagnoser.diagnose(ep)
            if diag is None:
                continue
            stat = cause_stats.setdefault(diag.cause.value, {
                "count": 0, "hypothesis": diag.hypothesis, "evidence": [],
            })
            stat["count"] += 1
            if len(stat["evidence"]) < 2:
                stat["evidence"].append(str(getattr(ep, "id", "")))

        for cause, stat in sorted(
                cause_stats.items(), key=lambda kv: -kv[1]["count"]):
            insights.append(ReflectionInsight(
                category="错误",
                description=(
                    f"失败原因 {cause} 出现 {stat['count']} 次: "
                    f"{stat['hypothesis']}"),
                evidence=",".join(stat["evidence"]),
                severity="critical" if stat["count"] >= 3 else "warning",
                recommendation=self._cause_recommendation(cause),
                metadata={"source": "failure_diagnosis", "cause": cause,
                          "count": stat["count"]},
            ))

        # 3. 策略补充洞见
        if strategy == ReflectionStrategy.COMPARATIVE and (
                success_count or failure_count):
            insights.append(ReflectionInsight(
                category="验证",
                description=(
                    f"预期 vs 实际: 近期 {success_count + failure_count} 条经历中 "
                    f"成功 {success_count}、失败 {failure_count} "
                    f"(成功率 {success_count / (success_count + failure_count):.0%})"),
                evidence=f"episodes[{subject_type}:{subject_id}]",
                severity="info",
                metadata={"source": "comparative", "success": success_count,
                          "failure": failure_count},
            ))
        elif strategy == ReflectionStrategy.CAUSAL and cause_stats:
            top = next(iter(cause_stats))
            insights.append(ReflectionInsight(
                category="模式",
                description=(
                    f"因果主导失败原因为 '{top}'（{cause_stats[top]['count']} 次），"
                    "同类失败集中于单一原因提示系统性缺陷而非偶发"),
                evidence=",".join(cause_stats[top]["evidence"]),
                severity="warning",
                metadata={"source": "causal", "dominant_cause": top},
            ))

        if not insights:
            insights.append(ReflectionInsight(
                category="验证",
                description="lesson 管道无可用教训与失败记录（近期无失败、无合成教训）",
                evidence="",
                severity="info",
            ))
        return insights

    @staticmethod
    def _cause_recommendation(cause: str) -> str:
        """按失败原因给出确定性改进建议。"""
        return {
            "ambiguous_task": "细化目标描述（补充数据源/产出物），再转执行",
            "permission_denied": "确认审批模式或补白名单，避免重复拦截",
            "timeout": "拆分长任务或调大超时窗口",
            "tool_unavailable": "注册缺失能力或改用可用工具",
            "llm_conversion_failed": "优化任务措辞或更换执行模型",
            "execution_error": "查看 stderr 明细，修复执行层问题",
            "unknown": "补充失败文本信号以便归因",
        }.get(cause, "人工复核该类失败")

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
        if reflect_fn is None and self._memory_store is None:
            return RuntimeResult(
                success=False,
                process_id=process.process_id,
                trace_id="",
                message="No reflect_fn provided and no memory_store injected",
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
