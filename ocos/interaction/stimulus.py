"""Phase 22-F — Stimulus 模型: 外部刺激 → Intent + Context。

职责:
  - Stimulus: 外部输入的内部表示
  - StimulusType: 输入类型枚举
  - StimulusResult: 刺激处理结果
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class StimulusType(Enum):
    """刺激类型。"""
    TEXT = "text"
    COMMAND = "command"
    EVENT = "event"
    OBSERVATION = "observation"
    UNKNOWN = "unknown"

    @classmethod
    def from_str(cls, s: str) -> "StimulusType":
        try:
            return cls(s.lower())
        except ValueError:
            return cls.UNKNOWN


@dataclass
class Stimulus:
    """外部或内部刺激。

    Attributes:
        source: 来源标识 (cli/api/event/engine)
        type: 刺激类型
        content: 内容
        metadata: 附加元数据
        timestamp: 时间戳
    """
    source: str
    type: StimulusType = StimulusType.TEXT
    content: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def is_command(self) -> bool:
        return self.type == StimulusType.COMMAND

    @property
    def is_text(self) -> bool:
        return self.type == StimulusType.TEXT


@dataclass
class StimulusResult:
    """刺激处理结果。"""
    stimulus: Stimulus
    accepted: bool = False
    error: str = ""
    response: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
