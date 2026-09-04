"""OCOS state_serializer 序列化器不变式测试。

PS51-04: format_version 保证跨版本可读。
"""

import json
import os
import tempfile
import pytest

from ocos.persistence.storage_types import (
    Snapshot, DomainSnapshot, SnapshotDomain, SnapshotStatus,
)
from ocos.persistence.state_serializer import StateSerializer


@pytest.fixture
def serializer():
    with tempfile.TemporaryDirectory() as tmpdir:
        s = StateSerializer(storage_root=__import__("pathlib").Path(tmpdir) / "snapshots")
        yield s


@pytest.fixture
def sample_snapshot():
    return Snapshot(
        snapshot_id="test-snap-001",
        format_version="1.0.0",
        tick=42,
        timestamp=1234567890.0,
        domains={
            SnapshotDomain.RUNTIME.value: DomainSnapshot(
                domain=SnapshotDomain.RUNTIME, tick=42,
                timestamp=1234567890.0, data={"tick": 42},
                checksum="abc", status=SnapshotStatus.VALIDATED,
            ),
            SnapshotDomain.MEMORY.value: DomainSnapshot(
                domain=SnapshotDomain.MEMORY, tick=42,
                timestamp=1234567890.0, data={"beliefs": 100},
                checksum="def", status=SnapshotStatus.TAKEN,
            ),
        },
        metadata={"host": "test-host"},
        status=SnapshotStatus.VALIDATED,
    )


class TestSerializeDeserialize:
    def test_roundtrip(self, serializer, sample_snapshot):
        raw = serializer.serialize(sample_snapshot)
        restored = serializer.deserialize(raw)
        assert restored.snapshot_id == sample_snapshot.snapshot_id
        assert restored.tick == sample_snapshot.tick
        assert restored.format_version == sample_snapshot.format_version
        assert restored.status == sample_snapshot.status

    def test_json_format_valid(self, serializer, sample_snapshot):
        raw = serializer.serialize(sample_snapshot)
        data = json.loads(raw)
        assert data["_format"] == "ocos-snapshot-v1"
        assert data["snapshot_id"] == "test-snap-001"
        assert "domains" in data

    def test_deserialize_missing_fields_falls_back(self, serializer):
        minimal = '{"snapshot_id": "min-001", "tick": 0}'
        s = serializer.deserialize(minimal)
        assert s.snapshot_id == "min-001"
        assert s.tick == 0
        assert s.domains == {}

    def test_deserialize_old_format_version(self, serializer):
        """PS51-04: 旧格式也能读取（带 warning）。"""
        old = json.dumps({
            "snapshot_id": "old-001",
            "format_version": "0.9.0",
            "tick": 10,
            "domains": {},
        })
        s = serializer.deserialize(old)
        assert s.snapshot_id == "old-001"
        assert s.format_version == "0.9.0"


class TestSaveLoad:
    def test_save_and_load(self, serializer, sample_snapshot):
        path = serializer.save(sample_snapshot)
        assert path.exists()
        loaded = serializer.load("test-snap-001")
        assert loaded is not None
        assert loaded.snapshot_id == "test-snap-001"

    def test_load_missing_returns_none(self, serializer):
        assert serializer.load("nonexistent") is None

    def test_list_snapshots_empty(self, serializer):
        assert serializer.list_snapshots() == []

    def test_manifest_updated_after_save(self, serializer, sample_snapshot):
        serializer.save(sample_snapshot)
        manifest = serializer.list_snapshots()
        assert len(manifest) == 1
        assert manifest[0]["snapshot_id"] == "test-snap-001"

    def test_load_latest_returns_full_snapshot(self, serializer, sample_snapshot):
        serializer.save(sample_snapshot)
        latest = serializer.load_latest()
        assert latest is not None
        assert latest.snapshot_id == "test-snap-001"

    def test_load_latest_with_corrupt_entry(self, serializer):
        """损坏的 manifest entry 应跳过。"""
        import json as _json
        from pathlib import Path
        manifest_path = serializer.storage_root / "manifest.json"
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(
            _json.dumps({"snapshots": [
                {"snapshot_id": "bad", "tick": 1, "status": "taken",
                 "timestamp": 0.0, "domains": []},
            ]})
        )
        # bad snapshot file doesn't exist, load_latest should return None
        assert serializer.load_latest() is None


class TestPrune:
    def test_prune_keeps_latest(self, serializer):
        for i in range(5):
            s = Snapshot(snapshot_id=f"snap-{i}", tick=i)
            serializer.save(s)
        removed = serializer.prune(keep=2)
        assert removed == 3  # 5 - 2 = 3

    def test_prune_no_remove_when_under_limit(self, serializer):
        for i in range(3):
            s = Snapshot(snapshot_id=f"snap-{i}", tick=i)
            serializer.save(s)
        removed = serializer.prune(keep=10)
        assert removed == 0
