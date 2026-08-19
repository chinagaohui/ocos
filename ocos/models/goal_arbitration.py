"""
GoalArbitration Model — 目标仲裁引擎数据模型。

Phase 19 — 第五个能力引擎。

在冲突目标之间做仲裁决策：哪些目标优先执行，哪些挂起/降级。
"""

from __future__ import annotations

import dataclasses
import logging
import uuid
from datetime import datetime, timezone
from enum import Enum

logger = logging.getLogger(__name__)


class ArbitrationStrategy(str, Enum):
    """仲裁策略。"""
    PRIORITY = "priority"          # 优先级高低裁决
    WEIGHTED = "weighted"          # 加权评分裁决
    EMERGENCY = "emergency"        # 紧急程度优先
    RESOURCE_AWARE = "resource_aware"  # 资源约束优先


@dataclasses.dataclass(frozen=True)
class GoalCandidate:
    """待仲裁的目标候选。"""
    goal_id: str
    label: str
    priority: int                      # 1=最高
    urgency: float = 0.0               # 0.0~1.0
    resource_cost: float = 1.0         # 预估资源消耗
    weight: float = 1.0                # 加权分


@dataclasses.dataclass(frozen=True)
class ArbitrationResult:
    """单个目标的仲裁结果。"""
    candidate_id: str
    goal_id: str
    label: str
    selected: bool                     # 是否被选中执行
    rank: int                          # 排序位置
    score: float                       # 策略评分
    reason: str                        # 仲裁理由


@dataclasses.dataclass(frozen=True)
class GoalArbitrationTrace:
    """仲裁过程的完整记录。"""
    trace_id: str = dataclasses.field(default_factory=lambda: str(uuid.uuid4()))
    strategy: ArbitrationStrategy = ArbitrationStrategy.PRIORITY
    candidates: tuple[ArbitrationResult, ...] = ()
    selected_ids: tuple[str, ...] = ()
    suspended_ids: tuple[str, ...] = ()
    created_at: str = dataclasses.field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    summary: str = ""
