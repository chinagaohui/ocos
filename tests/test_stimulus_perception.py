"""感知层上电回归（2026-09-07 V3 感知-反应）。

刺激驱动行为首例: StimulusScanner（真实环境信号）→ EventBus 留痕
→ MotivationHub.propose_stimulus（低风险 PROBE，与动机候选同通道）。
此前全部行为皆目标驱动/用户驱动，此为第一条刺激驱动通路。
"""

from __future__ import annotations

import json
import sqlite3

import pytest

from ocos.perception.stimulus_scanner import StimulusScanner
from ocos.perception_bus import EventBus


def _db(tmp_path):
    conn = sqlite3.connect(str(tmp_path / "per.db"))
    conn.execute(
        "CREATE TABLE episodes (id TEXT PRIMARY KEY, experience_id TEXT, "
        "created_at TEXT, session_id TEXT, context TEXT, goal TEXT, "
        "decision TEXT, action TEXT, outcome TEXT, condition TEXT, "
        "significance_score REAL, evaluation_trace TEXT, source TEXT, "
        "status TEXT, tags TEXT)")
    conn.execute(
        "CREATE TABLE goals (id TEXT PRIMARY KEY, title TEXT, "
        "description TEXT, domain TEXT, level TEXT, status TEXT, "
        "priority INTEGER, progress REAL, origin_level TEXT, source TEXT, "
        "created_at TEXT, updated_at TEXT, metadata TEXT)")
    return conn


def _scanner(tmp_path) -> StimulusScanner:
    return StimulusScanner(db_path=str(tmp_path / "per.db"),
                           audit_dir=str(tmp_path / "audit"))


class TestStimulusScanner:
    @staticmethod
    def _usage(total_gb: float, used_gb: float):
        from collections import namedtuple
        U = namedtuple("usage", "total used free")
        g = 1024 ** 3
        return U(total=int(total_gb * g), used=int(used_gb * g),
                 free=int((total_gb - used_gb) * g))

    def test_disk_threshold_fires_and_cooldowns(self, tmp_path, monkeypatch):
        import ocos.perception.stimulus_scanner as mod

        monkeypatch.setattr(mod.shutil, "disk_usage",
                            lambda p: self._usage(100, 90))
        s = _scanner(tmp_path)
        fired = s.scan()
        assert [x["key"] for x in fired] == ["disk_high"]
        assert "越" in fired[0]["description"]
        # 冷却: 立即重扫不重发
        assert s.scan() == []

    def test_disk_critical_severity(self, tmp_path, monkeypatch):
        import ocos.perception.stimulus_scanner as mod

        monkeypatch.setattr(mod.shutil, "disk_usage",
                            lambda p: self._usage(100, 95))
        s = _scanner(tmp_path)
        fired = s.scan()
        assert fired[0]["key"] == "disk_critical"
        assert fired[0]["severity"] == "critical"

    def test_memory_high(self, tmp_path, monkeypatch):
        s = _scanner(tmp_path)
        monkeypatch.setattr(s, "_read_rss_mb", lambda: 640.0)
        fired = s.scan()
        assert fired[0]["key"] == "memory_high"
        monkeypatch.setattr(s, "_read_rss_mb", lambda: 100.0)
        assert s.scan() == []

    def test_failure_cluster_needs_three(self, tmp_path):
        conn = _db(tmp_path)
        now = "2026-09-07T10:00:00+00:00"
        for i in range(2):                          # 2 次不触发
            conn.execute(
                "INSERT INTO episodes (id, source, created_at, outcome) "
                "VALUES (?, 'goal_result', ?, ?)",
                (f"F{i}", now, json.dumps({"success": False,
                                           "error": "boom"})))
        conn.commit()
        s = _scanner(tmp_path)
        assert s.scan() == []
        conn.execute(
            "INSERT INTO episodes (id, source, created_at, outcome) "
            "VALUES ('F2', 'goal_result', ?, ?)",
            (now, json.dumps({"success": False, "error": "boom"})))
        conn.commit()
        conn.close()
        fired = s.scan()
        assert fired[0]["key"] == "failure_cluster"
        assert fired[0]["evidence"]["fail_count"] == 3

    def test_goal_stuck(self, tmp_path):
        from datetime import datetime, timedelta, timezone
        stale = (datetime.now(timezone.utc)
                 - timedelta(hours=8)).isoformat()   # 动态相对时间
        conn = _db(tmp_path)
        conn.execute(
            "INSERT INTO goals VALUES ('G1', 't', 'd', 'analysis', 'TASK', "
            "'IN_PROGRESS', 1, 0.0, 'SELF', 'autonomous', ?, ?, '{}')",
            (stale, stale))
        conn.commit()
        conn.close()
        fired = _scanner(tmp_path).scan()
        assert fired[0]["key"] == "goal_stuck"

    def test_audit_log_written(self, tmp_path):
        conn = _db(tmp_path)
        for i, ts in enumerate(("10:00:00", "10:01:00", "10:02:00")):
            conn.execute(
                "INSERT INTO episodes (id, source, created_at, outcome) "
                f"VALUES ('{chr(65+i)}', 'goal_result', "
                f"'2026-09-07T{ts}+00:00', ?)",
                (json.dumps({"success": False, "error": "x"}),))
        conn.commit()
        conn.close()
        _scanner(tmp_path).scan()
        log = tmp_path / "audit" / "perception.jsonl"
        assert log.exists()
        rec = json.loads(log.read_text(encoding="utf-8").splitlines()[0])
        assert rec["key"] == "failure_cluster"


class TestBusAndMotivation:
    def test_bus_push_stimulus_ingestable(self):
        bus = EventBus()
        bus.push_stimulus({"key": "disk_high", "severity": "high",
                           "description": "d", "evidence": {}})
        events = bus.ingest()
        assert len(events) == 1
        assert events[0].source.name == "SYSTEM"
        assert events[0].metadata.get("stimulus", {}).get("key") \
            == "disk_high"

    def test_propose_stimulus_level2_writes_goal(self, tmp_path):
        from ocos.daemon.motivation import MotivationHub
        from ocos.goal.store import GoalStore

        db = str(tmp_path / "per.db")
        GoalStore(db_path=db)                  # 建真实 schema
        hub = MotivationHub(db_path=db, goal_store=GoalStore(db_path=db))
        stats = hub.propose_stimulus(
            [{"key": "disk_high", "severity": "high",
              "description": "根分区 90%", "evidence": {"used_pct": 90}}],
            level=2)
        assert stats["proposed"] == 1 and stats["auto_enqueued"] == 1
        # 直查 goals 表验证落地 + perception 标记
        c = sqlite3.connect(db)
        row = c.execute(
            "SELECT description, metadata FROM goals").fetchone()
        c.close()
        assert "响应环境刺激[disk_high]" in row[0]
        assert "perception stimulus" in row[1]     # vitals 统计依据

    def test_propose_stimulus_level1_pends(self, tmp_path):
        from ocos.daemon.motivation import MotivationHub
        from ocos.execution.pending import PendingStore

        db = str(tmp_path / "per.db")
        hub = MotivationHub(db_path=db,
                            pending_store=PendingStore(db_path=db))
        stats = hub.propose_stimulus(
            [{"key": "memory_high", "severity": "high", "description": "m",
              "evidence": {}}], level=1)
        assert stats["pending_enqueued"] == 1
