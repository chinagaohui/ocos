"""Stage ④: Goal Maintenance — Phase 39.6 目标生命维持。

每 Tick:
    1. 从 GoalStore 读取活跃 Goal
    2. 通过 MaintenanceEngine 评估健康状态
    3. 产出 MaintenanceEvent → 添加到 context.goal_updates
    4. 维护事件流入 Attention (下一 tick)

Governance Checkpoint (Phase 38):
    ✅ 刷新已有 Goal 状态
    ✅ 更新进度
    ✅ 检测 STALLED / BLOCKED / WARNING
    ❌ goal_store.create() — 不能创建新 Goal
    ❌ 修改 User Goal
    ❌ Maintenance Goal 升级为 Human Goal
    ❌ 改变 Goal 优先级

约束:
    Stage 自身无状态 (MaintenanceEngine 由 RuntimeKernel 注入)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..pipeline_protocol import TickStage
from ..tick_context import TickContext

if TYPE_CHECKING:
    from ocos.goal.maintenance_engine import MaintenanceEngine


class GoalMaintenanceStage:
    """目标维护阶段 — Governance Checkpoint。

    依赖 (由 RuntimeKernel 注入):
        - maintenance_engine: MaintenanceEngine
        - goal_store: 任何提供 get_active_goals() 的对象
        - progress_data: {goal_id: progress_score} — 外部提供
        - attention_history: {goal_id: last_focus_tick} — 从 Attention 获取
    """

    name = "GOAL_MAINTENANCE"

    def __init__(
        self,
        maintenance_engine: MaintenanceEngine | None = None,
        goal_store: object | None = None,
    ) -> None:
        self._engine = maintenance_engine
        self._goal_store = goal_store
        # 进展数据应由上层注入（如 Execution Stage 产出）
        self._progress_data: dict[str, float] = {}
        # 注意力历史应由 Attention Stage 记录
        self._attention_history: dict[str, int] = {}

    def execute(self, context: TickContext) -> TickContext:
        """执行目标维护。

        Returns:
            TickContext with goal_updates = (MaintenanceEvent dicts, ...)
        """
        if self._engine is None or self._goal_store is None:
            # Stub mode: no maintenance engine configured
            return context.with_updates(
                goal_updates=()
            ).with_stage_trace(self.name)

        result = self._engine.run_maintenance(
            goal_provider=self._goal_store,
            progress_data=self._progress_data,
            attention_history=self._attention_history,
            current_tick=context.tick_id,
        )

        # 序列化事件为 context.goal_updates
        events_tuple = tuple(
            evt.to_dict() for evt in result.events
        )

        return context.with_updates(
            goal_updates=events_tuple,
        ).with_stage_trace(self.name)

    # ── 外部接口 ─────────────────────────────────────────────────────

    def update_progress(self, goal_id: str, progress: float) -> None:
        """更新目标进展分数（由 Execution/Permission 阶段调用）。"""
        self._progress_data[goal_id] = progress

    def record_attention(self, goal_id: str, tick: int) -> None:
        """记录目标被关注的时间（由 Attention 阶段调用）。"""
        self._attention_history[goal_id] = tick

    def set_goal_store(self, store: object) -> None:
        """注入 GoalStore。"""
        self._goal_store = store

    def set_engine(self, engine: MaintenanceEngine) -> None:
        """注入 MaintenanceEngine。"""
        self._engine = engine
