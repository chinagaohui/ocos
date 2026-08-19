"""CheckpointManager 测试。"""
from __future__ import annotations

import time
import tempfile
from pathlib import Path

import pytest

from ocos.storage.checkpoint import CheckpointManager


@pytest.fixture
def db_path():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    yield path
    Path(path).unlink(missing_ok=True)


@pytest.fixture
def cp(db_path):
    return CheckpointManager(db_path, default_ttl=86400.0)


class TestCheckpointManager:
    def test_save_and_load(self, cp):
        """save 后能 load 回完整检查点。"""
        pid = cp.save("proc-001", "execution", {"step": 5, "data": "hello"})
        assert pid == "proc-001"
        loaded = cp.load("proc-001")
        assert loaded is not None
        assert loaded["process_id"] == "proc-001"
        assert loaded["phase"] == "execution"
        assert loaded["context_snapshot"] == {"step": 5, "data": "hello"}
        assert loaded["completed"] is False

    def test_load_missing_returns_none(self, cp):
        """不存在的 process_id 返回 None。"""
        assert cp.load("nonexistent") is None

    def test_mark_completed(self, cp):
        """mark_completed 后 completed 为 True。"""
        cp.save("proc-002", "done", {"result": "ok"})
        assert cp.mark_completed("proc-002") is True
        loaded = cp.load("proc-002")
        assert loaded["completed"] is True

    def test_mark_completed_nonexistent(self, cp):
        """标记不存在的 id 返回 False。"""
        assert cp.mark_completed("nothing") is False

    def test_list_incomplete(self, cp):
        """list_incomplete 只列出未完成且未过期的。"""
        cp.save("proc-a", "phase1", {"a": 1})
        cp.save("proc-b", "phase2", {"b": 2})
        cp.mark_completed("proc-b")
        items = cp.list_incomplete()
        assert len(items) == 1
        assert items[0]["process_id"] == "proc-a"

    def test_exists(self, cp):
        """exists 返回进程是否存在。"""
        cp.save("proc-exists", "x", {})
        assert cp.exists("proc-exists") is True
        assert cp.exists("nonexistent") is False

    def test_count(self, cp):
        """count 返回正确数量。"""
        assert cp.count() == 0
        cp.save("a", "x", {})
        cp.save("b", "x", {})
        assert cp.count() == 2

    def test_delete(self, cp):
        """delete 后 load 返回 None。"""
        cp.save("proc-del", "x", {})
        assert cp.delete("proc-del") is True
        assert cp.load("proc-del") is None

    def test_delete_nonexistent(self, cp):
        """删除不存在的 id 返回 False。"""
        assert cp.delete("nothing") is False

    def test_ttl_expiration(self, db_path):
        """TTL 过期后 load 返回 None。"""
        cp = CheckpointManager(db_path, default_ttl=None)
        cp.save("proc-ttl", "ephemeral", {"data": "gone"}, ttl=0.001)
        time.sleep(0.1)
        assert cp.load("proc-ttl") is None

    def test_clear_expired(self, db_path):
        """clear_expired 只清理过期条目。"""
        cp = CheckpointManager(db_path, default_ttl=None)
        cp.save("keep", "live", {}, ttl=3600)
        cp.save("dead", "expired", {}, ttl=0.001)
        time.sleep(0.1)
        cleaned = cp.clear_expired()
        assert cleaned >= 1
        assert cp.load("keep") is not None

    def test_clear_all(self, cp):
        """clear_all 清空所有。"""
        cp.save("a", "x", {})
        cp.save("b", "x", {})
        assert cp.clear_all() == 2
        assert cp.count() == 0

    def test_list_incomplete_excludes_expired(self, db_path):
        """list_incomplete 排除过期条目。"""
        cp = CheckpointManager(db_path, default_ttl=None)
        cp.save("fresh", "phase1", {}, ttl=3600)
        cp.save("stale", "phase2", {}, ttl=0.001)
        time.sleep(0.1)
        items = cp.list_incomplete()
        assert len(items) == 1
        assert items[0]["process_id"] == "fresh"

    def test_persistence_across_instances(self, db_path):
        """关闭后重新打开数据仍在。"""
        cp1 = CheckpointManager(db_path)
        cp1.save("persist", "phase1", {"key": 99})
        loaded1 = cp1.load("persist")
        assert loaded1 is not None

        cp2 = CheckpointManager(db_path)
        loaded2 = cp2.load("persist")
        assert loaded2 is not None
        assert loaded2["context_snapshot"] == {"key": 99}
