"""OCOS HTTP API — server 入口。

FastAPI 应用工厂，聚合所有 Interaction Layer API 路由。

启动方式:
    uvicorn ocos.interaction.api.server:app --reload
    或
    python -m ocos.interaction.api.server

架构约束:
    API → PermissionGuard → Kernel（Goal Interface）
    API 不拥有写入 Memory/Self/Constitution 的权限。
"""

from __future__ import annotations

import sys

from fastapi import FastAPI

from ocos.interaction.api.models import HealthResponse, APIResponse

app = FastAPI(
    title="OCOS Cognitive Interface API",
    description="OCOS Digital Brain — Cognitive Interface Layer. Provides REST endpoints for human agents, external systems, and web frontends.",
    version="1.1",
    docs_url="/ocos/docs",
    redoc_url="/ocos/redoc",
    openapi_url="/ocos/openapi.json",
)


@app.get("/ocos/health", tags=["health"])
async def health_check():
    """GET /ocos/health — 健康检查。"""
    return APIResponse(
        success=True,
        message="OCOS Cognitive Interface Layer is healthy",
        data=HealthResponse(status="ok", version="1.1", layer="cognitive_interface").model_dump(),
    )


# ── 注册路由 ─────────────────────────────────────────────────────

from ocos.interaction.api.routes.goal import router as goal_router
from ocos.interaction.api.routes.plan import router as plan_router
from ocos.interaction.api.routes.memory import router as memory_router
from ocos.interaction.api.routes.belief import router as belief_router
from ocos.interaction.api.routes.trace import router as trace_router
from ocos.interaction.api.routes.chat import router as chat_router  # S6: WebChat

app.include_router(goal_router)
app.include_router(plan_router)
app.include_router(memory_router)
app.include_router(belief_router)
app.include_router(trace_router)
app.include_router(chat_router)


def main():
    """API 服务器入口。"""
    import os
    import uvicorn
    # S6：默认 8900，避免与 OpenTale（8000）端口冲突；可 OCOS_API_PORT 覆盖
    port = int(os.getenv("OCOS_API_PORT", "8900"))
    print(f"Starting OCOS Cognitive Interface API on http://localhost:{port}")
    print(f"Docs: http://localhost:{port}/ocos/docs")
    uvicorn.run(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    sys.exit(main())
