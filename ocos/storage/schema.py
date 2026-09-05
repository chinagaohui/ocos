"""SQLite Schema 定义 — 所有持久化表的建表语句和数据字典。"""

STORAGE_SCHEMA_VERSION = 6  # S2.6: goal→goal_legacy（双目标表并存治理）  # UX-P2: user_messages  # AUD-F8: plan_dag

# ── 表名常量 ────────────────────────────────────────────────────────────────

TABLE_WORKING_MEMORY = "working_memory"
TABLE_EVENT_STORE = "event_store"
TABLE_DEAD_LETTER_QUEUE = "dead_letter_queue"
TABLE_CHECKPOINT = "checkpoint"
TABLE_USER = "users"
TABLE_SCHEMA_VERSION = "schema_version"

# P1-B: 记忆域表（从各 store 提取，字节级一致）
TABLE_EPISODES = "episodes"
TABLE_BELIEF = "belief"
TABLE_PATTERN = "pattern"
TABLE_KNOWLEDGE = "knowledge"
TABLE_IDENTITY = "identity"
TABLE_GOAL = "goal"
TABLE_WISDOM = "wisdom_items"

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

# ── P1-B: 记忆域表 DDL（来源: 各 store 模块，保持字节级一致）───────────────

CREATE_EPISODES = [
    """CREATE TABLE IF NOT EXISTS episodes (
        id              TEXT PRIMARY KEY,
        experience_id   TEXT NOT NULL,
        session_id      TEXT NOT NULL DEFAULT 'default',

        -- 客观事实 (What, How, Result, Why)
        context         TEXT NOT NULL DEFAULT '{}',  -- JSON
        goal            TEXT,
        decision        TEXT NOT NULL DEFAULT '',
        action          TEXT NOT NULL DEFAULT '',
        outcome         TEXT NOT NULL DEFAULT '{}',  -- JSON
        condition       TEXT NOT NULL DEFAULT '',

        -- 门控结果
        significance_score  REAL NOT NULL DEFAULT 0.0,
        evaluation_trace    TEXT NOT NULL DEFAULT '{}',  -- JSON (可审计)
        source              TEXT NOT NULL DEFAULT 'decision',

        -- 元数据
        status          TEXT NOT NULL DEFAULT 'active',
        tags            TEXT NOT NULL DEFAULT '[]',  -- JSON array
        created_at      TEXT NOT NULL
    )""",
    "CREATE INDEX IF NOT EXISTS idx_episodes_goal ON episodes(goal, significance_score DESC)",
    "CREATE INDEX IF NOT EXISTS idx_episodes_created ON episodes(created_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_episodes_significance ON episodes(significance_score DESC)",
    "CREATE INDEX IF NOT EXISTS idx_episodes_experience ON episodes(experience_id)",
]

CREATE_BELIEF = [
    """CREATE TABLE IF NOT EXISTS belief (
        id                      TEXT PRIMARY KEY,
        statement               TEXT NOT NULL,
        source_knowledge_ids     TEXT NOT NULL,  -- JSON array
        evidence_ids            TEXT NOT NULL,  -- JSON array
        confidence              REAL NOT NULL,
        uncertainty             REAL NOT NULL,
        scope                   TEXT NOT NULL,  -- JSON dict
        status                  TEXT NOT NULL DEFAULT 'active',
        created_at              TEXT NOT NULL,
        last_updated            TEXT NOT NULL
    )""",
    "CREATE INDEX IF NOT EXISTS idx_belief_status   ON belief(status)",
    "CREATE INDEX IF NOT EXISTS idx_belief_confidence ON belief(confidence)",
    "CREATE INDEX IF NOT EXISTS idx_belief_created   ON belief(created_at)",
    "CREATE INDEX IF NOT EXISTS idx_belief_domain    ON belief(json_extract(scope, '$.domain'))",
]

