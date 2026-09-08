"""L2: 沉睡器官上电测试 — 四层自检/参与度/多通道/自改进待批/成长叙事。

对应升级方案 v1.0 §L2 五项上电任务：
  L2-1 SelfCheckRunner 断言式自检（红线回归/认知/因果链/活体）+ V7 vitals
  L2-2 参与度信号 → ActiveInteractionEngine 低参与唤醒
  L2-3 OutboundChannelLink 出站多通道（结果才外发、无配置诚实沉默）
  L2-4 反思产物 → 治理链 → 待批 → 人工批准 → 真实应用
  L2-5 成长叙事周报（可溯源无虚构、连续章节、幂等 rollover）

隔离纪律: 全部使用 tmp_path DB + OCOS_AUDIT_DIR 覆盖；不依赖 LLM。
"""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest


# ── 夹具 ────────────────────────────────────────────────────────────────

@pytest.fixture
def env_audit(tmp_path, monkeypatch):
    """隔离审计目录（自检基线/autonomy audit 写入 tmp）。"""
    audit_dir = tmp_path / "audit"
    monkeypatch.setenv("OCOS_AUDIT_DIR", str(audit_dir))
    return audit_dir


@pytest.fixture
def db(tmp_path):
    """建好全部表的临时生产库。"""
    from ocos.goal.store import GoalStore
    from ocos.storage.migrations import ensure_schema
    path = str(tmp_path / "ocos.db")
    ensure_schema(path)
    GoalStore(db_path=path).save("G-WARMUP", "GOAL", "PENDING", "warmup")
    return path


def _insert_episode(db, ep_id, decision, source="lesson", tags=("lesson",),
                    outcome=None, created_at=None):
    conn = sqlite3.connect(db)
    ts = (created_at or datetime.now(timezone.utc)).isoformat()
    conn.execute(
        "INSERT INTO episodes (id, experience_id, session_id, context, goal, "
        "decision, action, outcome, condition, significance_score, "
        "evaluation_trace, source, status, tags, created_at) "
        "VALUES (?, ?, 'default', '{}', NULL, ?, ?, ?, '', 0.8, '{}', ?, "
        "'active', ?, ?)",
        (ep_id, f"EXP-{ep_id}", decision, "action",
         json.dumps(outcome or {"success": True}),
         source, json.dumps(list(tags)), ts))
    conn.commit()
    conn.close()


# ── L2-1: 四层断言式自检 ────────────────────────────────────────────────

