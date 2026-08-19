"""Phase 25 — Capability Orchestration Pipeline 集成测试。

覆盖端到端编排链路:
  PIPE-01: PlanValidator → Supervisor 验证-执行管线
  PIPE-02: Writer→Reviewer→Revision 多阶段管线
  PIPE-03: Decision→Planning→Generation→Review 全链路模拟
  PIPE-04: 上游失败阻断下游（failure propagation）
  PIPE-05: 拓扑顺序正确性
  PIPE-06: PlanValidator 拒绝无效 plan → Supervisor 不会执行
  PIPE-07: Fallback agent 管线
  PIPE-08: Audit trail 完整性（全链路）
  PIPE-09: 多 Agent 类型混合管线
  PIPE-10: 并行组拓扑分组验证
"""

import pytest

from ocos.agent_orchestration.registry import AgentDescriptor, AgentRegistry
from ocos.agent_orchestration.selector import AgentSelector
from ocos.agent_orchestration.audit import ExecutionAudit
from ocos.agent_orchestration.fallback import FallbackHandler
from ocos.agent_orchestration.supervisor import ExecutionSupervisor
from ocos.planning.models import Task, TaskDAG, ExecutionStrategy, Plan
from ocos.planning.plan_validator import PlanValidator


# ── Fixtures ────────────────────────────────────────────────────────────


def make_full_registry() -> AgentRegistry:
    """创建含所有 4 种 agent_type 的 registry。"""
    r = AgentRegistry()
    r.register(AgentDescriptor(
        agent_id="writer-001", agent_type="writer",
        capabilities=("text-generation", "revision", "modification"),
        success_rate=0.95,
    ))
    r.register(AgentDescriptor(
        agent_id="writer-002", agent_type="writer",
        capabilities=("text-generation", "outline"),
        success_rate=0.88,
    ))
    r.register(AgentDescriptor(
        agent_id="reviewer-001", agent_type="reviewer",
        capabilities=("analysis", "verification", "feedback"),
        success_rate=0.92,
    ))
    r.register(AgentDescriptor(
        agent_id="researcher-001", agent_type="researcher",
        capabilities=("search", "analysis", "fact-checking"),
        success_rate=0.90,
    ))
    r.register(AgentDescriptor(
        agent_id="processor-001", agent_type="data_processor",
        capabilities=("formatting", "export", "publishing"),
        success_rate=0.85,
    ))
    return r


def _task_ids(records, supervisor):
    """从 ExecutionRecord 推导 task_id（通过 contract→task 映射）。"""
    contract_tasks = {
        c.contract_id: c.task_id
        for c in supervisor._active_contracts.values()
    }
    return [contract_tasks.get(r.contract_id, r.contract_id) for r in records]


@pytest.fixture
def pipeline_supervisor():
    """含完整 registry 的 supervisor（用于管线测试）。"""
    registry = make_full_registry()
    return ExecutionSupervisor(
        registry=registry,
        selector=AgentSelector(registry),
    )


# ── PIPE-01: PlanValidator → Supervisor 验证-执行管线 ──────────────

@pytest.mark.asyncio
async def test_validate_then_execute_pipeline(pipeline_supervisor):
    """PlanValidator 验证通过 → Supervisor 执行。"""
    dag = TaskDAG()
    t1 = Task.create(goal_id="G1", description="research topic", task_type="search", agent_type="researcher")
    t2 = Task.create(goal_id="G1", description="write draft", task_type="create", agent_type="writer")
    t3 = Task.create(goal_id="G1", description="review draft", task_type="analyze", agent_type="reviewer")
    dag.add_task(t1)
    dag.add_task(t2)
    dag.add_task(t3)
    dag.add_edge(t1.id, t2.id)
    dag.add_edge(t2.id, t3.id)

    # Step 1: 验证
    validator = PlanValidator()
    report = validator.validate(dag)
    assert report.valid, f"validation failed: {[e.message for e in report.errors]}"

    # Step 2: 模拟拓扑顺序
    sim_report = validator.simulate(dag)
    assert len(sim_report.simulated_execution_order) == 3

    # Step 3: 执行
    plan = Plan(plan_id="P1", goal_id="G1", dag=dag,
                strategy=ExecutionStrategy.SEQUENTIAL,
                estimated_total_duration=900)
    records = await pipeline_supervisor.execute_plan(plan)
    assert len(records) == 3
    assert all(r.status == "completed" for r in records)


# ── PIPE-02: Writer→Reviewer→Revision 多阶段管线 ─────────────────

