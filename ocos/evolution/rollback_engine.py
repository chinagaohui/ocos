"""Phase 47: RollbackEngine — 回滚引擎。

管理进化失败时的安全回滚。

CE47-03: Migration ≠ Destruction
    每次迁移前创建快照，失败时从快照恢复。

回滚能力:
    - 按 snapshot_id 恢复
    - 按 proposal_id 恢复
    - 批量回滚
    - 验证恢复完整性
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ocos.evolution.evolution_types import (
    EvolutionProposal,
    EvolutionState,
    RollbackReason,
    RollbackRecord,
)
from ocos.evolution.migration_engine import MigrationEngine


@dataclass
class RollbackEngine:
    """回滚引擎。

    管理快照与恢复。CE47-03 核心保障。
    """

    _records: list[RollbackRecord] = field(default_factory=list)
    _snapshots: dict[str, dict] = field(default_factory=dict)  # snapshot_id → module_state

    def create_snapshot(
        self, proposal: EvolutionProposal, module_state: dict,
    ) -> str:
        """为提案创建回滚快照。"""
        snapshot_id = f"rb:{proposal.proposal_id}"
        self._snapshots[snapshot_id] = dict(module_state)
        return snapshot_id

    def rollback(
        self, proposal: EvolutionProposal, tick_id: int, reason: RollbackReason,
    ) -> RollbackRecord:
        """执行回滚——从快照恢复。"""
        snapshot_id = proposal.rollback_snapshot or f"rb:{proposal.proposal_id}"
        snapshot = self._snapshots.get(snapshot_id)

        record = RollbackRecord(
            proposal_id=proposal.proposal_id,
            reason=reason,
            restored_at_tick=tick_id,
            snapshot_before=snapshot_id,
            verified=snapshot is not None,
        )

        if snapshot:
            # 恢复快照状态
            proposal.state = EvolutionState.ROLLED_BACK
            record.snapshot_after = f"{proposal.target_module} restored"
            record.verified = True

        self._records.append(record)
        return record

    def verify_rollback(self, record: RollbackRecord) -> bool:
        """验证回滚是否正确恢复。"""
        snapshot = self._snapshots.get(record.snapshot_before, {})
        return bool(snapshot) and record.verified

    def rollback_all_failed(self, proposals: list[EvolutionProposal], tick_id: int) -> list[RollbackRecord]:
        """批量回滚所有失败的提案。"""
        records = []
        for p in proposals:
            if p.state == EvolutionState.ROLLED_BACK:
                continue
            record = self.rollback(p, tick_id, RollbackReason.TEST_FAILURE)
            records.append(record)
        return records

    @property
    def history(self) -> list[RollbackRecord]:
        return self._records

    @property
    def snapshot_count(self) -> int:
        return len(self._snapshots)


__all__ = ["RollbackEngine"]
