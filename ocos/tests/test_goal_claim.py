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
        rt._user_inbox = None   # 认领 progress 出站通道（2026-09-08 可见性）
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


def _save_approved_self_goal(db: str, gid: str = "GOAL-AUTO-test1",
                             approved: bool = True) -> None:
    """模拟 autonomous_goal_sink 落库（approvals.py / factory.py 同款）。"""
    from ocos.goal.store import GoalStore
    GoalStore(db_path=db).save(
        goal_id=gid, level="TASK", status="PENDING",
        description="只读探测：验证信念", source="autonomous",
        metadata={"autonomous": True, "kind": "probe",
                  "approved": approved},
        origin_level="SELF", authority="AUTONOMOUS")


class TestClaimApprovedSelfGoals:
    """V1 闭环最后一环 — 批准后的自主目标（SELF/PENDING）必须可认领。

    缺陷史: 此前唯一认领通道 claim_pending_human 只认 origin_level='HUMAN'，
    autonomous_goal_sink 落库的 SELF 目标永久滞留 PENDING（生产 5 条实证）。
    """

    def test_approved_self_goal_claimable(self, db):
        from ocos.goal.store import GoalStore
        _save_approved_self_goal(db)
        store = GoalStore(db_path=db)
        claimed = store.claim_pending_approved_self(limit=1)
        assert len(claimed) == 1
        assert claimed[0]["id"] == "GOAL-AUTO-test1"
        # 原子性 — 二次认领为空
        assert store.claim_pending_approved_self(limit=1) == []
        assert store.load("GOAL-AUTO-test1")["status"] == "ACTIVE"

    def test_unapproved_self_goal_not_claimable(self, db):
        from ocos.goal.store import GoalStore
        _save_approved_self_goal(db, "GOAL-AUTO-nope", approved=False)
        store = GoalStore(db_path=db)
        assert store.claim_pending_approved_self(limit=1) == []
        assert store.load("GOAL-AUTO-nope")["status"] == "PENDING"

    def test_human_claim_untouched_by_self_channel(self, db):
        from ocos.goal.store import GoalStore
        _create_goal_via_store(db)
        store = GoalStore(db_path=db)
        assert store.claim_pending_approved_self(limit=1) == []
        assert len(store.claim_pending_human(limit=1)) == 1

    def test_daemon_claims_self_goal_at_level1(self, db, monkeypatch):
        """daemon 认领链: LEVEL>=1 时 SELF 目标经 fallback 认领入 runtime。"""
        import types
        _save_approved_self_goal(db)
        # 钉死级别=1（覆盖文件优先级最高 — 隔离宿主机 ~/.ocos/autonomy_level）
        override = db + ".level"
        with open(override, "w") as f:
            f.write("1")
        monkeypatch.setenv("OCOS_AUTONOMY_OVERRIDE", override)

        from ocos.daemon import ResidentRuntime
        from ocos.agent.goal_store import GoalSQLiteStore
        rt = ResidentRuntime.__new__(ResidentRuntime)
        rt._runtime = types.SimpleNamespace(_goal_store=GoalSQLiteStore(db))
        rt._runtime._goal_store.initialize()
        rt._goal_store = rt._runtime._goal_store
        rt._goal_processed = 0
        rt._autonomous_inflight = []
        rt._user_inbox = None   # 认领 progress 出站通道（2026-09-08 可见性）
        rt._domain_goal_store = __import__(
            "ocos.goal.store", fromlist=["GoalStore"]).GoalStore(db_path=db)

        n = rt._claim_persisted_goals()
        assert n == 1
        assert rt._goal_processed == 1
        # autonomous 目标入在途队列（防跑飞配对）
        assert "GOAL-AUTO-test1" in rt._autonomous_inflight
        assert rt._goal_store.load("GOAL-AUTO-test1") is not None

    def test_daemon_skips_self_goal_at_level0(self, db, monkeypatch):
        """LEVEL=0 = 只执行用户目标 — 批准过的 SELF 目标也不认领。"""
        import types
        _save_approved_self_goal(db)
        override = db + ".level0"
        with open(override, "w") as f:
            f.write("0")
        monkeypatch.setenv("OCOS_AUTONOMY_OVERRIDE", override)

        from ocos.daemon import ResidentRuntime
        from ocos.agent.goal_store import GoalSQLiteStore
        rt = ResidentRuntime.__new__(ResidentRuntime)
        rt._runtime = types.SimpleNamespace(_goal_store=GoalSQLiteStore(db))
        rt._runtime._goal_store.initialize()
        rt._goal_store = rt._runtime._goal_store
        rt._goal_processed = 0
        rt._autonomous_inflight = []
        rt._user_inbox = None   # 认领 progress 出站通道（2026-09-08 可见性）
        rt._domain_goal_store = __import__(
            "ocos.goal.store", fromlist=["GoalStore"]).GoalStore(db_path=db)

        assert rt._claim_persisted_goals() == 0
        assert rt._goal_store.load("GOAL-AUTO-test1") is None
        assert rt._domain_goal_store.load("GOAL-AUTO-test1")["status"] == "PENDING"

    def test_daemon_claims_unapproved_self_goal_at_level2(self, db, monkeypatch):
        """LEVEL=2 低风险自主执行 — goals_table 直写提案（无 approved
        标记）可直接认领，无需批准环节。"""
        import types
        from ocos.goal.store import GoalStore
        # 模拟 motivation._propose LEVEL>=2 直写（metadata 无 approved 键）
        GoalStore(db_path=db).save(
            goal_id="GOAL-AUTO-lv2", level="TASK", status="PENDING",
            description="只读探测：宿主机", source="autonomous",
            metadata={"autonomous": True, "kind": "probe", "score": 0.9},
            origin_level="SELF", authority="AUTONOMOUS")
        override = db + ".level2"
        with open(override, "w") as f:
            f.write("2")
        monkeypatch.setenv("OCOS_AUTONOMY_OVERRIDE", override)

        from ocos.daemon import ResidentRuntime
        from ocos.agent.goal_store import GoalSQLiteStore
        rt = ResidentRuntime.__new__(ResidentRuntime)
        rt._runtime = types.SimpleNamespace(_goal_store=GoalSQLiteStore(db))
        rt._runtime._goal_store.initialize()
        rt._goal_store = rt._runtime._goal_store
        rt._goal_processed = 0
        rt._autonomous_inflight = []
        rt._user_inbox = None   # 认领 progress 出站通道（2026-09-08 可见性）
        rt._domain_goal_store = __import__(
            "ocos.goal.store", fromlist=["GoalStore"]).GoalStore(db_path=db)

        assert rt._claim_persisted_goals() == 1
        assert "GOAL-AUTO-lv2" in rt._autonomous_inflight


