"""Schema 迁移管理 — 版本追踪、迁移执行。"""

from __future__ import annotations

import sqlite3
from typing import Optional

from ocos.storage.connection import get_connection
from ocos.storage.schema import (
    CREATE_CHECKPOINT,
    CREATE_DEAD_LETTER_QUEUE,
    CREATE_EVENT_STORE,
    CREATE_SCHEMA_VERSION,
    CREATE_USER,
    CREATE_WORKING_MEMORY,
    TABLE_SCHEMA_VERSION,
    STORAGE_SCHEMA_VERSION,
)

# ── 迁移函数注册表 ─────────────────────────────────────────────────────────
# key=目标版本号, value=(描述, SQL 语句列表)

MIGRATIONS: dict[int, tuple[str, list[str]]] = {
    1: (
        "初始 schema：working_memory, event_store, dead_letter_queue, checkpoint",
        [
            CREATE_SCHEMA_VERSION,
            *CREATE_WORKING_MEMORY,
            *CREATE_EVENT_STORE,
            *CREATE_DEAD_LETTER_QUEUE,
            *CREATE_CHECKPOINT,
        ],
    ),
    2: (
        "新增 users 表（身份与权限）",
        [*CREATE_USER],
    ),
}


def ensure_schema(db_path: str) -> None:
    """确保数据库 schema 是最新的。自动运行未应用的迁移。"""
    conn = get_connection(db_path)
    current_version = _get_current_version(conn)

    if current_version is None:
        # 全新数据库 — 应用全部迁移
        _apply_migration(conn, 1, MIGRATIONS[1])
        _apply_migration(conn, 2, MIGRATIONS[2])
        _set_version(conn, 2)
        return

    # 后续版本迁移在此追加
    for version in sorted(MIGRATIONS.keys()):
        if version > current_version:
            _apply_migration(conn, version, MIGRATIONS[version])
            _set_version(conn, version)


def _get_current_version(conn: sqlite3.Connection) -> Optional[int]:
    """读取当前 schema 版本号。"""
    try:
        cursor = conn.execute("SELECT MAX(version) FROM schema_version")
        row = cursor.fetchone()
        return row[0] if row and row[0] is not None else None
    except sqlite3.OperationalError:
        # schema_version 表还不存在
        return None


def _apply_migration(conn: sqlite3.Connection, version: int, migration: tuple[str, list[str]]) -> None:
    """执行单个迁移版本。"""
    description, sql_statements = migration
    for stmt in sql_statements:
        conn.execute(stmt)
    conn.commit()


def _set_version(conn: sqlite3.Connection, version: int) -> None:
    """记录已应用的版本号。"""
    conn.execute("INSERT INTO schema_version (version) VALUES (?)", (version,))
    conn.commit()
