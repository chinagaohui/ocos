"""
Learning Model — 学习引擎数据模型。

Phase 19 — 第七个能力引擎。

从过往经验/轨迹中学习，更新内部模型。
不包含具体学习算法——由使用者提供 learn_fn。
"""

from __future__ import annotations

import dataclasses
import logging
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class LearningStrategy(str, Enum):
    """学习策略。"""
    SUPERVISED = "supervised"             # 有监督：输入→输出映射
    REINFORCEMENT = "reinforcement"       # 强化：基于奖励信号调整
    PATTERN_DISCOVERY = "pattern_discovery"  # 模式发现：从未标注数据提取结构
    TRANSFER = "transfer"                 # 迁移：从已有模型适应新场景


@dataclasses.dataclass(frozen=True)
class LearningExample:
    """单个训练样本。"""
    input_data: dict[str, Any]
    output_data: dict[str, Any] = dataclasses.field(default_factory=dict)
    reward: float | None = None
    feedback: str = ""
    metadata: dict[str, Any] = dataclasses.field(default_factory=dict)


@dataclasses.dataclass(frozen=True)
class LearningModel:
    """学习产物——更新后的模型快照。"""
    model_id: str = dataclasses.field(default_factory=lambda: str(uuid.uuid4()))
    strategy: LearningStrategy = LearningStrategy.SUPERVISED
    parameters: dict[str, Any] = dataclasses.field(default_factory=dict)
    rules: tuple[dict[str, Any], ...] = ()
    accuracy: float | None = None
    metadata: dict[str, Any] = dataclasses.field(default_factory=dict)


@dataclasses.dataclass(frozen=True)
class LearningTrace:
    """一次学习会话记录。"""
    trace_id: str = dataclasses.field(default_factory=lambda: str(uuid.uuid4()))
    strategy: LearningStrategy = LearningStrategy.SUPERVISED
    examples_count: int = 0
    model: LearningModel | None = None
    created_at: str = dataclasses.field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    summary: str = ""
