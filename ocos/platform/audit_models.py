"""Audit 数据模型 — C2 Audit Engine 的核心类型定义。

包含：
- AuditRecordType 枚举（4 类：DECISION / GOVERNANCE / EXECUTION / SYSTEM）
- AuditRecord / AuditRule / AuditFinding frozen dataclass
- CheckFn 类型别名
- 默认配置常量

从 platform/audit_engine.py 提取（v1.0 拆分）。
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from ocos.kernel.abi import SCHEMA_VERSION


# ── 枚举 ────────────────────────────────────────────────────────────────────

class AuditRecordType(str, Enum):
    """审计记录类型，对应宪法核心事件类别。"""
    DECISION = "audit.decision"
    GOVERNANCE = "audit.governance"
    EXECUTION = "audit.execution"
    SYSTEM = "audit.system"


# ── 默认配置 ────────────────────────────────────────────────────────────────

DEFAULT_AUDIT_STORE_SIZE: int = 10_000
DEFAULT_EMIT_AUDIT_EVENTS: bool = False
QUERY_MAX_LIMIT: int = 500
QUERY_DEFAULT_LIMIT: int = 50


# ── 数据模型 ────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class AuditRecord:
    """审计记录：一个可审计事件的完整记录。

    每个 AuditRecord 对应一次可审计事件，关联到 Trace 和 Event 的 ID 链。
    """
    audit_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    record_type: str = ""  # AuditRecordType.value
    source: str = ""
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    summary: str = ""
    related_trace_ids: tuple[str, ...] = field(default_factory=tuple)
    related_event_ids: tuple[str, ...] = field(default_factory=tuple)
    details: dict[str, Any] = field(default_factory=dict)
    schema_version: str = SCHEMA_VERSION


@dataclass(frozen=True)
class AuditRule:
    """审计规则定义。"""
    rule_id: str = ""
    name: str = ""
    description: str = ""
    severity: str = "info"  # error | warning | info
    check_type: str = "compliance"  # completeness | permission | compliance


@dataclass(frozen=True)
class AuditFinding:
    """审计发现：规则检查的输出。"""
    finding_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    rule_id: str = ""
    severity: str = "info"
    message: str = ""
    related_audit_ids: tuple[str, ...] = field(default_factory=tuple)
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


# ── 类型别名 ────────────────────────────────────────────────────────────────

# 审计规则检查函数签名：接收记录列表，返回 AuditFinding 列表
CheckFn = Callable[[list[AuditRecord]], list[AuditFinding]]
