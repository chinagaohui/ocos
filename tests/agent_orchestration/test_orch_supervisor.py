"""Phase 28+22 — Gate Tests: ExecutionSupervisor (async)。

验证:
  28-V01: execute_task success (async)
  28-V02: execute_plan sequential (async)
  28-V03: execute_plan with failure stops downstream
  28-V04: cancel execution (async)
  28-V05: no available agent → failure record
  28-V06: audit trail populated
  22-D01: sync wrappers available for backward compat
"""

import pytest
from ocos.agent_orchestration.registry import AgentDescriptor, AgentRegistry
from ocos.agent_orchestration.selector import AgentSelector
from ocos.agent_orchestration.audit import ExecutionAudit
from ocos.agent_orchestration.fallback import FallbackHandler
from ocos.agent_orchestration.supervisor import ExecutionSupervisor
from ocos.planning.models import Task, TaskDAG, ExecutionStrategy, Plan


@pytest.fixture
def supervisor() -> ExecutionSupervisor:
    r = AgentRegistry()
    r.register(AgentDescriptor(agent_id="A1", agent_type="writer",
                                capabilities=("generation", "modification"),
                                success_rate=0.95))
    r.register(AgentDescriptor(agent_id="A2", agent_type="reviewer",
                                capabilities=("analysis", "verification"),
                                success_rate=0.90))
    r.register(AgentDescriptor(agent_id="A3", agent_type="writer",
                                capabilities=("generation",),
                                success_rate=0.70))

    class _StubExecutor:
        """AUD-F11: 回退执行器已改诚实失败 — 注入 stub 才能测 completed 路径。"""
        def execute(self, contract):
            return True, f"executed {contract.task_id}", None

    return ExecutionSupervisor(
        registry=r,
        selector=AgentSelector(r),
        executor=_StubExecutor(),
    )


# ── 28-V01: execute_task success ─────────────────────────────────

@pytest.mark.asyncio
async def test_execute_task_success(supervisor):
    task = Task(id="T1", goal_id="G1", description="test",
                task_type="create", agent_type="writer")
    record = await supervisor.execute_task(task)
    assert record.status == "completed"
    assert supervisor.registry.get_available("writer") is not None


# ── 28-V02: execute_plan sequential ──────────────────────────────

@pytest.mark.asyncio
async def test_execute_plan_sequential(supervisor):
    dag = TaskDAG()
    dag.add_task(Task(id="T1", goal_id="G1", description="outline",
                      task_type="create", agent_type="writer"))
    dag.add_task(Task(id="T2", goal_id="G1", description="chapter1",
                      task_type="create", agent_type="writer"))
    dag.add_edge("T1", "T2")
    plan = Plan(plan_id="P1", goal_id="G1", dag=dag,
                strategy=ExecutionStrategy.SEQUENTIAL,
                estimated_total_duration=600)
    records = await supervisor.execute_plan(plan)
    assert len(records) == 2
    assert all(r.status == "completed" for r in records)


# ── 28-V03: no available agent ───────────────────────────────────

@pytest.mark.asyncio
async def test_no_available_agent():
    r = AgentRegistry()
    r.register(AgentDescriptor(agent_id="A1", agent_type="reviewer",
                                capabilities=("analysis",)))
    sup = ExecutionSupervisor(registry=r, selector=AgentSelector(r))
    task = Task(id="T1", goal_id="G1", description="test",
                task_type="create", agent_type="writer")
    record = await sup.execute_task(task)
    assert record.status == "failed"


# ── 28-V04: cancel execution ─────────────────────────────────────

@pytest.mark.asyncio
async def test_cancel_execution(supervisor):
    task = Task(id="T1", goal_id="G1", description="test",
                task_type="create", agent_type="writer")
    await supervisor.execute_task(task)
    assert await supervisor.cancel("nonexistent") is False


@pytest.mark.asyncio
async def test_cancel_active_contract(supervisor):
    from ocos.agent_orchestration.contract import ExecutionContract
    c = ExecutionContract.create(task_id="T1", agent_id="A1")
    supervisor._active_contracts[c.contract_id] = c
    assert await supervisor.cancel(c.contract_id) is True
    assert c.contract_id not in supervisor._active_contracts


# ── 28-V05: audit trail populated ────────────────────────────────

@pytest.mark.asyncio
async def test_audit_trail_populated(supervisor):
    task = Task(id="T1", goal_id="G1", description="test",
                task_type="create", agent_type="writer")
    await supervisor.execute_task(task)
    assert len(supervisor.audit) >= 2  # at least start + complete


# ── 28-V06: _execute_agent is opaque ─────────────────────────────

def test_agent_fn_is_callable():
    from ocos.agent_orchestration.supervisor import _execute_agent
    from ocos.agent_orchestration.contract import ExecutionContract
    c = ExecutionContract.create(task_id="T1", agent_id="A1")
    ok, result = _execute_agent("A1", c)
    # AUD-F11: 回退行为 = 诚实失败（无 AgentExecutor 注入 → 任务未执行）
    assert not ok
    assert "NOT executed" in result


# ── 22-D01: sync wrappers ────────────────────────────────────────

def test_sync_wrapper_task(supervisor):
    """execute_task_sync 作为向后兼容包装器。"""
    task = Task(id="T1", goal_id="G1", description="sync wrap",
                task_type="create", agent_type="writer")
    record = supervisor.execute_task_sync(task)
    assert record.status == "completed"


def test_sync_wrapper_cancel(supervisor):
    """cancel_sync 作为向后兼容包装器。"""
    assert supervisor.cancel_sync("nonexistent") is False
