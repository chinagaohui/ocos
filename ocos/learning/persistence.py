"""FIX-08: Learning 持久化 — rules/skills 落库与加载。

表: learning_models (model_id, strategy, created_at, rules_json, skills_json)
写库失败降级为内存，不阻塞 daemon。
"""
from __future__ import annotations

import json
import logging
import sqlite3
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


def _init_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """CREATE TABLE IF NOT EXISTS learning_models (
            model_id      TEXT PRIMARY KEY,
            strategy      TEXT NOT NULL DEFAULT 'SUPERVISED',
            created_at    TEXT NOT NULL DEFAULT (datetime('now')),
            rules_json    TEXT DEFAULT NULL,
            skills_json   TEXT DEFAULT NULL
        )"""
    )
    conn.commit()


def save_learning_rules(
    db_path: str,
    model_id: str,
    strategy: str,
    rules: list[dict[str, Any]],
    skills: Optional[list[str]] = None,
) -> bool:
    """将学习规则持久化到 SQLite。写库失败返回 False。"""
    if not db_path or db_path == ":memory:":
        return False
    try:
        conn = sqlite3.connect(db_path)
        _init_table(conn)
        conn.execute(
            """INSERT OR REPLACE INTO learning_models
               (model_id, strategy, rules_json, skills_json)
               VALUES (?, ?, ?, ?)""",
            (
                model_id,
                strategy,
                json.dumps(rules, ensure_ascii=False),
                json.dumps(skills or [], ensure_ascii=False),
            ),
        )
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.debug("save_learning_rules failed: %s", e)
        return False


def load_learning_rules(
    db_path: str,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """从 SQLite 读取最近 N 条学习规则（按 created_at 倒序）。

    返回 [{task_pattern, success_rate, success_count}, ...] 格式，
    与 CapabilityConfidence.evaluate 的期望结构兼容。
    """
    if not db_path or db_path == ":memory:":
        return []
    try:
        conn = sqlite3.connect(db_path)
        rows = conn.execute(
            """SELECT rules_json FROM learning_models
               ORDER BY created_at DESC LIMIT ?""",
            (limit,),
        ).fetchall()
        conn.close()
        results = []
        for (rules_json,) in rows:
            if not rules_json:
                continue
            try:
                rules = json.loads(rules_json)
                if isinstance(rules, list):
                    results.extend(rules)
            except Exception:
                pass
        return results[:limit]
    except Exception as e:
        logger.debug("load_learning_rules failed: %s", e)
        return []


def load_learning_summary(db_path: str) -> dict[str, Any]:
    """快速摘要（供 build_context 注入）。"""
    if not db_path or db_path == ":memory:":
        return {"count": 0}
    try:
        conn = sqlite3.connect(db_path)
        row = conn.execute(
            "SELECT COUNT(*), MAX(created_at) FROM learning_models"
        ).fetchone()
        conn.close()
        return {"count": row[0] or 0, "latest": row[1] or ""}
    except Exception:
        return {"count": 0}
