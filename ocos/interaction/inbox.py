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
    note         TEXT DEFAULT '',
    reply        TEXT DEFAULT '',
    replied_at   TEXT,
    kind         TEXT DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_user_messages_status ON user_messages(status);
"""

_COLS = ("id, sender, content, status, created_at, consumed_at, note, "
         "reply, replied_at, kind")


def _row_to_dict(row) -> dict:
    keys = ["id", "sender", "content", "status",
            "created_at", "consumed_at", "note", "reply", "replied_at",
            "kind"]
    return dict(zip(keys, row))


class UserInbox:
    """用户消息收件箱（user_messages 表）。"""

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path

    def _conn(self):
        conn = get_connection(self._db_path)
        conn.executescript(_DDL)   # 自愈建表（CLI 独立运行时未经 ensure_schema）
        # R1: 旧库升级 — legacy user_messages 表缺 reply 列时 ALTER 补列
        existing = {
            r[1] for r in conn.execute("PRAGMA table_info(user_messages)").fetchall()
        }
        if existing:
            for col in ("reply", "replied_at", "kind"):
                if col not in existing:
                    conn.execute(f"ALTER TABLE user_messages ADD COLUMN {col} TEXT DEFAULT ''")
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

    def get(self, mid: str) -> Optional[dict]:
        """按 id 取单条消息。"""
        conn = self._conn()
        row = conn.execute(
            f"SELECT {_COLS} FROM user_messages WHERE id = ?", (mid,)
        ).fetchone()
        return _row_to_dict(row) if row else None

    def reply(self, mid: str, reply_text: str) -> None:
        """R1: 写回 agent 的回复（daemon 消费消息后调用）。"""
        conn = self._conn()
        conn.execute(
            "UPDATE user_messages SET reply = ?, replied_at = ? WHERE id = ?",
            (reply_text[:4000], datetime.now(timezone.utc).isoformat(), mid),
        )
        conn.commit()
        logger.info("UserInbox: reply written for %s (%d chars)",
                    mid, len(reply_text))

    def wait_for_reply(self, mid: str, timeout: float = 60.0,
                       interval: float = 0.5) -> Optional[dict]:
        """R3: 轮询等待回复（ocos say --wait）。超时返回当前状态。"""
        import time
        deadline = time.time() + timeout
        while time.time() < deadline:
            row = self.get(mid)
            if row and row.get("reply"):
                return row
            time.sleep(interval)
        return self.get(mid)

    def post_outbound(self, content: str, kind: str = "result") -> str:
        """UX-J: agent 主动消息（outbound 回推 TUI 对话流）。

        kind 分类（D1 修复 2026-09-07 — TUI 按此选面板样式）:
          result   目标执行结果/回复（青色「目标执行结果」面板）
          proposal 主动提议/提醒（P5.2 交互、动机通知、制动状态 —
                   黄色「主动提议」面板）
          report   成长叙事/生命体征日报（绿色「成长报告」面板）
        旧库无 kind 列时由 _conn() 迁移补列；kind 随 /ocos/outbox
        透传给 TUI，无 kind 的历史行 TUI 按 result 兜底。
        """
        mid = f"MSG-{uuid.uuid4().hex[:8]}"
        conn = self._conn()
        conn.execute(
            """INSERT INTO user_messages
               (id, sender, content, status, created_at, kind)
               VALUES (?, 'ocos', ?, 'outbound', ?, ?)""",
            (mid, content[:4000], datetime.now(timezone.utc).isoformat(),
             (kind or "result")[:16]))
        conn.commit()
        return mid

    def list_outbound_after(self, after_rowid: int = 0,
                            limit: int = 20) -> list[dict]:
        """UX-J: 增量拉取 agent 主动消息（UI 轮询用，按 rowid 游标）。"""
        conn = self._conn()
        rows = conn.execute(
            f"SELECT rowid AS rid, {_COLS} FROM user_messages "
            "WHERE sender = 'ocos' AND rowid > ? ORDER BY rowid LIMIT ?",
            (after_rowid, limit)).fetchall()
        out = []
        for r in rows:
            d = _row_to_dict(r[1:])   # r[0]=rid, 其余按 _COLS 顺序
            d["rid"] = r[0]
            out.append(d)
        return out

    def max_rowid(self) -> int:
        conn = self._conn()
        return conn.execute(
            "SELECT COALESCE(MAX(rowid), 0) FROM user_messages").fetchone()[0]

    def count_queued(self) -> int:
        conn = self._conn()
        return conn.execute(
            "SELECT COUNT(*) FROM user_messages WHERE status = 'queued'"
        ).fetchone()[0]
