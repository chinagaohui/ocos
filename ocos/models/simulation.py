"""
Simulation Model — 模拟引擎数据模型。

Phase 19 — 第六个能力引擎。

模拟引擎运行假设情景/单步推演，记录每个步骤的状态变化。
不包含领域模拟逻辑——由使用者提供 step_fn。
"""

from __future__ import annotations

import dataclasses
import logging
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class SimulationStrategy(str, Enum):
    """模拟策略。"""
    WHAT_IF = "what_if"               # 假设分析：给定条件X，结果Y
    TIME_SERIES = "time_series"       # 时间序列：固定步长向前推进
    MONTE_CARLO = "monte_carlo"       # 蒙特卡洛：随机采样多次
    AGENT_BASED = "agent_based"       # 基于智能体：多实体交互


@dataclasses.dataclass(frozen=True)
class SimulationScenario:
    """模拟场景定义。"""
    scenario_id: str = dataclasses.field(
        default_factory=lambda: str(uuid.uuid4())
    )
    strategy: SimulationStrategy = SimulationStrategy.WHAT_IF
    initial_state: dict[str, Any] = dataclasses.field(default_factory=dict)
    parameters: dict[str, Any] = dataclasses.field(default_factory=dict)
    steps: int = 10


@dataclasses.dataclass(frozen=True)
class SimulationStep:
    """单步模拟结果。"""
    step_number: int
    state: dict[str, Any]
    delta: dict[str, Any]          # 本步变化
    metadata: dict[str, Any] = dataclasses.field(default_factory=dict)


@dataclasses.dataclass(frozen=True)
class SimulationTrace:
    """完整模拟记录。"""
    trace_id: str = dataclasses.field(default_factory=lambda: str(uuid.uuid4()))
    scenario_id: str = ""
    strategy: SimulationStrategy = SimulationStrategy.WHAT_IF
    steps: tuple[SimulationStep, ...] = ()
    initial_state: dict[str, Any] = dataclasses.field(default_factory=dict)
    parameters: dict[str, Any] = dataclasses.field(default_factory=dict)
    final_state: dict[str, Any] = dataclasses.field(default_factory=dict)
    created_at: str = dataclasses.field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    summary: str = ""
