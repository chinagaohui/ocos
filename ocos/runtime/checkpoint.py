"""Phase 39.1: Checkpoint Engine — OCOS Runtime 可恢复状态快照。

Checkpoint 不是日志。它是 Runtime 自身的持久化状态，允许
停止 → 恢复 → 继续。

39.1 约束:
    - 不保存 Goal / Memory / Attention / Agent (这些未接入)
    - 只保存 Runtime 自身: runtime_id, tick_id, state, version
    - JSON 格式，完整性包含 hash
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class CheckpointRecord:
    """Runtime 可恢复状态快照。

    对应 RUNTIME_ABI §Checkpoint Model v1.0。
    """

    version: str                # "39.1"
    runtime_id: str             # UUID of this Runtime instance
    tick_id: int                # Last completed tick
    state: str                  # RuntimeState value
    timestamp: str              # ISO 8601 UTC
    integrity_hash: str = ""    # SHA-256 of content (excl. integrity_hash)

    def compute_hash(self, exclude_key: str = "integrity_hash") -> str:
        """计算内容哈希（不含 integrity_hash 自身）。"""
        payload = {k: v for k, v in asdict(self).items() if k != exclude_key}
        canonical = json.dumps(payload, sort_keys=True)
        return hashlib.sha256(canonical.encode()).hexdigest()

    def verify_integrity(self) -> bool:
        """验证完整性哈希。"""
        if not self.integrity_hash:
            return False
        expected = self.compute_hash()
        return self.integrity_hash == expected

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["integrity_hash"] = self.compute_hash()
        return d


class CheckpointEngine:
    """Phase 39.1 最小 Checkpoint 引擎。

    职责:
        - save: 写入 checkpoint JSON
        - load: 读取并验证完整性
        - latest_checkpoint: 查找最近 checkpoint

    约束 (Phase 38):
        - Checkpoint MUST 在 runtime 启动后第一个 tick 之前可用
        - 恢复时 Identity 先于 Goal 恢复（39.1 暂不涉及 Goal）
    """

    def __init__(self, checkpoint_dir: str | Path = "/tmp/ocos_checkpoints"):
        self._dir = Path(checkpoint_dir)
        self._dir.mkdir(parents=True, exist_ok=True)

    def _path(self, runtime_id: str, tick_id: int) -> Path:
        return self._dir / f"{runtime_id}_tick_{tick_id:06d}.json"

    def save(self, record: CheckpointRecord) -> Path:
        """保存 checkpoint。返回文件路径。"""
        data = record.to_dict()
        # 使用 compute_hash 后的 to_dict（包含正确 hash）
        path = self._path(record.runtime_id, record.tick_id)
        path.write_text(json.dumps(data, indent=2))
        return path

    def load(self, runtime_id: str, tick_id: int) -> CheckpointRecord | None:
        """加载指定 checkpoint。返回 None 如果不存在或损坏。"""
        path = self._path(runtime_id, tick_id)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text())
            record = CheckpointRecord(**data)
            if not record.verify_integrity():
                return None
            return record
        except (json.JSONDecodeError, TypeError):
            return None

    def latest_checkpoint(self, runtime_id: str) -> CheckpointRecord | None:
        """查找最近的有效 checkpoint。"""
        prefix = f"{runtime_id}_tick_"
        files = sorted(
            [f for f in self._dir.glob(f"{prefix}*.json")],
            reverse=True,
        )
        for path in files:
            try:
                data = json.loads(path.read_text())
                record = CheckpointRecord(**data)
                if record.verify_integrity():
                    return record
            except (json.JSONDecodeError, TypeError):
                continue
        return None

    def has_checkpoint(self, runtime_id: str) -> bool:
        return self.latest_checkpoint(runtime_id) is not None
