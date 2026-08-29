"""P2-D: 主动输出审计存储 — SQLite 记录每次主动输出尝试（含被拒）。

频率闸门数据源：count_since(今日 0:00)。
"""

from __future__ import annotations

import logging
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class ProactiveAuditStore:
    """主动输出审计存储（内存默认；生产注入文件路径）。"""

    def __init__(self, db_path: str | Path = ":memory:") -> None:
        self.db_path = str(db_path)
        self._conn: sqlite3.Connection | None = None

    def initialize(self) -> None:
        """建表（幂等）。"""
        conn = self.connection
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS proactive_audit (
                id TEXT PRIMARY KEY,
                ts TEXT NOT NULL,
                kind TEXT NOT NULL,
                message TEXT NOT NULL,
                granted INTEGER NOT NULL,
                reason TEXT NOT NULL DEFAULT ''
            )
            """
        )
        conn.commit()
        logger.info("ProactiveAuditStore initialized at %s", self.db_path)

    @property
    def connection(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path)
        return self._conn

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def record(
        self,
        kind: str,
        message: str,
        granted: bool,
        reason: str = "",
    ) -> None:
        """记录一次主动输出尝试（granted=True 表示实际输出）。"""
        now = datetime.now(timezone.utc)
        self.connection.execute(
            "INSERT INTO proactive_audit (id, ts, kind, message, granted, reason) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (uuid.uuid4().hex, now.isoformat(), kind, message, int(granted), reason),
        )
        self.connection.commit()

    def count_since(self, since: datetime) -> int:
        """统计 since 之后被允许的输出次数（频率闸门）。"""
        row = self.connection.execute(
            "SELECT COUNT(*) FROM proactive_audit "
            "WHERE granted = 1 AND ts >= ?",
            (since.isoformat(),),
        ).fetchone()
        return int(row[0]) if row else 0

    def count_granted_today(self) -> int:
        """今日（UTC 0:00 起）实际输出次数。"""
        today_start = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        return self.count_since(today_start)

    def recent(self, limit: int = 20) -> list[dict[str, Any]]:
        """最近审计记录（调试/测试用）。"""
        rows = self.connection.execute(
            "SELECT ts, kind, message, granted, reason FROM proactive_audit "
            "ORDER BY ts DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [
            {
                "ts": r[0],
                "kind": r[1],
                "message": r[2],
                "granted": bool(r[3]),
                "reason": r[4],
            }
            for r in rows
        ]
