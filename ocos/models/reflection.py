"""
Reflection Model — 反思引擎数据模型。

Phase 19 — 第八个能力引擎。

对过往过程、决策、轨迹进行反思，产出行为了洞见和改进建议。
"""

from __future__ import annotations

import dataclasses
import logging
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class ReflectionStrategy(str, Enum):
    """反思策略。"""
    CRITICAL = "critical"           # 批判性反思：发现错误/不足
    COMPARATIVE = "comparative"     # 比较反思：对比预期与实际
    CAUSAL = "causal"               # 因果反思：分析原因与结果
    META = "meta"                   # 元反思：反思反思过程本身


@dataclasses.dataclass(frozen=True)
class ReflectionInsight:
    """单条反思洞见。"""
    category: str                   # 错误/改进/模式/验证
    description: str                # 洞见描述
    evidence: str = ""              # 支撑证据
    severity: str = "info"          # info / warning / critical
    recommendation: str = ""        # 改进建议
    metadata: dict[str, Any] = dataclasses.field(default_factory=dict)


@dataclasses.dataclass(frozen=True)
class ReflectionTrace:
    """一次反思会话记录。"""
    trace_id: str = dataclasses.field(default_factory=lambda: str(uuid.uuid4()))
    strategy: ReflectionStrategy = ReflectionStrategy.CRITICAL
    subject_type: str = ""          # 反思对象类型（process / trace / outcome）
    subject_id: str = ""            # 反思对象 ID
    insights: tuple[ReflectionInsight, ...] = ()
    created_at: str = dataclasses.field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    summary: str = ""
