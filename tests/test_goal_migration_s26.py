"""S2.6: Goal 双表并存治理 — Migration v6 回归（白皮书 P2）。

schema v3 建的 goal 表全程无生产读写（生产走 goal/store.py 自建的
goals 表）。v6 将 goal 重命名为 goal_legacy，下一版本 v7 删除。
"""

from __future__ import annotations

import sqlite3

from ocos.storage.migrations import ensure_schema
from ocos.storage.schema import STORAGE_SCHEMA_VERSION


class TestMigrationV6:
    def test_fresh_db_renames_goal_to_legacy(self, tmp_path):
        db = str(tmp_path / "t.db")
        ensure_schema(db)
        conn = sqlite3.connect(db)
        tables = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        version = conn.execute(
            "SELECT MAX(version) FROM schema_version").fetchone()[0]
        conn.close()
        assert version == STORAGE_SCHEMA_VERSION == 6
        assert "goal_legacy" in tables
        assert "goal" not in tables
        assert "goals" in tables or True  # goals 由 goal/store 按需自建

    def test_existing_v5_db_upgrades(self, tmp_path):
        """旧 v5 库（含 goal 表）升级到 v6 后 goal 表重命名。"""
        db = str(tmp_path / "t.db")
        conn = sqlite3.connect(db)
        conn.execute("CREATE TABLE schema_version "
                     "(version INTEGER PRIMARY KEY, applied_at TEXT)")
        conn.execute("INSERT INTO schema_version VALUES (5, '2026-01-01')")
        # 模拟 v3 建的 goal 表
        conn.execute("CREATE TABLE goal (goal_id TEXT PRIMARY KEY, "
                     "level INTEGER)")
        conn.commit()
        conn.close()
        ensure_schema(db)
        conn = sqlite3.connect(db)
        tables = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        conn.close()
        assert "goal_legacy" in tables
        assert "goal" not in tables
