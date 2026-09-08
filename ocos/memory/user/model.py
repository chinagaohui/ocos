"""user_model — 用户画像模块

Freeze Phase 47: 记录用户偏好、习惯、人际关系、近期关注
所有决策和记忆检索都将融入用户画像
"""

from __future__ import annotations
import json
import sqlite3
import threading
from dataclasses import dataclass, field, fields
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# O-4: update_profile 对集合字段做合并而非整体替换
_MERGE_DICT_FIELDS = frozenset({"preferences", "relationships", "habits", "context"})
_MERGE_LIST_FIELDS = frozenset({"interests", "recent_focus"})


@dataclass
class UserProfile:
    """用户画像 — 经 UserMemory 的更新方法变更并持久化."""
    user_id: str
    name: str = ""
    description: str = ""           # 一句话描述用户
    preferences: dict[str, Any] = field(default_factory=dict)
    interests: list[str] = field(default_factory=list)
    relationships: dict[str, str] = field(default_factory=dict)  # name -> role
    recent_focus: list[str] = field(default_factory=list)         # 近期关注主题
    habits: dict[str, Any] = field(default_factory=dict)
    context: dict[str, Any] = field(default_factory=dict)         # 当前上下文
    created_at: str = ""
    updated_at: str = ""

    @classmethod
    def create(cls, user_id: str, **kwargs) -> "UserProfile":
        now = datetime.now(timezone.utc).isoformat()
        return cls(
            user_id=user_id,
            created_at=now,
            updated_at=now,
            **kwargs,
        )


