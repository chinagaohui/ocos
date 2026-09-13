"""SELF-EVO 自进化闭环回归测试（2026-09-12 用户裁决）.

用户诉求: OCOS 思考结果（认知循环反思+LLM 学习）必须能直接让 agent
执行优化升级。此前断链两处（生产实锤 271 条 EVO-GOAL 全部 ABANDONED）:
  ① Step③ Mini-Plan 是固定模板无真实行动 → Pump 闸拦截
  ② Pump 转_goal 时未设 origin_level（默认 SYSTEM）→ 认领通道
     只认 HUMAN/SELF → goal 永久滞留 → ABANDONED
修复后全链: EVO-Plan(真实行动+success_criteria) → Pump 自动批准
→ goals(SELF+approved) → claim_pending_approved_self → agent 执行。
"""

from __future__ import annotations

import json
import sqlite3

import pytest

FINDINGS = (
    "LLM 验证发现: websearch.py 的重试间隔固定 2 秒，连续失败时会被 "
    "cn.bing.com 限流；建议改为指数退避并加 UA 轮换。"
)


def _bare_runtime():
    """构造未 boot 的 ResidentRuntime 壳 — 涉及方法只依赖 _db_path。"""
    from ocos.daemon import ResidentRuntime

    return ResidentRuntime.__new__(ResidentRuntime)


class TestPlanBuilder:
    """Step③: 思考结果 → 可执行 EVO-Plan（非固定模板）。"""

    def test_findings_produce_executable_plan(self):
        rt = _bare_runtime()
        plan = rt._build_plan_from_reflection(
            {"source": "new_knowledge", "question": "深入学习: 重试策略"},
            FINDINGS, ":memory:")
        assert plan is not None
        assert plan["title"].startswith("EVO-Plan:"), (
            "新方案必须用 EVO-Plan 前缀（Pump 模板闸只拦旧 Mini-Plan）")
        assert "执行行动" in plan["content"]
        assert "success_criteria" in plan["content"]
        assert FINDINGS[:100] in plan["content"]
        # 不得再是旧模板的"建议增加 follow-up goal"
        assert "建议增加一个 follow-up goal" not in plan["content"]

    def test_no_findings_no_plan(self):
        rt = _bare_runtime()
        assert rt._build_plan_from_reflection(
            {"source": "deepen_topic", "question": "q"}, "", ":memory:") is None
        assert rt._build_plan_from_reflection(
            {"source": "deepen_topic", "question": "q"}, "太短", ":memory:") is None


class TestRevisitFuel:
    """反思池冷却重考 — 自进化可持续燃料.

    池饥饿实锤 (2026-09-12): 159 条 lesson 全部 consumed、seed 全 used
    → pick_reflect 永 None → 思考结果断供。重考: 24h 冷却期外可再考，
    _revisit 日期盐入键（同日幂等，跨日换键）。
    """

    def test_revisit_pick_after_cooldown(self, tmp_path):
        rt = _bare_runtime()
        db = str(tmp_path / "revisit.db")
        conn = sqlite3.connect(db)
        conn.execute(
            "CREATE TABLE knowledge (statement TEXT, scope_domain TEXT, "
            "created_at TEXT DEFAULT '2026-09-01')")
        conn.execute(
            "CREATE TABLE cognition_consumed (reflection_key TEXT PRIMARY KEY, "
            "source TEXT NOT NULL, consumed_at TEXT NOT NULL, "
            "knowledge_rowid INTEGER, consumed_episode_rowid INTEGER)")
        # 唯一一条 lesson: 2 天前已消费（超出 24h 冷却）
        conn.execute(
            "INSERT INTO knowledge (rowid, statement, scope_domain) "
            "VALUES (10, 'curl 被误诊 dependency_missing 封禁 7 天', 'lesson')")
        conn.execute(
            "INSERT INTO cognition_consumed VALUES "
            "('R:old', 'new_knowledge', datetime('now', '-48 hours'), 10, NULL)")
        # seed 表不存在没关系 — pick_reflect 各分支独立 try/except
        conn.commit()
        conn.close()

        pt = rt._pick_reflection_point(db)
        assert pt is not None, "冷却期外的 lesson 必须可重考（池饥饿回退）"
        assert pt.get("_knowledge_rowid") == 10
        assert pt.get("_revisit"), "重考反思必须带日期盐"

    def test_revisit_salt_changes_key_same_day_idempotent(self):
        rt = _bare_runtime()
        base = {"source": "new_knowledge", "question": "q", "hint": "h",
                "_knowledge_rowid": 10}
        k_fresh = rt._make_consumption_key(dict(base))
        k_rev = rt._make_consumption_key({**base, "_revisit": "2026-09-12"})
        assert k_fresh != k_rev, "重考键必须与新鲜键不同（跨日可再考）"
        k_rev2 = rt._make_consumption_key({**base, "_revisit": "2026-09-12"})
        assert k_rev == k_rev2, "同日重考键必须相同（幂等红线）"
        k_rev3 = rt._make_consumption_key({**base, "_revisit": "2026-09-13"})
        assert k_rev != k_rev3, "跨日重考键必须不同"

    def test_recently_consumed_not_repicked(self, tmp_path):
        rt = _bare_runtime()
        db = str(tmp_path / "revisit2.db")
        conn = sqlite3.connect(db)
        conn.execute(
            "CREATE TABLE knowledge (statement TEXT, scope_domain TEXT, "
            "created_at TEXT DEFAULT '2026-09-01')")
        conn.execute(
            "CREATE TABLE cognition_consumed (reflection_key TEXT PRIMARY KEY, "
            "source TEXT NOT NULL, consumed_at TEXT NOT NULL, "
            "knowledge_rowid INTEGER, consumed_episode_rowid INTEGER)")
        conn.execute(
            "INSERT INTO knowledge (rowid, statement, scope_domain) "
            "VALUES (10, 'curl 被误诊封禁', 'lesson')")
        # 1 小时前消费 — 冷却期内，不得重考
        conn.execute(
            "INSERT INTO cognition_consumed VALUES "
            "('R:old', 'new_knowledge', datetime('now', '-1 hours'), 10, NULL)")
        conn.commit()
        conn.close()

        assert rt._pick_reflection_point(db) is None, (
            "24h 冷却期内的条目不得重考（防重复处理红线）")