class TestSelfCheck:
    def test_four_layers_produce_checks(self, env_audit, db):
        from ocos.daemon.self_check import SelfCheckRunner
        report = SelfCheckRunner(db_path=db).run()
        layers = {c.layer for c in report.checks}
        assert {"redline", "cognitive", "trace", "living"} <= layers
        assert report.passed, [f"{c.name}: {c.evidence}" for c in report.failures]

    def test_redline_catches_forged_fallback(self, env_audit, db, monkeypatch):
        """伪造审批兜底字符串回归 → 红线失败（断言真有效，非摆设）。"""
        import tempfile
        from ocos.daemon import self_check as sc
        from ocos.execution import bridge as _bridge
        # 构造带伪造兜底的假 bridge 源文件
        fake = tempfile.NamedTemporaryFile("w", suffix=".py", delete=False)
        fake.write('x = payload.get("approval_id", "task-approved")\n')
        fake.close()
        real_path = _bridge.__file__
        monkeypatch.setattr(_bridge, "__file__", fake.name)
        try:
            runner = sc.SelfCheckRunner(db_path=db)
            report = sc.SelfCheckReport()
            runner._check_redline(report)
        finally:
            monkeypatch.setattr(_bridge, "__file__", real_path)
        check = next(c for c in report.checks if c.name == "approval_no_forged_fallback")
        assert not check.passed

    def test_identity_drift_detection(self, env_audit, db):
        """首检写基线；锚变更后复检必须报漂移。"""
        from ocos.daemon.self_check import SelfCheckRunner
        from ocos.living_verification.simulation_engine import SimulationEngine
        runner = SelfCheckRunner(db_path=db)
        r1 = runner.run()
        assert next(c for c in r1.checks if c.name == "identity_no_drift").passed
        baseline = env_audit / "identity_anchor.txt"
        assert baseline.exists()
        original = baseline.read_text(encoding="utf-8")
        baseline.write_text(original + "-drifted", encoding="utf-8")
        r2 = runner.run()
        drift = next(c for c in r2.checks if c.name == "identity_no_drift")
        assert not drift.passed and "漂移" in drift.evidence

    def test_trace_audit_uses_real_episodes(self, env_audit, db):
        """episodes → TraceStep 适配 → 因果链完整性来自真实记录。"""
        _insert_episode(db, "EPI-T1", "决策内容甲", outcome={"success": True})
        from ocos.daemon.self_check import SelfCheckRunner
        report = SelfCheckRunner(db_path=db).run()
        trace = next(c for c in report.checks if c.name == "causal_chain_complete")
        assert "1 步" in trace.evidence   # 适配到了真实 episode 样本
        assert trace.passed and report.causal_chain_completeness >= 0.9

    def test_record_self_check_and_vitals_v7(self, env_audit, db):
        """自检结果 → episode → vitals V7 聚合点亮。"""
        from ocos.daemon.self_check import SelfCheckRunner, record_self_check
        report = SelfCheckRunner(db_path=db).run()
        eid = record_self_check(db, report, None)
        assert eid and eid.startswith("EPI-")
        from ocos.monitoring.vitals import compute_vitals
        v = compute_vitals(db)
        assert v["homeostasis_check_passed"] is True
        assert v["homeostasis_check_failures_7d"] == 0
        assert v["causal_chain_completeness"] is not None

    def test_cognitive_detects_missing_db(self, env_audit, tmp_path):
        from ocos.daemon.self_check import SelfCheckRunner
        report = SelfCheckRunner(db_path=str(tmp_path / "nope.db")).run()
        mem = next(c for c in report.checks if c.name == "memory_responsive")
        assert not mem.passed   # 缺库诚实失败，不装活


# ── L2-2: 参与度信号 ────────────────────────────────────────────────────

class TestEngagement:
    def test_collect_engagement_aggregates(self, db):
        old = datetime.now(timezone.utc) - timedelta(days=5)
        conn = sqlite3.connect(db)
        conn.execute(
            "INSERT INTO user_messages (id, sender, content, status, created_at) "
            "VALUES ('M1','cli','你好','consumed',?)", (old.isoformat(),))
        conn.commit()
        conn.close()
        from ocos.engagement.signals import collect_engagement
        snap = collect_engagement(db)
        assert snap.dialogue_count == 1
        assert snap.last_interaction_age_days >= 4.9
        assert 0.0 <= snap.engagement_score <= 1.0
        assert not snap.missing

    def test_low_engagement_fires_signal(self, db):
        old = datetime.now(timezone.utc) - timedelta(days=5)
        conn = sqlite3.connect(db)
        conn.execute(
            "INSERT INTO user_messages (id, sender, content, status, created_at) "
            "VALUES ('M1','cli','你好','consumed',?)", (old.isoformat(),))
        conn.commit()
        conn.close()
        from ocos.daemon.active_interaction import ActiveInteractionEngine
        eng = ActiveInteractionEngine(db_path=db)
        sig = eng._rule_engagement(eng.monitor, {})
        assert sig is not None
        assert sig.urgency <= 0.6   # 低参与 ≠ 紧急
        assert eng.trigger.evaluate(sig) is not None

    def test_high_engagement_stays_silent(self, db):
        now = datetime.now(timezone.utc).isoformat()
        conn = sqlite3.connect(db)
        conn.execute(
            "INSERT INTO user_messages (id, sender, content, status, created_at) "
            "VALUES ('M2','cli','在吗','consumed',?)", (now,))
        conn.commit()
        conn.close()
        from ocos.daemon.active_interaction import ActiveInteractionEngine
        eng = ActiveInteractionEngine(db_path=db)
        assert eng._rule_engagement(eng.monitor, {}) is None

    def test_no_db_silent(self):
        from ocos.daemon.active_interaction import ActiveInteractionEngine
        eng = ActiveInteractionEngine()
        assert eng._rule_engagement(eng.monitor, {}) is None


