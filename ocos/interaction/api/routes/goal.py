"""OCOS HTTP API — goal 路由。"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ocos.goal.models import GoalDomain
from ocos.kernel.goal_types import GoalStatus as KernelGoalStatus
from ocos.interaction.api.models import (
    APIResponse,
    GoalCreateRequest,
    GoalDomainAPI,
    GoalResponse,
    GoalStatusAPI,
)
from ocos.interaction.base import GoalRequest, PermissionGuard

router = APIRouter(prefix="/ocos/goal", tags=["goal"])
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
async def create_goal(req: GoalCreateRequest):
    """POST /ocos/goal — 创建新目标。

    调用链: API → PermissionGuard → GoalRequest → UserGoal
    """
    result = _guard.check("create_goal")
    if not result.allowed:
        raise HTTPException(status_code=403, detail=result.violations)

    try:
        goal_req = GoalRequest.create(
            raw_input=req.goal,
            objective=req.goal,
            domain=DOMAIN_MAP[req.domain],
            caller="api",
            priority=req.priority,
            constraints=tuple(req.constraints) if req.constraints else (),
        )
        goal = goal_req.to_user_goal()

        return APIResponse(
            success=True,
            message=f"Goal created: {goal.id}",
            data=GoalResponse(
                goal_id=goal.id,
                status=_STATUS_MAP.get(goal.status, GoalStatusAPI.pending),
                domain=GoalDomainAPI(goal.domain.value),
                priority=goal.priority,
                caller=goal.caller,
                created_at=goal.created_at.isoformat() if hasattr(goal, 'created_at') else "",
            ).model_dump(),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{goal_id}", response_model=APIResponse)
async def get_goal(goal_id: str):
    """GET /ocos/goal/{id} — 查询目标状态。"""
    result = _guard.check("create_goal")
    if not result.allowed:
        raise HTTPException(status_code=403, detail=result.violations)

    # Note: GoalStore integration TBD
    return APIResponse(
        success=True,
        message=f"Goal {goal_id} queried",
        data={"goal_id": goal_id, "note": "GoalStore integration TBD"},
    )
