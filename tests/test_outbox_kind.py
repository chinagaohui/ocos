"""D1 修复回归（2026-09-07）: outbox 消息 kind 分类。

此前 TUI 把所有 outbound 都渲染为「目标执行结果」面板 — P5.2 提议/
参与度唤醒顶着错误标题进对话流。现在 post_outbound 打 kind 标
(result/proposal/report)，随 /ocos/outbox 透传，TUI 分类渲染。
"""

from __future__ import annotations

import json
import sqlite3
from types import SimpleNamespace

import pytest

from ocos.interaction.inbox import UserInbox


@pytest.fixture
def inbox(tmp_path):
    return UserInbox(db_path=str(tmp_path / "inbox.db"))


class TestKindTagging:
    def test_kind_roundtrip(self, inbox):
        inbox.post_outbound("目标 A 完成", kind="result")
        inbox.post_outbound("目标「x」已 30 天无进展", kind="proposal")
        inbox.post_outbound("[成长叙事 第3章]", kind="report")
        rows = inbox.list_outbound_after()
        kinds = [r["kind"] for r in rows]
        assert kinds == ["result", "proposal", "report"]

    def test_default_is_result(self, inbox):
        inbox.post_outbound("任意出站消息")
        assert inbox.list_outbound_after()[0]["kind"] == "result"

    def test_kind_truncated_to_16(self, inbox):
        inbox.post_outbound("x", kind="x" * 40)
        assert len(inbox.list_outbound_after()[0]["kind"]) == 16

    def test_legacy_migration_adds_kind(self, tmp_path):
        # 模拟旧库: 无 kind 列 + 既有行
        db = str(tmp_path / "legacy.db")
        conn = sqlite3.connect(db)
        conn.execute(
            "CREATE TABLE user_messages (id TEXT PRIMARY KEY, sender TEXT, "
            "content TEXT, status TEXT, created_at TEXT, consumed_at TEXT, "
            "note TEXT DEFAULT '', reply TEXT DEFAULT '', replied_at TEXT)")
        conn.execute(
            "INSERT INTO user_messages VALUES "
            "('M1', 'ocos', '旧消息', 'outbound', '2026-09-01', '', '', '', '')")
        conn.commit()
        conn.close()
        inbox = UserInbox(db_path=db)
        rows = inbox.list_outbound_after()          # 触发迁移
        assert rows[0]["kind"] == ""                # 历史行 kind 空
        inbox.post_outbound("新消息", kind="proposal")
        assert [r["kind"] for r in inbox.list_outbound_after()] == [
            "", "proposal"]


class TestProgressKind:
    """P1 执行可见性（2026-09-08）: kind=progress — 目标认领/执行起点。

    用户反馈"不知道后台是在做还是断了" → daemon 认领目标即发
    progress 出站消息；TUI 独立面板「⟳ 目标认领」不冒充执行结果；
    WebUI pollOutbox 路由 progress 进中央对话流。
    """

    def test_progress_kind_roundtrip(self, inbox):
        inbox.post_outbound("⟳ 已认领目标 GOAL-x：写文件", kind="progress")
        assert inbox.list_outbound_after()[0]["kind"] == "progress"

    def test_tui_renders_progress_panel_not_result(self, inbox):
        """TUI 收到 progress → 「⟳ 目标认领」面板（非「目标执行结果」）。"""
        from ocos.interaction.tui import ChatScreen

        inbox.post_outbound("⟳ 已认领目标 GOAL-x：测试任务", kind="progress")
        rows = inbox.list_outbound_after()
        for r in rows:
            r["rid"] = 1

        app = ChatScreen.__new__(ChatScreen)
        panels: list[tuple[str, str]] = []
        app._outbox_cursor = 0
        app._recent_outbox = []
        app.turn_active = False
        app._pending_approvals = []
        app._approval_hinted = False
        app._panel = lambda body, title, border="dim": panels.append(
            (title, border))
        app._update_status = lambda: None
        app._sys_line = lambda *a, **k: None

        app._render_outbox_rows(rows)          # 真实渲染方法（非复制逻辑）
        assert panels == [("⟳ 目标认领", "cyan")]


