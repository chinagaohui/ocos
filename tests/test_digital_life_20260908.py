"""数字生命能力建设（2026-09-08）— 自我连续性 + 好奇心去噪与自我探查。

用户决策：不要模仿者（WeClone 路线废弃），要 OCOS 成为数字生命本身。
数字生命区别于模仿者的本质：人格来自自身经历的连续沉淀，而非复刻他人。

A. 自我连续性 — identity_snapshots 此前仅优雅 shutdown 路径写入
   （agent_runtime._save_identity_snapshot 唯一调用点在 shutdown），
   systemd 下 daemon 从不优雅关闭 → 表恒空。新增周键幂等周度快照，
   daemon 周期块调用，payload 带成长统计（本周完成目标/经历数）。

B. 好奇心去噪与自我探查 —
   B1 生产实证 belief 边界区间 241 个候选 100% 为 pattern 模板回声
      （"主题X相关经历持续出现"），探测它们 = 好奇心空转 → 过滤；
   B2 新增自我探查源：pkgutil 实扫 ocos 子包 × episodes 全文提及，
      从未被触及的模块 → 只读梳理候选（对自身未知疆域的好奇）。
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone

import pytest


@pytest.fixture()
def env_autonomy(tmp_path, monkeypatch):
    override = tmp_path / "autonomy_level"
    override.write_text("2", encoding="utf-8")
    monkeypatch.setenv("OCOS_AUTONOMY_OVERRIDE", str(override))
    monkeypatch.setenv("OCOS_AUDIT_DIR", str(tmp_path / "audit"))
    return override


@pytest.fixture()
def db(tmp_path):
    p = str(tmp_path / "life.db")
    from ocos.memory.episode.store import EpisodeStore
    EpisodeStore(db_path=p).initialize()
    return p


def _make_hub(db, level: int = 2):
    from ocos.daemon.motivation import MotivationHub
    from ocos.execution.pending import PendingStore
    from ocos.goal.store import GoalStore
    return MotivationHub(
        db_path=db,
        goal_store=GoalStore(db_path=db),
        pending_store=PendingStore(db_path=db),
    )


# ── A. 自我连续性：周度身份快照 ──────────────────────────────────────

class TestWeeklyIdentitySnapshot:
    """identity_snapshots 表此前 0 行（生产 2026-09-08 实证）——
    周度快照必须真实落盘且幂等。"""

    def _make_runtime(self, tmp_path):
        """最小 AgentRuntime：identity_store + db_path 即可支撑快照路径。

        _save_identity_snapshot 只触 identity_store / memory / beliefs /
        _state / _cycle_count / _result_cursor / _recent_results /
        agent.agent_id —— 全部用 __new__ 后手工置齐，绕开重装配。
        """
        from ocos.agent.agent_runtime import AgentRuntime
        from ocos.agent.identity_store import IdentitySQLiteStore
        db_path = str(tmp_path / "life_rt.db")
        store = IdentitySQLiteStore(db_path)
        store.initialize()
        rt = AgentRuntime.__new__(AgentRuntime)
        rt._identity_store = store
        rt._db_path = db_path
        rt._cycle_count = 42
        rt._result_cursor = 0
        rt._recent_results = []
        rt._state = type("S", (), {"name": "RUNNING"})()
        rt.memory = type("M", (), {"working_count": 3})()
        rt.beliefs = type("B", (), {"belief_count": 7})()
        rt.agent = type("A", (), {"agent_id": "test-agent"})()
        # 周度统计需要 goals/episodes 表（惰性建表，触发一次即可）
        from ocos.goal.store import GoalStore
        from ocos.memory.episode.store import EpisodeStore
        EpisodeStore(db_path=db_path).initialize()
        GoalStore(db_path=db_path).load_active()
        return rt, db_path

    def test_snapshot_lands_in_table(self, tmp_path):
        rt, db_path = self._make_runtime(tmp_path)
        snap = rt.save_weekly_identity_snapshot()
        assert snap is not None
        iso = datetime.now(timezone.utc).isocalendar()
        assert snap["week_key"] == f"{iso[0]}-W{iso[1]:02d}"
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        try:
            rows = conn.execute(
                "SELECT snapshot_id, payload FROM identity_snapshots"
                " WHERE snapshot_id LIKE 'weekly-%'").fetchall()
        finally:
            conn.close()
        assert len(rows) == 1
        payload = json.loads(rows[0][1])
        assert payload["agent_id"] == "test-agent"
        assert "continuity_hash" in payload
        # 成长统计字段存在（空库 = 0，诚实计数）
        assert payload["goals_completed_this_week"] == 0
        assert payload["episodes_this_week"] == 0

    def test_snapshot_idempotent_per_week(self, tmp_path):
        rt, db_path = self._make_runtime(tmp_path)
        first = rt.save_weekly_identity_snapshot()
        second = rt.save_weekly_identity_snapshot()
        assert first is not None
        assert second is None                      # 同周重复 → 诚实沉默
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        try:
            n = conn.execute(
                "SELECT COUNT(*) FROM identity_snapshots"
                " WHERE snapshot_id LIKE 'weekly-%'").fetchone()[0]
        finally:
            conn.close()
        assert n == 1

    def test_shutdown_snapshot_id_still_separate(self, tmp_path):
        """runtime_identity（shutdown 语义）与 weekly-* 互不覆盖。"""
        rt, db_path = self._make_runtime(tmp_path)
        rt.save_weekly_identity_snapshot()
        rt._save_identity_snapshot()               # 默认 runtime_identity
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        try:
            ids = [r[0] for r in conn.execute(
                "SELECT DISTINCT snapshot_id FROM identity_snapshots")]
        finally:
            conn.close()
        assert "runtime_identity" in ids
        assert any(i.startswith("weekly-") for i in ids)

    def test_weekly_prune_keeps_26(self, tmp_path, monkeypatch):
        """周键行数全局封顶 26（save_snapshot keep-10 仅按 id 生效）。"""
        rt, db_path = self._make_runtime(tmp_path)
        conn = sqlite3.connect(db_path)
        try:
            for i in range(30):
                conn.execute(
                    "INSERT INTO identity_snapshots (snapshot_id, payload)"
                    " VALUES (?, ?)", (f"weekly-2020-W{i+1:02d}", "{}"))
            conn.commit()
        finally:
            conn.close()
        rt.save_weekly_identity_snapshot()
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        try:
            n = conn.execute(
                "SELECT COUNT(*) FROM identity_snapshots"
                " WHERE snapshot_id LIKE 'weekly-%'").fetchone()[0]
        finally:
            conn.close()
        assert n <= 26


# ── B1. 好奇心去噪：模板回声信念过滤 ─────────────────────────────────

class _Belief:
    def __init__(self, bid: str, statement: str, confidence: float):
        self.id = bid
        self.statement = statement
        self.confidence = confidence


class _TemplateBeliefStore:
    """生产实证形态：边界区间全是"主题X相关经历持续出现"模板回声。"""

    def __init__(self, beliefs):
        self._beliefs = beliefs

    def query_by_confidence(self, lo, hi, limit=10):
        return [b for b in self._beliefs if lo <= b.confidence <= hi][:limit]


class TestBeliefTemplateFilter:
    def test_template_beliefs_filtered(self, db):
        hub = _make_hub(db)
        store = _TemplateBeliefStore([
            _Belief("BLF-1", "主题「测试验证」相关经历持续出现", 0.5),
            _Belief("BLF-2", "主题「自栓」相关经历持续出现", 0.6),
        ])
        hub._belief_store = store
        assert hub._from_belief_boundary() == []    # 全模板 →诚实沉默

    def test_substantive_belief_still_probes(self, db):
        hub = _make_hub(db)
        store = _TemplateBeliefStore([
            _Belief("BLF-9", "docker 容器内 GPU 直通在驱动 595 下不稳定", 0.45),
        ])
        hub._belief_store = store
        out = hub._from_belief_boundary()
        assert len(out) == 1
        assert out[0].kind == "PROBE"
        assert "GPU 直通" in out[0].description


# ── B2. 自我探查：未触及模块 → 只读梳理候选 ──────────────────────────

class TestSelfExploration:
    def test_unexplored_module_proposed(self, db, monkeypatch):
        import ocos
        hub = _make_hub(db)
        # 桩 inventory：两个模块，growth 已在 episode 中提及，daemon 未
        monkeypatch.setattr(
            "pkgutil.iter_modules",
            lambda path: [type("M", (), {"name": "growth"})(),
                          type("M", (), {"name": "daemon"})()],
            raising=False)
        monkeypatch.setattr(ocos, "__path__", ["/fake"], raising=False)
        conn = sqlite3.connect(db)
        try:
            conn.execute(
                "INSERT INTO episodes (experience_id, session_id, context,"
                " goal, decision, action, outcome, condition,"
                " significance_score, evaluation_trace, source, status,"
                " tags, created_at) VALUES ('E1','s','{}','g',"
                "'梳理 ocos.growth 模块','act','{}','',0.5,'{}','src',"
                "'ACTIVE','[]','2026-09-08T00:00:00+00:00')")
            conn.commit()
        finally:
            conn.close()
        out = hub._from_self_exploration()
        assert len(out) == 1
        c = out[0]
        assert c.kind == "PROBE"
        assert "ocos.daemon" in c.description
        assert c.low_risk is True
        assert "无 episode 提及" in c.evidence

    def test_all_explored_silent(self, db, monkeypatch):
        import ocos
        hub = _make_hub(db)
        monkeypatch.setattr(
            "pkgutil.iter_modules",
            lambda path: [type("M", (), {"name": "growth"})()],
            raising=False)
        monkeypatch.setattr(ocos, "__path__", ["/fake"], raising=False)
        conn = sqlite3.connect(db)
        try:
            conn.execute(
                "INSERT INTO episodes (experience_id, session_id, context,"
                " goal, decision, action, outcome, condition,"
                " significance_score, evaluation_trace, source, status,"
                " tags, created_at) VALUES ('E1','s','{}','g',"
                "'关于 ocos.growth 的工作','act','{}','',0.5,'{}','src',"
                "'ACTIVE','[]','2026-09-08T00:00:00+00:00')")
            conn.commit()
        finally:
            conn.close()
        assert hub._from_self_exploration() == []

    def test_registered_in_collect_candidates(self, db, monkeypatch):
        """自我探查已接入信号聚合（通道静默失败要有 warning 而非消失）。"""
        hub = _make_hub(db)
        called = []
        monkeypatch.setattr(hub, "_from_belief_boundary",
                            lambda: called.append("belief") or [])
        monkeypatch.setattr(hub, "_from_self_exploration",
                            lambda: called.append("explore") or [])
        hub.collect_candidates()
        assert "explore" in called
