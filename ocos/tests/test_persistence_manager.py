"""Phase V: PersistenceManager 单元测试。"""

import json
import time
from pathlib import Path

import pytest

from ocos.persistence.manager import (
    PersistenceManager,
    PersistenceConfig,
    SnapshotType,
    RestoreStrategy,
)


class TestPersistenceManager:
    """PersistenceManager 核心功能测试。"""

    def test_create(self, tmp_path):
        config = PersistenceConfig(base_dir=str(tmp_path / "persistence"))
        mgr = PersistenceManager(config)
        stats = mgr.get_stats()
        assert stats["total_saves"] == 0
        assert stats["total_restores"] == 0

    def test_save_and_restore(self, tmp_path):
        config = PersistenceConfig(base_dir=str(tmp_path / "persistence"))
        mgr = PersistenceManager(config)

        data = {"domain1": {"key": "value1"}, "domain2": {"key": "value2"}}
        result = mgr.save(data, SnapshotType.FULL, reason="test")
        assert result.success is True
        assert result.snapshot_id != ""
        assert result.size_bytes > 0

        restore_result = mgr.restore(RestoreStrategy.SPECIFIC, result.snapshot_id)
        assert restore_result.success is True
        assert restore_result.snapshot_id == result.snapshot_id
        assert "domain1" in restore_result.domains_restored
        assert "domain2" in restore_result.domains_restored

    def test_save_multiple_snapshots(self, tmp_path):
        config = PersistenceConfig(base_dir=str(tmp_path / "persistence"))
        mgr = PersistenceManager(config)

        for i in range(5):
            mgr.save({"step": i}, SnapshotType.FULL, reason=f"test_{i}")

        snapshots = mgr.list_snapshots()
        assert len(snapshots) == 5

    def test_list_snapshots(self, tmp_path):
        config = PersistenceConfig(base_dir=str(tmp_path / "persistence"))
        mgr = PersistenceManager(config)
        assert mgr.list_snapshots() == []

        mgr.save({"a": 1})
        mgr.save({"b": 2})
        snapshots = mgr.list_snapshots()
        assert len(snapshots) == 2
        assert all("snapshot_id" in s for s in snapshots)

    def test_delete_snapshot(self, tmp_path):
        config = PersistenceConfig(base_dir=str(tmp_path / "persistence"))
        mgr = PersistenceManager(config)
        result = mgr.save({"x": 1})
        assert mgr.delete_snapshot(result.snapshot_id) is True
        assert len(mgr.list_snapshots()) == 0
        assert mgr.delete_snapshot("nonexistent") is False

    def test_clear_all(self, tmp_path):
        config = PersistenceConfig(base_dir=str(tmp_path / "persistence"))
        mgr = PersistenceManager(config)
        mgr.save({"a": 1})
        mgr.save({"b": 2})
        assert mgr.clear_all() == 2
        assert len(mgr.list_snapshots()) == 0

    def test_auto_save_interval(self, tmp_path):
        config = PersistenceConfig(base_dir=str(tmp_path / "persistence"), snapshot_interval=0.1)
        mgr = PersistenceManager(config)

        # 首次保存
        r1 = mgr.auto_save_if_needed({"tick": 1}, tick=1)
        assert r1 is not None
        assert r1.success is True

        # 间隔内不保存
        r2 = mgr.auto_save_if_needed({"tick": 2}, tick=2)
        assert r2 is None

        # 等待间隔后再次保存
        time.sleep(0.2)
        r3 = mgr.auto_save_if_needed({"tick": 3}, tick=3)
        assert r3 is not None

    def test_get_stats(self, tmp_path):
        config = PersistenceConfig(base_dir=str(tmp_path / "persistence"))
        mgr = PersistenceManager(config)
        mgr.save({"test": 1})
        stats = mgr.get_stats()
        assert stats["total_saves"] == 1
        assert stats["snapshot_count"] == 1

    def test_generate_report(self, tmp_path):
        config = PersistenceConfig(base_dir=str(tmp_path / "persistence"))
        mgr = PersistenceManager(config)
        mgr.save({"test": 1})
        report = mgr.generate_report()
        assert "持久化与恢复报告" in report
        assert "总保存次数: 1" in report

    def test_prune_snapshots(self, tmp_path):
        config = PersistenceConfig(base_dir=str(tmp_path / "persistence"), max_snapshots=3)
        mgr = PersistenceManager(config)
        for i in range(5):
            mgr.save({"step": i})
        snapshots = mgr.list_snapshots()
        assert len(snapshots) <= 3

    def test_restore_no_snapshot(self, tmp_path):
        config = PersistenceConfig(base_dir=str(tmp_path / "persistence"))
        mgr = PersistenceManager(config)
        result = mgr.restore(RestoreStrategy.LATEST)
        assert result.success is False
        assert "No snapshot found" in result.error

    def test_restore_latest(self, tmp_path):
        config = PersistenceConfig(base_dir=str(tmp_path / "persistence"))
        mgr = PersistenceManager(config)
        mgr.save({"domain1": "val1"}, reason="first")
        time.sleep(0.1)
        mgr.save({"domain2": "val2"}, reason="second")

        result = mgr.restore(RestoreStrategy.LATEST)
        assert result.success is True
        assert "domain2" in result.domains_restored


class TestSnapshotTypes:
    """快照类型测试。"""

    def test_full_snapshot(self, tmp_path):
        mgr = PersistenceManager(PersistenceConfig(base_dir=str(tmp_path / "p")))
        result = mgr.save({"data": "full"}, SnapshotType.FULL)
        assert result.snapshot_type == "FULL"

    def test_incremental_snapshot(self, tmp_path):
        mgr = PersistenceManager(PersistenceConfig(base_dir=str(tmp_path / "p")))
        result = mgr.save({"delta": True}, SnapshotType.INCREMENTAL)
        assert result.snapshot_type == "INCREMENTAL"


class TestRestoreStrategies:
    """恢复策略测试。"""

    def test_latest_strategy(self, tmp_path):
        mgr = PersistenceManager(PersistenceConfig(base_dir=str(tmp_path / "p")))
        mgr.save({"a": 1})
        result = mgr.restore(RestoreStrategy.LATEST)
        assert result.success is True

    def test_specific_strategy(self, tmp_path):
        mgr = PersistenceManager(PersistenceConfig(base_dir=str(tmp_path / "p")))
        r = mgr.save({"x": 1})
        result = mgr.restore(RestoreStrategy.SPECIFIC, r.snapshot_id)
        assert result.success is True
        assert result.snapshot_id == r.snapshot_id
