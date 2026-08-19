"""IdentityStore — Agent 身份持久化存储。

Phase 21→22 桥接模块。Phase 22 MasterAgent.boot() 依赖此模块
在启动时加载自己的身份记录。

ABI 兼容：v1.0 向后，v2.0 前不破坏。
"""
from __future__ import annotations

import sqlite3
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class AgentIdentityRecord:
    """Agent 身份记录——谁、属于谁、从哪来。"""

    agent_id: str
    name: str = "OCOS"
    owner_user_id: str = ""
    type: str = "master_agent"
    version: str = "1.0.0"
    identity_doc_version: str = "1.0"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_boot: Optional[datetime] = None
    manifest_url: str = "docs/MANIFESTO.md"
    constitution_version: str = "1.0"


class IdentityStore:
    """Agent 身份持久化存储（SQLite）。

    Phase 23-B: 使用 storage.connection 连接池，避免连接泄漏。
    """

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        self._owns_connection = False
        try:
            from ocos.storage.connection import get_connection as _get_conn
            self._conn = _get_conn(db_path)
        except ImportError:
            self._conn = sqlite3.connect(db_path)
            self._owns_connection = True
            self._conn.execute("PRAGMA journal_mode=WAL")
        self._init_schema()

    def _init_schema(self) -> None:
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS agent_identity (
                agent_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                owner_user_id TEXT NOT NULL DEFAULT '',
                type TEXT NOT NULL DEFAULT 'master_agent',
                version TEXT NOT NULL DEFAULT '1.0.0',
                identity_doc_version TEXT NOT NULL DEFAULT '1.0',
                created_at TEXT NOT NULL,
                last_boot TEXT,
                manifest_url TEXT NOT NULL DEFAULT 'docs/MANIFESTO.md',
                constitution_version TEXT NOT NULL DEFAULT '1.0'
            )
            """
        )
        self._conn.commit()

    def save(self, record: AgentIdentityRecord) -> str:
        """持久化身份记录。已存在则覆盖。"""
        self._conn.execute(
            """
            INSERT OR REPLACE INTO agent_identity
                (agent_id, name, owner_user_id, type, version,
                 identity_doc_version, created_at, last_boot,
                 manifest_url, constitution_version)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.agent_id,
                record.name,
                record.owner_user_id,
                record.type,
                record.version,
                record.identity_doc_version,
                record.created_at.isoformat(),
                record.last_boot.isoformat() if record.last_boot else None,
                record.manifest_url,
                record.constitution_version,
            ),
        )
        self._conn.commit()
        return record.agent_id

    def load(self, agent_id: str) -> Optional[AgentIdentityRecord]:
        """按 agent_id 加载身份记录。"""
        row = self._conn.execute(
            "SELECT * FROM agent_identity WHERE agent_id = ?",
            (agent_id,),
        ).fetchone()
        if row is None:
            return None
        return self._row_to_record(row)

    def update_last_boot(self, agent_id: str) -> None:
        """更新最后启动时间。"""
        now = datetime.now(timezone.utc).isoformat()
        self._conn.execute(
            "UPDATE agent_identity SET last_boot = ? WHERE agent_id = ?",
            (now, agent_id),
        )
        self._conn.commit()

    def verify_identity(self, agent_id: str) -> bool:
        """验证 agent_id 是否存在且有效。"""
        row = self._conn.execute(
            "SELECT 1 FROM agent_identity WHERE agent_id = ?",
            (agent_id,),
        ).fetchone()
        return row is not None

    def list(self) -> list[AgentIdentityRecord]:
        """列出所有身份记录。"""
        rows = self._conn.execute(
            "SELECT * FROM agent_identity ORDER BY created_at"
        ).fetchall()
        return [self._row_to_record(r) for r in rows]

    def delete(self, agent_id: str) -> bool:
        """删除身份记录。"""
        cur = self._conn.execute(
            "DELETE FROM agent_identity WHERE agent_id = ?",
            (agent_id,),
        )
        self._conn.commit()
        return cur.rowcount > 0

    def close(self) -> None:
        """关闭数据库连接（仅关闭自己创建的连接）。

        Phase 23-B: 池化管理时不自闭（由 storage.connection.close_all 统一关闭）。
        """
        if self._owns_connection:
            try:
                self._conn.close()
            except Exception:
                pass
        self._conn = None  # type: ignore[assignment]

    def __enter__(self) -> IdentityStore:
        """上下文管理器进入。"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """上下文管理器退出 — 自动关闭连接。"""
        self.close()

    @staticmethod
    def _row_to_record(row: sqlite3.Row) -> AgentIdentityRecord:
        return AgentIdentityRecord(
            agent_id=row[0],
            name=row[1],
            owner_user_id=row[2],
            type=row[3],
            version=row[4],
            identity_doc_version=row[5],
            created_at=datetime.fromisoformat(row[6]),
            last_boot=datetime.fromisoformat(row[7]) if row[7] else None,
            manifest_url=row[8],
            constitution_version=row[9],
        )
