"""Phase 39.4 Acceptance Tests: R39-401 ~ R39-408.

验证 Cognitive Recovery & Continuity:
    R39-401: Snapshot Creation — 运行状态可保存
    R39-402: Runtime Restore — 重启恢复状态
    R39-403: Goal Continuity — Goal 不丢失
    R39-404: Execution Recovery — 避免重复执行
    R39-405: Permission Recovery — 审批状态恢复
    R39-406: Event Replay — 事件可重放
    R39-407: Integrity Check — 恢复前状态验证
    R39-408: Crash Simulation — 模拟异常恢复 (end-to-end)
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from ocos.runtime.recovery import (
    CognitiveStateRestore,
    EventLog,
    EventReplayEngine,
    EventType,
    ExecutionLedger,
    ExecutionStatus,
    ApprovalStore,
    ApprovalStatus,
    IntegrityReport,
    IntegrityVerifier,
    RecoveryManager,
    RestoreResult,
    RuntimeSnapshot,
    SnapshotReason,
    SnapshotStore,
)
from ocos.runtime.runtime_state import RuntimeState


# ── helpers ──

@pytest.fixture
def temp_data_dir():
    with tempfile.TemporaryDirectory() as tmp:
        yield Path(tmp)


# ═══════════════════════════════════════════════════════════════════════════
# R39-401: Snapshot Creation
# ═══════════════════════════════════════════════════════════════════════════

class TestR39401SnapshotCreation:
    """R39-401: 运行状态可保存为快照，可加载。"""

    def test_capture_and_serialize(self):
        snap = RuntimeSnapshot.capture(
            tick_id=500,
            runtime_state="RUNNING",
            active_goal_ids=("g-1", "g-2"),
            attention_focus={"target": "cache_design"},
            working_memory_keys=("kv:cache:1",),
            reason=SnapshotReason.PERIODIC,
        )
        d = snap.to_dict()
        assert d["tick_id"] == 500
        assert d["runtime_state"] == "RUNNING"
        assert d["reason"] == "periodic"
        assert json.dumps(d)  # serializable

    def test_snapshot_store_save_load(self, temp_data_dir):
        store = SnapshotStore(temp_data_dir)
        snap = RuntimeSnapshot.capture(
            tick_id=42, runtime_state="RUNNING",
            active_goal_ids=("goal_a",),
        )
        store.save(snap)

        loaded = store.latest()
        assert loaded is not None
        assert loaded.snapshot_id == snap.snapshot_id
        assert loaded.tick_id == 42
        assert loaded.active_goal_ids == ("goal_a",)

    def test_snapshot_store_latest(self, temp_data_dir):
        store = SnapshotStore(temp_data_dir, max_snapshots=3)
        for i in range(5):
            store.save(RuntimeSnapshot.capture(tick_id=i, runtime_state="RUNNING"))

        assert store.latest().tick_id == 4
        assert len(store.list_ids()) == 3  # pruned to 3


# ═══════════════════════════════════════════════════════════════════════════
# R39-402: Runtime Restore
# ═══════════════════════════════════════════════════════════════════════════

class TestR39402RuntimeRestore:
    """R39-402: 重启后从快照恢复状态。"""

    def test_cold_start_no_snapshot(self, temp_data_dir):
        store = SnapshotStore(temp_data_dir)
        restorer = CognitiveStateRestore(store)
        result = restorer.restore()
        assert result.success
        assert result.resume_tick == 0
        assert "cold start" in result.warnings[0].lower() if result.warnings else True

    def test_warm_restore_from_snapshot(self, temp_data_dir):
        store = SnapshotStore(temp_data_dir)
        store.save(RuntimeSnapshot.capture(
            tick_id=500, runtime_state="RUNNING",
            active_goal_ids=("goal_1", "goal_2"),
            attention_focus={"target": "db_optimization"},
            pending_executions=("exec-1",),
            pending_approvals=("appr-1",),
            event_log_cursor=10,
        ))

        restorer = CognitiveStateRestore(store)
        result = restorer.restore()

        assert result.success
        assert result.snapshot_id is not None
        assert result.resume_tick == 501
        assert result.active_goal_ids == ("goal_1", "goal_2")
        assert result.attention_focus == {"target": "db_optimization"}
        assert result.pending_executions == ("exec-1",)
        assert result.pending_approvals == ("appr-1",)
        assert result.event_cursor == 10

    def test_recovery_manager_start_cold(self, temp_data_dir):
        mgr = RecoveryManager(temp_data_dir)
        result = mgr.start()
        assert result.success
        assert result.resume_tick == 0

    def test_recovery_manager_start_warm(self, temp_data_dir):
        mgr = RecoveryManager(temp_data_dir)
        mgr.take_snapshot(tick_id=100, active_goal_ids=("g-1",),
                          runtime_state="RUNNING")

        # 模拟重启 → 新 RecoveryManager
        mgr2 = RecoveryManager(temp_data_dir)
        result = mgr2.start()
        assert result.success
        assert result.resume_tick == 101
        assert result.active_goal_ids == ("g-1",)


# ═══════════════════════════════════════════════════════════════════════════
# R39-403: Goal Continuity
# ═══════════════════════════════════════════════════════════════════════════

class TestR39403GoalContinuity:
    """R39-403: Goal 在快照前后不丢失。"""

    def test_goals_preserved_across_snapshot_roundtrip(self, temp_data_dir):
        mgr = RecoveryManager(temp_data_dir)

        # 运行: 2 个活跃 Goal
        mgr.take_snapshot(tick_id=500, active_goal_ids=("goal_a", "goal_b"),
                          runtime_state="RUNNING")

        # 重启
        mgr2 = RecoveryManager(temp_data_dir)
        result = mgr2.start()
        assert result.active_goal_ids == ("goal_a", "goal_b")

    def test_empty_goals_still_valid(self, temp_data_dir):
        mgr = RecoveryManager(temp_data_dir)
        mgr.take_snapshot(tick_id=10, active_goal_ids=(),
                          runtime_state="RUNNING")

        mgr2 = RecoveryManager(temp_data_dir)
        result = mgr2.start()
        assert result.active_goal_ids == ()


# ═══════════════════════════════════════════════════════════════════════════
# R39-404: Execution Recovery
# ═══════════════════════════════════════════════════════════════════════════

class TestR39404ExecutionRecovery:
    """R39-404: 执行账本防止重复执行。"""

    def test_record_success_then_skip(self):
        ledger = ExecutionLedger()
        ledger.record_start("exec-1", "file.download", "download", "/tmp/x")
        ledger.record_success("exec-1", tick_id=100, summary="ok")

        # 已完成 → skip
        assert ledger.should_skip("exec-1") is True

    def test_running_on_crash_becomes_unknown(self):
        ledger = ExecutionLedger()
        ledger.record_start("exec-2", "agent.invoke", "invoke")

        # 崩溃恢复
        resolved = ledger.resolve_on_recovery()
        assert resolved["exec-2"] == ExecutionStatus.UNKNOWN
        assert not ledger.should_skip("exec-2")  # unknown ≠ skip

    def test_recovery_manager_tracks_execution(self, temp_data_dir):
        mgr = RecoveryManager(temp_data_dir)
        rec = mgr.track_execution_start("e1", "api.call", "call", tick_id=50)
        assert rec.status == ExecutionStatus.RUNNING
        assert rec.tick_started == 50

        mgr.track_execution_success("e1", tick_id=60, summary="done")
        assert mgr.should_skip_execution("e1") is True

    def test_unknown_after_recovery_not_skipped(self, temp_data_dir):
        mgr = RecoveryManager(temp_data_dir)
        mgr.track_execution_start("e3", "agent.run", "run", tick_id=100)
        # 不解算 → 模拟崩溃
        unresolved = mgr.ledger.get_unresolved()
        assert len(unresolved) == 1
        assert not mgr.should_skip_execution("e3")


# ═══════════════════════════════════════════════════════════════════════════
# R39-405: Permission Recovery
# ═══════════════════════════════════════════════════════════════════════════

class TestR39405PermissionRecovery:
    """R39-405: 审批状态在重启后恢复。"""

    def test_add_and_restore_approval(self, temp_data_dir):
        store = ApprovalStore(temp_data_dir)
        a = store.add("file.write", "write", "/tmp/test.py", tick_id=42)
        assert a.status == ApprovalStatus.WAITING

        # 模拟重启
        store2 = ApprovalStore(temp_data_dir)
        waiting = store2.get_waiting()
        assert len(waiting) == 1
        assert waiting[0].capability_id == "file.write"
        assert waiting[0].approval_id == a.approval_id

    def test_approve_then_cleanup(self, temp_data_dir):
        store = ApprovalStore(temp_data_dir)
        a = store.add("agent.invoke", "invoke", tick_id=10)
        store.approve(a.approval_id)
        assert store.count_waiting() == 0

        # 重启后
        store2 = ApprovalStore(temp_data_dir)
        assert store2.count_waiting() == 0

    def test_recovery_manager_approvals(self, temp_data_dir):
        mgr = RecoveryManager(temp_data_dir)
        mgr.request_approval("file.write", "write", "/tmp/x", tick_id=5)
        assert mgr.pending_approvals_count() == 1

        mgr2 = RecoveryManager(temp_data_dir)
        assert mgr2.pending_approvals_count() == 1


# ═══════════════════════════════════════════════════════════════════════════
# R39-406: Event Replay
# ═══════════════════════════════════════════════════════════════════════════

class TestR39406EventReplay:
    """R39-406: 事件可追加、可重放、可重建状态。"""

    def test_event_append_and_replay(self, temp_data_dir):
        log = EventLog(temp_data_dir)
        log.append(EventType.GOAL_CREATED, tick_id=1, payload={"goal_id": "g-1"})
        log.append(EventType.TASK_DECOMPOSED, tick_id=2, payload={"goal_id": "g-1", "tasks": 3})
        log.append(EventType.AGENT_COMPLETED, tick_id=3, payload={"agent": "codex", "ok": True})

        events = log.replay_all()
        assert len(events) == 3
        assert events[0].event_type == "goal_created"
        assert events[0].seq == 1
        assert events[2].seq == 3

    def test_replay_from_cursor(self, temp_data_dir):
        log = EventLog(temp_data_dir)
        for i in range(10):
            log.append(EventType.GOAL_UPDATED, tick_id=i, payload={"i": i})

        events = log.replay_from(from_seq=6)
        assert len(events) == 5
        assert events[0].seq == 6

    def test_event_replay_engine_rebuilds_state(self, temp_data_dir):
        log = EventLog(temp_data_dir)
        log.append(EventType.GOAL_CREATED, tick_id=1, payload={"goal_id": "g-1"})
        log.append(EventType.GOAL_COMPLETED, tick_id=5, payload={"goal_id": "g-1"})

        engine = EventReplayEngine(log)

        def goal_handler(event, state):
            s = dict(state) if state else {}
            s[event.payload["goal_id"]] = event.event_type
            return s

        engine.register_handler(EventType.GOAL_CREATED, goal_handler, "goals")
        engine.register_handler(EventType.GOAL_COMPLETED, goal_handler, "goals")

        state = engine.rebuild_state()
        assert state["goals"]["g-1"] == "goal_completed"
        assert state["replay_cursor"] == 2
        assert state["events_processed"] == 2

    def test_recovery_manager_event_logging(self, temp_data_dir):
        mgr = RecoveryManager(temp_data_dir)
        mgr.log_event(EventType.GOAL_CREATED, tick_id=1, payload={"id": "g-1"})
        mgr.log_event(EventType.AGENT_COMPLETED, tick_id=2, payload={"agent": "x"})

        events = mgr.replay_events()
        assert len(events) == 2


# ═══════════════════════════════════════════════════════════════════════════
# R39-407: Integrity Check
# ═══════════════════════════════════════════════════════════════════════════

class TestR39407IntegrityCheck:
    """R39-407: 恢复前状态一致性验证。"""

    def test_empty_state_passes(self, temp_data_dir):
        events = EventLog(temp_data_dir)
        ledger = ExecutionLedger()
        approvals = ApprovalStore(temp_data_dir)
        verifier = IntegrityVerifier(events, ledger, approvals)

        snap = RuntimeSnapshot.capture(tick_id=10, runtime_state="RUNNING")
        report = verifier.verify(snap)
        assert report.passed

    def test_tick_cannot_regress(self, temp_data_dir):
        events = EventLog(temp_data_dir)
        for i in range(20):
            events.append(EventType.GOAL_UPDATED, tick_id=i, payload={})

        verifier = IntegrityVerifier(events)
        snap = RuntimeSnapshot.capture(tick_id=5, runtime_state="RUNNING")
        report = verifier.verify(snap)
        assert not report.passed
        assert any("tick_continuity" in c["name"] for c in report.violations)

    def test_missing_execution_detected(self):
        ledger = ExecutionLedger()
        # 不记录 "exec-999" → 应该检测到缺失
        verifier = IntegrityVerifier(execution_ledger=ledger)
        snap = RuntimeSnapshot.capture(
            tick_id=10, runtime_state="RUNNING",
            pending_executions=("exec-999",),
        )
        report = verifier.verify(snap)
        assert not report.passed
        assert any("execution_consistency" in c["name"] for c in report.violations)

    def test_missing_approval_detected(self, temp_data_dir):
        approvals = ApprovalStore(temp_data_dir)
        verifier = IntegrityVerifier(approval_store=approvals)
        snap = RuntimeSnapshot.capture(
            tick_id=10, runtime_state="RUNNING",
            pending_approvals=("missing-appr",),
        )
        report = verifier.verify(snap)
        assert not report.passed
        assert any("approval_consistency" in c["name"] for c in report.violations)

    def test_matching_state_passes(self, temp_data_dir):
        events = EventLog(temp_data_dir)
        events.append(EventType.GOAL_CREATED, tick_id=1, payload={"goal_id": "g-1"})

        ledger = ExecutionLedger()
        ledger.record_start("exec-1", "api.call", "call")
        ledger.record_success("exec-1", tick_id=2)

        approvals = ApprovalStore(temp_data_dir)
        approvals.add("file.write", "write", tick_id=1)

        verifier = IntegrityVerifier(events, ledger, approvals)
        snap = RuntimeSnapshot.capture(
            tick_id=2, runtime_state="RUNNING",
            pending_executions=("exec-1",),
            pending_approvals=(),
            event_log_cursor=1,
        )

        report = verifier.verify(snap)
        # execution-1 exists → OK; approvals empty → OK
        assert report.passed


# ═══════════════════════════════════════════════════════════════════════════
# R39-408: Crash Simulation
# ═══════════════════════════════════════════════════════════════════════════

class TestR39408CrashSimulation:
    """R39-408: 模拟异常恢复 — 端到端。"""

    def test_simulate_crash_and_recover(self, temp_data_dir):
        """完整流程: 运行 → 快照 → 崩溃 → 恢复 → 继续。"""
        # 第一阶段: 运行
        mgr = RecoveryManager(temp_data_dir)

        # Goal 活跃中
        mgr.take_snapshot(tick_id=500, runtime_state="RUNNING",
                          active_goal_ids=("goal_optimize_db", "goal_design_cache"))

        # 执行中
        mgr.track_execution_start("exec-1", "file.write", "write", "/tmp/config")
        mgr.track_execution_start("exec-2", "agent.invoke", "invoke")
        mgr.track_execution_success("exec-1", tick_id=500, summary="config written")
        # exec-2 仍在 RUNNING → 崩溃

        # 审批等待中
        mgr.request_approval("shell.execute", "run", "deploy.sh", tick_id=500)

        # 事件日志
        mgr.log_event(EventType.GOAL_CREATED, tick_id=1, payload={"goal": "goal_optimize_db"})
        mgr.log_event(EventType.AGENT_INVOKED, tick_id=100, payload={"agent": "codex"})

        # 最终快照 (模拟 shutdown / crash)
        mgr.shutdown(tick_id=500, runtime_state="SHUTDOWN",
                     active_goal_ids=("goal_optimize_db", "goal_design_cache"))

        # ── 第二阶段: 恢复 ──
        mgr2 = RecoveryManager(temp_data_dir)
        result = mgr2.start()

        # 基本恢复
        assert result.success
        assert result.resume_tick == 501

        # Goal 连续性
        assert result.active_goal_ids == ("goal_optimize_db", "goal_design_cache")

        # 执行恢复: exec-1 已完成 → 不在 pending
        assert mgr2.should_skip_execution("exec-1") is True
        # exec-2 未完成 → RUNNING→UNKNOWN
        rec = mgr2.ledger.get("exec-2")
        assert rec is not None
        assert rec.status == ExecutionStatus.UNKNOWN

        # 审批恢复
        assert mgr2.pending_approvals_count() == 1

        # 事件日志可重放
        events = mgr2.replay_events()
        assert len(events) == 2
        assert events[0].event_type == "goal_created"

    def test_crash_mid_execution_no_duplicate(self, temp_data_dir):
        """验证已完成任务不会重复执行。"""
        mgr = RecoveryManager(temp_data_dir)
        mgr.track_execution_start("unique-download", "file.download", "download", "/tmp/big")
        mgr.track_execution_success("unique-download", tick_id=100)
        mgr.take_snapshot(tick_id=100, runtime_state="RUNNING",
                          pending_executions=("unique-download",))

        # 恢复
        mgr2 = RecoveryManager(temp_data_dir)
        mgr2.start()

        # 已完成 → skip
        assert mgr2.should_skip_execution("unique-download") is True

    def test_cold_start_after_crash_no_recovery(self, temp_data_dir):
        """没有快照 → 冷启动。"""
        mgr = RecoveryManager(temp_data_dir)
        result = mgr.start()
        assert result.success
        assert result.resume_tick == 0
