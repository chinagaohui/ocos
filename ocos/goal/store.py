"""GoalStore — Goal 持久化存储层。

Phase 21.02: Goal Persistence
Phase 22: Goal Origin Model v1.0 集成 (origin_level + authority)

职责分工(GAP-P3-4 裁决): 本模块 = goal 域包持久化(goals 表,
原生参数 API, 生产: goal_monitor/api/routes/goal/runtime/stages);
ocos/agent/goal_store.py = agent 层 Goal 对象存储(goal 表,
对象 API, 生产: agent/goal_stack/agent_runtime)。两套 schema 有
互斥字段(本表独有 progress/source/source_id/updated_at/
decision_refs/TEXT level; agent 表独有 result_json/INTEGER
level), 无损合并需 schema 超集 + 调用点迁移 + 数据迁移, 超出
GAP-P3 纯重构范围 → 两套并存, 统一收敛留待后续阶段。

操作:
- save: 保存 Goal 到 SQLite (含 origin_level, authority)
- load_active: 加载所有活跃 (非终止态) 的 Goal
- update_progress: 更新 Goal 进度 (0.0 ~ 1.0)
- record_decision: 记录关联 Decision ID
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
from datetime import datetime, timezone

from ocos.storage.connection import get_connection

logger = logging.getLogger(__name__)

DB_PATH = os.environ.get("OCOS_DB_PATH", "ocos.db")


class GoalStore:
    """Goal 持久化存储。

    使用 SQLite goals 表，支持事务安全操作。
    """

    def __init__(self, db_path: str = DB_PATH) -> None:
        self._db_path = db_path

    def _conn(self):
        conn = get_connection(self._db_path)
        # GAP-P2-5: 自愈建表 — goals 表此前仅测试夹具创建, 生产路径缺失
        # AUD-F8 修复: 补齐 save() 实际写入的 agent_id/metadata 列（此前缺失致
        # 自愈表上 INSERT 报 no such column）; plan_dag 同步自愈（CLI 独立运行时
        # 未经 run.py ensure_schema）
        conn.execute(
            """CREATE TABLE IF NOT EXISTS goals (
                id TEXT PRIMARY KEY,
                agent_id TEXT DEFAULT 'master',
                level TEXT NOT NULL,
                status TEXT NOT NULL,
                progress REAL DEFAULT 0.0,
                description TEXT DEFAULT '',
                priority REAL DEFAULT 5.0,
                parent_id TEXT DEFAULT '',
                source TEXT DEFAULT '',
                source_id TEXT DEFAULT '',
                deadline TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                metadata TEXT,
                origin_level TEXT DEFAULT 'SYSTEM',
                authority TEXT DEFAULT 'AUTONOMOUS',
                decision_refs TEXT DEFAULT '[]'
            )"""
        )
        conn.execute(
            """CREATE TABLE IF NOT EXISTS plan_dag (
                plan_id     TEXT PRIMARY KEY,
                goal_id     TEXT NOT NULL,
                dag_json    TEXT NOT NULL,
                strategy    TEXT,
                task_count  INTEGER NOT NULL DEFAULT 0,
                created_at  TEXT NOT NULL
            )"""
        )
        # AUD-F8: 旧库升级 — legacy goals 表缺列时 ALTER 补列（PRAGMA 检查）
        existing = {
            r[1] for r in conn.execute("PRAGMA table_info(goals)").fetchall()
        }
        for col, ddl in (("agent_id", "TEXT DEFAULT 'master'"),
                         ("metadata", "TEXT")):
            if existing and col not in existing:
                conn.execute(f"ALTER TABLE goals ADD COLUMN {col} {ddl}")
        return conn

    # ── 保存 ────────────────────────────────────────────────────────

    def save(self, goal_id: str, level: str, status: str, description: str = "",
             parent_id: str = "", priority: float = 5.0, source: str = "",
             source_id: str = "", deadline: str = "", metadata: dict | None = None,
             origin_level: str = "SYSTEM", authority: str = "AUTONOMOUS") -> None:
        """保存或更新 Goal。

        Goal Origin Model v1.0: origin_level / authority 持久化。
        """
        now = datetime.now(timezone.utc).isoformat()
        conn = self._conn()
        try:
            conn.execute(
                """
                INSERT OR REPLACE INTO goals
                    (id, agent_id, parent_id, level, status, progress,
                     description, deadline, source, source_id,
                     created_at, updated_at, priority, metadata,
                     origin_level, authority)
                VALUES (?, ?, ?, ?, ?, 0.0, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    goal_id, "master", parent_id or None, level, status,
                    description, deadline or None, source, source_id,
                    now, now, priority,
                    json.dumps(metadata) if metadata else None,
                    origin_level, authority,
                ),
            )
            conn.commit()
            logger.debug("Goal saved: %s (%s) origin=%s auth=%s",
                         goal_id, status, origin_level, authority)
        except Exception:
            conn.rollback()
            raise

    # ── 加载 ────────────────────────────────────────────────────────

    _GOAL_COLS = ("id, agent_id, level, status, progress, description, "
                  "priority, parent_id, source, source_id, deadline, "
                  "created_at, updated_at, metadata, origin_level, authority")

    @staticmethod
    def _goal_row_to_dict(row) -> dict:
        keys = ["id", "agent_id", "level", "status", "progress", "description",
                "priority", "parent_id", "source", "source_id", "deadline",
                "created_at", "updated_at", "metadata", "origin_level", "authority"]
        return dict(zip(keys, row))

    def load(self, goal_id: str) -> dict | None:
        """按 id 加载单个 goal（AUD-F8: CLI goal status 查询）。"""
        conn = self._conn()
        row = conn.execute(
            f"SELECT {self._GOAL_COLS} FROM goals WHERE id = ?", (goal_id,)
        ).fetchone()
        return self._goal_row_to_dict(row) if row else None

    def load_active(self) -> list[dict]:
        """加载所有活跃 Goal（非终止态）。"""
        conn = self._conn()
        # GAP-P2-5: 不再重置 row_factory — 共享连接池连接改 tuple 会污染同 db 其他 store
        rows = conn.execute(
            """
            SELECT id, level, status, progress, description,
                   priority, parent_id, source, deadline,
                   created_at, updated_at,
                   origin_level, authority
            FROM goals
            WHERE status NOT IN ('COMPLETED', 'CANCELLED', 'FAILED',
                                 'SUPERSEDED', 'EXPIRED')
            ORDER BY priority DESC, created_at ASC
            """
        ).fetchall()

        return [
            {
                "id": r[0], "level": r[1], "status": r[2], "progress": r[3],
                "description": r[4], "priority": r[5], "parent_id": r[6],
                "source": r[7], "deadline": r[8],
                "created_at": r[9], "updated_at": r[10],
                "origin_level": r[11], "authority": r[12],
            }
            for r in rows
        ]

    # ── 进度 ────────────────────────────────────────────────────────

    def claim_pending_human(self, limit: int = 1) -> list[dict]:
        """UX-1: 认领 PENDING 的人类来源目标（daemon 每 tick 调用）。

        认领 = 原子置 status='ACTIVE' + updated_at，防止多 daemon 重复认领。
        返回认领的行（含 metadata 中的 domain）。
        """
        now = datetime.now(timezone.utc).isoformat()
        conn = self._conn()
        rows = conn.execute(
            f"""SELECT {self._GOAL_COLS} FROM goals
                WHERE status = 'PENDING' AND origin_level = 'HUMAN'
                ORDER BY created_at LIMIT ?""",
            (limit,),
        ).fetchall()
        claimed = []
        for row in rows:
            cur = conn.execute(
                """UPDATE goals SET status = 'ACTIVE', updated_at = ?
                   WHERE id = ? AND status = 'PENDING'""",
                (now, row[0]),
            )
            if cur.rowcount:
                claimed.append(self._goal_row_to_dict(row))
        conn.commit()
        return claimed

    def update_progress(self, goal_id: str, progress: float) -> bool:
        """更新 Goal 进度。progress 自动钳制到 [0.0, 1.0]。"""
        clamped = min(1.0, max(0.0, progress))
        now = datetime.now(timezone.utc).isoformat()
        conn = self._conn()
        try:
            cursor = conn.execute(
                "UPDATE goals SET progress = ?, updated_at = ? WHERE id = ?",
                (clamped, now, goal_id),
            )
            conn.commit()
            updated = cursor.rowcount > 0
            if updated:
                logger.debug("Goal progress: %s = %.2f", goal_id, clamped)
            return updated
        except Exception:
            conn.rollback()
            raise

    # ── Decision 关联 ───────────────────────────────────────────────

    def save_plan_dag(self, goal_id: str, dag_json: str, strategy: str,
                      task_count: int, plan_id: str | None = None) -> None:
        """保存 plan 分解结果（AUD-F8: plan_dag 表, schema v4）。"""
        import uuid
        from datetime import datetime, timezone as _tz
        conn = self._conn()
        try:
            conn.execute(
                """INSERT OR REPLACE INTO plan_dag
                   (plan_id, goal_id, dag_json, strategy, task_count, created_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (plan_id or f"PLAN-{uuid.uuid4().hex[:8]}", goal_id, dag_json,
                 strategy, task_count,
                 datetime.now(_tz.utc).isoformat()),
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    _PLAN_COLS = "plan_id, goal_id, dag_json, strategy, task_count, created_at"

    def load_plan_dag(self, goal_id: str) -> dict | None:
        """加载 goal 的最新 plan 分解结果（AUD-F8）。"""
        conn = self._conn()
        row = conn.execute(
            f"""SELECT {self._PLAN_COLS} FROM plan_dag
                WHERE goal_id = ? ORDER BY created_at DESC LIMIT 1""",
            (goal_id,),
        ).fetchone()
        if not row:
            return None
        keys = ["plan_id", "goal_id", "dag_json", "strategy",
                "task_count", "created_at"]
        return dict(zip(keys, row))

    def record_decision(self, goal_id: str, decision_id: str) -> None:
        """记录关联的 Decision ID。"""
        conn = self._conn()
        # GAP-P2-5: 不再重置 row_factory — 共享连接池连接改 tuple 会污染同 db 其他 store
        try:
            row = conn.execute(
                "SELECT decision_refs FROM goals WHERE id = ?", (goal_id,)
            ).fetchone()

            refs: list[str] = []
            if row and row[0]:
                try:
                    refs = json.loads(row[0])
                except json.JSONDecodeError:
                    refs = []

            if decision_id not in refs:
                refs.append(decision_id)
                conn.execute(
                    "UPDATE goals SET decision_refs = ?, updated_at = ? WHERE id = ?",
                    (json.dumps(refs), datetime.now(timezone.utc).isoformat(), goal_id),
                )
                conn.commit()
                logger.debug("Decision %s linked to goal %s", decision_id, goal_id)
        except Exception:
            conn.rollback()
            raise
