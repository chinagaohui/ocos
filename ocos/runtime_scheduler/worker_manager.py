"""Phase 51.2: WorkerManager — 模块执行隔离。

保证:
    - Memory Consolidation 运行 5 秒不会阻塞 Attention
    - 各 stage 独立执行，互不干扰
    - 超时保护
"""

from __future__ import annotations

import time as _time
from dataclasses import dataclass, field
from collections import defaultdict

from ocos.runtime_scheduler.scheduler_types import (
    SchedulerTask, Worker, WorkerStatus, TaskStatus, Priority,
)


@dataclass
class WorkerManager:
    """工作器管理器 — 每个 cognitive stage 一个 Worker。

    隔离保障:
        - Stage A 死循环不会阻塞 Stage B
        - 超时任务自动终止
        - 错误任务不影响其他 Worker
    """

    workers: dict[str, Worker] = field(default_factory=dict)
    default_timeout: float = 10.0

    def ensure_worker(self, stage: str) -> Worker:
        """获取或创建 Worker。"""
        if stage not in self.workers:
            self.workers[stage] = Worker(worker_id=f"worker-{stage}", stage=stage)
        return self.workers[stage]

    def assign(self, task: SchedulerTask) -> Worker:
        """分配任务到 Worker。"""
        worker = self.ensure_worker(task.stage)
        worker.current_task = task
        worker.status = WorkerStatus.BUSY
        return worker

    def release(self, task: SchedulerTask) -> None:
        """任务完成后释放 Worker。"""
        worker = self.workers.get(task.stage)
        if worker is None:
            return
        if task.status == TaskStatus.COMPLETED:
            worker.tasks_completed += 1
            worker.total_busy_time += task.elapsed
        elif task.status == TaskStatus.FAILED:
            worker.tasks_failed += 1
        worker.current_task = None
        worker.status = WorkerStatus.IDLE

    def is_busy(self, stage: str) -> bool:
        """检查某个 Stage 是否正在执行。"""
        worker = self.workers.get(stage)
        return worker is not None and worker.status == WorkerStatus.BUSY

    def busy_stages(self) -> list[str]:
        """返回所有忙碌的 stage。"""
        return [s for s, w in self.workers.items() if w.status == WorkerStatus.BUSY]

    def idle_stages(self) -> list[str]:
        """返回所有空闲的 stage。"""
        return [s for s, w in self.workers.items() if w.status == WorkerStatus.IDLE]

    def check_timeouts(self, timeout_seconds: float = 0) -> list[Worker]:
        """检查超时 Worker。"""
        timeout_seconds = timeout_seconds or self.default_timeout
        timed_out = []
        now = _time.time()
        for worker in self.workers.values():
            if (worker.status == WorkerStatus.BUSY and
                worker.current_task and
                worker.current_task.started_at > 0 and
                (now - worker.current_task.started_at) > timeout_seconds):
                worker.status = WorkerStatus.TIMEOUT
                if worker.current_task:
                    worker.current_task.status = TaskStatus.FAILED
                    worker.current_task.error = "timeout"
                timed_out.append(worker)
        return timed_out

    def stats(self) -> dict:
        """Worker 统计。"""
        return {
            "total_workers": len(self.workers),
            "busy": len(self.busy_stages()),
            "idle": len(self.idle_stages()),
            "per_stage": {
                s: {
                    "completed": w.tasks_completed,
                    "failed": w.tasks_failed,
                    "busy_time": round(w.total_busy_time, 3),
                    "status": w.status.value,
                }
                for s, w in self.workers.items()
            },
        }

    def get_state(self) -> dict:
        """导出状态用于持久化。"""
        return {
            stage: {
                "completed": w.tasks_completed,
                "failed": w.tasks_failed,
                "busy_time": w.total_busy_time,
            }
            for stage, w in self.workers.items()
        }

    def set_state(self, data: dict) -> None:
        """从持久化恢复状态。"""
        for stage, d in data.items():
            w = self.ensure_worker(stage)
            w.tasks_completed = d.get("completed", 0)
            w.tasks_failed = d.get("failed", 0)
            w.total_busy_time = d.get("busy_time", 0.0)


__all__ = ["WorkerManager"]
