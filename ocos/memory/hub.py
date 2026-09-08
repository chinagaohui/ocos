"""MemoryHub — 统一记忆持久化中枢。

Phase 21: 统一管理所有 Memory Store 的 db_path 和生命周期。
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional
from uuid import uuid4

from ocos.memory.episode.store import EpisodeStore
from ocos.memory.belief.store import BeliefStore
from ocos.memory.semantic.store import SemanticStore
from ocos.memory.pattern.store import PatternStore

logger = logging.getLogger(__name__)


class MemoryHub:
    """统一记忆持久化中枢。

    单例持有 db_path，负责：
      - 初始化所有 Memory Store
      - 统一数据库路径（共享 SQLite WAL）
      - 生命周期管理

    使用示例:
        hub = MemoryHub("~/.ocos/db/ocos.db")
        hub.initialize()
        hub.episode.save(...)
        hub.shutdown()
    """

    def __init__(self, db_path: str | Path = ":memory:") -> None:
        self._db_path = str(db_path)
        # O-2: sqlite3 下 ":memory:" 每个连接各得一个私有内存库，四 Store
        # 会静默分裂。改用 per-hub shared-cache URI：同一 Hub 内四库共享
        # 同一内存库，不同 Hub 实例之间仍相互隔离。
        if self._db_path == ":memory:":
            self._store_path = f"file:memhub-{uuid4().hex}?mode=memory&cache=shared"
        else:
            self._store_path = self._db_path
        self._episode: Optional[EpisodeStore] = None
        self._belief: Optional[BeliefStore] = None
        self._semantic: Optional[SemanticStore] = None
        self._pattern: Optional[PatternStore] = None
        self._initialized = False

    # ── Properties ──────────────────────────────────────────────────────────

    @property
    def db_path(self) -> str:
        return self._db_path

    @property
    def episode(self) -> EpisodeStore:
        if self._episode is None:
            raise RuntimeError("MemoryHub not initialized. Call initialize() first.")
        return self._episode

    @property
    def belief(self) -> BeliefStore:
        if self._belief is None:
            raise RuntimeError("MemoryHub not initialized. Call initialize() first.")
        return self._belief

    @property
    def semantic(self) -> SemanticStore:
        if self._semantic is None:
            raise RuntimeError("MemoryHub not initialized. Call initialize() first.")
        return self._semantic

    @property
    def pattern(self) -> PatternStore:
        if self._pattern is None:
            raise RuntimeError("MemoryHub not initialized. Call initialize() first.")
        return self._pattern

    # ── 生命周期 ────────────────────────────────────────────────────────────

    def initialize(self) -> None:
        """初始化所有 Memory Store。

        使用共享 SQLite 文件——各 Store 经连接池共享同一连接，
        并共享同一个 WAL journal 以保证并发安全。
        ":memory:" 时使用 per-hub shared-cache URI（O-2），四库同库不分裂。
        """
        self._episode = EpisodeStore(self._store_path)
        self._belief = BeliefStore(self._store_path)
        self._semantic = SemanticStore(self._store_path)
        self._pattern = PatternStore(self._store_path)

        self._episode.initialize()
        self._belief.initialize()
        self._semantic.initialize()
        self._pattern.initialize()

        self._initialized = True
        logger.info("MemoryHub initialized at %s", self._db_path)

    def shutdown(self) -> None:
        """关闭所有 Store 连接。"""
        for store in [self._episode, self._belief, self._semantic, self._pattern]:
            if store is not None:
                store.close()
        # O-8: 置空引用——shutdown 后经 property 访问得到明确的
        # RuntimeError，而非已关闭连接的裸 sqlite3.ProgrammingError
        self._episode = None
        self._belief = None
        self._semantic = None
        self._pattern = None
        self._initialized = False
        logger.info("MemoryHub shutdown complete.")

    def is_initialized(self) -> bool:
        return self._initialized

    # ── 统计 ────────────────────────────────────────────────────────────────

    def get_stats(self) -> dict:
        """获取各 Store 统计信息。"""
        if not self._initialized:
            return {"initialized": False}
        return {
            "initialized": True,
            "episode_count": self._episode.count() if self._episode else 0,
            "belief_count": self._belief.count_by_status().get("active", 0) if self._belief else 0,
            "semantic_count": self._semantic.count() if self._semantic else 0,
            "pattern_count": self._pattern.count() if self._pattern else 0,
        }
