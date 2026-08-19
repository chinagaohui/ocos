"""
GoalArbitrationEngine — 目标仲裁能力引擎。

Phase 19 — 第五个能力引擎。

职责:
1. 接收一组冲突的 GoalCandidate
2. 按指定策略仲裁：优先级/加权/紧急/资源感知
3. 输出 selected(执行) 和 suspended(挂起) 的候选
4. 产生 GoalArbitrationTrace

与 Phase 18 的 GoalRuntimeEngine 互补:
- GoalRuntimeEngine: 目标生命周期管理
- GoalArbitrationEngine: 冲突目标仲裁逻辑
"""

from __future__ import annotations

import uuid
from typing import Any, Callable

from ocos.events.event_bus import EventBus
from ocos.kernel.abi import Event, EventType
from ocos.runtime.context_manager import WorkingMemory
from ocos.models.goal_arbitration import (
    ArbitrationStrategy,
    GoalCandidate,
    ArbitrationResult,
    GoalArbitrationTrace,
)
from ocos.models.process import TransformProcess, ProcessType

from ocos.logging import get_logger

logger = get_logger(__name__)

# 类型: 自定义仲裁器
Arbitrator = Callable[
    [list[GoalCandidate], dict[str, Any]],
    list[ArbitrationResult],
]

# 四个策略的默认仲裁器注册表
_DEFAULT_ARBITRATORS: dict[ArbitrationStrategy, Arbitrator] = {}


def register_default_arbitrator(
    strategy: ArbitrationStrategy,
    fn: Arbitrator,
) -> None:
    """注册默认仲裁器。"""
    _DEFAULT_ARBITRATORS[strategy] = fn


# ── 四个内置仲裁器 ────────────────────────────────────────────────────

def _priority_arbitrator(
    candidates: list[GoalCandidate], ctx: dict[str, Any],
) -> list[ArbitrationResult]:
    """优先级仲裁：按 priority 升序排列（1=最高）。"""
    sorted_c = sorted(candidates, key=lambda c: c.priority)
    results: list[ArbitrationResult] = []
    for i, c in enumerate(sorted_c):
        score = 1.0 / (1.0 + i)
        results.append(ArbitrationResult(
            candidate_id=str(uuid.uuid4()),
            goal_id=c.goal_id, label=c.label,
            selected=i == 0, rank=i, score=score,
            reason=f"Priority={c.priority} → rank #{i + 1}",
        ))
    return results


def _weighted_arbitrator(
    candidates: list[GoalCandidate], ctx: dict[str, Any],
) -> list[ArbitrationResult]:
    """加权仲裁：按 weight × (1 - resource_cost×0.1) 评分。"""
    scored = [(c, c.weight * (1.0 - c.resource_cost * 0.1)) for c in candidates]
    scored.sort(key=lambda x: -x[1])
    results: list[ArbitrationResult] = []
    for i, (c, s) in enumerate(scored):
        results.append(ArbitrationResult(
            candidate_id=str(uuid.uuid4()),
            goal_id=c.goal_id, label=c.label,
            selected=i == 0, rank=i, score=s,
            reason=f"Weighted score={s:.2f}",
        ))
    return results


def _emergency_arbitrator(
    candidates: list[GoalCandidate], ctx: dict[str, Any],
) -> list[ArbitrationResult]:
    """紧急仲裁：按 urgency 降序排列。"""
    sorted_c = sorted(candidates, key=lambda c: -c.urgency)
    results: list[ArbitrationResult] = []
    for i, c in enumerate(sorted_c):
        results.append(ArbitrationResult(
            candidate_id=str(uuid.uuid4()),
            goal_id=c.goal_id, label=c.label,
            selected=i == 0, rank=i, score=c.urgency,
            reason=f"Urgency={c.urgency} → rank #{i + 1}",
        ))
    return results


def _resource_aware_arbitrator(
    candidates: list[GoalCandidate], ctx: dict[str, Any],
) -> list[ArbitrationResult]:
    """资源感知仲裁：最小化资源消耗的同时兼顾优先级。"""
    scored = [(c, c.priority * 1.0 / (1.0 + c.resource_cost)) for c in candidates]
    scored.sort(key=lambda x: x[1])  # 分值越低越好
    results: list[ArbitrationResult] = []
    for i, (c, s) in enumerate(scored):
        results.append(ArbitrationResult(
            candidate_id=str(uuid.uuid4()),
            goal_id=c.goal_id, label=c.label,
            selected=i == 0, rank=i, score=s,
            reason=f"Resource-aware score={s:.2f}",
        ))
    return results


register_default_arbitrator(ArbitrationStrategy.PRIORITY, _priority_arbitrator)
register_default_arbitrator(ArbitrationStrategy.WEIGHTED, _weighted_arbitrator)
register_default_arbitrator(ArbitrationStrategy.EMERGENCY, _emergency_arbitrator)
register_default_arbitrator(ArbitrationStrategy.RESOURCE_AWARE, _resource_aware_arbitrator)


