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
    ConfidenceInterval,
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
    """预测引擎——基于数据的未来状态推断。

    L1 真实化: 支持内置历史统计预测器 — 从 EpisodeStore 历史
    （数值序列最小二乘外推 / 任务成功率统计）生成预测，无需注入 predict_fn。
    """

    def __init__(
        self,
        event_bus: EventBus,
        working_memory: WorkingMemory,
        memory_store: Any | None = None,
    ):
        self._event_bus = event_bus
        self._working_memory = working_memory
        self._traces: dict[str, PredictionTrace] = {}
        # L1: 可选注入 — 提供历史统计数据源
        self._memory_store = memory_store
        logger.debug("__init__ completed", component="prediction_engine")

    # ── 核心预测 ──────────────────────────────────────────────────────

    def predict(
        self,
        input_data: dict[str, Any],
        predict_fn: PredictFn | None = None,
        strategy: PredictionStrategy = PredictionStrategy.EXTRAPOLATION,
    ) -> PredictionTrace:
        """执行预测，返回轨迹。

        predict_fn 为 None 时使用内置历史统计预测器（需要 memory_store）。
        """
        logger.info("predict", extra=dict(
            strategy=strategy.value,
            input_keys=list(input_data.keys()),
        ))
        if predict_fn is None:
            has_explicit_series = isinstance(
                input_data.get("series"), (list, tuple)) and any(
                isinstance(v, (int, float)) and not isinstance(v, bool)
                for v in input_data["series"])
            if self._memory_store is None and not has_explicit_series:
                raise ValueError(
                    "predict_fn is None and no memory_store injected — "
                    "无法执行真实预测")
            predict_fn = self._history_predict
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

    # ── L1 真实化: 历史统计预测器 ─────────────────────────────────────

    def _history_predict(
        self,
        input_data: dict[str, Any],
        strategy: PredictionStrategy,
    ) -> list[PredictionResult]:
        """内置预测器 — 失败时降级为诚实标注结果，不抛异常。"""
        try:
            return self._history_predict_real(input_data, strategy)
        except Exception as e:
            logger.warning("history prediction unavailable, degraded: %s", e)
            return [PredictionResult(
                value=f"[degraded:prediction] {e}",
                confidence=0.0,
                label="degraded",
            )]

    def _history_predict_real(
        self,
        input_data: dict[str, Any],
        strategy: PredictionStrategy,
    ) -> list[PredictionResult]:
        if strategy == PredictionStrategy.CLASSIFICATION:
            return self._predict_success_rate(input_data)

        series, from_episodes = self._resolve_series(input_data)
        if len(series) < 3:
            raise RuntimeError(f"序列样本不足（{len(series)}<3），无法统计外推")
        horizon = max(1, min(30, int(input_data.get("horizon", 1) or 1)))

        if strategy == PredictionStrategy.REGRESSION:
            slope, intercept, r2, resid_std = self._linear_fit(series)
            return [PredictionResult(
                value={
                    "slope": round(slope, 6),
                    "intercept": round(intercept, 6),
                    "r2": round(r2, 4),
                    "residual_std": round(resid_std, 6),
                    "sample_size": len(series),
                },
                confidence=self._confidence_from_fit(r2, len(series)),
                label="regression",
                metadata={"method": "least_squares"},
            )]

        # EXTRAPOLATION / ENSEMBLE: 最小二乘外推未来 horizon 步
        # 成功率序列（episode 派生）截断至 [0,1]，避免外推出非法概率
        def _clamp(v: float) -> float:
            if from_episodes:
                return max(0.0, min(1.0, v))
            return v

        slope, intercept, r2, resid_std = self._linear_fit(series)
        conf = self._confidence_from_fit(r2, len(series))
        results: list[PredictionResult] = []
        for h in range(horizon):
            value = _clamp(slope * (len(series) + h) + intercept)
            margin = 1.96 * resid_std
            results.append(PredictionResult(
                value=round(value, 6),
                confidence=round(conf, 4),
                label=f"t+{h + 1}",
                interval=ConfidenceInterval(
                    lower=round(_clamp(value - margin), 6),
                    upper=round(_clamp(value + margin), 6),
                    confidence_level=0.95,
                ),
                metadata={"method": "linear_extrapolation", "r2": round(r2, 4)},
            ))
        if strategy == PredictionStrategy.ENSEMBLE:
            # 集成: 数值外推 + 任务成功率统计 双视角
            results.extend(self._predict_success_rate(input_data))
        return results

    # ── 数据源 ────────────────────────────────────────────────────────

    def _resolve_series(
        self,
        input_data: dict[str, Any],
    ) -> tuple[list[float], bool]:
        """解析数值序列 — 显式 series 优先，否则从 episode 历史按日聚合成功率。

        Returns:
            (序列, 是否为 episode 派生的成功率序列)
        """
        explicit = input_data.get("series")
        if isinstance(explicit, (list, tuple)):
            nums = [float(v) for v in explicit
                    if isinstance(v, (int, float)) and not isinstance(v, bool)]
            if len(nums) >= 2:
                return nums, False
            if explicit:
                raise RuntimeError("series 中无可用的数值元素")
        if self._memory_store is None:
            raise RuntimeError("无显式 series 且 memory_store unavailable")
        episodes = list(reversed(
            self._memory_store.query_by_time(limit=200)))  # 转为时间升序

        by_day: dict[str, tuple[int, int]] = {}  # date → (success, total)
        for ep in episodes:
            outcome = getattr(ep, "outcome", None)
            if not (isinstance(outcome, dict)
                    and isinstance(outcome.get("success"), bool)):
                continue
            created = getattr(ep, "created_at", None)
            day = created.date().isoformat() if hasattr(created, "date") else str(created)[:10]
            s, t = by_day.get(day, (0, 0))
            by_day[day] = (s + (1 if outcome["success"] else 0), t + 1)
        series = [s / t for day, (s, t) in sorted(by_day.items()) if t > 0]
        if len(series) < 2:
            raise RuntimeError("episode 历史不足以构成按日成功率序列")
        return series, True

    # ── 统计工具（纯计算，确定性）─────────────────────────────────────

    @staticmethod
    def _linear_fit(series: list[float]) -> tuple[float, float, float, float]:
        """最小二乘拟合 y = slope·x + intercept（x 为 0..n-1）。

        Returns:
            (slope, intercept, r2, residual_std)
        """
        n = len(series)
        xs = range(n)
        mean_x = (n - 1) / 2
        mean_y = sum(series) / n
        sxx = sum((x - mean_x) ** 2 for x in xs)
        sxy = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, series))
        slope = sxy / sxx if sxx else 0.0
        intercept = mean_y - slope * mean_x
        ss_tot = sum((y - mean_y) ** 2 for y in series)
        ss_res = sum(
            (y - (slope * x + intercept)) ** 2 for x, y in zip(xs, series))
        r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0
        resid_std = (ss_res / n) ** 0.5
        return slope, intercept, r2, resid_std

    @staticmethod
    def _confidence_from_fit(r2: float, n: int) -> float:
        """拟合优度 + 样本量 → 置信度（确定性映射，截断至 [0.05, 0.95]）。"""
        n_factor = n / (n + 5)
        return max(0.05, min(0.95, max(0.0, r2) * n_factor))

    def _predict_success_rate(
        self,
        input_data: dict[str, Any],
    ) -> list[PredictionResult]:
        """分类预测 — 任务描述匹配历史 episode 的成功率。"""
        if self._memory_store is None:
            raise RuntimeError("memory_store unavailable")
        task = str(input_data.get("task") or input_data.get("goal") or "").strip()
        episodes = self._memory_store.query_by_time(limit=100)
        usable: list[tuple[Any, bool]] = []
        for ep in episodes:
            outcome = getattr(ep, "outcome", None)
            if (isinstance(outcome, dict)
                    and isinstance(outcome.get("success"), bool)):
                usable.append((ep, outcome["success"]))
        if len(usable) < 3:
            raise RuntimeError(
                f"episode 成功样本不足（{len(usable)}<3），无法估计成功率")

        tokens = [t for t in task.replace("：", " ").replace(":", " ").split()
                  if len(t) >= 2]
        matched: list[bool] = []
        if task or tokens:
            for ep, s in usable:
                text = " ".join(filter(None, (
                    getattr(ep, "goal", "") or "",
                    getattr(ep, "decision", "") or "",
                    getattr(ep, "action", "") or "",
                )))
                if (task and task in text) or any(t in text for t in tokens):
                    matched.append(s)
        sample = matched if len(matched) >= 3 else [s for _, s in usable]
        method = "task_matched_history" if len(matched) >= 3 else "global_history"
        rate = sum(1 for s in sample if s) / len(sample)
        n = len(sample)
        confidence = max(0.05, min(0.95, (0.5 + abs(rate - 0.5)) * n / (n + 5)))
        return [PredictionResult(
            value={"success_probability": round(rate, 4), "samples": n},
            confidence=round(confidence, 4),
            label="success" if rate >= 0.5 else "failure",
            metadata={"method": method, "task": task[:100]},
        )]

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
        if predict_fn is None and self._memory_store is None:
            return RuntimeResult(
                success=False,
                process_id=process.process_id,
                trace_id="",
                message="No predict_fn provided and no memory_store injected",
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
