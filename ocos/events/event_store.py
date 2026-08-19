"""
OCOS Event Store — Event 持久化存储。

提供原子的 Event 追加、按 EventType 查询、全局事件流遍历。
底层为 list[Event] 的内存实现。
"""

from __future__ import annotations

import dataclasses
from typing import Any

from ocos.kernel.abi import Event, EventType, SCHEMA_VERSION
from ocos.kernel.event_schema import validate_event_payload
from ocos.logging import get_logger

logger = get_logger(__name__)


@dataclasses.dataclass(frozen=True)
class CommitResult:
    """Event append 操作的结果。"""
    success: bool = False
    committed_count: int = 0
    version: int = 0
    errors: tuple[str, ...] = ()


@dataclasses.dataclass(frozen=True)
class StoreSnapshot:
    """Event Store 的快照（用于重建状态）。"""
    version: int = 0
    event_count_by_type: dict[str, int] = dataclasses.field(default_factory=dict)
    timestamp: str = dataclasses.field(
        default_factory=lambda: __import__("datetime").datetime.now(
            __import__("datetime").timezone.utc
        ).isoformat()
    )


class InMemoryEventStore:
    """OCOS 原生 Event Store — 纯内存。

    替代旧的 opentale.app.reality.event_store.InMemoryEventStore。
    使用 kernel.abi.Event 作为统一类型。
    """

    def __init__(self):
        self._events: list[Event] = []
        self._version: int = 0
        logger.debug("InMemoryEventStore initialized")

    # ── 写入 ───────────────────────────────────────────────────────────────

    def append(self, events: list[Event], validate: bool = True) -> CommitResult:
        """原子追加 Event 列表。

        验证全部通过才写入，任一失败全不放行（原子性）。
        """
        if not events:
            return CommitResult(
                success=False,
                errors=("empty event list",),
            )

        if validate:
            validation_errors: list[str] = []
            for i, event in enumerate(events):
                # schema_version 检查
                if not event.schema_version:
                    validation_errors.append(f"event[{i}]: 缺少 schema_version")
                # payload 验证
                if not validate_event_payload(event.event_type, event.payload):
                    validation_errors.append(
                        f"event[{i}]: payload 不匹配 "
                        f"EventType.{event.event_type.value} 的 schema"
                    )
            if validation_errors:
                logger.warning(
                    "Event validation failed",
                    extra={"errors": validation_errors, "event_count": len(events)},
                )
                return CommitResult(
                    success=False,
                    errors=tuple(validation_errors),
                )

        # 原子写入
        self._events.extend(events)
        self._version = len(self._events)

        logger.info(
            "Events appended",
            extra={
                "count": len(events),
                "total_events": self._version,
            },
        )

        return CommitResult(
            success=True,
            committed_count=len(events),
            version=self._version,
        )

    # ── 查询 ───────────────────────────────────────────────────────────────

    def get_by_type(self, event_type: EventType) -> list[Event]:
        """按 EventType 查询事件（按时间序）。"""
        result = [e for e in self._events if e.event_type == event_type]
        logger.debug(
            "Query by type",
            extra={"event_type": event_type.value, "count": len(result)},
        )
        return result

    def get_by_source(self, source: str) -> list[Event]:
        """按 source 模块名查询。"""
        result = [e for e in self._events if e.source == source]
        logger.debug(
            "Query by source",
            extra={"source": source, "count": len(result)},
        )
        return result

    def get_all(self) -> list[Event]:
        """返回全部事件（不可变视图）。"""
        result = list(self._events)
        logger.debug(
            "Query all events",
            extra={"count": len(result)},
        )
        return result

    def count(self) -> int:
        """当前事件总数。"""
        return self._version

    def snapshot(self) -> StoreSnapshot:
        """构建存储快照（统计信息）。"""
        counts: dict[str, int] = {}
        for e in self._events:
            key = e.event_type.value
            counts[key] = counts.get(key, 0) + 1
        logger.debug(
            "Store snapshot taken",
            extra={"version": self._version, "event_type_count": len(counts)},
        )
        return StoreSnapshot(
            version=self._version,
            event_count_by_type=counts,
        )

    def clear(self) -> int:
        """清空存储（仅用于测试）。返回清除前的事件数。"""
        count = self._version
        self._events.clear()
        self._version = 0
        logger.debug("Event store cleared", extra={"removed_count": count})
        return count
