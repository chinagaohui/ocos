"""主动目标循环（2026-09-08）— 刺激通道解决导向 + 优先级认领。

背景: 生产实证近 2 天 19 条自主提案中 18 条为同 stimulus key 重复
PROBE（打地鼠）— 目标完成 ≠ 问题解决，刺激冷却结束即重复响应，
且刺激通道不占每日 cap。本组测试钉死三道闸契约:

  1. cap 共享 — propose_stimulus 与 scan() 共用每日提案预算；
  2. 升级阶梯 — 同 key 第 n 次响应 kind 沿 PROBE→LEARN→REPAIR 升级，
     描述诚实注明"第 N 次响应，前序响应未消除该条件"；
     REPAIR 永待批（LEVEL>=2 也不得自主执行）；
  3. 饱和静默 — 阶梯走满（MAX_RESPONSES_PER_KEY）后同 key 不再提案。

响应计数持久化于 autonomous_goal_proposal episodes — 跨重启/跨实例
对账（scanner 冷却是进程内存态，重启即失效）。

优先级认领: GoalStore claim SQL ORDER BY priority DESC（此前仅
created_at — "按优先级执行"的字面缺口）。
"""

from __future__ import annotations

import json

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
    p = str(tmp_path / "loop.db")
    from ocos.memory.episode.store import EpisodeStore
    EpisodeStore(db_path=p).initialize()
    return p


def _make_hub(db, level: int = 2, env=None):
    from ocos.daemon.motivation import MotivationHub
    from ocos.execution.pending import PendingStore
    from ocos.goal.store import GoalStore
    if env is not None:
        env.write_text(str(level), encoding="utf-8")
    return MotivationHub(
        db_path=db,
        goal_store=GoalStore(db_path=db),
        pending_store=PendingStore(db_path=db),
    )


def _stim(key: str = "failure_cluster", desc: str = "近 24h 失败 10 次"):
    return [{"key": key, "severity": "high", "description": desc,
             "evidence": {"count": 10}}]


def _goal_kinds(db) -> list[str]:
    """goals 表中自主目标 kind 序列（按创建序）。"""
    import sqlite3
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        rows = conn.execute(
            "SELECT metadata FROM goals WHERE source='autonomous' "
            "ORDER BY created_at").fetchall()
    finally:
        conn.close()
    return [json.loads(r[0]).get("kind") for r in rows]


def _pending_kinds(db) -> list[str]:
    """待批队列中 autonomous_goal 的 kind 序列（按入队序）。"""
    import sqlite3
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        rows = conn.execute(
            "SELECT payload_json FROM pending_actions "
            "WHERE action_type='autonomous_goal' "
            "ORDER BY queued_at").fetchall()
    finally:
        conn.close()
    return [json.loads(r[0]).get("kind") for r in rows]


# ── 升级阶梯 ──────────────────────────────────────────────────────────────

class TestEscalationLadder:
    def test_first_response_probe(self, env_autonomy, db):
        stats = _make_hub(db).propose_stimulus(_stim(), level=2)
        assert stats["proposed"] == 1
        assert stats["escalated"] == 0
        assert _goal_kinds(db) == ["PROBE"]

    def test_second_response_escalates_to_learn(self, env_autonomy, db):
        hub = _make_hub(db)
        hub.propose_stimulus(_stim(), level=2)
        # 新实例（跨重启语义）+ 冷却结束同 key 重复触发
        stats = _make_hub(db).propose_stimulus(_stim(), level=2)
        assert stats["proposed"] == 1
        assert stats["escalated"] == 1
        assert _goal_kinds(db) == ["PROBE", "LEARN"]

    def test_third_response_repair_goes_pending_even_at_level2(
            self, env_autonomy, db):
        for _ in range(2):
            _make_hub(db).propose_stimulus(_stim(), level=2)
        stats = _make_hub(db).propose_stimulus(_stim(), level=2)
        assert stats["proposed"] == 1
        assert stats["pending_enqueued"] == 1
        assert stats["auto_enqueued"] == 0      # REPAIR 永待批
        assert _pending_kinds(db) == ["REPAIR"]

    def test_saturated_after_three_responses(self, env_autonomy, db):
        for _ in range(3):
            _make_hub(db).propose_stimulus(_stim(), level=2)
        stats = _make_hub(db).propose_stimulus(_stim(), level=2)
        assert stats["proposed"] == 0
        assert stats["saturated"] == 1
        assert _goal_kinds(db) == ["PROBE", "LEARN"]   # goals 表仅 2 条
        assert _pending_kinds(db) == ["REPAIR"]

    def test_description_notes_prior_unresolved(self, env_autonomy, db):
        _make_hub(db).propose_stimulus(_stim(), level=2)
        _make_hub(db).propose_stimulus(_stim(), level=2)
        import sqlite3
        conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        try:
            rows = conn.execute(
                "SELECT description FROM goals ORDER BY created_at"
            ).fetchall()
        finally:
            conn.close()
        assert "响应环境刺激[failure_cluster]：" in rows[0][0]
        assert "第 2 次响应" in rows[1][0]
        assert "前序响应未消除该条件" in rows[1][0]

    def test_response_count_persists_across_instances(self, env_autonomy, db):
        hub = _make_hub(db)
        hub.propose_stimulus(_stim(), level=2)
        hub2 = _make_hub(db)
        assert hub2._stimulus_response_count("failure_cluster") == 1
        assert hub2._stimulus_response_count("other_key") == 0

    def test_different_keys_escalate_independently(self, env_autonomy, db):
        _make_hub(db).propose_stimulus(_stim("failure_cluster"), level=2)
        stats = _make_hub(db).propose_stimulus(_stim("disk_high"), level=2)
        assert stats["proposed"] == 1
        assert stats["escalated"] == 0          # 新 key 首响应 → PROBE
        assert _goal_kinds(db) == ["PROBE", "PROBE"]


# ── cap 共享 ──────────────────────────────────────────────────────────────

class TestSharedCap:
    def test_stimulus_shares_daily_budget(self, env_autonomy, db,
                                          monkeypatch):
        monkeypatch.setenv("OCOS_AUTONOMY_GOAL_CAP", "1")
        stats = _make_hub(db).propose_stimulus(
            _stim("k1") + _stim("k2"), level=2)
        assert stats["proposed"] == 1
        assert stats["capped"] is True
        assert len(_goal_kinds(db)) == 1

    def test_scan_budget_consumed_by_stimulus(self, env_autonomy, db,
                                              monkeypatch):
        monkeypatch.setenv("OCOS_AUTONOMY_GOAL_CAP", "1")
        _make_hub(db).propose_stimulus(_stim(), level=2)
        from ocos.belief import BeliefManager
        bs = BeliefManager()
        bs.add_belief("低置信信念", probability=0.4)
        from ocos.daemon.motivation import MotivationHub
        from ocos.execution.pending import PendingStore
        from ocos.goal.store import GoalStore
        hub = MotivationHub(db_path=db, goal_store=GoalStore(db_path=db),
                            pending_store=PendingStore(db_path=db),
                            belief_store=bs)
        stats = hub.scan()
        assert stats["proposed"] == 0           # 预算被刺激通道占满
        assert stats["capped"] is True

    def test_level0_silent(self, env_autonomy, db):
        env_autonomy.write_text("0", encoding="utf-8")
        # 通道全接 — LEVEL0 直调也零提案（纵深防御，不依赖调用侧门控）
        stats = _make_hub(db).propose_stimulus(_stim(), level=0)
        assert stats["proposed"] == 0
        assert stats["auto_enqueued"] == 0
        assert stats["pending_enqueued"] == 0


# ── 优先级认领 ────────────────────────────────────────────────────────────

class TestPriorityClaim:
    @pytest.fixture()
    def store(self, tmp_path):
        from ocos.goal.store import GoalStore
        return GoalStore(db_path=str(tmp_path / "prio.db"))

    def test_human_claim_orders_by_priority(self, store):
        store.save(goal_id="G-LOW", level="TASK", status="PENDING",
                   description="低优先级", priority=1.0,
                   origin_level="HUMAN")
        store.save(goal_id="G-HIGH", level="TASK", status="PENDING",
                   description="高优先级", priority=9.0,
                   origin_level="HUMAN")
        claimed = store.claim_pending_human(limit=1)
        assert [c["id"] for c in claimed] == ["G-HIGH"]

    def test_self_claim_orders_by_priority(self, store):
        store.save(goal_id="S-LOW", level="TASK", status="PENDING",
                   description="低", priority=2.0, source="autonomous",
                   metadata={"autonomous": True}, origin_level="SELF")
        store.save(goal_id="S-HIGH", level="TASK", status="PENDING",
                   description="高", priority=8.0, source="autonomous",
                   metadata={"autonomous": True}, origin_level="SELF")
        claimed = store.claim_pending_approved_self(limit=1,
                                                    require_approved=False)
        assert [c["id"] for c in claimed] == ["S-HIGH"]

    def test_same_priority_falls_back_to_fifo(self, store):
        store.save(goal_id="G-OLD", level="TASK", status="PENDING",
                   description="先创建", priority=5.0, origin_level="HUMAN")
        store.save(goal_id="G-NEW", level="TASK", status="PENDING",
                   description="后创建", priority=5.0, origin_level="HUMAN")
        claimed = store.claim_pending_human(limit=1)
        assert [c["id"] for c in claimed] == ["G-OLD"]
