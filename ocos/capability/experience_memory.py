"""Phase 25-B: Capability Experience Memory。

Freeze §4.4.3 — SQLite-backed experience store。
每次 Agent 执行完成后记录 ExperienceNode，按 Provider/Capability 查询历史表现。
与 Memory 层（ocos.memory.*）完全隔离。
"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Any

from ocos.logging import get_logger

from .knowledge_graph import ExperienceNode

logger = get_logger(__name__)


@dataclass
class CapabilityExperienceMemory:
    """能力经验记忆库（SQLite）。

    Freeze §4.4.3 设计:
      - 每次 Agent 执行完成后写入一条 ExperienceNode
      - 支持按 capability / provider / task_type 查询
      - 支持统计聚合（成功率、平均质量、平均耗时）
      - 与 ocos.memory 层完全隔离（独立数据库）
    """

    db_path: str = ":memory:"

    _conn: sqlite3.Connection | None = field(default=None, repr=False)
    _lock: Lock = field(default_factory=Lock, repr=False)

    # ── lifecycle ─────────────────────────────────────────────────────────

    def connect(self) -> None:
        with self._lock:
            if self._conn is not None:
                return
            # Ensure directory exists for file-based DBs
            if self.db_path != ":memory:":
                Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._create_schema()

    def close(self) -> None:
        with self._lock:
            if self._conn is not None:
                self._conn.close()
                self._conn = None

    @contextmanager
    def _cursor(self):
        if self._conn is None:
            self.connect()
        assert self._conn is not None
        with self._lock:
            cursor = self._conn.execute("BEGIN IMMEDIATE")
            try:
                yield self._conn
                self._conn.commit()
            except Exception:
                self._conn.rollback()
                raise

    # ── schema ─────────────────────────────────────────────────────────────

    def _create_schema(self) -> None:
        assert self._conn is not None
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS experiences (
                id              TEXT PRIMARY KEY,
                task_type       TEXT NOT NULL,
                capability_id   TEXT NOT NULL,
                provider_id     TEXT NOT NULL,
                outcome         TEXT NOT NULL DEFAULT 'success',
                quality_score   REAL NOT NULL DEFAULT 0.0,
                duration_ms     INTEGER NOT NULL DEFAULT 0,
                user_satisfaction REAL NOT NULL DEFAULT 0.0,
                timestamp       TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_exp_capability ON experiences(capability_id);
            CREATE INDEX IF NOT EXISTS idx_exp_provider ON experiences(provider_id);
            CREATE INDEX IF NOT EXISTS idx_exp_task_type ON experiences(task_type);
            CREATE INDEX IF NOT EXISTS idx_exp_timestamp ON experiences(timestamp);
        """)

    # ── CRUD ───────────────────────────────────────────────────────────────

    def save(self, experience: ExperienceNode) -> None:
        """写入一条经验记录."""
        with self._cursor() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO experiences
                   (id, task_type, capability_id, provider_id, outcome,
                    quality_score, duration_ms, user_satisfaction, timestamp)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    experience.experience_id,
                    experience.task_type,
                    experience.capability_id,
                    experience.provider_id,
                    experience.outcome,
                    experience.quality_score,
                    experience.duration_ms,
                    experience.user_satisfaction,
                    experience.timestamp.isoformat(),
                ),
            )
        logger.debug("saved experience %s", experience.experience_id)

    def save_batch(self, experiences: list[ExperienceNode]) -> None:
        """批量写入."""
        with self._cursor() as conn:
            conn.executemany(
                """INSERT OR REPLACE INTO experiences
                   (id, task_type, capability_id, provider_id, outcome,
                    quality_score, duration_ms, user_satisfaction, timestamp)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                [
                    (e.experience_id, e.task_type, e.capability_id, e.provider_id,
                     e.outcome, e.quality_score, e.duration_ms, e.user_satisfaction,
                     e.timestamp.isoformat())
                    for e in experiences
                ],
            )

    # ── queries ────────────────────────────────────────────────────────────

    def query_by_capability(self, capability_id: str, limit: int = 100) -> list[dict[str, Any]]:
        return self._fetch_all(
            "SELECT * FROM experiences WHERE capability_id = ? ORDER BY timestamp DESC LIMIT ?",
            (capability_id, limit),
        )

    def query_by_provider(self, provider_id: str, limit: int = 100) -> list[dict[str, Any]]:
        return self._fetch_all(
            "SELECT * FROM experiences WHERE provider_id = ? ORDER BY timestamp DESC LIMIT ?",
            (provider_id, limit),
        )

    def query_by_task_type(self, task_type: str, limit: int = 100) -> list[dict[str, Any]]:
        return self._fetch_all(
            "SELECT * FROM experiences WHERE task_type = ? ORDER BY timestamp DESC LIMIT ?",
            (task_type, limit),
        )

    def recent(self, limit: int = 50) -> list[dict[str, Any]]:
        return self._fetch_all(
            "SELECT * FROM experiences ORDER BY timestamp DESC LIMIT ?",
            (limit,),
        )

    # ── stats ──────────────────────────────────────────────────────────────

    def get_stats(self, capability_id: str | None = None,
                  provider_id: str | None = None) -> dict[str, Any]:
        """聚合统计：成功率、平均质量、平均耗时、平均满意度."""
        where_clause = ""
        params: list[str] = []

        if capability_id is not None:
            where_clause = "WHERE capability_id = ?"
            params = [capability_id]
        elif provider_id is not None:
            where_clause = "WHERE provider_id = ?"
            params = [provider_id]

        with self._cursor() as conn:
            row = conn.execute(
                f"""SELECT
                        COUNT(*) as total,
                        SUM(CASE WHEN outcome = 'success' THEN 1 ELSE 0 END) as successes,
                        AVG(quality_score) as avg_quality,
                        AVG(user_satisfaction) as avg_satisfaction,
                        AVG(duration_ms) as avg_duration_ms
                    FROM experiences {where_clause}""",
                params,
            ).fetchone()

        if row is None or row[0] == 0:
            return {"total": 0, "success_rate": 0.0}

        total = row[0]
        successes = row[1] or 0
        return {
            "total": total,
            "successes": successes,
            "success_rate": round(successes / total, 4),
            "avg_quality": round(row[2] or 0.0, 4),
            "avg_satisfaction": round(row[3] or 0.0, 4),
            "avg_duration_ms": int(row[4] or 0),
        }

    def rank_providers(self, capability_id: str, top_n: int = 5) -> list[dict[str, Any]]:
        """按历史表现排序 Provider（基于经验数据）."""
        with self._cursor() as conn:
            rows = conn.execute(
                """SELECT
                        provider_id,
                        COUNT(*) as total,
                        SUM(CASE WHEN outcome = 'success' THEN 1 ELSE 0 END) as successes,
                        AVG(quality_score) as avg_quality,
                        AVG(user_satisfaction) as avg_satisfaction,
                        AVG(duration_ms) as avg_duration_ms
                    FROM experiences
                    WHERE capability_id = ?
                    GROUP BY provider_id
                    ORDER BY avg_quality DESC, avg_satisfaction DESC
                    LIMIT ?""",
                (capability_id, top_n),
            ).fetchall()

        results = []
        for row in rows:
            total = row[1]
            succ = row[2] or 0
            results.append({
                "provider_id": row[0],
                "total_experiences": total,
                "success_rate": round(succ / total, 4) if total > 0 else 0.0,
                "avg_quality": round(row[3] or 0.0, 4),
                "avg_satisfaction": round(row[4] or 0.0, 4),
                "avg_duration_ms": int(row[5] or 0),
            })
        return results

    # ── helpers ────────────────────────────────────────────────────────────

    def _fetch_all(self, sql: str, params: tuple | None = None) -> list[dict[str, Any]]:
        assert self._conn is not None
        with self._lock:
            cursor = self._conn.execute(sql, params or ())
            return [self._row_to_dict(row, cursor) for row in cursor.fetchall()]

    @staticmethod
    def _row_to_dict(row: tuple, cursor: sqlite3.Cursor) -> dict[str, Any]:
        col_names = [d[0] for d in cursor.description] if cursor.description else []
        return dict(zip(col_names, row))

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass
