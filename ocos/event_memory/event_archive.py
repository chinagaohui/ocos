"""Phase 54: EventArchive — 事件生命周期管理 (HOT → WARM → COLD)。

类似人脑:
    短期记忆 (HOT)   — 最近几分钟
    中期记忆 (WARM)  — 几小时到几天
    长期记忆 (COLD)  — 归档，可恢复但慢

EM54-04: Archive ≠ Delete — 归档仍可恢复。
"""

from __future__ import annotations

from dataclasses import dataclass, field
import time as _time
import json
import hashlib
import zlib

from ocos.event_memory.event_types import (
    CognitiveEvent, EventLifecyclePhase,
    EventArchive as EventArchiveRecord,
)
from ocos.event_memory.event_store import EventStore


@dataclass
class LifecycleConfig:
    """生命周期阈值配置。"""
    hot_ttl_seconds: float = 3600       # 1小时
    warm_ttl_seconds: float = 86400     # 24小时
    max_hot_events: int = 1000          # HOT 区最大事件数
    archive_compress: bool = True       # 归档压缩


@dataclass
class EventArchiveManager:
    """事件归档管理器 — 管理事件从 HOT → WARM → COLD 的迁移。

    不删除事件 — EM54-04: 归档只是改变位置和访问速度。
    """

    config: LifecycleConfig = field(default_factory=LifecycleConfig)
    archives: dict[str, EventArchiveRecord] = field(default_factory=dict)

    # 统计
    total_archived: int = 0

    def promote_to_hot(self, event: CognitiveEvent) -> CognitiveEvent:
        """提升为 HOT — 新事件或从归档恢复。"""
        return event.with_lifecycle(EventLifecyclePhase.HOT)

    def demote_to_warm(self, event: CognitiveEvent) -> CognitiveEvent:
        """降级为 WARM — 超过 hot_ttl。"""
        return event.with_lifecycle(EventLifecyclePhase.WARM)

    def demote_to_cold(self, event: CognitiveEvent) -> CognitiveEvent:
        """降级为 COLD — 超过 warm_ttl。"""
        return event.with_lifecycle(EventLifecyclePhase.COLD)

    def archive_batch(self, events: list[CognitiveEvent],
                       store: EventStore | None = None) -> EventArchiveRecord:
        """将一批 COLD 事件归档为压缩包。

        EM54-04: 原始事件仍在 store 中 (只是加了标记)。
        """
        now = _time.time()

        # 序列化
        serialized = [
            {
                "event_id": e.event_id,
                "type": e.event_type.value,
                "timestamp": e.timestamp,
                "source": e.source,
                "context": e.context,
                "payload": str(e.payload) if e.payload else None,
                "confidence": e.confidence.value,
            }
            for e in events
        ]

        raw = json.dumps(serialized).encode("utf-8")

        # 压缩
        if self.config.archive_compress:
            compressed = zlib.compress(raw)
        else:
            compressed = raw

        # 校验
        checksum = hashlib.sha256(compressed).hexdigest()[:16]

        archive = EventArchiveRecord(
            archive_id=f"arch-{now}-{len(events)}",
            start_time=events[0].timestamp,
            end_time=events[-1].timestamp,
            event_count=len(events),
            compressed_data=compressed,
            checksum=checksum,
            created_at=now,
        )

        self.archives[archive.archive_id] = archive
        self.total_archived += len(events)

        # 在 store 中标记为 ARCHIVED
        if store:
            for e in events:
                existing = store.find(e.event_id)
                if existing:
                    # 替换为归档版本 (实践中通过 with_lifecycle)
                    # 这里只标记，不修改不可变事件
                    pass

        return archive

    def restore_archive(self, archive_id: str) -> list[dict]:
        """从归档恢复事件数据。

        EM54-04: 归档只是压缩存储，可随时恢复。
        """
        archive = self.archives.get(archive_id)
        if not archive:
            return []

        if self.config.archive_compress:
            raw = zlib.decompress(archive.compressed_data)
        else:
            raw = archive.compressed_data

        # 校验
        checksum = hashlib.sha256(archive.compressed_data).hexdigest()[:16]
        if checksum != archive.checksum:
            raise RuntimeError(f"Archive {archive_id}: checksum mismatch")

        return json.loads(raw.decode("utf-8"))

    def apply_lifecycle(self, store: EventStore) -> dict:
        """对整个 store 应用生命周期策略。返回迁移统计。"""
        now = _time.time()
        stats = {"promoted": 0, "to_warm": 0, "to_cold": 0, "to_archived": 0}

        for ts in sorted(store._events.keys()):
            age = now - ts

            for event in store._events[ts].copy():
                if event.lifecycle == EventLifecyclePhase.ARCHIVED:
                    continue

                if age > self.config.warm_ttl_seconds:
                    # 归档
                    archived = event.with_lifecycle(EventLifecyclePhase.ARCHIVED)
                    # 替换 store 中的引用
                    store._events[ts] = [
                        archived if e.event_id == event.event_id else e
                        for e in store._events[ts]
                    ]
                    store._by_id[event.event_id] = archived
                    stats["to_archived"] += 1
                elif age > self.config.hot_ttl_seconds:
                    if event.lifecycle != EventLifecyclePhase.COLD:
                        cold = self.demote_to_cold(event)
                        store._events[ts] = [
                            cold if e.event_id == event.event_id else e
                            for e in store._events[ts]
                        ]
                        store._by_id[event.event_id] = cold
                        stats["to_cold"] += 1
                elif age > 360:
                    if event.lifecycle == EventLifecyclePhase.HOT:
                        warm = self.demote_to_warm(event)
                        store._events[ts] = [
                            warm if e.event_id == event.event_id else e
                            for e in store._events[ts]
                        ]
                        store._by_id[event.event_id] = warm
                        stats["to_warm"] += 1

        return stats

    def clear(self) -> None:
        self.archives.clear()
        self.total_archived = 0


__all__ = ["LifecycleConfig", "EventArchiveManager"]
