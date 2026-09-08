"""升级方案 v1.0 §3.1 — 生命体征日报告测试（vitals_report）。"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

from ocos.daemon.vitals_report import (
    check_day_rollover,
    generate_daily_vitals,
)


def _seed_db(tmp_path) -> str:
    """最小生产 DB：episodes（真实 DDL，V5/V7 记录）+ user_messages。"""
    p = str(tmp_path / "daily.db")
    from ocos.memory.episode.store import EpisodeStore
    EpisodeStore(p).initialize()   # 真实 schema（测试自建简化表会缺列）
    conn = sqlite3.connect(p)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS user_messages ("
        "id TEXT PRIMARY KEY, sender TEXT, content TEXT, status TEXT, "
        "created_at TEXT)")
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "INSERT INTO episodes (id, experience_id, created_at, session_id, "
        "goal, decision, action, outcome, source, tags) VALUES "
        "('E1','X1',?,'continuity','V5','OK','continuity_drift_alert',"
        "'{\"success\": true, \"drift\": false}','continuity_check','[\"v5\"]')",
        (now,))
    conn.execute(
        "INSERT INTO episodes (id, experience_id, created_at, session_id, "
        "goal, decision, action, outcome, source, tags) VALUES "
        "('E2','X2',?,'self_check','V7','OK','l2_self_check',"
        "'{\"success\": true}','self_check','[\"l2_self_check\"]')", (now,))
    for i in range(7):
        ts = (datetime.now(timezone.utc) - timedelta(days=i)).isoformat()
        conn.execute("INSERT INTO user_messages VALUES (?,?,?,?,?)",
                     (f"U{i}", "ocos", "推送", "outbound", ts))
    conn.commit()
    conn.close()
    return p


class TestGenerateDailyVitals:
    @pytest.fixture(autouse=True)
    def _pin_level(self, tmp_path, monkeypatch):
        """隔离宿主机环境：心跳文件（autonomy_level=2 会激活
        autonomy_goal_ratio 门 — 种子库 0 自主目标必炸）与
        自主级别覆盖文件都钉到受控 tmp。"""
        override = tmp_path / "level"
        override.write_text("1")
        monkeypatch.setenv("OCOS_AUTONOMY_OVERRIDE", str(override))
        monkeypatch.setenv("OCOS_HEARTBEAT_PATH", str(tmp_path / "hb.json"))
        monkeypatch.setenv("OCOS_AUDIT_DIR", str(tmp_path / "audit"))

    def test_report_passes_and_archives(self, tmp_path):
        db = _seed_db(tmp_path)
        adir = tmp_path / "reports"
        report = generate_daily_vitals(db, "2026-09-06", archive_dir=adir)
        assert report.passed is True
        assert report.violations == []
        assert (adir / "vitals_2026-09-06.md").exists()
        text = (adir / "vitals_2026-09-06.md").read_text(encoding="utf-8")
        assert "# 生命体征日报（2026-09-06）" in text
        assert "[Gate L4] ✓ 阈值全部达标" in text

    def test_violations_listed_in_markdown(self, tmp_path):
        db = _seed_db(tmp_path)
        conn = sqlite3.connect(db)
        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "INSERT INTO episodes (id, experience_id, created_at, session_id, "
            "goal, decision, action, outcome, source, tags) VALUES "
            "('EB','XB',?,'audit','x','y','z','{}','audit',"
            "'[\"redline_violation\"]')", (now,))
        conn.commit()
        conn.close()
        report = generate_daily_vitals(db, "2026-09-06",
                                       archive_dir=tmp_path / "r")
        assert report.passed is False
        assert any("redline" in v for v in report.violations)
        md = (tmp_path / "r" / "vitals_2026-09-06.md").read_text("utf-8")
        assert "未达标项" in md

    def test_episode_recorded(self, tmp_path):
        db = _seed_db(tmp_path)
        generate_daily_vitals(db, "2026-09-06", archive_dir=tmp_path / "r")
        conn = sqlite3.connect(db)
        row = conn.execute(
            "SELECT source, tags FROM episodes WHERE source='vitals_report'"
        ).fetchone()
        conn.close()
        assert row is not None
        assert "vitals_report" in row[1]

    def test_summary_direct_result(self, tmp_path):
        db = _seed_db(tmp_path)
        ok = generate_daily_vitals(db, "2026-09-06", archive_dir=tmp_path / "r")
        assert "✓ 全部达标" in ok.summary()


class TestDayRollover:
    def test_first_call_generates_yesterday(self, tmp_path):
        db = _seed_db(tmp_path)
        yesterday = (datetime.now(timezone.utc) - timedelta(days=1)
                     ).strftime("%Y-%m-%d")
        report = check_day_rollover(db, archive_dir=tmp_path / "r")
        assert report is not None
        assert report.day_key == yesterday

    def test_same_day_silent(self, tmp_path):
        """已生成到今天 → None（诚实沉默，零开销）。"""
        db = _seed_db(tmp_path)
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        from ocos.memory.episode.models import Episode
        from ocos.memory.episode.store import EpisodeStore
        store = EpisodeStore(db)
        store.initialize()
        store.save(Episode.from_candidate(
            experience_id=f"vitals-report-{today}",
            context={"day_key": today, "kind": "vitals_report"},
            goal="生命体征日报告", decision="md", action="vitals_report.generate",
            outcome={"success": True}, condition="t", significance_score=0.5,
            evaluation_trace={}, source="vitals_report",
            tags=["vitals_report", today]))
        assert check_day_rollover(db, archive_dir=tmp_path / "r") is None

    def test_progress_catch_up_no_repeat(self, tmp_path):
        """中断多日 → 直接补昨日（不回溯历史、不生成当日半程）。"""
        db = _seed_db(tmp_path)
        today = datetime.now(timezone.utc)
        old = (today - timedelta(days=3)).strftime("%Y-%m-%d")
        from ocos.memory.episode.models import Episode
        from ocos.memory.episode.store import EpisodeStore
        store = EpisodeStore(db)
        store.initialize()
        store.save(Episode.from_candidate(
            experience_id=f"vitals-report-{old}",
            context={"day_key": old, "kind": "vitals_report"},
            goal="生命体征日报告", decision="md", action="vitals_report.generate",
            outcome={"success": True}, condition="t", significance_score=0.5,
            evaluation_trace={}, source="vitals_report",
            tags=["vitals_report", old]))
        r1 = check_day_rollover(db, archive_dir=tmp_path / "r")
        assert r1 is not None
        assert r1.day_key == (today - timedelta(days=1)).strftime("%Y-%m-%d")
        r2 = check_day_rollover(db, archive_dir=tmp_path / "r")
        assert r2 is None   # 已跟上昨日

    def test_empty_db_path_silent(self, tmp_path):
        assert check_day_rollover("", archive_dir=tmp_path / "r") is None
