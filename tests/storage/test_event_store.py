"""SQLiteEventStore 测试。"""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from ocos.storage.event_store import SQLiteEventStore


@pytest.fixture
def db_path():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    yield path
    Path(path).unlink(missing_ok=True)


@pytest.fixture
def es(db_path):
    return SQLiteEventStore(db_path)


class TestSQLiteEventStore:
    def test_append_and_load(self, es):
        """append 后能 load 回完整事件。"""
        eid = es.append("test.event", {"key": "value"}, source="test")
        loaded = es.load(eid)
        assert loaded is not None
        assert loaded["event_type"] == "test.event"
        assert loaded["payload"] == {"key": "value"}
        assert loaded["source"] == "test"
        assert loaded["sequence"] == 1

    def test_load_missing_returns_none(self, es):
        """不存在的 event_id 返回 None。"""
        assert es.load("nonexistent") is None

    def test_append_batch(self, es):
        """批量追加成功，序列号连续。"""
        ids = es.append_batch([
            {"event_type": "a", "payload": {"n": 1}},
            {"event_type": "b", "payload": {"n": 2}},
            {"event_type": "c", "payload": {"n": 3}},
        ])
        assert len(ids) == 3
        assert es.load(ids[0])["sequence"] == 1
        assert es.load(ids[1])["sequence"] == 2
        assert es.load(ids[2])["sequence"] == 3

    def test_empty_batch_returns_empty(self, es):
        """空批量返回空列表。"""
        assert es.append_batch([]) == []

    def test_replay_all(self, es):
        """replay 返回全部事件，按 sequence 排序。"""
        es.append("a", {"n": 1})
        es.append("b", {"n": 2})
        events = es.replay()
        assert len(events) == 2
        assert [e["event_type"] for e in events] == ["a", "b"]

    def test_replay_by_type(self, es):
        """按事件类型过滤 replay。"""
        es.append("type_a", {"n": 1})
        es.append("type_b", {"n": 2})
        es.append("type_a", {"n": 3})
        events = es.replay(event_type="type_a")
        assert len(events) == 2
        assert all(e["event_type"] == "type_a" for e in events)

    def test_replay_with_limit_and_offset(self, es):
        """replay 支持分页。"""
        for i in range(10):
            es.append("t", {"i": i})
        page1 = es.replay(limit=3)
        assert len(page1) == 3
        page2 = es.replay(limit=3, offset=3)
        assert len(page2) == 3
        # 无重叠
        assert page1[0]["event_id"] != page2[0]["event_id"]

    def test_count(self, es):
        """count 返回正确数量。"""
        assert es.count() == 0
        es.append("a", {})
        es.append("b", {})
        assert es.count() == 2

    def test_count_by_type(self, es):
        """按类型统计数量。"""
        es.append("x", {})
        es.append("y", {})
        es.append("x", {})
        assert es.count(event_type="x") == 2
        assert es.count(event_type="y") == 1

    def test_idempotent_append(self, es):
        """相同 event_id 不会重复写入。"""
        eid = "fixed-id-001"
        es.append("t", {"v": 1}, event_id=eid)
        es.append("t", {"v": 2}, event_id=eid)
        events = es.replay()
        assert len(events) == 1
        assert events[0]["payload"] == {"v": 1}  # 首次写入保留

    def test_latest_sequence(self, es):
        """latest_sequence 返回当前最大序列号。"""
        assert es.latest_sequence() == 0
        es.append("a", {})
        assert es.latest_sequence() == 1
        es.append("b", {})
        assert es.latest_sequence() == 2

    def test_delete_all(self, es):
        """delete_all 清空事件表。"""
        es.append("a", {})
        es.append("b", {})
        assert es.delete_all() == 2
        assert es.count() == 0
        # 序列号重置
        es.append("c", {})
        assert es.latest_sequence() == 1