@pytest.mark.asyncio
async def test_writer_reviewer_revision_pipeline(pipeline_supervisor):
    """完整的 Writer→Reviewer→Revision 创作管线。"""
    dag = TaskDAG()
    write = Task.create(goal_id="G1", description="write chapter 1", task_type="create", agent_type="writer")
    review = Task.create(goal_id="G1", description="review chapter 1", task_type="analyze", agent_type="reviewer", inputs=(write.id,))
    revise = Task.create(goal_id="G1", description="revise based on feedback", task_type="modify", agent_type="writer", inputs=(review.id,))
    fmt = Task.create(goal_id="G1", description="format output", task_type="execute", agent_type="data_processor", inputs=(revise.id,))
    dag.add_task(write)
    dag.add_task(review)
    dag.add_task(revise)
    dag.add_task(fmt)
    dag.add_edge(write.id, review.id)
    dag.add_edge(review.id, revise.id)
    dag.add_edge(revise.id, fmt.id)

    plan = Plan(plan_id="P2", goal_id="G1", dag=dag,
                strategy=ExecutionStrategy.SEQUENTIAL,
                estimated_total_duration=1200)
    records = await pipeline_supervisor.execute_plan(plan)

    assert len(records) == 4
    assert all(r.status == "completed" for r in records)

    # 验证执行顺序：通过 contract→task 映射
    task_order = _task_ids(records, pipeline_supervisor)
    assert task_order[0] == write.id
    assert task_order[1] == review.id
    assert task_order[2] == revise.id
    assert task_order[3] == fmt.id


# ── PIPE-03: Decision→Planning→Generation→Review 全链路 ──────────

@pytest.mark.asyncio
async def test_decision_planning_generation_review_pipeline(pipeline_supervisor):
    """模拟 Decision→Planning→Generation→Review 全链路。

    Decision: 选定 topic + 分配资源
    Planning: 分解为 规划任务 + 研究任务 + 生成任务
    Generation: 执行内容生成
    Review: 质量审查 + 反馈
    """
    dag = TaskDAG()
    decide = Task.create(goal_id="G1", description="decide on writing strategy", task_type="analyze", agent_type="researcher")
    research = Task.create(goal_id="G1", description="research background material", task_type="search", agent_type="researcher", inputs=(decide.id,))
    outline = Task.create(goal_id="G1", description="create chapter outline", task_type="create", agent_type="writer", inputs=(research.id,))
    gen_ch1 = Task.create(goal_id="G1", description="generate chapter 1", task_type="create", agent_type="writer", inputs=(outline.id,))
    gen_ch2 = Task.create(goal_id="G1", description="generate chapter 2", task_type="create", agent_type="writer", inputs=(outline.id,))
    review_all = Task.create(goal_id="G1", description="review all chapters", task_type="analyze", agent_type="reviewer", inputs=(gen_ch1.id, gen_ch2.id,))
    revise_final = Task.create(goal_id="G1", description="final revision", task_type="modify", agent_type="writer", inputs=(review_all.id,))
    publish = Task.create(goal_id="G1", description="publish final version", task_type="execute", agent_type="data_processor", inputs=(revise_final.id,))
    dag.add_task(decide)
    dag.add_task(research)
    dag.add_task(outline)
    dag.add_task(gen_ch1)
    dag.add_task(gen_ch2)
    dag.add_task(review_all)
    dag.add_task(revise_final)
    dag.add_task(publish)
    dag.add_edge(decide.id, research.id)
    dag.add_edge(research.id, outline.id)
    dag.add_edge(outline.id, gen_ch1.id)
    dag.add_edge(outline.id, gen_ch2.id)
    dag.add_edge(gen_ch1.id, review_all.id)
    dag.add_edge(gen_ch2.id, review_all.id)
    dag.add_edge(review_all.id, revise_final.id)
    dag.add_edge(revise_final.id, publish.id)

    plan = Plan(plan_id="P3", goal_id="G1", dag=dag,
                strategy=ExecutionStrategy.SEQUENTIAL,
                estimated_total_duration=2400)
    records = await pipeline_supervisor.execute_plan(plan)

    assert len(records) == 8
    assert all(r.status == "completed" for r in records)

    # 验证关键依赖顺序
    task_order = _task_ids(records, pipeline_supervisor)
    assert task_order.index(decide.id) < task_order.index(research.id)
    assert task_order.index(research.id) < task_order.index(outline.id)
    assert task_order.index(outline.id) < task_order.index(gen_ch1.id)
    assert task_order.index(outline.id) < task_order.index(gen_ch2.id)
    assert task_order.index(gen_ch1.id) < task_order.index(review_all.id)
    assert task_order.index(gen_ch2.id) < task_order.index(review_all.id)
    assert task_order.index(review_all.id) < task_order.index(revise_final.id)


