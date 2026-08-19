"""PatternStore — Pattern 的 SQLite 持久化存储。

Phase 21: Pattern 持久化——补全 Memory 层 SQLite 覆盖。
"""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from ocos.memory.pattern.models import PatternCandidate, PatternStatus

logger = logging.getLogger(__name__)

_DDL = """
CREATE TABLE IF NOT EXISTS pattern (
    id                      TEXT PRIMARY KEY,
    trigger_condition       TEXT NOT NULL,
    observed_relation       TEXT NOT NULL,
    causal_explanation      TEXT NOT NULL,
    confidence              REAL NOT NULL,
    supporting_episode_count INTEGER NOT NULL,
    source                  TEXT NOT NULL DEFAULT 'episode_aggregation',
    status                  TEXT NOT NULL DEFAULT 'candidate',
    created_at              TEXT NOT NULL,
    validated_at            TEXT,             -- 仅 VALIDATED 状态
    validation_notes        TEXT DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_pattern_status ON pattern(status);
CREATE INDEX IF NOT EXISTS idx_pattern_confidence ON pattern(confidence DESC);
CREATE INDEX IF NOT EXISTS idx_pattern_created ON pattern(created_at);
"""


class PatternStore:
    """Pattern SQLite 持久化存储。

    支持 PatternCandidate（候选）和 Pattern（已验证）混合存储。
    validated_at 字段只在 status='validated' 时非 NULL。
    """

    def __init__(self, db_path: str | Path = ":memory:") -> None:
        self._db_path = str(db_path)
        self._conn: Optional[sqlite3.Connection] = None

    # ── 生命周期 ────────────────────────────────────────────────────────────

    def initialize(self) -> None:
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.executescript(_DDL)
        logger.info("PatternStore initialized at %s", self._db_path)

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    @property
    def connection(self) -> sqlite3.Connection:
        if self._conn is None:
            raise RuntimeError("PatternStore not initialized. Call initialize() first.")
        return self._conn

    # ── CRUD ────────────────────────────────────────────────────────────────

    def save(self, pattern: PatternCandidate) -> None:
        """保存 PatternCandidate。幂等（INSERT OR REPLACE）。"""
        validated_at = None
        validation_notes = ""
        if hasattr(pattern, "validated_at"):
            validated_at = pattern.validated_at.isoformat()
        if hasattr(pattern, "validation_notes"):
            validation_notes = getattr(pattern, "validation_notes", "")

        self.connection.execute(
            """INSERT OR REPLACE INTO pattern
               (id, trigger_condition, observed_relation, causal_explanation,
                confidence, supporting_episode_count, source, status,
                created_at, validated_at, validation_notes)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                pattern.id,
                pattern.trigger_condition,
                pattern.observed_relation,
                pattern.causal_explanation,
                pattern.confidence,
                pattern.supporting_episode_count,
                pattern.source if hasattr(pattern, "source") else "episode_aggregation",
                pattern.status.value,
                pattern.created_at.isoformat(),
                validated_at,
                validation_notes,
            ),
        )
        self.connection.commit()

    def get(self, pattern_id: str) -> Optional[PatternCandidate]:
        """按 ID 获取 Pattern。"""
        row = self.connection.execute(
            "SELECT * FROM pattern WHERE id = ?", (pattern_id,)
        ).fetchone()
        if row is None:
            return None
        return self._row_to_pattern(row)

    def query_by_status(
        self, status: PatternStatus, limit: int = 50
    ) -> list[PatternCandidate]:
        """按状态查询 Patterns。"""
        rows = self.connection.execute(
            "SELECT * FROM pattern WHERE status = ? ORDER BY confidence DESC LIMIT ?",
            (status.value, limit),
        ).fetchall()
        return [self._row_to_pattern(r) for r in rows]

    def query_highest_confidence(self, limit: int = 10) -> list[PatternCandidate]:
        """查询置信度最高的 Patterns（不限状态）。"""
        rows = self.connection.execute(
            "SELECT * FROM pattern ORDER BY confidence DESC LIMIT ?", (limit,)
        ).fetchall()
        return [self._row_to_pattern(r) for r in rows]

    def count(self, status: Optional[PatternStatus] = None) -> int:
        """统计 Pattern 数量。"""
        if status:
            row = self.connection.execute(
                "SELECT COUNT(*) as cnt FROM pattern WHERE status = ?",
                (status.value,),
            ).fetchone()
        else:
            row = self.connection.execute(
                "SELECT COUNT(*) as cnt FROM pattern"
            ).fetchone()
        return row["cnt"] if row else 0

    def update_status(
        self, pattern_id: str, status: PatternStatus
    ) -> bool:
        """更新 Pattern 状态。"""
        cur = self.connection.execute(
            "UPDATE pattern SET status = ? WHERE id = ?",
            (status.value, pattern_id),
        )
        self.connection.commit()
        return cur.rowcount > 0

    # ── Internal ────────────────────────────────────────────────────────────

    def _row_to_pattern(self, row: sqlite3.Row) -> PatternCandidate:
        d = dict(row)
        status = PatternStatus(d["status"])
        created_at = datetime.fromisoformat(d["created_at"])
        return PatternCandidate(
            id=d["id"],
            trigger_condition=d["trigger_condition"],
            observed_relation=d["observed_relation"],
            causal_explanation=d["causal_explanation"],
            confidence=d["confidence"],
            supporting_episode_count=d["supporting_episode_count"],
            source=d.get("source", "episode_aggregation"),
            status=status,
            created_at=created_at,
        )
