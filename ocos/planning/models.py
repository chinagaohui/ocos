"""Phase 27 Planning Intelligence — 数据模型。

宪法约束:
  - Task 引用 Goal（外键），不持有 Goal
  - Plan 不可修改 Goal
  - MAX_DAG_DEPTH=5, MAX_PARALLEL_WIDTH=4
  - 不导入 ocos.self
"""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


# ── 拓扑预算 ────────────────────────────────────────────────────────

MAX_DAG_DEPTH = 5
MAX_PARALLEL_WIDTH = 4


# ── TaskStatus ────────────────────────────────────────────────────────


class TaskStatus(str, Enum):
    PENDING = "pending"
    READY = "ready"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

    @property
    def is_terminal(self) -> bool:
        return self in (TaskStatus.COMPLETED, TaskStatus.FAILED)

    def can_transition_to(self, target: TaskStatus) -> bool:
        return target in _TRANSITIONS.get(self, set())


_TRANSITIONS: dict[TaskStatus, set[TaskStatus]] = {
    TaskStatus.PENDING:   {TaskStatus.READY},
    TaskStatus.READY:     {TaskStatus.RUNNING},
    TaskStatus.RUNNING:   {TaskStatus.COMPLETED, TaskStatus.FAILED},
    TaskStatus.FAILED:    {TaskStatus.READY},  # retry
    TaskStatus.COMPLETED: set(),
}


# ── Task ───────────────────────────────────────────────────────────────

# Phase 23: 统一 agent_type 枚举 — Task 与 AgentDescriptor 共享同一有效值集合
VALID_AGENT_TYPES: frozenset[str] = frozenset({
    "writer",
    "researcher",
    "reviewer",
    "data_processor",
})


@dataclass(frozen=True)
class Task:
    """不可变任务单元。"""
    id: str
    goal_id: str
    description: str
    task_type: str              # create|modify|analyze|execute|verify
    agent_type: str             # writer|researcher|reviewer|data_processor
    inputs: tuple[str, ...] = ()          # 依赖的 Task IDs
    estimated_duration: int = 60          # 秒
    priority: int = 1                     # 1-5
    retry_policy: str = "retry_3x"        # no_retry|retry_3x|retry_with_fallback

    def __post_init__(self):
        if not self.id:
            raise ValueError("id must not be empty")
        if not self.goal_id:
            raise ValueError("goal_id must not be empty")
        if not self.description:
            raise ValueError("description must not be empty")
        if self.agent_type not in VALID_AGENT_TYPES:
            raise ValueError(
                f"agent_type '{self.agent_type}' not in {sorted(VALID_AGENT_TYPES)}"
            )
        if self.priority < 1 or self.priority > 5:
            raise ValueError(f"priority 1-5, got {self.priority}")
        if self.estimated_duration <= 0:
            raise ValueError(f"estimated_duration <= 0, got {self.estimated_duration}")

    @classmethod
    def create(
        cls,
        goal_id: str,
        description: str,
        task_type: str = "execute",
        agent_type: str = "writer",
        inputs: tuple[str, ...] = (),
        estimated_duration: int = 60,
        priority: int = 1,
        retry_policy: str = "retry_3x",
    ) -> Task:
        return cls(
            id=f"TASK-{uuid.uuid4().hex[:8]}",
            goal_id=goal_id,
            description=description,
            task_type=task_type,
            agent_type=agent_type,
            inputs=inputs,
            estimated_duration=estimated_duration,
            priority=priority,
            retry_policy=retry_policy,
        )


# ── TaskDAG ───────────────────────────────────────────────────────────


@dataclass
class TaskDAG:
    """有向无环任务图。
    线程安全：所有公开方法由 self._lock 保护。"""
    tasks: dict[str, Task] = field(default_factory=dict)
    edges: list[tuple[str, str]] = field(default_factory=list)  # (from_id, to_id)

    def __post_init__(self):
        object.__setattr__(self, "_lock", threading.RLock())

    def add_task(self, task: Task) -> None:
        with self._lock:
            if task.id in self.tasks:
                raise ValueError(f"task {task.id} already in DAG")
            self.tasks[task.id] = task

    def add_edge(self, from_id: str, to_id: str) -> None:
        with self._lock:
            if from_id not in self.tasks:
                raise ValueError(f"from task {from_id} not found")
            if to_id not in self.tasks:
                raise ValueError(f"to task {to_id} not found")
            self.edges.append((from_id, to_id))

    def validate_acyclic(self) -> bool:
        """Kahn 算法检测环。"""
        with self._lock:
            in_degree: dict[str, int] = {tid: 0 for tid in self.tasks}
            for frm, to in self.edges:
                in_degree[to] = in_degree.get(to, 0) + 1
                in_degree.setdefault(frm, 0)

            queue = [tid for tid, deg in in_degree.items() if deg == 0]
            visited = 0
            while queue:
                node = queue.pop(0)
                visited += 1
                for frm, to in self.edges:
                    if frm == node:
                        in_degree[to] -= 1
                        if in_degree[to] == 0:
                            queue.append(to)
            return visited == len(self.tasks)

    def topological_order(self) -> list[str]:
        """Kahn 拓扑排序。"""
        with self._lock:
            in_degree: dict[str, int] = {tid: 0 for tid in self.tasks}
            for frm, to in self.edges:
                in_degree[to] = in_degree.get(to, 0) + 1
                in_degree.setdefault(frm, 0)

            queue = [tid for tid, deg in in_degree.items() if deg == 0]
            order: list[str] = []
            while queue:
                node = queue.pop(0)
                order.append(node)
                for frm, to in self.edges:
                    if frm == node:
                        in_degree[to] -= 1
                        if in_degree[to] == 0:
                            queue.append(to)
            return order

    def parallel_groups(self) -> list[list[str]]:
        """按拓扑层级分组（每层内可并行）。"""
        with self._lock:
            order = self.topological_order()
            groups: list[list[str]] = []
            level: dict[str, int] = {}

            # 计算每个节点的拓扑层级
            for tid in order:
                max_pred_level = -1
                for frm, to in self.edges:
                    if to == tid and frm in level:
                        max_pred_level = max(max_pred_level, level[frm])
                level[tid] = max_pred_level + 1

            max_level = max(level.values()) if level else -1
            for lvl in range(max_level + 1):
                group = sorted(tid for tid, lv in level.items() if lv == lvl)
                groups.append(group)
            return groups


# ── ExecutionStrategy ──────────────────────────────────────────────────


class ExecutionStrategy(str, Enum):
    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"
    PRIORITY_DRIVEN = "priority_driven"


# ── Plan ───────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Plan:
    """不可变执行计划。"""
    plan_id: str
    goal_id: str
    dag: TaskDAG
    strategy: ExecutionStrategy
    estimated_total_duration: int
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self):
        if not self.plan_id:
            raise ValueError("plan_id must not be empty")
        if not self.goal_id:
            raise ValueError("goal_id must not be empty")
        if self.estimated_total_duration <= 0:
            raise ValueError(
                f"estimated_total_duration <= 0, got {self.estimated_total_duration}"
            )
