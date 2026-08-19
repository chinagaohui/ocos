"""User 模型与 UserStore 实现。

User:
- 不可变 frozen dataclass
- 拥有 role、preferences、认证信息

UserStore:
- SQLite 持久化
- 按 user_id 和 name 查询
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from ocos.storage.connection import get_connection, transaction

from ocos.auth.role import Role


@dataclass(frozen=True)
class User:
    """OCOS 用户模型。"""
    user_id: str
    name: str
    role: Role
    public_key_hash: Optional[str] = None
    created_at: Optional[str] = None
    last_active: Optional[str] = None
    preferences: dict[str, Any] = field(default_factory=dict)

    def to_row(self) -> dict[str, Any]:
        return {
            "user_id": self.user_id,
            "name": self.name,
            "role": self.role.value,
            "public_key_hash": self.public_key_hash,
            "created_at": self.created_at,
            "last_active": self.last_active,
            "preferences": json.dumps(self.preferences, ensure_ascii=False, default=str),
        }

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "User":
        return cls(
            user_id=row["user_id"],
            name=row["name"],
            role=Role(row["role"]),
            public_key_hash=row["public_key_hash"],
            created_at=row["created_at"],
            last_active=row["last_active"],
            preferences=json.loads(row["preferences"]) if row["preferences"] else {},
        )


class UserStore:
    """用户存储 — SQLite 持久化。"""

    def __init__(self, db_path: str):
        self._db_path = db_path
        self._ensure_table()

    def _ensure_table(self) -> None:
        from ocos.storage.schema import CREATE_USER
        conn = get_connection(self._db_path)
        for stmt in CREATE_USER:
            conn.execute(stmt)
        conn.commit()

    def save(self, user: User) -> str:
        """保存用户。已存在则更新。"""
        with transaction(self._db_path) as conn:
            row = user.to_row()
            conn.execute(
                f"INSERT OR REPLACE INTO users "
                f"(user_id, name, role, public_key_hash, created_at, last_active, preferences) "
                f"VALUES (:user_id, :name, :role, :public_key_hash, :created_at, :last_active, :preferences)",
                row,
            )
        return user.user_id

    def load(self, user_id: str) -> Optional[User]:
        """按 user_id 加载用户。"""
        conn = get_connection(self._db_path)
        cursor = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        return User.from_row(row) if row else None

    def load_by_name(self, name: str) -> Optional[User]:
        """按 name 加载用户。"""
        conn = get_connection(self._db_path)
        cursor = conn.execute("SELECT * FROM users WHERE name = ?", (name,))
        row = cursor.fetchone()
        return User.from_row(row) if row else None

    def list(self) -> list[User]:
        """列出所有用户。"""
        conn = get_connection(self._db_path)
        cursor = conn.execute("SELECT * FROM users ORDER BY created_at")
        return [User.from_row(row) for row in cursor.fetchall()]

    def update_last_active(self, user_id: str) -> None:
        """更新用户的最后活跃时间。"""
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")
        with transaction(self._db_path) as conn:
            conn.execute(
                "UPDATE users SET last_active = ? WHERE user_id = ?",
                (now, user_id),
            )

    def count(self) -> int:
        """返回用户数。"""
        conn = get_connection(self._db_path)
        cursor = conn.execute("SELECT COUNT(*) as cnt FROM users")
        return cursor.fetchone()["cnt"]
