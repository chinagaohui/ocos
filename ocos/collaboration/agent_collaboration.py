"""Agent Collaboration — 多Agent协作引擎

Freeze Phase 50: 协调多个Agent并行/顺序执行，聚合结果
"""

from __future__ import annotations
import logging
import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any
from concurrent.futures import ThreadPoolExecutor, as_completed

from ocos.agent_orchestration.registry import AgentDescriptor
from ocos.planning.models import Task, TaskStatus, Plan

logger = logging.getLogger(__name__)


@dataclass
class CollaborationRequest:
    """协作请求 — 定义需要哪些Agent协作完成什么"""
    request_id: str
    goal: str
    tasks: tuple[Task, ...]
    max_parallel: int = 3
    timeout_seconds: int = 300
    strategy: str = "parallel"  # parallel|sequential|pipeline

    def __post_init__(self):
        if not self.request_id:
            raise ValueError("request_id must not be empty")
        if not self.goal:
            raise ValueError("goal must not be empty")
        if not self.tasks:
            raise ValueError("tasks must not be empty")


@dataclass
class AgentTask:
    """Agent执行的任务（带协作元数据）"""
    task: Task
    agent: AgentDescriptor
    status: str = "pending"
    result: dict[str, Any] = field(default_factory=dict)
    started_at: float = 0.0
    finished_at: float = 0.0


@dataclass
class CollaborationState:
    """协作状态追踪"""
    request_id: str
    agent_tasks: dict[str, AgentTask] = field(default_factory=dict)
    completed_tasks: list[Task] = field(default_factory=list)
    failed_tasks: list[Task] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    started_at: float = 0.0
    finished_at: float = 0.0
    status: str = "pending"  # pending|running|completed|failed

    @property
    def progress(self) -> float:
        total = len(self.agent_tasks)
        if total == 0:
            return 0.0
        done = len(self.completed_tasks) + len(self.failed_tasks)
        return done / total

    @property
    def success_rate(self) -> float:
        total = len(self.completed_tasks) + len(self.failed_tasks)
        if total == 0:
            return 0.0
        return len(self.completed_tasks) / total

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "status": self.status,
            "progress": self.progress,
            "success_rate": self.success_rate,
            "completed": len(self.completed_tasks),
            "failed": len(self.failed_tasks),
            "errors": self.errors[:5],  # 限制错误数量
        }


