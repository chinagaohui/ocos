"""SQLite Schema 定义 — 所有持久化表的建表语句和数据字典。"""

STORAGE_SCHEMA_VERSION = 2

# ── 表名常量 ────────────────────────────────────────────────────────────────

TABLE_WORKING_MEMORY = "working_memory"
TABLE_EVENT_STORE = "event_store"
TABLE_DEAD_LETTER_QUEUE = "dead_letter_queue"
TABLE_CHECKPOINT = "checkpoint"
TABLE_USER = "users"
TABLE_SCHEMA_VERSION = "schema_version"

# ── 建表 SQL ───────────────────────────────────────────────────────────────

CREATE_SCHEMA_VERSION = """
CREATE TABLE IF NOT EXISTS schema_version (
    version     INTEGER NOT NULL,
    applied_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);
"""

CREATE_WORKING_MEMORY = [
    """CREATE TABLE IF NOT EXISTS working_memory (
        key         TEXT    PRIMARY KEY,
        value       TEXT    NOT NULL,           -- JSON 序列化
        created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
        expires_at  TEXT,                        -- NULL = 永不过期
        ttl_seconds INTEGER                     -- 创建时设置的 TTL
    )""",
    "CREATE INDEX IF NOT EXISTS idx_wm_expires ON working_memory(expires_at)",
]

CREATE_EVENT_STORE = [
    """CREATE TABLE IF NOT EXISTS event_store (
        event_id    TEXT    PRIMARY KEY,
        event_type  TEXT    NOT NULL,
        payload     TEXT    NOT NULL,           -- JSON 序列化
        source      TEXT,
        created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
        sequence    INTEGER NOT NULL            -- 单调递增序号
    )""",
    "CREATE INDEX IF NOT EXISTS idx_es_type   ON event_store(event_type)",
    "CREATE INDEX IF NOT EXISTS idx_es_time   ON event_store(created_at)",
    "CREATE INDEX IF NOT EXISTS idx_es_seq    ON event_store(sequence)",
]

CREATE_DEAD_LETTER_QUEUE = [
    """CREATE TABLE IF NOT EXISTS dead_letter_queue (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        event_id    TEXT    NOT NULL,
        reason      TEXT    NOT NULL,
        payload     TEXT,                       -- JSON 序列化
        failed_at   TEXT    NOT NULL DEFAULT (datetime('now')),
        retry_count INTEGER DEFAULT 0,
        resolved    INTEGER DEFAULT 0           -- 0=未处理, 1=已处理
    )""",
    "CREATE INDEX IF NOT EXISTS idx_dlq_resolved ON dead_letter_queue(resolved)",
]

CREATE_CHECKPOINT = [
    """CREATE TABLE IF NOT EXISTS checkpoint (
        process_id      TEXT    PRIMARY KEY,
        phase           TEXT    NOT NULL,
        context_snapshot TEXT   NOT NULL,       -- JSON 序列化
        created_at      TEXT    NOT NULL DEFAULT (datetime('now')),
        expires_at      TEXT,
        completed       INTEGER DEFAULT 0       -- 0=未完成, 1=已完成
    )""",
    "CREATE INDEX IF NOT EXISTS idx_cp_expires ON checkpoint(expires_at)",
    "CREATE INDEX IF NOT EXISTS idx_cp_completed ON checkpoint(completed)",
]

CREATE_USER = [
    """CREATE TABLE IF NOT EXISTS users (
        user_id         TEXT    PRIMARY KEY,
        name            TEXT    NOT NULL UNIQUE,
        role            TEXT    NOT NULL DEFAULT 'user',
        public_key_hash TEXT,
        created_at      TEXT    NOT NULL DEFAULT (datetime('now')),
        last_active     TEXT,
        preferences     TEXT    DEFAULT '{}'
    )""",
    "CREATE INDEX IF NOT EXISTS idx_users_name ON users(name)",
]

STORAGE_TABLES = {
    TABLE_WORKING_MEMORY: CREATE_WORKING_MEMORY,
    TABLE_EVENT_STORE: CREATE_EVENT_STORE,
    TABLE_DEAD_LETTER_QUEUE: CREATE_DEAD_LETTER_QUEUE,
    TABLE_CHECKPOINT: CREATE_CHECKPOINT,
    TABLE_USER: CREATE_USER,
}
