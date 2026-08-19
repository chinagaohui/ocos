"""MemoryConsolidator — 记忆巩固流水线。

工作记忆 → 情景记忆 → 长期记忆。
基于重要性、频率、时效性决定哪些记忆被巩固。
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Optional

from ocos.logging import get_logger

logger = get_logger(__name__)


class MemoryLevel(Enum):
    """记忆层级。"""
    WORKING = "working"       # 短期工作记忆
    EPISODIC = "episodic"     # 情景记忆
    LONG_TERM = "long_term"   # 长期记忆


@dataclass
class MemoryItem:
    """一条记忆项。"""
    content: str
    level: MemoryLevel
    importance: float          # 0.0 ~ 1.0
    frequency: int = 1
    created_at: float = field(default_factory=time.time)
    last_accessed: float = field(default_factory=time.time)
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    id: Optional[str] = None


class MemoryConsolidator:
    """记忆巩固器 — 管理记忆在层级间的流动。"""

    def __init__(self,
                 working_capacity: int = 10,
                 consolidation_threshold: float = 0.5,
                 importance_decay: float = 0.05):
        self._working: list[MemoryItem] = []
        self._episodic: list[MemoryItem] = []
        self._long_term: list[MemoryItem] = []
        self._working_capacity = working_capacity
        self._consolidation_threshold = consolidation_threshold
        self._importance_decay = importance_decay
        self._lock = threading.RLock()

    @property
    def working_count(self) -> int:
        with self._lock:
            return len(self._working)

    @property
    def episodic_count(self) -> int:
        with self._lock:
            return len(self._episodic)

    @property
    def long_term_count(self) -> int:
        with self._lock:
            return len(self._long_term)

    def get_working_items(self) -> list[MemoryItem]:
        """Phase 21: 获取所有工作记忆条目（用于持久化）。"""
        with self._lock:
            return list(self._working)

    def add_to_working(self, content: str, importance: float = 0.3,
                       tags: Optional[list[str]] = None,
                       metadata: Optional[dict[str, Any]] = None) -> MemoryItem:
        """添加记忆到工作记忆层。如超出容量则触发巩固。"""
        with self._lock:
            item = MemoryItem(
                content=content,
                level=MemoryLevel.WORKING,
                importance=importance,
                tags=tags or [],
                metadata=metadata or {},
                id=f"wm-{len(self._working) + len(self._episodic) + len(self._long_term) + 1}",
            )
            self._working.append(item)

            if len(self._working) > self._working_capacity:
                self._consolidate()

            return item

    def _consolidate(self) -> None:
        """巩固：将高重要性/高频次的工作记忆提升到情景记忆。"""
        # 按重要性 + 频率排序
        self._working.sort(
            key=lambda x: x.importance * (1 + 0.1 * x.frequency),
            reverse=True,
        )

        # 顶部的一半被巩固
        to_consolidate = max(1, len(self._working) // 2)
        for item in self._working[:to_consolidate]:
            if item.importance >= self._consolidation_threshold:
                episodic_item = MemoryItem(
                    content=item.content,
                    level=MemoryLevel.EPISODIC,
                    importance=item.importance,
                    frequency=item.frequency,
                    created_at=item.created_at,
                    last_accessed=item.last_accessed,
                    tags=item.tags,
                    metadata=item.metadata,
                    id=f"ep-{len(self._episodic) + 1}",
                )
                self._episodic.append(episodic_item)

        # 移除已被巩固的工作记忆
        self._working = self._working[to_consolidate:]

    def consolidate_to_long_term(self, max_items: int = 5) -> int:
        """将高重要性情景记忆巩固为长期记忆。返回巩固数量。"""
        with self._lock:
            # 情景记忆按重要性排序
            self._episodic.sort(
                key=lambda x: x.importance * (1 + 0.1 * x.frequency),
                reverse=True,
            )

            consolidated = 0
            for item in self._episodic[:max_items]:
                if item.importance >= self._consolidation_threshold + 0.2:
                    lt_item = MemoryItem(
                        content=item.content,
                        level=MemoryLevel.LONG_TERM,
                        importance=item.importance,
                        frequency=item.frequency,
                        created_at=item.created_at,
                        last_accessed=item.last_accessed,
                        tags=item.tags,
                        metadata=item.metadata,
                        id=f"lt-{len(self._long_term) + 1}",
                    )
                    self._long_term.append(lt_item)
                    consolidated += 1

            # 移除已巩固的
            self._episodic = self._episodic[max_items:]
            return consolidated

    # ── Phase 24-D: 定时调度 ────────────────────────────────────────

    def schedule_consolidation(self, off_peak: bool = True,
                               max_age_hours: float = 24.0) -> int:
        """24d1: 定时调度 — 夜间低峰期自动压缩。

        Args:
            off_peak: 是否仅在低峰期执行（如果为 True，检查当前时间）
            max_age_hours: 超过此时长的情景记忆全部压缩

        Returns:
            压缩的记忆数量
        """
        if off_peak:
            # 简化：检查是否在 0-6 点（低峰窗口）
            import datetime
            hour = datetime.datetime.now().hour
            if not (0 <= hour <= 6):
                logger.debug(
                    "schedule_consolidation: skipped (hour=%d, off-peak only 0-6)",
                    hour,
                )
                return 0

        with self._lock:
            now = time.time()
            deadline = now - max_age_hours * 3600
            old_episodes = [
                item for item in self._episodic
                if item.created_at <= deadline
            ]
            if not old_episodes:
                return 0

            # 压缩到长期记忆
            count = 0
            for item in old_episodes:
                if item.importance >= self._consolidation_threshold:
                    lt_item = MemoryItem(
                        content=item.content,
                        level=MemoryLevel.LONG_TERM,
                        importance=item.importance * 0.8,
                        frequency=item.frequency,
                        created_at=item.created_at,
                        last_accessed=item.last_accessed,
                        tags=item.tags,
                        metadata=item.metadata,
                        id=f"lt-sched-{len(self._long_term) + 1}",
                    )
                    self._long_term.append(lt_item)
                    count += 1

            # 移除已压缩的
            self._episodic = [
                e for e in self._episodic if e not in old_episodes
            ]
            logger.info(
                "schedule_consolidation: %d episodic → long-term "
                "(total lt=%d, ep=%d)",
                count, len(self._long_term), len(self._episodic),
            )
            return count

    def compact_expired(self, max_age_days: float = 7.0) -> int:
        """清理过期工作记忆（超过 N 天未访问则遗忘）。"""
        with self._lock:
            now = time.time()
            deadline = now - max_age_days * 86400
            before = len(self._working)
            self._working = [
                w for w in self._working
                if w.last_accessed > deadline
            ]
            removed = before - len(self._working)
            if removed:
                logger.debug("compact_expired: removed %d stale working items", removed)
            return removed

    def recall(self, query: str, max_results: int = 5) -> list[MemoryItem]:
        """跨层级检索记忆。"""
        with self._lock:
            results = []

            for pool, level in [
                (self._long_term, MemoryLevel.LONG_TERM),
                (self._episodic, MemoryLevel.EPISODIC),
                (self._working, MemoryLevel.WORKING),
            ]:
                for item in pool:
                    if len(results) >= max_results:
                        break
                    if query.lower() in item.content.lower() or \
                       any(query.lower() in t.lower() for t in item.tags):
                        item.last_accessed = time.time()
                        item.frequency += 1
                        results.append(item)

            return results

    def get_stats(self) -> dict[str, Any]:
        """获取记忆统计。"""
        with self._lock:
            return {
                "working": len(self._working),
                "episodic": len(self._episodic),
                "long_term": len(self._long_term),
                "total": len(self._working) + len(self._episodic)
                         + len(self._long_term),
            }

    def clear(self) -> None:
        """清除所有记忆。"""
        with self._lock:
            self._working.clear()
            self._episodic.clear()
            self._long_term.clear()
