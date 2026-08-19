"""OCOS HTTP API — plan 路由。"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ocos.goal.models import GoalDomain
from ocos.kernel.goal_types import GoalStatus as KernelGoalStatus
from ocos.interaction.api.models import (
    APIResponse,
    GoalDomainAPI,
    PlanRequest,
    PlanResponse,
    GoalStatusAPI,
)
from ocos.interaction.base import GoalRequest, PermissionGuard

router = APIRouter(prefix="/ocos/plan", tags=["plan"])
_guard = PermissionGuard()

DOMAIN_MAP = {
    GoalDomainAPI.writing: GoalDomain.WRITING,
    GoalDomainAPI.analysis: GoalDomain.ANALYSIS,
    GoalDomainAPI.research: GoalDomain.RESEARCH,
    GoalDomainAPI.development: GoalDomain.DEVELOPMENT,
}

_STATUS_MAP: dict[KernelGoalStatus, GoalStatusAPI] = {
    KernelGoalStatus.PENDING: GoalStatusAPI.pending,
    KernelGoalStatus.ACTIVE: GoalStatusAPI.active,
    KernelGoalStatus.COMPLETED: GoalStatusAPI.completed,
    KernelGoalStatus.CANCELLED: GoalStatusAPI.abandoned,
    KernelGoalStatus.FAILED: GoalStatusAPI.failed,
    KernelGoalStatus.ABANDONED: GoalStatusAPI.abandoned,
}


@router.post("", response_model=APIResponse)
async def request_plan(req: PlanRequest):
    """POST /ocos/plan — 请求规划。

    API → PermissionGuard → GoalRequest → UserGoal
    """
    result = _guard.check("request_plan")
    if not result.allowed:
        raise HTTPException(status_code=403, detail=result.violations)

    try:
        goal_req = GoalRequest.create(
            raw_input=req.goal,
            objective=req.goal,
            domain=DOMAIN_MAP[req.domain],
            caller="api",
        )
        goal = goal_req.to_user_goal()

        # Phase 29-F: TaskDecomposer real-time decomposition
        from ocos.planning.decomposer import TaskDecomposer
        from ocos.planning.strategy import StrategyEngine
        dag = TaskDecomposer.decompose(goal)
        strategy = StrategyEngine.select(dag)
        tasks = dag.topological_order()
        plan_steps = [
            {"id": tid, "description": dag.tasks[tid].description,
             "task_type": dag.tasks[tid].task_type,
             "agent_type": dag.tasks[tid].agent_type,
             "estimated_duration": dag.tasks[tid].estimated_duration}
            for tid in tasks
        ]

        return APIResponse(
            success=True,
            message=f"Plan created for goal: {goal.id} — {strategy.value}",
            data=PlanResponse(
                goal_id=goal.id,
                status=_STATUS_MAP.get(goal.status, GoalStatusAPI.pending),
                plan_steps=plan_steps,
                note=f"{len(tasks)} tasks, strategy={strategy.value}",
            ).model_dump(),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
