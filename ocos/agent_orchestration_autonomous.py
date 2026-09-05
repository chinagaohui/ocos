"""Phase 61: Agent Orchestration Autonomous — 自主化编排层。

⚠️ S4.3 / 上电方案 W5：本模块已标记废弃（deprecated）。
    _monitor_running 以 attempts 计数模拟任务完成（伪造成功段，无真实执行）；
    正式编排能力由 ocos.agent_orchestration 提供。本模块仅保留供遗留测试
    兼容（test_phase61/test_phase62c/test_import_rules），新代码禁止引用。

将 Phase 60 的 AutonomousLoop 与 Phase 28 的 AgentOrchestration 连接，
使 OCOS 能自主完成:
    1. Goal → 子任务分解
    2. Agent 选择与调度
    3. 执行监控与自适应
    4. 失败回退与重试

这是从"人工驱动编排"到"自主认知编排"的关键跃迁。

Architecture:
    AutonomousOrchestrator
    ├── goal_store (Goal + Task)
    ├── supervisor (ExecutionSupervisor)
    ├── loop (AutonomousLoop — 认知引擎)
    └── self.tick() — 自主决策/调度/监控循环
"""

from __future__ import annotations

import warnings

warnings.warn(
    "ocos.agent_orchestration_autonomous 已废弃（S4.3 / 上电方案 W5）— "
    "_monitor_running 存在伪造成功段，请迁移到 ocos.agent_orchestration。"
    "本模块仅保留供遗留测试兼容。",
    DeprecationWarning, stacklevel=2)

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from ocos.logging import get_logger
from ocos.agent_orchestration import (
    AgentDescriptor,
    AgentRegistry,
    AgentSelector,
)
from ocos.agent_orchestration.contract import ExecutionContract
from ocos.agent_orchestration.agent_pool import AgentPool
from ocos.planning.models import Task

logger = get_logger(__name__)


# ── Types ────────────────────────────────────────────────────────────────────


class OrchestrationPhase(str, Enum):
    """编排阶段。"""
    IDLE = "IDLE"
    DECOMPOSING = "DECOMPOSING"
    DISPATCHING = "DISPATCHING"
    EXECUTING = "EXECUTING"
    MONITORING = "MONITORING"
    ADAPTING = "ADAPTING"
    COMPLETED = "COMPLETED"


@dataclass
class OrchestrationTask:
    """编排任务 — Goal 分解后的可执行单元。"""
    task_id: str
    parent_goal_id: str
    description: str
    agent_type: str = "writer"  # valid: writer|researcher|reviewer|data_processor
    priority: int = 5
    status: str = "pending"  # pending/dispatched/running/completed/failed
    agent_id: str = ""
    started_at: float = 0.0
    completed_at: float = 0.0
    result_summary: str = ""
    attempts: int = 0
    max_attempts: int = 3

    def to_planning_task(self) -> Task:
        """转换为 ocos.planning.models.Task（供 AgentSelector 使用）。"""
        agent_type = self.agent_type if self.agent_type in {"writer", "researcher", "reviewer", "data_processor"} else "writer"
        return Task.create(
            goal_id=self.parent_goal_id,
            description=self.description,
            task_type="execute",
            agent_type=agent_type,
            priority=min(self.priority, 5),
        )


@dataclass
class OrchestrationStats:
    """编排统计。"""
    total_goals_processed: int = 0
    total_tasks_dispatched: int = 0
    total_tasks_completed: int = 0
    total_tasks_failed: int = 0
    total_fallbacks_triggered: int = 0
    current_phase: OrchestrationPhase = OrchestrationPhase.IDLE
    uptime_seconds: float = 0.0
    last_tick_at: float = 0.0


# ── AutonomousOrchestrator ───────────────────────────────────────────────────