class RuntimeResult:
    """仲裁引擎的通用结果类。"""
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


class GoalArbitrationEngine:
    """目标仲裁引擎。"""

    def __init__(
        self,
        event_bus: EventBus,
        working_memory: WorkingMemory,
        custom_arbitrators: dict[ArbitrationStrategy, Arbitrator] | None = None,
    ):
        self._event_bus = event_bus
        self._working_memory = working_memory
        self._arbitrators: dict[ArbitrationStrategy, Arbitrator] = {
            **_DEFAULT_ARBITRATORS,
            **(custom_arbitrators or {}),
        }
        self._traces: dict[str, GoalArbitrationTrace] = {}
        logger.debug("__init__ completed", component="goal_arbitration_engine")

    # ── 核心仲裁 ──────────────────────────────────────────────────────

    def arbitrate(
        self,
        candidates: list[GoalCandidate],
        strategy: ArbitrationStrategy = ArbitrationStrategy.PRIORITY,
        context: dict[str, Any] | None = None,
    ) -> tuple[ArbitrationResult, GoalArbitrationTrace]:
        """对候选目标执行仲裁，返回 (最佳结果, 完整跟踪)。"""
        logger.info("arbitrate", extra=dict(
            candidate_count=len(candidates), strategy=strategy.value,
        ))
        ctx = context or {}
        arbitrator = self._arbitrators.get(strategy)
        if arbitrator is None:
            logger.error("arbitrate failed: unknown strategy", extra=dict(
                strategy=strategy.value,
            ))
            raise ValueError(f"Unknown arbitration strategy: {strategy}")

        results = arbitrator(candidates, ctx)
        selected_ids = tuple(
            r.goal_id for r in results if r.selected
        )
        suspended_ids = tuple(
            r.goal_id for r in results if not r.selected
        )
        best = results[0] if results else None

        trace = GoalArbitrationTrace(
            trace_id=str(uuid.uuid4()),
            strategy=strategy,
            candidates=tuple(results),
            selected_ids=selected_ids,
            suspended_ids=suspended_ids,
            summary=f"{strategy.value}: selected {len(selected_ids)}, "
                    f"suspended {len(suspended_ids)}",
        )
        self._traces[trace.trace_id] = trace
        return best, trace

    # ── 执行接口 ──────────────────────────────────────────────────────

    def execute(
        self,
        process: TransformProcess,
        context: dict[str, Any] | None = None,
    ) -> RuntimeResult:
        """通过 ProcessRuntimeEngine 执行仲裁。"""
        logger.info("execute goal_arbitration", extra=dict(
            process_id=process.process_id,
        ))
        if process.process_type != ProcessType.ARBITRATION.value:
            return RuntimeResult(
                success=False,
                process_id=process.process_id,
                trace_id="",
                message="Not an ARBITRATION process",
            )

        candidates: list[GoalCandidate] = (context or {}).get("candidates", [])
        strategy_str: str = (context or {}).get("strategy", "priority")

        try:
            strategy = ArbitrationStrategy(strategy_str)
        except ValueError:
            strategy = ArbitrationStrategy.PRIORITY

        if not candidates:
            return RuntimeResult(
                success=False,
                process_id=process.process_id,
                trace_id="",
                message="No candidates provided for arbitration",
            )

        self._event_bus.publish(Event(
            event_type=EventType.INFORMATION_TRANSFORMATION_STARTED,
            payload={
                "process_id": process.process_id,
                "strategy": strategy.value,
                "source": "arbitration",
            },
        ))

        best, trace = self.arbitrate(candidates, strategy, context)

        self._event_bus.publish(Event(
            event_type=EventType.INFORMATION_TRANSFORMATION_COMPLETED,
            payload={
                "process_id": process.process_id,
                "selected": list(trace.selected_ids),
                "source": "arbitration",
            },
        ))

        return RuntimeResult(
            success=True,
            process_id=process.process_id,
            trace_id=trace.trace_id,
            message=f"Arbitration complete: selected={best.goal_id}",
        )

    # ── 跟踪管理 ──────────────────────────────────────────────────────

    def get_trace(self, trace_id: str) -> GoalArbitrationTrace | None:
        return self._traces.get(trace_id)

    def list_traces(self) -> list[GoalArbitrationTrace]:
        return list(self._traces.values())

    def clear_traces(self) -> None:
        self._traces.clear()

# ── Engine Manifest ──────────────────────────────────────────────────────────
from ocos.platform.engine_manifest import EngineManifest

__manifest__ = EngineManifest(
    engine_id="goal_arbitration_engine",
    name="Goal Arbitration Engine",
    version="1.0.0",
    engine_class="ocos.engines.goal_arbitration_engine.GoalArbitrationEngine",
    capabilities=['goal_arbitration'],
    dependencies=[],
    singleton=True,
    auto_load=True,
)