class AgentCollaboration:
    """多Agent协作引擎

    支持：
    - 并行执行无依赖任务
    - 顺序执行有依赖任务
    - 结果聚合与错误处理
    - 超时控制
    """

    def __init__(self, max_workers: int = 5, timeout_seconds: int = 300):
        self._max_workers = max_workers
        self._timeout_seconds = timeout_seconds
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._state: dict[str, CollaborationState] = {}
        self._lock = threading.RLock()

    def start(
        self,
        request: CollaborationRequest,
        agent_map: dict[str, AgentDescriptor],
        execute_fn,
    ) -> CollaborationState:
        """启动协作任务

        Args:
            request: 协作请求
            agent_map: agent_type -> AgentDescriptor
            execute_fn: 执行函数签名 execute(task: Task, agent: AgentDescriptor) -> dict
        """
        state = CollaborationState(request_id=request.request_id)
        with self._lock:
            self._state[request.request_id] = state

        # 构建任务映射
        agent_tasks: dict[str, AgentTask] = {}
        for task in request.tasks:
            agent = agent_map.get(task.agent_type)
            if agent is None:
                state.errors.append(f"No agent available for type: {task.agent_type}")
                continue
            agent_tasks[task.id] = AgentTask(task=task, agent=agent)
            state.agent_tasks[task.id] = agent_tasks[task.id]

        if not agent_tasks:
            state.status = "failed"
            with self._lock:
                self._state[request.request_id] = state
            return state

        state.started_at = time.time()
        state.status = "running"

        # 执行任务
        logger.info(
            "Starting collaboration %s: %d tasks, strategy=%s",
            request.request_id, len(agent_tasks), request.strategy,
        )

        try:
            if request.strategy == "parallel":
                self._execute_parallel(agent_tasks, execute_fn, state)
            elif request.strategy == "sequential":
                self._execute_sequential(agent_tasks, execute_fn, state)
            elif request.strategy == "pipeline":
                self._execute_pipeline(agent_tasks, execute_fn, state)
            else:
                raise ValueError(f"Unknown strategy: {request.strategy}")

            state.status = "completed"
        except Exception as e:
            state.status = "failed"
            state.errors.append(str(e))
            logger.error("Collaboration %s failed: %s", request.request_id, e)
        finally:
            state.finished_at = time.time()
            with self._lock:
                self._state[request.request_id] = state

        return state

    def _execute_parallel(
        self,
        agent_tasks: dict[str, AgentTask],
        execute_fn,
        state: CollaborationState,
    ) -> None:
        """并行执行所有任务"""
        futures = {}
        for task_id, at in agent_tasks.items():
            at.status = "running"
            at.started_at = time.time()
            future = self._executor.submit(
                self._run_task, execute_fn, at
            )
            futures[future] = at

        deadline = time.time() + self._timeout_seconds
        for future in as_completed(futures, timeout=self._timeout_seconds):
            if time.time() > deadline:
                state.errors.append("Timeout exceeded")
                break
            at = futures[future]
            try:
                result = future.result(timeout=30)
                at.status = "completed"
                at.result = result
                at.finished_at = time.time()
                with self._lock:
                    state.completed_tasks.append(at.task)
            except Exception as e:
                at.status = "failed"
                at.finished_at = time.time()
                state.errors.append(f"Task {at.task.id} failed: {e}")
                with self._lock:
                    state.failed_tasks.append(at.task)

    def _execute_sequential(
        self,
        agent_tasks: dict[str, AgentTask],
        execute_fn,
        state: CollaborationState,
    ) -> None:
        """顺序执行所有任务"""
        for task_id, at in agent_tasks.items():
            if time.time() > state.started_at + self._timeout_seconds:
                state.errors.append("Timeout exceeded")
                break
            at.status = "running"
            at.started_at = time.time()
            try:
                result = execute_fn(at.task, at.agent)
                at.status = "completed"
                at.result = result
                at.finished_at = time.time()
                with self._lock:
                    state.completed_tasks.append(at.task)
            except Exception as e:
                at.status = "failed"
                at.finished_at = time.time()
                state.errors.append(f"Task {at.task.id} failed: {e}")
                with self._lock:
                    state.failed_tasks.append(at.task)

    def _execute_pipeline(
        self,
        agent_tasks: dict[str, AgentTask],
        execute_fn,
        state: CollaborationState,
    ) -> None:
        """流水线执行（按拓扑顺序）"""
        # 简化版：只按优先级排序执行
        sorted_tasks = sorted(
            agent_tasks.values(),
            key=lambda x: (-x.task.priority, x.task.id),
        )

        for at in sorted_tasks:
            if time.time() > state.started_at + self._timeout_seconds:
                state.errors.append("Timeout exceeded")
                break
            at.status = "running"
            at.started_at = time.time()
            try:
                result = execute_fn(at.task, at.agent)
                at.status = "completed"
                at.result = result
                at.finished_at = time.time()
                with self._lock:
                    state.completed_tasks.append(at.task)
            except Exception as e:
                at.status = "failed"
                at.finished_at = time.time()
                state.errors.append(f"Task {at.task.id} failed: {e}")
                with self._lock:
                    state.failed_tasks.append(at.task)

    def _run_task(self, execute_fn, at: AgentTask) -> dict[str, Any]:
        """运行单个任务（供线程池使用）"""
        return execute_fn(at.task, at.agent)

    def get_state(self, request_id: str) -> CollaborationState | None:
        """获取协作状态"""
        with self._lock:
            return self._state.get(request_id)

    def get_all_states(self) -> dict[str, CollaborationState]:
        """获取所有协作状态"""
        with self._lock:
            return dict(self._state)

    def cancel(self, request_id: str) -> bool:
        """取消协作"""
        with self._lock:
            state = self._state.get(request_id)
            if state and state.status == "running":
                state.status = "failed"
                state.errors.append("Cancelled by user")
                return True
            return False

    def close(self) -> None:
        """关闭执行器"""
        self._executor.shutdown(wait=False)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


# ── 便捷函数 ───────────────────────────────────────────────────────


def create_collaboration_request(
    goal: str,
    tasks: tuple[Task, ...],
    request_id: str | None = None,
    max_parallel: int = 3,
    strategy: str = "parallel",
) -> CollaborationRequest:
    """创建协作请求的便捷函数"""
    import uuid
    rid = request_id or f"COREQ-{uuid.uuid4().hex[:8]}"
    return CollaborationRequest(
        request_id=rid,
        goal=goal,
        tasks=tasks,
        max_parallel=max_parallel,
        strategy=strategy,
    )
