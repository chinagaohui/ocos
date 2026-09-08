"""L4-1 (升级方案 v1.0): VersionedConstitution — 价值观参数化。

原则条目版本化（constitution_versions 表）:
    - 每个版本 = 原则条目列表的 JSON 快照（id/title/content/params）
    - v1 由内置默认原则 bootstrap（诚实优先/主权归人/隐私保护/谨慎自改）
    - 当前版本 = 最高版本号（只增不改 —— 人格演变全程可追溯）

修改走待批（MODIFY_CONSTITUTION 属人工审批动作）:
    propose_change() → PendingStore(action_type='constitution_update')
    → 人工 `ocos approvals approve` → bridge handler（注入回调）→
    save_version() 新版本落库 + audit episode。

prompt 注入: render_principles() 产【价值观宪法】块（对话/决策上下文）。
"""

from __future__ import annotations

import json
import logging
import sqlite3
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

_DDL = """
CREATE TABLE IF NOT EXISTS constitution_versions (
    version     INTEGER PRIMARY KEY,
    principles  TEXT NOT NULL,            -- JSON [{id,title,content,params}]
    reason      TEXT DEFAULT '',
    approved_by TEXT DEFAULT 'human',
    created_at  TEXT NOT NULL
)
"""

# v1 bootstrap 默认原则 — 主权与诚实是底线，参数可经待批演变
DEFAULT_PRINCIPLES: list[dict] = [
    {"id": "honesty", "title": "诚实优先",
     "content": "任何汇报不虚构、不夸大；失败如实归因，能力边界如实声明。",
     "params": {}},
    {"id": "human_sovereignty", "title": "主权归人类主人",
     "content": "重大决策（自改进/身份/审批绕过）必须经主人批准；主人指令优先于自主判断。",
     "params": {}},
    {"id": "privacy", "title": "隐私保护",
     "content": "不外发主人隐私数据；外部通道只传输结果类信息。",
     "params": {}},
    {"id": "caution_self_modify", "title": "谨慎自改",
     "content": "自我修改必须走治理链与快照回滚；主权冻结域（身份锚/宪法本条）不可自动触碰。",
     "params": {"auto_modify_max_risk": 0.2}},
]


@dataclass
class ConstitutionSnapshot:
    """一个宪法版本的完整快照。"""
    version: int
    principles: list[dict] = field(default_factory=list)
    reason: str = ""
    approved_by: str = "human"
    created_at: str = ""

    def to_markdown(self) -> str:
        lines = [f"# 价值观宪法 v{self.version}",
                 f"> 生效于 {self.created_at}（{self.reason or 'bootstrap'}）", ""]
        for p in self.principles:
            params = (f"（参数: {json.dumps(p['params'], ensure_ascii=False)}）"
                      if p.get("params") else "")
            lines.append(f"- **{p['title']}**: {p['content']}{params}")
        return "\n".join(lines)


class VersionedConstitution:
    """宪法原则条目的版本化存储（SQLite，同库共生存）。"""

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.execute(_DDL)
        return conn

    def current(self) -> ConstitutionSnapshot:
        """当前生效版本（无任何版本时 bootstrap v1 默认原则）。"""
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT version, principles, reason, approved_by, created_at "
                "FROM constitution_versions ORDER BY version DESC LIMIT 1"
            ).fetchone()
            if row is None:
                snap = ConstitutionSnapshot(
                    version=1, principles=DEFAULT_PRINCIPLES,
                    reason="bootstrap", approved_by="system",
                    created_at=datetime.now(timezone.utc).isoformat())
                self._write(conn, snap)
                return snap
            return ConstitutionSnapshot(
                version=int(row[0]), principles=json.loads(row[1]),
                reason=row[2], approved_by=row[3], created_at=row[4])
        finally:
            conn.close()

    def history(self, limit: int = 20) -> list[ConstitutionSnapshot]:
        """版本历史（新→旧）——人格演变的可追溯轨迹。"""
        conn = self._conn()
        try:
            rows = conn.execute(
                "SELECT version, principles, reason, approved_by, created_at "
                "FROM constitution_versions ORDER BY version DESC LIMIT ?",
                (limit,)).fetchall()
            return [ConstitutionSnapshot(
                version=int(r[0]), principles=json.loads(r[1]),
                reason=r[2], approved_by=r[3], created_at=r[4]) for r in rows]
        finally:
            conn.close()

    def save_version(self, principles: list[dict], reason: str,
                     approved_by: str = "human") -> ConstitutionSnapshot:
        """落新版本（version = 当前 + 1，只增不改）。调用方须已获人工批准。"""
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT COALESCE(MAX(version), 0) FROM constitution_versions"
            ).fetchone()
            snap = ConstitutionSnapshot(
                version=int(row[0]) + 1, principles=principles,
                reason=reason, approved_by=approved_by,
                created_at=datetime.now(timezone.utc).isoformat())
            self._write(conn, snap)
            logger.info("Constitution v%d saved (%s)", snap.version, reason)
            return snap
        finally:
            conn.close()

    @staticmethod
    def _write(conn: sqlite3.Connection, snap: ConstitutionSnapshot) -> None:
        conn.execute(
            "INSERT OR REPLACE INTO constitution_versions "
            "(version, principles, reason, approved_by, created_at) "
            "VALUES (?,?,?,?,?)",
            (snap.version, json.dumps(snap.principles, ensure_ascii=False),
             snap.reason, snap.approved_by, snap.created_at))
        conn.commit()

    # ── 提案（修改走待批） ────────────────────────────────────────────

    def propose_change(self, db_path: str, change: dict, reason: str) -> dict:
        """原则修改提案 → 待批队列（未经批准永不生效）。

        change: {"principles": [...完整新原则列表...]}（全量快照语义，
        避免增量补丁的合并歧义 —— 人格演变的每一步都是显式整体）。
        """
        from ocos.execution.pending import PendingStore
        store = PendingStore(db_path=db_path)
        pid = store.enqueue(
            action_type="constitution_update",
            target="constitution_versions",
            payload={"principles": change.get("principles", []),
                     "reason": reason},
            text=f"宪法修改提案: {reason}",
            source="l4_constitution")
        # 提案 episode（可溯源）
        try:
            from ocos.memory.episode.models import Episode, EpisodeStatus
            from ocos.memory.episode.store import EpisodeStore
            estore = EpisodeStore(db_path=db_path)
            estore.initialize()
            estore.save(Episode(
                id=f"EPI-CONST-{uuid.uuid4().hex[:12]}",
                experience_id=f"EXP-CONST-{uuid.uuid4().hex[:8]}",
                created_at=datetime.now(timezone.utc),
                session_id="constitution",
                context={"pending_id": pid},
                goal="宪法修改提案",
                decision=reason[:500],
                action="constitution_change_proposal",
                outcome={"success": True, "pending_id": pid},
                significance_score=0.9,
                source="constitution_proposal",
                status=EpisodeStatus.ACTIVE,
                tags=["constitution"],
            ))
        except Exception as e:  # noqa: BLE001 — 提案 episode 失败不阻断
            logger.debug("constitution proposal episode skipped: %s", e)
        return {"pending_id": pid}

    # ── prompt 注入 ───────────────────────────────────────────────────

    def render_principles(self) -> str:
        """【价值观宪法】块 — 注入对话/决策上下文（'我是谁'的一部分）。"""
        snap = self.current()
        lines = [f"价值观宪法 v{snap.version}（修改须经主人批准）:"]
        for p in snap.principles:
            lines.append(f"  - {p['title']}: {p['content']}")
        return "\n".join(lines)
