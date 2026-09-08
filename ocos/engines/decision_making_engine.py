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
        memory_store: Any | None = None,
        text_generator: Any | None = None,
    ) -> None:
        self._event_bus = event_bus
        self._wm = working_memory
        self._traces: dict[str, DecisionMakingTrace] = {}
        # L1: 可选注入 — 缺省时懒加载（生产路径 get_text_generator 缓存）
        self._memory_store = memory_store
        self._text_generator = text_generator
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
            # L1 诚实降级语义: fallback（维度投票等）产出有效决策 → success=True，
            # 降级事实保留在 trace.error 与 message，不把降级伪装成失败
            success=bool(selected_id),
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

        errors: list[str] = []
        rationale = ""

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
        elif strat == DecisionStrategy.SATISFICING:
            threshold = context.get("threshold", 5.0)
            selected = next((o for o in options if o.total_score >= threshold), options[0])
        elif strat in (DecisionStrategy.MAJORITY,
                       DecisionStrategy.OPPORTUNITY_COST,
                       DecisionStrategy.PARETO):
            # L1 真实化: 真分支优先，降级保留确定性选择（诚实标注 degraded）
            try:
                selected, rationale = self._real_select(strat, options, context)
            except Exception as e:
                logger.warning("real decision unavailable (%s), degraded: %s",
                               strat.value, e)
                selected, rationale = self._fallback_select(strat, options)
                errors.append(f"degraded: {e}")
        else:
            selected = options[0]

        # 标记选中的
        selected_idx = next(i for i, o in enumerate(options) if o.label == selected.label)
        options[selected_idx] = DecisionOption(
            label=selected.label, scores=selected.scores,
            total_score=selected.total_score, rank=1, is_selected=True,
        )

        rationale = (rationale or
                     f"{strat.value}: selected '{selected.label}' "
                     f"(score={selected.total_score:.1f})")
        return options, options[selected_idx].option_id, rationale, errors

    # ── L1 真实化: 三策略真分支 / 降级 ──────────────────────────────────

    # 这些维度数值越低越好（Pareto/多数投票/效用计算时取负向）
    _LOWER_IS_BETTER = {"cost", "risk", "effort", "latency", "time", "expense"}
    DEFAULT_WEIGHTS = {"quality": 1.0, "cost": 0.5, "risk": 0.3}

    @classmethod
    def _utility(
        cls,
        o: DecisionOption,
        weights: dict[str, float],
    ) -> float:
        """方向感知加权效用 — 负向维度（cost/risk 等）取反。"""
        return sum(
            v * weights.get(d, 1.0)
            * (-1.0 if d.lower() in cls._LOWER_IS_BETTER else 1.0)
            for d, v in o.scores.items()
        )

    def _real_select(
        self,
        strat: DecisionStrategy,
        options: list[DecisionOption],
        context: dict[str, Any],
    ) -> tuple[DecisionOption, str]:
        """三策略真分支。

        Raises:
            Exception: LLM/记忆不可用或数据不足（调用方降级）
        """
        weights = context.get("weights", self.DEFAULT_WEIGHTS)
        if strat == DecisionStrategy.MAJORITY:
            return self._select_by_majority(options, weights)
        if strat == DecisionStrategy.OPPORTUNITY_COST:
            return self._select_by_opportunity_cost(options, weights)
        return self._select_by_pareto(options, weights)

    # ── MAJORITY: LLM 三评审（质量/成本/风险）投票 ──────────────────────

    def _select_by_majority(
        self,
        options: list[DecisionOption],
        weights: dict[str, float],
    ) -> tuple[DecisionOption, str]:
        votes = self._llm_majority_votes(options)
        tally: dict[str, int] = {}
        for v in votes:
            tally[v] = tally.get(v, 0) + 1
        max_votes = max(tally.values())
        tied = [o for o in options if tally.get(o.label, 0) == max_votes]
        selected = max(tied, key=lambda o: self._utility(o, weights))
        rationale = (
            f"majority: 评审投票 {tally} → '{selected.label}'"
            + ("（平票以方向感知效用决胜）" if len(tied) > 1 else "")
        )
        return selected, rationale

    def _llm_majority_votes(self, options: list[DecisionOption]) -> list[str]:
        """LLM 三评审投票，返回有效票 label 列表。

        Raises:
            Exception: LLM 不可用或有效票不足
        """
        import asyncio

        if self._text_generator is None:
            from ocos.engines.text_generator import get_text_generator
            self._text_generator = get_text_generator()
        provider = self._text_generator.provider
        if not getattr(provider, "available", False):
            raise RuntimeError("LLM provider unavailable")

        opts_block = "\n".join(
            f"- {o.label}: 维度分 {o.scores}（加权总分 {o.total_score}）"
            for o in options
        )
        prompt = (
            "对以下候选选项进行三方评审投票：质量官（重 quality）、"
            "成本官（重 cost，越低越好）、风险官（重 risk，越低越好）。\n"
            f"候选:\n{opts_block}\n\n"
            "每人投一票给最推荐的选项，输出 3 行，格式严格为:\n"
            "VOTE|<选项label>\n不要输出解释。"
        )
        raw = asyncio.run(provider.generate(
            prompt,
            system_prompt="你是 OCOS 的决策引擎。只输出 VOTE 行。",
            temperature=0.2, max_tokens=200))
        labels = {o.label for o in options if o.label}
        votes: list[str] = []
        for line in raw.splitlines():
            line = line.strip().strip("`")
            if line.startswith("VOTE|"):
                v = line.split("|", 1)[1].strip()
                if v in labels:
                    votes.append(v)
        if len(votes) < 2:
            raise RuntimeError(f"LLM 有效票不足（{len(votes)}<2）")
        return votes

    # ── OPPORTUNITY_COST: episode 历史成功率 × 期望收益 ─────────────────

    def _select_by_opportunity_cost(
        self,
        options: list[DecisionOption],
        weights: dict[str, float],
    ) -> tuple[DecisionOption, str]:
        rates, global_rate = self._episode_success_rates(options)
        evs: list[tuple[DecisionOption, float, float]] = []
        for o in options:
            rate = rates.get(o.label, global_rate)
            utility = self._utility(o, weights)
            evs.append((o, utility * rate, rate))
        best = max(evs, key=lambda x: x[1])
        alternatives = [x for x in evs if x[0] is not best[0]]
        alt = max(alternatives, key=lambda x: x[1]) if alternatives else None
        opportunity_cost = (best[1] - alt[1]) if alt else 0.0
        rate_detail = "、".join(
            f"{o.label}成功率 {r:.2f}" for o, _, r in evs) or "无历史"
        rationale = (
            f"opportunity_cost: 选用 '{best[0].label}' "
            f"(EV={best[1]:.2f} = 效用 {self._utility(best[0], weights):.2f} "
            f"× 成功率 {best[2]:.2f})，"
            f"放弃 '{alt[0].label}' (EV={alt[1]:.2f})，"
            f"机会成本差 {opportunity_cost:.2f}；[{rate_detail}]"
            if alt else
            f"opportunity_cost: 选用 '{best[0].label}' (EV={best[1]:.2f})；[{rate_detail}]"
        )
        return best[0], rationale

    def _episode_success_rates(
        self,
        options: list[DecisionOption],
    ) -> tuple[dict[str, float], float]:
        """从 episode 记忆估计每个选项的历史成功率。

        Returns:
            (按选项匹配的成功率, 全局成功率)

        Raises:
            Exception: 记忆库不可用或可判成功与否的样本不足
        """
        if self._memory_store is None:
            raise RuntimeError("memory_store unavailable")
        episodes = self._memory_store.query_by_time(limit=100)

        def _ok(ep: Any) -> bool | None:
            outcome = getattr(ep, "outcome", None)
            if isinstance(outcome, dict) and isinstance(outcome.get("success"), bool):
                return outcome["success"]
            return None

        samples = [(ep, _ok(ep)) for ep in episodes]
        usable = [(ep, s) for ep, s in samples if s is not None]
        if len(usable) < 3:
            raise RuntimeError(
                f"episode 成功样本不足（{len(usable)}<3），无法估计期望收益")
        global_rate = sum(1 for _, s in usable if s) / len(usable)

        rates: dict[str, float] = {}
        for o in options:
            label = (o.label or "").strip()
            tokens = [t for t in label.replace("：", " ").replace(":", " ").split()
                      if len(t) >= 2]
            matched: list[bool] = []
            for ep, s in usable:
                text = " ".join(filter(None, (
                    getattr(ep, "goal", "") or "",
                    getattr(ep, "decision", "") or "",
                    getattr(ep, "action", "") or "",
                )))
                if (label and label in text) or any(t in text for t in tokens):
                    matched.append(s)
            if len(matched) >= 3:
                rates[o.label] = sum(1 for s in matched if s) / len(matched)
        return rates, global_rate

    # ── PARETO: 真实非支配排序（纯计算，无 LLM 依赖）────────────────────

    def _select_by_pareto(
        self,
        options: list[DecisionOption],
        weights: dict[str, float],
    ) -> tuple[DecisionOption, str]:
        dims = sorted({d for o in options for d in o.scores})
        if not dims:
            raise RuntimeError("no score dimensions for pareto")

        def vec(o: DecisionOption) -> tuple[float, ...]:
            # 越低越好的维度取负，统一为“越大越好”
            return tuple(
                o.scores.get(d, 0.0) * (-1.0 if d.lower() in self._LOWER_IS_BETTER else 1.0)
                for d in dims
            )

        vecs = {o.option_id: vec(o) for o in options}
        front: list[DecisionOption] = []
        for o in options:
            v = vecs[o.option_id]
            dominated = any(
                all(w >= z for w, z in zip(vecs[q.option_id], v))
                and any(w > z for w, z in zip(vecs[q.option_id], v))
                for q in options if q.option_id != o.option_id
            )
            if not dominated:
                front.append(o)
        if not front:
            raise RuntimeError("pareto front empty（异常）")
        # 非支配前沿内以方向感知效用决胜
        selected = max(front, key=lambda o: self._utility(o, weights))
        rationale = (
            f"pareto: 非支配前沿 {[o.label for o in front]}，"
            f"前沿内效用最高 '{selected.label}' "
            f"(utility={self._utility(selected, weights):.2f})"
        )
        return selected, rationale

    # ── 降级分支（确定性，诚实标注）─────────────────────────────────────

    def _fallback_select(
        self,
        strat: DecisionStrategy,
        options: list[DecisionOption],
    ) -> tuple[DecisionOption, str]:
        """降级选择 — 不依赖 LLM/记忆库的确定性逻辑。"""
        weights = self.DEFAULT_WEIGHTS
        if strat == DecisionStrategy.MAJORITY:
            # 维度多数投票：每个维度最优者得一票，票多者当选（平票以效用决胜）
            dims = sorted({d for o in options for d in o.scores})
            tally: dict[str, int] = {}
            for d in dims:
                lower = d.lower() in self._LOWER_IS_BETTER
                best = (min if lower else max)(
                    options, key=lambda o: o.scores.get(d, 0.0))
                tally[best.label] = tally.get(best.label, 0) + 1
            max_votes = max(tally.values()) if tally else 0
            tied = [o for o in options if tally.get(o.label, 0) == max_votes] or options
            selected = max(tied, key=lambda o: self._utility(o, weights))
            return selected, (
                f"[degraded:majority] 维度投票 {tally} → '{selected.label}'")
        if strat == DecisionStrategy.OPPORTUNITY_COST:
            # 无历史数据 → 期望收益退化为方向感知效用
            selected = max(options, key=lambda o: self._utility(o, weights))
            return selected, (
                f"[degraded:opportunity_cost] 无历史成功率数据，"
                f"退化为方向感知效用 → '{selected.label}'")
        # PARETO 真分支为纯计算，仅维度缺失才会到此
        selected = max(options, key=lambda o: self._utility(o, weights))
        return selected, (
            f"[degraded:pareto] 无有效评分维度，退化为方向感知效用 → '{selected.label}'")


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
