"""L4-1 (升级方案 v1.0) — 价值观参数化测试：宪法版本化 + 待批 + prompt 注入。

覆盖:
  - bootstrap: 全新库 current() → v1 默认原则（诚实/主权/隐私/谨慎自改）并落库
  - 版本只增不改: save_version 递增; history 新→旧
  - propose_change: 待批入队 + 提案 episode 溯源（未经批准永不生效）
  - bridge constitution_update handler: 无 sink 诚实报错 / 有 sink 落新版本 /
    空 principles 拒绝
  - 审批执行链: execute_approved + approval_id 溯源 → 新版本生效
  - 装配层: build_execution_bridge 注入 constitution_sink → CLI 批准可落库
  - prompt 注入: render_principles 含版本号与原则标题; build_context 含宪法块
"""

from __future__ import annotations

import json
import sqlite3

import pytest

from ocos.constitution.versioned import (
    DEFAULT_PRINCIPLES,
    VersionedConstitution,
)


@pytest.fixture()
def db(tmp_path):
    p = str(tmp_path / "l4.db")
    from ocos.memory.episode.store import EpisodeStore
    EpisodeStore(db_path=p).initialize()
    return p


def _make_bridge(db, **kw):
    from ocos.execution.bridge import DecisionBridge
    from ocos.execution.pending import PendingStore
    bridge = DecisionBridge(pending_store=PendingStore(db_path=db),
                            db_path=db, **kw)
    bridge.attach_default_handlers()
    return bridge


# ── bootstrap 与版本化 ────────────────────────────────────────────────


class TestBootstrap:
    def test_bootstrap_v1_defaults(self, db):
        snap = VersionedConstitution(db).current()
        assert snap.version == 1
        assert len(snap.principles) == 4
        ids = {p["id"] for p in snap.principles}
        assert {"honesty", "human_sovereignty", "privacy",
                "caution_self_modify"} == ids
        assert snap.approved_by == "system"

    def test_bootstrap_persists(self, db):
        vc = VersionedConstitution(db)
        vc.current()
        # 第二次读不再重复 bootstrap（仍是 v1）
        assert vc.current().version == 1
        conn = sqlite3.connect(db)
        n = conn.execute(
            "SELECT COUNT(*) FROM constitution_versions").fetchone()[0]
        conn.close()
        assert n == 1

    def test_save_version_increments(self, db):
        vc = VersionedConstitution(db)
        vc.current()  # bootstrap v1
        new = [dict(p) for p in DEFAULT_PRINCIPLES]
        new[0]["params"] = {"strictness": "high"}
        snap = vc.save_version(new, reason="测试修订", approved_by="human")
        assert snap.version == 2
        assert snap.principles[0]["params"] == {"strictness": "high"}
        # v1 快照未被改写（只增不改）
        hist = vc.history()
        assert [h.version for h in hist] == [2, 1]
        assert hist[1].principles[0].get("params") == {}

    def test_snapshot_markdown(self, db):
        md = VersionedConstitution(db).current().to_markdown()
        assert "# 价值观宪法 v1" in md
        assert "诚实优先" in md


# ── 提案（修改走待批） ────────────────────────────────────────────────


class TestPropose:
    def test_propose_enqueues_pending(self, db):
        from ocos.execution.pending import PendingStore
        vc = VersionedConstitution(db)
        out = vc.propose_change(
            db, {"principles": DEFAULT_PRINCIPLES}, reason="加严诚实条款")
        pid = out["pending_id"]
        row = PendingStore(db_path=db).get(pid)
        assert row is not None
        assert row["status"] == "pending"
        assert row["action_type"] == "constitution_update"
        payload = json.loads(row["payload_json"])
        assert payload["reason"] == "加严诚实条款"
        assert len(payload["principles"]) == 4

    def test_propose_episode_traceable(self, db):
        from ocos.memory.episode.store import EpisodeStore
        vc = VersionedConstitution(db)
        out = vc.propose_change(db, {"principles": []}, reason="r")
        estore = EpisodeStore(db_path=db)
        estore.initialize()
        rows = estore.query_by_time(limit=50)
        matches = [e for e in rows
                   if getattr(e, "source", "") == "constitution_proposal"]
        assert len(matches) == 1
        assert matches[0].context.get("pending_id") == out["pending_id"]

    def test_propose_does_not_change_current(self, db):
        vc = VersionedConstitution(db)
        before = vc.current().version
        vc.propose_change(db, {"principles": DEFAULT_PRINCIPLES}, reason="x")
        # 提案≠生效 — 未经批准版本不变
        assert vc.current().version == before


# ── bridge handler ───────────────────────────────────────────────────


