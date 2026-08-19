"""Alert 数据模型。"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional


class AlertLevel(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class Alert:
    """告警条目。

    由 AlertManager 创建并通过 AlertChannel 发送。
    """

    alert_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    level: AlertLevel = AlertLevel.INFO
    source: str = ""                            # "audit_rule_engine" / "dlq" / "scheduler"
    message: str = ""
    detail: Optional[dict[str, Any]] = None     # 额外上下文
    finding_id: Optional[str] = None            # 关联的审计发现
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    acknowledged: bool = False
