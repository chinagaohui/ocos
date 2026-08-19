"""Phase 39.6 Goal Maintenance Module — 目标生命维持系统。

Goal Maintenance 不创造目标，只维护已有目标。

核心约束:
    Goal ≠ Task           — Maintenance 管理 Goal，Planner 管理 Task
    Maintenance ≠ Desire  — 不自动生成目标
    Maintenance ≠ Decider — 不修改/删除/改变优先级

架构:
    Goal → GoalMonitor.evaluate() → GoalHealth state
    → MaintenanceEngine → MaintenanceEvent → EventBus
    → Attention CandidateCollector → Attention Scoring → Focus Decision
"""

from .maintenance_types import (
    GoalHealth,
    GoalHealthSnapshot,
    MaintenanceEvent,
)
from .goal_monitor import GoalMonitor, GoalMonitorConfig
from .maintenance_engine import MaintenanceEngine, MaintenanceResult

__all__ = [
    "GoalHealth",
    "GoalHealthSnapshot",
    "MaintenanceEvent",
    "GoalMonitor",
    "GoalMonitorConfig",
    "MaintenanceEngine",
    "MaintenanceResult",
]
