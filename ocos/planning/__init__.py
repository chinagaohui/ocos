"""Phase 27 — Planning Intelligence 层。

导入规则:
  ✅ ocos.goal
  ✅ ocos.memory
  ✅ ocos.capability
  ❌ ocos.self (宪法禁止)
"""

from ocos.planning.models import (
    ExecutionStrategy,
    MAX_DAG_DEPTH,
    MAX_PARALLEL_WIDTH,
    Plan,
    Task,
    TaskDAG,
    TaskStatus,
)

__all__ = [
    "ExecutionStrategy",
    "MAX_DAG_DEPTH",
    "MAX_PARALLEL_WIDTH",
    "Plan",
    "Task",
    "TaskDAG",
    "TaskStatus",
]
