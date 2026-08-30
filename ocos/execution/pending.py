"""AUD-F12: PendingStore — R4-B 待批队列持久化。

DecisionBridge 的 ASK 类动作（写章节/网络检索/高危 DAG 任务）经本 store
落 SQLite pending_actions 表（schema v4），跨进程存活。

审批语义（人工 = authority）:
    approve → 人工已授权，尝试真实执行:
        - dispatcher 有 handler 的动作 → dispatch 执行 → executed
        - 无 executor 的动作（WRITE_CHAPTER/SEARCH_WEB/dag_*）→ blocked
          （诚实记录：批准不等于有执行器，落失败审计可见）
    deny → denied，不再出现。

审批不二次过 PermissionGuard 语义双检（人工决策即 authority），
但每次决定/执行必须落 ExecutionAudit。
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from ocos.storage.connection import get_connection

logger = logging.getLogger(__name__)

_DDL = """
CREATE TABLE IF NOT EXISTS pending_actions (
    id              TEXT PRIMARY KEY,
    action_type     TEXT NOT NULL,
    target          TEXT DEFAULT '',
    payload_json    TEXT DEFAULT '{}',
    text            TEXT DEFAULT '',
    source          TEXT DEFAULT '',
    status          TEXT NOT NULL DEFAULT 'pending',
    queued_at       TEXT NOT NULL,
    decided_at      TEXT,
    decided_by      TEXT,
    executed_at     TEXT,
    result_summary  TEXT
);
CREATE INDEX IF NOT EXISTS idx_pending_actions_status ON pending_actions(status);
"""


class PendingStore:
    """待批动作持久化存储（pending_actions 表, schema v4）。"""

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path

    def _conn(self):
        conn = get_connection(self._db_path)
        conn.executescript(_DDL)   # 自愈建表（CLI 独立运行时未经 ensure_schema）
        conn.commit()
        return conn

    def enqueue(self, action_type: str, target: str = "", payload: Optional[dict] = None,
                text: str = "", source: str = "") -> str:
        """入队待批动作，返回 pending id。"""
        pid = f"PEND-{uuid.uuid4().hex[:8]}"
        conn = self._conn()
        try:
            conn.execute(
                """INSERT INTO pending_actions
                   (id, action_type, target, payload_json, text, source,
                    status, queued_at)
                   VALUES (?, ?, ?, ?, ?, ?, 'pending', ?)""",
                (pid, action_type, target,
                 json.dumps(payload or {}, ensure_ascii=False),
                 text[:200], source,
                 datetime.now(timezone.utc).isoformat()),
            )
            conn.commit()
            logger.info("PendingStore: %s enqueued (%s)", pid, action_type)
            return pid
        finally:
            conn.close()

    def get(self, pid: str) -> Optional[dict]:
        import sqlite3
        conn = get_connection(self._db_path)
        conn.row_factory = sqlite3.Row
        try:
            conn.executescript(_DDL)
            row = conn.execute(
                "SELECT * FROM pending_actions WHERE id = ?", (pid,)
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def list_by_status(self, status: str = "pending") -> list[dict]:
        import sqlite3
        conn = get_connection(self._db_path)
        conn.row_factory = sqlite3.Row
        try:
            conn.executescript(_DDL)
            rows = conn.execute(
                "SELECT * FROM pending_actions WHERE status = ? ORDER BY queued_at",
                (status,),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def decide(self, pid: str, approved: bool, decided_by: str = "cli") -> bool:
        """审批决定（人工 authority）。返回是否存在该 pending。"""
        status = "approved" if approved else "denied"
        conn = self._conn()
        try:
            cur = conn.execute(
                """UPDATE pending_actions
                   SET status = ?, decided_at = ?, decided_by = ?
                   WHERE id = ? AND status = 'pending'""",
                (status, datetime.now(timezone.utc).isoformat(), decided_by, pid),
            )
            conn.commit()
            return cur.rowcount > 0
        finally:
            conn.close()

    def mark_executed(self, pid: str, result_summary: str,
                      executed: bool = True) -> None:
        """审批后执行回写（executed / blocked）。"""
        status = "executed" if executed else "blocked"
        conn = self._conn()
        try:
            conn.execute(
                """UPDATE pending_actions
                   SET status = ?, executed_at = ?, result_summary = ?
                   WHERE id = ?""",
                (status, datetime.now(timezone.utc).isoformat(),
                 result_summary[:500], pid),
            )
            conn.commit()
        finally:
            conn.close()
