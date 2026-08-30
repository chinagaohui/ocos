"""
OCOS Dead Letter Queue — 投递失败的事件存储。

分工裁决（AUD-F6, 2026-08-30）: 本模块 = 进程内总线侧内存 DLQ
（EventBus 可选注入）；ocos/storage/dead_letter_queue.py = SQLite 持久化版
（恢复链专用）。按层分工，不合并。

Event Bus 投递失败时，事件进入 DLQ 而非静默丢弃。
支持 DLQ 查询、重放、清理。
"""

from __future__ import annotations

import dataclasses
import threading
from datetime import datetime, timezone
from typing import Any

from ocos.kernel.abi import Event
from ocos.logging import get_logger

logger = get_logger(__name__)


@dataclasses.dataclass(frozen=True)
class DeadLetterRecord:
    """死信记录：投递失败的事件及其元信息。"""
    record_id: str = ""
    event: Event = dataclasses.field(default_factory=Event)
    subscriber_id: str = ""
    error: str = ""
    failed_at: str = dataclasses.field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    retry_count: int = 0


class DeadLetterQueue:
    """死信队列 — 管理投递失败的 Event。

    特性:
    - 线程安全
    - 按 EventType / 时间 查询
    - 重放（replay）支持
    - 自动清理旧记录
    """

    def __init__(self, max_records: int = 1000):
        self._records: list[DeadLetterRecord] = []
        self._lock = threading.RLock()
        self._max_records = max_records
        logger.debug("DeadLetterQueue initialized", extra={"max_records": max_records})

    def put(
        self,
        event: Event,
        subscriber_id: str,
        error: str,
    ) -> DeadLetterRecord:
        """将失败的 Event 放入死信队列。"""
        import uuid
        record = DeadLetterRecord(
            record_id=uuid.uuid4().hex,
            event=event,
            subscriber_id=subscriber_id,
            error=error,
            retry_count=0,
        )
        with self._lock:
            self._records.append(record)
            # 超过上限时移除最早的记录
            if len(self._records) > self._max_records:
                self._records = self._records[-self._max_records:]
        logger.info(
            "Event sent to dead letter queue",
            extra={
                "record_id": record.record_id,
                "event_id": record.event.event_id,
                "subscriber_id": subscriber_id,
                "error": error,
            },
        )
        return record

    def get_all(self) -> list[DeadLetterRecord]:
        """返回所有死信记录。"""
        with self._lock:
            return list(self._records)

    def get_by_type(self, event_type: EventType) -> list[DeadLetterRecord]:
        """按 Event 类型过滤死信记录。"""
        with self._lock:
            return [
                r for r in self._records
                if r.event.event_type == event_type
            ]

    def count(self) -> int:
        """当前死信总数。"""
        with self._lock:
            return len(self._records)

    def replay(
        self,
        replay_callback: Any,
        max_records: int | None = None,
    ) -> int:
        """重放死信队列中的事件到回调函数。

        Args:
            replay_callback: 接收 Event 的可调用对象
            max_records: 最大重放数（None = 全部）

        Returns:
            成功重放的数量
        """
        import uuid
        with self._lock:
            target = list(self._records)
            if max_records is not None:
                target = target[:max_records]
            self._records = [
                r for r in self._records if r not in target
            ]

        success = 0
        for record in target:
            try:
                replay_callback(record.event)
                success += 1
            except Exception:
                # 重放失败，重新入队列（增量 retry_count）
                new_record = DeadLetterRecord(
                    record_id=uuid.uuid4().hex,
                    event=record.event,
                    subscriber_id=record.subscriber_id,
                    error=record.error,
                    retry_count=record.retry_count + 1,
                )
                with self._lock:
                    self._records.append(new_record)
        logger.info(
            "Dead letter replay completed",
            extra={"replayed": success, "total": len(target)},
        )
        return success

    def clear(self) -> int:
        """清空死信队列。返回被移除的记录数。"""
        with self._lock:
            count = len(self._records)
            self._records.clear()
        logger.debug("Dead letter queue cleared", extra={"removed_count": count})
        return count

    def prune_older_than(self, max_age_hours: float = 24) -> int:
        """清理超过指定时长的死信记录。"""
        import uuid
        from datetime import timedelta
        cutoff = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)
        with self._lock:
            before = len(self._records)
            self._records = [
                r for r in self._records
                if datetime.fromisoformat(r.failed_at) > cutoff
            ]
            pruned = before - len(self._records)
        logger.info(
            "Dead letter queue pruned",
            extra={"pruned_count": pruned, "max_age_hours": max_age_hours},
        )
        return pruned
