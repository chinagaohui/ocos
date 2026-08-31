"""
Process Model — Layer 4 认知过程层的数据模型实现。

对应 PROCESS_THEORY.md 中的核心概念（冻结中）：
- ProcessType：所有认知过程类型的统一枚举
- ProcessState：过程的运行状态
- ProcessStep：过程中的单个步骤（可追溯、可审计）
- TransformProcess：认知过程的统一表示（不嵌入任何具体认知能力）

设计原则（四"不堆叠"）：
1. Engine 不堆叠 — 认知能力不是独立 Engine
2. Model 不堆叠 — 认知能力不是特殊 dataclass（统一 TransformProcess + process_type）
3. 层命名不堆叠 — L4 是 Process Theory，不是 Reasoning Theory
4. Capability 不堆叠 — 新增能力优先用 ProcessType，不新增架构边界
"""

from __future__ import annotations

import dataclasses
import logging
import uuid
import warnings
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from ocos.kernel.abi import SCHEMA_VERSION
from ocos.models.information import UniversalAddress

logger = logging.getLogger(__name__)


# ── Enum: ProcessType（已弃用） ────────────────────────────────


class ProcessType(str, Enum):
    """已弃用。使用 TransformProcess.engine_id 替代。"""

    def __new__(cls, value: str) -> "ProcessType":
        warnings.warn(
            "ProcessType is deprecated, use TransformProcess.engine_id instead",
            DeprecationWarning,
            stacklevel=2,
        )
        _warned = getattr(cls, "_warned_values", None)
        if _warned is None:
            _warned = set()
            cls._warned_values = _warned
        if value not in _warned:   # P3-1: 每值仅告警一次（此前每 tick 刷 7 行）
            _warned.add(value)
            logger.warning("ProcessType used (deprecated): %s", value)
        obj = str.__new__(cls, value)
        obj._value_ = value
        return obj

    REASONING = "reasoning"
    DECISION = "decision"
    PLANNING = "planning"
    POLICY = "policy"
    ARBITRATION = "arbitration"
    SIMULATION = "simulation"
    LEARNING = "learning"

    # 未来扩展示例（仅作参考，不激活）：
    # REFLECTION = "reflection"
    # NEGOTIATION = "negotiation"
    # VERIFICATION = "verification"
    # OPTIMIZATION = "optimization"
    # SELF_REPAIR = "self_repair"


# ── Enum: ProcessState ─────────────────────────────────────────────────


class ProcessState(str, Enum):
    """Process 的状态生命周期。

    CREATED → RUNNING → COMPLETED
                      ↘ FAILED
    """

    CREATED = "created"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


# ── Dataclass: ProcessStep ─────────────────────────────────────────────


@dataclasses.dataclass(frozen=True)
class ProcessStep:
    """Process 中的单个步骤。

    设计原则：
    - 不拥有 Information（使用地址引用）
    - 不包含执行逻辑（纯数据）
    - 可序列化、可追踪
    - 必须引用 Evidence（可追溯审计）
    """

    step_id: str = dataclasses.field(default_factory=lambda: uuid.uuid4().hex)
    description: str = ""
    input_addresses: tuple[UniversalAddress, ...] = dataclasses.field(
        default_factory=tuple
    )
    output_addresses: tuple[UniversalAddress, ...] = dataclasses.field(
        default_factory=tuple
    )
    operation: str = ""  # 步骤操作描述（如 "retrieve", "infer", "compare"）
    confidence: float = 0.0  # 0.0 ~ 1.0

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be in [0.0, 1.0]")
        logger.debug("ProcessStep created: step_id=%s, operation=%s, confidence=%.2f", self.step_id, self.operation, self.confidence)


# ── Dataclass: TransformProcess ────────────────────────────────────────


@dataclasses.dataclass(frozen=True)
class TransformProcess:
    """OCOS 认知过程的统一表示。

    不变量（四条）：
    1. Process 不拥有 Information（使用地址引用，不嵌入）
    2. Process 不改变 Information 生命周期（由 Lifecycle Engine 管理）
    3. Process 不执行 Action（由 Execution 层处理）
    4. Process 必须引用 Evidence（可追溯审计）
    """

    process_id: str = dataclasses.field(default_factory=lambda: uuid.uuid4().hex)
    process_type: ProcessType = ProcessType.REASONING
    engine_id: Optional[str] = None  # 替代 process_type
    process_state: ProcessState = ProcessState.CREATED
    input_addresses: tuple[UniversalAddress, ...] = dataclasses.field(
        default_factory=tuple
    )
    output_addresses: tuple[UniversalAddress, ...] = dataclasses.field(
        default_factory=tuple
    )
    steps: tuple[ProcessStep, ...] = dataclasses.field(default_factory=tuple)
    confidence: float = 0.0  # 0.0 ~ 1.0
    metadata: dict[str, Any] = dataclasses.field(default_factory=dict)
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be in [0.0, 1.0]")
        logger.debug("TransformProcess created: process_id=%s, type=%s, state=%s", self.process_id, self.process_type.value, self.process_state.value)
