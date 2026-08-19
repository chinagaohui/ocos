"""Phase 27 — Simulator: 执行模拟。

模拟 Plan 执行，检测:
  - 死锁
  - 超时风险
  - 资源冲突
  - 拓扑预算违规
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ocos.planning.models import (
    MAX_DAG_DEPTH,
    MAX_PARALLEL_WIDTH,
    ExecutionStrategy,
    Plan,
    TaskDAG,
    TaskStatus,
)


@dataclass
class SimulationResult:
    """模拟结果。"""
    plan_id: str
    success: bool
    total_steps: int
    estimated_duration: int
    warnings: list[str] = field(default_factory=list)
    deadlock_detected: bool = False
    risks: list[str] = field(default_factory=list)


class PlanSimulator:
    """执行计划模拟器。"""

    @staticmethod
    def simulate(plan: Plan) -> SimulationResult:
        """模拟整个 Plan 执行。"""
        dag = plan.dag
        warnings: list[str] = []
        risks: list[str] = []

        # 1. 死锁检测
        deadlock = not dag.validate_acyclic()
        if deadlock:
            return SimulationResult(
                plan_id=plan.plan_id,
                success=False,
                total_steps=0,
                estimated_duration=0,
                warnings=["Deadlock detected: DAG contains a cycle"],
                deadlock_detected=True,
            )

        # 2. 拓扑预算检查
        groups = dag.parallel_groups()
        if len(groups) > MAX_DAG_DEPTH:
            warnings.append(
                f"DAG depth {len(groups)} exceeds MAX_DAG_DEPTH {MAX_DAG_DEPTH}"
            )
        for i, group in enumerate(groups):
            if len(group) > MAX_PARALLEL_WIDTH:
                warnings.append(
                    f"Level {i} has {len(group)} tasks, "
                    f"exceeds MAX_PARALLEL_WIDTH {MAX_PARALLEL_WIDTH}"
                )

        # 3. 时长估算（考虑策略）
        total_duration = PlanSimulator._estimate_duration(dag, plan.strategy)

        # 4. 风险分析
        tasks = list(dag.tasks.values())
        long_tasks = [t for t in tasks if t.estimated_duration > 600]
        for t in long_tasks:
            risks.append(
                f"Task {t.id} ({t.description}) has long duration "
                f"({t.estimated_duration}s)"
            )

        # 高重试风险
        retry_tasks = [t for t in tasks if t.retry_policy in ("retry_3x", "retry_with_fallback")]
        if retry_tasks:
            risks.append(f"{len(retry_tasks)} task(s) have retry policy enabled")

        return SimulationResult(
            plan_id=plan.plan_id,
            success=len(warnings) == 0,
            total_steps=len(groups),
            estimated_duration=total_duration,
            warnings=warnings,
            deadlock_detected=False,
            risks=risks,
        )

    @staticmethod
    def _estimate_duration(dag: TaskDAG, strategy: ExecutionStrategy) -> int:
        """基于策略估算总时长。"""
        groups = dag.parallel_groups()
        tasks = dag.tasks

        if strategy == ExecutionStrategy.SEQUENTIAL:
            return sum(
                tasks[tid].estimated_duration
                for group in groups
                for tid in group
            )

        elif strategy == ExecutionStrategy.PARALLEL:
            # 并行: 总时长 = 最大时长
            return max(
                tasks[tid].estimated_duration
                for group in groups
                for tid in group
            )

        else:  # PRIORITY_DRIVEN
            # 每层取最大，跨层加总
            return sum(
                max(tasks[tid].estimated_duration for tid in group)
                for group in groups
            )
