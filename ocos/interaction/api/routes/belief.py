"""OCOS HTTP API — belief 路由。"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from ocos.interaction.api.models import APIResponse
from ocos.interaction.base import PermissionGuard

router = APIRouter(prefix="/ocos/belief", tags=["belief"])
_guard = PermissionGuard()


@router.get(
    "",
    response_model=APIResponse,
    deprecated=True,  # S4.2: 占位端点 — BeliefStore 未接线
)
async def query_beliefs(
    domain: str | None = Query(default=None, description="信念域过滤器"),
    min_confidence: float = Query(default=0.0, ge=0.0, le=1.0, description="最低置信度"),
    limit: int = Query(default=20, ge=1, le=100, description="返回条数"),
):
    """GET /ocos/belief — 查询信念列表。

    S4.2: 占位端点 501 化 — 信念查询由记忆子系统承担，API 层未接线时
    明确 501，不再返回 200 空结果。
    """
    result = _guard.check("view_belief")
    if not result.allowed:
        raise HTTPException(status_code=403, detail=result.violations)

    raise HTTPException(
        status_code=501,
        detail={"note": "not implemented", "endpoint": "/ocos/belief"},
    )
