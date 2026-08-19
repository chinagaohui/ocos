"""Phase 23-A — CapabilityDescriptor ABI (§4.4.2 CapabilityNode)。

能力描述符：单条能力的结构化元数据。
与 EngineManifest 的关系：CapabilityDescriptor 是能力的抽象面，
EngineManifest 是引擎实例的元数据。一个 Provider 可以提供多个 CapabilityDescriptor。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class CapabilityStatus(str, Enum):
    """能力生命周期状态。"""
    DISCOVERED = "DISCOVERED"   # 已发现，未注册
    REGISTERED = "REGISTERED"   # 已注册，未验证
    VERIFIED = "VERIFIED"       # 已通过验证
    DEPRECATED = "DEPRECATED"   # 标记为废弃
    DISABLED = "DISABLED"       # 已禁用


class CapabilityCategory(str, Enum):
    """能力分类。"""
    REASONING = "reasoning"
    PLANNING = "planning"
    DECISION = "decision"
    EXECUTION = "execution"
    LEARNING = "learning"
    REFLECTION = "reflection"
    PREDICTION = "prediction"
    COMMUNICATION = "communication"
    PERCEPTION = "perception"
    CREATIVITY = "creativity"
    CUSTOM = "custom"


@dataclass(frozen=True)
class CapabilityDescriptor:
    """能力描述符 — 一条独立的能力单元。

    §4.4.2 CapabilityNode 的 ABI 定义。

    Attributes:
        capability_id: 全局唯一标识 (e.g. "ocos.reasoning.deductive")
        name: 人类可读名称
        category: 能力分类
        description: 能力描述
        version: 语义版本
        input_schema: 输入 JSON Schema
        output_schema: 输出 JSON Schema
        tags: 标签列表
        status: 生命周期状态
        metadata: 扩展元数据
    """
    capability_id: str
    name: str
    category: CapabilityCategory = CapabilityCategory.CUSTOM
    description: str = ""
    version: str = "1.0.0"
    input_schema: dict[str, Any] = field(default_factory=dict)
    output_schema: dict[str, Any] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)
    status: CapabilityStatus = CapabilityStatus.DISCOVERED
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc),
        compare=False,
    )

    def match_tag(self, tag: str) -> bool:
        return tag in self.tags

    def match_category(self, category: CapabilityCategory) -> bool:
        return self.category == category
