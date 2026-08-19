"""
OCOS Time Manager — 统一时间源。

提供逻辑时钟（单调递增 cycle 计数）和物理时钟（UTC 时间戳）的统一接口。
所有模块通过 TimeManager 获取时间，而非直接调用 datetime.now()。
"""

from __future__ import annotations

import threading
import time
from datetime import datetime, timezone
from typing import Optional


class TimeManager:
    """统一时间管理器。

    - `cycle`: 单调递增逻辑时钟，每次 tick 递增
    - `timeline_id`: 时间线标识（支持多时间线隔离）
    - 物理时间从系统时钟获取，格式为 ISO 8601 UTC
    """

    def __init__(self, timeline_id: str = "default"):
        self._timeline_id = timeline_id
        self._cycle: int = 0
        self._lock = threading.Lock()
        self._start_time: float = time.time()

    # ── 逻辑时钟 ─────────────────────────────────────────────────────────────

    @property
    def cycle(self) -> int:
        """当前逻辑 cycle 号（单调递增）。"""
        return self._cycle

    def tick(self) -> int:
        """递增逻辑时钟并返回新的 cycle 号。"""
        with self._lock:
            self._cycle += 1
            return self._cycle

    def reset_cycle(self) -> None:
        """重置逻辑时钟（仅用于测试）。"""
        with self._lock:
            self._cycle = 0

    # ── 物理时钟 ─────────────────────────────────────────────────────────────

    @property
    def timeline_id(self) -> str:
        return self._timeline_id

    @staticmethod
    def utc_now() -> str:
        """当前 UTC 时间的 ISO 8601 格式字符串。"""
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def utc_timestamp() -> float:
        """当前 UTC 时间戳（秒，浮点数）。"""
        return time.time()

    @property
    def uptime_seconds(self) -> float:
        """此 TimeManager 实例已运行时间（秒）。"""
        return time.time() - self._start_time

    # ── 时间格式化 ───────────────────────────────────────────────────────────

    @staticmethod
    def format_timestamp(ts: Optional[float] = None) -> str:
        """格式化时间戳为人类可读字符串。"""
        t = ts if ts is not None else time.time()
        return datetime.fromtimestamp(t, tz=timezone.utc).strftime(
            "%Y-%m-%d %H:%M:%S UTC"
        )

    def __repr__(self) -> str:
        return (
            f"TimeManager(timeline={self._timeline_id}, "
            f"cycle={self._cycle}, uptime={self.uptime_seconds:.1f}s)"
        )
