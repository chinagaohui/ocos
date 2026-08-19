"""Phase 39.6: MaintenanceEngine — 目标维护编排器。

职责:
    - 接收 GoalStore 接口
    - 调用 GoalMonitor 评估健康状态
    - 产出 MaintenanceEvent → EventBus
    - 产出 GoalHealthSnapshot → GoalStore (审计)

设计约束:
    ❌ 不创建 Goal (Goal ≠ Task, Maintenance ≠ Autonomous Desire)
    ❌ 不修改 Goal (Maintenance ≠ Decision Maker)
    ❌ 不删除 Goal
    ❌ 不改变 Goal 优先级
    ✅ 只读 Goal 状态 → 判定健康 → 产出事件
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .goal_monitor import GoalMonitor, GoalMonitorConfig
from .maintenance_types import GoalHealthSnapshot, MaintenanceEvent


@dataclass
class MaintenanceResult:
    """单次维护运行结果。

    包含:
        snapshots: 所有 Goal 的健康评估结果
        events: 需要关注的维护事件
        total_goals: 评估的 Goal 总数
        needs_attention_count: 需要关注的 Goal 数量
    """

    snapshots: list[GoalHealthSnapshot] = field(default_factory=list)
    events: list[MaintenanceEvent] = field(default_factory=list)
    total_goals: int = 0
    needs_attention_count: int = 0


class MaintenanceEngine:
    """目标维护编排器。

    每 Tick 调用:
        result = engine.run_maintenance(goal_store, progress, attention_history, tick_id)
        # result.events → EventBus
        # result.snapshots → audit trace

    用法示例:
        engine = MaintenanceEngine()
        store = ...  # GoalStore (agent layer)
        result = engine.run_maintenance(
            goal_provider=store,
            progress_data={"goal_a": 0.8, "goal_b": 0.1},
            attention_history={"goal_a": 100, "goal_b": 50},
            current_tick=1000,
        )
        for event in result.events:
            event_bus.publish(EventType.MAINTENANCE, event)
    """

    def __init__(self, config: GoalMonitorConfig | None = None) -> None:
        self._monitor = GoalMonitor(config=config)

    def run_maintenance(
        self,
        goal_provider: Any,
        progress_data: dict[str, float] | None = None,
        attention_history: dict[str, int] | None = None,
        current_tick: int = 0,
    ) -> MaintenanceResult:
        """执行一次目标维护。

        Args:
            goal_provider: GoalStore 或任何有 .get_all_goals() 方法的对象
            progress_data: {goal_id: progress_score}
            attention_history: {goal_id: last_focus_tick}
            current_tick: 当前 tick ID

        Returns:
            MaintenanceResult — 包含快照和事件
        """
        # 获取活跃 Goal
        goals = self._get_goals(goal_provider)

        # 评估健康
        snapshots = self._monitor.evaluate(
            goals=goals,
            progress_data=progress_data,
            attention_focus_history=attention_history,
            current_tick=current_tick,
        )

        # 产出事件
        events = self._monitor.to_events(snapshots, current_tick)

        needs_attention = sum(1 for s in snapshots if s.health.needs_attention)

        return MaintenanceResult(
            snapshots=snapshots,
            events=events,
            total_goals=len(goals),
            needs_attention_count=needs_attention,
        )

    @property
    def monitor(self) -> GoalMonitor:
        """获取底层 GoalMonitor（供测试/审计）。"""
        return self._monitor

    # ── 私有 ──────────────────────────────────────────────────────────

    @staticmethod
    def _get_goals(goal_provider: Any) -> list[Any]:
        """从 GoalProvider 获取 Goal 列表。

        支持:
            - GoalStore (有 get_active_goals() 方法)
            - 任意可迭代对象
        """
        if goal_provider is None:
            return []
        if hasattr(goal_provider, "get_active_goals"):
            return goal_provider.get_active_goals()
        if hasattr(goal_provider, "get_all_goals"):
            return goal_provider.get_all_goals()
        # 尝试当作列表
        try:
            return list(goal_provider)
        except TypeError:
            return []
