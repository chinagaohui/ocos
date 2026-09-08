"""CHAT-ROUTE FIX (2026-09-07): converse 结果回推 feed + 网关个人模式豁免。

- /ocos/converse/feed: goal_result episode 增量流（since 过滤、升序、上限 5）
- ChatResponder._gateway_check: 个人模式（OCOS_SANDBOX_DISABLED=true）下
  SSRF 文本信号放行，与 bridge 侧豁免语义一致；其它 violation 仍拦
"""
from __future__ import annotations

import asyncio
import json
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

import pytest


# ── feed 端点 ────────────────────────────────────────────────────────

@pytest.fixture()
def _feed_env(tmp_path, monkeypatch):
    """临时 db + 3 条 goal_result episode（2 新 1 旧）。"""
    db = str(tmp_path / "feed.db")
    conn = sqlite3.connect(db)
    conn.execute(
        "CREATE TABLE episodes (id TEXT PRIMARY KEY, created_at TEXT, "
        "decision TEXT, outcome TEXT, action TEXT)")
    now = datetime.now(timezone.utc)
    rows = [
        ("EPI-old", now - timedelta(hours=2),
         "✗ 旧结果", '{"success": false}', "goal_result"),
        ("EPI-new-1", now - timedelta(minutes=1),
         "✓ 任务A → stdout ok", '{"success": true}', "goal_result"),
        ("EPI-new-2", now - timedelta(seconds=10),
         "✗ 任务B → 写操作被拒", '{"success": false}', "goal_result"),
        ("EPI-conv", now - timedelta(seconds=5),
         "不应出现在 feed", '{"success": true}', "conversation_reply"),
    ]
    for rid, ts, dec, out, act in rows:
        conn.execute(
            "INSERT INTO episodes VALUES (?,?,?,?,?)",
            (rid, ts.isoformat(), dec, out, act))
    conn.commit()
    conn.close()
    monkeypatch.setenv("OCOS_DB_PATH", db)
    return db


def _call_feed(since: str = ""):
    from ocos.interaction.api.routes.converse import converse_feed
    return asyncio.run(converse_feed(since=since))


class TestConverseFeed:
    def test_feed_returns_newest_goal_results_ascending(
            self, _feed_env, monkeypatch):
        monkeypatch.setenv("OCOS_SANDBOX_DISABLED", "false")
        resp = _call_feed(since=(datetime.now(timezone.utc)
                                 - timedelta(hours=1)).isoformat())
        items = resp.data["items"]
        assert [i["id"] for i in items] == ["EPI-new-1", "EPI-new-2"]
        assert items[0]["success"] is True
        assert items[1]["success"] is False
        assert "不应出现" not in "".join(
            i["decision"] for i in items)   # 非 goal_result 不进 feed

    def test_feed_since_filters_incrementally(self, _feed_env, monkeypatch):
        monkeypatch.setenv("OCOS_SANDBOX_DISABLED", "false")
        mid = (datetime.now(timezone.utc)
               - timedelta(seconds=30)).isoformat()
        resp = _call_feed(since=mid)
        assert [i["id"] for i in resp.data["items"]] == ["EPI-new-2"]

    def test_feed_empty_when_no_new(self, _feed_env, monkeypatch):
        monkeypatch.setenv("OCOS_SANDBOX_DISABLED", "false")
        resp = _call_feed(since=datetime.now(timezone.utc).isoformat())
        assert resp.data["items"] == []
        assert resp.data["server_time"]

    def test_feed_bad_since_rejected(self, _feed_env, monkeypatch):
        from fastapi import HTTPException
        monkeypatch.setenv("OCOS_SANDBOX_DISABLED", "false")
        with pytest.raises(HTTPException) as ei:
            _call_feed(since="not-a-time")
        assert ei.value.status_code == 400


# ── feed activity 快照（2026-09-08 执行可见性） ──────────────────────

@pytest.fixture()
def _activity_env(_feed_env, tmp_path, monkeypatch):
    """goals 表（1 ACTIVE + 1 PENDING）+ 活跃 daemon 心跳文件。"""
    db = _feed_env
    conn = sqlite3.connect(db)
    conn.execute(
        "CREATE TABLE goals (id TEXT PRIMARY KEY, description TEXT, "
        "status TEXT, origin_level TEXT, updated_at TEXT)")
    now = datetime.now(timezone.utc)
    conn.execute("INSERT INTO goals VALUES (?,?,?,?,?)",
                 ("G-ACT", "执行中的目标", "ACTIVE", "HUMAN",
                  (now - timedelta(seconds=5)).isoformat()))
    conn.execute("INSERT INTO goals VALUES (?,?,?,?,?)",
                 ("G-P1", "排队目标", "PENDING", "HUMAN",
                  (now - timedelta(minutes=9)).isoformat()))
    conn.commit()
    conn.close()
    hb = tmp_path / "hb.json"
    hb.write_text(json.dumps(
        {"ts": now.isoformat(), "cycle": 42, "pid": 123}), encoding="utf-8")
    monkeypatch.setenv("OCOS_HEARTBEAT_PATH", str(hb))
    return db


