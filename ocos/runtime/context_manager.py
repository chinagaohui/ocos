"""
B1 Context Manager — 从 Working Memory + Goal 组装 Context。

Context 是 Runtime 的输入聚合体，包含：
- goals: 当前活跃目标（按优先级排序）
- tasks: 从 Goal 拆解出的任务列表
- preferences: 用户/系统偏好设置
- available_tools: 当前可用的工具列表

依赖方向：ocos.runtime → ocos.kernel (frozen ABI)
           ocos.runtime → ocos.events (可选，用于事件驱动重建)
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from dataclasses import dataclass, field
from typing import Any, Optional

from ocos.kernel.abi import Goal, SCHEMA_VERSION
from ocos.events.event_bus import EventBus
from ocos.kernel.abi import Event, EventType, Decision
from ocos.models.execution import Execution
from ocos.models.process import TransformProcess
from ocos.logging import get_logger

logger = get_logger(__name__)


# ── Working Memory ─────────────────────────────────────────────────────────

class WorkingMemory:
    """工作记忆：当前会话状态的临时存储。

    作为 Goal 和偏好的来源（B1 需求：从 Working Memory + Goal 组装）。
    后续 B2-B6 也会通过 Working Memory 读写中间状态。
    """

    def __init__(self, event_bus: EventBus | None = None):
        self._event_bus = event_bus
        self._goals: dict[str, Goal] = {}
        self._decisions: dict[str, Decision] = {}
        self._executions: dict[str, Execution] = {}
        self._processes: dict[str, TransformProcess] = {}
        self._preferences: dict[str, Any] = {}
        self._tools: set[str] = set()
        logger.debug("WorkingMemory initialized")

    # ── Event Emission ──────────────────────────────────────────────

    def _emit(self, operation: str, memory_id: str | None = None) -> None:
        """发射 MEMORY_STORED 事件（如果 EventBus 可用）。"""
        if self._event_bus is None:
            return
        self._event_bus.publish(Event(
            event_type=EventType.MEMORY_STORED,
            source="context_manager",
            payload={
                "memory_id": memory_id or uuid.uuid4().hex,
                "operation": operation,
            },
        ), sync=True)

    def _emit_retrieval(self, operation: str) -> None:
        """发射 MEMORY_RETRIEVED 事件（如果 EventBus 可用）。"""
        if self._event_bus is None:
            return
        self._event_bus.publish(Event(
            event_type=EventType.MEMORY_RETRIEVED,
            source="context_manager",
            payload={
                "memory_id": uuid.uuid4().hex,
                "operation": operation,
            },
        ), sync=True)

    # ── Goals ─────────────────────────────────────────────────────────

    def add_goal(self, goal: Goal) -> None:
        """添加或更新目标。"""
        self._goals[goal.goal_id] = goal
        self._emit("add_goal", goal.goal_id)

    def remove_goal(self, goal_id: str) -> None:
        """移除目标。"""
        self._goals.pop(goal_id, None)
        self._emit("remove_goal", goal_id)

    def get_goals(self, status: str | None = "active") -> list[Goal]:
        """获取目标列表，按优先级降序排列。status=None 返回全部。"""
        if status:
            filtered = [g for g in self._goals.values() if g.status == status]
        else:
            filtered = list(self._goals.values())
        filtered.sort(key=lambda g: (-g.priority, g.timestamp))
        self._emit_retrieval("get_goals")
        return filtered

    def update_goal_status(self, goal_id: str, status: str) -> bool:
        """更新目标状态。返回是否成功。"""
        if goal_id not in self._goals:
            return False
        old = self._goals[goal_id]
        # Goal 是 frozen dataclass，替换整个对象
        import dataclasses
        self._goals[goal_id] = dataclasses.replace(old, status=status)
        self._emit("update_goal_status", goal_id)
        return True

    # ── Decisions (Phase 18 — Decision Runtime) ─────────────────────────

    def add_decision(self, decision: Decision) -> None:
        """添加或更新决策。"""
        self._decisions[decision.decision_id] = decision
        self._emit("add_decision", decision.decision_id)

    def get_decisions(self, status: str | None = None) -> list[Decision]:
        """获取决策列表。status=None 返回全部。"""
        if status is None:
            return list(self._decisions.values())
        return [d for d in self._decisions.values() if d.status == status]

    def update_decision(self, decision: Decision) -> None:
        """替换决策（frozen dataclass 必须整体替换）。"""
        self._decisions[decision.decision_id] = decision
        self._emit("update_decision", decision.decision_id)

    # ── Executions (Phase 18 — Execution Runtime) ──────────────────────

    def add_execution(self, execution: Execution) -> None:
        """添加或更新执行。"""
        self._executions[execution.execution_id] = execution
        self._emit("add_execution", execution.execution_id)

    def get_executions(self, status: str | None = None) -> list[Execution]:
        """获取执行列表。status=None 返回全部。"""
        if status is None:
            return list(self._executions.values())
        return [e for e in self._executions.values() if e.status == status]

    def update_execution(self, execution: Execution) -> None:
        """替换执行（frozen dataclass 必须整体替换）。"""
        self._executions[execution.execution_id] = execution
        self._emit("update_execution", execution.execution_id)

    # ── Processes (Phase 18 — Process Runtime) ─────────────────────────

    def add_process(self, process: TransformProcess) -> None:
        """添加或更新过程。"""
        self._processes[process.process_id] = process
        self._emit("add_process", process.process_id)

    def get_processes(self, status: str | None = None) -> list[TransformProcess]:
        """获取过程列表。status=None 返回全部。"""
        if status is None:
            return list(self._processes.values())
        return [p for p in self._processes.values() if p.process_state == status]

    def update_process(self, process: TransformProcess) -> None:
        """替换过程（frozen dataclass 必须整体替换）。"""
        self._processes[process.process_id] = process
        self._emit("update_process", process.process_id)

    # ── Preferences ──────────────────────────────────────────────────

    def set_preference(self, key: str, value: Any) -> None:
        """设置偏好。"""
        self._preferences[key] = value
        self._emit("set_preference")

    def get_preference(self, key: str, default: Any = None) -> Any:
        """获取偏好。"""
        return self._preferences.get(key, default)

    def get_all_preferences(self) -> dict[str, Any]:
        """获取全部偏好的副本。"""
        return dict(self._preferences)

    def clear_preferences(self) -> None:
        """清除所有偏好。"""
        self._preferences.clear()
        self._emit("clear_preferences")

    # ── Tools ────────────────────────────────────────────────────────

    def register_tool(self, tool_name: str) -> None:
        """注册可用工具。"""
        self._tools.add(tool_name)
        self._emit("register_tool")

    def unregister_tool(self, tool_name: str) -> None:
        """注销工具。"""
        self._tools.discard(tool_name)
        self._emit("unregister_tool")

    def get_available_tools(self) -> list[str]:
        """获取当前可用工具列表。"""
        return sorted(self._tools)

    def has_tool(self, tool_name: str) -> bool:
        """检查工具是否可用。"""
        return tool_name in self._tools

    # ── 状态 ─────────────────────────────────────────────────────────

    def clear(self) -> None:
        """清空工作记忆。"""
        self._goals.clear()
        self._decisions.clear()
        self._executions.clear()
        self._processes.clear()
        self._preferences.clear()
        self._tools.clear()
        self._emit("clear")

    @property
    def goal_count(self) -> int:
        return len(self._goals)

    @property
    def active_goal_count(self) -> int:
        return sum(1 for g in self._goals.values() if g.status == "active")


# ── Context ────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Context:
    """运行时上下文：Runtime 各模块的输入聚合体。

    由 ContextManager 从 Working Memory + Goal 组装，对消费方只读。
    """
    context_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    goals: list[Goal] = field(default_factory=list)
    tasks: list[str] = field(default_factory=list)
    preferences: dict[str, Any] = field(default_factory=dict)
    available_tools: list[str] = field(default_factory=list)
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    schema_version: str = SCHEMA_VERSION

    @property
    def goal_count(self) -> int:
        return len(self.goals)

    @property
    def highest_priority_goal(self) -> Goal | None:
        """返回当前最高优先级的活跃目标。"""
        if not self.goals:
            return None
        return max(self.goals, key=lambda g: g.priority)


# ── Context Builder ─────────────────────────────────────────────────────────

class ContextManager:
    """上下文管理器：组装 Context，可选通过 Event Bus 自动重建。

    B1 核心职责：从 Working Memory + Goal 组装 Context 数据结构。
    """

    def __init__(
        self,
        working_memory: WorkingMemory,
        event_bus: EventBus | None = None,
    ):
        self._wm = working_memory
        self._event_bus = event_bus
        self._active_context: Context | None = None
        self._subscription_ids: list[str] = []

        # 如果提供了 Event Bus，订阅 Goal 相关事件以自动重建
        if event_bus is not None:
            self._subscribe()
        logger.debug("ContextManager initialized")

    # ── 公共接口 ─────────────────────────────────────────────────────

    def build_context(
        self,
        goal_ids: list[str] | None = None,
        additional_tasks: list[str] | None = None,
    ) -> Context:
        """从 Working Memory + Goal 组装 Context。

        Args:
            goal_ids: 限定只包含指定 goal_ids。None = 全部活跃目标。
            additional_tasks: 额外任务（非来自 Goal 拆解）。

        Returns:
            新的 Context（frozen dataclass）。
        """
        # 获取目标
        if goal_ids is not None:
            all_goals = self._wm.get_goals(status=None)
            goals = [g for g in all_goals if g.goal_id in goal_ids]
            goals.sort(key=lambda g: (-g.priority, g.timestamp))
        else:
            goals = self._wm.get_goals(status="active")

        # 从 Goal description 拆解任务
        tasks: list[str] = []
        for goal in goals:
            desc = goal.description.strip()
            if desc:
                # 按句号或换行拆分为子任务
                for line in desc.replace("\n", " ").split("。 "):
                    line = line.strip().rstrip("。")
                    if line:
                        tasks.append(f"[{goal.goal_id[:8]}] {line}")

        # 合并额外任务
        if additional_tasks:
            tasks.extend(additional_tasks)

        # 组装 Context
        ctx = Context(
            goals=goals,
            tasks=tasks,
            preferences=self._wm.get_all_preferences(),
            available_tools=self._wm.get_available_tools(),
        )

        self._active_context = ctx
        self._publish_context_built(ctx)
        logger.info(
            "Context built",
            component="context_manager",
            context_id=ctx.context_id,
            goals=len(goals),
            tasks=len(tasks),
        )
        return ctx

    def get_active_context(self) -> Context | None:
        """获取当前活跃 Context（最后构建的那个）。"""
        return self._active_context

    @property
    def working_memory(self) -> WorkingMemory:
        return self._wm

    # ── 事件集成 ────────────────────────────────────────────────────

    def _subscribe(self) -> None:
        """订阅 Goal 相关事件以自动重建 Context。（仅在 event_bus 非 None 时调用）"""
        if self._event_bus is None:
            return

        sid1 = self._event_bus.subscribe(
            EventType.GOAL_SET,
            self._on_goal_event,
            subscriber_id="ctxmgr-goal-set",
        )
        sid2 = self._event_bus.subscribe(
            EventType.GOAL_UPDATED,
            self._on_goal_event,
            subscriber_id="ctxmgr-goal-updated",
        )
        sid3 = self._event_bus.subscribe(
            EventType.GOAL_COMPLETED,
            self._on_goal_event,
            subscriber_id="ctxmgr-goal-completed",
        )
        self._subscription_ids = [sid1, sid2, sid3]

    def _on_goal_event(self, event: Event) -> None:
        """Goal 事件回调：自动重建 Context。"""
        payload = event.payload
        goal_id = payload.get("goal_id", "")
        logger.info(f"Goal event received: type={event.event_type} goal_id={goal_id}")
        if goal_id:
            # 同步工作记忆状态（Goal 可能已不在总线持有者手中）
            if event.event_type == EventType.GOAL_COMPLETED:
                self._wm.update_goal_status(goal_id, "completed")
            elif event.event_type == EventType.GOAL_SET:
                # GOAL_SET 可能有新的 Goal 对象
                desc = payload.get("description", "")
                priority = payload.get("priority", 0)
                new_goal = Goal(
                    goal_id=goal_id,
                    description=desc,
                    priority=priority,
                    status="active",
                )
                self._wm.add_goal(new_goal)
            # 重建 Context
            self.build_context()

    def unsubscribe(self) -> None:
        """取消事件订阅。"""
        if self._event_bus is None:
            logger.debug("unsubscribe skipped: no event_bus")
            return
        count = len(self._subscription_ids)
        for sid in self._subscription_ids:
            self._event_bus.unsubscribe(sid)
        self._subscription_ids.clear()
        logger.info(f"Unsubscribed {count} event handlers")

    def _publish_context_built(self, context: Context) -> None:
        """发布 Context 已构建事件（如果 Event Bus 存在且有 CONTEXT_BUILT 事件类型）。"""
        # B1 上下文管理本身不依赖 CONTEXT_BUILT 事件（避免循环依赖）
        # 未来 B3 Scheduler 可订阅此事件自动触发
        pass
