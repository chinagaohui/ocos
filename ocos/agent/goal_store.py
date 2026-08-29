"""GoalSQLiteStore — Goal 的 SQLite 持久化存储。

Phase 21: GoalStack 持久化——解决 AR-2。

职责分工(GAP-P3-4 裁决): 本模块 = agent 层 Goal 对象存储
(goal 表, 对象 API, 生产: agent/goal_stack/agent_runtime);
ocos/goal/store.py = goal 域包持久化(goals 表, 原生参数 API,
生产: goal_monitor/api/routes/goal/runtime/stages)。两套 schema
有互斥字段(本表独有 result_json/INTEGER level; goal 域表独有
progress/source/source_id/updated_at/decision_refs/TEXT level),
无损合并需 schema 超集 + 调用点迁移 + 数据迁移, 超出 GAP-P3
纯重构范围 → 两套并存, 统一收敛留待后续阶段。
"""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from ocos.storage.connection import get_connection
from ocos.agent.goal_types import Goal, GoalLevel, GoalStatus, GoalOriginLevel, GoalAuthority

logger = logging.getLogger(__name__)

_DDL = """
CREATE TABLE IF NOT EXISTS goal (
    goal_id         TEXT PRIMARY KEY,
    level           INTEGER NOT NULL,
    description     TEXT NOT NULL DEFAULT '',
    parent_id       TEXT,
    priority        REAL NOT NULL DEFAULT 1.0,
    created_at      TEXT NOT NULL,
    deadline        TEXT,
    status          TEXT NOT NULL DEFAULT 'PENDING',
    result_json     TEXT,
    origin_level    TEXT NOT NULL DEFAULT 'SYSTEM',
    authority       TEXT NOT NULL DEFAULT 'AUTONOMOUS'
);

CREATE INDEX IF NOT EXISTS idx_goal_status ON goal(status);
CREATE INDEX IF NOT EXISTS idx_goal_level ON goal(level);
CREATE INDEX IF NOT EXISTS idx_goal_priority ON goal(priority DESC);
"""


class GoalSQLiteStore:
    """Goal SQLite 持久化存储。

    使用示例:
        store = GoalSQLiteStore("~/.ocos/db/ocos.db")
        store.initialize()
        store.save(goal)
        active = store.load_active()
    """

    def __init__(self, db_path: str | Path = ":memory:") -> None:
        self._db_path = str(db_path)
        self._conn: Optional[sqlite3.Connection] = None

    def initialize(self) -> None:
        self._conn = get_connection(self._db_path)
        # 2026-08-29 P2-A 修复: 此前 _DDL 定义后从未执行, 建表缺失
        # （对齐 ocos/memory/*/store.py 的 initialize 模式）。
        self._conn.executescript(_DDL)
        self._conn.commit()
        logger.info("GoalSQLiteStore initialized at %s", self._db_path)

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    @property
    def connection(self) -> sqlite3.Connection:
        if self._conn is None:
            raise RuntimeError("GoalSQLiteStore not initialized.")
        return self._conn

    # ── CRUD ────────────────────────────────────────────────────────────────

    def save(self, goal: Goal) -> None:
        """保存 Goal。幂等（INSERT OR REPLACE）。"""
        self.connection.execute(
            """INSERT OR REPLACE INTO goal
               (goal_id, level, description, parent_id, priority,
                created_at, deadline, status, result_json,
                origin_level, authority)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                goal.goal_id,
                goal.level.value,
                goal.description,
                goal.parent_id,
                goal.priority,
                goal.created_at.isoformat(),
                goal.deadline.isoformat() if goal.deadline else None,
                goal.status.name,
                json.dumps(goal.result) if goal.result else None,
                goal.origin_level.value,
                goal.authority.value,
            ),
        )
        self.connection.commit()

    def load(self, goal_id: str) -> Optional[Goal]:
        """按 ID 加载 Goal。"""
        row = self.connection.execute(
            "SELECT * FROM goal WHERE goal_id = ?", (goal_id,)
        ).fetchone()
        if row is None:
            return None
        return self._row_to_goal(row)

    def load_active(self) -> list[Goal]:
        """加载所有 ACTIVE 和 PENDING 状态的 Goal（用于 BOOT 恢复）。"""
        rows = self.connection.execute(
            "SELECT * FROM goal WHERE status IN ('ACTIVE', 'PENDING') ORDER BY level ASC, priority DESC"
        ).fetchall()
        return [self._row_to_goal(r) for r in rows]

    def delete(self, goal_id: str) -> bool:
        """删除 Goal 记录（COMPLETED/CANCELLED/FAILED 的 Goal）。"""
        cur = self.connection.execute(
            "DELETE FROM goal WHERE goal_id = ?", (goal_id,)
        )
        self.connection.commit()
        return cur.rowcount > 0

    def count_by_status(self) -> dict[str, int]:
        """按状态统计 Goal 数量。"""
        rows = self.connection.execute(
            "SELECT status, COUNT(*) as cnt FROM goal GROUP BY status"
        ).fetchall()
        return {r["status"]: r["cnt"] for r in rows}

    # ── Internal ────────────────────────────────────────────────────────────

    @staticmethod
    def _row_to_goal(row: sqlite3.Row) -> Goal:
        d = dict(row)
        created_at = datetime.fromisoformat(d["created_at"])
        deadline = datetime.fromisoformat(d["deadline"]) if d.get("deadline") else None
        result = json.loads(d["result_json"]) if d.get("result_json") else None
        return Goal(
            goal_id=d["goal_id"],
            level=GoalLevel(d["level"]),
            description=d.get("description", ""),
            parent_id=d.get("parent_id"),
            priority=d.get("priority", 1.0),
            created_at=created_at,
            deadline=deadline,
            status=GoalStatus[d.get("status", "PENDING")],
            result=result,
            origin_level=GoalOriginLevel(d.get("origin_level", "SYSTEM")),
            authority=GoalAuthority(d.get("authority", "AUTONOMOUS")),
        )
