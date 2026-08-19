"""Phase 21 Prompt 1 测试: Agent Snapshot System + 数据库 Schema。

验收条件:
- test_snapshot_frozen: AgentSnapshot 不可变
- test_snapshot_working_memory_items_empty: sleep 后 items 为空
- test_snapshot_save_load_roundtrip: 保存→加载→反序列化 完整性
- test_snapshot_atomic_lock: 并发保存不丢数据
- test_recovery_no_snapshot: 无快照时返回失败
- test_recovery_with_snapshot: 有快照时成功恢复
"""

import json
import os
import sqlite3
import tempfile
import threading
from datetime import datetime, timezone

import pytest

from ocos.snapshot.models import AgentSnapshot
from ocos.snapshot.manager import SnapshotManager
from ocos.snapshot.recovery import CrashRecovery, RecoveryResult


# ── Fixtures ──────────────────────────────────────────────────────────


@pytest.fixture
def temp_db():
    """创建临时 SQLite 数据库。"""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    # 创建表
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS snapshots (
            snapshot_id TEXT PRIMARY KEY,
            version TEXT NOT NULL,
            created_at TIMESTAMP NOT NULL,
            is_recovered BOOLEAN DEFAULT 0,
            data JSON NOT NULL,
            size_kb INTEGER,
            recovered_at TIMESTAMP,
            agent_id TEXT DEFAULT 'master'
        );
        CREATE INDEX IF NOT EXISTS idx_snapshots_created_at ON snapshots(created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_snapshots_recovered ON snapshots(is_recovered);
    """)
    conn.close()
    old_db = os.environ.get("OCOS_DB_PATH")
    os.environ["OCOS_DB_PATH"] = path
    yield path
    if old_db:
        os.environ["OCOS_DB_PATH"] = old_db
    os.unlink(path)


@pytest.fixture
def snapshot_mgr(temp_db):
    """创建 SnapshotManager 实例。"""
    return SnapshotManager(db_path=temp_db)


@pytest.fixture
def sample_snapshot():
    """创建一个样例 AgentSnapshot。"""
    return AgentSnapshot(
        snapshot_id="snap-test-001",
        identity_state={"agent_id": "master", "name": "OCOS-Test"},
        goal_state=[
            {"id": "g-1", "level": "LONG", "status": "ACTIVE", "description": "Test goal"}
        ],
        working_memory_config={"capacity": 100, "items": []},
        runtime_state={"agent_state": "WAKE"},
    )


# ── 模型测试 ──────────────────────────────────────────────────────────


def test_snapshot_frozen():
    """AgentSnapshot 不可变。"""
    snap = AgentSnapshot(snapshot_id="snap-frozen")
    with pytest.raises(Exception):  # FrozenInstanceError
        snap.snapshot_id = "modified"  # type: ignore[misc]


def test_snapshot_working_memory_items_empty(sample_snapshot):
    """sleep 后 Snapshot 的 working_memory_config 中 items 为空。"""
    wm = sample_snapshot.working_memory_config
    # items 强制为空
    assert wm.get("items", ["SHOULD_NOT_EXIST"]) == []
    # capacity 存在
    assert wm.get("capacity", 0) == 100


def test_snapshot_to_json_from_json_roundtrip(sample_snapshot):
    """JSON 序列化和反序列化往返测试。"""
    json_str = sample_snapshot.to_json()
    restored = AgentSnapshot.from_json(json_str)

    assert restored.snapshot_id == sample_snapshot.snapshot_id
    assert restored.identity_state == sample_snapshot.identity_state
    assert restored.goal_state == sample_snapshot.goal_state
    assert restored.working_memory_config["capacity"] == 100
    assert restored.working_memory_config.get("items", []) == []


# ── Manager 测试 ──────────────────────────────────────────────────────


def test_snapshot_save_and_load(snapshot_mgr, sample_snapshot):
    """保存后可以加载。"""
    sid = snapshot_mgr.save(sample_snapshot)
    assert sid == "snap-test-001"

    loaded = snapshot_mgr.load_latest()
    assert loaded is not None
    assert loaded.snapshot_id == "snap-test-001"
    assert loaded.identity_state == sample_snapshot.identity_state


def test_snapshot_load_empty(snapshot_mgr):
    """空数据库返回 None。"""
    loaded = snapshot_mgr.load_latest()
    assert loaded is None


def test_snapshot_atomic_lock(snapshot_mgr):
    """并发保存不丢数据。"""
    errors = []
    results = []

    def save_snapshot(i):
        try:
            snap = AgentSnapshot(
                snapshot_id=f"snap-concurrent-{i}",
                identity_state={"index": i},
            )
            sid = snapshot_mgr.save(snap)
            results.append(sid)
        except Exception as e:
            errors.append(str(e))

    threads = [threading.Thread(target=save_snapshot, args=(i,)) for i in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(errors) == 0, f"Errors: {errors}"
    assert len(results) == 10


def test_snapshot_mark_recovered(snapshot_mgr, sample_snapshot):
    """标记恢复后 is_recovered 变为 1。"""
    snapshot_mgr.save(sample_snapshot)
    snapshot_mgr.mark_recovered("snap-test-001")

    # 通过 load_latest 重新序列化不会保留 is_recovered 字段
    # 因此直接查 SQLite
    import sqlite3
    conn = sqlite3.connect(snapshot_mgr._db_path)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT is_recovered, recovered_at FROM snapshots WHERE snapshot_id = ?",
        ("snap-test-001",),
    ).fetchone()
    conn.close()
    assert row is not None
    assert row["is_recovered"] == 1
    assert row["recovered_at"] is not None


# ── Recovery 测试 ─────────────────────────────────────────────────────


def test_recovery_no_snapshot(snapshot_mgr):
    """无快照时返回失败。"""
    recovery = CrashRecovery(snapshot_mgr)
    result = recovery.recover()
    assert result.success is False
    assert result.snapshot_id is None
    assert "No snapshot found" in result.errors


def test_recovery_with_snapshot(snapshot_mgr, sample_snapshot):
    """有快照时成功恢复。"""
    snapshot_mgr.save(sample_snapshot)

    recovery = CrashRecovery(snapshot_mgr)
    result = recovery.recover()

    assert result.success is True
    assert result.snapshot_id == "snap-test-001"
    assert result.restored_goals == 1
    assert len(result.errors) == 0
