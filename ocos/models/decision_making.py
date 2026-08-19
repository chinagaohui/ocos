"""
DecisionMaking Model — 决策生成引擎数据模型。

Phase 19 — 第三个能力引擎。

与 Phase 18 的 DecisionRuntimeEngine 互补:
- DecisionRuntimeEngine: 决策生命周期管理（create/commit/revoke）
- DecisionMakingEngine: 决策逻辑（选项评分、排序、权衡选择）

遵循"4 不堆叠"原则:
- 使用 ProcessType.DECISION，不新增 ProcessType
- 决策过程记录为 DecisionMakingTrace，不注入新生命周期
"""

from __future__ import annotations

import dataclasses
import logging
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from ocos.kernel.abi import SCHEMA_VERSION

logger = logging.getLogger(__name__)


class DecisionStrategy(str, Enum):
    """决策策略类型。"""
    SCORING = "scoring"                # 加权评分
    RANKING = "ranking"                # 排序选择
    MAJORITY = "majority"              # 多数投票
    SATISFICING = "satisficing"        # 满意原则（选择第一个满足阈值的）
    OPPORTUNITY_COST = "opportunity_cost"  # 机会成本
    PARETO = "pareto"                  # 帕累托最优（仅保留非支配选项）


@dataclasses.dataclass(frozen=True)
class DecisionOption:
    """候选选项。"""
    option_id: str = dataclasses.field(default_factory=lambda: uuid.uuid4().hex)
    label: str = ""
    scores: dict[str, float] = dataclasses.field(default_factory=dict)  # 维度 → 分数
    total_score: float = 0.0
    rank: int = 0
    is_selected: bool = False


@dataclasses.dataclass(frozen=True)
class DecisionMakingTrace:
    """决策过程的完整记录。"""
    trace_id: str = dataclasses.field(default_factory=lambda: uuid.uuid4().hex)
    process_id: str = ""
    strategy: DecisionStrategy = DecisionStrategy.SCORING
    options: tuple[DecisionOption, ...] = dataclasses.field(default_factory=tuple)
    selected_option_id: str = ""
    input_addresses: tuple[str, ...] = dataclasses.field(default_factory=tuple)
    output_addresses: tuple[str, ...] = dataclasses.field(default_factory=tuple)
    rationale: str = ""
    error: str = ""
    timestamp: str = dataclasses.field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    schema_version: str = SCHEMA_VERSION
