"""AlertManager — 告警管理器。

聚合 AlertChannel，提供统一发送接口。
"""

from __future__ import annotations

import threading
from typing import Any, Optional

from ocos.alerts.models import Alert, AlertLevel
from ocos.alerts.channels import AlertChannel


class AlertManager:
    """告警管理器。

    管理告警通道注册、告警发送和历史记录。
    """

    def __init__(self):
        self._channels: list[AlertChannel] = []
        self._history: list[Alert] = []
        self._lock = threading.Lock()

    def register_channel(self, channel: AlertChannel) -> None:
        """注册告警通道。"""
        with self._lock:
            self._channels.append(channel)

    def unregister_channel(self, channel: AlertChannel) -> None:
        """注销告警通道。"""
        with self._lock:
            self._channels.remove(channel)

    def send(
        self,
        level: AlertLevel,
        source: str,
        message: str,
        detail: Optional[dict[str, Any]] = None,
        finding_id: Optional[str] = None,
    ) -> Alert:
        """创建并发送告警。"""
        alert = Alert(
            level=level,
            source=source,
            message=message,
            detail=detail,
            finding_id=finding_id,
        )

        with self._lock:
            self._history.append(alert)
            for channel in self._channels:
                try:
                    channel.send(alert)
                except Exception:
                    pass  # 通道发送失败不影响其他通道

        return alert

    def send_alert(self, alert: Alert) -> None:
        """发送已创建的 Alert 对象。"""
        with self._lock:
            self._history.append(alert)
            for channel in self._channels:
                try:
                    channel.send(alert)
                except Exception:
                    pass

    @property
    def history(self) -> list[Alert]:
        """告警历史。"""
        with self._lock:
            return list(self._history)

    def acknowledge(self, alert_id: str) -> bool:
        """确认告警。"""
        with self._lock:
            for alert in self._history:
                if alert.alert_id == alert_id:
                    alert.acknowledged = True
                    return True
        return False

    def clear_history(self) -> None:
        """清空告警历史。"""
        with self._lock:
            self._history.clear()
