"""SQLiteWorkingMemory — SQLite 工作记忆持久化实现。

职责：
- 键值存储 + TTL 过期 + 容量限制
- 作为 WorkingMemory 的持久化后端
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from ocos.storage.connection import get_connection, transaction
from ocos.storage.migrations import ensure_schema
from ocos.storage.schema import TABLE_WORKING_MEMORY


class SQLiteWorkingMemory:
    """基于 SQLite 的 WorkingMemory 持久化实现。

    Args:
        db_path: SQLite 数据库文件路径。
        max_entries: 最大条目数，超过时拒绝写入。
        default_ttl: 默认 TTL 秒数（0 或 None 表示永不过期）。
    """

    def __init__(
        self,
        db_path: str,
        max_entries: int = 10000,
        default_ttl: Optional[float] = 3600.0,
    ):
        self._db_path = db_path
        self._max_entries = max_entries
        self._default_ttl = default_ttl
        ensure_schema(db_path)

    # ── 公共 API ────────────────────────────────────────────────────────────

    def store(self, key: str, value: dict[str, Any], ttl: Optional[float] = None) -> str:
        """存储一个键值对。

        Args:
            key: 唯一键。
            value: 要存储的字典。
            ttl: 自定义 TTL 秒数（覆盖默认 TTL）。

        Returns:
            存储的 key。

        Raises:
            ValueError: 超过 max_entries 限制。
        """
        if self.count() >= self._max_entries:
            raise ValueError(
                f"WorkingMemory 已满 ({self._max_entries} 条)，无法存储 key={key}"
            )

        ttl_seconds = ttl if ttl is not None else self._default_ttl
        expires_at = None
        if ttl_seconds and ttl_seconds > 0:
            expires_at = (
                datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(seconds=ttl_seconds)
            ).isoformat()

        with transaction(self._db_path) as conn:
            conn.execute(
                f"INSERT OR REPLACE INTO {TABLE_WORKING_MEMORY} (key, value, expires_at, ttl_seconds) "
                "VALUES (?, ?, ?, ?)",
                (key, json.dumps(value, default=str), expires_at, ttl_seconds),
            )
        return key

    def load(self, key: str) -> Optional[dict[str, Any]]:
        """按 key 加载一个值。

        如果条目已过期，自动删除并返回 None。
        """
        conn = get_connection(self._db_path)
        cursor = conn.execute(
            f"SELECT value, expires_at FROM {TABLE_WORKING_MEMORY} WHERE key = ?",
            (key,),
        )
        row = cursor.fetchone()
        if row is None:
            return None

        # 检查过期
        if row["expires_at"]:
            expires = datetime.fromisoformat(row["expires_at"])
            # expires_at 存储时无 timezone，用 replace 对齐
            if expires < datetime.now(timezone.utc).replace(tzinfo=None):
                self.delete(key)
                return None

        return json.loads(row["value"])

    def delete(self, key: str) -> bool:
        """删除一个键。返回是否删除了任何内容。"""
        with transaction(self._db_path) as conn:
            cursor = conn.execute(
                f"DELETE FROM {TABLE_WORKING_MEMORY} WHERE key = ?",
                (key,),
            )
            return cursor.rowcount > 0

    def list_keys(self, pattern: Optional[str] = None) -> list[str]:
        """列出所有键（可选 SQL LIKE 模式匹配）。"""
        conn = get_connection(self._db_path)
        if pattern:
            cursor = conn.execute(
                f"SELECT key FROM {TABLE_WORKING_MEMORY} WHERE key LIKE ?",
                (pattern,),
            )
        else:
            cursor = conn.execute(f"SELECT key FROM {TABLE_WORKING_MEMORY}")
        return [row["key"] for row in cursor.fetchall()]

    def count(self) -> int:
        """返回当前条目数（含已过期但未清理的条目）。"""
        conn = get_connection(self._db_path)
        cursor = conn.execute(f"SELECT COUNT(*) AS cnt FROM {TABLE_WORKING_MEMORY}")
        return cursor.fetchone()["cnt"]

    def clear_expired(self) -> int:
        """清理所有过期条目。返回清理条数。"""
        now_sql = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")
        with transaction(self._db_path) as conn:
            cursor = conn.execute(
                f"DELETE FROM {TABLE_WORKING_MEMORY} WHERE expires_at IS NOT NULL AND expires_at < ?",
                (now_sql,),
            )
            return cursor.rowcount

    def close(self) -> None:
        """关闭底层连接。"""
        from ocos.storage.connection import close

        close(self._db_path)