class TestAutoApprovalPump:
    """全自动模式（OCOS_APPROVAL_MODE=auto）: daemon 每 tick 清空待批队列。

    用户决策 2026-09-07: 个人使用不审批、全自动通过。泵走与人工批准
    同一条溯源通道（decide(decided_by=auto) → execute_approved →
    mark_executed），ask 模式下零开销空转。
    """

    def _make_daemon(self, db: str):
        import types
        from ocos.execution.bridge import DecisionBridge
        from ocos.execution.pending import PendingStore
        from ocos.daemon import ResidentRuntime

        store = PendingStore(db_path=db)
        sunk: list[dict] = []
        bridge = DecisionBridge(
            pending_store=store, db_path=db,
            autonomous_goal_sink=lambda p: sunk.append(p))
        bridge.attach_default_handlers()

        rt = ResidentRuntime.__new__(ResidentRuntime)
        rt._runtime = types.SimpleNamespace(_decision_bridge=bridge)
        return rt, store, sunk

    def test_pump_auto_approves_and_executes(self, db, monkeypatch):
        monkeypatch.setenv("OCOS_APPROVAL_MODE", "auto")
        rt, store, sunk = self._make_daemon(db)
        pid = store.enqueue(
            action_type="autonomous_goal", target="autonomous_goal",
            payload={"goal_id": "GOAL-AUTO-pump1",
                     "description": "只读探测：泵验证", "kind": "probe"},
            text="自主目标提案", source="motivation")

        n = rt._auto_approve_pending()
        assert n == 1
        row = store.get(pid)
        assert row["status"] == "executed"
        assert row["decided_by"] == "auto"
        # autonomous_goal sink 被真实调用 → 目标落库（后续由认领通道消费）
        assert sunk and sunk[0]["goal_id"] == "GOAL-AUTO-pump1"

    def test_pump_noop_in_ask_mode(self, db, monkeypatch):
        monkeypatch.setenv("OCOS_APPROVAL_MODE", "ask")
        rt, store, sunk = self._make_daemon(db)
        store.enqueue(action_type="autonomous_goal", target="",
                      payload={"goal_id": "G1", "description": "x"})
        assert rt._auto_approve_pending() == 0
        assert sunk == []
        assert store.list_by_status("pending")

    def test_pump_marks_blocked_honestly(self, db, monkeypatch):
        """无执行器的动作类型 → approved 但 blocked（诚实记录，不假装成功）。"""
        monkeypatch.setenv("OCOS_APPROVAL_MODE", "auto")
        rt, store, _sunk = self._make_daemon(db)
        pid = store.enqueue(action_type="no_such_handler", target="",
                            payload={})
        rt._auto_approve_pending()
        row = store.get(pid)
        assert row["status"] == "blocked"
        assert row["decided_by"] == "auto"
