"""Phase 26 — GoalTracker: 进度追踪。

轻量级追踪器，不依赖外部存储。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from ocos.goal.models import GoalStatus, UserGoal


@dataclass
class GoalTracker:
    """进度追踪器。"""

    _progress: dict[str, float] = field(default_factory=dict)   # goal_id → 0.0-1.0
    _notes: dict[str, list[str]] = field(default_factory=dict)   # goal_id → notes
    _started_at: dict[str, datetime] = field(default_factory=dict)
    _completed_at: dict[str, datetime | None] = field(default_factory=dict)

    # ── API ───────────────────────────────────────────────────────

    def start(self, goal: UserGoal) -> None:
        """标记 goal 为进行中。"""
        gid = goal.id
        self._started_at[gid] = datetime.now(timezone.utc)
        self._progress[gid] = 0.0
        self._completed_at[gid] = None

    def update(self, goal_id: str, progress: float, note: str = "") -> None:
        """更新进度。"""
        if progress < 0.0 or progress > 1.0:
            raise ValueError(f"progress must be 0.0-1.0, got {progress}")
        self._progress[goal_id] = progress
        if note:
            self._notes.setdefault(goal_id, []).append(note)

    def complete(self, goal_id: str, note: str = "") -> None:
        """标记完成。"""
        self._progress[goal_id] = 1.0
        self._completed_at[goal_id] = datetime.now(timezone.utc)
        if note:
            self._notes.setdefault(goal_id, []).append(note)

    def get_progress(self, goal_id: str) -> float:
        """获取进度 0.0-1.0。"""
        return self._progress.get(goal_id, 0.0)

    def is_complete(self, goal_id: str) -> bool:
        """检查是否 100% 完成。"""
        return self._progress.get(goal_id, 0.0) >= 1.0

    def get_notes(self, goal_id: str) -> list[str]:
        """获取追踪备注。"""
        return self._notes.get(goal_id, [])

    def get_elapsed(self, goal_id: str) -> float | None:
        """获取已用时间（秒）。None 如果未开始。"""
        start = self._started_at.get(goal_id)
        if start is None:
            return None
        end = self._completed_at.get(goal_id) or datetime.now(timezone.utc)
        return (end - start).total_seconds()

    def is_started(self, goal_id: str) -> bool:
        """检查是否已开始。"""
        return goal_id in self._started_at
