"""OCOS HTTP API — memory 路由。"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ocos.interaction.api.models import APIResponse, MemoryQueryRequest, MemoryResponse
from ocos.interaction.base import PermissionGuard

router = APIRouter(prefix="/ocos/memory", tags=["memory"])
_guard = PermissionGuard()


@router.post("/query", response_model=APIResponse)
async def query_memory(req: MemoryQueryRequest):
    """POST /ocos/memory/query — 查询记忆。

    API → PermissionGuard → EpisodeStore (TBD)
    """
    result = _guard.check("query_memory")
    if not result.allowed:
        raise HTTPException(status_code=403, detail=result.violations)

    return APIResponse(
        success=True,
        message=f"Memory query: '{req.query}'",
        data=MemoryResponse(
            query=req.query,
            results=[],
            total=0,
            note="EpisodeStore integration TBD",
        ).model_dump(),
    )