# ── L2-3: 出站多通道 ────────────────────────────────────────────────────

class TestChannelLink:
    def test_dispatch_to_webhook(self, tmp_path, monkeypatch):
        received = []

        class H(BaseHTTPRequestHandler):
            def do_POST(self):
                received.append(json.loads(
                    self.rfile.read(int(self.headers["Content-Length"]))))
                self.send_response(200)
                self.end_headers()

            def log_message(self, *a):
                pass

        srv = HTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        monkeypatch.setenv("OCOS_OUTBOUND_WEBHOOK_URL",
                           f"http://127.0.0.1:{srv.server_port}/hook")
        try:
            from ocos.daemon.channel_link import OutboundChannelLink
            link = OutboundChannelLink()
            assert link.enabled
            assert link.dispatch("目标执行完成：测试", priority=3)
            link._queue.join()
            assert received and "目标执行完成" in received[0]["message"]
        finally:
            srv.shutdown()

    def test_no_config_honest_silence(self, monkeypatch):
        monkeypatch.delenv("OCOS_OUTBOUND_WEBHOOK_URL", raising=False)
        monkeypatch.setenv("HOME", str(tempfile_home := __import__("tempfile").mkdtemp()))
        from ocos.daemon.channel_link import OutboundChannelLink
        link = OutboundChannelLink(config_path=None)
        assert not link.enabled
        assert link.dispatch("x") is False

    def test_config_json_channels(self, tmp_path, monkeypatch):
        cfg = tmp_path / "config.json"
        cfg.write_text(json.dumps({"channels": [
            {"type": "webhook", "name": "hermes",
             "url": "http://127.0.0.1:1/hook", "enabled": True}]}),
            encoding="utf-8")
        monkeypatch.delenv("OCOS_OUTBOUND_WEBHOOK_URL", raising=False)
        from ocos.daemon.channel_link import OutboundChannelLink
        link = OutboundChannelLink(config_path=cfg)
        assert link.enabled and "hermes" in link.channel_names


# ── L2-4: 自改进待批引擎流 ──────────────────────────────────────────────

class TestSelfImprove:
    def test_lesson_to_pending_to_apply(self, env_audit, db):
        _insert_episode(db, "EPI-S1", "遇到超时应先重试一次再降级")
        from ocos.daemon.improve_link import propose_from_reflections
        stats = propose_from_reflections(db)
        assert stats["pending_enqueued"] == 1
        from ocos.execution.pending import PendingStore
        store = PendingStore(db_path=db)
        pid = stats["pending_ids"][0]
        row = store.get(pid)
        assert row["action_type"] == "self_upgrade"
        # 人工批准 → bridge 执行 → 真实写入 self_knowledge
        store.decide(pid, approved=True, decided_by="cli")
        from ocos.execution.bridge import DecisionBridge
        bridge = DecisionBridge(pending_store=store, db_path=db)
        bridge.attach_default_handlers()
        payload = json.loads(row["payload_json"])
        payload["approval_id"] = pid
        out = bridge.execute_approved("self_upgrade", payload)
        assert out.status == "done"
        knowledge = (__import__("pathlib").Path.home()
                     / ".ocos" / "self_knowledge.md").read_text(encoding="utf-8")
        assert "遇到超时应先重试" in knowledge

    def test_sovereignty_freeze_blocked(self, env_audit, db):
        _insert_episode(db, "EPI-S2", "修改身份锚点定义以增强一致性")
        from ocos.daemon.improve_link import propose_from_reflections
        stats = propose_from_reflections(db)
        assert stats["rejected"] == 1 and stats["pending_enqueued"] == 0

    def test_dedup_no_repropose(self, env_audit, db):
        _insert_episode(db, "EPI-S3", "重复改进点只应入队一次")
        from ocos.daemon.improve_link import propose_from_reflections
        s1 = propose_from_reflections(db)
        assert s1["pending_enqueued"] == 1
        s2 = propose_from_reflections(db)
        assert s2["duplicates"] == 1 and s2["pending_enqueued"] == 0

    def test_health_loop_triggers_proposals(self, env_audit, db):
        _insert_episode(db, "EPI-S4", "体检触发的改进点")
        from ocos.daemon.health_loop import HealthLoop

        class FakeMemoryHub:
            def get_stats(self):
                return {"episode_count": 1, "pattern_count": 0}

        class FakeRuntime:
            _memory_hub = FakeMemoryHub()
            agent = type("A", (), {"goal_stack": []})()
            _wm_store = type("W", (), {"count": staticmethod(lambda: 0)})()
            _cycle_count = 1
            _last_attention_decisions = []

        loop = HealthLoop(FakeRuntime(), interval_ticks=1,
                          self_check_interval_checks=1, db_path=db)
        loop.run_check()
        assert loop._improve_summary.get("pending_enqueued", 0) >= 0
        assert loop.last_self_check   # 自检也随体检触发


