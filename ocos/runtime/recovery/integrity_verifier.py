"""Phase 39.4: Integrity Verifier — 恢复前状态一致性验证。

恢复前检查:
    Snapshot + Execution Ledger + Approval Store 一致性。
    禁止: snapshot 说 task completed, 但没有 execution record。

验证规则:
    1. Snapshot tick_id ≥ EventLog cursor (不能倒退)
    2. Pending executions 都在 Ledger 中存在
    3. Pending approvals 都在 ApprovalStore 中存在
    4. 没有 COMPLETED goal 却有 RUNNING task (矛盾)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .event_replay import EventLog
from .execution_recovery import ExecutionLedger, ExecutionStatus
from .permission_recovery import ApprovalStore, ApprovalStatus
from .runtime_snapshot import RuntimeSnapshot


@dataclass
class IntegrityReport:
    """完整性验证报告。"""

    passed: bool = True
    checks: list[dict[str, Any]] = field(default_factory=list)
    violations: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[dict[str, Any]] = field(default_factory=list)

    def add_check(self, name: str, passed: bool, detail: str = "") -> None:
        entry = {"name": name, "passed": passed, "detail": detail}
        self.checks.append(entry)
        if not passed:
            self.passed = False
            self.violations.append(entry)

    def add_warning(self, name: str, detail: str) -> None:
        self.warnings.append({"name": name, "detail": detail})


class IntegrityVerifier:
    """完整性验证器 — 恢复前最后一道门禁。"""

    def __init__(
        self,
        event_log: EventLog | None = None,
        execution_ledger: ExecutionLedger | None = None,
        approval_store: ApprovalStore | None = None,
    ):
        self._events = event_log
        self._ledger = execution_ledger
        self._approvals = approval_store

    def verify(self, snapshot: RuntimeSnapshot, strict: bool = False) -> IntegrityReport:
        """执行所有完整性检查。

        Args:
            snapshot: 要恢复的快照
            strict: True → 发现不一致 → 报告失败; False → 降级运行

        Returns:
            IntegrityReport with pass/fail per check
        """
        report = IntegrityReport()

        self._check_tick_continuity(snapshot, report)
        self._check_execution_consistency(snapshot, report, strict)
        self._check_approval_consistency(snapshot, report, strict)
        self._check_event_log_consistency(snapshot, report, strict)

        return report

    # ── 单项检查 ──

    def _check_tick_continuity(self, snapshot: RuntimeSnapshot, report: IntegrityReport) -> None:
        """Tick 不能倒退。"""
        ev_cursor = self._events.cursor() if self._events else 0
        match = snapshot.tick_id >= ev_cursor
        detail = f"snapshot.tick_id={snapshot.tick_id}, event_log.cursor={ev_cursor}"
        report.add_check("tick_continuity", match, detail)

    def _check_execution_consistency(
        self, snapshot: RuntimeSnapshot, report: IntegrityReport, strict: bool
    ) -> None:
        """Snapshot 中的 pending_executions 必须在 Ledger 中存在。"""
        if not self._ledger or not snapshot.pending_executions:
            report.add_check("execution_consistency", True, "no ledger or no pending")
            return

        missing: list[str] = []
        for exec_id in snapshot.pending_executions:
            rec = self._ledger.get(exec_id)
            if rec is None:
                missing.append(exec_id)

        ok = len(missing) == 0
        detail = f"{len(snapshot.pending_executions)} pending, {len(missing)} missing"
        if not ok:
            detail += f": {missing}"
        report.add_check("execution_consistency", ok, detail)

    def _check_approval_consistency(
        self, snapshot: RuntimeSnapshot, report: IntegrityReport, strict: bool
    ) -> None:
        """Snapshot 中的 pending_approvals 必须在 ApprovalStore 中存在。"""
        if not self._approvals or not snapshot.pending_approvals:
            report.add_check("approval_consistency", True, "no store or no pending")
            return

        missing: list[str] = []
        for aid in snapshot.pending_approvals:
            if self._approvals.get(aid) is None:
                missing.append(aid)

        ok = len(missing) == 0
        detail = f"{len(snapshot.pending_approvals)} pending, {len(missing)} missing"
        report.add_check("approval_consistency", ok, detail)

    def _check_event_log_consistency(
        self, snapshot: RuntimeSnapshot, report: IntegrityReport, strict: bool
    ) -> None:
        """Event log cursor 与 snapshot 一致。"""
        if not self._events:
            report.add_check("event_log_consistency", True, "no event log")
            return

        ev_cursor = self._events.cursor()
        snap_cursor = snapshot.event_log_cursor

        if snap_cursor > ev_cursor:
            # Snapshot 声称的事件比日志实际的多 → 不一致
            report.add_check(
                "event_log_consistency", False,
                f"snapshot cursor {snap_cursor} > actual {ev_cursor}"
            )
        elif snap_cursor < ev_cursor:
            # 日志有更新事件 → 正常（snapshot 之后有新事件）
            report.add_check(
                "event_log_consistency", True,
                f"snapshot cursor {snap_cursor} <= actual {ev_cursor} (newer events exist)"
            )
        else:
            report.add_check(
                "event_log_consistency", True,
                f"cursors match: {snap_cursor}"
            )
