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
            ValueError: 清理过期 + 淘汰后仍超过 max_entries 限制。
        """
        # AUD-FIX (2026-09-12): 工作记忆语义 = 有界 + 淘汰，拒绝新输入是认知错误。
        # 此前满即 raise → attention 分配全链断流（每 tick 刷 warning，生产已复现：
        # 上一实例倾倒 ~740 条 attention 条目后 1000 上限打满，WM 零写入）。
        # 修复: 先清过期 → 仍满则按 rowid 淘汰最老的 attention:/environmental 条目
        # （新感知通常比旧感知更相关）→ 仍满才 raise。
        try:
            self.clear_expired()
        except Exception:
            pass  # 清理失败不阻断写入

        if self.count() >= self._max_entries:
            evict_n = max(1, self._max_entries // 10)
            with transaction(self._db_path) as conn:
                # R10-FIX (2026-09-12): user_input 观测 = 用户刚说的话，驱逐保护。
                # 六轮 A/B 实锤: sensor 洪流（生产 ~50 条/s）下按 rowid 最老优先
                # 驱逐，用户消息 30s 内被 LRU 清空（marker T1 可召回 → T2 已被
                # 驱逐），Observation→Decision 因果链再次断裂。修复: 最新 20 条
                # user_input 观测免驱逐（封顶防累积），非 user_input 不足额时
                # 回退正常驱逐，保证腾出空间。
                conn.execute(
                    f"DELETE FROM {TABLE_WORKING_MEMORY} WHERE rowid IN ("
                    f"  SELECT rowid FROM {TABLE_WORKING_MEMORY}"
                    f"  WHERE key LIKE 'attention:%'"
                    f"    AND rowid NOT IN ("
                    f"      SELECT rowid FROM {TABLE_WORKING_MEMORY}"
                    f"      WHERE key LIKE 'attention:%'"
                    f"        AND value LIKE '%\"source\": \"user_input\"%'"
                    f"      ORDER BY rowid DESC LIMIT 20)"
                    f"  ORDER BY rowid ASC LIMIT ?)",
                    (evict_n,),
                )
                if self.count() >= self._max_entries:
                    # 回退: 满库且非 user_input 不足额 — 按原策略驱逐最老
                    conn.execute(
                        f"DELETE FROM {TABLE_WORKING_MEMORY} WHERE rowid IN ("
                        f"  SELECT rowid FROM {TABLE_WORKING_MEMORY}"
                        f"  WHERE key LIKE 'attention:%'"
                        f"  ORDER BY rowid ASC LIMIT ?)",
                        (evict_n,),
                    )

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

    def recent(self, prefix: str = "attention:", limit: int = 5) -> list[dict[str, Any]]:
        """R10-UNIFY (2026-09-12): 按写入时间倒序返回最近条目（含值）。

        供观测召回（WM → MEM_CTX）：此前 WM 只写不读，观测内容
        无法进入决策上下文，Observation→Decision 因果链断在 Recall。
        """
        conn = get_connection(self._db_path)
        cursor = conn.execute(
            f"SELECT key, value FROM {TABLE_WORKING_MEMORY} "
            "WHERE key LIKE ? ORDER BY rowid DESC LIMIT ?",
            (prefix + "%", max(1, limit)),
        )
        out: list[dict[str, Any]] = []
        for row in cursor.fetchall():
            try:
                out.append({"key": row["key"], "value": json.loads(row["value"])})
            except Exception:
                continue  # 损坏条目跳过，不阻断召回
        return out

    def recent_by_source(
        self, prefix: str = "attention:", source: str = "user_input",
        limit: int = 3,
    ) -> list[dict[str, Any]]:
        """R10-FIX (2026-09-12): 按信源召回最近条目 — user_input 保底通道。

        行为级 A/B 实锤: sensor 噪声吞吐（生产每秒数十条 Process 事件）
        可在数秒内把 user_input 观测挤出 recent(limit=20) 时间窗口，
        source 排序只在窗口内生效，窗口本身守不住 → marker 落库 3 秒
        后即不可召回。本方法按 source 直取，不受无关观测吞吐影响；
        LIKE 粗筛 + JSON 精筛双保险，格式漂移时只漏召不错召。
        """
        conn = get_connection(self._db_path)
        cursor = conn.execute(
            f"SELECT key, value FROM {TABLE_WORKING_MEMORY} "
            "WHERE key LIKE ? AND value LIKE ? ORDER BY rowid DESC LIMIT 200",
            (prefix + "%", f'%"source": "{source}"%'),
        )
        out: list[dict[str, Any]] = []
        for row in cursor.fetchall():
            try:
                val = json.loads(row["value"])
            except Exception:
                continue
            if str(val.get("source", "")) != source:
                continue
            out.append({"key": row["key"], "value": val})
            if len(out) >= max(1, limit):
                break
        return out

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
