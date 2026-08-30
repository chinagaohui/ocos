"""UX-P2: 对话通道测试 — UserInbox + ocos say + daemon 消费 + inject_user_message。"""

from __future__ import annotations

import pytest


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

        rt = AgentRuntime(agent=build_master_agent("t"),
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
        agent = build_master_agent("t")
        rt._runtime = AgentRuntime(agent=agent, max_cycles=10,
                                   db_path=":memory:")
        rt._runtime.boot()

        n = rt._drain_user_inbox()
        assert n == 1
        assert UserInbox(db).count_queued() == 0
