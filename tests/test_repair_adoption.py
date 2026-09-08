"""V2 行为级验收 + V4 知识边界自省 回归（2026-09-07）。

V2: REPAIR 目标完成 → repair_completed 打点 → verify_repairs 6h 验收
    （复发/先验注入）→ reflection_adoption_rate（vitals 行为级真值）。
V4: 知识边界块（语义知识/低置信信念/失败集中域）+ "我不知道X，因为Y"
    格式强制注入。
"""

from __future__ import annotations

import json
import sqlite3

from ocos.daemon.motivation import MotivationHub


def _hub(tmp_path, monkeypatch) -> MotivationHub:
    monkeypatch.setenv("OCOS_AUDIT_DIR", str(tmp_path / "audit"))  # 隔离!
    db = str(tmp_path / "m.db")
    conn = sqlite3.connect(db)
    conn.execute(
        "CREATE TABLE episodes (id TEXT PRIMARY KEY, experience_id TEXT, "
        "created_at TEXT, session_id TEXT, context TEXT, goal TEXT, "
        "decision TEXT, action TEXT, outcome TEXT, condition TEXT, "
        "significance_score REAL, evaluation_trace TEXT, source TEXT, "
        "status TEXT, tags TEXT)")
    conn.commit()
    conn.close()
    return MotivationHub(db_path=db)


def _lesson(hub, cause: str, iso: str) -> None:
    conn = sqlite3.connect(hub._db_path)
    conn.execute(
        "INSERT INTO episodes (id, source, created_at, tags) VALUES "
        "(?, 'lesson', ?, ?)",
        (f"L{cause}{iso[-8:-6]}{id(cause) % 97}", iso,
         json.dumps(["failure_lesson", cause])))
    conn.commit()
    conn.close()


class TestRepairAdoption:
    def test_pending_before_window(self, tmp_path, monkeypatch):
        hub = _hub(tmp_path, monkeypatch)
        hub.record_repair_completion("ambiguous_task", "复盘目标")
        stats = hub.verify_repairs()
        assert stats["pending"] == 1 and stats["adopted"] == 0

    def test_adopted_behavior_via_prior_injection(self, tmp_path, monkeypatch):
        hub = _hub(tmp_path, monkeypatch)
        old = "2026-09-06T06:00:00+00:00"          # 昨日 — 越验收窗
        hub._audit_dir.mkdir(parents=True, exist_ok=True)
        with (hub._audit_dir / "learning.jsonl").open(
                "w", encoding="utf-8") as f:
            f.write(json.dumps({"ts": old, "type": "repair_completed",
                                "cause": "ambiguous_task"}) + "\n")
            f.write(json.dumps({"ts": "2026-09-06T07:00:00+00:00",
                                "type": "lesson_prior_injected",
                                "cause": "ambiguous_task"}) + "\n")
        stats = hub.verify_repairs()
        assert stats["adopted"] == 1 and stats["not_adopted"] == 0
        marks = hub._read_marks()
        v = [m for m in marks if m.get("type") == "repair_verified"]
        assert v[0]["status"] == "adopted_behavior"

    def test_not_adopted_on_recurrence(self, tmp_path, monkeypatch):
        hub = _hub(tmp_path, monkeypatch)
        old = "2026-09-06T06:00:00+00:00"          # 昨日 — 越验收窗
        hub.record_repair_completion("execution_error", "复盘目标")
        # 把打点 ts 改老（越验收窗）+ 之后复发同 cause lesson
        marks = hub._read_marks()
        marks[0]["ts"] = old
        with (hub._audit_dir / "learning.jsonl").open(
                "w", encoding="utf-8") as f:
            for m in marks:
                f.write(json.dumps(m) + "\n")
        _lesson(hub, "execution_error", "2026-09-06T08:00:00+00:00")
        stats = hub.verify_repairs()
        assert stats["not_adopted"] == 1
        v = [m for m in hub._read_marks()
             if m.get("type") == "repair_verified"]
        assert v[0]["status"] == "not_adopted"

    def test_idempotent(self, tmp_path, monkeypatch):
        hub = _hub(tmp_path, monkeypatch)
        hub._audit_dir.mkdir(parents=True, exist_ok=True)
        with (hub._audit_dir / "learning.jsonl").open(
                "w", encoding="utf-8") as f:
            f.write(json.dumps({"ts": "2026-09-06T06:00:00+00:00",
                                "type": "repair_completed",
                                "cause": "timeout"}) + "\n")
        hub.verify_repairs()
        n1 = len(hub._read_marks())
        hub.verify_repairs()                      # 重扫不重复写
        assert len(hub._read_marks()) == n1


class TestReflectionVitals:
    def test_adoption_rate(self, tmp_path, monkeypatch):
        import os
        monkeypatch.setenv("OCOS_AUDIT_DIR", str(tmp_path / "audit"))
        audit = tmp_path / "audit" / "learning.jsonl"
        audit.parent.mkdir(parents=True, exist_ok=True)
        with audit.open("w", encoding="utf-8") as f:
            f.write(json.dumps({"ts": "2026-09-07T12:00:00+00:00",
                                "type": "repair_verified",
                                "status": "adopted_behavior"}) + "\n")
            f.write(json.dumps({"ts": "2026-09-07T12:01:00+00:00",
                                "type": "repair_verified",
                                "status": "not_adopted"}) + "\n")
        from ocos.monitoring.vitals import _reflection_metrics
        m = _reflection_metrics(sqlite3.connect(":memory:"),
                                "2026-09-01T00:00:00+00:00")
        assert m["repair_verifications_7d"] == 2
        assert m["reflection_adoption_rate"] == 0.5

    def test_metric_always_present_in_computed_vitals(self, tmp_path,
                                                      monkeypatch):
        import sqlite3 as _sq
        monkeypatch.setenv("OCOS_AUDIT_DIR", str(tmp_path / "audit"))
        vdb = str(tmp_path / "v.db")
        _sq.connect(vdb).close()               # 空库文件（非 missing 路径）
        from ocos.monitoring.vitals import compute_vitals
        v = compute_vitals(vdb)
        assert "reflection_adoption_rate" in v          # 字段恒存在
        assert v["reflection_adoption_rate"] is None    # 无打点诚实 None