CREATE_PATTERN = [
    """CREATE TABLE IF NOT EXISTS pattern (
        id                      TEXT PRIMARY KEY,
        trigger_condition       TEXT NOT NULL,
        observed_relation       TEXT NOT NULL,
        causal_explanation      TEXT NOT NULL,
        confidence              REAL NOT NULL,
        supporting_episode_count INTEGER NOT NULL,
        source                  TEXT NOT NULL DEFAULT 'episode_aggregation',
        status                  TEXT NOT NULL DEFAULT 'candidate',
        created_at              TEXT NOT NULL,
        validated_at            TEXT,             -- 仅 VALIDATED 状态
        validation_notes        TEXT DEFAULT ''
    )""",
    "CREATE INDEX IF NOT EXISTS idx_pattern_status ON pattern(status)",
    "CREATE INDEX IF NOT EXISTS idx_pattern_confidence ON pattern(confidence DESC)",
    "CREATE INDEX IF NOT EXISTS idx_pattern_created ON pattern(created_at)",
]

CREATE_KNOWLEDGE = [
    """CREATE TABLE IF NOT EXISTS knowledge (
        id                      TEXT PRIMARY KEY,
        statement               TEXT NOT NULL,
        source_patterns         TEXT NOT NULL DEFAULT '[]',   -- JSON array
        confidence              REAL NOT NULL DEFAULT 0.0,
        scope_domain            TEXT NOT NULL DEFAULT '',
        scope_preconditions     TEXT NOT NULL DEFAULT '[]',   -- JSON array
        scope_limitations       TEXT NOT NULL DEFAULT '[]',   -- JSON array
        scope_counterexamples   INTEGER NOT NULL DEFAULT 0,
        stability               REAL NOT NULL DEFAULT 0.0,
        revision                INTEGER NOT NULL DEFAULT 1,
        status                  TEXT NOT NULL DEFAULT 'active',
        created_at              TEXT NOT NULL,
        updated_at              TEXT
    )""",
    "CREATE INDEX IF NOT EXISTS idx_knowledge_domain ON knowledge(scope_domain, confidence DESC)",
    "CREATE INDEX IF NOT EXISTS idx_knowledge_confidence ON knowledge(confidence DESC)",
    "CREATE INDEX IF NOT EXISTS idx_knowledge_stability ON knowledge(stability DESC)",
    "CREATE INDEX IF NOT EXISTS idx_knowledge_status ON knowledge(status)",
    "CREATE INDEX IF NOT EXISTS idx_knowledge_created ON knowledge(created_at DESC)",
]

CREATE_IDENTITY = [
    """CREATE TABLE IF NOT EXISTS identity (
        agent_id TEXT PRIMARY KEY,
        born_at TEXT NOT NULL,
        owner_id TEXT,
        name TEXT NOT NULL DEFAULT 'OCOS Agent',
        version TEXT NOT NULL DEFAULT '1.0.0',
        self_view_json TEXT NOT NULL DEFAULT '{}',
        state_json TEXT NOT NULL DEFAULT '{}',
        anchor_json TEXT NOT NULL DEFAULT '{}',
        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
    )""",
]


# AUD-F8 (2026-08-30): plan_dag — CLI plan 分解结果落库（goal_id 关联 goals 表）

# AUD-F12 (2026-08-30): pending_actions — R4-B 待批队列持久化（DecisionBridge ASK 动作）

# UX-P2 (2026-08-30): user_messages — 用户消息收件箱（ocos say → daemon 消费）
CREATE_USER_MESSAGES = [
    """CREATE TABLE IF NOT EXISTS user_messages (
        id           TEXT PRIMARY KEY,
        sender       TEXT NOT NULL DEFAULT 'cli',
        content      TEXT NOT NULL,
        status       TEXT NOT NULL DEFAULT 'queued',
        created_at   TEXT NOT NULL,
        consumed_at  TEXT,
        note         TEXT DEFAULT '',
        reply        TEXT DEFAULT '',
        replied_at   TEXT
    )""",
    "CREATE INDEX IF NOT EXISTS idx_user_messages_status ON user_messages(status)",
]

