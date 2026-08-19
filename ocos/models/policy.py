"""
Policy Model — 策略引擎数据模型。

Phase 19 — 第四个能力引擎。

策略引擎负责评估决策/行动是否符合预定义的规则集。
不与任何 Runtime Engine 重叠——策略是规则评估，不是生命周期管理。
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


class PolicyEffect(str, Enum):
    """策略规则的效果类型。"""
    ALLOW = "allow"           # 明确允许
    DENY = "deny"             # 明确禁止
    WARN = "warn"             # 警告（不阻止但标记）


class PolicyDomain(str, Enum):
    """策略适用的领域。"""
    SECURITY = "security"
    QUALITY = "quality"
    COMPLIANCE = "compliance"
    RESOURCE = "resource"
    PREFERENCE = "preference"
    CUSTOM = "custom"


@dataclasses.dataclass(frozen=True)
class PolicyRule:
    """策略规则定义。"""
    rule_id: str = dataclasses.field(default_factory=lambda: uuid.uuid4().hex)
    name: str = ""
    description: str = ""
    domain: PolicyDomain = PolicyDomain.CUSTOM
    effect: PolicyEffect = PolicyEffect.ALLOW
    priority: int = 0  # 数值越大优先级越高
    condition: str = ""  # 规则条件的简略描述（引擎不执行条件，交给评估器判断）
    metadata: dict[str, Any] = dataclasses.field(default_factory=dict)


@dataclasses.dataclass(frozen=True)
class PolicyEvaluation:
    """单条规则评估结果。"""
    rule_id: str = ""
    rule_name: str = ""
    effect: PolicyEffect = PolicyEffect.ALLOW
    passed: bool = True
    detail: str = ""


@dataclasses.dataclass(frozen=True)
class PolicyTrace:
    """策略评估的完整记录。"""
    trace_id: str = dataclasses.field(default_factory=lambda: uuid.uuid4().hex)
    process_id: str = ""
    target_description: str = ""  # 被评估的目标描述
    rules: tuple[PolicyRule, ...] = dataclasses.field(default_factory=tuple)
    evaluations: tuple[PolicyEvaluation, ...] = dataclasses.field(default_factory=tuple)
    all_passed: bool = True
    input_addresses: tuple[str, ...] = dataclasses.field(default_factory=tuple)
    output_addresses: tuple[str, ...] = dataclasses.field(default_factory=tuple)
    error: str = ""
    timestamp: str = dataclasses.field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    schema_version: str = SCHEMA_VERSION
