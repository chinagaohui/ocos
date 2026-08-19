"""Phase 51.2: Runtime Scheduler — Types.

OCOS 的心跳控制器。

不是智能。不是决策者。只是：
    负责让 OCOS 的认知循环按照时间和优先级稳定运行。

核心边界:
    RS51-01: Scheduler ≠ Brain — 不能 create_goal / modify_memory / make_decision
    RS51-02: Tick Stability — tick 连续、无重复、无丢失
    RS51-03: Priority Handling — 用户请求 > 系统维护
    RS51-04: Backpressure — 过载时降级不崩溃
    RS51-05: Persistence Integration — 与 51.1 生命周期联动
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, IntEnum
from typing import Any, Callable
import time as _time


# ═══════════════════════════════════════════════════════════════════════════════
# Priority
# ═══════════════════════════════════════════════════════════════════════════════


class Priority(IntEnum):
    """任务优先级。

    注意: Priority ≠ Desire — 只是资源分配顺序。
    """
    CRITICAL = 0    # 用户请求、系统告警
    HIGH = 1        # Goal 维护、Attention 更新
    MEDIUM = 2      # Memory 整理、能力调用
    LOW = 3         # 统计报告、后台清理
    BACKGROUND = 4  # 知识老化、长期维护


# ═══════════════════════════════════════════════════════════════════════════════
# Tick
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass(order=True, frozen=True)
class Tick:
    """不可变 tick — RS51-02: 连续、不可变。"""
    number: int = 0
    timestamp: float = field(default_factory=_time.time, compare=False)

    def __add__(self, n: int) -> Tick:
        return Tick(number=self.number + n)

    def __sub__(self, other: Tick) -> int:
        return self.number - other.number


# ═══════════════════════════════════════════════════════════════════════════════
# Task / Stage
# ═══════════════════════════════════════════════════════════════════════════════


class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    BACKPRESSURED = "backpressured"  # RS51-04: 过载时推迟


@dataclass
class SchedulerTask:
    """调度器任务。

    RS51-01: task 不能是 create_goal/modify_memory/make_decision。
    只调度认知阶段: perception/attention/working_memory/decision/action/feedback。
    """
    task_id: str = ""
    stage: str = ""                   # cognitive loop stage name
    priority: Priority = Priority.MEDIUM
    tick: int = 0
    fn: Callable[[], Any] | None = None  # 实际执行函数
    status: TaskStatus = TaskStatus.PENDING
    retries: int = 0
    max_retries: int = 2
    timeout_seconds: float = 10.0
    created_at: float = field(default_factory=_time.time)
    started_at: float = 0.0
    finished_at: float = 0.0
    result: Any = None
    error: str = ""

    @property
    def is_done(self) -> bool:
        return self.status in (
            TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED,
        )

    @property
    def elapsed(self) -> float:
        if self.finished_at and self.started_at:
            return self.finished_at - self.started_at
        if self.started_at:
            return _time.time() - self.started_at
        return 0.0


# ═══════════════════════════════════════════════════════════════════════════════
# Clock / Schedule
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class TickSchedule:
    """周期性 tick 任务定义。

    例如:
        TickSchedule("memory_consolidation", every=100, priority=Priority.LOW)
        每 100 tick 执行一次 memory consolidation。
    """
    name: str = ""
    stage: str = ""
    every: int = 1          # 每 N tick 执行一次
    priority: Priority = Priority.MEDIUM
    offset: int = 0         # 起始偏移
    last_run: int = -1      # 上次执行 tick

    def should_run(self, tick: int) -> bool:
        if self.last_run < 0:
            return tick >= self.offset
        return tick - self.last_run >= self.every


# ═══════════════════════════════════════════════════════════════════════════════
# Scheduler Status
# ═══════════════════════════════════════════════════════════════════════════════


class SchedulerStatus(Enum):
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    PAUSED = "paused"
    BACKPRESSURED = "backpressured"  # RS51-04
    DEGRADED = "degraded"
    STOPPING = "stopping"


@dataclass
class SchedulerStats:
    """调度器运行时统计。"""
    total_ticks: int = 0
    total_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    backpressured_tasks: int = 0    # RS51-04
    skipped_ticks: int = 0          # RS51-02
    duplicate_ticks: int = 0        # RS51-02
    avg_task_latency: float = 0.0
    current_queue_depth: int = 0
    status: SchedulerStatus = SchedulerStatus.STOPPED


# ═══════════════════════════════════════════════════════════════════════════════
# Worker
# ═══════════════════════════════════════════════════════════════════════════════


class WorkerStatus(Enum):
    IDLE = "idle"
    BUSY = "busy"
    TIMEOUT = "timeout"
    ERROR = "error"


@dataclass
class Worker:
    """工作器 — 模块执行隔离。

    每个 Worker 绑定一个 cognitive stage，独立执行，不阻塞其他 stage。
    """
    worker_id: str = ""
    stage: str = ""
    status: WorkerStatus = WorkerStatus.IDLE
    current_task: SchedulerTask | None = None
    tasks_completed: int = 0
    tasks_failed: int = 0
    total_busy_time: float = 0.0


# ═══════════════════════════════════════════════════════════════════════════════
# Backpressure State
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class BackpressureState:
    """RS51-04: 背压状态。

    当队列深度超过阈值，启动背压:
        - 拒绝低优先级任务
        - 推迟 MEDIUM 任务
        - 只接受 HIGH/CRITICAL
    """
    active: bool = False
    queue_depth: int = 0
    high_watermark: int = 100    # 超过此值触发背压
    low_watermark: int = 30      # 低于此值解除背压
    rejected_count: int = 0
    deferred_count: int = 0
    triggered_at_tick: int = 0

    def should_reject(self, priority: Priority) -> bool:
        """RS51-04: 过载时拒绝低优先级任务。"""
        if not self.active:
            return False
        return priority >= Priority.LOW  # LOW & BACKGROUND rejected


__all__ = [
    "Priority", "Tick",
    "TaskStatus", "SchedulerTask",
    "TickSchedule",
    "SchedulerStatus", "SchedulerStats",
    "WorkerStatus", "Worker",
    "BackpressureState",
]
