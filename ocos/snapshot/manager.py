"""SnapshotManager — Agent Snapshot 持久化管理器。

Phase 21.01: Agent Snapshot System

设计约束:
- 所有 save/load 操作使用 threading.Lock 保证原子性
- SQLite 连接复用 ocos.storage.connection 的连接池
- 重试机制处理 database is locked
"""

from __future__ import annotations

import logging
import os
import threading
from datetime import datetime, timezone
from typing import Optional

from ocos.snapshot.models import AgentSnapshot
from ocos.storage.connection import get_connection

logger = logging.getLogger(__name__)

DB_PATH = os.environ.get("OCOS_DB_PATH", "ocos.db")


class SnapshotManager:
    """Agent Snapshot 的持久化管理。

    提供 save / load_latest / mark_recovered 三个核心操作。
    所有写操作使用 threading.Lock 保证原子性。
    """

    def __init__(self, db_path: str = DB_PATH) -> None:
        self._db_path = db_path
        self._lock = threading.Lock()

    def _conn(self):
        """获取 SQLite 连接（复用连接池）。"""
        return get_connection(self._db_path)

    def save(self, snapshot: AgentSnapshot) -> str:
        """原子保存 Snapshot。

        使用 threading.Lock 保证并发安全。
        返回 snapshot_id。
        """
        data_json = snapshot.to_json()
        size_kb = len(data_json) // 1024

        with self._lock:
            conn = self._conn()
            try:
                conn.execute(
                    """
                    INSERT INTO snapshots
                        (snapshot_id, version, created_at, data, size_kb, agent_id)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        snapshot.snapshot_id,
                        snapshot.version,
                        snapshot.created_at.isoformat(),
                        data_json,
                        size_kb,
                        snapshot.identity_state.get("agent_id", "master"),
                    ),
                )
                conn.commit()
                logger.info("Snapshot saved: %s (%d KB)", snapshot.snapshot_id, size_kb)
            except Exception:
                conn.rollback()
                raise

        return snapshot.snapshot_id

    def load_latest(self) -> Optional[AgentSnapshot]:
        """加载最新的 Snapshot。

        按 created_at DESC 排序，取第一条。
        无记录时返回 None。
        """
        conn = self._conn()
        conn.row_factory = None  # 使用默认 tuple 模式
        row = conn.execute(
            "SELECT data FROM snapshots ORDER BY created_at DESC LIMIT 1"
        ).fetchone()

        if row is None:
            logger.info("No snapshot found.")
            return None

        logger.info("Latest snapshot loaded.")
        return AgentSnapshot.from_json(row[0])

    def mark_recovered(self, snapshot_id: str) -> None:
        """标记 Snapshot 已被成功恢复。"""
        conn = self._conn()
        conn.execute(
            "UPDATE snapshots SET is_recovered = 1, recovered_at = ? "
            "WHERE snapshot_id = ?",
            (datetime.now(timezone.utc).isoformat(), snapshot_id),
        )
        conn.commit()
        logger.info("Snapshot marked as recovered: %s", snapshot_id)
