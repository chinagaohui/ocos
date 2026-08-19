"""
DecisionMakingEngine — 决策生成能力引擎。

Phase 19 — 第三个能力引擎。

职责:
1. 基于策略对选项进行评分/排序/选择
2. 使用 ProcessType.DECISION
3. 产生 DecisionMakingTrace 记录
4. 输出选择的选项到 output_addresses

与 Phase 18 DecisionRuntimeEngine 互补而非取代。
"""

from __future__ import annotations

import uuid
from typing import Any, Callable

from ocos.kernel.abi import Event, EventType
from ocos.events.event_bus import EventBus
from ocos.models.process import TransformProcess, ProcessType
from ocos.models.decision_making import (
    DecisionStrategy,
    DecisionOption,
    DecisionMakingTrace,
)
from ocos.runtime.context_manager import WorkingMemory

from ocos.logging import get_logger

_SOURCE = "decision_making_engine"

logger = get_logger(__name__)


class RuntimeResult:
    """决策引擎的通用结果类。"""
    def __init__(
        self,
        success: bool,
        message: str,
        trace_id: str = "",
        process_id: str = "",
        selected_option_id: str = "",
        option_count: int = 0,
        output_addresses: tuple[str, ...] = (),
    ):
        self.success = success
        self.message = message
        self.trace_id = trace_id
        self.process_id = process_id
        self.selected_option_id = selected_option_id
        self.option_count = option_count
        self.output_addresses = output_addresses

    def __repr__(self) -> str:
        return (
            f"RuntimeResult(success={self.success}, trace_id={self.trace_id!r}, "
            f"selected={self.selected_option_id!r}, options={self.option_count})"
        )


# ── 决策策略注册表 ──────────────────────────────────────────────────────────

_STRATEGY_HANDLERS: dict[DecisionStrategy, Callable] = {}


def register_decision_strategy(
    strategy: DecisionStrategy,
    handler: Callable[[list[dict[str, Any]], dict[str, Any]], tuple[list[DecisionOption], str]],
) -> None:
    """注册自定义决策策略处理器。

    Args:
        strategy: 策略类型
        handler: 接收 (options_data, context) → (options, selected_id)
    """
    _STRATEGY_HANDLERS[strategy] = handler


# ═══════════════════════════════════════════════════════════════════════════════
# DecisionMakingEngine
# ═══════════════════════════════════════════════════════════════════════════════

