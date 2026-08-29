"""Phase 30 — E2E Test 1: 复杂任务端到端。

验证链路:
  Goal Intelligence → Goal Tree → Planning → Agent Orchestration → Digital World
"""

import pytest
from ocos.goal.models import GoalDomain, GoalSource, UserGoal, SuccessCriteria
from ocos.goal.tree import GoalTree
from ocos.planning.decomposer import TaskDecomposer
from ocos.planning.models import ExecutionStrategy, Plan
from ocos.planning.strategy import StrategyEngine
from ocos.planning.simulator import PlanSimulator
from ocos.planning.plan_validator import validate_plan
from ocos.agent_orchestration.registry import AgentDescriptor, AgentRegistry
from ocos.agent_orchestration.selector import AgentSelector
from ocos.agent_orchestration.supervisor import ExecutionSupervisor
from ocos.digital_world.base import DigitalOperation, OperationResult
from ocos.digital_world.auditor import OperationAuditor


# ── 30-E1: Complex task end-to-end ────────────────────────────────

@pytest.mark.asyncio
async def test_e2e_complex_novel_task():
    """Goal → GoalTree → Plan → Simulate → Execute → Audit。"""
    # ── Step 1: Goal Intelligence ──
    goal = UserGoal(
        id="G-E2E-1",
        raw_input="创建一本5万字的商业科幻小说，主角是AI工程师，主题是人机关系",
        objective="创建一本5万字的商业科幻小说",
        domain=GoalDomain.WRITING,
        constraints=("5万字", "主角AI工程师", "主题人机关系"),
        source=GoalSource.HUMAN,
        caller="orchestrator",
        success_criteria=(
            SuccessCriteria(description="word_count >= 50000", measurable=True, threshold="50000"),
            SuccessCriteria(description="genre is sci-fi", measurable=False),
        ),
    )
    assert goal.source == GoalSource.HUMAN
    assert goal.domain == GoalDomain.WRITING
    assert len(goal.constraints) == 3

    # ── Step 2: Goal Tree ──
    tree = GoalTree(root=goal)
    child1 = UserGoal(id="G-E2E-1-1", raw_input="写大纲", objective="写大纲",
                      domain=GoalDomain.WRITING, source=GoalSource.DECOMPOSED,
                      parent_id="G-E2E-1", caller="orchestrator")
    child2 = UserGoal(id="G-E2E-1-2", raw_input="写正文", objective="写正文",
                      domain=GoalDomain.WRITING, source=GoalSource.DECOMPOSED,
                      parent_id="G-E2E-1", caller="orchestrator")
    tree.add_child("G-E2E-1", child1)
    tree.add_child("G-E2E-1", child2)
    assert tree.children["G-E2E-1"][0].source == GoalSource.DECOMPOSED
    assert len(tree.get_leaves()) >= 2

    # ── Step 3: Planning ──
    dag = TaskDecomposer.decompose(goal)
    assert len(dag.tasks) >= 3
    order = dag.topological_order()
    first_desc = dag.tasks[order[0]].description
    assert "大纲" in first_desc

    # ── Step 4: Strategy ──
    strategy = StrategyEngine.select(dag)
    assert strategy in (ExecutionStrategy.SEQUENTIAL, ExecutionStrategy.PRIORITY_DRIVEN)

    # ── Step 5: Simulate ──
    plan = Plan(plan_id="P-E2E-1", goal_id="G-E2E-1",
                dag=dag, strategy=strategy, estimated_total_duration=1800)
    sim_result = PlanSimulator.simulate(plan)
    assert sim_result.success
    assert not sim_result.deadlock_detected

    # ── Step 6: Validate ──
    ok, reason = validate_plan(plan)
    assert ok, reason

    # ── Step 7: Agent Orchestration ──
    registry = AgentRegistry()
    registry.register(AgentDescriptor(agent_id="writer-1", agent_type="writer",
                                      capabilities=("generation", "modification")))
    registry.register(AgentDescriptor(agent_id="reviewer-1", agent_type="reviewer",
                                      capabilities=("analysis", "verification")))
    selector = AgentSelector(registry)
    supervisor = ExecutionSupervisor(registry=registry, selector=selector)
    records = await supervisor.execute_plan(plan)
    assert len(records) > 0
    for r in records:
        assert r.status == "completed", f"Task {r.contract_id} {r.status}: {r.error}"

    # ── Step 8: Audit — Digital World ──
    auditor = OperationAuditor()
    op = DigitalOperation.create("file_write", "/tmp/novel_output.md", "G-E2E-1",
                                 params={"content": "novel draft"}, approval_id="APPROVED-1")
    result = OperationResult.success(op.op_id, "wrote 50000 bytes")
    audit = auditor.record(op, result)
    assert audit.op_type == "file_write"
    assert audit.status == "success"
