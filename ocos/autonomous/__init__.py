"""Autonomous module — 自主认知子系统."""

from ocos.autonomous.goal_manager import (
    GoalManager,
    GoalManagerProtocol,
    GeneratedGoal,
    GoalSyncResult,
    create_goal_manager,
)

__all__ = [
    "GoalManager",
    "GoalManagerProtocol",
    "GeneratedGoal",
    "GoalSyncResult",
    "create_goal_manager",
]