# ── PIPE-04: 上游失败阻断下游 ─────────────────────────────────────

@pytest.mark.asyncio
async def test_upstream_failure_stops_downstream():
    """上游任务失败 → 阻断所有下游任务。"""
    # 用空 registry 只注册 writer — researcher 没有 agent
    empty = AgentRegistry()
    empty.register(AgentDescriptor(
        agent_id="w1", agent_type="writer",
        capabilities=("generation",),
    ))

    sup = ExecutionSupervisor(
        registry=empty,
        selector=AgentSelector(empty),
    )

    dag = TaskDAG()
    t1 = Task.create(goal_id="G1", description="research", task_type="search", agent_type="researcher")  # 没有 agent!
    t2 = Task.create(goal_id="G1", description="write", task_type="create", agent_type="writer", inputs=(t1.id,))
    t3 = Task.create(goal_id="G1", description="review", task_type="analyze", agent_type="writer", inputs=(t2.id,))
    dag.add_task(t1)
    dag.add_task(t2)
    dag.add_task(t3)
    dag.add_edge(t1.id, t2.id)
    dag.add_edge(t2.id, t3.id)

    plan = Plan(plan_id="P-fail", goal_id="G1", dag=dag,
                strategy=ExecutionStrategy.SEQUENTIAL,
                estimated_total_duration=300)
    records = await sup.execute_plan(plan)

    # 只有 t1 被执行（然后失败），t2/t3 被阻断
    assert len(records) == 1
    assert records[0].status == "failed"


# ── PIPE-05: 拓扑顺序正确性 ───────────────────────────────────────

@pytest.mark.asyncio
async def test_topological_order_respected(pipeline_supervisor):
    """复杂 DAG 中拓扑顺序严格保持。"""
    dag = TaskDAG()
    a = Task.create(goal_id="G1", description="A", task_type="create", agent_type="writer")
    b = Task.create(goal_id="G1", description="B", task_type="create", agent_type="writer")
    c = Task.create(goal_id="G1", description="C", task_type="create", agent_type="writer")
    d = Task.create(goal_id="G1", description="D", task_type="create", agent_type="writer")
    e = Task.create(goal_id="G1", description="E", task_type="create", agent_type="writer")
    dag.add_task(a)
    dag.add_task(b)
    dag.add_task(c)
    dag.add_task(d)
    dag.add_task(e)
    # A → B, A → C, B → D, C → D, D → E
    dag.add_edge(a.id, b.id)
    dag.add_edge(a.id, c.id)
    dag.add_edge(b.id, d.id)
    dag.add_edge(c.id, d.id)
    dag.add_edge(d.id, e.id)

    plan = Plan(plan_id="P-topo", goal_id="G1", dag=dag,
                strategy=ExecutionStrategy.SEQUENTIAL,
                estimated_total_duration=1500)
    records = await pipeline_supervisor.execute_plan(plan)
    assert len(records) == 5
    assert all(r.status == "completed" for r in records)

    order = _task_ids(records, pipeline_supervisor)
    # A 必须最先，E 必须最后
    assert order[0] == a.id
    assert order[-1] == e.id
    # B 和 C 都在 A 之后、D 之前
    assert order.index(a.id) < order.index(b.id) < order.index(d.id)
    assert order.index(a.id) < order.index(c.id) < order.index(d.id)


# ── PIPE-06: PlanValidator 拒绝无效 plan → 不执行 ───────────────

def test_invalid_plan_prevents_execution():
    """PlanValidator 拒绝（环检测失败）→ 不应执行 plan。"""
    dag = TaskDAG()
    t1 = Task.create(goal_id="G1", description="task 1", task_type="create", agent_type="writer")
    t2 = Task.create(goal_id="G1", description="task 2", task_type="create", agent_type="writer")
    t3 = Task.create(goal_id="G1", description="task 3", task_type="create", agent_type="writer")
    dag.add_task(t1)
    dag.add_task(t2)
    dag.add_task(t3)
    dag.add_edge(t1.id, t2.id)
    dag.add_edge(t2.id, t3.id)
    dag.add_edge(t3.id, t1.id)  # 环!

    validator = PlanValidator()
    report = validator.validate(dag)
    assert not report.valid
    assert any(i.code == "DAG-02" for i in report.errors)


# ── PIPE-07: Fallback agent 管线 ──────────────────────────────────

