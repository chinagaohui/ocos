"""SQLiteWorkingMemory 测试。"""
from __future__ import annotations

import json
import time
import tempfile
from pathlib import Path

import pytest

from ocos.storage.working_memory import SQLiteWorkingMemory


@pytest.fixture
def db_path():
    """每个测试使用独立的临时数据库文件。"""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    yield path
    Path(path).unlink(missing_ok=True)


@pytest.fixture
def wm(db_path):
    """创建一个默认配置的 WorkingMemory 实例。"""
    return SQLiteWorkingMemory(db_path, max_entries=100, default_ttl=3600)


class TestSQLiteWorkingMemory:
    def test_store_and_load(self, wm):
        """store 后能 load 回相同内容。"""
        wm.store("test:1", {"name": "hello", "count": 42})
        result = wm.load("test:1")
        assert result is not None
        assert result["name"] == "hello"
        assert result["count"] == 42

    def test_load_missing_returns_none(self, wm):
        """不存在的 key 返回 None。"""
        assert wm.load("nonexistent") is None

    def test_ttl_expiration(self, wm):
        """TTL 过期后 load 返回 None。"""
        wm.store("ephemeral", {"data": "gone"}, ttl=0.001)  # 1ms TTL
        time.sleep(0.1)
        result = wm.load("ephemeral")
        assert result is None

    def test_delete(self, wm):
        """delete 后 load 返回 None。"""
        wm.store("deletable", {"data": "bye"})
        assert wm.delete("deletable") is True
        assert wm.load("deletable") is None

    def test_delete_nonexistent_returns_false(self, wm):
        """删除不存在的 key 返回 False。"""
        assert wm.delete("nothing") is False

    def test_max_entries(self, db_path):
        """超过 max_entries 时拒绝写入。"""
        wm = SQLiteWorkingMemory(db_path, max_entries=3)
        wm.store("a", {"v": 1})
        wm.store("b", {"v": 2})
        wm.store("c", {"v": 3})
        with pytest.raises(ValueError, match="WorkingMemory 已满"):
            wm.store("d", {"v": 4})

    def test_clear_expired(self, wm):
        """clear_expired 只清理过期条目。"""
        wm.store("keep", {"data": "live"}, ttl=3600)       # 1 小时后过期
        wm.store("expire_fast", {"data": "dead"}, ttl=0.001)  # 1ms 过期
        time.sleep(0.1)
        cleaned = wm.clear_expired()
        assert cleaned >= 1
        assert wm.load("keep") is not None

    def test_persistence_across_instances(self, db_path):
        """关闭后重新打开数据仍在。"""
        wm1 = SQLiteWorkingMemory(db_path)
        wm1.store("persist", {"count": 99})
        wm1.close()

        wm2 = SQLiteWorkingMemory(db_path)
        result = wm2.load("persist")
        assert result is not None
        assert result["count"] == 99
        wm2.close()

    def test_list_keys(self, wm):
        """list_keys 返回所有键。"""
        wm.store("a:1", {"v": 1})
        wm.store("a:2", {"v": 2})
        wm.store("b:1", {"v": 3})
        keys = wm.list_keys()
        assert len(keys) == 3
        assert "a:1" in keys
        assert "a:2" in keys
        assert "b:1" in keys

    def test_list_keys_with_pattern(self, wm):
        """list_keys 支持模式匹配。"""
        wm.store("cat", {"v": 1})
        wm.store("car", {"v": 2})
        wm.store("dog", {"v": 3})
        keys = wm.list_keys("ca%")
        assert len(keys) == 2
        assert "cat" in keys
        assert "car" in keys

    def test_count(self, wm):
        """count 返回正确条目数。"""
        assert wm.count() == 0
        wm.store("a", {"v": 1})
        wm.store("b", {"v": 2})
        assert wm.count() == 2
