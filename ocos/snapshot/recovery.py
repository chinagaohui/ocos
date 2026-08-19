"""CrashRecovery — Agent Snapshot 恢复引擎。

Phase 21.01: Agent Snapshot System

从最新 Snapshot 恢复 Agent 完整状态。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

from ocos.snapshot.manager import SnapshotManager

logger = logging.getLogger(__name__)


@dataclass
class RecoveryResult:
    """恢复结果。"""

    success: bool
    snapshot_id: Optional[str] = None
    restored_goals: int = 0
    errors: list[str] = field(default_factory=list)


class CrashRecovery:
    """Agent Snapshot 恢复引擎。

    从 SQLite 加载最新 Snapshot 并返回 RecoveryResult。
    调用方根据 RecoveryResult 决定恢复路径。
    """

    def __init__(self, snapshot_manager: SnapshotManager) -> None:
        self._mgr = snapshot_manager

    def recover(self) -> RecoveryResult:
        """从最新 Snapshot 恢复。

        加载最新快照 → 标记为已恢复 → 返回 RecoveryResult。
        """
        snapshot = self._mgr.load_latest()
        if not snapshot:
            logger.warning("No snapshot found for recovery.")
            return RecoveryResult(success=False, errors=["No snapshot found"])

        self._mgr.mark_recovered(snapshot.snapshot_id)
        logger.info(
            "Recovery complete: %s (%d goals restored)",
            snapshot.snapshot_id,
            len(snapshot.goal_state),
        )

        return RecoveryResult(
            success=True,
            snapshot_id=snapshot.snapshot_id,
            restored_goals=len(snapshot.goal_state),
        )
