"""goal/models — deprecated，请迁移到 ocos.kernel.goal_types。

Phase 21: 此模块保留用于向后兼容，所有 import 已重定向到 kernel。
迁移后删除此文件。
"""

import warnings
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

warnings.warn(
    "ocos.goal.models is deprecated. Use ocos.kernel.goal_types instead.",
    DeprecationWarning,
    stacklevel=2,
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
