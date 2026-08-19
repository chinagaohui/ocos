"""OCOS HTTP API — trace 路由。"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ocos.interaction.api.models import APIResponse, TraceResponse
from ocos.interaction.base import PermissionGuard

router = APIRouter(prefix="/ocos/trace", tags=["trace"])
_guard = PermissionGuard()


@router.get("/{trace_id}", response_model=APIResponse)
async def get_trace(trace_id: str):
    """GET /ocos/trace/{id} — 查看决策追踪。

    API → PermissionGuard → DecisionTrace store (TBD)
    """
    result = _guard.check("view_trace")
    if not result.allowed:
        raise HTTPException(status_code=403, detail=result.violations)

    return APIResponse(
        success=True,
        message=f"Trace: {trace_id}",
        data=TraceResponse(
            trace_id=trace_id,
            steps=[],
            note="DecisionTrace store integration TBD",
        ).model_dump(),
    )
