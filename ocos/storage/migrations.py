"""Schema 迁移管理 — 版本追踪、迁移执行。"""

from __future__ import annotations

import sqlite3
from typing import Optional

from ocos.storage.connection import get_connection
from ocos.storage.schema import (
    CREATE_BELIEF,
    CREATE_CHECKPOINT,
    CREATE_DEAD_LETTER_QUEUE,
    CREATE_EPISODES,
    CREATE_EVENT_STORE,
    CREATE_GOAL,
    CREATE_PLAN_DAG,
    CREATE_PENDING_ACTIONS,
    CREATE_USER_MESSAGES,
    CREATE_IDENTITY,
    CREATE_KNOWLEDGE,
    CREATE_PATTERN,
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
    3: (
        "P1-B: 记忆域表（episodes/belief/pattern/knowledge/identity/goal）",
        [
            *CREATE_EPISODES,
            *CREATE_BELIEF,
            *CREATE_PATTERN,
            *CREATE_KNOWLEDGE,
            *CREATE_IDENTITY,
            *CREATE_GOAL,
        ],
    ),
    4: (
        "AUD-F8/F12: plan_dag（CLI plan 落库）+ pending_actions（R4-B 待批队列）",
        [
            *CREATE_PLAN_DAG,
            *CREATE_PENDING_ACTIONS,
        ],
    ),
    5: (
        "UX-P2: user_messages（用户消息收件箱 — ocos say 对话通道）",
        [*CREATE_USER_MESSAGES],
    ),
    6: (
        # S2.6 (白皮书 P2): goal 双表并存治理 —— schema v3 建的 goal 表
        # 全程无生产读写（生产走 goal/store.py 自建的 goals 表），
        # 重命名为 goal_legacy 留一个版本周期后由 v7 删除。
        # NOTE: _apply_migration 对 v6 做了条件化 —— 仅旧 schema goal 表
        # （无 domain 列）才 rename, GoalSQLiteStore 新 goal 表不会被覆盖。
        "S2.6: goal → goal_legacy（双目标表并存治理）",
        [
            "ALTER TABLE goal RENAME TO goal_legacy",
        ],
    ),
    7: (
        # 2026-09-10: LLM 动态生成 SQL 时想查 lessons 表但不存在，
        # 实际 failure_lesson 存在 episodes 表 (action='failure_lesson')。
        # 创建视图让 LLM 查询兼容。
        "L9: lessons 视图 — episodes 表 failure_lesson 别名",
        [
            """CREATE VIEW IF NOT EXISTS lessons AS
               SELECT id, created_at, decision, outcome, context, tags
               FROM episodes
               WHERE action='failure_lesson'""",
        ],
    ),
}


def ensure_schema(db_path: str) -> None:
    """确保数据库 schema 是最新的。自动运行未应用的迁移。"""
    conn = get_connection(db_path)
    current_version = _get_current_version(conn)

    if current_version is None:
        # 全新数据库 — 应用全部迁移
        for version in sorted(MIGRATIONS.keys()):
            _apply_migration(conn, version, MIGRATIONS[version])
            _set_version(conn, version)
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

    # v6 特殊：只 rename 旧 schema（无 domain 列）的 goal 表
    # GoalSQLiteStore 新 goal 表带 domain, 不应被误 rename
    if version == 6:
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        if "goal" not in tables:
            conn.execute("INSERT INTO schema_version (version) VALUES (?)", (version,))
            conn.commit()
            return
        # 检查是否带 domain 列 —— 有则是 GoalSQLiteStore 新表, 跳过 rename
        cols = {r[1] for r in conn.execute("PRAGMA table_info(goal)").fetchall()}
        if "domain" in cols:
            conn.execute("INSERT INTO schema_version (version) VALUES (?)", (version,))
            conn.commit()
            return

    for stmt in sql_statements:
        conn.execute(stmt)
    conn.commit()


def _set_version(conn: sqlite3.Connection, version: int) -> None:
    """记录已应用的版本号。"""
    conn.execute("INSERT INTO schema_version (version) VALUES (?)", (version,))
    conn.commit()
