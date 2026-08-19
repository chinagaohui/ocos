"""AlertChannel — 告警通道抽象。

可扩展：
- LogChannel：通过 logger 输出
- FileChannel：写入文件
- SlackChannel / EmailChannel（未来扩展）
"""

from __future__ import annotations

import json
import logging
import os
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any

from ocos.alerts.models import Alert


logger = logging.getLogger(__name__)


class AlertChannel(ABC):
    """告警通道抽象基类。"""

    @abstractmethod
    def send(self, alert: Alert) -> None:
        """发送告警。"""


class LogChannel(AlertChannel):
    """通过 logging 系统发送告警。"""

    def send(self, alert: Alert) -> None:
        log_entry = {
            "alert_id": alert.alert_id,
            "level": alert.level.value,
            "source": alert.source,
            "message": alert.message,
            "detail": alert.detail,
            "finding_id": alert.finding_id,
            "created_at": alert.created_at,
        }

        log_level = {
            "info": logging.INFO,
            "warning": logging.WARNING,
            "error": logging.ERROR,
            "critical": logging.CRITICAL,
        }.get(alert.level.value, logging.INFO)

        logger.log(log_level, json.dumps(log_entry))


class FileChannel(AlertChannel):
    """将告警写入文件（每行一个 JSON）。"""

    def __init__(self, filepath: str = "alerts.log"):
        self.filepath = filepath

    def send(self, alert: Alert) -> None:
        entry = {
            "alert_id": alert.alert_id,
            "level": alert.level.value,
            "source": alert.source,
            "message": alert.message,
            "detail": alert.detail,
            "finding_id": alert.finding_id,
            "created_at": alert.created_at,
        }

        dirname = os.path.dirname(self.filepath)
        if dirname:
            os.makedirs(dirname, exist_ok=True)

        with open(self.filepath, "a") as f:
            f.write(json.dumps(entry) + "\n")