class UserMemoryStore:
    """持久化存储 — SQLite + JSON fallback."""

    def __init__(self, db_path: str | Path | None = None):
        # Always use a file path (including /tmp for tests)
        self._path = Path(db_path) if db_path else Path.home() / ".ocos" / "user_model.db"
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        """O-6: 统一连接入口 — busy_timeout 缓解并发写下的 locked 错误."""
        conn = sqlite3.connect(self._path, timeout=10.0)
        conn.execute("PRAGMA busy_timeout=5000")
        return conn

    def _init_db(self) -> None:
        conn = self._connect()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS user_profiles (
                user_id TEXT PRIMARY KEY,
                snapshot TEXT NOT NULL,
                version INTEGER DEFAULT 1,
                updated_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS memory_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                payload TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES user_profiles(user_id)
            )
        """)
        # O-6: WAL 与全仓 memory 层一致, 缓解并发读写下的 database is locked
        conn.execute("PRAGMA journal_mode=WAL")
        conn.commit()
        conn.close()

    def save(self, profile: UserProfile) -> bool:
        with self._lock:
            conn = self._connect()
            try:
                snapshot = json.dumps(profile.__dict__, default=str, ensure_ascii=False)
                row = conn.execute(
                    "SELECT version FROM user_profiles WHERE user_id = ?",
                    (profile.user_id,),
                ).fetchone()
                version = (row[0] + 1) if row else 1  # O-9: 版本递增而非恒 1
                conn.execute(
                    """INSERT OR REPLACE INTO user_profiles
                       (user_id, snapshot, version, updated_at)
                       VALUES (?, ?, ?, ?)""",
                    (profile.user_id, snapshot, version, profile.updated_at),
                )
                conn.commit()
                return True
            finally:
                conn.close()

    def load(self, user_id: str) -> UserProfile | None:
        with self._lock:
            conn = self._connect()
            try:
                row = conn.execute(
                    "SELECT snapshot FROM user_profiles WHERE user_id = ?",
                    (user_id,),
                ).fetchone()
                if row:
                    # O-5: 旧快照含已删字段/缺新字段时按现有字段过滤,
                    # 缺失字段走默认值, 避免 schema 演进导致画像不可恢复加载
                    data = json.loads(row[0])
                    known = {f.name for f in fields(UserProfile)}
                    return UserProfile(**{k: v for k, v in data.items() if k in known})
                return None
            finally:
                conn.close()

    def append_event(self, user_id: str, event_type: str, payload: dict) -> None:
        with self._lock:
            conn = self._connect()
            try:
                conn.execute(
                    """INSERT INTO memory_events
                       (user_id, event_type, payload, created_at)
                       VALUES (?, ?, ?, ?)""",
                    (user_id, event_type, json.dumps(payload, ensure_ascii=False),
                     datetime.now(timezone.utc).isoformat()),
                )
                conn.commit()
            finally:
                conn.close()

    def get_events(self, user_id: str, limit: int = 20) -> list[dict]:
        with self._lock:
            conn = self._connect()
            try:
                rows = conn.execute(
                    """SELECT event_type, payload, created_at
                       FROM memory_events
                       WHERE user_id = ?
                       ORDER BY created_at DESC
                       LIMIT ?""",
                    (user_id, limit),
                ).fetchall()
                return [
                    {"type": r[0], "payload": json.loads(r[1]), "time": r[2]}
                    for r in rows
                ]
            finally:
                conn.close()


class UserMemory:
    """用户记忆中枢 — 聚合画像 + 事件日志."""

    def __init__(self, db_path: str | Path | None = None):
        self._store = UserMemoryStore(db_path)
        self._profile: UserProfile | None = None
        self._lock = threading.RLock()

    # ── Profile CRUD ──────────────────────────────────────────────

    def get_profile(self) -> UserProfile | None:
        with self._lock:
            if self._profile is None:
                # 尝试从 store 加载默认用户
                self._profile = self._store.load("default")
            return self._profile

    def create_profile(self, **kwargs) -> UserProfile:
        user_id = kwargs.pop("user_id", "default")
        profile = UserProfile.create(user_id, **kwargs)
        self.set_profile(profile)
        return profile

    def set_profile(self, profile: UserProfile) -> None:
        with self._lock:
            self._store.save(profile)
            self._profile = profile

    def update_profile(self, **kwargs) -> UserProfile:
        with self._lock:
            if self._profile is None:
                self._profile = UserProfile.create("default")
            for key, value in kwargs.items():
                if not hasattr(self._profile, key):
                    continue
                # O-4: 集合字段合并而非整体替换——原实现的合并分支不可达
                # (dataclass 字段 hasattr 恒 True), 单键更新会清空其余偏好
                if key in _MERGE_DICT_FIELDS and isinstance(value, dict):
                    getattr(self._profile, key).update(value)
                elif key in _MERGE_LIST_FIELDS and isinstance(value, list):
                    current = getattr(self._profile, key)
                    current.extend(v for v in value if v not in current)
                else:
                    setattr(self._profile, key, value)
            self._profile.updated_at = datetime.now(timezone.utc).isoformat()
            self._store.save(self._profile)
            return self._profile

    # ── Events ────────────────────────────────────────────────────

    def record_event(self, event_type: str, payload: dict | None = None) -> None:
        with self._lock:
            user_id = self._profile.user_id if self._profile else "default"
            self._store.append_event(user_id, event_type, payload or {})

    def get_recent_events(self, limit: int = 10) -> list[dict]:
        with self._lock:
            user_id = self._profile.user_id if self._profile else "default"
            return self._store.get_events(user_id, limit)

    # ── Context ───────────────────────────────────────────────────

    def set_context(self, key: str, value: Any) -> None:
        with self._lock:
            if self._profile is None:
                self._profile = UserProfile.create("default")
            self._profile.context[key] = value
            self._profile.updated_at = datetime.now(timezone.utc).isoformat()
            self._store.save(self._profile)

    def get_context(self, key: str | None = None) -> Any:
        with self._lock:
            if self._profile is None:
                return None
            if key:
                return self._profile.context.get(key)
            return dict(self._profile.context)

    # ── Summary ───────────────────────────────────────────────────

    def summarize(self) -> str:
        """生成用户画像摘要 — 用于注入到系统提示."""
        with self._lock:
            profile = self.get_profile()
            if profile is None:
                return "(no user profile yet)"

            parts = [f"## User Profile", f"- ID: {profile.user_id}"]
            if profile.name:
                parts.append(f"- Name: {profile.name}")
            if profile.description:
                parts.append(f"- About: {profile.description}")
            if profile.interests:
                parts.append(f"- Interests: {', '.join(profile.interests)}")
            if profile.recent_focus:
                parts.append(f"- Recent Focus: {', '.join(profile.recent_focus[:5])}")

            events = self.get_recent_events(limit=3)
            if events:
                parts.append("- Recent Activity:")
                for ev in events:
                    parts.append(f"  * {ev['type']}: {str(ev['payload'])[:50]}")

            return "\n".join(parts)
