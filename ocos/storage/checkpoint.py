"""CheckpointManager — 基于 SQLite 的进程检查点实现。

职责：
- 保存/加载进程上下文的快照
- 标记检查点为已完成（成功结束）或未完成（中断待恢复）
- 过期清理
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from ocos.storage.connection import get_connection, transaction
from ocos.storage.migrations import ensure_schema
from ocos.storage.schema import TABLE_CHECKPOINT


class CheckpointManager:
    """检查点管理器。

    Args:
        db_path: SQLite 数据库文件路径。
        default_ttl: 检查点的默认有效期（秒），None 表示永不过期。
    """

    def __init__(self, db_path: str, default_ttl: Optional[float] = 86400.0):
        self._db_path = db_path
        self._default_ttl = default_ttl
        ensure_schema(db_path)

    # ── 写入 ──────────────────────────────────────────────────────────────────

    def save(
        self,
        process_id: str,
        phase: str,
        context_snapshot: dict[str, Any],
        ttl: Optional[float] = None,
    ) -> str:
        """保存一个检查点。

        Args:
            process_id: 进程 ID（必须唯一）。
            phase: 当前阶段（如 'planning', 'execution'）。
            context_snapshot: 上下文快照（必须 JSON 可序列化）。
            ttl: 自定义有效期秒数（覆盖 default_ttl）。

        Returns:
            process_id。
        """
        ttl_seconds = ttl if ttl is not None else self._default_ttl
        expires_at = None
        if ttl_seconds is not None and ttl_seconds > 0:
            expires_at = (
                datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(seconds=ttl_seconds)
            ).isoformat()

        with transaction(self._db_path) as conn:
            conn.execute(
                f"INSERT OR REPLACE INTO {TABLE_CHECKPOINT} "
                "(process_id, phase, context_snapshot, expires_at, completed) "
                "VALUES (?, ?, ?, ?, 0)",
                (
                    process_id,
                    phase,
                    json.dumps(context_snapshot, default=str),
                    expires_at,
                ),
            )
        return process_id

    # ── 读取 ──────────────────────────────────────────────────────────────────

    def load(self, process_id: str) -> Optional[dict[str, Any]]:
        """加载一个检查点。

        如果检查点已过期，自动删除并返回 None。
        """
        conn = get_connection(self._db_path)
        cursor = conn.execute(
            f"SELECT * FROM {TABLE_CHECKPOINT} WHERE process_id = ?",
            (process_id,),
        )
        row = cursor.fetchone()
        if row is None:
            return None

        # 过期检查
        if row["expires_at"]:
            expires = datetime.fromisoformat(row["expires_at"])
            if expires < datetime.now(timezone.utc).replace(tzinfo=None):
                self.delete(process_id)
                return None

        return self._row_to_dict(row)

    def list_incomplete(
        self,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """列出所有未完成的检查点（可用于恢复）。"""
        now_sql = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")
        conn = get_connection(self._db_path)
        cursor = conn.execute(
            f"SELECT * FROM {TABLE_CHECKPOINT} "
            "WHERE completed = 0 AND (expires_at IS NULL OR expires_at >= ?) "
            "ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (now_sql, limit, offset),
        )
        return [self._row_to_dict(row) for row in cursor.fetchall()]

    def exists(self, process_id: str) -> bool:
        """检查进程是否存在（含过期检查）。"""
        conn = get_connection(self._db_path)
        cursor = conn.execute(
            f"SELECT 1 FROM {TABLE_CHECKPOINT} WHERE process_id = ?",
            (process_id,),
        )
        return cursor.fetchone() is not None

    def count(self) -> int:
        """返回所有检查点数。"""
        conn = get_connection(self._db_path)
        cursor = conn.execute(f"SELECT COUNT(*) AS cnt FROM {TABLE_CHECKPOINT}")
        return cursor.fetchone()["cnt"]

    # ── 更新 ──────────────────────────────────────────────────────────────────

    def mark_completed(self, process_id: str) -> bool:
        """标记检查点为已完成。"""
        with transaction(self._db_path) as conn:
            cursor = conn.execute(
                f"UPDATE {TABLE_CHECKPOINT} SET completed = 1 WHERE process_id = ?",
                (process_id,),
            )
            return cursor.rowcount > 0

    # ── 删除 ──────────────────────────────────────────────────────────────────

    def delete(self, process_id: str) -> bool:
        """删除一个检查点。"""
        with transaction(self._db_path) as conn:
            cursor = conn.execute(
                f"DELETE FROM {TABLE_CHECKPOINT} WHERE process_id = ?",
                (process_id,),
            )
            return cursor.rowcount > 0

    def clear_expired(self) -> int:
        """清理所有过期检查点。返回清理条数。"""
        now_sql = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")
        with transaction(self._db_path) as conn:
            cursor = conn.execute(
                f"DELETE FROM {TABLE_CHECKPOINT} "
                "WHERE expires_at IS NOT NULL AND expires_at < ?",
                (now_sql,),
            )
            return cursor.rowcount

    def clear_all(self) -> int:
        """清空所有检查点（仅用于测试）。"""
        with transaction(self._db_path) as conn:
            cursor = conn.execute(f"DELETE FROM {TABLE_CHECKPOINT}")
            return cursor.rowcount

    # ── 内部 ──────────────────────────────────────────────────────────────────

    @staticmethod
    def _row_to_dict(row) -> dict[str, Any]:
        return {
            "process_id": row["process_id"],
            "phase": row["phase"],
            "context_snapshot": json.loads(row["context_snapshot"]),
            "created_at": row["created_at"],
            "expires_at": row["expires_at"],
            "completed": bool(row["completed"]),
        }
