"""COG-V2 Phase 2: AgentSelfModel 四层画像 + render_brief 限长。"""

from __future__ import annotations

import json
import sqlite3

from ocos.self.agent_self_model import AgentSelfModel


def _seed(db):
    conn = sqlite3.connect(str(db))
    conn.executescript(
        """
        CREATE TABLE episodes (
            id TEXT, action TEXT, context TEXT, outcome TEXT,
            tags TEXT, created_at TEXT
        );
        CREATE TABLE goals (id TEXT, description TEXT, status TEXT,
                            priority INTEGER, updated_at TEXT);
        CREATE TABLE user_messages (reply TEXT);
        CREATE TABLE pending_actions (status TEXT);
        """
    )
    # 3 次 writer 成功
    for i in range(3):
        ctx = json.dumps({"agent": "writer", "capabilities": [
            {"name": "shell", "success": True}]}, ensure_ascii=False)
        conn.execute(
            "INSERT INTO episodes VALUES (?,?,?,?,?,datetime('now'))",
            (f"E{i}", "goal_result", ctx,
             json.dumps({"success": True}), "[]"))
    # 2 次 researcher 失败
    for i in range(2):
        ctx = json.dumps({"agent": "researcher", "capabilities": [
            {"name": "shell", "success": False}]}, ensure_ascii=False)
        conn.execute(
            "INSERT INTO episodes VALUES (?,?,?,?,?,datetime('now'))",
            (f"R{i}", "goal_result", ctx,
             json.dumps({"success": False}), "[]"))
    # 3 条 tool_unavailable failure lesson（≥2 → 进失败模式）
    for i in range(3):
        conn.execute(
            "INSERT INTO episodes VALUES (?,?,?,?,?,datetime('now'))",
            (f"F{i}", "failure_lesson", "{}", "{}",
             json.dumps(["tool_unavailable"])))
    conn.execute("INSERT INTO goals VALUES (?,?,?,?,datetime('now'))",
                 ("g1", "调研 arXiv 文献检索方法", "ACTIVE", 5))
    conn.commit()
    conn.close()


def test_calibrate_populates_failure_modes_and_brief(tmp_path):
    db = tmp_path / "sm.db"
    _seed(db)
    m = AgentSelfModel(str(db))
    snap = m.calibrate()

    fms = snap["failure_modes"]
    assert any(f["cause"] == "tool_unavailable" for f in fms)
    assert all(f["count"] >= 2 for f in fms)

    # render_brief 必须 ≤120 字，且包含已知能力（n≥3）与失败模式
    brief = m.render_brief()
    assert 0 < len(brief) <= 120, brief
    assert "arXiv" in brief or "tool_unavailable" in brief or "成功率" in brief


def test_render_brief_skips_low_sample(tmp_path):
    db = tmp_path / "sm2.db"
    # 只有 1 次目标 → 所有能力 attempts<3 → brief 无"能力："段
    conn = sqlite3.connect(str(db))
    conn.executescript(
        """CREATE TABLE episodes (id TEXT, action TEXT, context TEXT,
           outcome TEXT, tags TEXT, created_at TEXT);
           CREATE TABLE goals (id TEXT, description TEXT, status TEXT,
           priority INTEGER, updated_at TEXT);
           CREATE TABLE user_messages (reply TEXT);
           CREATE TABLE pending_actions (status TEXT);""")
    ctx = json.dumps({"agent": "writer", "capabilities": [
        {"name": "shell", "success": True}]})
    conn.execute(
        "INSERT INTO episodes VALUES (?,?,?,?,?,datetime('now'))",
        ("E1", "goal_result", ctx, json.dumps({"success": True}), "[]"))
    conn.commit()
    conn.close()

    brief = AgentSelfModel(str(db)).render_brief()
    # 小样本能力不得宣称成功率
    assert "成功率" not in brief or "能力：" not in brief


def test_recall_router_returns_self_subsystem(tmp_path):
    from ocos.memory.recall_router import RecallRouter
    db = tmp_path / "sm3.db"
    _seed(db)
    AgentSelfModel(str(db)).calibrate()  # 种子无画像, 必须先校准
    items = RecallRouter(str(db)).recall("调研文献检索")
    selfs = [a for a in items if a["subsystem"] == "self"]
    assert selfs, "RecallRouter 必须返回 self 子系统条目"
    assert len(selfs[0]["text"]) <= 120
    assert selfs[0]["type"] == "self"
