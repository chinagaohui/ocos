"""Phase 24.4-C — BeliefStore。

Belief 的 SQLite 持久化 + 查询 + 生命周期管理。

约束:
    - Query 只读取，不驱动行为
    - Retrieval 不生成 Goal
    - Belief 不参与 Authority
    - 可 archive / weaken / invalidate，禁止 delete
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from ocos.storage.connection import get_connection
from ocos.memory.belief.models import Belief, BeliefStatus


# ── DDL ──────────────────────────────────────────────────────────────────────

_DDL = """
CREATE TABLE IF NOT EXISTS belief (
    id                      TEXT PRIMARY KEY,
    statement               TEXT NOT NULL,
    source_knowledge_ids     TEXT NOT NULL,  -- JSON array
    evidence_ids            TEXT NOT NULL,  -- JSON array
    confidence              REAL NOT NULL,
    uncertainty             REAL NOT NULL,
    scope                   TEXT NOT NULL,  -- JSON dict
    status                  TEXT NOT NULL DEFAULT 'active',
    created_at              TEXT NOT NULL,
    last_updated            TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_belief_status   ON belief(status);
CREATE INDEX IF NOT EXISTS idx_belief_confidence ON belief(confidence);
CREATE INDEX IF NOT EXISTS idx_belief_created   ON belief(created_at);
CREATE INDEX IF NOT EXISTS idx_belief_domain    ON belief(json_extract(scope, '$.domain'));
"""


class BeliefStore:
    """Belief 持久化存储 (append-oriented, 禁止删除)。

    操作:
        save — 持久化 Belief
        get  — 按 ID 查询
        weaken / invalidate / archive — 生命周期状态变更
        query_by_status / query_by_confidence / query_by_domain / query_by_lineage
    """

    def __init__(self, db_path: str | Path = ":memory:") -> None:
        self._db_path = str(db_path)
        self._conn: Optional[sqlite3.Connection] = None

    def initialize(self) -> None:
        self._conn = get_connection(self._db_path)
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
            raise RuntimeError("BeliefStore not initialized. Call initialize() first.")
        return self._conn

    # ── CRUD ─────────────────────────────────────────────────────────────────

    def save(self, belief: Belief) -> None:
        """保存 Belief（幂等 — 如果 ID 已存在则 update）。"""
        self.connection.execute(
            """
            INSERT OR REPLACE INTO belief (
                id, statement, source_knowledge_ids, evidence_ids,
                confidence, uncertainty, scope, status, created_at, last_updated
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                belief.id,
                belief.statement,
                json.dumps(list(belief.source_knowledge_ids)),
                json.dumps(list(belief.evidence_ids)),
                belief.confidence,
                belief.uncertainty,
                json.dumps(belief.scope),
                belief.status.value,
                belief.created_at.isoformat(),
                belief.last_updated.isoformat(),
            ),
        )
        self.connection.commit()

    def get(self, belief_id: str) -> Optional[Belief]:
        """按 ID 获取 Belief。"""
        row = self.connection.execute(
            "SELECT * FROM belief WHERE id = ?", (belief_id,)
        ).fetchone()
        if row is None:
            return None
        return self._row_to_belief(row)

    # ── 生命周期 ───────────────────────────────────────────────────────────

    def weaken(self, belief_id: str) -> Optional[Belief]:
        """降低 Belief 为 WEAKENED，提高 uncertainty。"""
        belief = self.get(belief_id)
        if belief is None:
            return None
        weakened = belief.weaken()
        self.save(weakened)
        return weakened

    def invalidate(self, belief_id: str) -> Optional[Belief]:
        """标记 Belief 为 INVALIDATED。"""
        belief = self.get(belief_id)
        if belief is None:
            return None
        invalidated = belief.invalidate()
        self.save(invalidated)
        return invalidated

    def archive(self, belief_id: str) -> Optional[Belief]:
        """归档 Belief (不参与后续推理)。"""
        belief = self.get(belief_id)
        if belief is None:
            return None
        archived = belief.archive()
        self.save(archived)
        return archived

    # ── 查询 ───────────────────────────────────────────────────────────────

    def query_by_status(self, status: BeliefStatus, limit: int = 50) -> list[Belief]:
        """按状态查询。"""
        rows = self.connection.execute(
            "SELECT * FROM belief WHERE status = ? ORDER BY created_at DESC LIMIT ?",
            (status.value, limit),
        ).fetchall()
        return [self._row_to_belief(r) for r in rows]

    def query_by_confidence(
        self, min_confidence: float = 0.0, max_confidence: float = 1.0, limit: int = 50
    ) -> list[Belief]:
        """按置信度范围查询。"""
        rows = self.connection.execute(
            "SELECT * FROM belief WHERE confidence BETWEEN ? AND ? "
            "ORDER BY confidence DESC LIMIT ?",
            (min_confidence, max_confidence, limit),
        ).fetchall()
        return [self._row_to_belief(r) for r in rows]

    def query_by_domain(self, domain: str, limit: int = 50) -> list[Belief]:
        """按 domain 查询。"""
        rows = self.connection.execute(
            "SELECT * FROM belief WHERE json_extract(scope, '$.domain') = ? "
            "ORDER BY confidence DESC LIMIT ?",
            (domain, limit),
        ).fetchall()
        return [self._row_to_belief(r) for r in rows]

    def query_by_lineage(self, knowledge_id: str, limit: int = 50) -> list[Belief]:
        """按源 Knowledge ID 查询。"""
        rows = self.connection.execute(
            "SELECT * FROM belief WHERE source_knowledge_ids LIKE ? "
            "ORDER BY created_at DESC LIMIT ?",
            (f"%{knowledge_id}%", limit),
        ).fetchall()
        return [self._row_to_belief(r) for r in rows]

    def get_all_active(self, limit: int = 100) -> list[Belief]:
        """获取所有活跃 Belief (按 confidence 降序)。"""
        return self.query_by_status(BeliefStatus.ACTIVE, limit=limit)

    def count_by_status(self) -> dict[str, int]:
        """统计各状态 Belief 数量。"""
        rows = self.connection.execute(
            "SELECT status, COUNT(*) as cnt FROM belief GROUP BY status"
        ).fetchall()
        return {r["status"]: r["cnt"] for r in rows}

    # ── 内部 ───────────────────────────────────────────────────────────────

    @staticmethod
    def _row_to_belief(row: sqlite3.Row) -> Belief:
        return Belief(
            id=row["id"],
            statement=row["statement"],
            source_knowledge_ids=tuple(json.loads(row["source_knowledge_ids"])),
            evidence_ids=tuple(json.loads(row["evidence_ids"])),
            confidence=row["confidence"],
            uncertainty=row["uncertainty"],
            scope=json.loads(row["scope"]),
            status=BeliefStatus(row["status"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            last_updated=datetime.fromisoformat(row["last_updated"]),
        )
