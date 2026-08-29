"""Phase 39.4: Recovery Engine — 升级为 Cognitive Recovery。

39.1 → 39.4 升级路径:
    39.1 RecoveryEngine: 只恢复 RuntimeKernel tick 计数
    39.4 RecoveryManager: 恢复完整认知状态 (snapshot + event + execution + approval)

向后兼容: RecoveryEngine 和 RecoveryResult 接口保留，
通过 RecoveryManager 实现。旧调用方无需修改。
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path

from .checkpoint import CheckpointEngine, CheckpointRecord
from .recovery.recovery_manager import RecoveryManager
from .runtime_state import RuntimeState


@dataclass
class RecoveryResult:
    """Recovery 尝试的结果 (39.1 ABI, 保留向后兼容)。

    39.4: 增加 snapshot_id 和 restore_result 字段。
    """
    recovered: bool
    runtime_id: str
    last_tick_id: int
    state: RuntimeState
    next_tick_id: int
    from_checkpoint: bool = False
    snapshot_id: str | None = None
    warnings: list[str] | None = None

    @property
    def has_pending_approvals(self) -> bool:
        return False  # 向后兼容占位; 实际由 RestoreResult 提供

    def summary(self) -> str:
        if not self.recovered:
            return f"Cold start @ tick 1"
        return (f"Restore from {self.snapshot_id or 'checkpoint'} "
                f"→ tick {self.next_tick_id}")


class RecoveryEngine:
    """Phase 39.4 Recovery 控制器 (升级版)。

    保持 39.1 ABI，升级到 39.4 RecoveryManager。
    """

    def __init__(
        self,
        checkpoint_engine: CheckpointEngine,
        runtime_id: str | None = None,
        data_dir: Path | str | None = None,
    ):
        self._ckpt = checkpoint_engine
        self._runtime_id = runtime_id or str(uuid.uuid4())

        if data_dir is None:
            data_dir = Path("ocos_data")
        elif isinstance(data_dir, str):
            data_dir = Path(data_dir)

        self._recovery_mgr = RecoveryManager(data_dir)

    def attempt_recovery(self) -> RecoveryResult:
        """尝试恢复 — 39.4: 完整的认知状态恢复。

        没有快照 → 冷启动 (向后兼容 39.1)。
        """
        # 尝试 RecoveryManager 的认知恢复
        restore = self._recovery_mgr.start()

        if not restore.snapshot_id:
            # 退路: 尝试旧式 checkpoint 恢复
            record = self._ckpt.latest_checkpoint(self._runtime_id)
            if record is None:
                return RecoveryResult(
                    recovered=False, runtime_id=self._runtime_id,
                    last_tick_id=0, state=RuntimeState.BOOTING,
                    next_tick_id=1, from_checkpoint=False,
                )
            return RecoveryResult(
                recovered=True, runtime_id=record.runtime_id,
                last_tick_id=record.tick_id,
                state=RuntimeState(record.state) if record.state else RuntimeState.BOOTING,
                next_tick_id=record.tick_id + 1, from_checkpoint=True,
            )

        # 认知恢复成功
        return RecoveryResult(
            recovered=True,
            runtime_id=self._runtime_id,
            last_tick_id=restore.resume_tick - 1,
            state=RuntimeState.BOOTING,
            next_tick_id=restore.resume_tick,
            from_checkpoint=True,
            snapshot_id=restore.snapshot_id,
            warnings=restore.warnings,
        )

    def create_checkpoint(self, tick_id: int, state: RuntimeState) -> CheckpointRecord:
        """创建 checkpoint（39.1 ABI）。同时生成快照。"""
        from datetime import datetime, timezone
        record = CheckpointRecord(
            version="39.4",
            runtime_id=self._runtime_id,
            tick_id=tick_id,
            state=state.value,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
        self._ckpt.save(record)

        # 39.4: 同时生成认知快照
        self._recovery_mgr.take_snapshot(tick_id=tick_id, runtime_state=state.value)

        return record

    @property
    def runtime_id(self) -> str:
        return self._runtime_id

    @property
    def recovery_manager(self) -> RecoveryManager:
        """39.4: 直接访问 RecoveryManager。"""
        return self._recovery_mgr
