"""Phase 27 — StrategyEngine: 策略选择。

基于 TaskDAG 拓扑结构选择最优执行策略:
  - 无依赖任务 → PARALLEL
  - 全串行链 → SEQUENTIAL
  - 混合结构 → PRIORITY_DRIVEN
"""

from __future__ import annotations

from ocos.planning.models import (
    ExecutionStrategy,
    MAX_PARALLEL_WIDTH,
    TaskDAG,
)


class StrategyEngine:
    """执行策略引擎。"""

    @staticmethod
    def select(dag: TaskDAG) -> ExecutionStrategy:
        """基于 DAG 结构选择策略。"""
        groups = dag.parallel_groups()

        if not groups:
            return ExecutionStrategy.SEQUENTIAL

        # 每层只有1个任务 → 全串行
        if all(len(g) == 1 for g in groups):
            return ExecutionStrategy.SEQUENTIAL

        # 所有任务都在同一层（无依赖）→ 全并行
        if len(groups) == 1 and len(groups[0]) > 1:
            return ExecutionStrategy.PARALLEL

        # 混合结构 → 优先级驱动
        return ExecutionStrategy.PRIORITY_DRIVEN

    @staticmethod
    def explain(dag: TaskDAG) -> str:
        """解释策略选择原因。"""
        groups = dag.parallel_groups()
        strategy = StrategyEngine.select(dag)

        if strategy == ExecutionStrategy.SEQUENTIAL:
            return f"全串行链：{len(groups)} 层，每层1个任务"
        elif strategy == ExecutionStrategy.PARALLEL:
            return f"全并行：{len(groups[0])} 个任务无依赖关系"
        else:
            parallel_layers = sum(1 for g in groups if len(g) > 1)
            return (
                f"优先级驱动：{len(groups)} 层，"
                f"{parallel_layers} 层有并行任务"
            )

    @staticmethod
    def validate_parallel_width(dag: TaskDAG) -> tuple[bool, str]:
        """验证并行宽度不超预算。"""
        for i, group in enumerate(dag.parallel_groups()):
            if len(group) > MAX_PARALLEL_WIDTH:
                return False, (
                    f"Level {i} has {len(group)} tasks, "
                    f"exceeds MAX_PARALLEL_WIDTH {MAX_PARALLEL_WIDTH}"
                )
        return True, "ok"
