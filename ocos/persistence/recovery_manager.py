"""Phase 51.1: RecoveryManager — 冷启动恢复引擎。

处理 OCOS 从关机/崩溃恢复的完整流程:
    1. Discover → 扫描可用快照
    2. Select → 选择最佳恢复点
    3. Validate → 校验完整性
    4. Restore → 注入各域状态
    5. Report → 生成恢复报告

PS51-03: 允许部分恢复 — 单域损坏不阻止整体恢复。
        恢复后系统进入 DEGRADED 模式，缺失的域从零初始化。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ocos.persistence.storage_types import (
    Snapshot, RecoveryState, RecoveryOutcome, LifecyclePhase,
    SnapshotStatus, SnapshotDomain,
)
from ocos.persistence.snapshot_manager import SnapshotManager


@dataclass
class RecoveryManager:
    """冷启动恢复引擎。"""

    snapshot_manager: SnapshotManager = field(default_factory=SnapshotManager)
    recovery_log: list[RecoveryState] = field(default_factory=list)

    # ── Public API ──

    def cold_boot(self) -> RecoveryState:
        """冷启动：尝试从最新快照恢复。返回恢复状态。"""
        # Step 1: Discover
        snapshots = self._discover()
        if not snapshots:
            return self._no_snapshot()

        # Step 2: Select — 选最新的完整快照
        candidate = self._select_best(snapshots)
        if candidate is None:
            return self._no_snapshot()

        # Step 3: Validate
        if not self.snapshot_manager.validate(candidate):
            # 快照损坏，尝试下一个
            fallback = self._select_fallback(snapshots, exclude=candidate.snapshot_id)
            if fallback is None:
                return RecoveryState(
                    outcome=RecoveryOutcome.FAILED,
                    snapshot=candidate,
                    warnings=["Best snapshot is corrupt, no fallback available"],
                )
            candidate = fallback
            self.snapshot_manager.validate(candidate)

        # Step 4: Restore
        result = self.snapshot_manager.restore(candidate)

        # Step 5: Record
        self.recovery_log.append(result)
        return result

    def warm_boot(self, snapshot_id: str) -> RecoveryState:
        """温启动：从指定快照恢复。"""
        return self.snapshot_manager.load_and_restore(snapshot_id)

    def get_phase(self, result: RecoveryState) -> LifecyclePhase:
        """根据恢复结果确定启动阶段。"""
        if result.outcome == RecoveryOutcome.NO_SNAPSHOT:
            return LifecyclePhase.COLD_BOOT
        elif result.outcome == RecoveryOutcome.FULL:
            return LifecyclePhase.WARM_BOOT
        elif result.outcome == RecoveryOutcome.PARTIAL:
            return LifecyclePhase.DEGRADED  # PS51-03
        else:
            # FAILED: 尝试从零启动
            return LifecyclePhase.COLD_BOOT

    # ── Internal ──

    def _discover(self) -> list[dict[str, Any]]:
        """发现所有可用快照。"""
        return self.snapshot_manager.list_snapshots()

    def _select_best(self, snapshots: list[dict[str, Any]]) -> Snapshot | None:
        """选择最佳恢复点：最新的 validated 完整快照。"""
        # 按 tick 降序
        entries = sorted(snapshots, key=lambda e: e.get("tick", 0), reverse=True)

        for entry in entries:
            if entry.get("status") in ("validated", "taken"):
                snap = self.snapshot_manager.serializer.load(entry["snapshot_id"])
                if snap and snap.is_complete:
                    return snap

        # 退一步：任何完整快照
        for entry in entries:
            snap = self.snapshot_manager.serializer.load(entry["snapshot_id"])
            if snap and snap.is_complete:
                return snap

        return None

    def _select_fallback(
        self, snapshots: list[dict[str, Any]], exclude: str,
    ) -> Snapshot | None:
        """选择次优快照（主快照损坏时）。"""
        entries = sorted(snapshots, key=lambda e: e.get("tick", 0), reverse=True)
        for entry in entries:
            if entry["snapshot_id"] == exclude:
                continue
            snap = self.snapshot_manager.serializer.load(entry["snapshot_id"])
            if snap:
                return snap
        return None

    def _no_snapshot(self) -> RecoveryState:
        """无可用快照 — 冷启动。"""
        from time import time
        result = RecoveryState(
            outcome=RecoveryOutcome.NO_SNAPSHOT,
            tick_at_recovery=0,
            age_seconds=0.0,
        )
        self.recovery_log.append(result)
        return result


__all__ = ["RecoveryManager"]
