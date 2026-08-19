"""Phase 23 — Skill Registry。

SQLite 持久化的 Skill 和 SkillGraph 注册表。
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from ocos.capability.models import Skill, SkillGraph


class SkillRegistry:
    """Skill 和 SkillGraph 的 SQLite 持久化存储。

    用法:
        registry = SkillRegistry(db_path="ocos/capability.db")
        registry.init_db()

        skill = Skill(id="infer", name="Inference", ...)
        registry.save_skill(skill)

        graph = SkillGraph(id="solve", name="Problem Solving", skills=[skill])
        registry.save_graph(graph)

        loaded = registry.load_graph("solve")
    """

    # ── 默认 SQL Schema ──────────────────────────────────────────────────

    DEFAULT_SCHEMA = """
    CREATE TABLE IF NOT EXISTS skill (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        description TEXT DEFAULT '',
        prerequisite TEXT DEFAULT '[]',
        input_state TEXT DEFAULT '{}',
        output_state TEXT DEFAULT '{}',
        required_capability TEXT DEFAULT 'reasoning',
        failure_condition TEXT,
        evaluation_method TEXT,
        improvement_history TEXT DEFAULT '[]',
        version TEXT DEFAULT '1.0.0',
        fallback_strategy TEXT DEFAULT 'abort',
        max_retries INTEGER DEFAULT 0,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS skill_graph (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        description TEXT DEFAULT '',
        skill_ids TEXT DEFAULT '[]',
        entry_point TEXT,
        version TEXT DEFAULT '1.0.0',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        metadata TEXT DEFAULT '{}'
    );
    """

    def __init__(self, db_path: str | Path = "ocos/capability.db"):
        self._db_path = Path(db_path)
        self._conn: Optional[sqlite3.Connection] = None

    # ── 连接管理 ────────────────────────────────────────────────────────

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._db_path.parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(str(self._db_path))
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
        return self._conn

    def init_db(self) -> None:
        """初始化数据库表。"""
        conn = self._get_conn()
        conn.executescript(self.DEFAULT_SCHEMA)
        conn.commit()

    def close(self) -> None:
        """关闭连接。"""
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    # ── Skill CRUD ───────────────────────────────────────────────────────

    def save_skill(self, skill: Skill) -> None:
        """保存或更新 Skill。"""
        conn = self._get_conn()
        conn.execute(
            """
            INSERT OR REPLACE INTO skill (
                id, name, description, prerequisite,
                input_state, output_state, required_capability,
                failure_condition, evaluation_method, improvement_history,
                version, fallback_strategy, max_retries,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                skill.id,
                skill.name,
                skill.description,
                json.dumps(skill.prerequisite),
                json.dumps(skill.input_state),
                json.dumps(skill.output_state),
                skill.required_capability,
                skill.failure_condition,
                skill.evaluation_method,
                json.dumps(skill.improvement_history),
                skill.version,
                skill.fallback_strategy,
                skill.max_retries,
                skill.created_at.isoformat(),
                skill.updated_at.isoformat(),
            ),
        )
        conn.commit()

    def load_skill(self, skill_id: str) -> Optional[Skill]:
        """按 ID 加载 Skill。"""
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM skill WHERE id = ?", (skill_id,)
        ).fetchone()
        if row is None:
            return None
        return self._row_to_skill(row)

    def list_skills(self) -> list[Skill]:
        """列出所有 Skill。"""
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM skill ORDER BY name"
        ).fetchall()
        return [self._row_to_skill(r) for r in rows]

    def delete_skill(self, skill_id: str) -> bool:
        """删除 Skill。返回是否实际删除了行。"""
        conn = self._get_conn()
        c = conn.execute("DELETE FROM skill WHERE id = ?", (skill_id,))
        conn.commit()
        return c.rowcount > 0

    # ── SkillGraph CRUD ──────────────────────────────────────────────────

    def save_graph(self, graph: SkillGraph) -> None:
        """保存 SkillGraph。

        只保存 skill_ids；加载时需通过 load_skill 重建。

        Args:
            restore_skills: 可选，预先加载的 Skill 字典 {id: Skill}

        Returns:
            带完整 Skill 列表的 SkillGraph
        """
        conn = self._get_conn()
        conn.execute(
            """
            INSERT OR REPLACE INTO skill_graph (
                id, name, description, skill_ids,
                entry_point, version,
                created_at, updated_at, metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                graph.id,
                graph.name,
                graph.description,
                json.dumps([s.id for s in graph.skills]),
                graph.entry_point,
                graph.version,
                graph.created_at.isoformat(),
                graph.updated_at.isoformat(),
                json.dumps(graph.metadata),
            ),
        )
        conn.commit()

    def load_graph(self, graph_id: str) -> Optional[SkillGraph]:
        """按 ID 加载 SkillGraph。

        skill_ids 还原为完整的 Skill 对象。
        """
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM skill_graph WHERE id = ?", (graph_id,)
        ).fetchone()
        if row is None:
            return None

        skill_ids: list[str] = json.loads(row["skill_ids"])
        skills: list[Skill] = []
        for sid in skill_ids:
            skill = self.load_skill(sid)
            if skill:
                skills.append(skill)
            else:
                skills.append(Skill(id=sid, name=sid))  # 占位

        return SkillGraph(
            id=row["id"],
            name=row["name"],
            description=row["description"] or "",
            skills=skills,
            entry_point=row["entry_point"],
            version=row["version"] or "1.0.0",
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            metadata=json.loads(row["metadata"] or "{}"),
        )

    def list_graphs(self) -> list[SkillGraph]:
        """列出所有 SkillGraph（不含完整 Skill）。"""
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT id, name, description, version FROM skill_graph ORDER BY name"
        ).fetchall()
        return [
            SkillGraph(
                id=r["id"],
                name=r["name"],
                description=r["description"] or "",
                version=r["version"] or "1.0.0",
                skills=[],
            )
            for r in rows
        ]

    def delete_graph(self, graph_id: str) -> bool:
        """删除 SkillGraph。"""
        conn = self._get_conn()
        c = conn.execute("DELETE FROM skill_graph WHERE id = ?", (graph_id,))
        conn.commit()
        return c.rowcount > 0

    # ── 辅助 ────────────────────────────────────────────────────────────

    @staticmethod
    def _row_to_skill(row: sqlite3.Row) -> Skill:
        return Skill(
            id=row["id"],
            name=row["name"],
            description=row["description"] or "",
            prerequisite=json.loads(row["prerequisite"] or "[]"),
            input_state=json.loads(row["input_state"] or "{}"),
            output_state=json.loads(row["output_state"] or "{}"),
            required_capability=row["required_capability"] or "reasoning",
            failure_condition=row["failure_condition"],
            evaluation_method=row["evaluation_method"],
            improvement_history=json.loads(row["improvement_history"] or "[]"),
            version=row["version"] or "1.0.0",
            fallback_strategy=row["fallback_strategy"] or "abort",
            max_retries=row["max_retries"] or 0,
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )
