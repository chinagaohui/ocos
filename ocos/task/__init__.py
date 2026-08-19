"""Phase 23-C — TaskDAG with RLock。

任务有向无环图：管理任务间的依赖关系与拓扑排序。
用于 ExecutiveController 的策略制定阶段。
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from enum import Enum


class TaskStatus(str, Enum):
    PENDING = "PENDING"
    READY = "READY"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


@dataclass
class TaskNode:
    """DAG 节点。"""
    task_id: str
    name: str
    status: TaskStatus = TaskStatus.PENDING
    deps: set[str] = field(default_factory=set)
    metadata: dict = field(default_factory=dict)


class TaskDAG:
    """任务有向无环图 — 线程安全。

    支持：
      - add_task / add_dependency
      - resolve_ready — 返回无阻塞依赖的就绪任务
      - 拓扑排序
      - 循环依赖检测
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._nodes: dict[str, TaskNode] = {}

    # ── 写操作 ───────────────────────────────────────────────────────────

    def add_task(self, task_id: str, name: str = "", **meta) -> TaskNode:
        with self._lock:
            if task_id in self._nodes:
                raise ValueError(f"task {task_id} already exists")
            node = TaskNode(task_id=task_id, name=name or task_id, metadata=meta)
            self._nodes[task_id] = node
            return node

    def add_dependency(self, task_id: str, depends_on: str) -> None:
        with self._lock:
            if task_id not in self._nodes:
                raise ValueError(f"task {task_id} not found")
            if depends_on not in self._nodes:
                raise ValueError(f"dependency {depends_on} not found")
            if depends_on == task_id:
                raise ValueError("self-dependency not allowed")
            self._nodes[task_id].deps.add(depends_on)
            # 循环检测
            if self._has_cycle(task_id, {task_id}):
                self._nodes[task_id].deps.discard(depends_on)
                raise ValueError(f"adding {depends_on} → {task_id} creates cycle")

    def set_status(self, task_id: str, status: TaskStatus) -> None:
        with self._lock:
            node = self._nodes.get(task_id)
            if node is None:
                raise ValueError(f"task {task_id} not found")
            node.status = status

    # ── 读操作 ───────────────────────────────────────────────────────────

    def get(self, task_id: str) -> TaskNode | None:
        with self._lock:
            return self._nodes.get(task_id)

    def resolve_ready(self) -> list[TaskNode]:
        """返回所有就绪任务（无未完成依赖）。"""
        with self._lock:
            ready = []
            for node in self._nodes.values():
                if node.status != TaskStatus.PENDING:
                    continue
                all_deps_ok = all(
                    self._nodes[d].status == TaskStatus.COMPLETED
                    for d in node.deps
                )
                if all_deps_ok:
                    ready.append(node)
            return ready

    def topological_order(self) -> list[TaskNode]:
        """拓扑排序。"""
        with self._lock:
            visited: set[str] = set()
            temp: set[str] = set()
            order: list[TaskNode] = []

            for tid in self._nodes:
                if tid not in visited:
                    self._topo_dfs(tid, visited, temp, order)

            return order

    def __len__(self) -> int:
        with self._lock:
            return len(self._nodes)

    # ── internal ────────────────────────────────────────────────────────

    def _has_cycle(self, start: str, path: set[str]) -> bool:
        """DFS 检测从 start 出发的循环。"""
        for dep in self._nodes[start].deps:
            if dep in path:
                return True
            if self._has_cycle(dep, path | {dep}):
                return True
        return False

    def _topo_dfs(self, tid: str, visited: set[str], temp: set[str],
                  order: list[TaskNode]) -> None:
        if tid in temp:
            raise ValueError(f"cycle detected at {tid}")
        if tid in visited:
            return
        temp.add(tid)
        for dep in self._nodes[tid].deps:
            self._topo_dfs(dep, visited, temp, order)
        temp.discard(tid)
        visited.add(tid)
        order.append(self._nodes[tid])
