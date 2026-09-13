"""COG-V2 Phase 1: RecallRouter 子记忆召回 + 全局工作空间配额测试。"""

from __future__ import annotations

import json
import sqlite3

import pytest

from ocos.memory.recall_router import RecallRouter, DEFAULT_BUDGETS


def _build_db(path):
    conn = sqlite3.connect(str(path))
    conn.executescript(
        """
        CREATE TABLE knowledge (
            id TEXT PRIMARY KEY, statement TEXT, confidence REAL,
            status TEXT, created_at TEXT, updated_at TEXT
        );
        CREATE TABLE belief (
            id TEXT PRIMARY KEY, statement TEXT, confidence REAL,
            status TEXT, created_at TEXT, last_updated TEXT
        );
        CREATE TABLE episodes (
            id TEXT PRIMARY KEY, action TEXT, goal TEXT, decision TEXT,
            outcome TEXT, context TEXT, created_at TEXT
        );
        """
    )
    conn.commit()
    return conn


def test_knowledge_recall_hits_clean_only(tmp_path):
    db = tmp_path / "r.db"
    conn = _build_db(db)
    conn.execute(
        "INSERT INTO knowledge VALUES (?,?,?,?,datetime('now'),datetime('now'))",
        ("K1", "arXiv API 查询方法：用 search_query 传 AND 组合词", 0.8,
         "unstable"),
    )
    # 拒答/套娃垃圾不得召回
    conn.execute(
        "INSERT INTO knowledge VALUES (?,?,?,?,datetime('now'),datetime('now'))",
        ("K2", "我没有关于 arXiv 查询的权威知识库来源，无法确认", 0.9,
         "unstable"),
    )
    conn.execute(
        "INSERT INTO knowledge VALUES (?,?,?,?,datetime('now'),datetime('now'))",
        ("K3", "EVO-Plan: new_knowledge — 新知识 [procedure] 说套娃", 0.9,
         "unstable"),
    )
    # rejected 不召回
    conn.execute(
        "INSERT INTO knowledge VALUES (?,?,?,?,datetime('now'),datetime('now'))",
        ("K4", "arXiv 查询的另一条干净知识", 0.8, "rejected"),
    )
    conn.commit()
    conn.close()

    items = RecallRouter(db).recall("如何用 arXiv 查询文献")
    ids = [a["artifact_id"] for a in items]
    assert "K1" in ids
    assert "K2" not in ids and "K3" not in ids and "K4" not in ids
    assert all(a["subsystem"] == "semantic" for a in items)


def test_belief_recall_active_threshold(tmp_path):
    db = tmp_path / "b.db"
    conn = _build_db(db)
    conn.execute(
        "INSERT INTO belief VALUES (?,?,?,?,datetime('now'),datetime('now'))",
        ("B1", "宿主机磁盘容量检查通常用 df 命令完成", 0.9, "active"))
    conn.execute(
        "INSERT INTO belief VALUES (?,?,?,?,datetime('now'),datetime('now'))",
        ("B2", "低置信信念不应被召回", 0.5, "active"))
    conn.commit()
    conn.close()

    items = RecallRouter(db).recall("检查宿主机磁盘容量")
    ids = [a["artifact_id"] for a in items]
    assert "B1" in ids and "B2" not in ids


def test_episodic_recall_structures_situation(tmp_path):
    db = tmp_path / "e.db"
    conn = _build_db(db)
    ctx = json.dumps({
        "agent": "researcher",
        "description": "用 curl 探测 GitHub API 趋势榜",
        "success": True,
        "output": "返回 30 个趋势仓库",
    }, ensure_ascii=False)
    conn.execute(
        "INSERT INTO episodes VALUES (?,?,?,?,?,?,datetime('now'))",
        ("E1", "researcher.execute", "用 curl 探测 GitHub API 趋势榜",
         "curl -s api.github.com", '{"success": true}', ctx))
    # 套娃目标的情景不召回
    ctx_junk = json.dumps({
        "agent": "writer",
        "description": "EVO-Plan: new_knowledge — 新知识 [procedure] 套娃",
        "success": True,
    }, ensure_ascii=False)
    conn.execute(
        "INSERT INTO episodes VALUES (?,?,?,?,?,?,datetime('now'))",
        ("E2", "writer.execute", "junk", "", "{}", ctx_junk))
    conn.commit()
    conn.close()

    items = RecallRouter(db).recall("探测 GitHub API 趋势")
    ids = [a["artifact_id"] for a in items]
    assert "E1" in ids and "E2" not in ids
    e1 = next(a for a in items if a["artifact_id"] == "E1")
    assert "既往researcher任务" in e1["text"] and "成功" in e1["text"]
    assert e1["subsystem"] == "episodic"


def test_self_table_absent_is_silent(tmp_path):
    db = tmp_path / "s.db"
    conn = _build_db(db)
    conn.commit()
    conn.close()
    # 无 self_model_fact 表 → 不抛异常
    assert RecallRouter(db).recall("任意查询词") == []


def test_workspace_quota_and_dedup():
    from ocos.agent.agent_runtime import AgentRuntime

    def art(atype, text, score=2, conf=0.8, sub=None):
        d = {"type": atype, "text": text, "score": score,
             "confidence": conf, "artifact_id": text[:8]}
        if sub:
            d["subsystem"] = sub
        return d

    candidates = (
        [art("episode", f"情景记忆编号 {i}", score=3) for i in range(5)]
        + [art("belief", f"语义信念编号 {i}", score=2) for i in range(5)]
        + [art("failure_lesson", "唯一教训", score=5)]
        + [art("observation", "用户最新输入 MARKER", score=6)]
        + [art("episode", "情景记忆编号 0", score=3)]  # 完全重复
    )
    # 未绑定 self 的实例方法（仅用静态归类，无状态依赖）
    selected = AgentRuntime._workspace_select(object.__new__(AgentRuntime),
                                              candidates, total=9)
    assert len(selected) <= 9
    subs = [AgentRuntime._subsystem_of(a) for a in selected]
    assert subs.count("episodic") <= DEFAULT_BUDGETS["episodic"]
    assert subs.count("semantic") <= DEFAULT_BUDGETS["semantic"]
    # 高分用户观测与教训必须保住
    assert any("MARKER" in a["text"] for a in selected)
    assert any(a["type"] == "failure_lesson" for a in selected)
    # 去重生效
    assert sum("情景记忆编号 0" == a["text"] for a in selected) == 1
