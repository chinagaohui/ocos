"""Phase 58.0: RuntimeExaminer — 运行时健康检查。

监测 24h 模拟指标:
    - CPU 趋势
    - Memory 趋势
    - Event Queue 深度
    - Scheduler 延迟
    - Tick 延迟
"""

from __future__ import annotations
from dataclasses import dataclass, field
import time

from ocos.health_examination.health_model import (
    HealthCategory, CategoryScore, RuntimeMetrics,
)


@dataclass
class RuntimeExaminer:
    """运行时健康检查器。"""

    # 阈值
    max_queue_depth: int = 1000
    max_scheduler_latency_ms: float = 500.0
    max_tick_latency_ms: float = 100.0
    max_memory_growth_per_tick: float = 10.0  # KB/tick

    def collect_metrics(self, sim_engine) -> RuntimeMetrics:
        """从模拟引擎采集运行时指标。"""
        stats = sim_engine.stats()

        # CPU 趋势 (基于错误率)
        error_rate = stats.get("errors", 0) / max(stats.get("total_ticks", 1), 1)
        if error_rate < 0.01:
            cpu_trend = "stable"
        elif error_rate < 0.05:
            cpu_trend = "increasing"
        else:
            cpu_trend = "spiky"

        # Memory 趋势 (基于记忆增长)
        mem_count = stats.get("memory_records", 0)
        if mem_count < 5000:
            mem_trend = "stable"
        else:
            mem_trend = "leaking"  # 实际需要更精确的检测

        queue_depth = stats.get("event_queue_depth", 0)

        return RuntimeMetrics(
            cpu_trend=cpu_trend,
            memory_trend=mem_trend,
            queue_depth=queue_depth,
            queue_blocked=queue_depth > self.max_queue_depth,
            scheduler_latency_ms=stats.get("avg_latency_ms", 0.0),
            tick_latency_ms=stats.get("tick_latency_ms", 0.0),
            uptime_ticks=stats.get("total_ticks", 0),
        )

    def examine(self, metrics: RuntimeMetrics | None = None,
                sim_engine=None) -> CategoryScore:
        """评估运行健康。"""
        if metrics is None and sim_engine:
            metrics = self.collect_metrics(sim_engine)

        if metrics is None:
            return CategoryScore(
                category=HealthCategory.RUNTIME,
                raw_score=15.0, max_score=15.0, normalized=1.0,
                details={"status": "no runtime data — assumed healthy"},
            )

        deductions = 0.0
        warnings = []

        if metrics.cpu_trend == "spiky":
            deductions += 5.0
            warnings.append(f"CPU spiky")
        elif metrics.cpu_trend == "increasing":
            deductions += 2.0
            warnings.append(f"CPU increasing")

        if metrics.memory_trend == "leaking":
            deductions += 5.0
            warnings.append("memory leaking")

        if metrics.queue_blocked:
            deductions += 3.0
            warnings.append(f"queue blocked: depth={metrics.queue_depth}")

        if metrics.scheduler_latency_ms > self.max_scheduler_latency_ms:
            deductions += 2.0
            warnings.append(f"scheduler latency high: {metrics.scheduler_latency_ms}ms")

        if metrics.tick_latency_ms > self.max_tick_latency_ms:
            deductions += 2.0
            warnings.append(f"tick latency high: {metrics.tick_latency_ms}ms")

        score = max(0.0, 15.0 - deductions)
        return CategoryScore(
            category=HealthCategory.RUNTIME,
            raw_score=score,
            max_score=15.0,
            normalized=score / 15.0,
            details={
                "cpu_trend": metrics.cpu_trend,
                "memory_trend": metrics.memory_trend,
                "queue_depth": metrics.queue_depth,
                "scheduler_latency_ms": metrics.scheduler_latency_ms,
                "uptime_ticks": metrics.uptime_ticks,
            },
            warnings=warnings,
        )


__all__ = ["RuntimeExaminer"]
