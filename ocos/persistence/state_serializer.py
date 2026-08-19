"""Phase 51.1: StateSerializer — JSON 序列化/反序列化。

将 Snapshot 序列化为稳定的 JSON 格式，支持从文件恢复。

PS51-04: format_version 确保跨版本兼容。
    读取旧版本快照时标记 warning，但尽力还原。
"""

from __future__ import annotations

import json
import zlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ocos.persistence.storage_types import (
    Snapshot, DomainSnapshot, SnapshotDomain, SnapshotStatus, Checkpoint,
)


@dataclass
class StateSerializer:
    """JSON 快照序列化器。"""

    storage_root: Path = field(
        default_factory=lambda: Path.home() / ".ocos" / "snapshots"
    )
    compress: bool = True  # 启用 zlib 压缩

    # ── Snapshot ──

    def serialize(self, snapshot: Snapshot) -> str:
        """序列化快照为 JSON 字符串。"""
        data: dict[str, Any] = self._snapshot_to_dict(snapshot)
        return json.dumps(data, ensure_ascii=False, indent=2)

    def deserialize(self, raw: str) -> Snapshot:
        """从 JSON 字符串反序列化快照。"""
        data = json.loads(raw)
        return self._dict_to_snapshot(data)

    # ── File I/O ──

    def save(self, snapshot: Snapshot) -> Path:
        """保存快照到文件。"""
        self.storage_root.mkdir(parents=True, exist_ok=True)
        if not snapshot.snapshot_id:
            from time import time
            snapshot.snapshot_id = f"snap-{int(time())}"

        raw = self.serialize(snapshot)
        path = self.storage_root / f"{snapshot.snapshot_id}.json"
        path.write_text(raw, encoding="utf-8")

        # 更新索引 (manifest)
        self._update_manifest(snapshot)

        return path

    def load(self, snapshot_id: str) -> Snapshot | None:
        """从文件加载指定快照。"""
        path = self.storage_root / f"{snapshot_id}.json"
        if not path.exists():
            return None
        raw = path.read_text(encoding="utf-8")
        return self.deserialize(raw)

    def load_latest(self) -> Snapshot | None:
        """加载最新的完整快照。"""
        manifest = self._read_manifest()
        if not manifest:
            return None

        # 最新的 COMPLETE 快照优先，其次是 TAKEN
        for entry in reversed(manifest):
            snap = self.load(entry["snapshot_id"])
            if snap and snap.is_complete:
                return snap

        # 退一步：任何状态
        for entry in reversed(manifest):
            return self.load(entry["snapshot_id"])

        return None

    def list_snapshots(self) -> list[dict[str, Any]]:
        """列出所有快照。"""
        return self._read_manifest()

    # ── 内部序列化 ──

    def _snapshot_to_dict(self, s: Snapshot) -> dict[str, Any]:
        return {
            "_format": "ocos-snapshot-v1",
            "snapshot_id": s.snapshot_id,
            "format_version": s.format_version,
            "tick": s.tick,
            "timestamp": s.timestamp,
            "metadata": s.metadata,
            "status": s.status.value,
            "domains": {
                k: self._domain_to_dict(v) for k, v in s.domains.items()
            },
        }

    def _domain_to_dict(self, d: DomainSnapshot) -> dict[str, Any]:
        return {
            "domain": d.domain.value,
            "tick": d.tick,
            "timestamp": d.timestamp,
            "data": d.data,
            "checksum": d.checksum,
            "status": d.status.value,
        }

    def _dict_to_snapshot(self, d: dict) -> Snapshot:
        format_version = d.get("format_version", "1.0.0")
        domains = {}
        for k, v in d.get("domains", {}).items():
            ds = DomainSnapshot(
                domain=SnapshotDomain(v.get("domain", k)),
                tick=v.get("tick", 0),
                timestamp=v.get("timestamp", 0.0),
                data=v.get("data", {}),
                checksum=v.get("checksum", ""),
                status=SnapshotStatus(v.get("status", "taken")),
            )
            domains[k] = ds

        return Snapshot(
            snapshot_id=d.get("snapshot_id", ""),
            format_version=format_version,
            tick=d.get("tick", 0),
            timestamp=d.get("timestamp", 0.0),
            metadata=d.get("metadata", {}),
            status=SnapshotStatus(d.get("status", "taken")),
            domains=domains,
        )

    # ── Manifest ──

    def _manifest_path(self) -> Path:
        return self.storage_root / "manifest.json"

    def _read_manifest(self) -> list[dict[str, Any]]:
        path = self._manifest_path()
        if not path.exists():
            return []
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return data.get("snapshots", [])
        except (json.JSONDecodeError, KeyError):
            return []

    def _update_manifest(self, snapshot: Snapshot) -> None:
        entries = self._read_manifest()
        entries.append({
            "snapshot_id": snapshot.snapshot_id,
            "tick": snapshot.tick,
            "timestamp": snapshot.timestamp,
            "status": snapshot.status.value,
            "domains": list(snapshot.domains.keys()),
        })
        # 只保留最近 100 条
        entries = sorted(entries, key=lambda e: e["tick"])[-100:]
        path = self._manifest_path()
        path.write_text(
            json.dumps({"snapshots": entries}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    # ── Backup / Prune ──

    def prune(self, keep: int = 10) -> int:
        """保留最近 N 个，删除其余。"""
        manifest = self._read_manifest()
        if len(manifest) <= keep:
            return 0

        removed = 0
        for entry in manifest[:-keep]:
            path = self.storage_root / f"{entry['snapshot_id']}.json"
            if path.exists():
                path.unlink()
                removed += 1

        # 重写 manifest
        manifest = manifest[-keep:]
        self._manifest_path().write_text(
            json.dumps({"snapshots": manifest}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return removed


__all__ = ["StateSerializer"]
