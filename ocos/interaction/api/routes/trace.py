"""OCOS HTTP API — trace 路由。"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ocos.interaction.api.models import APIResponse
from ocos.interaction.base import PermissionGuard

router = APIRouter(prefix="/ocos/trace", tags=["trace"])
_guard = PermissionGuard()


@router.get(
    "/{trace_id}",
    response_model=APIResponse,
    deprecated=True,  # S4.2: 占位端点 — DecisionTrace store 未接线
)
async def get_trace(trace_id: str):
    """GET /ocos/trace/{id} — 查看决策追踪。

    S4.2: 占位端点 501 化 — 决策追踪由 trace 子系统承担，API 层未接线时
    明确 501，不再返回 200 空结果。
    """
    result = _guard.check("view_trace")
    if not result.allowed:
        raise HTTPException(status_code=403, detail=result.violations)

    raise HTTPException(
        status_code=501,
        detail={"note": "not implemented", "endpoint": f"/ocos/trace/{trace_id}"},
    )
