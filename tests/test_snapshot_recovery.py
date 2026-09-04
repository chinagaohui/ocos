"""OCOS snapshot_manager + recovery_manager 快照/恢复测试。

PS51-01: Snapshot ≠ Live State（只读采集）
PS51-02: Restore ≠ Overwrite（填充，不覆盖）
PS51-03: Partial Recovery OK（部分域失败不阻止整体恢复）
"""

import pytest
import tempfile
import os

from ocos.persistence.storage_types import (
    Snapshot, DomainSnapshot, SnapshotDomain, SnapshotStatus,
    RecoveryState, RecoveryOutcome,
)
from ocos.persistence.snapshot_manager import SnapshotManager, StateProvider
from ocos.persistence.recovery_manager import RecoveryManager
from ocos.persistence.state_serializer import StateSerializer
from pathlib import Path


class FakeProvider:
    """模拟状态提供者。"""

    def __init__(self, domain: SnapshotDomain, state: dict = None):
        self._domain = domain
        self._state = state or {}

    def snapshot_domain(self) -> SnapshotDomain:
        return self._domain

    def get_state(self) -> dict:
        return self._state.copy()

    def set_state(self, data: dict) -> None:
        self._state.update(data)


class TestSnapshotManager:
    @pytest.fixture
    def manager(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            m = SnapshotManager(serializer=StateSerializer(
                storage_root=Path(tmpdir) / "snapshots"
            ))
            yield m

    def test_take_without_providers(self, manager):
        snap = manager.take(tick=1)
        assert snap.tick == 1
        assert snap.domain_count == 0
        assert snap.status == SnapshotStatus.VALIDATED

    def test_take_with_provider(self, manager):
        provider = FakeProvider(SnapshotDomain.RUNTIME, {"tick": 42})
        manager.register_provider(provider)
        snap = manager.take(tick=10)
        assert snap.domain_count == 1
        assert "runtime" in snap.domains
        ds = snap.domains["runtime"]
        assert ds.data == {"tick": 42}
        assert ds.checksum != ""

    def test_take_does_not_modify_provider(self, manager):
        """PS51-01: 快照是副本，不修改运行时。"""
        provider = FakeProvider(SnapshotDomain.RUNTIME, {"x": 1})
        manager.register_provider(provider)
        snap = manager.take(tick=1)
        assert provider.get_state() == {"x": 1}  # unchanged

    def test_validate_passes(self, manager):
        provider = FakeProvider(SnapshotDomain.RUNTIME, {"x": 1})
        manager.register_provider(provider)
        snap = manager.take(tick=1)
        assert manager.validate(snap) is True

    def test_validate_fails_on_corrupt_data(self, manager):
        provider = FakeProvider(SnapshotDomain.RUNTIME, {"x": 1})
        manager.register_provider(provider)
        snap = manager.take(tick=1)
        # Tamper with data
        snap.domains["runtime"].data["x"] = 999
        assert manager.validate(snap) is False
        assert snap.domains["runtime"].status == SnapshotStatus.CORRUPT

    def test_restore_full(self, manager):
        provider = FakeProvider(SnapshotDomain.RUNTIME, {"x": 1})
        manager.register_provider(provider)
        snap = manager.take(tick=5)
        provider.set_state({})  # clear state
        result = manager.restore(snap)
        assert result.outcome == RecoveryOutcome.FULL
        assert len(result.recovered_domains) == 1
        assert provider.get_state()["x"] == 1

    def test_restore_partial_missing_provider(self, manager):
        """PS51-03: 部分域无 provider 时仍应恢复其他域。"""
        provider = FakeProvider(SnapshotDomain.RUNTIME, {"x": 1})
        manager.register_provider(provider)
        # 创建包含两个域的快照（MEMORY 没有 provider）
        snap = Snapshot(
            snapshot_id="test-partial", tick=1,
            domains={
                SnapshotDomain.RUNTIME.value: DomainSnapshot(
                    domain=SnapshotDomain.RUNTIME, tick=1, data={"x": 1},
                    checksum="", status=SnapshotStatus.TAKEN,
                ),
                SnapshotDomain.MEMORY.value: DomainSnapshot(
                    domain=SnapshotDomain.MEMORY, tick=1, data={"mem": "data"},
                    checksum="", status=SnapshotStatus.TAKEN,
                ),
            },
        )
        result = manager.restore(snap)
        assert result.outcome == RecoveryOutcome.PARTIAL
        assert len(result.recovered_domains) == 1
        assert len(result.failed_domains) == 1

    def test_restore_no_providers(self, manager):
        snap = Snapshot(snapshot_id="s", tick=1,
                        domains={SnapshotDomain.RUNTIME.value: DomainSnapshot(
                            domain=SnapshotDomain.RUNTIME, data={"x": 1})})
        result = manager.restore(snap)
        assert result.outcome == RecoveryOutcome.FAILED

    def test_list_snapshots_empty(self, manager):
        assert manager.list_snapshots() == []

    def test_save_and_list(self, manager):
        provider = FakeProvider(SnapshotDomain.RUNTIME, {"x": 1})
        manager.register_provider(provider)
        snap = manager.take_and_save(tick=1)
        snaps = manager.list_snapshots()
        assert len(snaps) == 1
        assert snaps[0]["snapshot_id"] == snap.snapshot_id


class TestRecoveryManager:
    @pytest.fixture
    def rm(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            mgr = SnapshotManager(serializer=StateSerializer(
                storage_root=Path(tmpdir) / "snapshots"
            ))
            yield RecoveryManager(snapshot_manager=mgr)

    def test_cold_boot_no_snapshots(self, rm):
        result = rm.cold_boot()
        assert result.outcome == RecoveryOutcome.NO_SNAPSHOT

    def test_warm_boot_no_snapshots(self, rm):
        result = rm.warm_boot("nonexistent")
        assert result.outcome == RecoveryOutcome.NO_SNAPSHOT

    def test_get_phase_no_snapshot(self, rm):
        result = rm.cold_boot()
        phase = rm.get_phase(result)
        assert phase.name == "COLD_BOOT"
