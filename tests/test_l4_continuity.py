"""L4-3 (升级方案 v1.0) — 跨重启一致性测试：V5 身份 hash 校验 + 记忆计数断言。

覆盖:
  - 首启: 写基线（不算漂移），基线文件落 audit 目录
  - 无漂移复检: 同参数二启 → OK，无告警
  - 身份锚漂移: born_at/name 变化 → drift=True + 漂移原因可读
  - 宪法漂移: 原则变更（版本化落库）→ drift=True（价值观属身份）
  - 自我模型演进: 画像更新 → 不算漂移（正常演进不误报）
  - 记忆计数断言: episodes 减少 → memory_loss=True
  - 漂移审计: audit episode（source=continuity_check）落库
  - daemon 接线: start() 挂载 boot_check（源码级断言）
环境隔离: OCOS_AUDIT_DIR 指向 tmp。
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone

import pytest


@pytest.fixture()
def env_audit(tmp_path, monkeypatch):
    audit = tmp_path / "audit"
    monkeypatch.setenv("OCOS_AUDIT_DIR", str(audit))
    return audit


@pytest.fixture()
def db(tmp_path):
    p = str(tmp_path / "l4c.db")
    from ocos.memory.episode.store import EpisodeStore
    EpisodeStore(db_path=p).initialize()
    return p


_ID = {"agent_id": "agent-test", "born_at": "2026-01-01T00:00:00+00:00",
       "name": "OCOS Agent"}


def _checker(db):
    from ocos.daemon.continuity import ContinuityChecker
    return ContinuityChecker(db)


def _insert_episode(db) -> None:
    from ocos.memory.episode.models import Episode, EpisodeStatus
    from ocos.memory.episode.store import EpisodeStore
    estore = EpisodeStore(db_path=db)
    estore.initialize()
    estore.save(Episode(
        id=f"EPI-{uuid.uuid4().hex[:12]}",
        experience_id=f"EXP-{uuid.uuid4().hex[:10]}",
        created_at=datetime.now(timezone.utc),
        session_id="t", context={}, goal="g", decision="d",
        action="goal_result", outcome={"success": True},
        significance_score=0.5, source="agent_runtime",
        status=EpisodeStatus.ACTIVE, tags=[],
    ))


# ── 基线与无漂移 ─────────────────────────────────────────────────────


class TestBaseline:
    def test_first_boot_creates_baseline(self, env_audit, db):
        r = _checker(db).boot_check(identity_params=_ID)
        assert r["baseline_created"] is True
        assert r["drift"] is False and r["memory_loss"] is False
        base = json.loads(
            (env_audit / "continuity_baseline.json").read_text("utf-8"))
        assert base["identity_hash"] == r["identity_hash"]
        assert base["memory_count"] == r["memory_count"]

    def test_second_boot_no_drift(self, env_audit, db):
        c = _checker(db)
        c.boot_check(identity_params=_ID)
        _insert_episode(db)  # 记忆增长正常
        r2 = c.boot_check(identity_params=_ID)
        assert r2["drift"] is False and r2["memory_loss"] is False
        assert r2["baseline_created"] is False

    def test_no_anchor_honest_flag(self, env_audit, db):
        r = _checker(db).boot_check(identity_params=None)
        assert r["baseline_created"] is True
        base = json.loads(
            (env_audit / "continuity_baseline.json").read_text("utf-8"))
        assert base["snapshot"]["identity_available"] is False


# ── 漂移检测 ─────────────────────────────────────────────────────────


class TestDrift:
    def test_identity_change_detected(self, env_audit, db):
        c = _checker(db)
        c.boot_check(identity_params=_ID)
        drifted = dict(_ID, born_at="2026-02-02T00:00:00+00:00")
        r2 = c.boot_check(identity_params=drifted)
        assert r2["drift"] is True
        assert any("身份锚" in d for d in r2["details"])

    def test_constitution_change_detected(self, env_audit, db):
        c = _checker(db)
        c.boot_check(identity_params=_ID)
        # 宪法修改走待批+批准（人工 = authority），落新版本
        from ocos.constitution.versioned import VersionedConstitution
        vc = VersionedConstitution(db)
        vc.current()
        new = [{"id": "honesty", "title": "诚实优先",
                "content": "加严后的条款。", "params": {}}]
        vc.save_version(new, reason="测试修订", approved_by="human")
        r2 = c.boot_check(identity_params=_ID)
        assert r2["drift"] is True
        assert any("宪法" in d for d in r2["details"])

    def test_self_model_evolution_not_drift(self, env_audit, db):
        c = _checker(db)
        c.boot_check(identity_params=_ID)
        # 自我模型校准演进（正常行为）→ 不算人格漂移
        from ocos.self.agent_self_model import AgentSelfModel
        AgentSelfModel(db).calibrate(capability_names=["filesystem"])
        r2 = c.boot_check(identity_params=_ID)
        assert r2["drift"] is False


# ── 记忆计数断言 ─────────────────────────────────────────────────────


class TestMemoryAssertion:
    def test_memory_loss_detected(self, env_audit, db):
        c = _checker(db)
        _insert_episode(db)
        c.boot_check(identity_params=_ID)
        # 模拟记忆丢失: 直接删 episodes
        conn = sqlite3.connect(db)
        conn.execute("DELETE FROM episodes")
        conn.commit()
        conn.close()
        r2 = c.boot_check(identity_params=_ID)
        assert r2["memory_loss"] is True
        assert any("记忆计数下降" in d for d in r2["details"])

    def test_memory_growth_normal(self, env_audit, db):
        c = _checker(db)
        c.boot_check(identity_params=_ID)
        _insert_episode(db)
        _insert_episode(db)
        r2 = c.boot_check(identity_params=_ID)
        assert r2["memory_loss"] is False
        assert r2["memory_count"] >= 2


# ── 漂移审计 ─────────────────────────────────────────────────────────


class TestAudit:
    def test_drift_writes_episode(self, env_audit, db):
        c = _checker(db)
        c.boot_check(identity_params=_ID)
        c.boot_check(identity_params=dict(_ID, name="改名了"))
        from ocos.memory.episode.store import EpisodeStore
        estore = EpisodeStore(db_path=db)
        estore.initialize()
        rows = estore.query_by_time(limit=50)
        checks = [e for e in rows
                  if getattr(e, "source", "") == "continuity_check"]
        # 成功校验也落库（vitals continuity_checks 正向证据），漂移单独告警
        assert len(checks) == 2
        alerts = [e for e in checks
                  if e.action == "continuity_drift_alert"]
        assert len(alerts) == 1
        assert alerts[0].outcome.get("drift") is True
        assert alerts[0].outcome.get("success") is False

    def test_ok_records_boot_check_evidence(self, env_audit, db):
        """无漂移 → 落 boot_check 证据 episode（success=true, drift=false）。"""
        c = _checker(db)
        c.boot_check(identity_params=_ID)
        c.boot_check(identity_params=_ID)
        from ocos.memory.episode.store import EpisodeStore
        estore = EpisodeStore(db_path=db)
        estore.initialize()
        rows = estore.query_by_time(limit=50)
        checks = [e for e in rows
                  if getattr(e, "source", "") == "continuity_check"]
        assert len(checks) == 2
        assert all(e.action == "continuity_boot_check" for e in checks)
        assert all(e.outcome.get("success") is True and
                   e.outcome.get("drift") is False for e in checks)


# ── daemon 接线 ──────────────────────────────────────────────────────


class TestDaemonWiring:
    def test_daemon_start_wiring(self):
        import inspect
        from ocos import daemon
        src = inspect.getsource(daemon)
        assert "ContinuityChecker(self._db_path)" in src
        assert "boot_check(" in src
        assert "get_born_at" in src