class TestBridgeHandler:
    def test_no_sink_honest_error(self, db):
        bridge = _make_bridge(db)
        r = bridge.dispatcher.dispatch_by_name(
            "constitution_update",
            {"principles": DEFAULT_PRINCIPLES, "reason": "x"})
        assert r is not None and r.status == "done"
        assert r.result["ok"] is False
        assert "constitution_sink" in r.result["error"]

    def test_empty_principles_rejected(self, db):
        bridge = _make_bridge(db, constitution_sink=lambda p: {"version": 9})
        r = bridge.dispatcher.dispatch_by_name(
            "constitution_update", {"principles": [], "reason": "x"})
        assert r.result["ok"] is False
        assert "principles" in r.result["error"]

    def test_with_sink_applies_version(self, db):
        vc = VersionedConstitution(db)
        vc.current()

        def _sink(payload):
            snap = vc.save_version(payload["principles"],
                                   reason=payload["reason"])
            return {"version": snap.version}

        bridge = _make_bridge(db, constitution_sink=_sink)
        new_principles = [dict(p) for p in DEFAULT_PRINCIPLES]
        new_principles.append({"id": "focus", "title": "专注用户目标",
                               "content": "空闲算力优先服务主人目标。",
                               "params": {}})
        r = bridge.dispatcher.dispatch_by_name(
            "constitution_update",
            {"principles": new_principles, "reason": "新增专注原则"})
        assert r.result["ok"] is True
        assert r.result["version"] == 2
        assert vc.current().version == 2
        assert any(p["id"] == "focus" for p in vc.current().principles)


# ── 审批执行链（approval_id 溯源） ─────────────────────────────────────


class TestApprovalFlow:
    def test_execute_approved_full_chain(self, db):
        from ocos.execution.pending import PendingStore
        vc = VersionedConstitution(db)
        vc.current()
        out = vc.propose_change(
            db, {"principles": DEFAULT_PRINCIPLES, "reason": "批准链测试"},
            reason="批准链测试")

        def _sink(payload):
            snap = vc.save_version(payload["principles"],
                                   reason=payload["reason"])
            return {"version": snap.version}

        bridge = _make_bridge(db, constitution_sink=_sink)
        store = PendingStore(db_path=db)
        assert store.decide(out["pending_id"], approved=True,
                            decided_by="test")
        payload = {"principles": DEFAULT_PRINCIPLES,
                   "reason": "批准链测试",
                   "approval_id": out["pending_id"]}
        dispatched = bridge.execute_approved("constitution_update", payload)
        assert dispatched.status == "done"
        assert dispatched.result["ok"] is True
        assert dispatched.result["version"] == 2
        # CLI 契约: approvals 在 execute_approved 后标记已执行
        store.mark_executed(out["pending_id"],
                            result_summary=str(dispatched.result)[:500],
                            executed=True)
        row = store.get(out["pending_id"])
        assert row["status"] == "executed"

    def test_forged_approval_id_blocked(self, db):
        vc = VersionedConstitution(db)
        vc.current()
        bridge = _make_bridge(db, constitution_sink=lambda p: {"version": 9})
        r = bridge.execute_approved(
            "constitution_update",
            {"principles": DEFAULT_PRINCIPLES, "reason": "伪造",
             "approval_id": "PEND-fake"})
        assert r.status == "failed"
        assert "invalid or unapproved" in r.result["error"]
        assert vc.current().version == 1  # 未生效


# ── 装配层注入 ────────────────────────────────────────────────────────


class TestFactoryWiring:
    def test_build_execution_bridge_has_sink(self, db):
        from ocos.daemon.factory import build_execution_bridge
        vc = VersionedConstitution(db)
        vc.current()
        bridge = build_execution_bridge(db_path=db)
        r = bridge.dispatcher.dispatch_by_name(
            "constitution_update",
            {"principles": DEFAULT_PRINCIPLES, "reason": "装配链验证"})
        assert r.result["ok"] is True
        assert r.result["version"] == 2
        assert vc.current().version == 2

    def test_approvals_bridge_has_sink(self, db, monkeypatch):
        """CLI 审批入口 (_store_and_bridge 等价构造) 落库通道可用。"""
        import importlib
        approvals = importlib.import_module(
            "ocos.interaction.cli.commands.approvals")
        # 检查源码级接线（避免依赖 resolve_db_path 的全局状态）
        import inspect
        src = inspect.getsource(approvals._store_and_bridge)
        assert "constitution_sink=_constitution_sink" in src
        assert "_constitution_sink" in src


# ── prompt 注入 ──────────────────────────────────────────────────────


class TestPromptInjection:
    def test_render_principles(self, db):
        text = VersionedConstitution(db).render_principles()
        assert "价值观宪法 v1" in text
        assert "诚实优先" in text
        assert "主权归人类主人" in text
        assert "修改须经主人批准" in text

    def test_build_context_contains_constitution(self, db, monkeypatch):
        """对话上下文注入宪法块（build_context）。"""
        monkeypatch.setenv("OCOS_AUDIT_DIR", str(db + ".audit"))
        from ocos.interaction.converse import ChatResponder
        mgr = ChatResponder(db_path=db)
        ctx = mgr.build_context("", session_id="t")
        assert "价值观宪法 v1" in ctx
        assert "诚实优先" in ctx
