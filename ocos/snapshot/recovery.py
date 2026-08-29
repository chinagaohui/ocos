"""CrashRecovery — Agent Snapshot 恢复引擎。

Phase 21.01: Agent Snapshot System

从最新 Snapshot 恢复 Agent 完整状态。

职责分工(GAP-P3-3 裁决): 本模块 = agent 轻量快照恢复
(CrashRecovery.recover 从最新 AgentSnapshot 恢复, master_agent
生产路径在用); ocos/recovery/crash_recovery.py = 进程级完整
恢复管理器(recover_checkpoint/replay_events/reattempt_dlq,
依赖 storage 三件套, 由 tests/recovery 契约锁定)。两套同名
CrashRecovery 职责不同、并存不合并; 命名统一留待后续阶段。
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
