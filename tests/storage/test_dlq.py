"""SQLiteDLQ 测试。"""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from ocos.storage.dead_letter_queue import SQLiteDLQ


@pytest.fixture
def db_path():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    yield path
    Path(path).unlink(missing_ok=True)


@pytest.fixture
def dlq(db_path):
    return SQLiteDLQ(db_path, max_retries=3)


class TestSQLiteDLQ:
    def test_enqueue_and_list(self, dlq):
        """enqueue 后能在列表中查到。"""
        eid = dlq.enqueue("evt-001", "timeout", {"data": "test"})
        assert eid > 0
        unresolved = dlq.list_unresolved()
        assert len(unresolved) == 1
        assert unresolved[0]["event_id"] == "evt-001"
        assert unresolved[0]["reason"] == "timeout"
        assert unresolved[0]["payload"] == {"data": "test"}
        assert unresolved[0]["resolved"] is False

    def test_enqueue_without_payload(self, dlq):
        """enqueue 可以不传 payload。"""
        eid = dlq.enqueue("evt-002", "format_error")
        assert eid > 0
        item = dlq.list_unresolved()[0]
        assert item["payload"] is None

    def test_mark_resolved(self, dlq):
        """mark_resolved 将状态改为已解决。"""
        eid = dlq.enqueue("evt-003", "ok")
        assert dlq.mark_resolved(eid) is True
        assert dlq.count_unresolved() == 0

    def test_mark_resolved_nonexistent(self, dlq):
        """标记不存在的 id 返回 False。"""
        assert dlq.mark_resolved(9999) is False

    def test_increment_retry(self, dlq):
        """increment_retry 增加重试计数。"""
        eid = dlq.enqueue("evt-004", "retry")
        assert dlq.increment_retry(eid) == 1
        assert dlq.increment_retry(eid) == 2

    def test_is_exhausted(self, dlq):
        """超过 max_retries 后 is_exhausted 返回 True。"""
        eid = dlq.enqueue("evt-005", "exhaust")
        dlq.increment_retry(eid)
        dlq.increment_retry(eid)
        dlq.increment_retry(eid)
        assert dlq.is_exhausted(eid) is True

    def test_list_all_filter(self, dlq):
        """list_all 支持按 resolved 状态过滤。"""
        id1 = dlq.enqueue("evt-a", "x")
        id2 = dlq.enqueue("evt-b", "y")
        dlq.mark_resolved(id2)
        all_items = dlq.list_all()
        assert len(all_items) == 2
        resolved_items = dlq.list_all(resolved=True)
        assert len(resolved_items) == 1
        assert resolved_items[0]["event_id"] == "evt-b"
        unresolved_items = dlq.list_all(resolved=False)
        assert len(unresolved_items) == 1
        assert unresolved_items[0]["event_id"] == "evt-a"

    def test_count_unresolved(self, dlq):
        """count_unresolved 返回正确的未处理数量。"""
        assert dlq.count_unresolved() == 0
        dlq.enqueue("evt-c", "err")
        dlq.enqueue("evt-d", "err")
        assert dlq.count_unresolved() == 2

    def test_delete(self, dlq):
        """delete 移除记录。"""
        eid = dlq.enqueue("evt-del", "gone")
        assert dlq.delete(eid) is True
        assert dlq.count_unresolved() == 0

    def test_delete_nonexistent(self, dlq):
        """删除不存在的 id 返回 False。"""
        assert dlq.delete(9999) is False

    def test_clear_all(self, dlq):
        """clear_all 清空所有记录。"""
        dlq.enqueue("evt-e", "a")
        dlq.enqueue("evt-f", "b")
        assert dlq.clear_all() == 2
        assert dlq.count_unresolved() == 0
