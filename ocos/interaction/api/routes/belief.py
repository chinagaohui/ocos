"""OCOS HTTP API — belief 路由。"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from ocos.interaction.api.models import APIResponse, BeliefResponse
from ocos.interaction.base import PermissionGuard

router = APIRouter(prefix="/ocos/belief", tags=["belief"])
_guard = PermissionGuard()


@router.get("", response_model=APIResponse)
async def query_beliefs(
    domain: str | None = Query(default=None, description="信念域过滤器"),
    min_confidence: float = Query(default=0.0, ge=0.0, le=1.0, description="最低置信度"),
    limit: int = Query(default=20, ge=1, le=100, description="返回条数"),
):
    """GET /ocos/belief — 查询信念列表。

    API → PermissionGuard → BeliefStore (TBD)
    """
    result = _guard.check("view_belief")
    if not result.allowed:
        raise HTTPException(status_code=403, detail=result.violations)

    return APIResponse(
        success=True,
        message=f"Belief query: domain={domain}, min_confidence={min_confidence}",
        data=BeliefResponse(
            beliefs=[],
            total=0,
            counts_by_status={},
            note="BeliefStore integration TBD",
        ).model_dump(),
    )
