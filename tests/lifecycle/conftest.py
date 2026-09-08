"""S1–S10 生命周期场景库 — 共享确定性骨架。

来源: docs/OCOS_数字生命升级与测试方案_v1.0.md §3.2 第二层
（场景行为测试: LLM 语义断言 + 确定性骨架）。

确定性约定:
  - 全部场景无 LLM 依赖（bridge 一律显式钉死 _llm_available=False，
    防 ~/.ocos/config.json 有 key 的机器走 LLM 转换路径结果漂移）；
  - 环境隔离: OCOS_AUDIT_DIR / OCOS_AUTONOMY_OVERRIDE /
    OCOS_HEARTBEAT_PATH / OCOS_AUTONOMY_GOAL_CAP 全部指向 tmp_path；
  - 记忆种子两条通道: 裸 episodes 表（bridge/self-model/技能合成
    直读场景）与真实 EpisodeStore（MotivationHub/continuity 等经
    store API 写读的场景，避免同库双 schema 冲突）。
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any


# ── 环境隔离 ─────────────────────────────────────────────────────────────

import pytest


@pytest.fixture(autouse=True)
def _isolated_env(tmp_path, monkeypatch):
    monkeypatch.setenv("OCOS_AUDIT_DIR", str(tmp_path / "audit"))
    monkeypatch.setenv("OCOS_AUTONOMY_OVERRIDE",
                       str(tmp_path / "autonomy_level"))
    monkeypatch.setenv("OCOS_HEARTBEAT_PATH", str(tmp_path / "hb.json"))
    monkeypatch.setenv("OCOS_AUTONOMY_GOAL_CAP", "5")
    return tmp_path


# ── outbox 捕获 ──────────────────────────────────────────────────────────

class FakeInbox:
    """outbox 捕获 — post_outbound 即 TUI /outbox 面板入口（UX-J）。"""

    def __init__(self, db_path: str):
        self._db_path = db_path          # daemon _push_goal_results 只读同库
        self.outbound: list[str] = []

    def post_outbound(self, message: str, kind: str = "result") -> None:
        self.outbound.append(message)


# ── 裸 episodes 表（bridge 直读 / 技能合成 / self-model 统计） ───────────

_RAW_DDL = (
    "CREATE TABLE IF NOT EXISTS episodes ("
    "id TEXT PRIMARY KEY, experience_id TEXT, created_at TEXT, "
    "session_id TEXT, context TEXT, goal TEXT, decision TEXT, "
    "action TEXT, outcome TEXT, condition TEXT, "
    "significance_score REAL, evaluation_trace TEXT, "
    "source TEXT, status TEXT, tags TEXT)")


def make_raw_db(path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path))
    conn.execute(_RAW_DDL)
    return conn


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def insert_lesson(conn: sqlite3.Connection, cause: str,
                  goal_pattern: str = "", created_at: str | None = None,
                  confidence: float = 0.7) -> None:
    """失败 lesson（bridge._failure_prior_hint / MotivationHub 读侧）。"""
    now = created_at or _now()
    conn.execute(
        "INSERT INTO episodes VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, "
        "?, ?, ?, ?, ?)",
        (f"EPI-{uuid.uuid4().hex[:10]}", None, now, "tick_1",
         json.dumps({"goal_pattern": goal_pattern}, ensure_ascii=False),
         goal_pattern[:60], "[LESSON] 失败假设", "failure_lesson",
         json.dumps({"success": False, "cause": cause,
                     "confidence": confidence}),
         f"task failed cause={cause}", 0.55, "{}", "lesson", "ACTIVE",
         json.dumps(["failure_lesson", cause])))
    conn.commit()


def insert_goal_result(conn: sqlite3.Connection, goal: str, decision: str,
                       created_at: str | None = None, agent: str = "",
                       success: bool = True) -> None:
    """goal_result episode（技能合成 / self-model 能力实测读侧）。"""
    now = created_at or _now()
    conn.execute(
        "INSERT INTO episodes VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, "
        "?, ?, ?, ?, ?)",
        (f"EPI-{uuid.uuid4().hex[:10]}", None, now, "tick_1",
         json.dumps({"goal": goal, **({"agent": agent} if agent else {})},
                    ensure_ascii=False), goal[:60], decision, "goal_result",
         json.dumps({"success": success}), "ok", 0.8, "{}",
         "goal_result", "ACTIVE", "[]"))
    conn.commit()


# ── 真实 EpisodeStore 通道（MotivationHub / continuity 读写） ────────────

def seed_episode(db_path, *, source: str, decision: str = "",
                 action: str = "", tags: list[str] | None = None,
                 context: dict | None = None, outcome: dict | None = None,
                 created_at: datetime | None = None,
                 session_id: str = "lifecycle") -> None:
    from ocos.memory.episode.models import Episode, EpisodeStatus
    from ocos.memory.episode.store import EpisodeStore
    store = EpisodeStore(db_path=str(db_path))
    store.initialize()
    store.save(Episode(
        id=f"EPI-{uuid.uuid4().hex[:12]}",
        experience_id=f"EXP-{uuid.uuid4().hex[:8]}",
        created_at=created_at or datetime.now(timezone.utc),
        session_id=session_id,
        context=context or {},
        decision=decision, action=action,
        outcome=outcome or {},
        source=source, status=EpisodeStatus.ACTIVE,
        tags=tags or []))


# ── 确定性 bridge ────────────────────────────────────────────────────────

def make_bridge(pending_store: Any = None):
    """无 LLM 依赖的 DecisionBridge（attach 后 handler 可达）。"""
    from ocos.execution.bridge import DecisionBridge
    b = DecisionBridge(pending_store=pending_store)
    b.attach_default_handlers()
    b._llm_available = lambda: False     # 契约: 本场景库零 LLM 依赖
    return b


def learning_marks(tmp_path) -> list[dict]:
    """learning.jsonl 读取（L8 消费打点观测）。"""
    path = tmp_path / "audit" / "learning.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(
        encoding="utf-8").splitlines() if line.strip()]
