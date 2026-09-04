"""OCOS persistence storage_types 不变式测试。

PS51-01: Snapshot ≠ Live State
PS51-02: Restore ≠ Overwrite
PS51-03: Partial Recovery OK
PS51-04: Storage Format Stable
"""

import pytest

from ocos.persistence.storage_types import (
    SnapshotDomain,
    SnapshotStatus,
    LifecyclePhase,
    RecoveryOutcome,
    DomainSnapshot,
    Snapshot,
    Checkpoint,
    RecoveryState,
    LifecycleEvent,
    LifecycleLog,
)


class TestSnapshotDomain:
    def test_four_domains(self):
        vals = {d.value for d in SnapshotDomain}
        assert vals == {"runtime", "cognitive", "memory", "world"}


class TestSnapshotStatus:
    def test_all_statuses(self):
        vals = {s.value for s in SnapshotStatus}
        expected = {"taken", "validated", "corrupt", "expired",
                    "restoring", "restored", "partial"}
        assert vals == expected


class TestLifecyclePhase:
    def test_all_phases(self):
        vals = {p.value for p in LifecyclePhase}
        expected = {"cold_boot", "warm_boot", "running",
                    "checkpointing", "degraded", "shutting_down", "crashed"}
        assert vals == expected


class TestRecoveryOutcome:
    def test_all_outcomes(self):
        vals = {o.value for o in RecoveryOutcome}
        assert vals == {"full", "partial", "failed", "no_snapshot"}


class TestDomainSnapshot:
    def test_defaults(self):
        ds = DomainSnapshot()
        assert ds.domain == SnapshotDomain.RUNTIME
        assert ds.tick == 0
        assert ds.timestamp == 0.0
        assert ds.data == {}
        assert ds.checksum == ""
        assert ds.status == SnapshotStatus.TAKEN

    def test_custom(self):
        ds = DomainSnapshot(
            domain=SnapshotDomain.WORLD,
            tick=42,
            timestamp=123.0,
            data={"key": "value"},
            checksum="abc123",
            status=SnapshotStatus.VALIDATED,
        )
        assert ds.domain == SnapshotDomain.WORLD
        assert ds.tick == 42
        assert ds.data == {"key": "value"}


class TestSnapshot:
    def test_empty_snapshot(self):
        s = Snapshot()
        assert s.snapshot_id == ""
        assert s.format_version == "1.0.0"
        assert s.domain_count == 0
        assert s.is_complete is False
        assert s.domain(SnapshotDomain.RUNTIME) is None

    def test_complete_snapshot(self):
        s = Snapshot(
            snapshot_id="snap-001",
            domains={
                d.value: DomainSnapshot(domain=d, tick=1, data={})
                for d in SnapshotDomain
            },
        )
        assert s.domain_count == 4
        assert s.is_complete is True

    def test_domain_retrieval(self):
        runtime_ds = DomainSnapshot(domain=SnapshotDomain.RUNTIME, tick=5)
        s = Snapshot(domains={"runtime": runtime_ds})
        assert s.domain(SnapshotDomain.RUNTIME) is runtime_ds
        assert s.domain(SnapshotDomain.MEMORY) is None

    def test_metadata_passthrough(self):
        s = Snapshot(metadata={"host": "test", "os": "linux"})
        assert s.metadata["host"] == "test"


class TestCheckpoint:
    def test_default(self):
        c = Checkpoint()
        assert c.tick == 0
        assert c.changed_domains == []
        assert c.delta == {}
        assert c.reason == ""

    def test_custom(self):
        c = Checkpoint(
            checkpoint_id="cp-001",
            parent_snapshot_id="snap-001",
            tick=100,
            changed_domains=[SnapshotDomain.RUNTIME],
            delta={"tick": 100},
            reason="tick",
        )
        assert c.tick == 100
        assert len(c.changed_domains) == 1
        assert c.reason == "tick"


class TestRecoveryState:
    def test_no_snapshot_outcome(self):
        rs = RecoveryState()
        assert rs.outcome == RecoveryOutcome.NO_SNAPSHOT
        assert rs.snapshot is None
        assert rs.is_partial is False
        assert rs.is_degraded is False

    def test_full_recovery(self):
        rs = RecoveryState(
            outcome=RecoveryOutcome.FULL,
            recovered_domains=[SnapshotDomain.RUNTIME, SnapshotDomain.MEMORY],
        )
        assert rs.is_partial is False
        assert rs.is_degraded is False

    def test_partial_recovery(self):
        rs = RecoveryState(
            outcome=RecoveryOutcome.PARTIAL,
            recovered_domains=[SnapshotDomain.RUNTIME],
            failed_domains=[SnapshotDomain.WORLD],
        )
        assert rs.is_partial is True
        assert rs.is_degraded is True

    def test_failed_recovery(self):
        rs = RecoveryState(outcome=RecoveryOutcome.FAILED)
        assert rs.is_partial is False
        assert rs.is_degraded is False


class TestLifecycleEvent:
    def test_defaults(self):
        e = LifecycleEvent()
        assert e.phase == LifecyclePhase.RUNNING
        assert e.tick == 0
        assert e.snapshot_id is None

    def test_custom(self):
        import time
        e = LifecycleEvent(
            event_id="LE-001",
            phase=LifecyclePhase.COLD_BOOT,
            timestamp=time.time(),
            tick=0,
            detail="initial boot",
            snapshot_id=None,
        )
        assert e.phase == LifecyclePhase.COLD_BOOT
        assert e.detail == "initial boot"


class TestLifecycleLog:
    def test_empty_log(self):
        log = LifecycleLog()
        assert log.events == []
        assert log.current_phase == LifecyclePhase.COLD_BOOT
        assert log.boot_count == 0
        assert log.total_uptime_ticks == 0

    def test_with_events(self):
        import time
        log = LifecycleLog(
            events=[
                LifecycleEvent(event_id="e1", phase=LifecyclePhase.COLD_BOOT,
                               timestamp=time.time()),
                LifecycleEvent(event_id="e2", phase=LifecyclePhase.RUNNING,
                               timestamp=time.time()),
            ],
            current_phase=LifecyclePhase.RUNNING,
            boot_count=1,
            total_uptime_ticks=100,
        )
        assert len(log.events) == 2
        assert log.boot_count == 1
        assert log.total_uptime_ticks == 100
