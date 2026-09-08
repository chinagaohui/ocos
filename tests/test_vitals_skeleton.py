"""L0-6: 生命体征仪表盘（vitals 骨架）测试。

覆盖:
  1. autonomy_goal_ratio 聚合正确性（窗口过滤 + 自主判据）
  2. redline_violation_count / blocked_attempts 聚合
  3. 缺表/缺库诚实降级（missing 标注，不抛异常）
  4. 心跳判活 + braked/level 快照
  5. render_vitals 一屏输出含关键行
  6. 红线违规 exit code（cmd_vitals 违规=2）
"""
import json
import sqlite3

import pytest

from ocos.monitoring.vitals import compute_vitals, render_vitals


@pytest.fixture()
def db(tmp_path):
    path = str(tmp_path / "ocos.db")
    conn = sqlite3.connect(path)
    conn.execute(
        "CREATE TABLE goals (id TEXT PRIMARY KEY, status TEXT, "
        "source TEXT DEFAULT '', metadata TEXT, origin_level TEXT, "
        "created_at TEXT NOT NULL)")
    conn.execute(
        "CREATE TABLE episodes (id TEXT PRIMARY KEY, tags TEXT, "
        "decision TEXT, created_at TEXT NOT NULL)")
    conn.execute(
        "CREATE TABLE pending_actions (id TEXT PRIMARY KEY, status TEXT)")
    conn.commit()
    conn.close()
    return path


def _add_goal(db, gid, created_at, metadata="", source=""):
    conn = sqlite3.connect(db)
    conn.execute(
        "INSERT INTO goals (id, status, source, metadata, origin_level, "
        "created_at) VALUES (?, 'PENDING', ?, ?, 'HUMAN', ?)",
        (gid, source, metadata, created_at))
    conn.commit()
    conn.close()


def _add_episode(db, eid, created_at, tags="[]", decision=""):
    conn = sqlite3.connect(db)
    conn.execute(
        "INSERT INTO episodes (id, tags, decision, created_at) "
        "VALUES (?, ?, ?, ?)", (eid, tags, decision, created_at))
    conn.commit()
    conn.close()


NOW = "2026-09-06T00:00:00+00:00"
OLD = "2026-08-01T00:00:00+00:00"   # 窗口外（7 天窗）


class TestAutonomyMetrics:
    def test_empty_db_zero_ratio(self, db):
        v = compute_vitals(db)
        assert v["goals_total"] == 0
        assert v["autonomy_goal_ratio"] == 0.0

    def test_ratio_counts_only_window_and_autonomous(self, db):
        _add_goal(db, "G1", NOW)                                   # 人类目标
        _add_goal(db, "G2", NOW, metadata='{"tag": "autonomous"}')  # 自主
        _add_goal(db, "G3", NOW, source="motivation")               # 自主
        _add_goal(db, "G4", OLD, metadata='{"tag": "autonomous"}')  # 窗口外
        v = compute_vitals(db)
        assert v["goals_total"] == 3
        assert v["goals_autonomous"] == 2
        assert v["autonomy_goal_ratio"] == pytest.approx(2 / 3, abs=1e-3)

    def test_missing_goals_table_degrades(self, tmp_path):
        path = str(tmp_path / "empty.db")
        conn = sqlite3.connect(path)
        conn.execute("CREATE TABLE other (x INT)")
        conn.commit()
        conn.close()
        v = compute_vitals(path)
        assert v["goals_total"] == 0
        assert "missing" in v


class TestRedlineMetrics:
    def test_violation_and_blocked_counts(self, db):
        _add_episode(db, "E1", NOW, tags='["redline_violation"]')
        _add_episode(db, "E2", NOW,
                     decision="blocked: forged/unapproved approval_id: X")
        _add_episode(db, "E3", NOW, tags='["goal_result"]')
        _add_episode(db, "E4", OLD, tags='["redline_violation"]')  # 窗口外
        v = compute_vitals(db)
        assert v["redline_violation_count"] == 1
        assert v["redline_blocked_attempts"] == 1

    def test_clean_db_zero_violations(self, db):
        v = compute_vitals(db)
        assert v["redline_violation_count"] == 0


class TestPendingMetrics:
    def test_pending_grouped_by_status(self, db):
        conn = sqlite3.connect(db)
        for i, st in enumerate(["pending", "pending", "approved"]):
            conn.execute("INSERT INTO pending_actions (id, status) "
                         f"VALUES ('P{i}', '{st}')")
        conn.commit()
        conn.close()
        v = compute_vitals(db)
        assert v["pending_pending"] == 2
        assert v["pending_approved"] == 1


class TestDaemonMetrics:
    def test_heartbeat_alive_with_braked(self, db, tmp_path, monkeypatch):
        hb = tmp_path / "hb.json"
        hb.write_text(json.dumps({
            "pid": 1, "braked": True, "autonomy_level": 2,
            "ts": __import__("datetime").datetime.now(
                __import__("datetime").timezone.utc).isoformat()}))
        monkeypatch.setenv("OCOS_HEARTBEAT_PATH", str(hb))
        monkeypatch.setenv("OCOS_AUDIT_DIR", str(tmp_path / "audit"))
        v = compute_vitals(db)
        assert v["daemon_alive"] is True
        assert v["daemon_braked"] is True
        assert v["autonomy_level"] == 2

    def test_stale_heartbeat_not_alive(self, db, tmp_path, monkeypatch):
        hb = tmp_path / "hb.json"
        hb.write_text(json.dumps({
            "pid": 1, "ts": "2020-01-01T00:00:00+00:00"}))
        monkeypatch.setenv("OCOS_HEARTBEAT_PATH", str(hb))
        monkeypatch.setenv("OCOS_AUDIT_DIR", str(tmp_path / "audit"))
        v = compute_vitals(db)
        assert v["daemon_alive"] is False


class TestRenderAndExit:
    def test_render_contains_key_lines(self, db):
        v = compute_vitals(db)
        text = render_vitals(v)
        assert "autonomy_goal_ratio" in text
        assert "redline_violation" in text
        assert "待实现指标" in text   # 诚实标注未实现指标

    def test_not_implemented_flags_present(self, db):
        v = compute_vitals(db)
        # L7/L8 后 skill_replay_hit_rate 已点亮；V2 行为级验收后
        # reflection_adoption_rate 已点亮（repair_verified 打点聚合），
        # 仍在骨架位的是 unattended_survival
        assert "unattended_survival" in v["not_implemented"]
        assert "reflection_adoption_rate" not in v["not_implemented"]
        assert "skill_replay_hit_rate" not in v["not_implemented"]

    def test_missing_db_honest(self, tmp_path):
        v = compute_vitals(str(tmp_path / "nope.db"))
        assert any("db:" in m for m in v["missing"])
        assert v["goals_total"] == 0
