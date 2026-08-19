"""Phase 51.2: PriorityQueue — 优先级排序的任务队列。

RS51-03: 用户请求(CRITICAL) > Goal维护(HIGH) > Memory整理(MEDIUM) > 后台(LOW/BG)

注意: Priority ≠ Desire — 只是资源分配顺序，不做价值判断。
"""

from __future__ import annotations

import heapq
from dataclasses import dataclass, field
from itertools import count

from ocos.runtime_scheduler.scheduler_types import (
    SchedulerTask, Priority, TaskStatus,
)


@dataclass
class PriorityQueue:
    """基于 heapq 的优先级队列。

    排序: Priority → 创建时间 (FIFO within same priority)
    RS51-03: CRITICAL 优先于 HIGH 优先于 MEDIUM 优先于 LOW
    """

    _heap: list[tuple[int, int, SchedulerTask]] = field(default_factory=list)
    _counter: count = field(default_factory=count)  # FIFO tiebreaker

    def push(self, task: SchedulerTask) -> None:
        """入队。优先级越低越先执行。"""
        heapq.heappush(
            self._heap,
            (task.priority.value, next(self._counter), task),
        )

    def pop(self) -> SchedulerTask | None:
        """出队最高优先级任务。"""
        if not self._heap:
            return None
        _, _, task = heapq.heappop(self._heap)
        return task

    def peek(self) -> SchedulerTask | None:
        """查看最高优先级任务 (不出队)。"""
        if not self._heap:
            return None
        return self._heap[0][2]

    def remove(self, task_id: str) -> SchedulerTask | None:
        """移除指定任务。O(n)。"""
        for i, (_, _, t) in enumerate(self._heap):
            if t.task_id == task_id:
                self._heap.pop(i)
                heapq.heapify(self._heap)
                return t
        return None

    def cancel_all(self) -> int:
        """取消所有 PENDING 任务。返回数量。"""
        count = len(self._heap)
        for _, _, task in self._heap:
            task.status = TaskStatus.CANCELLED
        self._heap.clear()
        return count

    @property
    def depth(self) -> int:
        return len(self._heap)

    @property
    def is_empty(self) -> bool:
        return len(self._heap) == 0

    def by_priority(self) -> dict[Priority, int]:
        """按优先级分组计数。"""
        counts: dict[Priority, int] = {}
        for _, _, task in self._heap:
            counts[task.priority] = counts.get(task.priority, 0) + 1
        return counts

    def drain_priority(self, priority: Priority) -> list[SchedulerTask]:
        """排出指定优先级的所有任务。用于背压。"""
        drained = []
        remaining = []
        for _, _, task in self._heap:
            if task.priority == priority:
                task.status = TaskStatus.CANCELLED
                drained.append(task)
            else:
                remaining.append((task.priority.value, next(self._counter), task))
        heapq.heapify(remaining)
        self._heap = remaining
        return drained

    def __len__(self) -> int:
        return self.depth

    def __bool__(self) -> bool:
        return not self.is_empty


__all__ = ["PriorityQueue"]
