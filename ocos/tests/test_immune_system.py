"""PW-3.1/PW-3.2: 免疫系统上电测试 — 诊断循环 + 白名单修复 + 损伤注入。"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone

import pytest


@pytest.fixture
def db(tmp_path, monkeypatch):
    path = str(tmp_path / "diag.db")
    monkeypatch.setenv("OCOS_DB_PATH", path)
    # S3.13: 默认已切 ask — 白名单修复直接执行路径需显式 auto
    monkeypatch.setenv("OCOS_APPROVAL_MODE", "auto")
    return path


def _seed_stale(db: str, n: int = 30) -> None:
    """注入陈旧低显著度 Episode（记忆膨胀损伤）。"""
    from ocos.storage.migrations import ensure_schema
    ensure_schema(db)
    conn = sqlite3.connect(db)
    old = (datetime.now(timezone.utc) - timedelta(days=90)).isoformat()
    for i in range(n):
        conn.execute(
            """INSERT OR IGNORE INTO episodes
               (id, experience_id, session_id, context, goal, decision,
                action, outcome, condition, significance_score,
                evaluation_trace, source, status, tags, created_at)
               VALUES (?, ?, 'drill', '{}', NULL, ?, 'task_execution',
                       '{}', '', 0.1, '{}', 'drill', 'ACTIVE', '[]', ?)""",
            (f"EPI-{i}", f"EXP-{i}", f"陈旧任务 {i}", old))
    conn.commit()
    conn.close()


class TestDiagnosisCycle:
    def test_bloat_detected_and_queued(self, db):
        """记忆膨胀 → 归档修剪直接执行（审批关闭时白名单路径）。"""
        from ocos.daemon.repair_link import run_diagnosis_cycle
        _seed_stale(db, n=30)
        out = run_diagnosis_cycle(db)
        assert any("记忆膨胀" in q["description"] for q in out["repairs_executed"])

    def test_clean_db_no_bloat_proposal(self, db):
        from ocos.daemon.repair_link import run_diagnosis_cycle
        out = run_diagnosis_cycle(db)
        assert not any("记忆膨胀" in q["description"]
                       for q in out["repairs_queued"])


class TestRepairExecution:
    def _bridge(self, db):
        from ocos.execution.bridge import DecisionBridge
        b = DecisionBridge(db_path=db)
        b.attach_default_handlers()
        return b

    def test_reindex_whitelisted(self, db):
        from ocos.execution.pending import PendingStore
        store = PendingStore(db)
        store.enqueue(action_type="system_repair", target="storage",
                      payload={"proposal_id": "r1", "steps": ["重建存储索引并验证完整性"],
                               "description": "重建索引", "target": "storage"},
                      text="重建索引")
        b = self._bridge(db)
        row = store.list_by_status("pending")[0]
        r = b.execute_approved("system_repair", json.loads(row["payload_json"]))
        assert r.result["ok"] is True
        assert r.result["result"] == "success"

    def test_non_whitelisted_step_rolls_back(self, db):
        """未白名单步骤 → 失败 → 自动回滚（诚实拒绝危险操作）。"""
        from ocos.execution.pending import PendingStore
        store = PendingStore(db)
        store.enqueue(action_type="system_repair", target="system",
                      payload={"proposal_id": "r2", "steps": ["删除全部记忆"],
                               "description": "危险操作", "target": "system"},
                      text="危险修复")
        b = self._bridge(db)
        row = store.list_by_status("pending")[0]
        r = b.execute_approved("system_repair", json.loads(row["payload_json"]))
        assert r.result["ok"] is False
        assert r.result["result"] == "rolled_back"

    def test_archive_repair_heals_bloat(self, db):
        """归档修复真实生效: ACTIVE 低显著度残留归零。"""
        _seed_stale(db, n=25)
        from ocos.daemon.repair_link import execute_system_repair
        out = execute_system_repair(
            {"proposal_id": "r3",
             "steps": ["归档 30 天前的低显著度记忆条目"],
             "description": "记忆膨胀修剪", "target": "memory"}, db)
        assert out["ok"] is True
        conn = sqlite3.connect(db)
        left = conn.execute(
            "SELECT COUNT(*) FROM episodes WHERE significance_score < 0.3 "
            "AND status='ACTIVE'").fetchone()[0]
        conn.close()
        assert left == 0


class TestResilienceDrill:
    def test_drill_scores_full(self):
        import subprocess
        import sys
        r = subprocess.run(
            [sys.executable, "scripts/resilience_drill.py"],
            capture_output=True, text=True, timeout=120)
        assert "resilience score: 10/10" in (r.stdout + r.stderr)
