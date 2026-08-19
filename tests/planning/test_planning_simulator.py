"""Phase 27 — Gate Tests: Simulator。

验证:
  27-M01: simulate no deadlock
  27-M02: simulate duration estimate
  27-M03: simulate deadlock detection
  27-M04: simulate risk detection
  27-M05: budget warnings
"""

from ocos.planning.simulator import PlanSimulator
from ocos.planning.models import (
    Task, TaskDAG, ExecutionStrategy, Plan,
    MAX_DAG_DEPTH, MAX_PARALLEL_WIDTH,
)


def _mkdag(*task_ids: str, edges: list[tuple] | None = None) -> TaskDAG:
    dag = TaskDAG()
    for tid in task_ids:
        dag.add_task(Task(
            id=tid, goal_id="G1", description=f"task {tid}",
            task_type="execute", agent_type="writer",
        ))
    if edges:
        for frm, to in edges:
            dag.add_edge(frm, to)
    return dag


def _plan(dag: TaskDAG, strategy=ExecutionStrategy.SEQUENTIAL) -> Plan:
    return Plan(
        plan_id="P-test",
        goal_id="G1",
        dag=dag,
        strategy=strategy,
        estimated_total_duration=300,
    )


# ── 27-M01: simulate no deadlock ────────────────────────────────────

def test_simulate_no_deadlock():
    dag = _mkdag("A", "B", edges=[("A", "B")])
    result = PlanSimulator.simulate(_plan(dag))
    assert result.success
    assert not result.deadlock_detected


# ── 27-M02: simulate duration estimate ──────────────────────────────

def test_simulate_duration_sequential():
    dag = TaskDAG()
    dag.add_task(Task(id="A", goal_id="G1", description="a",
                      task_type="execute", agent_type="writer",
                      estimated_duration=100))
    dag.add_task(Task(id="B", goal_id="G1", description="b",
                      task_type="execute", agent_type="writer",
                      estimated_duration=200))
    dag.add_edge("A", "B")
    result = PlanSimulator.simulate(_plan(dag))
    assert result.estimated_duration == 300


def test_simulate_duration_parallel():
    dag = TaskDAG()
    dag.add_task(Task(id="A", goal_id="G1", description="a",
                      task_type="execute", agent_type="writer",
                      estimated_duration=100))
    dag.add_task(Task(id="B", goal_id="G1", description="b",
                      task_type="execute", agent_type="writer",
                      estimated_duration=200))
    result = PlanSimulator.simulate(
        _plan(dag, strategy=ExecutionStrategy.PARALLEL)
    )
    # 并行: 取最大
    assert result.estimated_duration == 200


# ── 27-M03: deadlock detection ──────────────────────────────────────

def test_simulate_deadlock():
    dag = _mkdag("A", "B", "C", edges=[("A", "B"), ("B", "C"), ("C", "A")])
    result = PlanSimulator.simulate(_plan(dag))
    assert result.deadlock_detected
    assert not result.success


# ── 27-M04: risk detection ──────────────────────────────────────────

def test_simulate_long_task_risk():
    dag = TaskDAG()
    dag.add_task(Task(id="A", goal_id="G1", description="long task",
                      task_type="execute", agent_type="writer",
                      estimated_duration=900))
    result = PlanSimulator.simulate(_plan(dag))
    assert any("long" in r.lower() for r in result.risks)


# ── 27-M05: budget warnings ─────────────────────────────────────────

def test_simulate_budget_warnings():
    # > MAX_PARALLEL_WIDTH 无依赖任务
    dag = _mkdag(*[f"T{i}" for i in range(MAX_PARALLEL_WIDTH + 2)])
    result = PlanSimulator.simulate(
        _plan(dag, strategy=ExecutionStrategy.PARALLEL)
    )
    assert len(result.warnings) > 0
    assert any("MAX_PARALLEL_WIDTH" in w for w in result.warnings)
