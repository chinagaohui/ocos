"""Phase 51.1: Persistent Cognitive Storage — Tests.

测试完整持久化链路:
    - 类型系统
    - 序列化/反序列化 + 文件往返
    - 快照采集/保存/加载
    - 冷启动恢复 (完整/部分/无快照)
    - 生命周期 (Cold→Warm→Run→Shutdown→Recover)
    - 校验与往返一致性
    - 跨 session 语义 (Day1 work → Shutdown → Day7 recover)

边界:
    PS51-01: Snapshot ≠ Live State — take 不修改运行时
    PS51-02: Restore ≠ Overwrite — set_state 是填充
    PS51-03: Partial Recovery OK
    PS51-04: Format Stable
"""

import json
import os
import tempfile
from pathlib import Path
import pytest

from ocos.persistence.storage_types import (
    SnapshotDomain, SnapshotStatus, LifecyclePhase, RecoveryOutcome,
    DomainSnapshot, Snapshot, Checkpoint, RecoveryState,
    LifecycleEvent, LifecycleLog,
)
from ocos.persistence.state_serializer import StateSerializer
from ocos.persistence.snapshot_manager import SnapshotManager, StateProvider
from ocos.persistence.recovery_manager import RecoveryManager
from ocos.persistence.lifecycle_manager import LifecycleManager
from ocos.persistence.persistence_validator import PersistenceValidator


# ═══════════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════════


class FakeProvider(StateProvider):
    """模拟状态提供者。"""
    def __init__(self, domain: SnapshotDomain):
        self.domain = domain
        self._state: dict = {"domain": domain.value, "data": f"state-of-{domain.value}"}

    def snapshot_domain(self) -> SnapshotDomain:
        return self.domain

    def get_state(self) -> dict:
        return dict(self._state)

    def set_state(self, data: dict) -> None:
        self._state.update(data)  # PS51-02: 填充，不覆盖


def make_providers():
    """创建四个域的模拟提供者。"""
    return [
        FakeProvider(SnapshotDomain.RUNTIME),
        FakeProvider(SnapshotDomain.COGNITIVE),
        FakeProvider(SnapshotDomain.MEMORY),
        FakeProvider(SnapshotDomain.WORLD),
    ]


def make_manager():
    """创建带四个域的快照管理器。"""
    sm = SnapshotManager(
        serializer=StateSerializer(
            storage_root=Path(tempfile.mkdtemp(prefix="ocos-test-"))
        ),
    )
    for p in make_providers():
        sm.register_provider(p)
    return sm


# ═══════════════════════════════════════════════════════════════════════════════
# 1. Types
# ═══════════════════════════════════════════════════════════════════════════════


class TestStorageTypes:
    def test_snapshot_domain_values(self):
        assert SnapshotDomain.RUNTIME.value == "runtime"
        assert SnapshotDomain.COGNITIVE.value == "cognitive"
        assert SnapshotDomain.MEMORY.value == "memory"
        assert SnapshotDomain.WORLD.value == "world"

    def test_snapshot_status_values(self):
        assert SnapshotStatus.TAKEN.value == "taken"
        assert SnapshotStatus.VALIDATED.value == "validated"
        assert SnapshotStatus.CORRUPT.value == "corrupt"
        assert SnapshotStatus.PARTIAL.value == "partial"

    def test_lifecycle_phases(self):
        assert LifecyclePhase.WARM_BOOT.value == "warm_boot"
        assert LifecyclePhase.DEGRADED.value == "degraded"

    def test_recovery_outcome(self):
        assert RecoveryOutcome.FULL.value == "full"
        assert RecoveryOutcome.PARTIAL.value == "partial"

    def test_snapshot_creation(self):
        s = Snapshot(snapshot_id="test-1", tick=100)
        assert s.snapshot_id == "test-1"
        assert s.tick == 100
        assert s.format_version == "1.0.0"
        assert s.domain_count == 0
        assert not s.is_complete

    def test_snapshot_complete(self):
        s = Snapshot(snapshot_id="test-2")
        for d in SnapshotDomain:
            s.domains[d.value] = DomainSnapshot(domain=d)
        assert s.is_complete
        assert s.domain_count == 4

    def test_domain_snapshot_defaults(self):
        ds = DomainSnapshot(domain=SnapshotDomain.RUNTIME)
        assert ds.tick == 0
        assert ds.timestamp == 0.0
        assert ds.data == {}
        assert ds.status == SnapshotStatus.TAKEN

    def test_checkpoint_creation(self):
        cp = Checkpoint(
            checkpoint_id="cp-1",
            parent_snapshot_id="snap-1",
            tick=100,
            changed_domains=[SnapshotDomain.MEMORY],
            delta={"updated": True},
            reason="tick"
        )
        assert cp.tick == 100
        assert len(cp.changed_domains) == 1

    def test_recovery_state_degraded(self):
        rs = RecoveryState(
            outcome=RecoveryOutcome.PARTIAL,
            recovered_domains=[SnapshotDomain.RUNTIME],
            failed_domains=[SnapshotDomain.MEMORY],
            warnings=["partial recovery"]
        )
        assert rs.is_degraded
        assert rs.is_partial

    def test_lifecycle_log(self):
        log = LifecycleLog()
        assert log.current_phase == LifecyclePhase.COLD_BOOT
        assert log.boot_count == 0


