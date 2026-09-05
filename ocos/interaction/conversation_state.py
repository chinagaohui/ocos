"""ConversationState — 对话状态机持久层 (FIX-21, 评审 P0-4).

结构化对话状态: current_goal_id / last_goal_id / last_intent / active_topic。
解决"继续刚才那个任务"依赖 LLM 从文本猜的问题:
  task 受理   → 写 current_goal_id
  continue    → 按 session 精确恢复目标(状态/进度/真实结果), 不再猜
  结果已交付  → current → last 状态推进
状态落 SQLite(跨进程/跨重启), API 与 daemon 共享同一份。
"""
from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class ConversationStateStore:
    """每 session 一行的对话状态（SQLite 持久化）。"""

    def __init__(self, db_path: str):
        self._db_path = db_path

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path, timeout=5)
        conn.execute(
            """CREATE TABLE IF NOT EXISTS conversation_state (
                session_id TEXT PRIMARY KEY,
                current_goal_id TEXT,
                last_goal_id TEXT,
                last_intent TEXT,
                active_topic TEXT,
                updated_at TEXT NOT NULL
            )"""
        )
        return conn

    def get(self, session_id: str) -> dict:
        try:
            conn = self._conn()
            row = conn.execute(
                "SELECT current_goal_id, last_goal_id, last_intent,"
                " active_topic, updated_at"
                " FROM conversation_state WHERE session_id = ?",
                (session_id,),
            ).fetchone()
            conn.close()
        except Exception as e:
            logger.debug("conversation_state get failed: %s", e)
            return {}
        if not row:
            return {}
        return {
            "current_goal_id": row[0],
            "last_goal_id": row[1],
            "last_intent": row[2],
            "active_topic": row[3],
            "updated_at": row[4],
        }

    def update(self, session_id: str, *, current_goal_id: str | None = None,
               last_goal_id: str | None = None, last_intent: str | None = None,
               active_topic: str | None = None,
               clear_current: bool = False) -> None:
        """合并更新：未指定的字段保持不变；clear_current 把 current 让位给 last。"""
        try:
            conn = self._conn()
            cur = conn.execute(
                "SELECT current_goal_id, last_goal_id, last_intent, active_topic"
                " FROM conversation_state WHERE session_id = ?",
                (session_id,),
            ).fetchone()
            if cur:
                vals = {"current_goal_id": cur[0], "last_goal_id": cur[1],
                        "last_intent": cur[2], "active_topic": cur[3]}
            else:
                vals = {"current_goal_id": None, "last_goal_id": None,
                        "last_intent": None, "active_topic": None}
            if clear_current:
                if vals.get("current_goal_id"):
                    vals["last_goal_id"] = vals["current_goal_id"]
                vals["current_goal_id"] = None
            else:
                if current_goal_id is not None:
                    vals["current_goal_id"] = current_goal_id
            if last_goal_id is not None:
                vals["last_goal_id"] = last_goal_id
            if last_intent is not None:
                vals["last_intent"] = last_intent
            if active_topic is not None:
                vals["active_topic"] = active_topic
            conn.execute(
                """INSERT INTO conversation_state
                   (session_id, current_goal_id, last_goal_id, last_intent,
                    active_topic, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?)
                   ON CONFLICT(session_id) DO UPDATE SET
                     current_goal_id=excluded.current_goal_id,
                     last_goal_id=excluded.last_goal_id,
                     last_intent=excluded.last_intent,
                     active_topic=excluded.active_topic,
                     updated_at=excluded.updated_at""",
                (session_id, vals["current_goal_id"], vals["last_goal_id"],
                 vals["last_intent"], vals["active_topic"],
                 datetime.now(timezone.utc).isoformat(timespec="seconds")),
            )
            conn.commit()
            conn.close()
        except Exception as e:
            logger.debug("conversation_state update failed: %s", e)
