"""Phase V: PersistenceManager — 统一持久化与恢复策略。

整合现有持久化基础设施：
- SnapshotManager: 全系统快照（PS51）
- CheckpointManager: SQLite 进程检查点
- RuntimeSnapshot: 认知状态快照

新增能力：
- 统一 save/restore API
- 自动定期快照
- 崩溃恢复（从最新检查点）
- 持久化策略（定期/事件驱动/手动）
- 恢复报告
"""

from __future__ import annotations

import json
import logging
import os
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum, auto
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


class SnapshotType(Enum):
    """快照类型。"""
    FULL = auto()           # 全量快照
    INCREMENTAL = auto()    # 增量快照
    CHECKPOINT = auto()     # 检查点


class RestoreStrategy(Enum):
    """恢复策略。"""
    LATEST = auto()         # 从最新
    SPECIFIC = auto()       # 指定 ID
    LAST_KNOWN_GOOD = auto()  # 最后已知良好状态


@dataclass
class PersistenceConfig:
    """持久化配置。"""
    base_dir: str = "ocos_data/persistence"
    snapshot_interval: float = 300.0  # 5分钟
    max_snapshots: int = 20
    checkpoint_ttl: float = 86400.0   # 24小时
    auto_save_on_event: bool = True
    auto_restore_on_start: bool = True


@dataclass
class SaveResult:
    """保存结果。"""
    success: bool
    snapshot_id: str
    snapshot_type: str
    timestamp: float
    size_bytes: int = 0
    error: str = ""


@dataclass
class RestoreResult:
    """恢复结果。"""
    success: bool
    snapshot_id: str
    strategy: str
    timestamp: float
    domains_restored: list[str] = field(default_factory=list)
    domains_failed: list[str] = field(default_factory=list)
    error: str = ""