class TestFeedActivity:
    def test_active_goal_surfaced_with_elapsed(self, _activity_env,
                                               monkeypatch):
        monkeypatch.setenv("OCOS_SANDBOX_DISABLED", "false")
        resp = _call_feed(since=datetime.now(timezone.utc).isoformat())
        act = resp.data["activity"]
        assert act["active_goal"]["id"] == "G-ACT"
        assert act["active_goal"]["origin"] == "HUMAN"
        assert act["active_goal"]["elapsed_s"] >= 4.0
        assert act["pending_goals"] == 1
        assert act["daemon"]["alive"] is True
        assert act["daemon"]["cycle"] == 42

    def test_idle_alive_without_goals_table(self, _feed_env, monkeypatch,
                                            tmp_path):
        """goals 表缺失 → 快照诚实降级（None/0），心跳照报。"""
        monkeypatch.setenv("OCOS_SANDBOX_DISABLED", "false")
        hb = tmp_path / "hb.json"
        hb.write_text(json.dumps(
            {"ts": datetime.now(timezone.utc).isoformat(), "cycle": 7}),
            encoding="utf-8")
        monkeypatch.setenv("OCOS_HEARTBEAT_PATH", str(hb))
        resp = _call_feed(since=datetime.now(timezone.utc).isoformat())
        act = resp.data["activity"]
        assert act["active_goal"] is None
        assert act["pending_goals"] == 0
        assert act["daemon"]["alive"] is True

    def test_daemon_dead_reported(self, _feed_env, monkeypatch, tmp_path):
        """心跳超时 → alive=False + age（区分"空闲"与"断了"的关键）。"""
        monkeypatch.setenv("OCOS_SANDBOX_DISABLED", "false")
        hb = tmp_path / "hb.json"
        hb.write_text(json.dumps(
            {"ts": (datetime.now(timezone.utc)
                    - timedelta(minutes=10)).isoformat(), "cycle": 1}),
            encoding="utf-8")
        monkeypatch.setenv("OCOS_HEARTBEAT_PATH", str(hb))
        resp = _call_feed(since=datetime.now(timezone.utc).isoformat())
        act = resp.data["activity"]
        assert act["daemon"]["alive"] is False
        assert act["daemon"]["age_s"] >= 590

    def test_missing_heartbeat_honest(self, _feed_env, monkeypatch):
        monkeypatch.setenv("OCOS_SANDBOX_DISABLED", "false")
        monkeypatch.setenv("OCOS_HEARTBEAT_PATH", "/nonexistent/hb.json")
        resp = _call_feed(since=datetime.now(timezone.utc).isoformat())
        assert resp.data["activity"]["daemon"]["alive"] is False
        assert resp.data["activity"]["daemon"]["age_s"] is None


# ── 对话层网关个人模式豁免 ────────────────────────────────────────────

class TestConverseGatewayPersonalMode:
    """USE| 动作网关：个人模式下 SSRF 文本信号放行（与 bridge 一致）。"""

    def _responder(self):
        from ocos.interaction.converse import ChatResponder
        return ChatResponder(db_path=":memory:")

    def test_ssrf_allowed_under_personal_mode(self, monkeypatch):
        monkeypatch.setenv("OCOS_SANDBOX_DISABLED", "true")

        class _V:
            allowed = False
            violations = ["SSRF: internal URL pattern detected"]
            reason = ""

        class _GW:
            def validate(self, contract, **k):
                return _V()

        r = self._responder()
        r._permission_gateway = _GW()
        assert r._gateway_check(
            "shell", {"command": "curl http://127.0.0.1:8900/health"}
        ) is None

    def test_non_ssrf_still_blocked_under_personal_mode(self, monkeypatch):
        monkeypatch.setenv("OCOS_SANDBOX_DISABLED", "true")

        class _V:
            allowed = False
            violations = ["CMD_INJECTION: shell metacharacters detected"]
            reason = ""

        class _GW:
            def validate(self, contract, **k):
                return _V()

        r = self._responder()
        r._permission_gateway = _GW()
        reason = r._gateway_check(
            "shell", {"command": "echo a; rm -rf /tmp/x"})
        assert reason is not None
        assert "CMD_INJECTION" in reason

    def test_ssrf_still_blocked_without_personal_mode(self, monkeypatch):
        monkeypatch.setenv("OCOS_SANDBOX_DISABLED", "false")

        class _V:
            allowed = False
            violations = ["SSRF: internal URL pattern detected"]
            reason = ""

        class _GW:
            def validate(self, contract, **k):
                return _V()

        r = self._responder()
        r._permission_gateway = _GW()
        reason = r._gateway_check(
            "shell", {"command": "curl http://127.0.0.1:8900/health"})
        assert reason is not None
        assert "SSRF" in reason
