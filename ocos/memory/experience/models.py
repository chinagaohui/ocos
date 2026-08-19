"""Phase 24.1 — ExperienceCapture 数据模型。

TraceBundle + ExperienceCandidate (frozen dataclass)。

设计:
  - TraceBundle = 认知链路五要素封装
  - ExperienceCandidate = frozen，创建后不可修改
  - INCOMPLETE 不丢弃，保留供后续补充
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional


class ExperienceStatus(Enum):
    COMPLETE = "complete"
    INCOMPLETE = "incomplete"
    REJECTED = "rejected"
    ARCHIVED = "archived"


class ExperienceSource(Enum):
    DECISION = "decision"
    REFLECTION = "reflection"
    ANOMALY = "anomaly"
    GOAL_COMPLETION = "goal_completion"


@dataclass(frozen=True)
class TraceBundle:
    """一段认知链路的完整追踪。

    五要素: Observation + ReasoningTrace + DecisionTrace + Action + Outcome
    Reflection 为可选增强。
    """

    observation: dict
    reasoning_trace_id: str
    decision_trace_id: str
    action_result: dict
    outcome: dict
    reflection_trace_id: Optional[str] = None
    source_trace_ids: Optional[list[str]] = None
    timestamp: Optional[datetime] = None
    environment_state: Optional[dict] = None
    goal_context: Optional[dict] = None

    def __post_init__(self):
        if self.timestamp is None:
            object.__setattr__(self, "timestamp", datetime.now())
        if self.source_trace_ids is None:
            object.__setattr__(self, "source_trace_ids", [])


@dataclass(frozen=True)
class ExperienceCandidate:
    """完整认知链路的封装。一旦创建，不可变更。"""

    id: str
    trace_bundle: TraceBundle
    status: ExperienceStatus
    source: ExperienceSource
    context: dict
    completeness_score: float
    created_at: datetime
    sealed_at: datetime

    significance_score: Optional[float] = None
    boundary_passed: Optional[bool] = None
    rejection_reason: Optional[str] = None

    @classmethod
    def create(
        cls,
        trace_bundle: TraceBundle,
        source: ExperienceSource,
        context: dict,
        status: ExperienceStatus,
    ) -> "ExperienceCandidate":
        """工厂方法: 创建并自动生成 ID 和时间戳。"""
        timestamp = datetime.now()
        elements = [
            trace_bundle.observation,
            trace_bundle.reasoning_trace_id,
            trace_bundle.decision_trace_id,
            trace_bundle.action_result,
            trace_bundle.outcome,
        ]
        # 有效要素: 非 None、非空字符串、非空 dict
        def _is_present(value: object) -> bool:
            if value is None:
                return False
            if isinstance(value, str):
                return bool(value)
            if isinstance(value, dict):
                return bool(value)
            return True

        present = sum(1 for e in elements if _is_present(e))
        score = present / len(elements)
        if trace_bundle.reflection_trace_id:
            score = min(1.0, score + 0.1)

        return cls(
            id=f"EXP-{timestamp.strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}",
            trace_bundle=trace_bundle,
            status=status,
            source=source,
            context=context,
            completeness_score=round(score, 2),
            created_at=timestamp,
            sealed_at=timestamp,
        )