CREATE_PENDING_ACTIONS = [
    """CREATE TABLE IF NOT EXISTS pending_actions (
        id              TEXT PRIMARY KEY,
        action_type     TEXT NOT NULL,
        target          TEXT DEFAULT '',
        payload_json    TEXT DEFAULT '{}',
        text            TEXT DEFAULT '',
        source          TEXT DEFAULT '',
        status          TEXT NOT NULL DEFAULT 'pending',
        queued_at       TEXT NOT NULL,
        decided_at      TEXT,
        decided_by      TEXT,
        executed_at     TEXT,
        result_summary  TEXT
    )""",
    "CREATE INDEX IF NOT EXISTS idx_pending_actions_status ON pending_actions(status)",
]

CREATE_PLAN_DAG = [
    """CREATE TABLE IF NOT EXISTS plan_dag (
        plan_id     TEXT PRIMARY KEY,
        goal_id     TEXT NOT NULL,
        dag_json    TEXT NOT NULL,
        strategy    TEXT,
        task_count  INTEGER NOT NULL DEFAULT 0,
        created_at  TEXT NOT NULL
    )""",
    "CREATE INDEX IF NOT EXISTS idx_plan_dag_goal ON plan_dag(goal_id)",
]

CREATE_GOAL = [
    """CREATE TABLE IF NOT EXISTS goal (
        goal_id         TEXT PRIMARY KEY,
        level           INTEGER NOT NULL,
        description     TEXT NOT NULL DEFAULT '',
        parent_id       TEXT,
        priority        REAL NOT NULL DEFAULT 1.0,
        created_at      TEXT NOT NULL,
        deadline        TEXT,
        status          TEXT NOT NULL DEFAULT 'PENDING',
        result_json     TEXT,
        origin_level    TEXT NOT NULL DEFAULT 'SYSTEM',
        authority       TEXT NOT NULL DEFAULT 'AUTONOMOUS'
    )""",
    "CREATE INDEX IF NOT EXISTS idx_goal_status ON goal(status)",
    "CREATE INDEX IF NOT EXISTS idx_goal_level ON goal(level)",
    "CREATE INDEX IF NOT EXISTS idx_goal_priority ON goal(priority DESC)",
]

CREATE_WISDOM = [
    """CREATE TABLE IF NOT EXISTS wisdom_items (
        user_id TEXT NOT NULL,
        wisdom_id TEXT NOT NULL,
        principle TEXT NOT NULL,
        state TEXT NOT NULL,
        source_patterns TEXT NOT NULL DEFAULT '[]',
        evidence TEXT NOT NULL DEFAULT '[]',
        PRIMARY KEY (user_id, wisdom_id)
    )""",
]

STORAGE_TABLES = {
    TABLE_WORKING_MEMORY: CREATE_WORKING_MEMORY,
    TABLE_EVENT_STORE: CREATE_EVENT_STORE,
    TABLE_DEAD_LETTER_QUEUE: CREATE_DEAD_LETTER_QUEUE,
    TABLE_CHECKPOINT: CREATE_CHECKPOINT,
    TABLE_USER: CREATE_USER,
    TABLE_EPISODES: CREATE_EPISODES,
    TABLE_BELIEF: CREATE_BELIEF,
    TABLE_PATTERN: CREATE_PATTERN,
    TABLE_KNOWLEDGE: CREATE_KNOWLEDGE,
    TABLE_IDENTITY: CREATE_IDENTITY,
    TABLE_GOAL: CREATE_GOAL,
    "plan_dag": CREATE_PLAN_DAG,
    "pending_actions": CREATE_PENDING_ACTIONS,
    "user_messages": CREATE_USER_MESSAGES,
    TABLE_WISDOM: CREATE_WISDOM,
}
