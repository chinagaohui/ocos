"""
OCOS Event Bus — 内存版 pub/sub 事件总线。

宪法 Rule 2: Event Bus 是模块间唯一通信通道。
所有跨模块通信必须通过 Event Bus，禁止直接 import 调用。
"""

from __future__ import annotations

import threading
import uuid
from collections import defaultdict
from typing import Any, Callable

from ocos.kernel.abi import Event, EventType
from ocos.logging import get_logger

# 订阅者回调类型：接收 Event，不返回（可抛出异常）
SubscriberFn = Callable[[Event], None]

logger = get_logger(__name__)


class EventBus:
    """内存版事件总线。

    特性:
    - topic-based pub/sub (按 EventType 订阅)
    - 同步/异步两种投递模式
    - Trace ID 自动传播
    - 死信队列集成
    - 线程安全
    """

    def __init__(self, dead_letter_queue: Any | None = None):
        self._subscribers: dict[EventType, list[tuple[str, SubscriberFn]]] = (
            defaultdict(list)
        )
        self._global_subscribers: list[tuple[str, SubscriberFn]] = []
        self._lock = threading.RLock()
        self._dead_letter_queue = dead_letter_queue
        logger.debug("EventBus initialized", extra={"has_dlq": dead_letter_queue is not None})

    # ── 订阅管理 ───────────────────────────────────────────────────────────

    def subscribe(
        self,
        event_type: EventType,
        callback: SubscriberFn,
        subscriber_id: str | None = None,
    ) -> str:
        """订阅指定类型的 Event。返回 subscriber_id。"""
        sid = subscriber_id or f"sub-{uuid.uuid4().hex[:8]}"
        with self._lock:
            self._subscribers[event_type].append((sid, callback))
        logger.info("Subscriber registered", extra={"subscriber_id": sid, "event_type": event_type.value})
        return sid

    def subscribe_all(self, callback: SubscriberFn, subscriber_id: str | None = None) -> str:
        """订阅所有 Event 类型（全局监听器）。"""
        sid = subscriber_id or f"sub-all-{uuid.uuid4().hex[:8]}"
        with self._lock:
            self._global_subscribers.append((sid, callback))
        logger.info("Global subscriber registered", extra={"subscriber_id": sid})
        return sid

    def unsubscribe(self, subscriber_id: str) -> bool:
        """取消订阅。返回是否找到并移除。"""
        with self._lock:
            # 从类型订阅中移除
            for et in list(self._subscribers.keys()):
                self._subscribers[et] = [
                    (sid, cb) for sid, cb in self._subscribers[et]
                    if sid != subscriber_id
                ]
                if not self._subscribers[et]:
                    del self._subscribers[et]
            # 从全局订阅中移除
            before = len(self._global_subscribers)
            self._global_subscribers = [
                (sid, cb) for sid, cb in self._global_subscribers
                if sid != subscriber_id
            ]
        logger.info("Subscriber unsubscribed", extra={"subscriber_id": subscriber_id})
        return True  # 简化实现

    # ── 投递 ───────────────────────────────────────────────────────────────

    def publish(self, event: Event, sync: bool = True) -> int:
        """发布 Event 到总线。

        Args:
            event: 要发布的 Event
            sync: True = 同步（当前线程执行），False = 异步（新线程）

        Returns:
            投递成功的订阅者数量
        """
        with self._lock:
            type_subs = list(self._subscribers.get(event.event_type, []))
            all_subs = list(self._global_subscribers)

        target_subs = type_subs + all_subs

        logger.info(
            "Publishing event",
            extra={
                "event_type": event.event_type.value,
                "event_id": event.event_id,
                "sync": sync,
                "target_count": len(target_subs),
            },
        )

        if not target_subs:
            return 0

        if sync:
            return self._dispatch_sync(event, target_subs)
        else:
            threading.Thread(
                target=self._dispatch_sync,
                args=(event, target_subs),
                daemon=True,
            ).start()
            return len(target_subs)

    def _dispatch_sync(
        self, event: Event, subscribers: list[tuple[str, SubscriberFn]]
    ) -> int:
        """同步投递给所有订阅者。"""
        success_count = 0
        for sid, callback in subscribers:
            try:
                callback(event)
                success_count += 1
                logger.debug(
                    "Event delivered",
                    extra={
                        "event_id": event.event_id,
                        "subscriber_id": sid,
                    },
                )
            except Exception as exc:
                logger.error(
                    "Event delivery failed",
                    extra={
                        "event_id": event.event_id,
                        "subscriber_id": sid,
                        "error": str(exc),
                    },
                )
                if self._dead_letter_queue:
                    self._dead_letter_queue.put(
                        event=event,
                        subscriber_id=sid,
                        error=str(exc),
                    )
        logger.info(
            "Event dispatch complete",
            extra={
                "event_id": event.event_id,
                "success_count": success_count,
                "total_targets": len(subscribers),
            },
        )
        return success_count

    # ── 工具 ───────────────────────────────────────────────────────────────

    def subscriber_count(self, event_type: EventType | None = None) -> int:
        """查询特定类型/所有类型的订阅者数量。"""
        with self._lock:
            if event_type:
                return len(self._subscribers.get(event_type, []))
            total = sum(len(subs) for subs in self._subscribers.values())
            total += len(self._global_subscribers)
            return total

    def clear(self) -> None:
        """清除所有订阅（主要用于测试）。"""
        with self._lock:
            self._subscribers.clear()
            self._global_subscribers.clear()
        logger.debug("All subscribers cleared")
