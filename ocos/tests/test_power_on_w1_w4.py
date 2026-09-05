"""PW-4.1/PW-1.1 上电测试 — operations 执行层 + WisdomStore 智慧沉淀。"""

from __future__ import annotations

import json

import pytest


@pytest.fixture
def db(tmp_path, monkeypatch):
    path = str(tmp_path / "power.db")
    monkeypatch.setenv("OCOS_DB_PATH", path)
    monkeypatch.setenv("OCOS_APPROVAL_MODE", "ask")
    return path


# ── PW-4.1: 沙盒命令 / HTTP 抓取 ───────────────────────────────────────

class TestOperationsPowered:
    def _bridge(self, store=None):
        from ocos.execution.bridge import DecisionBridge
        b = DecisionBridge(pending_store=store)
        b.attach_default_handlers()
        return b

    def test_run_command_ask_then_execute(self, db):
        """RUN_COMMAND → ASK 待批 → 批准 → 沙盒真实执行。"""
        from ocos.execution.pending import PendingStore
        store = PendingStore(db)
        b = self._bridge(store)
        b.process({"status": "completed",
                   "action_result": {"based_on": {"message": "run command `ls /tmp`"}}})
        rows = store.list_by_status("pending")
        assert rows and rows[0]["action_type"] == "RUN_COMMAND"

        d = b.dispatcher.dispatch_by_name("RUN_COMMAND", json.loads(rows[0]["payload_json"]))
        assert d.status == "done"
        assert d.result["ok"] is True
        assert d.result["blocked"] is False

    def test_run_command_blacklist_blocked(self):
        b = self._bridge()
        d = b.dispatcher.dispatch_by_name("RUN_COMMAND", {"command": "rm -rf /"})
        assert d.status == "done"
        assert d.result["ok"] is False
        assert d.result["blocked"] is True

    def test_run_command_empty_rejected(self):
        b = self._bridge()
        d = b.dispatcher.dispatch_by_name("RUN_COMMAND", {})
        assert d.status == "done"
        assert d.result["ok"] is False

    def test_http_fetch_unknown_url_blocked(self):
        """非白名单 URL → 诚实失败。"""
        b = self._bridge()
        d = b.dispatcher.dispatch_by_name(
            "HTTP_FETCH", {"url": "https://evil.example.com/steal"})
        assert d.status == "done"
        assert d.result["ok"] is False

    def test_ask_flow_uses_pending(self, db):
        """RUN_COMMAND 属 ASK — 不直接执行, 入待批队列。"""
        from ocos.execution.pending import PendingStore
        store = PendingStore(db)
        b = self._bridge(store)
        b.process({"status": "completed",
                   "action_result": {"based_on": {"message": "执行命令 `echo hi`"}}})
        assert len(store.list_by_status("pending")) == 1
        assert not b.audit_records or all(
            getattr(r, "status", "") != "completed" for r in b.audit_records)


# ── PW-1.1: 智慧沉淀 ───────────────────────────────────────────────────

def _seed_episodes(hub, n_per_action=4):
    from ocos.memory.episode.models import Episode
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    n = 0
    for action in ("conversation_reply", "task_execution"):
        for i in range(n_per_action):
            n += 1
            hub.episode.save(Episode(
                id=f"EPI-{n}", experience_id=f"EXP-{n}",
                created_at=now, action=action,
                outcome={"success": True}, significance_score=0.5,
                source="conversation"))


class TestWisdomPowered:
    def test_consolidate_persists_wisdom(self, db):
        from ocos.memory.hub import MemoryHub
        from ocos.agent.wisdom_trigger import consolidate_wisdom
        hub = MemoryHub(db); hub.initialize()
        _seed_episodes(hub)
        out = consolidate_wisdom(hub)
        assert out["patterns"] >= 2
        assert out["candidates"] >= 1
        assert out["persisted"] >= 1
        assert out["wisdom_total"] >= 1

    def test_consolidate_idempotent(self, db):
        from ocos.memory.hub import MemoryHub
        from ocos.agent.wisdom_trigger import consolidate_wisdom
        hub = MemoryHub(db); hub.initialize()
        _seed_episodes(hub)
        first = consolidate_wisdom(hub)
        second = consolidate_wisdom(hub)
        assert second["wisdom_total"] == first["wisdom_total"]  # 幂等

    def test_insufficient_episodes_honest(self, db):
        from ocos.memory.hub import MemoryHub
        from ocos.agent.wisdom_trigger import consolidate_wisdom
        hub = MemoryHub(db); hub.initialize()
        out = consolidate_wisdom(hub)
        assert out["wisdom_total"] == 0
        assert out.get("reason") == "insufficient_episodes"

    def test_wisdom_flows_into_responder_context(self, db):
        """沉淀的智慧回注 ChatResponder 上下文。"""
        from ocos.memory.hub import MemoryHub
        from ocos.agent.wisdom_trigger import consolidate_wisdom
        from ocos.interaction.converse import ChatResponder
        hub = MemoryHub(db); hub.initialize()
        _seed_episodes(hub)
        consolidate_wisdom(hub)
        ctx = ChatResponder(db).build_context()
        assert "人生智慧" in ctx
