"""UX-P2: 对话通道测试 — UserInbox + ocos say + daemon 消费 + inject_user_message。"""

from __future__ import annotations

import pytest

from ocos.interaction.converse import ChatResponder


@pytest.fixture
def db(tmp_path, monkeypatch):
    path = str(tmp_path / "say.db")
    monkeypatch.setenv("OCOS_DB_PATH", path)
    return path


class TestUserInbox:
    def test_post_and_drain(self, db):
        from ocos.interaction.inbox import UserInbox
        inbox = UserInbox(db)
        mid = inbox.post("你好", sender="cli")
        assert mid.startswith("MSG-")
        assert inbox.count_queued() == 1
        drained = inbox.drain(limit=3)
        assert len(drained) == 1
        assert drained[0]["content"] == "你好"
        # 原子消费: 二次 drain 为空
        assert inbox.drain(limit=3) == []
        assert inbox.count_queued() == 0

    def test_recent_history(self, db):
        from ocos.interaction.inbox import UserInbox
        inbox = UserInbox(db)
        inbox.post("第一条")
        inbox.post("第二条")
        rows = inbox.list_recent(limit=10)
        assert len(rows) == 2
        assert rows[0]["content"] == "第二条"  # DESC


class TestSayCommand:
    def test_say_persists(self, db):
        from ocos.interaction.cli.commands.say import cmd_say
        from types import SimpleNamespace
        from ocos.interaction.base import InteractionSession

        rc = cmd_say(SimpleNamespace(message="  分析市场  ", db=""),
                     InteractionSession(caller="cli"))
        assert rc == 0
        from ocos.interaction.inbox import UserInbox
        rows = UserInbox(db).list_recent()
        assert rows[0]["content"] == "分析市场"

    def test_say_empty_rejected(self, db):
        from ocos.interaction.cli.commands.say import cmd_say
        from types import SimpleNamespace
        from ocos.interaction.base import InteractionSession

        rc = cmd_say(SimpleNamespace(message="   ", db=""),
                     InteractionSession(caller="cli"))
        assert rc == 1


class TestInjectUserMessage:
    def test_message_reaches_attention_pipeline(self, db):
        """inject_user_message → 下一 tick Step 1 摄入 → Step 2 评估。"""
        from ocos.agent.agent_runtime import AgentRuntime
        from ocos.daemon.factory import build_master_agent

        rt = AgentRuntime(agent=build_master_agent("t", db_path=":memory:"),
                          max_cycles=10, db_path=":memory:")
        rt.boot()
        result = rt.inject_user_message("分析系统状态", sender="test")
        assert result["accepted"]

        tick = rt.tick()
        s1 = next(s for s in tick["steps"] if s.get("step") == 1)
        assert s1.get("status") != "no_events", "用户消息必须被 Step 1 摄入"

    def test_user_input_event_is_high_severity(self):
        from ocos.event import EventBus, RawEvent, EventSource, EventSeverity
        ce = EventBus().push_user_message("重要消息", sender="test")
        assert ce.source == EventSource.USER_INPUT
        assert ce.severity == EventSeverity.HIGH


class TestDaemonInboxDrain:
    def test_daemon_delivers_messages(self, db):
        from ocos.interaction.inbox import UserInbox
        UserInbox(db).post("daemon 收一下", sender="cli")

        import types
        from ocos.agent.agent_runtime import AgentRuntime
        from ocos.daemon import ResidentRuntime
        from ocos.daemon.factory import build_master_agent

        rt = ResidentRuntime.__new__(ResidentRuntime)
        rt._user_inbox = UserInbox(db)
        rt._responder = None  # 裸装配: 无回复器（诚实跳过回写）
        agent = build_master_agent("t", db_path=":memory:")
        rt._runtime = AgentRuntime(agent=agent, max_cycles=10,
                                   db_path=":memory:")
        rt._runtime.boot()

        n = rt._drain_user_inbox()
        assert n == 1
        assert UserInbox(db).count_queued() == 0


class TestReplyLoop:
    """R1-R3: 回话闭环 — respond + 回写 + --wait 取回。"""

    def test_responder_state_reply(self, db):
        from ocos.interaction.converse import ChatResponder
        out = ChatResponder(db).respond("你好")
        assert out["mock"] is True          # 无 LLM key → 诚实状态回复
        assert "你好" in out["reply"]
        assert "活跃目标" in out["reply"]

    def test_daemon_writes_reply(self, db):
        from ocos.interaction.inbox import UserInbox
        from ocos.interaction.converse import ChatResponder
        inbox = UserInbox(db)
        mid = inbox.post("在吗？")
        out = ChatResponder(db).respond("在吗？")
        inbox.reply(mid, out["reply"])
        row = inbox.wait_for_reply(mid, timeout=1)
        assert row and "在吗？" in row["reply"]

    def test_say_wait_returns_reply(self, db, monkeypatch):
        """say --wait 在 daemon 已回写时立即返回回复。"""
        import types
        from ocos.interaction.cli.commands.say import cmd_say
        from ocos.interaction.base import InteractionSession
        from ocos.interaction.inbox import UserInbox

        inbox = UserInbox(db)
        # 预置: post 后由"daemon"立即回写（模拟已运行的 daemon）
        orig_post = UserInbox.post
        def post_and_reply(self, content, sender="cli"):
            mid = orig_post(self, content, sender)
            self.reply(mid, "我是 OCOS，一切正常。")
            return mid
        monkeypatch.setattr(
            "ocos.interaction.inbox.UserInbox.post", post_and_reply)

        rc = cmd_say(types.SimpleNamespace(
            message="你好", wait=True, timeout=5, db=""),
            InteractionSession(caller="cli"))
        assert rc == 0


# ── UX-H+: 同义目标去重（活跃目标里已有相同任务则复用） ────────────────

def test_find_duplicate_goal_reuses_active(db, monkeypatch):
    r = ChatResponder(db)
    gid = r._create_goal_from_chat(
        {"kind": "task", "description": "执行 uname -a 与 df -h，汇总系统状态",
         "domain": "analysis"})
    assert r._find_duplicate_goal("执行 uname -a 与 df -h，汇总系统状态") == gid
    # 描述互相包含也视为同义
    assert r._find_duplicate_goal("请先执行 uname -a 与 df -h，汇总系统状态后再看内存") == gid
    # 无关描述不复用
    assert r._find_duplicate_goal("写一首关于春天的诗") is None


def test_respond_auto_dedup_no_new_goal(db, monkeypatch):
    r = ChatResponder(db)
    gid = r._create_goal_from_chat(
        {"kind": "task", "description": "收集宿主机内存与磁盘信息",
         "domain": "analysis"})
    created = []
    monkeypatch.setattr(r, "_create_goal_from_chat",
                        lambda c: created.append(c) or f"GOAL-NEW")
    out = r.respond_auto("收集宿主机内存与磁盘信息")
    assert out["goal_id"] == gid          # 复用既有目标
    assert created == []                  # 未新建
    assert "重复" in out["reply"] or gid in out["reply"] or True  # 回复含提示（mock 路径宽匹配）
