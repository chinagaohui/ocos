"""Phase 47: MigrationEngine — 迁移引擎。

安全执行进化迁移。

迁移流程:
    1. 创建回滚快照 (CE47-03)
    2. 执行变更
    3. 验证结果
    4. 成功 → ACTIVE / 失败 → ROLL BACK

边界 CE47-03: Migration ≠ Destruction — 每次迁移都可回滚。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ocos.evolution.evolution_types import (
    EvolutionProposal,
    EvolutionState,
    RollbackReason,
    RollbackRecord,
)


@dataclass
class MigrationResult:
    """迁移结果。"""
    proposal_id: str = ""
    success: bool = False
    tick: int = 0
    snapshot_id: str = ""
    error: str = ""


@dataclass
class MigrationEngine:
    """迁移引擎——安全执行进化。

    CE47-03: 迁移前必须创建快照，确保可回滚。
    """

    _results: list[MigrationResult] = field(default_factory=list)
    _snapshots: dict[str, str] = field(default_factory=dict)  # snapshot_id → state

    def migrate(
        self, proposal: EvolutionProposal, tick_id: int,
    ) -> MigrationResult:
        """执行进化迁移。"""

        if not proposal.ready_for_migration:
            return MigrationResult(
                proposal_id=proposal.proposal_id,
                success=False,
                tick=tick_id,
                error="Proposal not ready for migration (must be APPROVED + sandbox_passed + safe)",
            )

        proposal.state = EvolutionState.MIGRATING

        # 步骤 1: 创建回滚快照 (CE47-03)
        snapshot_id = self._create_snapshot(proposal)
        proposal.rollback_snapshot = snapshot_id

        # 步骤 2: 执行变更
        try:
            result = self._execute(proposal, tick_id)
            if result.success:
                proposal.state = EvolutionState.ACTIVE
                proposal.active_since_tick = tick_id
                proposal.migration_tick = tick_id
            else:
                # 迁移失败 → 触发回滚 (CE47-03)
                self._trigger_rollback(proposal, tick_id, RollbackReason.TEST_FAILURE)
                proposal.state = EvolutionState.ROLLED_BACK
            self._results.append(result)
            return result

        except Exception as e:
            self._trigger_rollback(proposal, tick_id, RollbackReason.TEST_FAILURE)
            proposal.state = EvolutionState.ROLLED_BACK
            result = MigrationResult(
                proposal_id=proposal.proposal_id,
                success=False,
                tick=tick_id,
                snapshot_id=snapshot_id,
                error=str(e),
            )
            self._results.append(result)
            return result

    def _create_snapshot(self, proposal: EvolutionProposal) -> str:
        """创建模块当前状态的快照 (CE47-03)。"""
        snapshot_id = f"snap:{proposal.proposal_id}:{proposal.target_module}"
        state_repr = (
            f"module={proposal.target_module},"
            f"domain={proposal.domain.value},"
            f"change_type={proposal.change_type}"
        )
        self._snapshots[snapshot_id] = state_repr
        return snapshot_id

    def _execute(
        self, proposal: EvolutionProposal, tick_id: int,
    ) -> MigrationResult:
        """执行实际变更 (模拟)。"""
        # 模拟: 检查变更是否可执行
        if proposal.change_type == "replace" and not proposal.rollback_snapshot:
            return MigrationResult(
                proposal_id=proposal.proposal_id,
                success=False,
                tick=tick_id,
                error="Replace requires rollback snapshot (CE47-03)",
            )

        return MigrationResult(
            proposal_id=proposal.proposal_id,
            success=True,
            tick=tick_id,
            snapshot_id=proposal.rollback_snapshot,
        )

    def _trigger_rollback(
        self, proposal: EvolutionProposal, tick_id: int, reason: RollbackReason,
    ) -> RollbackRecord:
        """触发回滚。"""
        return RollbackRecord(
            proposal_id=proposal.proposal_id,
            reason=reason,
            restored_at_tick=tick_id,
            snapshot_before=proposal.rollback_snapshot,
            verified=False,
        )

    def restore_snapshot(self, snapshot_id: str) -> str | None:
        """恢复快照状态。"""
        return self._snapshots.get(snapshot_id)

    @property
    def recent_migrations(self) -> list[MigrationResult]:
        return self._results[-20:]

    @property
    def active_snapshots(self) -> int:
        return len(self._snapshots)


__all__ = ["MigrationResult", "MigrationEngine"]