class DecisionMakingEngine:
    """决策生成引擎 — 为 ProcessType.DECISION 提供决策逻辑。"""

    def __init__(
        self,
        event_bus: EventBus,
        working_memory: WorkingMemory,
    ) -> None:
        self._event_bus = event_bus
        self._wm = working_memory
        self._traces: dict[str, DecisionMakingTrace] = {}
        logger.debug("__init__ completed", component="decision_making_engine")

    def __repr__(self) -> str:
        return f"DecisionMakingEngine(traces={len(self._traces)})"

    # ── 公共 API ─────────────────────────────────────────────────────────

    def execute(
        self,
        process: TransformProcess,
        strategy: str | None = None,
        options_data: list[dict[str, Any]] | None = None,
        context: dict[str, Any] | None = None,
    ) -> RuntimeResult:
        """基于 TransformProcess 执行决策。

        Args:
            process: 待决策的 process
            strategy: 决策策略覆盖
            options_data: 候选选项数据 [{label, scores}, ...]
            context: 决策上下文（权重、阈值等）

        Returns:
            RuntimeResult 包含选中的 option_id
        """
        logger.info("execute decision", extra=dict(
            process_id=process.process_id, strategy=strategy,
        ))
        if process.process_type != ProcessType.DECISION.value:
            return RuntimeResult(
                success=False,
                message=f"Not a DECISION process: {process.process_type}",
                process_id=process.process_id,
            )

        strat = self._resolve_strategy(process, strategy)
        opts_data = options_data or self._default_options_data()
        ctx = context or {}

        options, selected_id, rationale, errors = self._evaluate(
            strat, opts_data, ctx
        )

        # 输出地址
        output_addrs = (f"addr:decision:{selected_id}",) if selected_id else ()

        trace = DecisionMakingTrace(
            process_id=process.process_id,
            strategy=strat,
            options=tuple(options),
            selected_option_id=selected_id,
            input_addresses=tuple(str(a) for a in process.input_addresses),
            output_addresses=output_addrs,
            rationale=rationale,
            error="; ".join(errors) if errors else "",
        )
        self._traces[trace.trace_id] = trace

        self._event_bus.publish(Event(
            event_type=EventType.INFORMATION_TRANSFORMATION_STARTED,
            payload={
                "process_id": process.process_id,
                "process_type": ProcessType.DECISION.value,
                "strategy": strat.value,
                "option_count": len(options),
                "selected": selected_id,
                "trace_id": trace.trace_id,
            },
            source=_SOURCE,
        ))

        return RuntimeResult(
            success=not errors,
            message=f"Decision made: {selected_id} via {strat.value}"
                     + (f", errors: {errors}" if errors else ""),
            trace_id=trace.trace_id,
            process_id=process.process_id,
            selected_option_id=selected_id,
            option_count=len(options),
            output_addresses=output_addrs,
        )

    def get_trace(self, trace_id: str) -> DecisionMakingTrace | None:
        return self._traces.get(trace_id)

    def list_traces(self) -> list[DecisionMakingTrace]:
        return list(self._traces.values())

    def clear_traces(self) -> None:
        self._traces.clear()

    # ── 内部方法 ─────────────────────────────────────────────────────────

    def _resolve_strategy(
        self,
        process: TransformProcess,
        override: str | None,
    ) -> DecisionStrategy:
        if override:
            return DecisionStrategy(override)
        if process.metadata and "strategy" in process.metadata:
            try:
                return DecisionStrategy(process.metadata["strategy"])
            except ValueError:
                pass
        return DecisionStrategy.SCORING

    def _default_options_data(self) -> list[dict[str, Any]]:
        """默认提供 3 个候选选项。"""
        return [
            {"label": "Option A", "scores": {"quality": 8, "cost": 3, "risk": 4}},
            {"label": "Option B", "scores": {"quality": 6, "cost": 7, "risk": 2}},
            {"label": "Option C", "scores": {"quality": 9, "cost": 1, "risk": 8}},
        ]

    def _evaluate(
        self,
        strat: DecisionStrategy,
        options_data: list[dict[str, Any]],
        context: dict[str, Any],
    ) -> tuple[list[DecisionOption], str, str, list[str]]:
        """评估并选择最佳选项。"""
        # 自定义处理器
        if strat in _STRATEGY_HANDLERS:
            handler = _STRATEGY_HANDLERS[strat]
            try:
                opts, selected_id = handler(options_data, context)
                rationale = f"Custom {strat.value} handler: selected {selected_id}"
                return opts, selected_id, rationale, []
            except Exception as e:
                return [], "", "", [str(e)]

        return self._default_evaluate(strat, options_data, context)

    def _default_evaluate(
        self,
        strat: DecisionStrategy,
        options_data: list[dict[str, Any]],
        context: dict[str, Any],
    ) -> tuple[list[DecisionOption], str, str, list[str]]:
        """默认决策逻辑。"""
        weights = context.get("weights", {"quality": 1.0, "cost": 0.5, "risk": 0.3})

        options: list[DecisionOption] = []
        for data in options_data:
            scores = dict(data.get("scores", {}))
            total = sum(scores.get(dim, 0) * weights.get(dim, 1.0) for dim in scores)
            opt = DecisionOption(
                label=data.get("label", ""),
                scores=scores,
                total_score=round(total, 2),
            )
            options.append(opt)

        if not options:
            return [], "", "No options provided", ["no options"]

        # 根据策略选择
        if strat == DecisionStrategy.SCORING:
            selected = max(options, key=lambda o: o.total_score)
        elif strat == DecisionStrategy.RANKING:
            sorted_opts = sorted(options, key=lambda o: o.total_score, reverse=True)
            for i, o in enumerate(sorted_opts):
                options[options.index(o)] = DecisionOption(
                    label=o.label, scores=o.scores, total_score=o.total_score,
                    rank=i + 1, is_selected=(i == 0),
                )
            selected = sorted_opts[0]
        elif strat == DecisionStrategy.MAJORITY:
            selected = max(options, key=lambda o: o.total_score)
        elif strat == DecisionStrategy.SATISFICING:
            threshold = context.get("threshold", 5.0)
            selected = next((o for o in options if o.total_score >= threshold), options[0])
        elif strat == DecisionStrategy.OPPORTUNITY_COST:
            selected = max(options, key=lambda o: o.total_score)
        elif strat == DecisionStrategy.PARETO:
            # 简单实现：选总分最高的
            selected = max(options, key=lambda o: o.total_score)
        else:
            selected = options[0]

        # 标记选中的
        selected_idx = next(i for i, o in enumerate(options) if o.label == selected.label)
        options[selected_idx] = DecisionOption(
            label=selected.label, scores=selected.scores,
            total_score=selected.total_score, rank=1, is_selected=True,
        )

        rationale = f"{strat.value}: selected '{selected.label}' (score={selected.total_score:.1f})"
        return options, options[selected_idx].option_id, rationale, []


# ── 便利函数 ────────────────────────────────────────────────────────────────

def make_decision(
    engine: DecisionMakingEngine,
    process: TransformProcess,
    strategy: str | None = None,
    options: list[dict[str, Any]] | None = None,
    **context: Any,
) -> RuntimeResult:
    """简便调用的辅助函数。"""
    return engine.execute(
        process=process,
        strategy=strategy,
        options_data=options,
        context=context,
    )

# ── Engine Manifest ──────────────────────────────────────────────────────────
from ocos.platform.engine_manifest import EngineManifest

__manifest__ = EngineManifest(
    engine_id="decision_making_engine",
    name="Decision Making Engine",
    version="1.0.0",
    engine_class="ocos.engines.decision_making_engine.DecisionMakingEngine",
    capabilities=['decision_making'],
    dependencies=[],
    singleton=True,
    auto_load=True,
)
