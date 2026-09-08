"""Phase AK: ExternalCommunicationManager — 外部通信通道管理器。

L2 沉睡支线归档（2026-09-07, 升级方案 v1.0 §L2）:
    dormant=true — 全仓零生产引用。出站多通道职责由
    ocos/interaction/channel.py（ExternalInteraction）+ ocos/daemon/
    channel_link.py（OutboundChannelLink, L2-3 已上电）承担；
    本包 MQTT/EMAIL/PUSH 等重型通道待真实需求出现再评估上电。

整合多种通信通道，实现统一的外部通信层：
- WebSocket 通道：实时双向通信
- HTTP/REST 通道：标准 RESTful API
- MQTT 通道：轻量级消息队列
- Email 通道：邮件通知
- CLI 通道：命令行交互
- Push Notification 通道：推送通知

架构原则:
- AK-OUT-01: 通信 ≠ 认知 — 外部通信层只负责数据传输，不干涉决策
- AK-OUT-02: 异步优先 — 所有 IO 操作必须异步，阻塞视为故障
- AK-OUT-03: 降级机制 — 单个通道失败不影响其他通道
- AK-OUT-04: 身份验证 — 所有外部通信必须经过认证和授权
- AK-OUT-05: 审计追踪 — 所有通信记录必须可审计
- AK-OUT-06: 速率限制 — 防止 API 调用滥用和 DoS 攻击
- AK-OUT-07: 超时控制 — 所有通信必须有明确的超时和重试策略
- AK-OUT-08: 数据加密 — 敏感数据必须加密传输
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum, auto
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class ChannelType(Enum):
    """通信通道类型。"""
    WEBSOCKET = auto()
    HTTP = auto()
    MQTT = auto()
    EMAIL = auto()
    CLI = auto()
    PUSH = auto()


class ChannelStatus(Enum):
    """通道状态。"""
    ACTIVE = auto()
    INACTIVE = auto()
    CONNECTING = auto()
    ERROR = auto()
    DRAINED = auto()


class MessagePriority(Enum):
    """消息优先级。"""
    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3


@dataclass(frozen=True)
class ChannelConfig:
    """通道配置。"""
    channel_type: ChannelType
    name: str
    enabled: bool = True
    priority: int = 0
    config: dict[str, Any] = field(default_factory=dict)
    timeout_seconds: float = 30.0
    retry_count: int = 3
    encrypt_sensitive: bool = False


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
    avg_latency_ms: float = 0.0


@dataclass
class CommunicationMessage:
    """通信消息。"""
    message_id: str
    channel_type: ChannelType
    priority: MessagePriority
    content: str
    recipient: Optional[str] = None
    sender: Optional[str] = None
    timestamp: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)
    correlation_id: Optional[str] = None


@dataclass
class CommunicationRecord:
    """通信记录。"""
    record_id: str
    message_id: str
    channel_type: ChannelType
    status: str  # sent, failed, pending
    latency_ms: float
    error: Optional[str] = None
    timestamp: float = field(default_factory=time.time)
    response_data: Optional[dict] = None


class BaseChannel(ABC):
    """通信通道抽象基类。"""

    def __init__(self, config: ChannelConfig) -> None:
        self._config = config
        self._health = ChannelHealth(
            channel_id=config.name,
            status=ChannelStatus.ACTIVE if config.enabled else ChannelStatus.INACTIVE,
        )
        self._initialized = False

    @property
    def config(self) -> ChannelConfig:
        return self._config

    @property
    def health(self) -> ChannelHealth:
        return self._health

    @abstractmethod
    async def initialize(self) -> bool:
        pass

    @abstractmethod
    async def send(self, message: CommunicationMessage) -> CommunicationRecord:
        pass

    @abstractmethod
    async def receive(self, timeout: float = 5.0) -> Optional[CommunicationMessage]:
        pass

    @abstractmethod
    async def close(self) -> None:
        pass

    def get_status(self) -> dict[str, Any]:
        return {
            "channel_id": self._health.channel_id,
            "status": self._health.status.name,
            "message_count": self._health.message_count,
            "error_count": self._health.error_count,
            "success_count": self._health.success_count,
        }


class CommunicationChannelManager:
    """通信通道管理器。"""

    def __init__(self) -> None:
        self._channels: dict[str, BaseChannel] = {}
        self._records: list[CommunicationRecord] = []
        self._max_records: int = 10000

    def register_channel(self, channel: BaseChannel) -> bool:
        if channel.config.name in self._channels:
            logger.warning("Channel %s already exists", channel.config.name)
            return False
        self._channels[channel.config.name] = channel
        return True

    def unregister_channel(self, channel_id: str) -> bool:
        if channel_id not in self._channels:
            return False
        del self._channels[channel_id]
        return True

    def get_channel(self, channel_id: str) -> Optional[BaseChannel]:
        return self._channels.get(channel_id)

    def list_channels(self) -> list[dict[str, Any]]:
        return [ch.get_status() for ch in self._channels.values()]

    async def send_message(
        self,
        message: CommunicationMessage,
        channel_id: Optional[str] = None,
    ) -> CommunicationRecord:
        target_channel = self._channels.get(channel_id) if channel_id else self._get_best_channel(message.channel_type)
        if not target_channel:
            record = self._create_failed_record(message, "no_available_channel")
            self._records.append(record)
            return record

        start_time = time.time()
        try:
            record = await target_channel.send(message)
            record.latency_ms = (time.time() - start_time) * 1000
            target_channel._health.success_count += 1
            target_channel._health.last_activity = time.time()
        except Exception as e:
            record = self._create_failed_record(message, str(e))
            target_channel._health.error_count += 1
            target_channel._health.last_error = str(e)
            logger.warning("Send failed to %s: %s", target_channel.config.name, e)

        self._records.append(record)
        if len(self._records) > self._max_records:
            self._records = self._records[-self._max_records:]
        return record

    def _get_best_channel(self, channel_type: ChannelType) -> Optional[BaseChannel]:
        candidates = [ch for ch in self._channels.values()
                      if ch.config.channel_type == channel_type and ch.health.status == ChannelStatus.ACTIVE]
        return max(candidates, key=lambda ch: ch.config.priority) if candidates else None

    def _create_failed_record(self, message: CommunicationMessage, error: str) -> CommunicationRecord:
        return CommunicationRecord(
            record_id=str(uuid.uuid4()),
            message_id=message.message_id,
            channel_type=message.channel_type,
            status="failed",
            latency_ms=0.0,
            error=error,
        )

    def get_records(self, limit: int = 100) -> list[CommunicationRecord]:
        return self._records[-limit:]

    def get_stats(self) -> dict[str, Any]:
        total = len(self._records)
        failed = sum(1 for r in self._records if r.status == "failed")
        return {
            "total_messages": total,
            "failed_messages": failed,
            "active_channels": len([ch for ch in self._channels.values()
                                    if ch.health.status == ChannelStatus.ACTIVE]),
        }

    def clear_history(self) -> None:
        self._records.clear()


class ExternalCommunicationManager:
    """外部通信通道管理器（Phase AK）。

    统一外部通信层，整合多种通信通道，实现稳定可靠的外部通信能力。
    """

    def __init__(
        self,
        default_timeout: float = 30.0,
        default_retry_count: int = 3,
        max_record_history: int = 10000,
    ) -> None:
        self._manager = CommunicationChannelManager()
        self._default_timeout = default_timeout
        self._default_retry_count = default_retry_count
        self._manager._max_records = max_record_history
        self._initialized = False

    def initialize(self) -> bool:
        self._initialized = True
        logger.info("ExternalCommunicationManager initialized")
        return True

    def register_websocket_channel(
        self,
        name: str,
        url: str,
        priority: int = 0,
    ) -> bool:
        config = ChannelConfig(
            channel_type=ChannelType.WEBSOCKET,
            name=name,
            priority=priority,
            config={"url": url},
        )
        channel = _WebSocketChannelPlaceholder(config)
        return self._manager.register_channel(channel)

    def register_http_channel(
        self,
        name: str,
        base_url: str,
        api_key: Optional[str] = None,
        priority: int = 0,
    ) -> bool:
        config = ChannelConfig(
            channel_type=ChannelType.HTTP,
            name=name,
            priority=priority,
            config={"base_url": base_url, "api_key": api_key},
        )
        channel = _HTTPChannelPlaceholder(config)
        return self._manager.register_channel(channel)

    def unregister_channel(self, channel_id: str) -> bool:
        return self._manager.unregister_channel(channel_id)

    def list_channels(self) -> list[dict[str, Any]]:
        return self._manager.list_channels()

    def send_message(
        self,
        content: str,
        channel_type: ChannelType,
        recipient: Optional[str] = None,
        priority: MessagePriority = MessagePriority.NORMAL,
        metadata: Optional[dict[str, Any]] = None,
    ) -> CommunicationRecord:
        message = CommunicationMessage(
            message_id=str(uuid.uuid4()),
            channel_type=channel_type,
            priority=priority,
            content=content,
            recipient=recipient,
            metadata=metadata or {},
        )
        # 同步调用异步方法
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # 在运行的循环中，创建任务但不等待
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    future = pool.submit(lambda: loop.run_until_complete(self._async_send(message)))
                    return future.result(timeout=self._default_timeout)
            else:
                return loop.run_until_complete(self._async_send(message))
        except RuntimeError:
            # 没有事件循环，创建新的
            return asyncio.run(self._async_send(message))

    async def _async_send(self, message: CommunicationMessage) -> CommunicationRecord:
        return await self._manager.send_message(message)

    def send_websocket_message(
        self,
        content: str,
        channel_id: str,
        priority: MessagePriority = MessagePriority.NORMAL,
    ) -> CommunicationRecord:
        return self.send_message(content, ChannelType.WEBSOCKET, recipient=channel_id, priority=priority)

    def send_http_message(
        self,
        content: str,
        channel_id: str,
        priority: MessagePriority = MessagePriority.NORMAL,
    ) -> CommunicationRecord:
        return self.send_message(content, ChannelType.HTTP, recipient=channel_id, priority=priority)

    def get_channel_status(self, channel_id: str) -> Optional[dict[str, Any]]:
        channel = self._manager.get_channel(channel_id)
        return channel.get_status() if channel else None

    def get_statistics(self) -> dict[str, Any]:
        return self._manager.get_stats()

    def get_history(self, limit: int = 100) -> list[dict[str, Any]]:
        return [
            {
                "record_id": r.record_id,
                "message_id": r.message_id,
                "channel_type": r.channel_type.name,
                "status": r.status,
                "latency_ms": r.latency_ms,
                "error": r.error,
                "timestamp": r.timestamp,
            }
            for r in self._manager.get_records(limit)
        ]

    def get_health_summary(self) -> dict[str, Any]:
        channels = self.list_channels()
        return {
            "total_channels": len(channels),
            "active_channels": len([ch for ch in channels if ch["status"] == "ACTIVE"]),
            "error_channels": len([ch for ch in channels if ch["status"] == "ERROR"]),
            "total_messages": self._manager.get_stats().get("total_messages", 0),
            "failed_messages": self._manager.get_stats().get("failed_messages", 0),
        }

    def clear_history(self) -> None:
        self._manager.clear_history()

    def tick(self) -> dict[str, Any]:
        return {
            "health_summary": self.get_health_summary(),
            "stats": self.get_statistics(),
            "initialized": self._initialized,
        }


class _WebSocketChannelPlaceholder(BaseChannel):
    """WebSocket通道占位符。"""

    async def initialize(self) -> bool:
        self._health.status = ChannelStatus.ACTIVE
        return True

    async def send(self, message: CommunicationMessage) -> CommunicationRecord:
        return CommunicationRecord(
            record_id=str(uuid.uuid4()),
            message_id=message.message_id,
            channel_type=message.channel_type,
            status="sent",
            latency_ms=1.5,
        )

    async def receive(self, timeout: float = 5.0) -> Optional[CommunicationMessage]:
        return None

    async def close(self) -> None:
        pass


class _HTTPChannelPlaceholder(BaseChannel):
    """HTTP通道占位符。"""

    async def initialize(self) -> bool:
        self._health.status = ChannelStatus.ACTIVE
        return True

    async def send(self, message: CommunicationMessage) -> CommunicationRecord:
        return CommunicationRecord(
            record_id=str(uuid.uuid4()),
            message_id=message.message_id,
            channel_type=message.channel_type,
            status="sent",
            latency_ms=2.3,
        )

    async def receive(self, timeout: float = 5.0) -> Optional[CommunicationMessage]:
        return None

    async def close(self) -> None:
        pass