# ═══════════════════════════════════════════════════════════════════════════════
# 2. StateSerializer
# ═══════════════════════════════════════════════════════════════════════════════


class TestStateSerializer:
    def test_serialize_deserialize_roundtrip(self):
        ser = StateSerializer(storage_root=Path(tempfile.mkdtemp()))
        s = Snapshot(snapshot_id="snap-1", tick=42, timestamp=1000.0)
        s.domains["runtime"] = DomainSnapshot(
            domain=SnapshotDomain.RUNTIME, tick=42, data={"key": "val"},
        )

        raw = ser.serialize(s)
        restored = ser.deserialize(raw)

        assert restored.snapshot_id == "snap-1"
        assert restored.tick == 42
        assert restored.domains["runtime"].data["key"] == "val"

    def test_save_and_load(self):
        ser = StateSerializer(storage_root=Path(tempfile.mkdtemp()))
        s = Snapshot(snapshot_id="snap-x", tick=99)
        s.domains["runtime"] = DomainSnapshot(
            domain=SnapshotDomain.RUNTIME, data={"a": 1}
        )

        path = ser.save(s)
        assert path.exists()

        loaded = ser.load("snap-x")
        assert loaded is not None
        assert loaded.tick == 99
        assert loaded.domains["runtime"].data == {"a": 1}

    def test_load_nonexistent(self):
        ser = StateSerializer(storage_root=Path(tempfile.mkdtemp()))
        assert ser.load("nonexistent") is None

    def test_load_latest(self):
        ser = StateSerializer(storage_root=Path(tempfile.mkdtemp()))
        for i in range(5):
            s = Snapshot(snapshot_id=f"snap-{i}", tick=i * 10)
            for d in SnapshotDomain:
                s.domains[d.value] = DomainSnapshot(domain=d, data={"seq": i})
            ser.save(s)

        latest = ser.load_latest()
        assert latest is not None
        assert latest.tick == 40

    def test_list_snapshots(self):
        ser = StateSerializer(storage_root=Path(tempfile.mkdtemp()))
        s = Snapshot(snapshot_id="snap-list", tick=1)
        s.domains["runtime"] = DomainSnapshot(domain=SnapshotDomain.RUNTIME)
        ser.save(s)

        snaps = ser.list_snapshots()
        assert len(snaps) == 1

    def test_prune(self):
        ser = StateSerializer(storage_root=Path(tempfile.mkdtemp()))
        for i in range(20):
            s = Snapshot(snapshot_id=f"snap-{i}", tick=i)
            s.domains["runtime"] = DomainSnapshot(domain=SnapshotDomain.RUNTIME)
            ser.save(s)

        removed = ser.prune(keep=5)
        assert removed == 15
        remaining = ser.list_snapshots()
        assert len(remaining) == 5


# ═══════════════════════════════════════════════════════════════════════════════
# 3. SnapshotManager
# ═══════════════════════════════════════════════════════════════════════════════


