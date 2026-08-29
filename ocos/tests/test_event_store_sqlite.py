"""GAP-P2-3: event_memory SQLite 化 + archive 补实现测试。

覆盖:
  1. EventStore + connection → append 落库, load_from_db 重建
  2. append-only 语义保持（重复 ID 仍忽略）
  3. archive 后事件 header.lifecycle == ARCHIVED（pass → 真实标记）
"""

from __future__ import annotations

import json
import sqlite3

from ocos.event_memory.event_store import EventStore
from ocos.event_memory.event_archive import EventArchiveManager, LifecycleConfig
from ocos.event_memory.event_types import (
    CognitiveEvent, CognitiveEventType, EventLifecyclePhase,
)
from ocos.storage.schema import CREATE_EVENT_STORE


def _event(eid: str, ts: float, payload=None) -> CognitiveEvent:
    return CognitiveEvent(
        event_id=eid,
        event_type=CognitiveEventType.PERCEPTION,
        timestamp=ts,
        source="test",
        payload=payload or {"k": eid},
    )


def _conn(tmp_path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(tmp_path / "events.db"))
    for stmt in CREATE_EVENT_STORE:
        conn.execute(stmt)
    conn.commit()
    return conn


class TestSqlitePersistence:
    def test_append_persists_and_load_rebuilds(self, tmp_path):
        conn = _conn(tmp_path)
        store = EventStore(connection=conn)
        assert store.append(_event("e1", 100.0, {"v": 1}))
        assert store.append(_event("e2", 200.0, {"v": 2}))

        # 落库行数
        rows = conn.execute("SELECT COUNT(*) FROM event_store").fetchone()[0]
        assert rows == 2

        # 新进程重建（新连接 + load_from_db）
        conn2 = sqlite3.connect(str(tmp_path / "events.db"))
        restored = EventStore.load_from_db(conn2)
        assert restored.stats()["total_events"] == 2
        assert restored.find("e1").payload == {"v": 1}
        assert restored.find("e2").payload == {"v": 2}

    def test_append_only_ignores_duplicate_id(self, tmp_path):
        conn = _conn(tmp_path)
        store = EventStore(connection=conn)
        assert store.append(_event("e1", 100.0))
        assert not store.append(_event("e1", 200.0))  # 重复 ID 忽略（内存）
        rows = conn.execute("SELECT COUNT(*) FROM event_store").fetchone()[0]
        assert rows == 1  # INSERT OR IGNORE 未写第二行

    def test_no_connection_keeps_memory_only(self):
        store = EventStore()
        assert store.append(_event("e1", 100.0))
        assert store.stats()["total_events"] == 1


class TestArchiveMark:
    def test_archive_marks_header_archived(self):
        store = EventStore()
        store.append(_event("e1", 100.0))
        store.append(_event("e2", 200.0))
        mgr = EventArchiveManager(config=LifecycleConfig())
        all_events = [e for batch in store.iterate() for e in batch]
        archive = mgr.archive_batch(all_events, store=store)

        assert archive.event_count == 2
        assert store._headers["e1"].lifecycle == EventLifecyclePhase.ARCHIVED
        assert store._headers["e2"].lifecycle == EventLifecyclePhase.ARCHIVED
        # 事件本体不可变（EM54-01）
        assert store.find("e1").payload == {"k": "e1"}
