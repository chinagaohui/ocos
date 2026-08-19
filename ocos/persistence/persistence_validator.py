"""Phase 51.1: PersistenceValidator — 快照校验与完整性验证。

验证内容:
    - 快照格式版本兼容性 (PS51-04)
    - 域完整性 (四个域都存在)
    - 数据校验和
    - 跨 session 往返一致性
    - 受损快照检测与报告
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ocos.persistence.storage_types import (
    Snapshot, SnapshotStatus, SnapshotDomain,
)
from ocos.persistence.snapshot_manager import SnapshotManager


@dataclass
class PersistenceValidator:
    """快照校验器。"""

    snapshot_manager: SnapshotManager = field(default_factory=SnapshotManager)

    def validate_snapshot(self, snapshot: Snapshot) -> dict:
        """完整快照校验，返回报告。"""
        issues: list[str] = []
        warnings: list[str] = []

        # 1. 格式版本检查 (PS51-04)
        if not snapshot.format_version:
            issues.append("Missing format_version")
        elif snapshot.format_version < "1.0.0":
            warnings.append(f"Snapshot from older format: {snapshot.format_version}")

        # 2. ID 检查
        if not snapshot.snapshot_id:
            issues.append("Missing snapshot_id")

        # 3. 域完整性
        for domain in SnapshotDomain:
            if domain.value not in snapshot.domains:
                warnings.append(f"Missing domain: {domain.value}")

        # 4. 逐域校验和
        corrupt_domains = []
        for name, ds in snapshot.domains.items():
            expected = ds.checksum
            actual = self.snapshot_manager._checksum(ds.data)
            if expected and actual != expected:
                corrupt_domains.append(name)
                issues.append(f"Checksum mismatch in domain '{name}'")
            elif not expected:
                warnings.append(f"Domain '{name}' has no checksum")

        # 5. 数据基本结构检查
        for name, ds in snapshot.domains.items():
            if not isinstance(ds.data, dict):
                issues.append(f"Domain '{name}' data is not a dict")

        # 综合判断
        if issues:
            snapshot.status = SnapshotStatus.CORRUPT
        else:
            snapshot.status = SnapshotStatus.VALIDATED

        return {
            "snapshot_id": snapshot.snapshot_id,
            "format_version": snapshot.format_version,
            "tick": snapshot.tick,
            "domains": list(snapshot.domains.keys()),
            "domain_count": snapshot.domain_count,
            "corrupt_domains": corrupt_domains,
            "issues": issues,
            "warnings": warnings,
            "is_valid": len(issues) == 0,
            "status": snapshot.status.value,
        }

    def roundtrip_verify(self, snapshot: Snapshot) -> bool:
        """往返验证: serialize → deserialize → 再 validate。"""
        # 序列化
        raw = self.snapshot_manager.serializer.serialize(snapshot)
        # 反序列化
        restored = self.snapshot_manager.serializer.deserialize(raw)
        # 校验
        result = self.validate_snapshot(restored)

        # 额外: 核心字段一致性
        if (restored.snapshot_id != snapshot.snapshot_id or
            restored.tick != snapshot.tick):
            result["issues"].append("Roundtrip: id or tick mismatch")
            result["is_valid"] = False

        return result["is_valid"]


__all__ = ["PersistenceValidator"]
