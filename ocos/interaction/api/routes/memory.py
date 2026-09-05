"""OCOS HTTP API — memory 路由。"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ocos.interaction.api.models import APIResponse, MemoryQueryRequest
from ocos.interaction.base import PermissionGuard

router = APIRouter(prefix="/ocos/memory", tags=["memory"])
_guard = PermissionGuard()


@router.post(
    "/query",
    response_model=APIResponse,
    deprecated=True,  # S4.2: 占位端点 — EpisodeStore 未接线
)
async def query_memory(req: MemoryQueryRequest):
    """POST /ocos/memory/query — 查询记忆。

    S4.2: 占位端点 501 化 — 记忆查询由 memory 子系统（hub.episode）承担，
    API 层未接线时明确 501，不再返回 200 空结果误导调用方。
    """
    result = _guard.check("query_memory")
    if not result.allowed:
        raise HTTPException(status_code=403, detail=result.violations)

    raise HTTPException(
        status_code=501,
        detail={"note": "not implemented", "endpoint": "/ocos/memory/query"},
    )
