"""OCOS persistence_manager 持久化管理器不变式测试。"""

import json
import os
import tempfile
import pytest

from ocos.persistence.manager import (
    PersistenceManager,
    PersistenceConfig,
    SnapshotType,
    RestoreStrategy,
    SaveResult,
    RestoreResult,
)


@pytest.fixture
def pm():
    with tempfile.TemporaryDirectory() as tmpdir:
        config = PersistenceConfig(base_dir=tmpdir)
        yield PersistenceManager(config)


class TestPersistenceConfig:
    def test_defaults(self):
        c = PersistenceConfig()
        assert c.base_dir == "ocos_data/persistence"
        assert c.snapshot_interval == 300.0
        assert c.max_snapshots == 20
        assert c.auto_save_on_event is True
        assert c.auto_restore_on_start is True


class TestSaveRestore:
    def test_save_full_snapshot(self, pm):
        result = pm.save({"key": "value"}, SnapshotType.FULL, reason="test")
        assert result.success is True
        assert result.snapshot_type == "FULL"
        assert result.size_bytes > 0
        assert result.error == ""

    def test_save_incremental(self, pm):
        result = pm.save({"delta": 1}, SnapshotType.INCREMENTAL, reason="inc")
        assert result.success is True
        assert result.snapshot_type == "INCREMENTAL"

    def test_save_then_restore(self, pm):
        save_result = pm.save({"domain_a": 1, "domain_b": 2})
        assert save_result.success
        restore_result = pm.restore(RestoreStrategy.LATEST)
        assert restore_result.success
        assert restore_result.snapshot_id == save_result.snapshot_id

    def test_restore_missing_snapshot(self, pm):
        result = pm.restore(RestoreStrategy.LATEST)
        assert result.success is False
        assert "No snapshot found" in result.error

    def test_restore_specific(self, pm):
        r1 = pm.save({"data": 1}, reason="first")
        r2 = pm.save({"data": 2}, reason="second")
        result = pm.restore(RestoreStrategy.SPECIFIC, snapshot_id=r2.snapshot_id)
        assert result.success
        assert result.snapshot_id == r2.snapshot_id

    def test_list_snapshots(self, pm):
        assert pm.list_snapshots() == []
        pm.save({"a": 1})
        snaps = pm.list_snapshots()
        assert len(snaps) == 1
        assert "snapshot_id" in snaps[0]
        assert "type" in snaps[0]

    def test_delete_snapshot(self, pm):
        r = pm.save({"x": 1})
        assert pm.delete_snapshot(r.snapshot_id) is True
        assert pm.delete_snapshot("nonexistent") is False
        assert pm.list_snapshots() == []


class TestAutoOperations:
    def test_auto_save_if_needed_skip(self, pm):
        """短时间内不应重复保存。"""
        import time as _time
        pm._last_save_time = _time.time()
        pm._config.snapshot_interval = 300.0
        result = pm.auto_save_if_needed({"x": 1}, tick=10)
        assert result is None

    def test_auto_save_if_needed_trigger(self, pm):
        """时间间隔超过后应触发保存。"""
        pm._last_save_time = 0.0
        pm._config.snapshot_interval = 0.001  # 极短间隔
        result = pm.auto_save_if_needed({"x": 1})
        assert result is not None
        assert result.success is True

    def test_auto_restore_disabled(self, pm):
        pm._config.auto_restore_on_start = False
        pm.save({"x": 1})
        result = pm.auto_restore_on_start()
        assert result is None

    def test_auto_restore_enabled_no_snapshot(self, pm):
        pm._config.auto_restore_on_start = True
        result = pm.auto_restore_on_start()
        assert result is None  # 无快照

    def test_get_recovery_candidate_no_snapshot(self, pm):
        assert pm.get_recovery_candidate() is None

    def test_get_recovery_candidate_has_snapshot(self, pm):
        pm.save({"x": 1})
        candidate = pm.get_recovery_candidate()
        assert candidate is not None
        assert "snapshot_id" in candidate


class TestStatistics:
    def test_stats_empty(self, pm):
        stats = pm.get_stats()
        assert stats["total_saves"] == 0
        assert stats["total_restores"] == 0
        assert stats["snapshot_count"] == 0

    def test_stats_after_operations(self, pm):
        pm.save({"a": 1})
        pm.save({"b": 2})
        pm.restore(RestoreStrategy.LATEST)
        stats = pm.get_stats()
        assert stats["total_saves"] == 2
        assert stats["total_restores"] == 1
        assert stats["snapshot_count"] == 2

    def test_generate_report(self, pm):
        pm.save({"a": 1})
        report = pm.generate_report()
        assert "持久化与恢复报告" in report
        assert "总保存次数: 1" in report


class TestPrune:
    def test_prune_enforces_max_snapshots(self, pm):
        pm._config.max_snapshots = 2
        for i in range(5):
            pm.save({"i": i})
        # list_snapshots 按 mtime 排序
        snapshots = pm.list_snapshots()
        assert len(snapshots) <= 2
