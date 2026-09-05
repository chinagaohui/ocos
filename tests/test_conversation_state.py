"""FIX-21: ConversationState 对话状态机 — 结构化任务受理/恢复测试。

场景（评审 P0-4）:
  task 受理  → current_goal_id 落库（跨进程/跨重启）
  "继续刚才" → 按状态机精确恢复 goal_id/status/进度，不再 LLM 猜
  目标完成   → 注入真实执行结果 + 状态推进 current→last
"""
from datetime import datetime, timezone

from ocos.interaction.conversation_state import ConversationStateStore
from ocos.interaction.converse import ChatResponder
from ocos.goal.store import GoalStore


def _fake_respond(captured: dict):
    def fake(message, goal_note="", session_id=None, **kw):
        captured["goal_note"] = goal_note
        captured["session_id"] = session_id
        return {"reply": "ok"}
    return fake


def _responder(db: str, monkeypatch, kind_reply: dict) -> ChatResponder:
    r = ChatResponder(db_path=db)
    monkeypatch.setattr(r, "compile_goal", lambda msg: kind_reply)
    return r


def test_set_get_roundtrip_and_persistence(tmp_path):
    db = str(tmp_path / "ocos.db")
    ConversationStateStore(db).update(
        "s1", current_goal_id="GOAL-a", last_intent="task",
        active_topic="分析磁盘")
    # 新实例读同一 db（模拟跨进程/重启）
    st = ConversationStateStore(db).get("s1")
    assert st["current_goal_id"] == "GOAL-a"
    assert st["last_intent"] == "task"
    assert st["active_topic"] == "分析磁盘"


def test_update_merges_fields(tmp_path):
    s = ConversationStateStore(str(tmp_path / "ocos.db"))
    s.update("s1", current_goal_id="GOAL-a", last_intent="task")
    s.update("s1", last_intent="continue")
    st = s.get("s1")
    assert st["current_goal_id"] == "GOAL-a"  # 未被覆盖
    assert st["last_intent"] == "continue"


def test_clear_current_promotes_to_last(tmp_path):
    s = ConversationStateStore(str(tmp_path / "ocos.db"))
    s.update("s1", current_goal_id="GOAL-a")
    s.update("s1", clear_current=True)
    st = s.get("s1")
    assert st["current_goal_id"] is None
    assert st["last_goal_id"] == "GOAL-a"


def test_session_isolation(tmp_path):
    s = ConversationStateStore(str(tmp_path / "ocos.db"))
    s.update("sA", current_goal_id="GOAL-a")
    s.update("sB", current_goal_id="GOAL-b")
    assert s.get("sA")["current_goal_id"] == "GOAL-a"
    assert s.get("sB")["current_goal_id"] == "GOAL-b"


def test_task_acceptance_writes_state(tmp_path, monkeypatch):
    db = str(tmp_path / "ocos.db")
    r = _responder(db, monkeypatch,
                   {"kind": "task", "description": "分析磁盘占用",
                    "domain": "analysis"})
    monkeypatch.setattr(r, "respond", _fake_respond({}))
    out = r.respond_auto("帮我分析磁盘占用", session_id="s9")
    assert out["goal_id"]
    st = ConversationStateStore(db).get("s9")
    assert st["current_goal_id"] == out["goal_id"]
    assert st["last_intent"] == "task"
    # 目标 metadata 记录来源会话（兜底关联用）
    meta = GoalStore(db_path=db).load(out["goal_id"]).get("metadata")
    assert '"session_id": "s9"' in str(meta)


def test_continue_restores_from_state(tmp_path, monkeypatch):
    db = str(tmp_path / "ocos.db")
    r = _responder(db, monkeypatch,
                   {"kind": "task", "description": "分析磁盘占用",
                    "domain": "analysis"})
    monkeypatch.setattr(r, "respond", _fake_respond({}))
    gid = r.respond_auto("帮我分析磁盘占用", session_id="s1")["goal_id"]

    captured: dict = {}
    monkeypatch.setattr(r, "compile_goal", lambda msg: {"kind": "continue"})
    monkeypatch.setattr(r, "respond", _fake_respond(captured))
    r.respond_auto("继续刚才那个任务", session_id="s1")
    assert f"goal_id={gid}" in captured["goal_note"]
    assert "PENDING" in captured["goal_note"]
    assert "不要编造执行结果" in captured["goal_note"]


def test_continue_completed_goal_injects_result_and_clears(
        tmp_path, monkeypatch):
    db = str(tmp_path / "ocos.db")
    r = _responder(db, monkeypatch,
                   {"kind": "task", "description": "报告系统负载",
                    "domain": "analysis"})
    monkeypatch.setattr(r, "respond", _fake_respond({}))
    gid = r.respond_auto("报告系统负载", session_id="s1")["goal_id"]

    # 模拟 daemon 完成 + 结果 episode
    assert GoalStore(db_path=db).mark_completed(gid)
    _insert_goal_result_episode(db)

    captured: dict = {}
    monkeypatch.setattr(r, "compile_goal", lambda msg: {"kind": "continue"})
    monkeypatch.setattr(r, "respond", _fake_respond(captured))
    r.respond_auto("结果怎么样了", session_id="s1")
    assert "【执行结果】" in captured["goal_note"]
    assert "uname" in captured["goal_note"]
    assert "任务成功率=100%" in captured["goal_note"]
    # 状态推进: current 清空, last 保留
    st = ConversationStateStore(db).get("s1")
    assert st["current_goal_id"] is None
    assert st["last_goal_id"] == gid


def test_session_fallback_filters_by_metadata(tmp_path, monkeypatch):
    """无状态机记录时，兜底按 metadata.session_id 关联（原 getattr-dict 恒 None）。"""
    db = str(tmp_path / "ocos.db")
    r = _responder(db, monkeypatch,
                   {"kind": "task", "description": "会话A的任务",
                    "domain": "analysis"})
    monkeypatch.setattr(r, "respond", _fake_respond({}))
    gid_a = r.respond_auto("会话A的任务", session_id="sessA")["goal_id"]

    captured: dict = {}
    monkeypatch.setattr(r, "compile_goal", lambda msg: {"kind": "continue"})
    monkeypatch.setattr(r, "respond", _fake_respond(captured))
    r.respond_auto("刚才任务进展如何", session_id="sessA")
    assert f"goal_id={gid_a}" in captured["goal_note"]


def _insert_goal_result_episode(db: str) -> None:
    from ocos.memory.episode.models import Episode
    from ocos.memory.hub import MemoryHub
    hub = MemoryHub(db)
    hub.initialize()
    ep = Episode(
        id="EPI-TEST-RESULT", experience_id="EXP-GOAL-TEST",
        created_at=datetime.now(timezone.utc),
        session_id="tick_test",
        context={"kind": "goal_execution_result"},
        goal="目标执行结果汇总",
        decision="✓ uname -a → Linux host 7.0.0-28-generic",
        action="goal_result",
        outcome={"success": True, "task_success_rate": 1.0},
        significance_score=0.7,
        source="goal_result",
        tags=["goal_result"],
    )
    hub.episode.save(ep)
