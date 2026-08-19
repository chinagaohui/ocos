"""Phase 24.3-B — SemanticStore。

SQLite 持久化的 KnowledgeEntry 存储层。

约束:
    - Append-oriented: Knowledge 通过 supersede 升级而非原地修改
    - 查询: by_domain / by_confidence / by_stability / by_status / by_lineage
    - 禁止删除 (只能 DEPRECATED)
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from ocos.memory.semantic.models import KnowledgeEntry, KnowledgeScope, KnowledgeStatus


class SemanticStore:
    """KnowledgeEntry SQLite 持久化存储。"""

    def __init__(self, db_path: str | Path = ":memory:") -> None:
        self._db_path = str(db_path)
        self._conn: Optional[sqlite3.Connection] = None

    def initialize(self) -> None:
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.executescript(_DDL)

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    def __enter__(self):
        self.initialize()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False

    @property
    def connection(self) -> sqlite3.Connection:
        if self._conn is None:
            raise RuntimeError("SemanticStore not initialized. Call initialize() first.")
        return self._conn

    # ── CRUD ─────────────────────────────────────────────────────────────────

    def save(self, entry: KnowledgeEntry) -> None:
        """保存 KnowledgeEntry。如果 lineaged from 旧版本，deprecate 旧版本。"""
        # 如果一个旧版本被 superseded，标记旧版本
        if entry.revision > 1:
            self.connection.execute(
                "UPDATE knowledge SET status = ? WHERE id = ?",
                (KnowledgeStatus.SUPERSEDED.value, entry.id),
            )

        self.connection.execute(
            """
            INSERT INTO knowledge (
                id, statement, source_patterns, confidence,
                scope_domain, scope_preconditions, scope_limitations,
                scope_counterexamples, stability, revision, status,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                entry.id,
                entry.statement,
                json.dumps(list(entry.source_patterns), ensure_ascii=False),
                entry.confidence,
                entry.scope.domain,
                json.dumps(list(entry.scope.preconditions), ensure_ascii=False),
                json.dumps(list(entry.scope.limitations), ensure_ascii=False),
                entry.scope.counterexamples,
                entry.stability,
                entry.revision,
                entry.status.value,
                entry.created_at.isoformat(),
                entry.updated_at.isoformat() if entry.updated_at else None,
            ),
        )
        self.connection.commit()

    def get(self, entry_id: str) -> Optional[KnowledgeEntry]:
        row = self.connection.execute(
            "SELECT * FROM knowledge WHERE id = ?", (entry_id,)
        ).fetchone()
        return self._row_to_entry(row) if row else None

    def count(self) -> int:
        row = self.connection.execute("SELECT COUNT(*) as cnt FROM knowledge").fetchone()
        return row["cnt"] if row else 0

    def deprecate(self, entry_id: str) -> bool:
        cursor = self.connection.execute(
            "UPDATE knowledge SET status = ? WHERE id = ? AND status = ?",
            (KnowledgeStatus.DEPRECATED.value, entry_id, KnowledgeStatus.ACTIVE.value),
        )
        self.connection.commit()
        return cursor.rowcount > 0

    # ── 查询 ─────────────────────────────────────────────────────────────────

    def query_by_domain(
        self,
        domain: str,
        limit: int = 50,
        active_only: bool = True,
    ) -> list[KnowledgeEntry]:
        """按领域查询。"""
        query = "SELECT * FROM knowledge WHERE scope_domain = ?"
        params: list = [domain]
        if active_only:
            query += " AND status = ?"
            params.append(KnowledgeStatus.ACTIVE.value)
        query += " ORDER BY confidence DESC LIMIT ?"
        params.append(limit)

        rows = self.connection.execute(query, params).fetchall()
        return [self._row_to_entry(r) for r in rows if r]

    def query_by_confidence(
        self,
        min_confidence: float = 0.5,
        limit: int = 50,
        active_only: bool = True,
    ) -> list[KnowledgeEntry]:
        """按置信度查询。"""
        query = "SELECT * FROM knowledge WHERE confidence >= ?"
        params: list = [min_confidence]
        if active_only:
            query += " AND status = ?"
            params.append(KnowledgeStatus.ACTIVE.value)
        query += " ORDER BY confidence DESC LIMIT ?"
        params.append(limit)

        rows = self.connection.execute(query, params).fetchall()
        return [self._row_to_entry(r) for r in rows if r]

    def query_by_stability(
        self,
        min_stability: float = 0.5,
        limit: int = 50,
        active_only: bool = True,
    ) -> list[KnowledgeEntry]:
        """按稳定度查询。"""
        query = "SELECT * FROM knowledge WHERE stability >= ?"
        params: list = [min_stability]
        if active_only:
            query += " AND status = ?"
            params.append(KnowledgeStatus.ACTIVE.value)
        query += " ORDER BY stability DESC LIMIT ?"
        params.append(limit)

        rows = self.connection.execute(query, params).fetchall()
        return [self._row_to_entry(r) for r in rows if r]

    def query_by_status(
        self,
        status: KnowledgeStatus,
        limit: int = 50,
    ) -> list[KnowledgeEntry]:
        """按状态查询 (含非 active)。"""
        rows = self.connection.execute(
            "SELECT * FROM knowledge WHERE status = ? ORDER BY created_at DESC LIMIT ?",
            (status.value, limit),
        ).fetchall()
        return [self._row_to_entry(r) for r in rows if r]

    def query_by_lineage(
        self,
        pattern_id: str,
        limit: int = 50,
    ) -> list[KnowledgeEntry]:
        """按证据链追溯 — 找出引用此 Pattern 的所有 Knowledge。"""
        rows = self.connection.execute(
            """
            SELECT * FROM knowledge
            WHERE source_patterns LIKE ?
            ORDER BY confidence DESC LIMIT ?
            """,
            (f"%{pattern_id}%", limit),
        ).fetchall()
        return [self._row_to_entry(r) for r in rows if r]

    def get_all_active(self, limit: int = 50) -> list[KnowledgeEntry]:
        """获取所有活跃 Knowledge。"""
        rows = self.connection.execute(
            "SELECT * FROM knowledge WHERE status = ? ORDER BY confidence DESC LIMIT ?",
            (KnowledgeStatus.ACTIVE.value, limit),
        ).fetchall()
        return [self._row_to_entry(r) for r in rows if r]

    # ── 内部 ─────────────────────────────────────────────────────────────────

    def _row_to_entry(self, row: sqlite3.Row) -> KnowledgeEntry:
        scope = KnowledgeScope(
            domain=row["scope_domain"],
            preconditions=tuple(json.loads(row["scope_preconditions"])),
            limitations=tuple(json.loads(row["scope_limitations"])),
            counterexamples=row["scope_counterexamples"],
        )

        return KnowledgeEntry(
            id=row["id"],
            statement=row["statement"],
            source_patterns=tuple(json.loads(row["source_patterns"])),
            confidence=row["confidence"],
            scope=scope,
            stability=row["stability"],
            revision=row["revision"],
            status=KnowledgeStatus(row["status"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=(
                datetime.fromisoformat(row["updated_at"])
                if row["updated_at"] else None
            ),
        )


# ── DDL ──────────────────────────────────────────────────────────────────────

_DDL = """
CREATE TABLE IF NOT EXISTS knowledge (
    id                      TEXT PRIMARY KEY,
    statement               TEXT NOT NULL,
    source_patterns         TEXT NOT NULL DEFAULT '[]',   -- JSON array
    confidence              REAL NOT NULL DEFAULT 0.0,
    scope_domain            TEXT NOT NULL DEFAULT '',
    scope_preconditions     TEXT NOT NULL DEFAULT '[]',   -- JSON array
    scope_limitations       TEXT NOT NULL DEFAULT '[]',   -- JSON array
    scope_counterexamples   INTEGER NOT NULL DEFAULT 0,
    stability               REAL NOT NULL DEFAULT 0.0,
    revision                INTEGER NOT NULL DEFAULT 1,
    status                  TEXT NOT NULL DEFAULT 'active',
    created_at              TEXT NOT NULL,
    updated_at              TEXT
);

CREATE INDEX IF NOT EXISTS idx_knowledge_domain
    ON knowledge(scope_domain, confidence DESC);

CREATE INDEX IF NOT EXISTS idx_knowledge_confidence
    ON knowledge(confidence DESC);

CREATE INDEX IF NOT EXISTS idx_knowledge_stability
    ON knowledge(stability DESC);

CREATE INDEX IF NOT EXISTS idx_knowledge_status
    ON knowledge(status);

CREATE INDEX IF NOT EXISTS idx_knowledge_created
    ON knowledge(created_at DESC);
"""
