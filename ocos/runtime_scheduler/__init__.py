"""Phase 51.2: Runtime Scheduler.

OCOS 的心跳控制器 — 让认知循环按照时间和优先级稳定运行。

分工裁决（AUD-F2, 2026-08-30）:
    本包 = 独立任务心跳调度器（CognitiveClock/PriorityQueue/Backpressure/
    WorkerManager，Phase 51.2 契约，test_phase51_2 锁定），当前无生产消费者，
    候选接入点 = ResidentRuntime 任务队列需要背压时。
    ocos/runtime/scheduler.py = tick 内 stage 级事件分发器（B3，生产在用）。
    两者非重复实现，不合并。

核心能力:
    - CognitiveClock: tick 编号、时间推进、周期触发
    - PriorityQueue: 优先级排序 (CRITICAL > HIGH > MEDIUM > LOW)
    - TaskScheduler: 主调度循环
    - BackpressureManager: 过载保护 (RS51-04)
    - WorkerManager: 模块执行隔离
    - SchedulerHealth: 健康监控

边界:
    RS51-01: Scheduler ≠ Brain — 不能 create_goal/modify_memory/make_decision
    RS51-02: Tick Stability — 连续、无重复、无丢失
    RS51-03: Priority Handling — 用户请求优先于系统维护
    RS51-04: Backpressure — 过载降级不崩溃
    RS51-05: Persistence Integration — 与 51.1 完整联动

典型用法:

    from ocos.runtime_scheduler import TaskScheduler, CognitiveClock, Priority

    scheduler = TaskScheduler()
    scheduler.register_stage("perception", my_perception, Priority.CRITICAL, every=1)
    scheduler.register_stage("memory_consolidation", my_memory, Priority.LOW, every=100)
    scheduler.run(max_ticks=10000)
"""

from ocos.runtime_scheduler.scheduler_types import (
    Priority, Tick,
    TaskStatus, SchedulerTask,
    TickSchedule,
    SchedulerStatus, SchedulerStats,
    WorkerStatus, Worker,
    BackpressureState,
)

from ocos.runtime_scheduler.cognitive_clock import CognitiveClock
from ocos.runtime_scheduler.priority_queue import PriorityQueue
from ocos.runtime_scheduler.task_scheduler import TaskScheduler
from ocos.runtime_scheduler.backpressure import BackpressureManager
from ocos.runtime_scheduler.worker_manager import WorkerManager
from ocos.runtime_scheduler.scheduler_health import SchedulerHealth


__all__ = [
    # Types
    "Priority", "Tick",
    "TaskStatus", "SchedulerTask",
    "TickSchedule",
    "SchedulerStatus", "SchedulerStats",
    "WorkerStatus", "Worker",
    "BackpressureState",
    # Core
    "CognitiveClock",
    "PriorityQueue",
    "TaskScheduler",
    "BackpressureManager",
    "WorkerManager",
    "SchedulerHealth",
]
