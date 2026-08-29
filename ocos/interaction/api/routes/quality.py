"""OCOS HTTP API — 章节质量分析与趋势检测路由。

2026-08-23（老高裁决）：OpenTale 不 import ocos，仅纯 HTTP 转发。
本路由把 OCOS 的 QualityAnalyzer / TrendAnalyzer 暴露为 HTTP 端点，
供 OpenTale 生成流程每批章节后调用——OCOS 智脑据此检测质量趋势、
干预下一批生成（治本：跨章跑题/复读的架构级防线）。
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ocos.interaction.api.models import APIResponse
from ocos.interaction.base import PermissionGuard

router = APIRouter(prefix="/ocos/quality", tags=["quality"])
_guard = PermissionGuard()


class ChapterQualityRequest(BaseModel):
    """单章质量分析请求。"""
    chapter_text: str = Field(..., min_length=10)
    genre: str = "sci_fi"
    chapter_number: int = 1
    chapter_title: str = ""
    external_quality: float | None = None


class TrendAnalysisRequest(BaseModel):
    """多章趋势分析请求（检测跨章跑题/复读/衰减）。"""
    chapter_reports: list[dict[str, Any]] = Field(..., min_length=2)
    window_size: int | None = None


@router.post("/chapter", response_model=APIResponse)
async def analyze_chapter(req: ChapterQualityRequest):
    """POST /ocos/quality/chapter — 单章质量分析（OCOS 智脑视角）。"""
    result = _guard.check("analyze_quality")
    if not result.allowed:
        raise HTTPException(status_code=403, detail=result.violations)
    try:
        from ocos.opentale_bridge.quality_analyzer import QualityAnalyzer
        analyzer = QualityAnalyzer()
        report = analyzer.analyze(
            chapter_text=req.chapter_text,
            genre=req.genre,
            chapter_number=req.chapter_number,
            chapter_title=req.chapter_title,
            external_quality=req.external_quality,
        )
        return APIResponse(
            success=True,
            message=f"Quality analysis ch{req.chapter_number}",
            data={
                "overall_score": report.overall_score,
                "dimensions": report.to_ocos_feedback().get("ocos_dimensions", {}),
                "summary": report.summary,
                "recommendations": report.recommendations,
                "needs_repair": report.needs_repair(),
                "failing_dimensions": report.failing_dimensions(),
                "repair_guidance": report.repair_guidance(),
            },
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"quality analysis failed: {exc}")


@router.post("/trend", response_model=APIResponse)
async def analyze_trend(req: TrendAnalysisRequest):
    """POST /ocos/quality/trend — 多章趋势检测（跑题/复读/衰减信号）。"""
    result = _guard.check("analyze_trend")
    if not result.allowed:
        raise HTTPException(status_code=403, detail=result.violations)
    try:
        from ocos.opentale_bridge.trend_analyzer import TrendAnalyzer
        analyzer = TrendAnalyzer()
        signals = analyzer.analyze(
            chapter_reports=req.chapter_reports,
            window_size=req.window_size,
        )
        return APIResponse(
            success=True,
            message=f"Trend analysis: {len(signals)} signals",
            data={
                "signals": [s.to_dict() for s in signals],
                "signal_count": len(signals),
            },
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"trend analysis failed: {exc}")
