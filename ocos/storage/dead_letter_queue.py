"""SQLiteDLQ — 基于 SQLite 的死信队列实现。

职责：
- 存储处理失败的事件（含失败原因和重试计数）
- 标记已解决 / 重新入队
- 查询未处理的死信
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Optional

from ocos.storage.connection import get_connection, transaction
from ocos.storage.migrations import ensure_schema
from ocos.storage.schema import TABLE_DEAD_LETTER_QUEUE


class SQLiteDLQ:
    """基于 SQLite 的死信队列。

    Args:
        db_path: SQLite 数据库文件路径。
        max_retries: 自动重试的最大次数（超过后标记为不可自动恢复）。
    """

    def __init__(self, db_path: str, max_retries: int = 3):
        self._db_path = db_path
        self._max_retries = max_retries
        ensure_schema(db_path)

    # ── 写入 ──────────────────────────────────────────────────────────────────

    def enqueue(
        self,
        event_id: str,
        reason: str,
        payload: Optional[dict[str, Any]] = None,
    ) -> int:
        """将失败事件加入死信队列。

        Args:
            event_id: 失败的事件 ID。
            reason: 失败原因（如 'timeout', 'payload_invalid'）。
            payload: 原始事件负载副本。

        Returns:
            死信记录 ID（AUTOINCREMENT）。
        """
        with transaction(self._db_path) as conn:
            cursor = conn.execute(
                f"INSERT INTO {TABLE_DEAD_LETTER_QUEUE} "
                "(event_id, reason, payload) VALUES (?, ?, ?)",
                (event_id, reason, json.dumps(payload) if payload else None),
            )
            return cursor.lastrowid or 0

    # ── 读取 ──────────────────────────────────────────────────────────────────

    def list_unresolved(
        self,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """列出所有未处理的死信。"""
        conn = get_connection(self._db_path)
        cursor = conn.execute(
            f"SELECT * FROM {TABLE_DEAD_LETTER_QUEUE} "
            "WHERE resolved = 0 ORDER BY failed_at ASC LIMIT ? OFFSET ?",
            (limit, offset),
        )
        return [self._row_to_dict(row) for row in cursor.fetchall()]

    def list_all(
        self,
        resolved: Optional[bool] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """列出死信记录。可按 resolved 状态过滤。"""
        conn = get_connection(self._db_path)
        if resolved is not None:
            cursor = conn.execute(
                f"SELECT * FROM {TABLE_DEAD_LETTER_QUEUE} "
                "WHERE resolved = ? ORDER BY failed_at ASC LIMIT ? OFFSET ?",
                (1 if resolved else 0, limit, offset),
            )
        else:
            cursor = conn.execute(
                f"SELECT * FROM {TABLE_DEAD_LETTER_QUEUE} "
                "ORDER BY failed_at ASC LIMIT ? OFFSET ?",
                (limit, offset),
            )
        return [self._row_to_dict(row) for row in cursor.fetchall()]

    def count_unresolved(self) -> int:
        """返回未处理的死信数量。"""
        conn = get_connection(self._db_path)
        cursor = conn.execute(
            f"SELECT COUNT(*) AS cnt FROM {TABLE_DEAD_LETTER_QUEUE} WHERE resolved = 0",
        )
        return cursor.fetchone()["cnt"]

    # ── 更新 ──────────────────────────────────────────────────────────────────

    def mark_resolved(self, dlq_id: int) -> bool:
        """将死信标记为已解决。"""
        with transaction(self._db_path) as conn:
            cursor = conn.execute(
                f"UPDATE {TABLE_DEAD_LETTER_QUEUE} SET resolved = 1 WHERE id = ?",
                (dlq_id,),
            )
            return cursor.rowcount > 0

    def increment_retry(self, dlq_id: int) -> int:
        """增加重试计数。返回重试后的计数值。"""
        with transaction(self._db_path) as conn:
            conn.execute(
                f"UPDATE {TABLE_DEAD_LETTER_QUEUE} SET retry_count = retry_count + 1 WHERE id = ?",
                (dlq_id,),
            )
            cursor = conn.execute(
                f"SELECT retry_count FROM {TABLE_DEAD_LETTER_QUEUE} WHERE id = ?",
                (dlq_id,),
            )
            row = cursor.fetchone()
            return row["retry_count"] if row else -1

    def is_exhausted(self, dlq_id: int) -> bool:
        """检查该死信是否已耗尽重试次数。"""
        conn = get_connection(self._db_path)
        cursor = conn.execute(
            f"SELECT retry_count FROM {TABLE_DEAD_LETTER_QUEUE} WHERE id = ?",
            (dlq_id,),
        )
        row = cursor.fetchone()
        return row is None or row["retry_count"] >= self._max_retries

    # ── 删除 ──────────────────────────────────────────────────────────────────

    def delete(self, dlq_id: int) -> bool:
        """删除一条死信记录。"""
        with transaction(self._db_path) as conn:
            cursor = conn.execute(
                f"DELETE FROM {TABLE_DEAD_LETTER_QUEUE} WHERE id = ?",
                (dlq_id,),
            )
            return cursor.rowcount > 0

    def clear_all(self) -> int:
        """清空死信队列（仅用于测试）。"""
        with transaction(self._db_path) as conn:
            cursor = conn.execute(f"DELETE FROM {TABLE_DEAD_LETTER_QUEUE}")
            return cursor.rowcount

    # ── 内部 ──────────────────────────────────────────────────────────────────

    @staticmethod
    def _row_to_dict(row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "event_id": row["event_id"],
            "reason": row["reason"],
            "payload": json.loads(row["payload"]) if row["payload"] else None,
            "failed_at": row["failed_at"],
            "retry_count": row["retry_count"],
            "resolved": bool(row["resolved"]),
        }
