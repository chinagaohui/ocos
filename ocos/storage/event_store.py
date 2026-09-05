"""SQLiteEventStore — 基于 SQLite 的事件存储实现。

分工裁决（AUD-F6, 2026-08-30）: 本模块 = 持久化事件存储（恢复链专用，
recovery/crash_recovery 消费）；ocos/events/event_store.py = 进程内总线侧
内存 EventStore（契约测试锁定）。按层分工，不合并。

职责：
- 事件持久化存储（append-only）
- 按类型、时间、序列号查询
- 重放（replay）支持
- 事件已实现幂等（event_id 为主键）
"""

from __future__ import annotations

import json
import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from ocos.storage.connection import get_connection, transaction
from ocos.storage.migrations import ensure_schema
from ocos.storage.schema import TABLE_EVENT_STORE


class SQLiteEventStore:
    """SQLite 持久化事件存储（恢复链专用）。

    S3.12: 写路径进程内串行化——storage 连接池为同 db 单共享连接，
    多线程并发 execute 会交错产生 InterfaceError；跨进程由 WAL+timeout
    保证。
    """

    """基于 SQLite 的 EventStore 实现。

    Args:
        db_path: SQLite 数据库文件路径。
    """

    _write_lock = threading.Lock()

    def __init__(self, db_path: str):
        self._db_path = db_path
        ensure_schema(db_path)

    # ── 写入 ──────────────────────────────────────────────────────────────────

    def append(
        self,
        event_type: str,
        payload: dict[str, Any],
        source: Optional[str] = None,
        event_id: Optional[str] = None,
    ) -> str:
        """追加一个事件。已实现幂等（相同 event_id 不会重复写入）。

        Args:
            event_type: 事件类型（如 'process.created', 'goal.updated'）。
            payload: 事件负载（JSON 可序列化字典）。
            source: 事件来源（如 'engine:reasoning', 'agent:master'）。
            event_id: 自定义事件 ID。未提供则自动生成 UUID。

        Returns:
            事件 ID。
        """
        eid = event_id or str(uuid.uuid4())
        with self._write_lock, transaction(self._db_path) as conn:
            # S3.12 (白皮书 P2): sequence 用原子子查询取号——原 SELECT MAX
            # 与 INSERT 分离，多连接并发下撞号（后写者被 INSERT OR IGNORE
            # 静默丢弃）。子查询与 INSERT 同语句，天然原子。
            conn.execute(
                f"INSERT OR IGNORE INTO {TABLE_EVENT_STORE} "
                "(event_id, event_type, payload, source, sequence) "
                "VALUES (?, ?, ?, ?, "
                "(SELECT COALESCE(MAX(sequence), 0) + 1 FROM "
                f"{TABLE_EVENT_STORE}))",
                (eid, event_type, json.dumps(payload, default=str), source),
            )
        return eid

    def append_batch(
        self,
        events: list[dict[str, Any]],
    ) -> list[str]:
        """批量追加事件。原子操作。

        Args:
            events: 事件字典列表，每项含 event_type, payload, [source], [event_id]。

        Returns:
            事件 ID 列表。
        """
        if not events:
            return []

        with self._write_lock, transaction(self._db_path) as conn:
            ids: list[str] = []
            # S3.12: 每行用原子子查询取号（同一事务内单调递增）
            for evt in events:
                eid = evt.get("event_id") or str(uuid.uuid4())
                ids.append(eid)
                conn.execute(
                    f"INSERT OR IGNORE INTO {TABLE_EVENT_STORE} "
                    "(event_id, event_type, payload, source, sequence) "
                    "VALUES (?, ?, ?, ?, "
                    "(SELECT COALESCE(MAX(sequence), 0) + 1 FROM "
                    f"{TABLE_EVENT_STORE}))",
                    (
                        eid,
                        evt["event_type"],
                        json.dumps(evt.get("payload", {}), default=str),
                        evt.get("source"),
                    ),
                )
        return ids

    # ── 读取 ──────────────────────────────────────────────────────────────────

    def load(self, event_id: str) -> Optional[dict[str, Any]]:
        """加载单个事件。"""
        conn = get_connection(self._db_path)
        cursor = conn.execute(
            f"SELECT * FROM {TABLE_EVENT_STORE} WHERE event_id = ?",
            (event_id,),
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return self._row_to_dict(row)

    def replay(
        self,
        event_type: Optional[str] = None,
        since: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """重放事件序列。

        Args:
            event_type: 按事件类型过滤（None 表示全部）。
            since: ISO 时间戳，只返回该时间之后的事件。
            limit: 最大返回条数。
            offset: 分页偏移。

        Returns:
            事件字典列表，按 sequence 升序排列。
        """
        conn = get_connection(self._db_path)
        conditions: list[str] = []
        params: list[Any] = []

        if event_type:
            conditions.append("event_type = ?")
            params.append(event_type)
        if since:
            conditions.append("created_at >= ?")
            params.append(since)

        where = " AND ".join(conditions) if conditions else "1=1"
        cursor = conn.execute(
            f"SELECT * FROM {TABLE_EVENT_STORE} "
            f"WHERE {where} ORDER BY sequence ASC LIMIT ? OFFSET ?",
            (*params, limit, offset),
        )
        return [self._row_to_dict(row) for row in cursor.fetchall()]

    def count(
        self,
        event_type: Optional[str] = None,
        since: Optional[str] = None,
    ) -> int:
        """统计事件数量。"""
        conn = get_connection(self._db_path)
        conditions: list[str] = []
        params: list[Any] = []

        if event_type:
            conditions.append("event_type = ?")
            params.append(event_type)
        if since:
            conditions.append("created_at >= ?")
            params.append(since)

        where = " AND ".join(conditions) if conditions else "1=1"
        cursor = conn.execute(
            f"SELECT COUNT(*) AS cnt FROM {TABLE_EVENT_STORE} WHERE {where}",
            params,
        )
        return cursor.fetchone()["cnt"]

    def latest_sequence(self) -> int:
        """返回当前最大序列号（0 表示空库）。"""
        conn = get_connection(self._db_path)
        cursor = conn.execute(f"SELECT COALESCE(MAX(sequence), 0) AS seq FROM {TABLE_EVENT_STORE}")
        return cursor.fetchone()["seq"]

    def delete_all(self) -> int:
        """清空事件表。返回删除条数（仅用于测试）。"""
        with transaction(self._db_path) as conn:
            cursor = conn.execute(f"DELETE FROM {TABLE_EVENT_STORE}")
            return cursor.rowcount

    # ── 内部 ──────────────────────────────────────────────────────────────────

    def _next_sequence(self) -> int:
        """生成下一个单调递增序列号。"""
        return self.latest_sequence() + 1

    @staticmethod
    def _row_to_dict(row) -> dict[str, Any]:
        return {
            "event_id": row["event_id"],
            "event_type": row["event_type"],
            "payload": json.loads(row["payload"]),
            "source": row["source"],
            "created_at": row["created_at"],
            "sequence": row["sequence"],
        }
