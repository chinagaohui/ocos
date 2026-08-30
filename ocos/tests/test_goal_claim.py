"""UX-1: 目标认领机制测试 — CLI 创建的 goal 能被 daemon 认领并进入 runtime。"""

from __future__ import annotations

import json
import sqlite3

import pytest


@pytest.fixture
def db(tmp_path, monkeypatch):
    path = str(tmp_path / "claim.db")
    monkeypatch.setenv("OCOS_DB_PATH", path)
    return path


def _create_goal_via_store(db: str) -> str:
    """模拟 CLI goal create 的落库动作。"""
    from ocos.goal.store import GoalStore
    store = GoalStore(db_path=db)
    store.save(
        goal_id="GOAL-claimtest1", level="USER", status="PENDING",
        description="设计秒杀系统", priority=3.0, source="cli",
        origin_level="HUMAN", authority="FRAMEWORK",
        metadata={"domain": "development"},
    )
    return "GOAL-claimtest1"


class TestClaimMechanism:
    def test_claim_marks_active_and_returns_row(self, db):
        from ocos.goal.store import GoalStore
        gid = _create_goal_via_store(db)
        store = GoalStore(db_path=db)
        claimed = store.claim_pending_human(limit=1)
        assert len(claimed) == 1
        assert claimed[0]["id"] == gid
        meta = claimed[0]["metadata"]
        meta = json.loads(meta) if isinstance(meta, str) else meta
        assert meta["domain"] == "development"
        # 状态置 ACTIVE — 二次认领为空
        assert store.claim_pending_human(limit=1) == []

    def test_claim_ignores_system_and_non_pending(self, db):
        from ocos.goal.store import GoalStore
        store = GoalStore(db_path=db)
        store.save(goal_id="G-sys", level="USER", status="PENDING",
                   description="sys", source="runtime", origin_level="SYSTEM")
        store.save(goal_id="G-done", level="USER", status="COMPLETED",
                   description="done", source="cli", origin_level="HUMAN")
        assert store.claim_pending_human(limit=5) == []

    def test_daemon_claim_imports_into_runtime(self, db):
        """daemon._claim_persisted_goals → runtime goal 表出现同 id 目标。"""
        _create_goal_via_store(db)

        from ocos.agent.agent_runtime import AgentRuntime
        from ocos.daemon import ResidentRuntime
        rt = ResidentRuntime.__new__(ResidentRuntime)
        # 最小可运行装配（绕过完整 __init__，聚焦认领逻辑）
        import types
        from ocos.agent.goal_store import GoalSQLiteStore
        rt._runtime = types.SimpleNamespace(
            _goal_store=GoalSQLiteStore(db))
        rt._runtime._goal_store.initialize()
        rt._goal_store = rt._runtime._goal_store
        rt._goal_processed = 0
        rt._domain_goal_store = __import__(
            "ocos.goal.store", fromlist=["GoalStore"]).GoalStore(db_path=db)

        n = rt._claim_persisted_goals()
        assert n == 1
        assert rt._goal_processed == 1

        row = rt._goal_store.load("GOAL-claimtest1")
        assert row is not None
        from ocos.kernel.goal_types import GoalDomain
        assert row.domain == GoalDomain.DEVELOPMENT

    def test_runtime_step6_uses_claimed_domain(self, db):
        """Step 6 分解时 domain 跟随目标（非硬编码 WRITING）。"""
        from ocos.agent.agent_runtime import AgentRuntime
        from ocos.agent.goal_store import GoalSQLiteStore
        from ocos.kernel.goal_types import Goal, GoalDomain, GoalStatus

        runtime = AgentRuntime.__new__(AgentRuntime)
        runtime._goal_store = GoalSQLiteStore(db)
        runtime._goal_store.initialize()
        g = Goal(goal_id="GOAL-dev1", description="设计秒杀系统",
                 domain=GoalDomain.DEVELOPMENT)
        runtime._goal_store.save(g)

        # 直接构造最小 tick 上下文（Step 6 只需要 attention report 为 None 的路径）
        for attr in ("_active_dag", "_last_attention_decisions",
                     "_attention_report", "_goal_processed"):
            try:
                setattr(runtime, attr, None)
            except AttributeError:
                pass
        result = runtime._tick_step_planning_trigger()
        assert result["decomposed"] == 1
        assert runtime._active_dag is not None
        # development 模板: 设计架构(create)/实现代码(execute)/测试验证(verify)
        descs = [t.description for t in runtime._active_dag.tasks.values()]
        assert any("设计架构" in d for d in descs)
