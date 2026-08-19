"""Phase 51.2: SchedulerHealth — 调度器健康监控。

监控指标:
    - Tick 连续性 (无跳号)
    - 队列深度
    - 任务延迟
    - Worker 状态
    - 背压状态

不干预运行，只报告。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ocos.runtime_scheduler.scheduler_types import (
    Tick, SchedulerStats, SchedulerStatus,
)


@dataclass
class SchedulerHealth:
    """调度器健康监控器。"""

    stats: SchedulerStats = field(default_factory=SchedulerStats)
    last_tick: Tick = field(default_factory=lambda: Tick(-1))

    # 告警阈值
    max_queue_depth: int = 200
    max_task_latency: float = 5.0
    max_failure_rate: float = 0.1  # 10%

    def check(self, current: Tick, stats: SchedulerStats) -> dict:
        """检查健康状况，返回报告。"""
        issues: list[str] = []
        warnings: list[str] = []

        # 1. Tick 连续性 RS51-02
        if self.last_tick.number >= 0:
            gap = current.number - self.last_tick.number
            if gap > 1:
                issues.append(f"Tick gap detected: {current.number - gap} → {current.number} (gap={gap})")
                stats.skipped_ticks += gap - 1
            elif gap == 0:
                issues.append(f"Duplicate tick: {current.number}")
                stats.duplicate_ticks += 1

        self.last_tick = current

        # 2. 队列深度
        if stats.current_queue_depth > self.max_queue_depth:
            warnings.append(
                f"Queue depth {stats.current_queue_depth} > {self.max_queue_depth}"
            )

        # 3. 任务延迟
        if stats.avg_task_latency > self.max_task_latency:
            warnings.append(
                f"Avg task latency {stats.avg_task_latency:.2f}s > {self.max_task_latency}s"
            )

        # 4. 失败率
        total = stats.completed_tasks + stats.failed_tasks
        if total > 0:
            rate = stats.failed_tasks / total
            if rate > self.max_failure_rate:
                issues.append(
                    f"Failure rate {rate:.1%} > {self.max_failure_rate:.0%}"
                )

        # 5. 状态检查
        if stats.status == SchedulerStatus.BACKPRESSURED:
            warnings.append("Scheduler in backpressure")
        elif stats.status == SchedulerStatus.DEGRADED:
            warnings.append("Scheduler degraded")

        return {
            "tick": current.number,
            "healthy": len(issues) == 0,
            "issues": issues,
            "warnings": warnings,
            "queue_depth": stats.current_queue_depth,
            "avg_latency": round(stats.avg_task_latency, 4),
            "status": stats.status.value,
        }

    def reset(self) -> None:
        """重置监控状态。"""
        self.last_tick = Tick(-1)


__all__ = ["SchedulerHealth"]
