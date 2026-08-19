"""MetricsCollector — Agent 运行时轻量级指标收集器。

字段设计原则：
- 可观测性不改变运行时行为（无副作用）
- 所有计数器安全自增（无锁需求 — CPython GIL 保护 int）
- 延迟精度：毫秒级（time.monotonic）
"""

from __future__ import annotations

import logging
import time
from threading import Lock
from typing import Any

logger = logging.getLogger(__name__)

_SAMPLE_RATE_DEFAULT = 0.1  # 10% 采样率（高性能模式时自动降采样）


class EngineMetrics:
    """单引擎的运行时指标。"""

    __slots__ = (
        "engine_name",
        "total_calls",
        "success_calls",
        "failed_calls",
        "total_latency_ms",
        "min_latency_ms",
        "max_latency_ms",
        "_lock",
    )

    def __init__(self, engine_name: str) -> None:
        self.engine_name = engine_name
        self.total_calls = 0
        self.success_calls = 0
        self.failed_calls = 0
        self.total_latency_ms = 0.0
        self.min_latency_ms = 0.0
        self.max_latency_ms = 0.0
        self._lock = Lock()

    def record(self, success: bool, latency_ms: float) -> None:
        with self._lock:
            self.total_calls += 1
            if success:
                self.success_calls += 1
            else:
                self.failed_calls += 1
            self.total_latency_ms += latency_ms
            if self.min_latency_ms == 0 or latency_ms < self.min_latency_ms:
                self.min_latency_ms = round(latency_ms, 1)
            if latency_ms > self.max_latency_ms:
                self.max_latency_ms = round(latency_ms, 1)

    @property
    def avg_latency_ms(self) -> float:
        if self.total_calls == 0:
            return 0.0
        return round(self.total_latency_ms / self.total_calls, 1)

    @property
    def success_rate(self) -> float:
        if self.total_calls == 0:
            return 1.0
        return round(self.success_calls / self.total_calls, 3)

    def to_dict(self) -> dict[str, Any]:
        return {
            "engine_name": self.engine_name,
            "total_calls": self.total_calls,
            "success_calls": self.success_calls,
            "failed_calls": self.failed_calls,
            "success_rate": self.success_rate,
            "avg_latency_ms": self.avg_latency_ms,
            "min_latency_ms": self.min_latency_ms,
            "max_latency_ms": self.max_latency_ms,
        }

    def reset(self) -> None:
        with self._lock:
            self.total_calls = 0
            self.success_calls = 0
            self.failed_calls = 0
            self.total_latency_ms = 0.0
            self.min_latency_ms = 0.0
            self.max_latency_ms = 0.0

    def __repr__(self) -> str:
        return (
            f"EngineMetrics({self.engine_name}, "
            f"calls={self.total_calls}, "
            f"sr={self.success_rate}, "
            f"avg={self.avg_latency_ms}ms)"
        )


class MetricsCollector:
    """聚合引擎指标收集器。

    用法:
        collector = MetricsCollector()
        with collector.measure("planner"):
            result = planner.execute(...)
    """

    def __init__(self, sample_rate: float = _SAMPLE_RATE_DEFAULT) -> None:
        self._engines: dict[str, EngineMetrics] = {}
        self._sample_rate = sample_rate
        self._global_start = time.monotonic()

    def for_engine(self, name: str) -> EngineMetrics:
        """获取或创建引擎指标。"""
        if name not in self._engines:
            self._engines[name] = EngineMetrics(name)
        return self._engines[name]

    def measure(self, engine_name: str):
        """上下文管理器：自动记录时间+结果。

        用法:
            with collector.measure("writer") as ctx:
                result = engine.execute(...)
            # ctx.success / ctx.latency_ms 自动设置
        """
        return _MeasureContext(self, engine_name)

    def snapshot(self) -> dict[str, Any]:
        """获取所有引擎状态的快照。"""
        uptime = round(time.monotonic() - self._global_start, 1)
        return {
            "uptime_seconds": uptime,
            "engine_count": len(self._engines),
            "engines": {
                name: metrics.to_dict()
                for name, metrics in sorted(self._engines.items())
            },
            "total_calls": sum(
                m.total_calls for m in self._engines.values()
            ),
            "total_failures": sum(
                m.failed_calls for m in self._engines.values()
            ),
        }

    def reset_all(self) -> None:
        """重置所有指标（不清除引擎注册）。"""
        for m in self._engines.values():
            m.reset()

    def __repr__(self) -> str:
        return f"MetricsCollector(engines={len(self._engines)}, sample_rate={self._sample_rate})"


class _MeasureContext:
    """measure() 的上下文管理器。"""

    __slots__ = ("_collector", "_engine_name", "success", "latency_ms", "_start")

    def __init__(self, collector: MetricsCollector, engine_name: str) -> None:
        self._collector = collector
        self._engine_name = engine_name
        self.success = True
        self.latency_ms = 0.0
        self._start = 0.0

    def __enter__(self):
        self._start = time.monotonic()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        elapsed = time.monotonic() - self._start
        self.latency_ms = round(elapsed * 1000, 1)
        self.success = exc_type is None
        metrics = self._collector.for_engine(self._engine_name)
        metrics.record(success=self.success, latency_ms=self.latency_ms)
        if exc_type is not None:
            logger.debug(
                f"Metrics: {self._engine_name} failed in "
                f"{self.latency_ms}ms: {exc_val}"
            )
