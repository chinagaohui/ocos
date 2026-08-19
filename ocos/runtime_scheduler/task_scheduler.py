"""Phase 51.2: TaskScheduler — 主调度循环。

核心循环:
    while running:
        1. collect runnable stages (from clock.schedules)
        2. sort by priority
        3. backpressure check
        4. execute (via worker)
        5. record result
        6. checkpoint if needed

RS51-01: Scheduler ≠ Brain — 只调度，不做认知决策。
RS51-05: 与 Persistence (51.1) 集成 — checkpoint 时保存调度器状态。
"""

from __future__ import annotations

import time as _time
from dataclasses import dataclass, field
from typing import Any, Callable

from ocos.runtime_scheduler.scheduler_types import (
    Tick, Priority, SchedulerTask, TaskStatus,
    SchedulerStatus, SchedulerStats, TickSchedule, BackpressureState,
)
from ocos.runtime_scheduler.cognitive_clock import CognitiveClock
from ocos.runtime_scheduler.priority_queue import PriorityQueue


@dataclass
class TaskScheduler:
    """OCOS 运行时调度器。

    用法:
        scheduler = TaskScheduler()
        scheduler.register_stage("perception", my_perception_fn, Priority.CRITICAL, every=1)
        scheduler.register_stage("memory_consolidation", my_memory_fn, Priority.LOW, every=100)
        scheduler.run(max_ticks=1000)  # 模拟运行
    """

    clock: CognitiveClock = field(default_factory=CognitiveClock)
    queue: PriorityQueue = field(default_factory=PriorityQueue)
    stats: SchedulerStats = field(default_factory=SchedulerStats)
    backpressure: BackpressureState = field(default_factory=BackpressureState)

    # Stage 注册表: stage_name → (fn, default_priority)
    _stages: dict[str, Callable[[], Any]] = field(default_factory=dict)

    # 回调
    on_task_complete: Callable[[SchedulerTask], None] | None = None
    on_task_fail: Callable[[SchedulerTask], None] | None = None
    on_tick: Callable[[Tick], None] | None = None
    on_checkpoint: Callable[[int], None] | None = None  # RS51-05

    # 配置
    checkpoint_interval: int = 1000
    _running: bool = False
    _paused: bool = False

    # ── Stage Registration ──

    def register_stage(
        self,
        name: str,
        fn: Callable[[], Any],
        priority: Priority = Priority.MEDIUM,
        every: int = 1,
    ) -> None:
        """注册一个 cognitive stage。"""
        self._stages[name] = fn
        self.clock.register_schedule(
            TickSchedule(name=name, stage=name, every=every, priority=priority)
        )

    def register_schedule(self, schedule: TickSchedule) -> None:
        self.clock.register_schedule(schedule)

    # ── Run Loop ──

    def run(self, max_ticks: int = 0) -> SchedulerStats:
        """运行调度器主循环。

        max_ticks=0 表示无限运行 (需要外部 stop)。
        """
        self._running = True
        self.stats.status = SchedulerStatus.RUNNING

        tick_count = 0
        while self._running:
            if max_ticks > 0 and tick_count >= max_ticks:
                break

            if self._paused:
                _time.sleep(0.001)  # 暂停时不消耗 CPU
                continue

            tick = self.clock.advance()
            tick_count += 1
            self.stats.total_ticks += 1

            if self.on_tick:
                self.on_tick(tick)

            # 1. 收集周期任务
            self._enqueue_due_schedules(tick)

            # 2. 背压检查 RS51-04
            self._check_backpressure()

            # 3. 执行队列中任务
            self._drain_queue()

            # 4. Checkpoint RS51-05
            if tick.number > 0 and tick.number % self.checkpoint_interval == 0:
                self._checkpoint(tick)

        self.stats.status = SchedulerStatus.STOPPED
        return self.stats

    def stop(self) -> None:
        """停止调度器。"""
        self._running = False

    def pause(self) -> None:
        self._paused = True
        self.stats.status = SchedulerStatus.PAUSED

    def resume(self) -> None:
        self._paused = False
        self.stats.status = SchedulerStatus.RUNNING

    # ── Task Execution ──

    def submit(self, task: SchedulerTask) -> None:
        """提交一次性任务。"""
        self.queue.push(task)
        self.stats.total_tasks += 1

    # ── Internal ──

    def _enqueue_due_schedules(self, tick: Tick) -> None:
        """将到期周期任务入队。"""
        for schedule in self.clock.due_schedules(tick):
            fn = self._stages.get(schedule.stage)
            if fn is None:
                continue
            task = SchedulerTask(
                task_id=f"{schedule.name}-t{tick.number}",
                stage=schedule.stage,
                priority=schedule.priority,
                tick=tick.number,
                fn=fn,
            )
            # 背压检查
            if self.backpressure.active and self.backpressure.should_reject(schedule.priority):
                task.status = TaskStatus.BACKPRESSURED
                self.stats.backpressured_tasks += 1
                self.backpressure.deferred_count += 1
                continue

            self.queue.push(task)
            self.stats.total_tasks += 1
            self.clock.mark_completed(schedule, tick)

    def _drain_queue(self) -> None:
        """执行队列中所有任务。"""
        while not self.queue.is_empty:
            task = self.queue.pop()
            if task is None:
                break
            self._execute(task)

    def _execute(self, task: SchedulerTask) -> None:
        """执行单个任务。RS51-01: 不能 create_goal。"""
        task.status = TaskStatus.RUNNING
        task.started_at = _time.time()

        try:
            if task.fn:
                task.result = task.fn()
            task.status = TaskStatus.COMPLETED
            self.stats.completed_tasks += 1
            if self.on_task_complete:
                self.on_task_complete(task)
        except Exception as e:
            task.error = str(e)
            if task.retries < task.max_retries:
                task.retries += 1
                task.status = TaskStatus.PENDING
                self.queue.push(task)
            else:
                task.status = TaskStatus.FAILED
                self.stats.failed_tasks += 1
                if self.on_task_fail:
                    self.on_task_fail(task)
        finally:
            task.finished_at = _time.time()
            # 更新延迟统计
            n = self.stats.completed_tasks + self.stats.failed_tasks
            if n > 0:
                self.stats.avg_task_latency = (
                    (self.stats.avg_task_latency * (n - 1) + task.elapsed) / n
                )
            self.stats.current_queue_depth = self.queue.depth

    def _check_backpressure(self) -> None:
        """RS51-04: 背压管理。"""
        depth = self.queue.depth
        self.backpressure.queue_depth = depth

        if not self.backpressure.active and depth > self.backpressure.high_watermark:
            self.backpressure.active = True
            self.backpressure.triggered_at_tick = self.clock.current.number
            self.stats.status = SchedulerStatus.BACKPRESSURED

        elif self.backpressure.active and depth < self.backpressure.low_watermark:
            self.backpressure.active = False
            self.stats.status = SchedulerStatus.RUNNING

    def _checkpoint(self, tick: Tick) -> None:
        """RS51-05: 调度器状态 checkpoint。"""
        if self.on_checkpoint:
            self.on_checkpoint(tick.number)

    # ── State for Persistence ──

    def get_state(self) -> dict[str, Any]:
        """RS51-05: 导出调度器状态用于持久化。"""
        return {
            "current_tick": self.clock.current.number,
            "elapsed": self.clock.elapsed,
            "total_tasks": self.stats.total_tasks,
            "completed": self.stats.completed_tasks,
            "failed": self.stats.failed_tasks,
            "backpressured": self.stats.backpressured_tasks,
            "status": self.stats.status.value,
            "schedules": [
                {"name": s.name, "last_run": s.last_run, "every": s.every}
                for s in self.clock.schedules
            ],
        }

    def set_state(self, data: dict[str, Any]) -> None:
        """RS51-05: 从持久化恢复调度器状态。"""
        tick_num = data.get("current_tick", 0)
        self.clock.current = Tick(tick_num)
        self.stats.total_tasks = data.get("total_tasks", 0)
        self.stats.completed_tasks = data.get("completed", 0)
        self.stats.failed_tasks = data.get("failed", 0)
        self.stats.backpressured_tasks = data.get("backpressured", 0)

        # 恢复 schedule 的 last_run
        saved_schedules = {s["name"]: s["last_run"] for s in data.get("schedules", [])}
        for s in self.clock.schedules:
            if s.name in saved_schedules:
                s.last_run = saved_schedules[s.name]


__all__ = ["TaskScheduler"]