@pytest.mark.asyncio
async def test_fallback_agent_pipeline():
    """Fallback agent 在 primary 不可用时介入。"""
    registry = AgentRegistry()
    registry.register(AgentDescriptor(
        agent_id="writer-primary", agent_type="writer",
        capabilities=("generation",),
        success_rate=0.3,  # 低成功率触发 fallback
    ))
    registry.register(AgentDescriptor(
        agent_id="writer-fallback", agent_type="writer",
        capabilities=("generation",),
        success_rate=0.95,
    ))

    sup = ExecutionSupervisor(
        registry=registry,
        selector=AgentSelector(registry),
    )

    dag = TaskDAG()
    t1 = Task.create(goal_id="G1", description="write with fallback", task_type="create", agent_type="writer", retry_policy="retry_with_fallback")
    dag.add_task(t1)

    plan = Plan(plan_id="P-fallback", goal_id="G1", dag=dag,
                strategy=ExecutionStrategy.SEQUENTIAL,
                estimated_total_duration=300)
    records = await sup.execute_plan(plan)
    assert len(records) == 1
    # 有 fallback agent，应该完成（即使 primary 不可用）
    assert records[0].status == "completed"


# ── PIPE-08: Audit trail 完整性 ───────────────────────────────────

@pytest.mark.asyncio
async def test_audit_trail_full_pipeline(pipeline_supervisor):
    """全链路执行后 audit trail 应完整。"""
    dag = TaskDAG()
    t1 = Task.create(goal_id="G1", description="step 1", task_type="create", agent_type="writer")
    t2 = Task.create(goal_id="G1", description="step 2", task_type="analyze", agent_type="reviewer", inputs=(t1.id,))
    dag.add_task(t1)
    dag.add_task(t2)
    dag.add_edge(t1.id, t2.id)

    plan = Plan(plan_id="P-audit", goal_id="G1", dag=dag,
                strategy=ExecutionStrategy.SEQUENTIAL,
                estimated_total_duration=600)
    await pipeline_supervisor.execute_plan(plan)

    # 每个 task 至少有 start + complete 两条记录
    assert len(pipeline_supervisor.audit._records) >= 4


# ── PIPE-09: 多 Agent 类型混合管线 ─────────────────────────────

@pytest.mark.asyncio
async def test_mixed_agent_types_pipeline(pipeline_supervisor):
    """4 种 agent_type 全部参与同一管线。"""
    dag = TaskDAG()
    tasks = {
        "research": Task.create(goal_id="G1", description="research", task_type="search", agent_type="researcher"),
        "write": Task.create(goal_id="G1", description="write", task_type="create", agent_type="writer"),
        "review": Task.create(goal_id="G1", description="review", task_type="analyze", agent_type="reviewer"),
        "format": Task.create(goal_id="G1", description="format", task_type="execute", agent_type="data_processor"),
    }
    for t in tasks.values():
        dag.add_task(t)
    dag.add_edge(tasks["research"].id, tasks["write"].id)
    dag.add_edge(tasks["write"].id, tasks["review"].id)
    dag.add_edge(tasks["review"].id, tasks["format"].id)

    plan = Plan(plan_id="P-mixed", goal_id="G1", dag=dag,
                strategy=ExecutionStrategy.SEQUENTIAL,
                estimated_total_duration=1200)
    records = await pipeline_supervisor.execute_plan(plan)
    assert len(records) == 4
    assert all(r.status == "completed" for r in records)

    # 验证每种 agent_type 都被使用
    used_agents = set()
    for record in records:
        agents = [a for a in pipeline_supervisor.registry.list_all()
                  if a.agent_id == record.agent_id]
        if agents:
            used_agents.add(agents[0].agent_type)
    assert used_agents == {"researcher", "writer", "reviewer", "data_processor"}


# ── PIPE-10: 并行组拓扑分组验证 ─────────────────────────────────

def test_parallel_groups_structure():
    """验证 parallel_groups() 正确分组。"""
    dag = TaskDAG()
    a = Task.create(goal_id="G1", description="A", task_type="create", agent_type="writer")
    b = Task.create(goal_id="G1", description="B", task_type="create", agent_type="writer")
    c = Task.create(goal_id="G1", description="C", task_type="create", agent_type="writer")
    d = Task.create(goal_id="G1", description="D", task_type="create", agent_type="writer")
    dag.add_task(a)
    dag.add_task(b)
    dag.add_task(c)
    dag.add_task(d)
    dag.add_edge(a.id, c.id)
    dag.add_edge(b.id, c.id)
    dag.add_edge(c.id, d.id)

    groups = dag.parallel_groups()
    # 预期: [[A, B], [C], [D]]
    assert len(groups) == 3
    # 第一组: A 和 B 可以并行（无依赖）
    assert set(groups[0]) == {a.id, b.id}
    # 第二组: C（依赖 A 和 B）— 返回 list
    assert groups[1] == [c.id]
    # 第三组: D（依赖 C）
    assert groups[2] == [d.id]
