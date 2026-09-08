"""L3 (升级方案 v1.0) — 自主性涌现测试：MotivationHub + 待批流 + 防跑飞。

覆盖:
  - 信号聚合: lesson→REPAIR / belief 低置信边界→PROBE / goal_result 低成功率→LEARN
  - 诚实性: 无信号零提案
  - autonomy 闸: LEVEL0 沉默 / LEVEL1 待批 / LEVEL2 低风险直执行 / REPAIR 永待批
  - 限速 (OCOS_AUTONOMY_GOAL_CAP) 与去重（提案 episode 溯源）
  - 防跑飞: 连续 3 次失败自动降级 + 成功重置
  - bridge autonomous_goal handler: 批准 → goals 表 PENDING
环境隔离: OCOS_AUTONOMY_OVERRIDE / OCOS_AUDIT_DIR 指向 tmp。
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from ocos.execution.autonomy import get_autonomy_level, set_autonomy_level


@pytest.fixture()
def env_autonomy(tmp_path, monkeypatch):
    """自主级别覆盖文件 + 审计目录隔离。"""
    override = tmp_path / "autonomy_level"
    override.write_text("1", encoding="utf-8")
    monkeypatch.setenv("OCOS_AUTONOMY_OVERRIDE", str(override))
    monkeypatch.setenv("OCOS_AUDIT_DIR", str(tmp_path / "audit"))
    return override


@pytest.fixture()
def db(tmp_path):
    """共享 tmp 数据库：episodes/goals/pending 同库。"""
    p = str(tmp_path / "l3.db")
    from ocos.memory.episode.store import EpisodeStore
    EpisodeStore(db_path=p).initialize()
    return p


@pytest.fixture(autouse=True)
def _no_self_exploration(monkeypatch):
    """隔离自我探查源（2026-09-08 新增）：本文件专注原三类信号的
    评分/闸门/限速契约，空库下探查源恒有候选会污染计数断言。
    自我探查自身行为由 tests/test_digital_life_20260908.py 钉死。"""
    monkeypatch.setattr(
        "ocos.daemon.motivation.MotivationHub._from_self_exploration",
        lambda self: [])


def _set_level(override_path, level: int) -> None:
    override_path.write_text(str(level), encoding="utf-8")


def _make_hub(db, goal_store=None, belief_store=None):
    from ocos.daemon.motivation import MotivationHub
    from ocos.execution.pending import PendingStore
    return MotivationHub(
        db_path=db,
        goal_store=goal_store,
        pending_store=PendingStore(db_path=db),
        belief_store=belief_store,
    )


def _insert_episode(db, *, source: str, decision: str, outcome: dict,
                    tags: list[str], age_days: float = 0.0) -> None:
    from ocos.memory.episode.models import Episode, EpisodeStatus
    from ocos.memory.episode.store import EpisodeStore
    store = EpisodeStore(db_path=db)
    store.initialize()
    created = datetime.now(timezone.utc) - timedelta(days=age_days)
    store.save(Episode(
        id=f"EPI-T-{uuid.uuid4().hex[:12]}",
        experience_id=f"EXP-T-{uuid.uuid4().hex[:8]}",
        created_at=created,
        session_id="test",
        context={},
        goal="test",
        decision=decision,
        action="test",
        outcome=outcome,
        significance_score=0.5,
        source=source,
        status=EpisodeStatus.ACTIVE,
        tags=tags,
    ))


# ── 信号聚合 ──────────────────────────────────────────────────────────────

class TestSignals:
    def test_no_signals_no_proposals(self, env_autonomy, db):
        hub = _make_hub(db)
        stats = hub.scan()
        assert stats["candidates"] == 0
        assert stats["proposed"] == 0          # 无信号 → 诚实沉默

    def test_lesson_creates_repair(self, env_autonomy, db):
        _insert_episode(db, source="lesson",
                        decision="修复 api_timeout 的重试策略",
                        outcome={"success": True},
                        tags=["failure_lesson", "api_timeout"])
        hub = _make_hub(db)
        cands = hub.collect_candidates()
        repair = [c for c in cands if c.kind == "REPAIR"]
        assert repair and "api_timeout" in repair[0].description
        assert repair[0].evidence              # 证据可溯源

    def test_belief_boundary_creates_probe(self, env_autonomy, db):
        from ocos.belief import BeliefManager
        bs = BeliefManager()
        bs.add_belief("用户偏好深夜工作", probability=0.45)
        hub = _make_hub(db, belief_store=bs)
        cands = hub.collect_candidates()
        probe = [c for c in cands if c.kind == "PROBE"]
        assert probe and "只读探测" in probe[0].description
        assert probe[0].low_risk               # PROBE 属低风险白名单

    def test_belief_outside_boundary_ignored(self, env_autonomy, db):
        from ocos.belief import BeliefManager
        bs = BeliefManager()
        bs.add_belief("高置信信念", probability=0.95)   # 出界
        hub = _make_hub(db, belief_store=bs)
        assert not [c for c in hub.collect_candidates() if c.kind == "PROBE"]

    def test_low_goal_success_creates_learn(self, env_autonomy, db):
        for rate in (0.2, 0.4):
            _insert_episode(db, source="goal_result",
                            decision="目标结果", tags=["goal_result"],
                            outcome={"success": False,
                                     "task_success_rate": rate})
        hub = _make_hub(db)
        learn = [c for c in hub.collect_candidates() if c.kind == "LEARN"]
        assert learn and "成功率" in learn[0].description

    def test_healthy_goal_success_no_learn(self, env_autonomy, db):
        for rate in (0.9, 1.0):
            _insert_episode(db, source="goal_result",
                            decision="目标结果", tags=["goal_result"],
                            outcome={"success": True,
                                     "task_success_rate": rate})
        hub = _make_hub(db)
        assert not [c for c in hub.collect_candidates() if c.kind == "LEARN"]


# ── autonomy 闸与落地通道 ─────────────────────────────────────────────────

class TestAutonomyGate:
    def test_level0_silent(self, env_autonomy, db):
        _set_level(env_autonomy, 0)
        _insert_episode(db, source="lesson", decision="x",
                        outcome={"success": True},
                        tags=["failure_lesson", "api_timeout"])
        stats = _make_hub(db).scan()
        assert stats["proposed"] == 0

    def test_level1_repair_goes_pending(self, env_autonomy, db):
        _insert_episode(db, source="lesson", decision="x",
                        outcome={"success": True},
                        tags=["failure_lesson", "api_timeout"])
        stats = _make_hub(db).scan()
        assert stats["pending_enqueued"] == 1
        assert stats["auto_enqueued"] == 0     # LEVEL1 不得自主执行
        from ocos.execution.pending import PendingStore
        rows = PendingStore(db_path=db).list_by_status("pending")
        assert rows and rows[0]["action_type"] == "autonomous_goal"
        assert rows[0]["source"] == "l3_motivation"

    def test_level2_probe_auto_executes(self, env_autonomy, db):
        _set_level(env_autonomy, 2)
        from ocos.belief import BeliefManager
        from ocos.goal.store import GoalStore
        bs = BeliefManager()
        bs.add_belief("低置信信念", probability=0.4)
        gs = GoalStore(db_path=db)
        stats = _make_hub(db, goal_store=gs, belief_store=bs).scan()
        assert stats["auto_enqueued"] == 1
        pending = gs.load_active()
        assert pending and pending[0]["source"] == "autonomous"
        assert json.loads(pending[0]["metadata"])["autonomous"] is True
        assert pending[0]["origin_level"] == "SELF"

    def test_repair_pending_even_at_level2(self, env_autonomy, db):
        _set_level(env_autonomy, 2)
        _insert_episode(db, source="lesson", decision="x",
                        outcome={"success": True},
                        tags=["failure_lesson", "api_timeout"])
        stats = _make_hub(db).scan()
        assert stats["pending_enqueued"] == 1   # REPAIR 高风险 → 永待批
        assert stats["auto_enqueued"] == 0


# ── 限速与去重 ────────────────────────────────────────────────────────────

class TestRateLimit:
    def test_daily_cap(self, env_autonomy, db, monkeypatch):
        monkeypatch.setenv("OCOS_AUTONOMY_GOAL_CAP", "1")
        _insert_episode(db, source="lesson", decision="x",
                        outcome={"success": True},
                        tags=["failure_lesson", "api_timeout"])
        hub = _make_hub(db)
        stats = hub.scan()
        assert stats["proposed"] == 1
        assert stats["capped"] is False
        stats2 = hub.scan()                    # 当日已满 → capped
        assert stats2["proposed"] == 0
        assert stats2["capped"] is True

    def test_dedup_across_scans(self, env_autonomy, db):
        _insert_episode(db, source="lesson", decision="x",
                        outcome={"success": True},
                        tags=["failure_lesson", "api_timeout"])
        hub = _make_hub(db)
        assert hub.scan()["proposed"] == 1
        assert hub.scan()["proposed"] == 0     # 同 cause 二次扫描 → 去重


# ── 防跑飞 ────────────────────────────────────────────────────────────────

class TestRunawayGuard:
    def test_consecutive_failures_demote(self, env_autonomy, db):
        _set_level(env_autonomy, 2)
        hub = _make_hub(db)
        assert hub.record_result(False) is None   # 1
        assert hub.record_result(False) is None   # 2
        info = hub.record_result(False)           # 3 → 降级
        assert info and info["demoted"] is True
        assert info["from"] == 2 and info["to"] == 1
        assert get_autonomy_level() == 1

    def test_demote_writes_audit(self, env_autonomy, db, tmp_path):
        import os
        _set_level(env_autonomy, 2)
        hub = _make_hub(db)
        hub.record_result(False)
        hub.record_result(False)
        hub.record_result(False)
        audit_dir = tmp_path / "audit"
        files = list(audit_dir.glob("*.jsonl")) if audit_dir.exists() else []
        assert files, "降级必须留审计 JSONL"
        rec = json.loads(files[0].read_text(encoding="utf-8").strip().splitlines()[-1])
        assert rec["kind"] == "level_change" and rec["new"] == 1
        assert "防跑飞" in rec.get("source", "") or rec.get("old") == 2

    def test_success_resets_counter(self, env_autonomy, db):
        _set_level(env_autonomy, 2)
        hub = _make_hub(db)
        hub.record_result(False)
        hub.record_result(False)
        assert hub.record_result(True) is None  # 成功重置
        hub.record_result(False)
        assert hub.record_result(False) is None  # 未达 3 连败
        assert get_autonomy_level() == 2

    def test_demote_not_below_zero(self, env_autonomy, db):
        _set_level(env_autonomy, 0)
        hub = _make_hub(db)
        hub.record_result(False)
        hub.record_result(False)
        info = hub.record_result(False)
        assert info["demoted"] is False         # 已在 LEVEL0，如实上报
        assert get_autonomy_level() == 0


# ── bridge handler（待批 → 批准执行） ────────────────────────────────────

class TestBridgeHandler:
    def test_approved_autonomous_goal_written(self, env_autonomy, db, tmp_path):
        from ocos.execution.bridge import DecisionBridge
        from ocos.goal.store import GoalStore

        def _sink(payload: dict) -> None:
            GoalStore(db_path=db).save(
                goal_id=payload["goal_id"], level="TASK", status="PENDING",
                description=payload["description"], source="autonomous",
                metadata={"autonomous": True, "approved": True},
                origin_level="SELF", authority="AUTONOMOUS")

        bridge = DecisionBridge(db_path=db, autonomous_goal_sink=_sink)
        result = bridge._handler_autonomous_goal(SimpleNamespace(payload={
            "goal_id": "GOAL-AUTO-TEST1",
            "description": "只读探测：验证信念 X",
            "kind": "PROBE", "score": 0.8, "evidence": "belief bel-1",
        }))
        assert result["ok"] is True, result
        rows = GoalStore(db_path=db).load_active()
        assert rows and rows[0]["id"] == "GOAL-AUTO-TEST1"
        assert rows[0]["status"] == "PENDING"
        assert rows[0]["source"] == "autonomous"

    def test_handler_rejects_empty_payload(self, env_autonomy, db):
        from ocos.execution.bridge import DecisionBridge
        bridge = DecisionBridge(db_path=db)
        result = bridge._handler_autonomous_goal(
            SimpleNamespace(payload={}))
        assert result["ok"] is False and "missing" in result["error"]

    def test_handler_without_sink_reports_honestly(self, env_autonomy, db):
        from ocos.execution.bridge import DecisionBridge
        bridge = DecisionBridge(db_path=db)
        result = bridge._handler_autonomous_goal(SimpleNamespace(payload={
            "goal_id": "G1", "description": "d"}))
        assert result["ok"] is False and "sink" in result["error"]


# ── 提案 episode 溯源 ─────────────────────────────────────────────────────

class TestProposalTrace:
    def test_proposal_episode_recorded(self, env_autonomy, db):
        _insert_episode(db, source="lesson", decision="x",
                        outcome={"success": True},
                        tags=["failure_lesson", "api_timeout"])
        _make_hub(db).scan()
        conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        try:
            row = conn.execute(
                "SELECT COUNT(*) FROM episodes "
                "WHERE source='autonomous_goal_proposal'").fetchone()
        finally:
            conn.close()
        assert row[0] == 1                     # 提案可溯源（限速/去重依据）


# ── daemon 装配回归（2026-09-07 生产零提案根因）──────────────────────────

class TestDaemonWiring:
    """根因回归：daemon 必须给 MotivationHub 接 pending_store 与持久 BeliefStore。

    2026-09-07 生产排查：MotivationHub 构造漏传 pending_store → LEVEL1
    （默认档）全部候选在 _propose 走"无落地通道"静默 return（4 候选全过
    阈值仍 0 提案）；belief_store 误传内存 BeliefSystem（query(statement,
    threshold) 签名与 min_probability 调用不匹配）→ PROBE 通道 TypeError
    被吞。本组测试在 daemon 级装配钉死契约（单测用 BeliefManager 故未覆盖）。
    """

    @pytest.fixture()
    def daemon(self, tmp_path, monkeypatch):
        override = tmp_path / "autonomy_level"
        override.write_text("1", encoding="utf-8")
        monkeypatch.setenv("OCOS_AUTONOMY_OVERRIDE", str(override))
        monkeypatch.setenv("OCOS_AUDIT_DIR", str(tmp_path / "audit"))
        monkeypatch.setenv("OCOS_HEARTBEAT_PATH",
                           str(tmp_path / "hb.json"))
        from unittest.mock import MagicMock

        from ocos.daemon import ResidentRuntime
        return ResidentRuntime(agent=MagicMock(),
                               db_path=str(tmp_path / "daemon.db"))

    def test_wires_pending_store(self, daemon):
        assert daemon._motivation is not None
        # LEVEL1（默认档）提案的唯一落地通道 — 生产零提案根因即此为 None
        assert daemon._motivation._pending_store is not None

    def test_wires_lazy_belief_provider(self, daemon):
        # 构造时 memory hub 未 boot → 提供者诚实解析为 None（不炸不假活）
        assert callable(daemon._motivation._belief_store)
        assert daemon._motivation._belief_store() is None

    def test_level1_scan_enqueues_pending(self, daemon, tmp_path):
        db = str(tmp_path / "daemon.db")
        _insert_episode(db, source="lesson", decision="复盘 api_timeout",
                        outcome={"success": True},
                        tags=["failure_lesson", "api_timeout"])
        stats = daemon._motivation.scan()
        assert stats["proposed"] >= 1
        assert stats["pending_enqueued"] >= 1
        conn = sqlite3.connect(db)
        try:
            pend = conn.execute(
                "SELECT COUNT(*) FROM pending_actions "
                "WHERE action_type='autonomous_goal'").fetchone()[0]
            epi = conn.execute(
                "SELECT COUNT(*) FROM episodes "
                "WHERE source='autonomous_goal_proposal'").fetchone()[0]
        finally:
            conn.close()
        assert pend >= 1 and epi >= 1          # 待批入队 + 提案溯源双落库

    def test_probe_channel_alive_with_persistent_store(
            self, daemon, tmp_path, monkeypatch):
        hub = daemon._motivation
        # boot 后形态：runtime._memory_hub 就绪 → 提供者解析为持久 BeliefStore
        from ocos.memory.hub import MemoryHub
        mem = MemoryHub(str(tmp_path / "daemon.db"))
        mem.initialize()
        monkeypatch.setattr(daemon._runtime, "_memory_hub", mem)
        store = daemon._motivation._belief_store()
        assert hasattr(store, "query_by_confidence")   # PROBE 通道 API 匹配
        from ocos.memory.belief.models import Belief
        store.save(Belief.create(
            statement="测试假设：夜间批处理任务成功率更高",
            source_knowledge_ids=["KN-T1"], evidence_ids=["EV-T1"],
            confidence=0.45, uncertainty=0.55))
        probe = [c for c in hub.collect_candidates() if c.kind == "PROBE"]
        assert probe and "只读探测" in probe[0].description
        assert probe[0].low_risk               # PROBE 属低风险白名单


class TestSelfMonitorWiring:
    """Phase E 自演化装配回归（2026-09-07 同族病灶修复）。

    旧装配在 __init__ 期取 memory hub（boot 前恒 None）+ `belief()` 误作
    方法（property）→ 双重失效且 debug 级静默——自演化检查在生产从未
    启用。现初始化移至 start() 的 boot 之后（_init_self_monitor）。
    """

    @pytest.fixture()
    def daemon(self, tmp_path, monkeypatch):
        override = tmp_path / "autonomy_level"
        override.write_text("1", encoding="utf-8")
        monkeypatch.setenv("OCOS_AUTONOMY_OVERRIDE", str(override))
        monkeypatch.setenv("OCOS_AUDIT_DIR", str(tmp_path / "audit"))
        monkeypatch.setenv("OCOS_HEARTBEAT_PATH",
                           str(tmp_path / "hb.json"))
        from unittest.mock import MagicMock

        from ocos.daemon import ResidentRuntime
        return ResidentRuntime(agent=MagicMock(),
                               db_path=str(tmp_path / "daemon.db"))

    def test_passive_pre_boot_honest_silence(self, daemon):
        # 构造期不装配不炸（旧病灶：静默失败伪装成"未装配"）
        assert daemon._self_monitor is None
        assert daemon._self_monitor_eligible is False
        daemon._init_self_monitor()            # hub 未 boot → 诚实 passive
        assert daemon._self_monitor is None
        assert daemon._self_monitor_eligible is False

    def test_wired_post_boot_with_persistent_store(
            self, daemon, tmp_path, monkeypatch):
        from ocos.memory.hub import MemoryHub
        mem = MemoryHub(str(tmp_path / "daemon.db"))
        mem.initialize()
        monkeypatch.setattr(daemon._runtime, "_memory_hub", mem)
        daemon._init_self_monitor()
        assert daemon._self_monitor_eligible is True
        assert daemon._self_monitor is not None
        # 绑定的是持久 BeliefStore（builder 经 query_by_domain 取信念）
        assert hasattr(daemon._self_monitor._belief_store,
                       "query_by_domain")

    def test_init_idempotent(self, daemon, tmp_path, monkeypatch):
        from ocos.memory.hub import MemoryHub
        mem = MemoryHub(str(tmp_path / "daemon.db"))
        mem.initialize()
        monkeypatch.setattr(daemon._runtime, "_memory_hub", mem)
        daemon._init_self_monitor()
        first = daemon._self_monitor
        daemon._init_self_monitor()            # 重入不重建
        assert daemon._self_monitor is first
