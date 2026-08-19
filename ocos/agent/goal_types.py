"""agent/goal_types — 向后兼容重导出。

Phase 21: 所有类型定义已迁移到 ocos.kernel.goal_types。
此模块保留用于兼容旧导入路径。
"""

from ocos.kernel.goal_types import (
    Goal,
    GoalLevel,
    GoalStatus,
    GoalOriginLevel,
    GoalAuthority,
    GoalSource,
    GoalDomain,
    SuccessCriteria,
    UserGoal,
    CALLER_WHITELIST,
)

__all__ = [
    "Goal",
    "GoalLevel",
    "GoalStatus",
    "GoalOriginLevel",
    "GoalAuthority",
    "GoalSource",
    "GoalDomain",
    "SuccessCriteria",
    "UserGoal",
    "CALLER_WHITELIST",
]
