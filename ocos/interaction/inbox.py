"""UX-P2: UserInbox — 用户消息收件箱（ocos say → daemon 消费的跨进程通道）。

与 goal 认领（UX-1）同一模式: CLI 进程写库，daemon 每 tick drain。
连接纪律: 池化连接禁止 close()/row_factory，位置列查询。
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from ocos.storage.connection import get_connection

logger = logging.getLogger(__name__)

_DDL = """
CREATE TABLE IF NOT EXISTS user_messages (
    id           TEXT PRIMARY KEY,
    sender       TEXT NOT NULL DEFAULT 'cli',
    content      TEXT NOT NULL,
    status       TEXT NOT NULL DEFAULT 'queued',
    created_at   TEXT NOT NULL,
    consumed_at  TEXT,
    note         TEXT DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_user_messages_status ON user_messages(status);
"""

_COLS = "id, sender, content, status, created_at, consumed_at, note"


def _row_to_dict(row) -> dict:
    keys = ["id", "sender", "content", "status",
            "created_at", "consumed_at", "note"]
    return dict(zip(keys, row))


class UserInbox:
    """用户消息收件箱（user_messages 表）。"""

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path

    def _conn(self):
        conn = get_connection(self._db_path)
        conn.executescript(_DDL)   # 自愈建表（CLI 独立运行时未经 ensure_schema）
        conn.commit()
        return conn

    def post(self, content: str, sender: str = "cli") -> str:
        """投递一条用户消息，返回消息 id。"""
        mid = f"MSG-{uuid.uuid4().hex[:8]}"
        conn = self._conn()
        conn.execute(
            """INSERT INTO user_messages
               (id, sender, content, status, created_at)
               VALUES (?, ?, ?, 'queued', ?)""",
            (mid, sender, content[:2000],
             datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()
        logger.info("UserInbox: %s posted (sender=%s)", mid, sender)
        return mid

    def drain(self, limit: int = 3) -> list[dict]:
        """原子取走待处理消息（daemon 每 tick 调用，置 consumed）。"""
        now = datetime.now(timezone.utc).isoformat()
        conn = self._conn()
        rows = conn.execute(
            f"SELECT {_COLS} FROM user_messages WHERE status = 'queued' "
            "ORDER BY created_at LIMIT ?",
            (limit,),
        ).fetchall()
        out = []
        for row in rows:
            cur = conn.execute(
                "UPDATE user_messages SET status = 'consumed', consumed_at = ? "
                "WHERE id = ? AND status = 'queued'",
                (now, row[0]),
            )
            if cur.rowcount:
                out.append(_row_to_dict(row))
        conn.commit()
        return out

    def list_recent(self, limit: int = 10) -> list[dict]:
        conn = self._conn()
        rows = conn.execute(
            f"SELECT {_COLS} FROM user_messages ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [_row_to_dict(r) for r in rows]

    def count_queued(self) -> int:
        conn = self._conn()
        return conn.execute(
            "SELECT COUNT(*) FROM user_messages WHERE status = 'queued'"
        ).fetchone()[0]