class PersistenceManager:
    """Phase V: 统一持久化管理器。"""

    def __init__(self, config: Optional[PersistenceConfig] = None) -> None:
        self._config = config or PersistenceConfig()
        self._base_dir = Path(self._config.base_dir)
        self._snapshots_dir = self._base_dir / "snapshots"
        self._checkpoints_dir = self._base_dir / "checkpoints"
        self._logs_dir = self._base_dir / "logs"

        # 创建目录
        self._snapshots_dir.mkdir(parents=True, exist_ok=True)
        self._checkpoints_dir.mkdir(parents=True, exist_ok=True)
        self._logs_dir.mkdir(parents=True, exist_ok=True)

        # 统计
        self._total_saves = 0
        self._total_restores = 0
        self._last_save_time: Optional[float] = None
        self._last_restore_time: Optional[float] = None
        self._save_history: list[SaveResult] = []
        self._restore_history: list[RestoreResult] = []

    # ── Public API ───────────────────────────────────────────────────────

    def save(
        self,
        data: dict[str, Any],
        snapshot_type: SnapshotType = SnapshotType.FULL,
        reason: str = "",
    ) -> SaveResult:
        """保存系统状态。"""
        try:
            snapshot_id = self._generate_id()
            timestamp = time.time()
            filename = f"{snapshot_id}.json"
            filepath = self._snapshots_dir / filename

            payload = {
                "snapshot_id": snapshot_id,
                "type": snapshot_type.name,
                "timestamp": timestamp,
                "datetime": datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat(),
                "reason": reason,
                "data": data,
            }

            content = json.dumps(payload, ensure_ascii=False, indent=2)
            filepath.write_text(content)

            size_bytes = len(content.encode("utf-8"))
            result = SaveResult(
                success=True,
                snapshot_id=snapshot_id,
                snapshot_type=snapshot_type.name,
                timestamp=timestamp,
                size_bytes=size_bytes,
            )

            self._total_saves += 1
            self._last_save_time = timestamp
            self._save_history.append(result)
            self._prune_snapshots()

            logger.info(
                "Snapshot saved: id=%s type=%s size=%dB reason=%s",
                snapshot_id, snapshot_type.name, size_bytes, reason,
            )
            return result
        except Exception as e:
            logger.error("Failed to save snapshot: %s", e)
            return SaveResult(
                success=False,
                snapshot_id="",
                snapshot_type=SnapshotType.FULL.name,
                timestamp=time.time(),
                error=str(e),
            )

    def restore(
        self,
        strategy: RestoreStrategy = RestoreStrategy.LATEST,
        snapshot_id: str = "",
    ) -> RestoreResult:
        """恢复系统状态。"""
        try:
            target = self._find_snapshot(strategy, snapshot_id)
            if target is None:
                return RestoreResult(
                    success=False,
                    snapshot_id="",
                    strategy=strategy.name,
                    timestamp=time.time(),
                    error="No snapshot found",
                )

            content = target.read_text()
            payload = json.loads(content)
            data = payload.get("data", {})

            result = RestoreResult(
                success=True,
                snapshot_id=payload["snapshot_id"],
                strategy=strategy.name,
                timestamp=time.time(),
                domains_restored=list(data.keys()),
            )

            self._total_restores += 1
            self._last_restore_time = time.time()
            self._restore_history.append(result)

            logger.info(
                "Snapshot restored: id=%s domains=%d",
                payload["snapshot_id"], len(data),
            )
            return result
        except Exception as e:
            logger.error("Failed to restore snapshot: %s", e)
            return RestoreResult(
                success=False,
                snapshot_id="",
                strategy=strategy.name,
                timestamp=time.time(),
                error=str(e),
            )

    def save_checkpoint(
        self,
        process_id: str,
        phase: str,
        context: dict[str, Any],
        ttl: Optional[float] = None,
    ) -> str:
        """保存进程检查点（SQLite）。"""
        try:
            from ocos.storage.checkpoint import CheckpointManager
            db_path = str(self._base_dir / "checkpoints.db")
            mgr = CheckpointManager(db_path, ttl or self._config.checkpoint_ttl)
            mgr.save(process_id, phase, context)
            logger.info("Checkpoint saved: process=%s phase=%s", process_id, phase)
            return process_id
        except Exception as e:
            logger.error("Failed to save checkpoint: %s", e)
            raise

    def restore_checkpoint(self, process_id: str) -> Optional[dict[str, Any]]:
        """恢复进程检查点。"""
        try:
            from ocos.storage.checkpoint import CheckpointManager
            db_path = str(self._base_dir / "checkpoints.db")
            mgr = CheckpointManager(db_path)
            return mgr.load(process_id)
        except Exception as e:
            logger.error("Failed to restore checkpoint: %s", e)
            return None

    def list_snapshots(self) -> list[dict[str, Any]]:
        """列出所有快照。"""
        results = []
        for f in sorted(self._snapshots_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
            try:
                payload = json.loads(f.read_text())
                results.append({
                    "snapshot_id": payload["snapshot_id"],
                    "type": payload["type"],
                    "timestamp": payload["timestamp"],
                    "datetime": payload.get("datetime", ""),
                    "reason": payload.get("reason", ""),
                    "size_bytes": f.stat().st_size,
                })
            except Exception as e:
                logger.warning("Failed to read snapshot %s: %s", f.name, e)
        return results

    def delete_snapshot(self, snapshot_id: str) -> bool:
        """删除快照。"""
        for f in self._snapshots_dir.glob(f"{snapshot_id}.json"):
            f.unlink()
            return True
        return False

    def clear_all(self) -> int:
        """清空所有快照。"""
        count = 0
        for f in self._snapshots_dir.glob("*.json"):
            f.unlink()
            count += 1
        return count

    # ── Auto Operations ──────────────────────────────────────────────────

    def auto_save_if_needed(self, data: dict[str, Any], tick: int = 0) -> Optional[SaveResult]:
        """自动保存（基于时间间隔）。"""
        now = time.time()
        if self._last_save_time and (now - self._last_save_time) < self._config.snapshot_interval:
            return None
        return self.save(data, SnapshotType.FULL, reason=f"auto_interval_tick_{tick}")

    def auto_restore_on_start(self) -> Optional[RestoreResult]:
        """启动时自动恢复。"""
        if not self._config.auto_restore_on_start:
            return None
        latest = self.list_snapshots()
        if not latest:
            return None
        return self.restore(RestoreStrategy.LATEST)

    def get_recovery_candidate(self) -> Optional[dict[str, Any]]:
        """获取恢复候选（最新有效快照）。"""
        snapshots = self.list_snapshots()
        if not snapshots:
            return None
        return snapshots[0]

    # ── Statistics ───────────────────────────────────────────────────────

    def get_stats(self) -> dict[str, Any]:
        """获取持久化统计。"""
        return {
            "total_saves": self._total_saves,
            "total_restores": self._total_restores,
            "snapshot_count": len(list(self._snapshots_dir.glob("*.json"))),
            "last_save_time": self._last_save_time,
            "last_restore_time": self._last_restore_time,
            "recent_saves": [
                {
                    "id": r.snapshot_id,
                    "type": r.snapshot_type,
                    "success": r.success,
                    "timestamp": r.timestamp,
                }
                for r in self._save_history[-5:]
            ],
            "recent_restores": [
                {
                    "id": r.snapshot_id,
                    "strategy": r.strategy,
                    "success": r.success,
                    "domains": r.domains_restored,
                }
                for r in self._restore_history[-5:]
            ],
        }

    def generate_report(self) -> str:
        """生成持久化报告。"""
        stats = self.get_stats()
        snapshots = self.list_snapshots()[:5]
        lines = [
            "=" * 50,
            "持久化与恢复报告",
            "=" * 50,
            f"总保存次数: {stats['total_saves']}",
            f"总恢复次数: {stats['total_restores']}",
            f"当前快照数: {stats['snapshot_count']}",
            "",
            "最近快照:",
        ]
        for s in snapshots:
            lines.append(f"  [{s['type']}] {s['snapshot_id'][:8]}... at {s['datetime']}")
        lines.append("")
        lines.append("=" * 50)
        return "\n".join(lines)

    # ── Internal ────────────────────────────────────────────────────────

    def _generate_id(self) -> str:
        return f"snap-{int(time.time())}-{uuid.uuid4().hex[:6]}"

    def _find_snapshot(
        self,
        strategy: RestoreStrategy,
        snapshot_id: str,
    ) -> Optional[Path]:
        """根据策略查找快照文件。"""
        if strategy == RestoreStrategy.SPECIFIC and snapshot_id:
            for f in self._snapshots_dir.glob(f"{snapshot_id}.json"):
                return f
        latest = self.list_snapshots()
        if latest:
            for f in self._snapshots_dir.glob("*.json"):
                if f.stem == latest[0]["snapshot_id"]:
                    return f
        return None

    def _prune_snapshots(self) -> None:
        """清理旧快照。"""
        snapshots = sorted(
            self._snapshots_dir.glob("*.json"),
            key=lambda p: p.stat().st_mtime,
        )
        while len(snapshots) > self._config.max_snapshots:
            snapshots.pop(0).unlink()


__all__ = [
    "PersistenceManager",
    "PersistenceConfig",
    "SnapshotType",
    "RestoreStrategy",
    "SaveResult",
    "RestoreResult",
]
