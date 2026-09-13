"""COG-V2 Phase 4.1: 遗忘服务 — 引用强化/衰减/过期/情景归档。"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

from ocos.memory.forgetting import ForgettingService
from ocos.memory.recall_router import RecallRouter

_DDL = """
CREATE TABLE knowledge (
    id TEXT PRIMARY KEY, statement TEXT NOT NULL,
    source_patterns TEXT DEFAULT '[]', confidence REAL DEFAULT 0.7,
    scope_domain TEXT DEFAULT '', scope_preconditions TEXT DEFAULT '[]',
    scope_limitations TEXT DEFAULT '[]', scope_counterexamples INTEGER DEFAULT 0,
    stability REAL DEFAULT 0.8, revision INTEGER DEFAULT 1,
    status TEXT DEFAULT 'active', created_at TEXT NOT NULL, updated_at TEXT
);
CREATE TABLE recall_citation (
    id INTEGER PRIMARY KEY AUTOINCREMENT, subsystem TEXT NOT NULL,
    text_hash TEXT NOT NULL, artifact_id TEXT,
    cited_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE episodes (
    id TEXT PRIMARY KEY, experience_id TEXT DEFAULT 'x',
    session_id TEXT DEFAULT 'default', context TEXT DEFAULT '{}',
    goal TEXT, decision TEXT DEFAULT '', action TEXT DEFAULT '',
    outcome TEXT DEFAULT '{}', condition TEXT DEFAULT '',
    significance_score REAL DEFAULT 0.5, evaluation_trace TEXT DEFAULT '{}',
    source TEXT DEFAULT 'decision', status TEXT DEFAULT 'active',
    tags TEXT DEFAULT '[]', created_at TEXT
);
"""


def _db(tmp, name="f4.db"):
    p = tmp / name
    conn = sqlite3.connect(str(p))
    conn.executescript(_DDL)
    conn.commit()
    conn.close()
    return p


def _iso(days_ago: float) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()


def _cited_days_ago(days_ago: float) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days_ago)
            ).strftime("%Y-%m-%d %H:%M:%S")


def _k(db, kid, *, days, conf=0.75, status="unstable", prefix=""):
    conn = sqlite3.connect(str(db))
    conn.execute(
        "INSERT INTO knowledge (id, statement, confidence, status, created_at) "
        "VALUES (?,?,?,?,?)",
        (kid, f"{prefix}redis 哨兵集群 failover 排障要点 {kid}",
         conf, status, _iso(days)))
    conn.commit()
    conn.close()


def _cite(db, kid, *, days_ago, subsystem="semantic"):
    conn = sqlite3.connect(str(db))
    conn.execute(
        "INSERT INTO recall_citation (subsystem, text_hash, artifact_id, cited_at)"
        " VALUES (?,?,?,?)",
        (subsystem, f"h{kid}", kid, _cited_days_ago(days_ago)))
    conn.commit()
    conn.close()


def _ep(db, eid, *, days, status="active", action="writer.execute"):
    conn = sqlite3.connect(str(db))
    conn.execute(
        "INSERT INTO episodes (id, action, status, created_at, context) "
        "VALUES (?,?,?,?,?)",
        (eid, action, status, _iso(days),
         '{"success": true, "description": "redis 排障任务"}'))
    conn.commit()
    conn.close()


# ── 语义衰减/过期 ──────────────────────────────────────────────────────

def test_semantic_decay_uncited_only(tmp_path, monkeypatch):
    monkeypatch.delenv("OCOS_FORGETTING", raising=False)
    db = _db(tmp_path)
    _k(db, "K_OLD", days=31)                       # 31d 无引用 → 衰减
    _k(db, "K_CITED", days=31)                     # 31d 但近窗引用 → 不动
    _cite(db, "K_CITED", days_ago=2)
    _k(db, "K_FRESH", days=5)                      # 新 → 不动
    _k(db, "K_GARBAGE", days=60, status="rejected")

    stats = ForgettingService(str(db)).run()
    assert stats["ran"] is True

    conn = sqlite3.connect(str(db))
    old_conf = conn.execute(
        "SELECT confidence FROM knowledge WHERE id='K_OLD'").fetchone()[0]
    cited_conf, cited_st = conn.execute(
        "SELECT confidence, status FROM knowledge WHERE id='K_CITED'"
    ).fetchone()
    fresh_conf = conn.execute(
        "SELECT confidence FROM knowledge WHERE id='K_FRESH'").fetchone()[0]
    g_status = conn.execute(
        "SELECT status FROM knowledge WHERE id='K_GARBAGE'").fetchone()[0]
    conn.close()
    assert old_conf == pytest.approx(0.375, abs=0.001)
    assert cited_conf == 0.75 and cited_st == "unstable"
    assert fresh_conf == 0.75
    assert g_status == "rejected"
    assert stats["semantic_decayed"] == 1


def test_decay_is_idempotent_and_floored(tmp_path, monkeypatch):
    monkeypatch.delenv("OCOS_FORGETTING", raising=False)
    db = _db(tmp_path)
    _k(db, "K1", days=40, conf=0.62)
    s1 = ForgettingService(str(db)).run()
    s2 = ForgettingService(str(db)).run()
    conn = sqlite3.connect(str(db))
    conf = conn.execute(
        "SELECT confidence FROM knowledge WHERE id='K1'").fetchone()[0]
    conn.close()
    assert s1["semantic_decayed"] == 1
    assert s2["semantic_decayed"] == 0  # 到 floor 后不再写
    assert conf >= 0.35


def test_semantic_expire_90d_uncited(tmp_path, monkeypatch):
    monkeypatch.delenv("OCOS_FORGETTING", raising=False)
    db = _db(tmp_path)
    _k(db, "K_DEAD", days=91)
    _k(db, "K_OLD_CITED", days=120)
    _cite(db, "K_OLD_CITED", days_ago=10)
    _k(db, "K_AGED", days=91, status="unstable", conf=0.9)

    stats = ForgettingService(str(db)).run()
    conn = sqlite3.connect(str(db))
    dead = conn.execute(
        "SELECT status FROM knowledge WHERE id='K_DEAD'").fetchone()[0]
    cited = conn.execute(
        "SELECT status FROM knowledge WHERE id='K_OLD_CITED'").fetchone()[0]
    conn.close()
    assert dead == "deprecated"
    assert cited == "unstable"
    assert stats["semantic_expired"] == 2


def test_recipe_expires_30d_uncited_but_cited_survives(tmp_path, monkeypatch):
    monkeypatch.delenv("OCOS_FORGETTING", raising=False)
    db = _db(tmp_path)
    _k(db, "R_OLD", days=31, prefix="【工具配方】writer 用 curl，")
    _k(db, "R_USED", days=31, prefix="【工具配方】writer 用 sqlite3，")
    _cite(db, "R_USED", days_ago=3, subsystem="procedural")
    _k(db, "R_NEW", days=2, prefix="【工具配方】writer 用 uname，")

    ForgettingService(str(db)).run()
    conn = sqlite3.connect(str(db))
    st = dict(conn.execute(
        "SELECT id, status FROM knowledge").fetchall())
    conn.close()
    assert st["R_OLD"] == "deprecated"
    assert st["R_USED"] == "unstable"
    assert st["R_NEW"] == "unstable"


# ── 情景归档 ──────────────────────────────────────────────────────────

def test_episodes_archived_after_180d(tmp_path, monkeypatch):
    monkeypatch.delenv("OCOS_FORGETTING", raising=False)
    db = _db(tmp_path)
    _ep(db, "E_OLD_A", days=181, status="active")
    _ep(db, "E_OLD_C", days=200, status="consolidated")
    _ep(db, "E_NEW", days=10, status="active")

    stats = ForgettingService(str(db)).run()
    conn = sqlite3.connect(str(db))
    rows = dict(conn.execute("SELECT id, status FROM episodes").fetchall())
    conn.close()
    assert rows["E_OLD_A"] == "archived"
    assert rows["E_OLD_C"] == "archived"
    assert rows["E_NEW"] == "active"
    assert stats["episodes_archived"] == 2
    # 二次运行幂等
    assert ForgettingService(str(db)).run()["episodes_archived"] == 0


# ── 闸门 ──────────────────────────────────────────────────────────────

def test_env_gate_disables(tmp_path, monkeypatch):
    monkeypatch.setenv("OCOS_FORGETTING", "0")
    db = _db(tmp_path)
    _k(db, "K1", days=200)
    _ep(db, "E1", days=200)
    stats = ForgettingService(str(db)).run()
    assert stats["ran"] is False and stats["reason"] == "disabled"
    conn = sqlite3.connect(str(db))
    assert conn.execute(
        "SELECT status FROM knowledge WHERE id='K1'").fetchone()[0] == "unstable"
    assert conn.execute(
        "SELECT status FROM episodes WHERE id='E1'").fetchone()[0] == "active"
    conn.close()


# ── 行为闭环：RecallRouter 引用续命 + deprecated/archived 不可见 ──────

def test_router_reinforces_cited_old_knowledge(tmp_path):
    db = _db(tmp_path, "router.db")
    # 40 天的老知识：一条被近期引用，一条没有
    _k(db, "KC", days=40, conf=0.8, prefix="zookeeper 仲裁集群部署要点 ")
    _k(db, "KN", days=40, conf=0.8, prefix="kafka 分区重平衡处置手册 ")
    _cite(db, "KC", days_ago=1, subsystem="semantic")
    _k(db, "KD", days=40, conf=0.8, prefix="deprecated mongodb 副本集运维 ")
    conn = sqlite3.connect(str(db))
    conn.execute("UPDATE knowledge SET status='deprecated' WHERE id='KD'")
    conn.commit()
    conn.close()
    # 归档的执行 episode 不可召回
    _ep(db, "EA", days=40, status="archived")

    router = RecallRouter(str(db))
    items = router.recall("zookeeper 仲裁集群部署")
    ids = {it.get("artifact_id") for it in items}
    assert "KC" in ids, "近窗被引用的老知识应续命可召回"
    assert "KN" not in ids, "40d 无引用知识不应召回"
    assert "KD" not in ids, "deprecated 不可召回"
    assert "EA" not in ids, "archived episode 不可召回"
