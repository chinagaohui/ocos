"""Phase 24.2-B — Episode Store。

SQLite 持久化的 Episode 存储层。

约束:
    - Append-only: Episode 创建后不可修改
    - 索引: goal, significance_score, created_at
    - 禁止: 直接删除 Episode (只能 ARCHIVE)
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from ocos.storage.connection import get_connection
from ocos.memory.episode.models import Episode, EpisodeStatus


class EpisodeStore:
    """Episode SQLite 持久化存储。

    使用示例:
        store = EpisodeStore(":memory:")
        store.initialize()
        store.save(episode)
        results = store.query_by_goal("g1")
    """

    def __init__(self, db_path: str | Path = ":memory:") -> None:
        self._db_path = str(db_path)
        self._conn: Optional[sqlite3.Connection] = None

    # ── 生命周期 ────────────────────────────────────────────────────────────

    def initialize(self) -> None:
        """创建表结构。幂等。"""
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
            raise RuntimeError("EpisodeStore not initialized. Call initialize() first.")
        return self._conn

    # ── CRUD ─────────────────────────────────────────────────────────────────

    def save(self, episode: Episode) -> None:
        """保存 Episode。如果已存在 (相同 experience_id + source)，跳过。"""
        existing = self._find_by_experience_id(episode.experience_id)
        if existing:
            return  # 幂等 — 同一 Experience 不重复产生 Episode

        self.connection.execute(
            """
            INSERT INTO episodes (
                id, experience_id, session_id,
                context, goal, decision, action, outcome, condition,
                significance_score, evaluation_trace, source,
                status, tags, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                episode.id,
                episode.experience_id,
                episode.session_id,
                json.dumps(episode.context, ensure_ascii=False),
                episode.goal,
                episode.decision,
                episode.action,
                json.dumps(episode.outcome, ensure_ascii=False),
                episode.condition,
                episode.significance_score,
                json.dumps(episode.evaluation_trace, ensure_ascii=False),
                episode.source,
                episode.status.value,
                json.dumps(episode.tags, ensure_ascii=False),
                episode.created_at.isoformat(),
            ),
        )
        self.connection.commit()

    def get(self, episode_id: str) -> Optional[Episode]:
        """按 ID 获取 Episode。"""
        row = self.connection.execute(
            "SELECT * FROM episodes WHERE id = ?", (episode_id,)
        ).fetchone()
        return self._row_to_episode(row) if row else None

    def archive(self, episode_id: str) -> bool:
        """归档 Episode（不可删除）。"""
        cursor = self.connection.execute(
            "UPDATE episodes SET status = ? WHERE id = ? AND status = ?",
            (EpisodeStatus.ARCHIVED.value, episode_id, EpisodeStatus.ACTIVE.value),
        )
        self.connection.commit()
        return cursor.rowcount > 0

    def mark_consolidated(self, episode_id: str) -> bool:
        """标记 Episode 已巩固（P2-C dream 重放后置 CONSOLIDATED，幂等标记）。"""
        cursor = self.connection.execute(
            "UPDATE episodes SET status = ? WHERE id = ? AND status = ?",
            (EpisodeStatus.CONSOLIDATED.value, episode_id, EpisodeStatus.ACTIVE.value),
        )
        self.connection.commit()
        return cursor.rowcount > 0

    def count(self) -> int:
        """Episode 总数。"""
        row = self.connection.execute("SELECT COUNT(*) as cnt FROM episodes").fetchone()
        return row["cnt"] if row else 0

    # ── 查询 API ────────────────────────────────────────────────────────────

    def query_by_goal(
        self,
        goal: str,
        limit: int = 50,
        active_only: bool = True,
    ) -> list[Episode]:
        """按 Goal 查询 Episode。"""
        query = "SELECT * FROM episodes WHERE goal = ?"
        params: list = [goal]
        if active_only:
            query += " AND status = ?"
            params.append(EpisodeStatus.ACTIVE.value)
        query += " ORDER BY significance_score DESC LIMIT ?"
        params.append(limit)

        rows = self.connection.execute(query, params).fetchall()
        return [self._row_to_episode(r) for r in rows if r]

    def query_by_time(
        self,
        limit: int = 50,
        active_only: bool = True,
    ) -> list[Episode]:
        """按时间倒序查询 Episode。"""
        query = "SELECT * FROM episodes"
        params: list = []
        if active_only:
            query += " WHERE status = ?"
            params.append(EpisodeStatus.ACTIVE.value)
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        rows = self.connection.execute(query, params).fetchall()
        return [self._row_to_episode(r) for r in rows if r]

    def query_by_significance(
        self,
        min_score: float = 0.5,
        limit: int = 50,
        active_only: bool = True,
    ) -> list[Episode]:
        """按 Significance 分数查询 Episode。"""
        query = "SELECT * FROM episodes WHERE significance_score >= ?"
        params: list = [min_score]
        if active_only:
            query += " AND status = ?"
            params.append(EpisodeStatus.ACTIVE.value)
        query += " ORDER BY significance_score DESC LIMIT ?"
        params.append(limit)

        rows = self.connection.execute(query, params).fetchall()
        return [self._row_to_episode(r) for r in rows if r]

    def query_by_source(
        self,
        source: str,
        limit: int = 10,
    ) -> list[Episode]:
        """按来源查询（S2.4: lesson 召回通道）。

        LessonsLearned 落库形态为 source='lesson'，recall 经此召回。
        """
        rows = self.connection.execute(
            "SELECT * FROM episodes WHERE source = ? "
            "ORDER BY created_at DESC LIMIT ?",
            (source, limit),
        ).fetchall()
        return [self._row_to_episode(r) for r in rows if r]

    def query_by_tag(
        self,
        tag: str,
        limit: int = 50,
        active_only: bool = True,
    ) -> list[Episode]:
        """按 Tag 查询 Episode。"""
        # SQLite JSON 数组包含查询
        query = """
            SELECT * FROM episodes
            WHERE EXISTS (
                SELECT 1 FROM json_each(tags) WHERE value = ?
            )
        """
        params: list = [tag]
        if active_only:
            query += " AND status = ?"
            params.append(EpisodeStatus.ACTIVE.value)
        query += " ORDER BY significance_score DESC LIMIT ?"
        params.append(limit)

        rows = self.connection.execute(query, params).fetchall()
        return [self._row_to_episode(r) for r in rows if r]

    # ── 内部 ────────────────────────────────────────────────────────────────

    def _find_by_experience_id(self, experience_id: str) -> Optional[Episode]:
        row = self.connection.execute(
            "SELECT * FROM episodes WHERE experience_id = ?",
            (experience_id,),
        ).fetchone()
        return self._row_to_episode(row) if row else None

    def _row_to_episode(self, row: sqlite3.Row) -> Episode:
        return Episode(
            id=row["id"],
            experience_id=row["experience_id"],
            created_at=datetime.fromisoformat(row["created_at"]),
            session_id=row["session_id"],
            context=json.loads(row["context"]),
            goal=row["goal"],
            decision=row["decision"],
            action=row["action"],
            outcome=json.loads(row["outcome"]),
            condition=row["condition"],
            significance_score=row["significance_score"],
            evaluation_trace=json.loads(row["evaluation_trace"]),
            source=row["source"],
            status=EpisodeStatus(row["status"]),
            tags=json.loads(row["tags"]),
        )


