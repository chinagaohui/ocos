"""Phase Q: ExternalInteraction — 外部交互通道管理。

整合多种输出通道：
- LogChannel: 日志通道
- CallbackChannel: 注入回调通道
- WebhookChannel: Webhook 通道（HTTP POST）
- BroadcastChannel: 广播到所有子通道

职责:
  - 注册/注销通道
  - 按优先级路由输出
  - 通道健康检查
  - 失败降级
"""

from __future__ import annotations

import json
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum, auto
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class ChannelType(Enum):
    """通道类型。"""
    LOG = auto()
    CALLBACK = auto()
    WEBHOOK = auto()
    BROADCAST = auto()


class ChannelStatus(Enum):
    """通道状态。"""
    ACTIVE = auto()
    INACTIVE = auto()
    ERROR = auto()
    DRAINED = auto()


@dataclass(frozen=True)
class ChannelConfig:
    """通道配置。"""
    channel_type: ChannelType
    name: str
    enabled: bool = True
    priority: int = 0  # 0=最低, 9=最高
    config: dict[str, Any] = field(default_factory=dict)


@dataclass
class ChannelHealth:
    """通道健康状态。"""
    channel_id: str
    status: ChannelStatus
    last_error: Optional[str] = None
    last_activity: Optional[float] = None
    message_count: int = 0
    error_count: int = 0
    success_count: int = 0


class BaseChannel(ABC):
    """通道抽象基类。"""

    def __init__(self, config: ChannelConfig) -> None:
        self._config = config
        self._health = ChannelHealth(
            channel_id=config.name,
            status=ChannelStatus.ACTIVE if config.enabled else ChannelStatus.INACTIVE,
        )

    @property
    def config(self) -> ChannelConfig:
        return self._config

    @property
    def health(self) -> ChannelHealth:
        return self._health

    @abstractmethod
    def send(self, message: str, priority: int = 0) -> bool:
        raise NotImplementedError

    def record_success(self) -> None:
        self._health.success_count += 1
        self._health.last_activity = time.time()
        self._health.message_count += 1
        self._health.status = ChannelStatus.ACTIVE

    def record_error(self, error: str) -> None:
        self._health.error_count += 1
        self._health.last_error = error
        self._health.status = ChannelStatus.ERROR

    def deactivate(self) -> None:
        self._health.status = ChannelStatus.INACTIVE


class LogChannel(BaseChannel):
    """日志通道。"""

    def __init__(self, name: str = "log", priority: int = 0) -> None:
        super().__init__(ChannelConfig(
            channel_type=ChannelType.LOG,
            name=name,
            priority=priority,
        ))

    def send(self, message: str, priority: int = 0) -> bool:
        try:
            log_level = logging.WARNING if priority >= 3 else logging.INFO
            logger.log(log_level, message)
            self.record_success()
            return True
        except Exception as e:
            self.record_error(str(e))
            return False


class CallbackChannel(BaseChannel):
    """回调通道。"""

    def __init__(
        self,
        name: str,
        callback: Callable[[str, int], None],
        priority: int = 5,
    ) -> None:
        super().__init__(ChannelConfig(
            channel_type=ChannelType.CALLBACK,
            name=name,
            priority=priority,
        ))
        self._callback = callback

    def send(self, message: str, priority: int = 0) -> bool:
        try:
            self._callback(message, priority)
            self.record_success()
            return True
        except Exception as e:
            self.record_error(str(e))
            return False


class WebhookChannel(BaseChannel):
    """Webhook 通道（HTTP POST）。"""

    def __init__(
        self,
        name: str,
        url: str,
        timeout: float = 5.0,
        priority: int = 7,
        secret: str = "",
    ) -> None:
        super().__init__(ChannelConfig(
            channel_type=ChannelType.WEBHOOK,
            name=name,
            priority=priority,
            config={"url": url, "timeout": timeout},
        ))
        self._url = url
        self._timeout = timeout
        # D2（2026-09-07）: per-route HMAC secret — 配置后对每次 POST 计算
        # X-Hub-Signature-256（sha256=<hexdigest>），与 hermes-gateway
        # webhook 路由的校验格式一致（GitHub 风格）。
        self._secret = secret or ""

    def send(self, message: str, priority: int = 0) -> bool:
        try:
            import urllib.request
            payload = json.dumps({
                "message": message,
                "priority": priority,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "channel": self._config.name,
            }).encode("utf-8")
            headers = {"Content-Type": "application/json"}
            if self._secret:
                import hashlib
                import hmac
                sig = hmac.new(self._secret.encode("utf-8"), payload,
                               hashlib.sha256).hexdigest()
                headers["X-Hub-Signature-256"] = f"sha256={sig}"
            req = urllib.request.Request(
                self._url,
                data=payload,
                headers=headers,
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                if 200 <= resp.status < 300:
                    self.record_success()
                    return True
            self.record_error(f"HTTP {resp.status}")
            return False
        except Exception as e:
            self.record_error(str(e))
            return False


class BroadcastChannel(BaseChannel):
    """广播通道 — 发送到所有已注册的子通道。"""

    def __init__(self, name: str = "broadcast") -> None:
        super().__init__(ChannelConfig(
            channel_type=ChannelType.BROADCAST,
            name=name,
            priority=9,
        ))
        self._channels: list[BaseChannel] = []

    def add_channel(self, channel: BaseChannel) -> None:
        self._channels.append(channel)

    def remove_channel(self, name: str) -> bool:
        before = len(self._channels)
        self._channels = [c for c in self._channels if c.config.name != name]
        return len(self._channels) < before

    def send(self, message: str, priority: int = 0) -> bool:
        results = []
        for channel in self._channels:
            if channel.health.status == ChannelStatus.INACTIVE:
                continue
            success = channel.send(message, priority)
            results.append(success)
        if not results:
            self.record_error("no active channels")
            return False
        all_success = all(results)
        if all_success:
            self.record_success()
        else:
            self.record_error(f"partial: {sum(results)}/{len(results)} succeeded")
        return all_success


class ExternalInteraction:
    """Phase Q: 外部交互管理器。

    整合多种通道类型，按优先级路由输出，支持健康检查和失败降级。
    """

    def __init__(self) -> None:
        self._channels: dict[str, BaseChannel] = {}
        self._message_history: list[dict[str, Any]] = []
        self._max_history = 1000
        self._total_sent = 0
        self._total_failed = 0
        self._started_at = time.time()

    @property
    def channel_count(self) -> int:
        return len(self._channels)

    @property
    def active_channels(self) -> list[str]:
        return [
            name for name, ch in self._channels.items()
            if ch.health.status == ChannelStatus.ACTIVE
        ]

    def add_channel(self, channel: BaseChannel) -> str:
        name = channel.config.name
        self._channels[name] = channel
        logger.info("Channel registered: %s (type=%s)", name, channel.config.channel_type.name)
        return name

    def remove_channel(self, name: str) -> bool:
        if name in self._channels:
            del self._channels[name]
            return True
        return False

    def send(
        self,
        message: str,
        priority: int = 0,
        channel_names: Optional[list[str]] = None,
    ) -> dict[str, bool]:
        results = {}
        targets = channel_names or self.active_channels
        for name in targets:
            if name not in self._channels:
                results[name] = False
                continue
            success = self._channels[name].send(message, priority)
            results[name] = success
            if success:
                self._total_sent += 1
            else:
                self._total_failed += 1
        self._record_send(message, priority, results)
        return results

    def send_broadcast(self, message: str, priority: int = 0) -> bool:
        bc = self._channels.get("broadcast")
        if bc is None:
            bc = BroadcastChannel()
            self.add_channel(bc)
        return bc.send(message, priority)

    def get_channel_status(self, name: str) -> Optional[ChannelHealth]:
        channel = self._channels.get(name)
        return channel.health if channel else None

    def get_all_status(self) -> dict[str, dict[str, Any]]:
        return {
            name: {
                "status": ch.health.status.name,
                "priority": ch.config.priority,
                "success_count": ch.health.success_count,
                "error_count": ch.health.error_count,
                "last_error": ch.health.last_error,
            }
            for name, ch in self._channels.items()
        }

    def get_stats(self) -> dict[str, Any]:
        total = self._total_sent + self._total_failed
        return {
            "total_channels": len(self._channels),
            "active_channels": len(self.active_channels),
            "total_sent": self._total_sent,
            "total_failed": self._total_failed,
            "success_rate": self._total_sent / total if total > 0 else 0.0,
            "uptime_seconds": time.time() - self._started_at,
            "recent_messages": self._message_history[-5:],
        }

    # ── Factory Methods ──────────────────────────────────────────────────

    @classmethod
    def create_log_channel(cls, name: str = "log", priority: int = 0) -> LogChannel:
        return LogChannel(name=name, priority=priority)

    @classmethod
    def create_callback_channel(
        cls,
        name: str,
        callback: Callable[[str, int], None],
        priority: int = 5,
    ) -> CallbackChannel:
        return CallbackChannel(name=name, callback=callback, priority=priority)

    @classmethod
    def create_webhook_channel(
        cls,
        name: str,
        url: str,
        timeout: float = 5.0,
        priority: int = 7,
        secret: str = "",
    ) -> WebhookChannel:
        return WebhookChannel(name=name, url=url, timeout=timeout,
                              priority=priority, secret=secret)

    @classmethod
    def create_broadcast_channel(cls, name: str = "broadcast") -> BroadcastChannel:
        return BroadcastChannel(name=name)

    def _record_send(self, message: str, priority: int, results: dict[str, bool]) -> None:
        self._message_history.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "message": message[:100],
            "priority": priority,
            "results": results,
        })
        if len(self._message_history) > self._max_history:
            self._message_history = self._message_history[-self._max_history:]


__all__ = [
    "ExternalInteraction",
    "BaseChannel",
    "LogChannel",
    "CallbackChannel",
    "WebhookChannel",
    "BroadcastChannel",
    "ChannelType",
    "ChannelStatus",
    "ChannelConfig",
    "ChannelHealth",
]
