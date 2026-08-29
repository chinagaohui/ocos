"""Phase 39.4: Cognitive State Restore — 认知状态恢复流程。

完整启动序列:
    BOOT → Load Snapshot → Verify Integrity → Restore State → Resume Tick

恢复项目:
    - Goal 连续性: active_goal_ids
    - Attention 连续性: attention_focus
    - Working Memory 连续性: working_memory_keys
    - Execution 连续性: pending_executions → recovery
    - Permission 连续性: pending_approvals → restore
    - Event Log 连续性: from_cursor → resume

关键: 状态恢复不是简单的值复制，而是重建"此刻的认知矢量"。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .event_replay import EventLog, EventReplayEngine
from .execution_recovery import ExecutionLedger, ExecutionStatus
from .integrity_verifier import IntegrityReport, IntegrityVerifier
from .permission_recovery import ApprovalStore, ApprovalStatus, PendingApproval
from .runtime_snapshot import RuntimeSnapshot, SnapshotStore


@dataclass
class RestoreResult:
    """认知状态恢复结果。"""

    success: bool
    snapshot_id: str | None = None
    resume_tick: int = 0
    active_goal_ids: tuple[str, ...] = ()
    attention_focus: dict[str, Any] = field(default_factory=dict)
    pending_executions: tuple[str, ...] = ()
    pending_approvals: tuple[str, ...] = ()
    event_cursor: int = 0
    integrity_report: IntegrityReport | None = None
    warnings: list[str] = field(default_factory=list)

    def summary(self) -> str:
        if self.success:
            return (
                f"Restore OK @ tick {self.resume_tick}, "
                f"{len(self.active_goal_ids)} goals, "
                f"{len(self.pending_executions)} pending executions, "
                f"{len(self.pending_approvals)} pending approvals"
            )
        return "Restore FAILED"


class CognitiveStateRestore:
    """认知状态恢复引擎。

    用法:
        restorer = CognitiveStateRestore(snapshot_store, event_log, ledger, approvals)
        result = restorer.restore()

    BOOT → Load → Verify → Restore → Resume
    """

    def __init__(
        self,
        snapshot_store: SnapshotStore,
        event_log: EventLog | None = None,
        execution_ledger: ExecutionLedger | None = None,
        approval_store: ApprovalStore | None = None,
    ):
        self._snapshots = snapshot_store
        self._events = event_log
        self._ledger = execution_ledger
        self._approvals = approval_store
        self._verifier = IntegrityVerifier(event_log, execution_ledger, approval_store)

    def restore(self, strict: bool = False) -> RestoreResult:
        """执行完整恢复流程。"""
        warnings: list[str] = []

        # Step 1: Load latest snapshot
        snapshot = self._snapshots.latest()
        if snapshot is None:
            return RestoreResult(
                success=True,
                resume_tick=0,
                warnings=["no snapshot found — cold start"],
            )

        # Step 2: Verify integrity
        report = self._verifier.verify(snapshot, strict=strict)
        if not report.passed and strict:
            return RestoreResult(
                success=False,
                snapshot_id=snapshot.snapshot_id,
                integrity_report=report,
                warnings=[v["detail"] for v in report.violations],
            )
        if not report.passed:
            warnings.extend(
                f"[integrity] {v['name']}: {v['detail']}"
                for v in report.violations
            )

        # Step 3: Restore cognitive state
        attention_focus = snapshot.attention_focus
        active_goal_ids = snapshot.active_goal_ids

        # Step 4: Resolve execution state
        pending_executions = self._restore_executions(snapshot, warnings)

        # Step 5: Restore pending approvals
        pending_approvals = self._restore_approvals(snapshot, warnings)

        # Step 6: Compute resume tick
        resume_tick = snapshot.tick_id + 1

        return RestoreResult(
            success=True,
            snapshot_id=snapshot.snapshot_id,
            resume_tick=resume_tick,
            active_goal_ids=active_goal_ids,
            attention_focus=attention_focus,
            pending_executions=pending_executions,
            pending_approvals=pending_approvals,
            event_cursor=snapshot.event_log_cursor,
            integrity_report=report,
            warnings=warnings,
        )

    def _restore_executions(
        self, snapshot: RuntimeSnapshot, warnings: list[str]
    ) -> tuple[str, ...]:
        """恢复执行状态。RUNNING→UNKNOWN, 已完成→skip。"""
        if not self._ledger or not snapshot.pending_executions:
            return snapshot.pending_executions

        unresolved = self._ledger.resolve_on_recovery()
        for exec_id, status in unresolved.items():
            if status == ExecutionStatus.UNKNOWN:
                warnings.append(f"execution {exec_id}: status UNKNOWN — needs manual check")
            elif status == ExecutionStatus.SUCCESS:
                warnings.append(f"execution {exec_id}: already completed — skipping")

        # 返回仍需要处理的执行
        still_pending: list[str] = []
        for exec_id in snapshot.pending_executions:
            if not self._ledger.should_skip(exec_id):
                still_pending.append(exec_id)

        return tuple(still_pending)

    def _restore_approvals(
        self, snapshot: RuntimeSnapshot, warnings: list[str]
    ) -> tuple[str, ...]:
        """恢复审批状态。WAITING → 继续等待。"""
        if not self._approvals or not snapshot.pending_approvals:
            return snapshot.pending_approvals

        waiting = self._approvals.get_waiting()
        still_waiting: list[str] = []
        for aid in snapshot.pending_approvals:
            approval = self._approvals.get(aid)
            if approval is None:
                warnings.append(f"approval {aid}: not found in store — dropped")
            elif approval.status == ApprovalStatus.WAITING:
                still_waiting.append(aid)
            elif approval.status == ApprovalStatus.APPROVED:
                warnings.append(f"approval {aid}: was approved — cleanup")
            elif approval.status == ApprovalStatus.DENIED:
                warnings.append(f"approval {aid}: was denied — cleanup")

        return tuple(still_waiting)
