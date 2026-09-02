"""Phase N: OrchestrationEngine — Agent 调度层整合。

将 ExecutionSupervisor（单任务执行）+ AgentCollaboration（多任务协作）
+ RuntimeLoop（主循环）整合为统一的调度引擎。

职责:
  - 管理 Agent 生命周期（注册/选择/执行）
  - 支持单任务和多任务协作执行
  - 与 RuntimeLoop 集成，每 tick 检查待执行任务
  - 提供执行结果聚合和质量审计
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum, auto
from typing import Any, Callable, Optional

from ocos.agent_orchestration.registry import AgentRegistry
from ocos.agent_orchestration.selector import AgentSelector
from ocos.agent_orchestration.supervisor import ExecutionSupervisor
from ocos.agent_orchestration.contract import ExecutionContract
from ocos.collaboration.agent_collaboration import (
    AgentCollaboration,
    CollaborationRequest,
    AgentTask,
    CollaborationState,
)
from ocos.planning.models import Task, Plan, TaskStatus

logger = logging.getLogger(__name__)


class OrchestrationState(Enum):
    """调度器状态。"""
    IDLE = auto()
    RUNNING = auto()
    PAUSED = auto()
    STOPPING = auto()
    STOPPED = auto()


@dataclass
class OrchestrationMetrics:
    """调度执行指标。"""
    started_at: Optional[float] = None
    stopped_at: Optional[float] = None
    total_tasks_executed: int = 0
    total_tasks_completed: int = 0
    total_tasks_failed: int = 0
    total_collaborations: int = 0
    total_collaborations_completed: int = 0
    last_execution_time_ms: float = 0.0
    _execution_times: list[float] = field(default_factory=list)

    @property
    def uptime_seconds(self) -> float:
        if self.started_at is None:
            return 0.0
        end = self.stopped_at or time.time()
        return end - self.started_at

    @property
    def success_rate(self) -> float:
        total = self.total_tasks_completed + self.total_tasks_failed
        if total == 0:
            return 0.0
        return self.total_tasks_completed / total

    @property
    def avg_execution_time_ms(self) -> float:
        if not self._execution_times:
            return 0.0
        return sum(self._execution_times) / len(self._execution_times)

    def record_execution(self, duration_ms: float, success: bool):
        self.total_tasks_executed += 1
        if success:
            self.total_tasks_completed += 1
        else:
            self.total_tasks_failed += 1
        self.last_execution_time_ms = duration_ms
        self._execution_times.append(duration_ms)
        if len(self._execution_times) > 100:
            self._execution_times = self._execution_times[-100:]

    def record_collaboration(self, success: bool):
        self.total_collaborations += 1
        if success:
            self.total_collaborations_completed += 1


class OrchestrationEngine:
    """统一调度引擎 — Phase N。

    整合:
    - ExecutionSupervisor: 单任务执行
    - AgentCollaboration: 多任务协作
    - AgentRegistry: Agent 注册/选择
    - RuntimeLoop 集成: 每 tick 检查待执行任务
    """

    def __init__(
        self,
        registry: Optional[AgentRegistry] = None,
        selector: Optional[AgentSelector] = None,
        supervisor: Optional[ExecutionSupervisor] = None,
        collaboration: Optional[AgentCollaboration] = None,
        max_pending_tasks: int = 100,
    ) -> None:
        self._registry = registry or AgentRegistry()
        self._selector = selector or AgentSelector(self._registry)
        self._supervisor = supervisor or ExecutionSupervisor(
            registry=self._registry,
            selector=self._selector,
        )
        self._collaboration = collaboration or AgentCollaboration()
        self._max_pending_tasks = max_pending_tasks

        self._state = OrchestrationState.IDLE
        self._lock = threading.RLock()
        self._pending_tasks: list[Task] = []
        self._pending_collaborations: list[CollaborationRequest] = []
        self._running_collabs: dict[str, CollaborationState] = {}

        self._metrics = OrchestrationMetrics()
        self._on_task_start: Optional[Callable[[str, str], None]] = None
        self._on_task_complete: Optional[Callable[[str, bool, float], None]] = None
        self._on_tick: Optional[Callable[[int], None]] = None

    # ── Public API ───────────────────────────────────────────────────────

    @property
    def state(self) -> OrchestrationState:
        return self._state

    @property
    def metrics(self) -> OrchestrationMetrics:
        return self._metrics

    @property
    def registry(self) -> AgentRegistry:
        return self._registry

    @property
    def supervisor(self) -> ExecutionSupervisor:
        return self._supervisor

    def start(self) -> "OrchestrationEngine":
        """启动调度引擎。"""
        with self._lock:
            if self._state in (OrchestrationState.RUNNING, OrchestrationState.PAUSED):
                return self
            self._state = OrchestrationState.RUNNING
            self._metrics.started_at = time.time()
            logger.info("OrchestrationEngine started")
        return self

    def stop(self) -> bool:
        """停止调度引擎。"""
        with self._lock:
            if self._state not in (OrchestrationState.RUNNING, OrchestrationState.PAUSED):
                return True
            self._state = OrchestrationState.STOPPING

        # 取消所有运行中的协作
        for req_id, state in list(self._running_collabs.items()):
            try:
                self._collaboration.cancel(req_id)
            except Exception:
                pass
            del self._running_collabs[req_id]

        with self._lock:
            self._state = OrchestrationState.STOPPED
            self._metrics.stopped_at = time.time()
            logger.info(
                "OrchestrationEngine stopped. "
                f"tasks={self._metrics.total_tasks_executed} "
                f"collabs={self._metrics.total_collaborations} "
                f"success_rate={self._metrics.success_rate:.2%}"
            )
        return True

    def pause(self) -> None:
        """暂停调度。"""
        with self._lock:
            if self._state == OrchestrationState.RUNNING:
                self._state = OrchestrationState.PAUSED
                logger.info("OrchestrationEngine paused")

    def resume(self) -> None:
        """恢复调度。"""
        with self._lock:
            if self._state == OrchestrationState.PAUSED:
                self._state = OrchestrationState.RUNNING
                logger.info("OrchestrationEngine resumed")

    # ── Task Submission ──────────────────────────────────────────────────

    def submit_task(self, task: Task) -> bool:
        """提交单个任务。返回 True 若成功入队。"""
        with self._lock:
            if len(self._pending_tasks) >= self._max_pending_tasks:
                logger.warning(
                    "Task queue full (%d) — rejecting: %s",
                    len(self._pending_tasks), task.description[:40],
                )
                return False
            self._pending_tasks.append(task)
            logger.debug("Task queued: %s (queue=%d)", task.id, len(self._pending_tasks))
            return True

    def submit_plan(self, plan: Plan) -> bool:
        """提交计划（展开为多个任务）。"""
        with self._lock:
            if len(self._pending_tasks) + len(plan.tasks) > self._max_pending_tasks:
                logger.warning("Plan would exceed queue capacity")
                return False
            for task in plan.tasks:
                self._pending_tasks.append(task)
            logger.info(
                "Plan queued: %d tasks (queue=%d)",
                len(plan.tasks), len(self._pending_tasks),
            )
            return True

    def submit_collaboration(self, request: CollaborationRequest) -> str:
        """提交协作请求。返回 request_id。"""
        req_id = request.request_id
        with self._lock:
            self._pending_collaborations.append(request)
            logger.info(
                "Collaboration queued: %s (%d tasks, strategy=%s)",
                req_id, len(request.tasks), request.strategy,
            )
        return req_id

    # ── Tick Integration ────────────────────────────────────────────────

    def process_tick(self, tick_id: int) -> dict[str, Any]:
        """每 tick 处理逻辑。

        Returns:
            dict: {tasks_processed: int, collaborations_started: int, ...}
        """
        result = {"tasks_processed": 0, "collaborations_started": 0, "errors": []}

        with self._lock:
            # 处理待执行任务
            tasks_to_process = self._pending_tasks[:]
            self._pending_tasks.clear()

            # 处理待执行协作
            collabs_to_process = self._pending_collaborations[:]
            self._pending_collaborations.clear()

        # 执行协作（线程安全）
        for collab_req in collabs_to_process:
            try:
                self._execute_collaboration(collab_req)
                result["collaborations_started"] += 1
            except Exception as e:
                result["errors"].append(f"collab {collab_req.request_id}: {e}")
                logger.error("Collaboration execution failed: %s", e)

        # 执行单任务
        for task in tasks_to_process:
            try:
                start = time.perf_counter()
                record = self._supervisor.execute_task_sync(task)
                duration_ms = (time.perf_counter() - start) * 1000
                success = record.status == "completed"
                self._metrics.record_execution(duration_ms, success)
                result["tasks_processed"] += 1

                if self._on_task_start:
                    try:
                        self._on_task_start(task.id, task.agent_type)
                    except Exception:
                        pass
                if self._on_task_complete:
                    try:
                        self._on_task_complete(task.id, success, duration_ms)
                    except Exception:
                        pass

            except Exception as e:
                result["errors"].append(f"task {task.id}: {e}")
                logger.error("Task execution failed: %s", e)

        # 回调
        if self._on_tick:
            try:
                self._on_tick(tick_id)
            except Exception as e:
                logger.warning("on_tick hook failed: %s", e)

        return result

    # ── Hooks ───────────────────────────────────────────────────────────

    def on_task_start(self, fn: Callable[[str, str], None]) -> "OrchestrationEngine":
        """注册任务开始回调 (task_id, agent_type)。"""
        self._on_task_start = fn
        return self

    def on_task_complete(self, fn: Callable[[str, bool, float], None]) -> "OrchestrationEngine":
        """注册任务完成回调 (task_id, success, duration_ms)。"""
        self._on_task_complete = fn
        return self

    def on_tick(self, fn: Callable[[int], None]) -> "OrchestrationEngine":
        """注册 tick 回调 (tick_id)。"""
        self._on_tick = fn
        return self

    # ── Internal ────────────────────────────────────────────────────────

    def _execute_collaboration(self, request: CollaborationRequest) -> None:
        """执行协作请求。"""
        # 构建 agent 映射
        agent_map: dict[str, Any] = {}
        for task in request.tasks:
            agent = self._selector.select(task)
            if agent:
                agent_map[task.agent_type] = agent

        if not agent_map:
            logger.warning("No agents available for collaboration %s", request.request_id)
            return

        # 定义执行函数
        def execute_fn(task: Task, agent: Any) -> dict:
            start = time.perf_counter()
            try:
                record = self._supervisor.execute_task_sync(task)
                duration_ms = (time.perf_counter() - start) * 1000
                success = record.status == "completed"
                self._metrics.record_execution(duration_ms, success)
                return {"success": success, "result": record.to_dict()}
            except Exception as e:
                return {"success": False, "error": str(e)}

        # 启动协作
        state = self._collaboration.start(request, agent_map, execute_fn)

        with self._lock:
            self._running_collabs[request.request_id] = state
            self._metrics.total_collaborations += 1
            if state.status == "completed":
                self._metrics.total_collaborations_completed += 1

        logger.info(
            "Collaboration %s completed: %d/%d tasks succeeded",
            request.request_id,
            len(state.completed_tasks),
            len(request.tasks),
        )

    # ── Status ──────────────────────────────────────────────────────────

    def get_status(self) -> dict[str, Any]:
        """获取调度器状态快照。"""
        with self._lock:
            return {
                "state": self._state.name,
                "pending_tasks": len(self._pending_tasks),
                "pending_collaborations": len(self._pending_collaborations),
                "running_collaborations": len(self._running_collabs),
                "metrics": {
                    "total_tasks_executed": self._metrics.total_tasks_executed,
                    "total_tasks_completed": self._metrics.total_tasks_completed,
                    "total_tasks_failed": self._metrics.total_tasks_failed,
                    "success_rate": self._metrics.success_rate,
                    "avg_execution_time_ms": self._metrics.avg_execution_time_ms,
                    "uptime_seconds": self._metrics.uptime_seconds,
                },
            }


# ── Factory ─────────────────────────────────────────────────────────────

def create_orchestration_engine(
    registry: Optional[AgentRegistry] = None,
    max_pending_tasks: int = 100,
) -> OrchestrationEngine:
    """工厂函数：创建 OrchestrationEngine 实例。"""
    return OrchestrationEngine(
        registry=registry,
        max_pending_tasks=max_pending_tasks,
    )