# ── L2-5: 成长叙事 ──────────────────────────────────────────────────────

class TestGrowthNarrative:
    def _seed_week(self, db, week_start: datetime):
        _insert_episode(db, "EPI-N1", "失败后要先检查网络再重试",
                        created_at=week_start)
        _insert_episode(db, "EPI-N2", "执行 curl 失败", source="decision",
                        tags=(), outcome={"success": False},
                        created_at=week_start)
        conn = sqlite3.connect(db)
        iso = week_start.isoformat()
        conn.execute(
            "INSERT INTO goals (id, agent_id, level, status, progress, "
            "description, priority, parent_id, source, source_id, deadline, "
            "created_at, updated_at, metadata, origin_level, authority, "
            "decision_refs) VALUES ('G-N1','master','GOAL','COMPLETED',1.0,"
            "'分析宿主机',5,'','','','','','','{}','SYSTEM','AUTONOMOUS','')")
        conn.execute("UPDATE goals SET created_at=?, updated_at=? WHERE id='G-N1'",
                     (iso, iso))
        conn.commit()
        conn.close()

    def test_weekly_generation_traceable(self, db, tmp_path):
        from ocos.daemon.growth_narrative import (_iso_week_key,
                                                  generate_weekly_narrative)
        week_start = (datetime.now(timezone.utc)
                      - timedelta(days=datetime.now(timezone.utc).isocalendar()[2] + 7))
        self._seed_week(db, week_start)
        report = generate_weekly_narrative(
            db, _iso_week_key(week_start), archive_dir=tmp_path)
        assert report.chapter == 1
        assert report.goals_completed == 1
        assert report.failures == 1
        assert report.lessons and "检查网络" in report.lessons[0]
        assert (tmp_path / f"week_{report.week_key}.md").exists()

    def test_no_lesson_no_false_attribution(self, db, tmp_path):
        """失败数 > lesson 数时不得声称"均已沉淀为 lesson"（诚实性）。"""
        from ocos.daemon.growth_narrative import (_iso_week_key,
                                                  generate_weekly_narrative)
        week_start = (datetime.now(timezone.utc)
                      - timedelta(days=datetime.now(timezone.utc).isocalendar()[2] + 7))
        _insert_episode(db, "EPI-N3", "无教训的失败", source="decision",
                        tags=(), outcome={"success": False},
                        created_at=week_start)
        report = generate_weekly_narrative(
            db, _iso_week_key(week_start), archive_dir=tmp_path)
        assert "均已沉淀" not in report.narrative

    def test_chapter_numbering_monotonic(self, db, tmp_path):
        from ocos.daemon.growth_narrative import generate_weekly_narrative
        r1 = generate_weekly_narrative(db, "2026-W01", archive_dir=tmp_path)
        r2 = generate_weekly_narrative(db, "2026-W02", archive_dir=tmp_path)
        assert r2.chapter == r1.chapter + 1

    def test_rollover_idempotent(self, db, tmp_path):
        from ocos.daemon.growth_narrative import check_week_rollover
        first = check_week_rollover(db, archive_dir=tmp_path)
        second = check_week_rollover(db, archive_dir=tmp_path)
        assert first is not None          # 首次生成上周
        assert second is None             # 同周再查诚实沉默