# ── DDL ──────────────────────────────────────────────────────────────────────

_DDL = """
CREATE TABLE IF NOT EXISTS episodes (
    id              TEXT PRIMARY KEY,
    experience_id   TEXT NOT NULL,
    session_id      TEXT NOT NULL DEFAULT 'default',

    -- 客观事实 (What, How, Result, Why)
    context         TEXT NOT NULL DEFAULT '{}',  -- JSON
    goal            TEXT,
    decision        TEXT NOT NULL DEFAULT '',
    action          TEXT NOT NULL DEFAULT '',
    outcome         TEXT NOT NULL DEFAULT '{}',  -- JSON
    condition       TEXT NOT NULL DEFAULT '',

    -- 门控结果
    significance_score  REAL NOT NULL DEFAULT 0.0,
    evaluation_trace    TEXT NOT NULL DEFAULT '{}',  -- JSON (可审计)
    source              TEXT NOT NULL DEFAULT 'decision',

    -- 元数据
    status          TEXT NOT NULL DEFAULT 'active',
    tags            TEXT NOT NULL DEFAULT '[]',  -- JSON array
    created_at      TEXT NOT NULL
);

-- 查询索引
CREATE INDEX IF NOT EXISTS idx_episodes_goal
    ON episodes(goal, significance_score DESC);

CREATE INDEX IF NOT EXISTS idx_episodes_created
    ON episodes(created_at DESC);

CREATE INDEX IF NOT EXISTS idx_episodes_significance
    ON episodes(significance_score DESC);

CREATE INDEX IF NOT EXISTS idx_episodes_experience
    ON episodes(experience_id);

CREATE INDEX IF NOT EXISTS idx_episodes_status
    ON episodes(status);
"""