class TestSnapshotManager:
    def test_take_full_snapshot(self):
        sm = make_manager()
        snap = sm.take(100)
        assert snap.is_complete
        assert snap.tick == 100
        assert snap.status == SnapshotStatus.VALIDATED
        for d in SnapshotDomain:
            assert d.value in snap.domains

    def test_take_and_save(self):
        sm = make_manager()
        snap = sm.take_and_save(200, "test")
        assert snap.is_complete
        assert snap.tick == 200

        # 验证文件存在
        saved = sm.serializer.load(snap.snapshot_id)
        assert saved is not None
        assert saved.tick == 200

    def test_restore_full(self):
        sm = make_manager()
        snap = sm.take(300)

        result = sm.restore(snap)
        assert result.outcome == RecoveryOutcome.FULL
        assert len(result.recovered_domains) == 4
        assert len(result.failed_domains) == 0
        assert result.tick_at_recovery == 300

    def test_restore_partial(self):
        """PS51-03: 部分恢复 — 有一个域没有 provider。"""
        sm = make_manager()
        # 移除一个 provider
        del sm.providers["memory"]
        snap = sm.take(400)
        snap.domains["memory"] = DomainSnapshot(
            domain=SnapshotDomain.MEMORY, data={"old": True}
        )

        result = sm.restore(snap)
        assert result.outcome == RecoveryOutcome.PARTIAL
        assert "memory" not in [d.value for d in result.recovered_domains]
        assert len(result.warnings) >= 1

    def test_ps51_01_snapshot_not_live(self):
        """PS51-01: take 是只读采集，不修改 provider 内部 state。"""
        sm = make_manager()
        provider = sm.providers["runtime"]
        original = provider.get_state()

        sm.take(500)

        # provider 状态不变
        assert provider.get_state() == original

    def test_ps51_02_restore_is_fill(self):
        """PS51-02: restore 填充数据，不覆盖已有字段。"""
        sm = make_manager()
        provider = sm.providers["runtime"]
        provider._state["existing"] = "keep-me"

        snap = sm.take(600)
        # set_state 通过 .update() 实现填充
        result = sm.restore(snap)
        assert result.outcome == RecoveryOutcome.FULL

        # existing 字段保留
        assert provider._state["existing"] == "keep-me"
        # 快照数据也注入
        assert provider._state["data"] == "state-of-runtime"

    def test_validate_corrupt(self):
        sm = make_manager()
        snap = sm.take(700)
        # 损坏一个域的数据
        snap.domains["runtime"].data["corrupted"] = True
        # 不更新 checksum → 校验失败

        valid = sm.validate(snap)
        assert not valid
        assert snap.domains["runtime"].status == SnapshotStatus.CORRUPT

    def test_load_and_restore_latest(self):
        sm = make_manager()
        snap = sm.take_and_save(800, "pre-boot")

        result = sm.load_and_restore()
        assert result.outcome == RecoveryOutcome.FULL
        assert result.tick_at_recovery == 800

    def test_load_and_restore_none(self):
        sm = make_manager()
        result = sm.load_and_restore()
        assert result.outcome == RecoveryOutcome.NO_SNAPSHOT


# ═══════════════════════════════════════════════════════════════════════════════
# 4. RecoveryManager
# ═══════════════════════════════════════════════════════════════════════════════


class TestRecoveryManager:
    def test_cold_boot_with_nothing(self):
        rm = RecoveryManager(snapshot_manager=make_manager())
        result = rm.cold_boot()
        assert result.outcome == RecoveryOutcome.NO_SNAPSHOT

    def test_cold_boot_with_snapshot(self):
        sm = make_manager()
        sm.take_and_save(100, "day1")
        rm = RecoveryManager(snapshot_manager=sm)

        result = rm.cold_boot()
        assert result.outcome == RecoveryOutcome.FULL
        assert result.tick_at_recovery == 100

    def test_day1_seven_day_recovery(self):
        """验收场景: Day 1: 开发股票系统 → Shutdown → Day 7: 恢复。"""
        sm = make_manager()

        # Day 1: 模拟工作
        sm.providers["runtime"]._state["current_goal"] = "开发股票分析系统"
        sm.providers["runtime"]._state["completed"] = ["数据库设计"]
        sm.providers["memory"]._state["experience"] = ["数据库选型讨论"]
        sm.providers["world"]._state["knowledge"] = {"stocks": "basic"}

        snap = sm.take_and_save(1500, "day1-shutdown")
        snap_paths = sm.serializer.list_snapshots()
        assert len(snap_paths) == 1

        # --- SHUTDOWN ---

        # Day 7: 冷启动恢复
        sm2 = make_manager()
        rm = RecoveryManager(snapshot_manager=sm2)
        # 复用同一个 serializer (storage root)
        sm2.serializer = sm.serializer

        result = rm.cold_boot()
        assert result.outcome == RecoveryOutcome.FULL
        assert result.tick_at_recovery == 1500

        # 状态恢复
        runtime = sm2.providers["runtime"]
        assert runtime._state.get("current_goal") == "开发股票分析系统"
        assert "数据库设计" in runtime._state.get("completed", [])
        assert sm2.providers["memory"]._state.get("experience") == ["数据库选型讨论"]
        assert sm2.providers["world"]._state.get("knowledge") == {"stocks": "basic"}

    def test_recovery_logging(self):
        sm = make_manager()
        sm.take_and_save(10)
        rm = RecoveryManager(snapshot_manager=sm)

        rm.cold_boot()
        assert len(rm.recovery_log) == 1

    def test_get_phase_warm(self):
        rm = RecoveryManager(snapshot_manager=make_manager())
        rs = RecoveryState(outcome=RecoveryOutcome.FULL)
        assert rm.get_phase(rs) == LifecyclePhase.WARM_BOOT

    def test_get_phase_degraded(self):
        rm = RecoveryManager(snapshot_manager=make_manager())
        rs = RecoveryState(outcome=RecoveryOutcome.PARTIAL)
        assert rm.get_phase(rs) == LifecyclePhase.DEGRADED


# ═══════════════════════════════════════════════════════════════════════════════
# 5. LifecycleManager
# ═══════════════════════════════════════════════════════════════════════════════


class TestLifecycleManager:
    def test_cold_boot(self):
        sm = make_manager()
        lm = LifecycleManager(
            snapshot_manager=sm,
            recovery_manager=RecoveryManager(snapshot_manager=sm),
        )
        result = lm.boot()
        assert result.outcome == RecoveryOutcome.NO_SNAPSHOT
        assert lm.current_phase == LifecyclePhase.COLD_BOOT

    def test_warm_boot(self):
        sm = make_manager()
        sm.take_and_save(50, "pre")
        lm = LifecycleManager(
            snapshot_manager=sm,
            recovery_manager=RecoveryManager(snapshot_manager=sm),
        )
        result = lm.boot()
        assert lm.current_phase == LifecyclePhase.WARM_BOOT
        assert result.tick_at_recovery == 50

    def test_full_lifecycle(self):
        """完整生命周期: Cold → Running → Checkpoint → Shutdown → Warm Boot。"""
        sm = make_manager()
        rm = RecoveryManager(snapshot_manager=sm)
        lm = LifecycleManager(snapshot_manager=sm, recovery_manager=rm)

        # Cold boot
        result = lm.boot()
        assert lm.current_phase == LifecyclePhase.COLD_BOOT
        assert lm.log.boot_count == 0

        # 进入运行
        tick_count = [0]
        def tick():
            tick_count[0] += 1
            lm.current_tick = tick_count[0]

        lm.run(tick)
        assert lm.current_phase == LifecyclePhase.RUNNING

        # 几次 tick
        for _ in range(5):
            tick()

        # Checkpoint
        snap = lm.checkpoint("hourly")
        assert snap is not None
        assert snap.is_complete

        # Shutdown
        final = lm.shutdown("end of day")
        assert final is not None
        assert lm.current_phase == LifecyclePhase.SHUTTING_DOWN

        # --- 重新启动 ---
        sm2 = make_manager()
        sm2.serializer = sm.serializer  # 复用存储
        rm2 = RecoveryManager(snapshot_manager=sm2)
        lm2 = LifecycleManager(snapshot_manager=sm2, recovery_manager=rm2)

        result2 = lm2.boot()
        assert lm2.current_phase == LifecyclePhase.WARM_BOOT
        assert lm2.log.boot_count == 1

    def test_shutdown_saves(self):
        sm = make_manager()
        rm = RecoveryManager(snapshot_manager=sm)
        lm = LifecycleManager(snapshot_manager=sm, recovery_manager=rm)
        lm.boot()

        snap = lm.shutdown("test")
        assert snap is not None
        assert snap.is_complete

        # 确认文件存在
        loaded = sm.serializer.load(snap.snapshot_id)
        assert loaded is not None

    def test_degraded_mode(self):
        """PS51-03: 部分域恢复 → DEGRADED 模式。"""
        sm = make_manager()
        # 移除 memory provider → 恢复时该域失败
        del sm.providers["memory"]
        # take 只会采集已注册的 domain (runtime, cognitive, world)
        # 手动添加一个无 provider 的 memory domain
        snap = sm.take(100)
        snap.domains["memory"] = DomainSnapshot(
            domain=SnapshotDomain.MEMORY, data={"old": True}
        )
        # 不是完整的 4 域快照但是手动加了 memory

        result = sm.restore(snap)
        assert result.outcome == RecoveryOutcome.PARTIAL
        assert len(result.failed_domains) == 1
        assert result.failed_domains[0] == SnapshotDomain.MEMORY
        assert len(result.recovered_domains) == 3

    def test_health_properties(self):
        sm = make_manager()
        lm = LifecycleManager(
            snapshot_manager=sm,
            recovery_manager=RecoveryManager(snapshot_manager=sm),
        )
        lm.boot()
        assert not lm.is_healthy  # COLD_BOOT

        lm.current_phase = LifecyclePhase.RUNNING
        assert lm.is_healthy
        assert not lm.is_degraded

        lm.current_phase = LifecyclePhase.DEGRADED
        assert lm.is_degraded
        assert not lm.is_healthy

    def test_lifecycle_log(self):
        sm = make_manager()
        lm = LifecycleManager(
            snapshot_manager=sm,
            recovery_manager=RecoveryManager(snapshot_manager=sm),
        )
        lm.boot()
        assert len(lm.log.events) > 0
        assert lm.log.events[0].phase == LifecyclePhase.COLD_BOOT