class TestPumpToClaimChain:
    """Pump: APPROVED EVO-Plan → goal(origin_level=SELF) → 可认领。"""

    @pytest.fixture()
    def env(self, tmp_path):
        from ocos.evolution.artifacts import (
            EvolutionArtifact, EvolutionArtifactStore, ArtifactType,
        )
        from ocos.goal.store import GoalStore

        db = str(tmp_path / "selfevo.db")
        store = EvolutionArtifactStore(db_path=db)
        GoalStore(db)._conn().close()  # 自愈建 goals 表

        art = EvolutionArtifact.new(
            type=ArtifactType.PLAN,
            title="EVO-Plan: new_knowledge — 重试策略优化",
            summary="[new_knowledge] 深入学习: 重试策略",
            content="# EVO-Plan: 思考结果驱动优化\n\n## 执行行动\n"
                    "1. 调研改进点\n2. 实施变更\n\n## success_criteria\n"
                    "- 变更清单 + 验证命令结果",
            confidence=0.7,
            source_agent="continuous_cognition",
            tags=["cognition_loop", "auto_generated", "self_evolution"],
            risk_level="LOW",
            human_review_required=False,
        )
        store.save(art)
        store.review(art.artifact_id, __import__(
            "ocos.evolution.artifacts", fromlist=["ArtifactStatus"]
        ).ArtifactStatus.APPROVED, reviewer="test", comment="auto")
        return db, store, art.artifact_id

    def test_pump_creates_claimable_self_goal(self, env):
        db, store, aid = env
        rt = _bare_runtime()
        rt._db_path = db

        created = rt._pump_evolution_artifacts(cap=5)
        assert created >= 1, "Pump 必须把 APPROVED EVO-Plan 转成 goal"

        conn = sqlite3.connect(db)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM goals WHERE id LIKE 'EVO-GOAL-%'").fetchone()
        conn.close()
        assert row is not None, "goal 必须落库"
        assert row["origin_level"] == "SELF", (
            "origin_level 必须是 SELF（SYSTEM 永远无人认领 — 271 条 "
            "ABANDONED 根因）")
        assert row["status"] == "PENDING"
        meta = json.loads(row["metadata"])
        assert meta.get("approved") is True, "approved=true = 认领 authority"
        assert meta.get("artifact_id") == aid
        # description 必须携带方案正文（行动+criteria），agent 才能直接执行
        assert "执行行动" in row["description"]
        assert "success_criteria" in row["description"]

    def test_goal_actually_claimable(self, env):
        db, store, aid = env
        rt = _bare_runtime()
        rt._db_path = db
        rt._pump_evolution_artifacts(cap=5)

        from ocos.goal.store import GoalStore
        claimed = GoalStore(db).claim_pending_approved_self(limit=1)
        assert claimed, "SELF+approved goal 必须可被认领（自进化执行入口）"
        assert claimed[0]["id"].startswith("EVO-GOAL-")
        assert "执行行动" in claimed[0].get("description", "")

    def test_legacy_miniplan_still_blocked(self, env):
        db, store, _aid = env
        # 存量旧模板 artifact
        from ocos.evolution.artifacts import (
            EvolutionArtifact, ArtifactType,
        )
        import ocos.evolution.artifacts as _am
        legacy = EvolutionArtifact.new(
            type=ArtifactType.PLAN,
            title="Mini-Plan: deepen_topic — 深入学习: 旧模板",
            summary="[deepen_topic] 深入学习: 旧模板",
            content="# Mini-Plan: 来自持续认知循环\n\n## 建议行动\n"
                    "1. 基于以上分析, 增加一个 follow-up goal 深入探索",
            confidence=0.6,
            source_agent="continuous_cognition",
            tags=["cognition_loop", "auto_generated", "mini_plan"],
            risk_level="LOW",
            human_review_required=True,
        )
        store.save(legacy)
        store.review(legacy.artifact_id, _am.ArtifactStatus.APPROVED,
                     reviewer="test", comment="legacy")

        rt = _bare_runtime()
        rt._db_path = db
        rt._pump_evolution_artifacts(cap=5)

        conn = sqlite3.connect(db)
        n = conn.execute(
            "SELECT COUNT(*) FROM goals WHERE description LIKE '%旧模板%'"
        ).fetchone()[0]
        conn.close()
        assert n == 0, "旧模板 Mini-Plan 必须仍被拦截（防 goal 洪流）"