class TestDaemonClaimProgress:
    """daemon 认领目标 → progress 出站消息（执行起点可靠锚点）。"""

    @staticmethod
    def _runtime(store, inbox):
        from ocos.daemon import ResidentRuntime
        rt = ResidentRuntime.__new__(ResidentRuntime)
        rt._domain_goal_store = store
        rt._autonomous_inflight = []
        rt._goal_processed = 0
        rt._user_inbox = inbox
        rt._import_goal = lambda **k: True
        return rt

    @staticmethod
    def _store(rows):
        return SimpleNamespace(
            claim_pending_human=lambda limit: rows,
            claim_pending_approved_self=lambda **k: [])

    def test_claim_posts_progress_outbound(self):
        store = self._store([
            {"id": "GOAL-1", "description": "测试任务描述",
             "source": "chat",
             "metadata": json.dumps({"domain": "development"})}])
        posted: list[tuple[str, str]] = []
        inbox = SimpleNamespace(
            post_outbound=lambda content, kind="result":
                posted.append((content, kind)))
        rt = self._runtime(store, inbox)
        assert rt._claim_persisted_goals() == 1
        assert len(posted) == 1
        content, kind = posted[0]
        assert kind == "progress"
        assert "GOAL-1" in content
        assert "测试任务描述" in content

    def test_claim_without_inbox_silent(self):
        """_user_inbox 未装配 → 认领照常、不炸、不发消息。"""
        store = self._store([
            {"id": "GOAL-2", "description": "无 inbox 场景", "source": "cli",
             "metadata": "{}"}])
        rt = self._runtime(store, None)
        assert rt._claim_persisted_goals() == 1
        assert rt._goal_processed == 1


class TestApiPassthrough:
    def test_outbox_api_returns_kind(self, tmp_path, monkeypatch):
        """/ocos/outbox 透传 kind（TUI 分类渲染的数据源）。"""
        import os
        monkeypatch.setenv("OCOS_DB_PATH", str(tmp_path / "api.db"))
        inbox = UserInbox(db_path=os.environ["OCOS_DB_PATH"])
        inbox.post_outbound("提议内容", kind="proposal")
        rows = inbox.list_outbound_after()
        # API 端点直接透传 rows dict（routes/converse.py outbox）
        assert rows[0]["kind"] == "proposal"
        assert rows[0]["content"] == "提议内容"

    def test_outbox_init_cursor_skips_history(self, tmp_path, monkeypatch):
        """after=-1 → 只回当前游标不取历史（UI 首刷跳过存量回放）。

        此前 cursor=0 从最老 20 条开始爬，永远追不上新消息 —
        progress 执行起点消息因此进不了对话流（2026-09-08 实测）。
        """
        import asyncio
        import os
        monkeypatch.setenv("OCOS_DB_PATH", str(tmp_path / "init.db"))
        inbox = UserInbox(db_path=os.environ["OCOS_DB_PATH"])
        inbox.post_outbound("存量消息1", kind="result")
        inbox.post_outbound("存量消息2", kind="proposal")

        from ocos.interaction.api.routes.converse import outbox
        resp = asyncio.run(outbox(after=-1))
        assert resp.data["messages"] == []
        assert resp.data["next_cursor"] == inbox.max_rowid()

        # 游标之后的新消息正常增量透传
        inbox.post_outbound("⟳ 已认领目标 GOAL-x", kind="progress")
        resp2 = asyncio.run(outbox(after=resp.data["next_cursor"]))
        msgs = resp2.data["messages"]
        assert [m["content"] for m in msgs] == ["⟳ 已认领目标 GOAL-x"]
        assert msgs[0]["kind"] == "progress"
