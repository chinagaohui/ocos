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

    def test_mark_completed_closes_domain_goal(self, db):
        """P1: 域层 goals 表闭环 — ACTIVE → COMPLETED 可推进, 终止态不倒退。"""
        from ocos.goal.store import GoalStore
        gid = _create_goal_via_store(db)
        store = GoalStore(db_path=db)
        store.claim_pending_human(limit=1)
        assert store.load(gid) is not None
        assert store.load(gid)["status"] == "ACTIVE"
        # 完成推进
        assert store.mark_completed(gid) is True
        row = store.load(gid)
        assert row is not None
        assert row["status"] == "COMPLETED"
        assert row["progress"] == 1.0
        # 幂等 + 终止态不倒退
        assert store.mark_completed(gid) is False
        assert store.load(gid) is not None
        assert store.load(gid)["status"] == "COMPLETED"
        # 不存在的 id 返回 False
        assert store.mark_completed("GOAL-nope") is False

    def test_runtime_completion_syncs_domain_goal(self, db):
        """P1 集成: agent 层完成块 → 域层 goals 表同步 COMPLETED。

        认领路径 (daemon._claim_persisted_goals) 置域层 ACTIVE 并导入
        agent 层 goal 表 (同 id); DAG 执行完毕 agent_runtime 完成块
        更新 agent 层后必须同步域层, 否则目标永久卡 ACTIVE。
        """
        from ocos.goal.store import GoalStore
        gid = _create_goal_via_store(db)
        store = GoalStore(db_path=db)
        store.claim_pending_human(limit=1)

        from ocos.agent.goal_store import GoalSQLiteStore
        from ocos.agent.agent_runtime import AgentRuntime
        from ocos.kernel.goal_types import Goal, GoalStatus, GoalDomain
        rt = AgentRuntime.__new__(AgentRuntime)
        rt._goal_store = GoalSQLiteStore(db)
        rt._goal_store.initialize()
        # 模拟 daemon._import_goal 的 agent 层写入 (同 id, ACTIVE)
        rt._goal_store.save(Goal(
            goal_id=gid, description="设计秒杀系统",
            status=GoalStatus.ACTIVE, domain=GoalDomain.DEVELOPMENT))
        rt._db_path = db
        rt._active_dag_goal_id = gid
        rt._active_dag = None
        rt._dag_cursor = 0
        rt._dag_total = 0
        rt._recent_results = []
        rt._memory_hub = None

        # 执行完成块同款逻辑 (DAG exhausted 分支的核心动作)
        from ocos.kernel.goal_types import GoalStatus as _GS
        _g = rt._goal_store.load(gid)
        assert _g.status.name == "ACTIVE"
        _g.status = _GS.COMPLETED
        rt._goal_store.save(_g)
        # 域层同步 (agent_runtime 完成块新增逻辑)
        GoalStore(db_path=db).mark_completed(gid)

        # 双表闭环验证
        assert rt._goal_store.load(gid).status.name == "COMPLETED"
        row = store.load(gid)
        assert row is not None
        assert row["status"] == "COMPLETED"
        # 域层 load_active 不再返回该目标
        assert all(g["id"] != gid for g in store.load_active())

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
