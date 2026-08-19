"""IdentitySQLiteStore — IdentityAnchor 的 SQLite 持久化存储。

Phase 21: 身份锚点持久化——解决 AR-1。
"""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

from ocos.agent.identity_anchor import IdentityAnchor

logger = logging.getLogger(__name__)

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS identity (
    agent_id TEXT PRIMARY KEY,
    born_at TEXT NOT NULL,
    owner_id TEXT,
    name TEXT NOT NULL DEFAULT 'OCOS Agent',
    version TEXT NOT NULL DEFAULT '1.0.0',
    self_view_json TEXT NOT NULL DEFAULT '{}',
    state_json TEXT NOT NULL DEFAULT '{}',
    anchor_json TEXT NOT NULL DEFAULT '{}',
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


class IdentitySQLiteStore:
    """IdentityAnchor SQLite 持久化存储。

    使用示例:
        store = IdentitySQLiteStore("~/.ocos/db/ocos.db")
        store.initialize()
        store.save(identity)
        restored = store.load("agent-001")
    """

    def __init__(self, db_path: str | Path) -> None:
        self._db_path = str(db_path)
        self._conn: Optional[sqlite3.Connection] = None

    # ── 生命周期 ────────────────────────────────────────────────────────────

    def initialize(self) -> None:
        """创建表结构。幂等。"""
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute(_CREATE_TABLE_SQL)
        self._conn.commit()
        logger.info("IdentitySQLiteStore initialized at %s", self._db_path)

    def close(self) -> None:
        """关闭连接。"""
        if self._conn:
            self._conn.close()
            self._conn = None

    @property
    def connection(self) -> sqlite3.Connection:
        if self._conn is None:
            raise RuntimeError("IdentitySQLiteStore not initialized. Call initialize() first.")
        return self._conn

    # ── CRUD ────────────────────────────────────────────────────────────────

    def save(self, identity: IdentityAnchor) -> None:
        """保存或更新 IdentityAnchor。

        使用 INSERT OR REPLACE 确保幂等。
        """
        d = identity.to_dict()
        self.connection.execute(
            """INSERT OR REPLACE INTO identity
               (agent_id, born_at, owner_id, name, version,
                self_view_json, state_json, anchor_json, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                d["agent_id"],
                d["born_at"],
                d["owner_id"],
                d["name"],
                d["version"],
                d["self_view"],
                d["state"],
                d["anchor"],
                datetime.utcnow().isoformat(),
            ),
        )
        self.connection.commit()
        logger.debug("Identity saved: %s", d["agent_id"])

    def load(self, agent_id: str) -> Optional[IdentityAnchor]:
        """从数据库加载 IdentityAnchor。

        返回 None 如果不存在。
        """
        row = self.connection.execute(
            "SELECT * FROM identity WHERE agent_id = ?", (agent_id,)
        ).fetchone()
        if row is None:
            return None
        return IdentityAnchor.from_dict(dict(row))

    def exists(self, agent_id: str) -> bool:
        """检查 identity 是否存在。"""
        row = self.connection.execute(
            "SELECT 1 FROM identity WHERE agent_id = ? LIMIT 1", (agent_id,)
        ).fetchone()
        return row is not None

    def delete(self, agent_id: str) -> bool:
        """删除 identity 记录。返回是否实际删除。"""
        cur = self.connection.execute(
            "DELETE FROM identity WHERE agent_id = ?", (agent_id,)
        )
        self.connection.commit()
        return cur.rowcount > 0
