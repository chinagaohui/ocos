"""
Planning Model — 规划引擎的数据模型。

遵循四"不堆叠"原则：
- Planning 是 ProcessType.PLANNING 的能力提供者
- 不新增架构边界，不新增独立生命周期
- PlanningTrace 是规划过程的结构化记录
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


class PlanningStrategy(str, Enum):
    """规划策略类型。"""
    TOP_DOWN = "top_down"            # 自顶向下分解
    BOTTOM_UP = "bottom_up"          # 自底向上组合
    MEANS_END = "means_end"          # 手段-目的分析
    CASE_BASED = "case_based"        # 基于案例的规划
    ITERATIVE = "iterative"          # 迭代细化
    PARALLEL = "parallel"            # 并行分解


class PlanStatus(str, Enum):
    """计划的执行状态。"""
    DRAFT = "draft"
    APPROVED = "approved"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclasses.dataclass(frozen=True)
class PlanningStep:
    """规划步骤。"""
    step_id: str = dataclasses.field(default_factory=lambda: uuid.uuid4().hex)
    description: str = ""
    depends_on: tuple[str, ...] = dataclasses.field(default_factory=tuple)
    estimated_effort: int = 0  # 预估工作量（抽象单位）
    assignee: str = ""
    status: PlanStatus = PlanStatus.DRAFT
    metadata: dict[str, Any] = dataclasses.field(default_factory=dict)


@dataclasses.dataclass(frozen=True)
class PlanningTrace:
    """规划过程的完整记录。"""
    trace_id: str = dataclasses.field(default_factory=lambda: uuid.uuid4().hex)
    process_id: str = ""
    strategy: PlanningStrategy = PlanningStrategy.TOP_DOWN
    steps: tuple[PlanningStep, ...] = dataclasses.field(default_factory=tuple)
    total_effort: int = 0
    goal_address: str = ""
    input_addresses: tuple[str, ...] = dataclasses.field(default_factory=tuple)
    output_addresses: tuple[str, ...] = dataclasses.field(default_factory=tuple)
    error: str = ""
    timestamp: str = dataclasses.field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    schema_version: str = SCHEMA_VERSION
