"""Phase 39.4: Recovery Manager — 编排所有恢复子系统。

RecoveryManager 统一管理:
    - SnapshotStore:    定期快照存储
    - EventLog:         事件追加 + 游标
    - ExecutionLedger:  执行账本
    - ApprovalStore:    待审批存储
    - CognitiveStateRestore: 恢复引擎

与 39.1 RecoveryEngine 的升级关系:
    39.1 RecoveryEngine: 只恢复 RuntimeKernel 自身
    39.4 RecoveryManager: 恢复完整认知状态 + 执行 + 审批 + 事件

向后兼容: 39.1 RecoveryEngine 的接口保留，通过 RecoveryManager 实现。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .cognitive_restore import CognitiveStateRestore, RestoreResult
from .event_replay import EventLog, EventType
from .execution_recovery import ExecutionLedger, ExecutionRecord
from .integrity_verifier import IntegrityReport
from .permission_recovery import ApprovalStore, PendingApproval
from .runtime_snapshot import RuntimeSnapshot, SnapshotReason, SnapshotStore


class RecoveryManager:
    """恢复管理器 — Phase 39.4 总入口。

    用法:
        mgr = RecoveryManager(data_dir=Path("ocos_data"))
        mgr.start()  # ← 尝试恢复

        # 运行中...
        mgr.take_snapshot(tick_id=100, goals=("g-1",))
        mgr.log_event(EventType.GOAL_CREATED, tick_id=100, payload={...})

        mgr.shutdown()  # ← 最终快照
    """

    def __init__(self, data_dir: Path | None = None):
        base = data_dir or Path("ocos_data")

        self.snapshots = SnapshotStore(base / "snapshots")
        self.events = EventLog(base / "events")

        # Execution ledger: persist to disk
        self._ledger_path = base / "executions" / "ledger.json"
        self._ledger_path.parent.mkdir(parents=True, exist_ok=True)
        self.ledger = self._load_ledger()

        self.approvals = ApprovalStore(base / "approvals")

        self._restorer = CognitiveStateRestore(
            self.snapshots, self.events, self.ledger, self.approvals
        )
        self._last_snapshot_tick: int = 0
        self._snapshot_interval: int = 100  # 每 100 tick 生成快照

    # ── 恢复 ──

    def start(self) -> RestoreResult:
        """启动时尝试恢复 — 加载 latest snapshot → verify → restore → resume。"""
        return self._restorer.restore(strict=False)

    def restore_strict(self) -> RestoreResult:
        """严格恢复 — 不一致 → FAIL。"""
        return self._restorer.restore(strict=True)

    # ── 快照 ──

    def take_snapshot(
        self,
        tick_id: int,
        runtime_state: str = "RUNNING",
        active_goal_ids: tuple[str, ...] = (),
        attention_focus: dict[str, Any] | None = None,
        working_memory_keys: tuple[str, ...] = (),
        pending_executions: tuple[str, ...] | None = None,
        pending_approvals: tuple[str, ...] | None = None,
        reason: SnapshotReason = SnapshotReason.PERIODIC,
    ) -> RuntimeSnapshot:
        """生成并持久化快照。"""
        if pending_executions is None:
            pending_executions = tuple(r.execution_id for r in self.ledger._records.values()
                                      if not r.is_terminal)
        if pending_approvals is None:
            pending_approvals = tuple(a.approval_id for a in self.approvals.get_waiting())

        snapshot = RuntimeSnapshot.capture(
            tick_id=tick_id,
            runtime_state=runtime_state,
            active_goal_ids=active_goal_ids,
            attention_focus=attention_focus,
            working_memory_keys=working_memory_keys,
            pending_executions=pending_executions,
            pending_approvals=pending_approvals,
            event_log_cursor=self.events.cursor(),
            reason=reason,
        )
        self.snapshots.save(snapshot)
        self._last_snapshot_tick = tick_id
        return snapshot

    def should_snapshot(self, tick_id: int) -> bool:
        """判断是否应该在此 tick 生成快照。"""
        return tick_id - self._last_snapshot_tick >= self._snapshot_interval

    # ── 事件 ──

    def log_event(self, event_type: EventType | str, tick_id: int,
                  payload: dict[str, Any]) -> Any:
        return self.events.append(event_type, tick_id, payload)

    def replay_events(self, from_cursor: int = 0) -> list:
        return self.events.replay_from(from_cursor)

    # ── 关闭 ──

    def shutdown(self, tick_id: int, runtime_state: str = "SHUTDOWN",
                 active_goal_ids: tuple[str, ...] = ()) -> RuntimeSnapshot:
        """关闭前最终快照。"""
        self._save_ledger()
        return self.take_snapshot(
            tick_id=tick_id,
            runtime_state=runtime_state,
            active_goal_ids=active_goal_ids,
            reason=SnapshotReason.SHUTDOWN,
        )

    def _load_ledger(self) -> ExecutionLedger:
        if self._ledger_path.exists():
            try:
                data = json.loads(self._ledger_path.read_text())
                if data:
                    return ExecutionLedger.from_dict_list(data)
            except (json.JSONDecodeError, KeyError):
                pass
        return ExecutionLedger()

    def _save_ledger(self) -> None:
        self._ledger_path.write_text(
            json.dumps(self.ledger.to_dict_list(), indent=2)
        )

    def track_execution_start(self, execution_id: str, capability_id: str,
                              action: str, resource: str | None = None,
                              tick_id: int = 0) -> ExecutionRecord:
        rec = self.ledger.record_start(execution_id, capability_id, action, resource, tick_id)
        self._save_ledger()
        return rec

    def track_execution_success(self, execution_id: str, tick_id: int,
                                summary: str | None = None) -> ExecutionRecord | None:
        rec = self.ledger.record_success(execution_id, tick_id, summary)
        self._save_ledger()
        return rec

    def track_execution_failure(self, execution_id: str, tick_id: int,
                                summary: str | None = None) -> ExecutionRecord | None:
        rec = self.ledger.record_failure(execution_id, tick_id, summary)
        self._save_ledger()
        return rec

    def should_skip_execution(self, execution_id: str) -> bool:
        return self.ledger.should_skip(execution_id)

    # ── 审批 ──

    def request_approval(self, capability_id: str, action: str,
                         resource: str | None = None, tick_id: int = 0,
                         reason: str = "") -> PendingApproval:
        return self.approvals.add(capability_id, action, resource, tick_id, reason=reason)

    def approve(self, approval_id: str) -> PendingApproval | None:
        return self.approvals.approve(approval_id)

    def deny_approval(self, approval_id: str, reason: str = "") -> PendingApproval | None:
        return self.approvals.deny(approval_id, reason)

    def pending_approvals_count(self) -> int:
        return self.approvals.count_waiting()

    # ── 验证 ──

    def verify(self, snapshot: RuntimeSnapshot) -> IntegrityReport:
        return self._verifier.verify(snapshot)

    @property
    def _verifier(self):
        from .integrity_verifier import IntegrityVerifier
        return IntegrityVerifier(self.events, self.ledger, self.approvals)

    # ── 关闭 ──

    def shutdown(self, tick_id: int, runtime_state: str = "SHUTDOWN",
                 active_goal_ids: tuple[str, ...] = ()) -> RuntimeSnapshot:
        """关闭前最终快照。"""
        return self.take_snapshot(
            tick_id=tick_id,
            runtime_state=runtime_state,
            active_goal_ids=active_goal_ids,
            reason=SnapshotReason.SHUTDOWN,
        )
