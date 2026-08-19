"""
Prediction Model — 预测引擎数据模型。

Phase 19 — 第九个（最后）能力引擎。

基于当前数据和模型对系统未来状态进行预测，附带置信度评估。
"""

from __future__ import annotations

import dataclasses
import logging
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class PredictionStrategy(str, Enum):
    """预测策略。"""
    EXTRAPOLATION = "extrapolation"     # 趋势外推
    REGRESSION = "regression"           # 回归分析
    CLASSIFICATION = "classification"   # 分类预测
    ENSEMBLE = "ensemble"               # 集成方法


@dataclasses.dataclass(frozen=True)
class ConfidenceInterval:
    """置信区间。"""
    lower: float
    upper: float
    confidence_level: float = 0.95      # 0.0 ~ 1.0


@dataclasses.dataclass(frozen=True)
class PredictionResult:
    """单次预测结果。"""
    value: float | str | dict[str, Any]
    confidence: float                   # 0.0 ~ 1.0
    label: str = ""
    interval: ConfidenceInterval | None = None
    metadata: dict[str, Any] = dataclasses.field(default_factory=dict)


@dataclasses.dataclass(frozen=True)
class PredictionTrace:
    """一次预测会话记录。"""
    trace_id: str = dataclasses.field(default_factory=lambda: str(uuid.uuid4()))
    strategy: PredictionStrategy = PredictionStrategy.EXTRAPOLATION
    input_summary: str = ""
    predictions: tuple[PredictionResult, ...] = ()
    created_at: str = dataclasses.field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    summary: str = ""
