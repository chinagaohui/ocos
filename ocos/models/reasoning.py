"""
Reasoning Model — 推理引擎的数据模型。

遵循四"不堆叠"原则：
1. 不新增架构边界 — 推理能力是 ProcessType.REASONING，不是独立架构层
2. 不新增 ProcessType 以外的生命周期 — 推理生命周期由 ProcessRuntimeEngine 管理
3. 数据模型仅描述推理过程的结构化记录
4. 推理的具体操作（deduction/induction/abduction）是 operation 字段值，不是类型

设计:
- InferenceRule: 推理规则描述（纯元数据）
- ReasoningTrace: 一次推理执行的完整记录
  包含有序的推理步骤、输入输出地址、置信度
- 不包含执行逻辑 — 执行在 ReasoningEngine 中
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


class InferenceOperation(str, Enum):
    """推理操作类型。

    每个操作是 Information → Information 的转换规则。
    """
    DEDUCTION = "deduction"        # 演绎：从一般到特殊
    INDUCTION = "induction"        # 归纳：从特殊到一般
    ABDUCTION = "abduction"        # 溯因：从结果到原因
    ANALOGY = "analogy"            # 类比：从相似到相似
    ANALYSIS = "analysis"          # 分析：分解为子问题
    SYNTHESIS = "synthesis"        # 综合：组合为整体
    COMPARISON = "comparison"      # 比较：差异与相似
    EVALUATION = "evaluation"      # 评估：价值判断


@dataclasses.dataclass(frozen=True)
class ReasoningStep:
    """推理过程中的一个步骤。

    每个步骤记录:
    - 输入信息地址（从何处获取前提）
    - 使用的推理操作
    - 输出信息地址（结论写入何处）
    - 置信度
    - 自由文本理由
    """
    step_index: int
    operation: str  # InferenceOperation 的值
    input_address: str  # 前提信息地址
    output_address: str  # 结论信息地址
    premises: tuple[str, ...] = dataclasses.field(default_factory=tuple)
    conclusion: str = ""
    confidence: float = 0.0
    metadata: dict[str, Any] = dataclasses.field(default_factory=dict)

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"confidence must be in [0.0, 1.0], got {self.confidence}")
        logger.debug("ReasoningStep created: step=%d, operation=%s, confidence=%.2f", self.step_index, self.operation, self.confidence)


@dataclasses.dataclass(frozen=True)
class ReasoningTrace:
    """一次推理执行的完整记录。

    被 ProcessRuntimeEngine 的 Process 引用。
    一个 REASONING Process 可能产生多个 ReasoningTrace。
    """
    trace_id: str = dataclasses.field(default_factory=lambda: uuid.uuid4().hex)
    process_id: str = ""
    steps: tuple[ReasoningStep, ...] = dataclasses.field(default_factory=tuple)
    input_addresses: tuple[str, ...] = dataclasses.field(default_factory=tuple)
    output_addresses: tuple[str, ...] = dataclasses.field(default_factory=tuple)
    overall_confidence: float = 0.0
    error: str = ""
    timestamp: str = dataclasses.field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not 0.0 <= self.overall_confidence <= 1.0:
            raise ValueError(
                f"overall_confidence must be in [0.0, 1.0], got {self.overall_confidence}"
            )
        logger.debug("ReasoningTrace created: trace_id=%s, process_id=%s, steps=%d, confidence=%.2f", self.trace_id, self.process_id, len(self.steps), self.overall_confidence)
