"""OCOS HTTP API — /ocos/metrics 路由（升级方案 §3.1: 生命体征仪表盘暴露）。

只读聚合 vitals（episodes/goals/pending/user_messages 现有表），
经 AuthMiddleware 保护（与全部业务端点同一 token 源 — 红线 R2 合规）。
"""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import APIRouter, Query

from ocos.interaction.api.models import APIResponse

router = APIRouter(prefix="/ocos/metrics", tags=["metrics"])


@router.get("", response_model=APIResponse)
async def get_vitals(
    window: int = Query(7, ge=1, le=90, description="聚合窗口（天）"),
    phase: str = Query("L4", pattern="^(L0|L1|L2|L3|L4)$",
                       description="§3.4 验收阶段（决定阈值集）"),
):
    """GET /ocos/metrics — 生命体征快照 + 阶段阈值判定。

    返回 data.vitals（§3.1 指标聚合）与 data.threshold_violations
    （check_thresholds 结果，空列表 = 达到该阶段出口判据）。
    """
    from ocos.interaction.cli.paths import resolve_db_path
    from ocos.monitoring.vitals import check_thresholds, compute_vitals

    db = os.environ.get("OCOS_DB_PATH", "") or resolve_db_path()
    vitals = compute_vitals(db, window_days=window)
    return APIResponse(
        success=True,
        message=f"vitals snapshot (window={window}d, phase={phase})",
        data={
            "vitals": vitals,
            "phase": phase,
            "threshold_violations": check_thresholds(vitals, phase),
        },
    )
