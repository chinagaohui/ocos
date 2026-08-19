"""Phase 51.1: SnapshotManager — 快照创建/恢复/列表/校验。

管理完整的系统快照生命周期:
    - take: 采集当前四个域的状态，生成 Snapshot
    - restore: 将 Snapshot 数据注入四个域
    - list: 列出历史快照
    - validate: 校验快照完整性

PS51-01: 快照是副本 — take 不修改运行时状态
PS51-02: 恢复是填充 — restore 不覆盖已有数据
PS51-03: 部分恢复 — 单域失败不阻止其他域恢复
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Protocol

from ocos.persistence.storage_types import (
    Snapshot, DomainSnapshot, SnapshotDomain, SnapshotStatus,
    RecoveryState, RecoveryOutcome,
)
from ocos.persistence.state_serializer import StateSerializer


# ═══════════════════════════════════════════════════════════════════════════════
# State Providers — 各域的状态提供者协议
# ═══════════════════════════════════════════════════════════════════════════════


class StateProvider(Protocol):
    """状态提供者 — 每个域实现此协议。"""
    def snapshot_domain(self) -> SnapshotDomain: ...
    def get_state(self) -> dict[str, Any]: ...
    def set_state(self, data: dict[str, Any]) -> None: ...


# ═══════════════════════════════════════════════════════════════════════════════
# Snapshot Manager
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class SnapshotManager:
    """系统快照管理器。"""

    serializer: StateSerializer = field(default_factory=StateSerializer)
    providers: dict[str, StateProvider] = field(default_factory=dict)

    def register_provider(self, provider: StateProvider) -> None:
        """注册状态提供者。"""
        self.providers[provider.snapshot_domain().value] = provider

    # ── Take Snapshot ──

    def take(self, tick: int, reason: str = "") -> Snapshot:
        """创建全系统快照 (PS51-01: 只读采集)。"""
        from time import time
        snapshot = Snapshot(
            snapshot_id=f"snap-{int(time())}",
            tick=tick,
            timestamp=time(),
            metadata={"reason": reason},
        )

        for name, provider in self.providers.items():
            data = provider.get_state()
            checksum = self._checksum(data)
            snapshot.domains[name] = DomainSnapshot(
                domain=SnapshotDomain(name),
                tick=tick,
                timestamp=time(),
                data=data,
                checksum=checksum,
                status=SnapshotStatus.TAKEN,
            )

        # 所有域验证后更新状态
        snapshot.status = SnapshotStatus.VALIDATED
        snapshot.metadata["domain_count"] = snapshot.domain_count

        return snapshot

    def save(self, snapshot: Snapshot) -> str:
        """保存快照到持久化存储。"""
        path = self.serializer.save(snapshot)
        return str(path)

    def take_and_save(self, tick: int, reason: str = "") -> Snapshot:
        """采集并保存 — 常用快捷操作。"""
        snapshot = self.take(tick, reason)
        self.save(snapshot)
        return snapshot

    # ── Restore Snapshot ──

    def restore(self, snapshot: Snapshot) -> RecoveryState:
        """从快照恢复系统状态 (PS51-02: 填充，不覆盖)。"""
        recovered: list[SnapshotDomain] = []
        failed: list[SnapshotDomain] = []
        warnings: list[str] = []

        for name, domain_snap in snapshot.domains.items():
            provider = self.providers.get(name)
            if provider is None:
                failed.append(domain_snap.domain)
                warnings.append(f"No provider for domain '{name}'")
                continue
            try:
                provider.set_state(domain_snap.data)
                recovered.append(domain_snap.domain)
            except Exception as e:
                failed.append(domain_snap.domain)
                warnings.append(f"Restore failed for '{name}': {e}")

        # 判断恢复结果
        if len(recovered) == len(snapshot.domains):
            outcome = RecoveryOutcome.FULL
        elif len(recovered) > 0:
            outcome = RecoveryOutcome.PARTIAL  # PS51-03
        else:
            outcome = RecoveryOutcome.FAILED

        from time import time
        return RecoveryState(
            outcome=outcome,
            snapshot=snapshot,
            recovered_domains=recovered,
            failed_domains=failed,
            tick_at_recovery=snapshot.tick,
            age_seconds=time() - snapshot.timestamp,
            warnings=warnings,
        )

    # ── List / Validate ──

    def list_snapshots(self) -> list[dict[str, Any]]:
        """列出所有已保存的快照。"""
        return self.serializer.list_snapshots()

    def validate(self, snapshot: Snapshot) -> bool:
        """验证快照完整性 — 逐域 checksum 校验。"""
        valid = True
        for name, domain_snap in snapshot.domains.items():
            expected = domain_snap.checksum
            actual = self._checksum(domain_snap.data)
            if expected and actual != expected:
                domain_snap.status = SnapshotStatus.CORRUPT
                valid = False
        if valid:
            snapshot.status = SnapshotStatus.VALIDATED
        return valid

    def load_and_restore(self, snapshot_id: str = "") -> RecoveryState:
        """加载指定快照并恢复。空 ID = 加载最新。"""
        if snapshot_id:
            snapshot = self.serializer.load(snapshot_id)
        else:
            snapshot = self.serializer.load_latest()

        if snapshot is None:
            return RecoveryState(outcome=RecoveryOutcome.NO_SNAPSHOT)

        # 校验完整性
        if not self.validate(snapshot):
            snapshot.status = SnapshotStatus.CORRUPT

        return self.restore(snapshot)

    # ── Helpers ──

    @staticmethod
    def _checksum(data: dict[str, Any]) -> str:
        """计算数据校验和。"""
        raw = json.dumps(data, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


__all__ = ["SnapshotManager", "StateProvider"]