@dataclass
class AutonomousOrchestrator:
    """自主编排器 — Phase 61 核心。

    OCOS 能自主将 Goal 分解为 Agent 可执行任务，
    通过认知循环决定调度策略，监控执行结果，自适应调整。

    用法:
        orch = AutonomousOrchestrator()
        orch.submit_goal("分析科幻小说市场趋势")
        for _ in range(20):
            summary = orch.tick()
    """

    # ── 核心组件 ──
    registry: AgentRegistry = field(default_factory=AgentRegistry)
    _selector: Optional[AgentSelector] = None
    _pool: Optional[AgentPool] = None  # Phase 62c: 并发调度池

    # ── 状态 ──
    phase: OrchestrationPhase = OrchestrationPhase.IDLE
    stats: OrchestrationStats = field(default_factory=OrchestrationStats)
    _task_queue: list[OrchestrationTask] = field(default_factory=list)
    _completed_tasks: list[OrchestrationTask] = field(default_factory=list)
    _goal_queue: list[dict] = field(default_factory=list)
    _started_at: float = field(default_factory=time.time)
    _event_log: list[dict] = field(default_factory=list)

    @property
    def selector(self) -> AgentSelector:
        if self._selector is None:
            self._selector = AgentSelector(self.registry)
        return self._selector

    def submit_goal(self, goal_description: str, goal_id: str = "") -> str:
        """提交目标到编排队列。"""
        gid = goal_id or f"goal-{int(time.time())}-{len(self._goal_queue)}"
        self._goal_queue.append({
            "goal_id": gid,
            "description": goal_description,
            "submitted_at": time.time(),
            "status": "pending",
        })
        self._log("goal_submitted", {"goal_id": gid, "description": goal_description[:80]})
        if self.phase == OrchestrationPhase.IDLE:
            self.phase = OrchestrationPhase.DECOMPOSING
        return gid

    def tick(self) -> dict:
        """执行一次自主编排 tick。返回当前状态摘要。"""
        self.stats.last_tick_at = time.time()
        self.stats.uptime_seconds = time.time() - self._started_at

        if self.phase == OrchestrationPhase.DECOMPOSING:
            self._decompose_goals()

        if self.phase in (OrchestrationPhase.DISPATCHING, OrchestrationPhase.EXECUTING):
            self._dispatch_pending()

        self._monitor_running()

        if self.phase == OrchestrationPhase.ADAPTING:
            self._adapt()

        if (not self._goal_queue or all(g["status"] == "completed" for g in self._goal_queue)) \
                and not self._task_queue:
            if self.stats.total_tasks_completed > 0:
                self.phase = OrchestrationPhase.COMPLETED

        return self.summary()

    # ── Internal ───────────────────────────────────────────────────────

    def _decompose_goals(self):
        pending = [g for g in self._goal_queue if g["status"] == "pending"]
        if not pending:
            self.phase = OrchestrationPhase.DISPATCHING if self._task_queue else OrchestrationPhase.IDLE
            return

        goal = pending[0]
        goal["status"] = "decomposing"
        gid = goal["goal_id"]
        desc = goal["description"]

        tasks = [
            OrchestrationTask(
                task_id=f"{gid}-analyze",
                parent_goal_id=gid,
                description=f"分析: {desc}",
                agent_type="researcher",
                priority=1,
            ),
            OrchestrationTask(
                task_id=f"{gid}-execute",
                parent_goal_id=gid,
                description=f"执行: {desc}",
                agent_type="writer",
                priority=2,
            ),
            OrchestrationTask(
                task_id=f"{gid}-review",
                parent_goal_id=gid,
                description=f"审查: {desc}",
                agent_type="reviewer",
                priority=3,
            ),
        ]
        self._task_queue.extend(tasks)
        self.stats.total_tasks_dispatched += len(tasks)
        goal["status"] = "dispatched"
        self.phase = OrchestrationPhase.DISPATCHING
        self._log("goal_decomposed", {"goal_id": gid, "task_count": len(tasks)})

    def _dispatch_pending(self):
        pending = [t for t in self._task_queue if t.status == "pending"]
        if not pending:
            self.phase = OrchestrationPhase.EXECUTING if self._task_queue else OrchestrationPhase.IDLE
            return

        # Phase 62c: 如果有 AgentPool，并行执行全部待调度任务
        if self._pool is not None:
            self._dispatch_via_pool(pending)
            return

        # Fallback: 串行逐个调度（原有行为，每 tick 最多 3 个）
        for task in pending[:3]:
            planning_task = task.to_planning_task()
            agent = self.selector.select(planning_task)
            if agent:
                task.agent_id = agent.agent_id
                task.status = "dispatched"
                self._log("task_dispatched", {
                    "task_id": task.task_id,
                    "agent_id": agent.agent_id,
                    "agent_type": task.agent_type,
                })
            else:
                task.agent_id = "default-agent"
                task.status = "dispatched"
                self._log("task_fallback", {"task_id": task.task_id, "reason": "no_agent_found"})

        self.phase = OrchestrationPhase.EXECUTING

    def _dispatch_via_pool(self, pending: list[OrchestrationTask]):
        """Phase 62c: 通过 AgentPool 并行执行所有待调度任务。"""
        contracts = [self._task_to_contract(t) for t in pending]
        results = self._pool.execute_sync(contracts)

        completed = []
        for task, result in zip(pending, results):
            task.attempts = 1
            if result.success:
                task.status = "completed"
                task.result_summary = result.output or f"Task {task.task_id} completed"
                task.completed_at = time.time()
                self.stats.total_tasks_completed += 1
                self._log("task_completed", {
                    "task_id": task.task_id,
                    "elapsed_ms": round(result.elapsed_ms, 1),
                })
            else:
                task.status = "failed"
                task.result_summary = result.error or f"Task {task.task_id} failed"
                task.completed_at = time.time()
                self.stats.total_tasks_failed += 1
                self.stats.total_fallbacks_triggered += 1
                self._log("task_failed", {
                    "task_id": task.task_id,
                    "error": result.error,
                })
            completed.append(task)

        # 清理队列
        self._task_queue = [t for t in self._task_queue if t.status == "pending"]
        self._completed_tasks.extend(completed)

        # 同步目标状态
        self._sync_goal_status()

        # 有更多目标待处理？
        pending_goals = [g for g in self._goal_queue if g["status"] not in ("completed", "failed")]
        if pending_goals:
            self.phase = OrchestrationPhase.DECOMPOSING
        elif self._task_queue:
            self.phase = OrchestrationPhase.DISPATCHING
        else:
            self.phase = OrchestrationPhase.MONITORING

    def _task_to_contract(self, task: OrchestrationTask) -> ExecutionContract:
        """将 OrchestrationTask 转为 AgentPool 可用的 ExecutionContract。"""
        return ExecutionContract.create(
            task_id=task.task_id,
            agent_id=task.agent_id or task.agent_type,
            input_spec={
                "description": task.description,
                "parent_goal_id": task.parent_goal_id,
                "priority": task.priority,
            },
            timeout_seconds=30,
            retry_policy="no_retry",
        )

    def _monitor_running(self):
        running = [t for t in self._task_queue if t.status in ("dispatched", "running")]
        if not running:
            if self._task_queue:
                pending_goals = [g for g in self._goal_queue if g["status"] not in ("completed", "failed")]
                self.phase = OrchestrationPhase.DECOMPOSING if pending_goals else OrchestrationPhase.COMPLETED
            return

        completed_this_tick = []
        for task in running:
            task.attempts += 1
            if task.status == "dispatched":
                task.status = "running"
                task.started_at = time.time()
                self._log("task_running", {"task_id": task.task_id, "agent_id": task.agent_id})
            elif task.status == "running":
                success = task.attempts <= task.max_attempts
                if success:
                    task.status = "completed"
                    task.result_summary = f"Task {task.task_id} completed by {task.agent_id}"
                    task.completed_at = time.time()
                    self.stats.total_tasks_completed += 1
                    self._log("task_completed", {"task_id": task.task_id, "attempts": task.attempts})
                else:
                    task.status = "failed"
                    task.result_summary = f"Task {task.task_id} failed after {task.attempts} attempts"
                    self.stats.total_tasks_failed += 1
                    self.stats.total_fallbacks_triggered += 1
                    self._log("task_failed", {"task_id": task.task_id, "attempts": task.attempts})
                completed_this_tick.append(task)

        self._task_queue = [t for t in self._task_queue if t not in completed_this_tick]
        self._completed_tasks.extend(completed_this_tick)
        self._sync_goal_status()

        # 只有任务实际完成后才检查是否有更多工作
        if completed_this_tick:
            pending_goals = [g for g in self._goal_queue if g["status"] not in ("completed", "failed")]
            if pending_goals:
                self.phase = OrchestrationPhase.DECOMPOSING
            elif self._task_queue:
                self.phase = OrchestrationPhase.DISPATCHING

    def _sync_goal_status(self):
        for goal in self._goal_queue:
            if goal["status"] == "completed":
                continue
            goal_tasks = [t for t in self._completed_tasks if t.parent_goal_id == goal["goal_id"]]
            if len(goal_tasks) >= 3:
                if all(t.status == "completed" for t in goal_tasks):
                    goal["status"] = "completed"
                    self.stats.total_goals_processed += 1
                    self._log("goal_completed", {"goal_id": goal["goal_id"]})

    def _adapt(self):
        failed = [t for t in self._completed_tasks if t.status == "failed"]
        for task in failed:
            if task.attempts < task.max_attempts:
                task.status = "pending"
                task.attempts += 1
                self._task_queue.append(task)
                self._log("task_retry", {"task_id": task.task_id, "attempt": task.attempts})
        self._completed_tasks = [t for t in self._completed_tasks if t.status != "failed"]
        self.phase = OrchestrationPhase.DISPATCHING if self._task_queue else OrchestrationPhase.MONITORING

    # ── Summary ─────────────────────────────────────────────────────────

    def summary(self) -> dict:
        return {
            "phase": self.phase.value,
            "total_goals_processed": self.stats.total_goals_processed,
            "pending_goals": len([g for g in self._goal_queue if g["status"] == "pending"]),
            "tasks_in_queue": len(self._task_queue),
            "tasks_completed": self.stats.total_tasks_completed,
            "tasks_failed": self.stats.total_tasks_failed,
            "fallbacks": self.stats.total_fallbacks_triggered,
            "uptime_seconds": round(self.stats.uptime_seconds, 1),
        }

    def drain_events(self) -> list[dict]:
        events = list(self._event_log)
        self._event_log.clear()
        return events

    def _log(self, event: str, data: dict):
        self._event_log.append({
            "event": event,
            "timestamp": time.time(),
            "phase": self.phase.value,
            **data,
        })
