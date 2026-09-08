"""Phase 39.4: RuntimeSnapshot — 系统生命状态快照。

保存恢复认知连续性所需的最小状态集。
不是完整数据转储 — 只保存"恢复意识需要知道的"。

与 Checkpoint 的区别:
    Checkpoint = 持久化 Tick #(低层, 39.1)
    Snapshot  = 认知状态矢量(高层, 39.4)
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class SnapshotReason(Enum):
    PERIODIC = "periodic"          # 每 N 个 tick
    SHUTDOWN = "shutdown"         # 正常关闭
    PRE_ACTION = "pre_action"     # 高风险操作前
    MANUAL = "manual"             # 手动触发


@dataclass(frozen=True)
class RuntimeSnapshot:
    """运行时快照 — 不可变。

    Fields:
        snapshot_id:        快照唯一 ID
        tick_id:            快照时刻的 tick
        runtime_state:      Runtime 状态 (e.g. 'RUNNING')
        attention_focus:    当前注意力焦点描述
        active_goal_ids:    活跃 Goal ID 列表
        working_memory_keys: WorkingMemory 键列表 (cursor)
        pending_executions:  待执行任务 ID 列表
        pending_approvals:   待审批 Permission ID 列表
        event_log_cursor:    事件日志游标
        timestamp:           快照时间戳
        reason:              快照触发原因
    """

    snapshot_id: str
    tick_id: int
    runtime_state: str
    attention_focus: dict[str, Any] = field(default_factory=dict)
    active_goal_ids: tuple[str, ...] = ()
    working_memory_keys: tuple[str, ...] = ()
    pending_executions: tuple[str, ...] = ()
    pending_approvals: tuple[str, ...] = ()
    event_log_cursor: int = 0
    timestamp: float = field(default_factory=time.time)
    reason: str = "periodic"

    @classmethod
    def capture(
        cls,
        tick_id: int,
        runtime_state: str,
        active_goal_ids: tuple[str, ...] = (),
        attention_focus: dict[str, Any] | None = None,
        working_memory_keys: tuple[str, ...] = (),
        pending_executions: tuple[str, ...] = (),
        pending_approvals: tuple[str, ...] = (),
        event_log_cursor: int = 0,
        reason: SnapshotReason = SnapshotReason.PERIODIC,
    ) -> RuntimeSnapshot:
        return cls(
            snapshot_id=str(uuid.uuid4()),
            tick_id=tick_id,
            runtime_state=runtime_state,
            attention_focus=attention_focus or {},
            active_goal_ids=active_goal_ids,
            working_memory_keys=working_memory_keys,
            pending_executions=pending_executions,
            pending_approvals=pending_approvals,
            event_log_cursor=event_log_cursor,
            timestamp=time.time(),
            reason=reason.value,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "tick_id": self.tick_id,
            "runtime_state": self.runtime_state,
            "attention_focus": self.attention_focus,
            "active_goal_ids": list(self.active_goal_ids),
            "working_memory_keys": list(self.working_memory_keys),
            "pending_executions": list(self.pending_executions),
            "pending_approvals": list(self.pending_approvals),
            "event_log_cursor": self.event_log_cursor,
            "timestamp": self.timestamp,
            "reason": self.reason,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> RuntimeSnapshot:
        return cls(
            snapshot_id=d["snapshot_id"],
            tick_id=d["tick_id"],
            runtime_state=d["runtime_state"],
            attention_focus=d.get("attention_focus", {}),
            active_goal_ids=tuple(d.get("active_goal_ids", [])),
            working_memory_keys=tuple(d.get("working_memory_keys", [])),
            pending_executions=tuple(d.get("pending_executions", [])),
            pending_approvals=tuple(d.get("pending_approvals", [])),
            event_log_cursor=d.get("event_log_cursor", 0),
            timestamp=d.get("timestamp", 0),
            reason=d.get("reason", "unknown"),
        )


class SnapshotStore:
    """快照持久化存储。

    存储路径: ocos_data/snapshots/
    保留最近 N 个快照。
    """

    def __init__(self, base_dir: Path | None = None, max_snapshots: int = 20):
        self._base = base_dir or Path("ocos_data/snapshots")
        self._max = max_snapshots
        self._base.mkdir(parents=True, exist_ok=True)

    def save(self, snapshot: RuntimeSnapshot) -> Path:
        path = self._base / f"{snapshot.snapshot_id}.json"
        path.write_text(json.dumps(snapshot.to_dict(), indent=2))
        self._prune()
        return path

    def load(self, snapshot_id: str) -> RuntimeSnapshot | None:
        path = self._base / f"{snapshot_id}.json"
        if not path.exists():
            return None
        try:
            return RuntimeSnapshot.from_dict(json.loads(path.read_text()))
        except (json.JSONDecodeError, ValueError, OSError):
            # 损坏快照诚实降级为不存在（恢复链不得被损坏数据杀死）
            return None

    def latest(self) -> RuntimeSnapshot | None:
        """加载最新快照（按文件名时间排序）。

        L3 自愈加固（2026-09-08）：crash-loop 期间写快照可被中断产生空/
        截断文件——latest 跳过不可解析文件取次新，全部损坏时诚实返回
        None（无快照可恢复 ≠ 起不来）。
        """
        files = sorted(
            self._base.glob("*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        for path in files:
            try:
                return RuntimeSnapshot.from_dict(json.loads(path.read_text()))
            except (json.JSONDecodeError, ValueError, OSError):
                continue
        return None

    def latest_id(self) -> str | None:
        snap = self.latest()
        return snap.snapshot_id if snap else None

    def list_ids(self) -> list[str]:
        files = sorted(
            self._base.glob("*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        return [f.stem for f in files]

    def _prune(self) -> None:
        files = sorted(
            self._base.glob("*.json"),
            key=lambda p: p.stat().st_mtime,
        )
        while len(files) > self._max:
            files.pop(0).unlink()
