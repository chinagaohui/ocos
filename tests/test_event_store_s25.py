"""S2.5: event_store 时间统一 + 生命周期归一回归（白皮书 P2）。

- 新写入 created_at 为统一 UTC ISO Z 格式（含亚秒）
- load_from_db 兼容解析三种历史格式
- mark_archived 同步 header 与事件本体（headers() 与 find() 一致）
- 迁移脚本 classify 三种格式 + dry-run 不写库
"""

from __future__ import annotations

import json
import sqlite3
import sys
import uuid
from datetime import datetime, timezone

import pytest

from ocos.event_memory.event_store import (
    EventStore, _parse_created_at,
)
from ocos.event_memory.event_types import (
    CognitiveEvent, CognitiveEventType, EventConfidence,
    EventLifecyclePhase,
)


def _event() -> CognitiveEvent:
    return CognitiveEvent(
        event_id=f"ev-action-{uuid.uuid4().hex[:8]}",
        event_type=CognitiveEventType.ACTION,
        timestamp=datetime.now(timezone.utc).timestamp(),
        source="s25-test",
        payload={"step": "probe"},
        confidence=EventConfidence.HIGH,
    )


class TestUnifiedTimeFormat:
    def test_new_write_uses_utc_z_format(self, tmp_path):
        conn = sqlite3.connect(str(tmp_path / "t.db"))
        conn.execute(
            "CREATE TABLE event_store (event_id TEXT PRIMARY KEY, "
            "event_type TEXT, payload TEXT, source TEXT, "
            "created_at TEXT, sequence INTEGER)")
        store = EventStore(connection=conn)
        ev = _event()
        store.append(ev)
        row = conn.execute(
            "SELECT created_at FROM event_store").fetchone()
        created = row[0]
        assert created.endswith("Z")
        assert "." in created  # 含亚秒
        # 解析回 Epoch 与事件时间戳误差 <1s
        assert abs(_parse_created_at(created) - ev.timestamp) < 1.0

    def test_load_parses_legacy_formats(self, tmp_path):
        """三种历史格式的行都能被 load_from_db 解析（ts>0）。"""
        conn = sqlite3.connect(str(tmp_path / "t.db"))
        conn.execute(
            "CREATE TABLE event_store (event_id TEXT PRIMARY KEY, "
            "event_type TEXT, payload TEXT, source TEXT, "
            "created_at TEXT, sequence INTEGER)")
        payload = json.dumps({"x": 1})
        for i, created in enumerate([
            "2026-09-05T12:00:00.123456Z",  # 新统一格式
            "2026-09-05T12:00:00",          # 旧本地 ISO
            "2026-09-05 12:00:00",          # datetime('now') 空格式
        ]):
            conn.execute(
                "INSERT INTO event_store VALUES (?,?,?,?,?,?)",
                (f"ev-{i}", "action", payload, "s", created, i + 1))
        store = EventStore.load_from_db(conn)
        for batch in store.iterate(from_time=0.0):
            for ev in batch:
                assert ev.timestamp > 0.0, f"格式解析失败: {ev.event_id}"


class TestLifecycleUnification:
    def test_mark_archived_syncs_header_and_body(self):
        store = EventStore()
        ev = _event()
        store.append(ev)
        assert store.mark_archived(ev.event_id) is True
        # header 已归档
        assert store._headers[ev.event_id].lifecycle == \
            EventLifecyclePhase.ARCHIVED
        # 本体与索引一致（修复前只有 header 变）
        assert store._by_id[ev.event_id].lifecycle == \
            EventLifecyclePhase.ARCHIVED
        for bucket in store._events.values():
            for e in bucket:
                if e.event_id == ev.event_id:
                    assert e.lifecycle == EventLifecyclePhase.ARCHIVED

    def test_mark_archived_missing_returns_false(self):
        store = EventStore()
        assert store.mark_archived("ev-nonexistent") is False


class TestMigrationScript:
    def test_classify_and_dry_run(self, tmp_path, capsys):
        import sys as _sys
        conn = sqlite3.connect(str(tmp_path / "t.db"))
        conn.execute(
            "CREATE TABLE event_store (event_id TEXT PRIMARY KEY, "
            "event_type TEXT, payload TEXT, source TEXT, "
            "created_at TEXT, sequence INTEGER)")
        for i, created in enumerate([
            "2026-09-05T12:00:00.123456Z",
            "2026-09-05T12:00:00",
            "2026-09-05 12:00:00",
            "garbage",
        ]):
            conn.execute(
                "INSERT INTO event_store VALUES (?,?,?,?,?,?)",
                (f"ev-{i}", "action", "{}", "s", created, i + 1))
        conn.commit()
        conn.close()

        sys.path.insert(0, "scripts")
        from migrate_event_store_time import migrate
        rc = migrate(tmp_path / "t.db", assume_offset_hours=8, apply=False)
        assert rc == 0
        out = capsys.readouterr().out
        assert "local_iso(→UTC-8h)=1" in out
        assert "utc_space=1" in out
        assert "dry-run" in out
        # dry-run 未写库
        conn = sqlite3.connect(str(tmp_path / "t.db"))
        still_old = conn.execute(
            "SELECT created_at FROM event_store WHERE rowid=2").fetchone()[0]
        assert still_old == "2026-09-05T12:00:00"

    def test_apply_migrates(self, tmp_path):
        import sys as _sys
        conn = sqlite3.connect(str(tmp_path / "t.db"))
        conn.execute(
            "CREATE TABLE event_store (event_id TEXT PRIMARY KEY, "
            "event_type TEXT, payload TEXT, source TEXT, "
            "created_at TEXT, sequence INTEGER)")
        conn.execute("INSERT INTO event_store VALUES (?,?,?,?,?,?)",
                     ("ev-1", "action", "{}", "s", "2026-09-05 12:00:00", 1))
        conn.commit()
        conn.close()
        sys.path.insert(0, "scripts")
        from migrate_event_store_time import migrate
        rc = migrate(tmp_path / "t.db", assume_offset_hours=8, apply=True)
        assert rc == 0
        conn = sqlite3.connect(str(tmp_path / "t.db"))
        new_val = conn.execute(
            "SELECT created_at FROM event_store").fetchone()[0]
        assert new_val.endswith("Z") and "." in new_val