# ═══════════════════════════════════════════════════════════════════════════════
# 6. PersistenceValidator
# ═══════════════════════════════════════════════════════════════════════════════


class TestPersistenceValidator:
    def test_valid_snapshot(self):
        sm = make_manager()
        snap = sm.take(100)
        pv = PersistenceValidator(snapshot_manager=sm)

        report = pv.validate_snapshot(snap)
        assert report["is_valid"]
        assert snap.status == SnapshotStatus.VALIDATED

    def test_missing_format_version(self):
        sm = make_manager()
        snap = sm.take(100)
        snap.format_version = ""
        pv = PersistenceValidator(snapshot_manager=sm)

        report = pv.validate_snapshot(snap)
        assert not report["is_valid"]
        assert "Missing format_version" in report["issues"]

    def test_missing_id(self):
        sm = make_manager()
        snap = sm.take(100)
        snap.snapshot_id = ""
        pv = PersistenceValidator(snapshot_manager=sm)

        report = pv.validate_snapshot(snap)
        assert not report["is_valid"]

    def test_roundtrip_verify(self):
        sm = make_manager()
        snap = sm.take(100)
        pv = PersistenceValidator(snapshot_manager=sm)
        assert pv.roundtrip_verify(snap)

    def test_old_format_warning(self):
        sm = make_manager()
        snap = sm.take(100)
        snap.format_version = "0.9.0"
        pv = PersistenceValidator(snapshot_manager=sm)

        report = pv.validate_snapshot(snap)
        assert report["is_valid"]
        assert any("older" in w for w in report["warnings"])


# ═══════════════════════════════════════════════════════════════════════════════
# 7. Integration: 跨 session 持续存在
# ═══════════════════════════════════════════════════════════════════════════════


class TestPersistenceIntegration:
    def test_multi_session_persistence(self):
        """多 session 持续存在测试。

        Session 1: 工作 + checkpoint + shutdown
        Session 2: cold boot → 恢复状态
        Session 3: cold boot → 恢复状态
        验证: 状态跨三次 session 持续存在。
        """
        # Session 1: 工作和保存
        sm = make_manager()
        storage = sm.serializer
        storage_root = sm.serializer.storage_root

        sm.providers["runtime"]._state.update({
            "current_goal": "开发股票系统",
            "completed": ["数据库设计", "缓存架构"],
        })
        sm.providers["memory"]._state["wisdom"] = ["缓存优先于数据库"]

        snap = sm.take_and_save(3000, "session1-shutdown")
        assert snap.is_complete

        # Session 2: 恢复
        sm2 = SnapshotManager(
            serializer=StateSerializer(storage_root=storage_root),
        )
        for p in make_providers():
            sm2.register_provider(p)

        rm2 = RecoveryManager(snapshot_manager=sm2)
        r2 = rm2.cold_boot()
        assert r2.outcome == RecoveryOutcome.FULL
        assert sm2.providers["runtime"]._state["current_goal"] == "开发股票系统"

        # Session 3: 恢复
        sm3 = SnapshotManager(
            serializer=StateSerializer(storage_root=storage_root),
        )
        for p in make_providers():
            sm3.register_provider(p)

        r3 = RecoveryManager(snapshot_manager=sm3).cold_boot()
        assert r3.outcome == RecoveryOutcome.FULL
        assert len(sm3.providers["runtime"]._state["completed"]) == 2
        assert "缓存优先于数据库" in str(sm3.providers["memory"]._state.get("wisdom", ""))
