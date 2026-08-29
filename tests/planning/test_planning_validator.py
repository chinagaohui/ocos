"""Phase 27 — Gate Tests: PlanValidator。

验证:
  27-V01: plan must reference goal
  27-V02: no self import
  27-V03: plan with valid DAG
  27-V04: plan with cyclic DAG
  27-V05: plan with empty DAG
"""

import pytest
from ocos.planning.plan_validator import validate_no_self_module, validate_plan
from ocos.planning.models import Task, TaskDAG, ExecutionStrategy, Plan


def _dag(*task_ids: str, edges: list[tuple] | None = None) -> TaskDAG:
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


def _plan(
    dag: TaskDAG,
    goal_id: str = "G1",
    plan_id: str = "P1",
) -> Plan:
    return Plan(
        plan_id=plan_id,
        goal_id=goal_id,
        dag=dag,
        strategy=ExecutionStrategy.SEQUENTIAL,
        estimated_total_duration=300,
    )


# ── 27-V01: plan must reference goal ────────────────────────────────

def test_validate_with_goal():
    dag = _dag("A", "B", edges=[("A", "B")])
    ok, reason = validate_plan(_plan(dag))
    assert ok


def test_validate_with_no_goal():
    # goal_id 在 __post_init__ 层就被拒绝了
    pass  # enforced at model level


# ── 27-V02: no self import ──────────────────────────────────────────

def test_validate_no_self_module():
    validate_no_self_module()
    # 真正的检查在 test_import_rules.py


# ── 27-V03: valid DAG ───────────────────────────────────────────────

def test_validate_valid_dag():
    dag = _dag("A", "B", "C", edges=[("A", "B"), ("B", "C")])
    ok, reason = validate_plan(_plan(dag))
    assert ok
    assert reason == "ok"


# ── 27-V04: cyclic DAG ─────────────────────────────────────────────

def test_validate_cyclic_dag():
    dag = _dag("A", "B", "C", edges=[("A", "B"), ("B", "C"), ("C", "A")])
    ok, reason = validate_plan(_plan(dag))
    assert not ok
    assert "cycle" in reason


# ── 27-V05: empty DAG ──────────────────────────────────────────────

def test_validate_empty_dag():
    dag = TaskDAG()
    ok, reason = validate_plan(_plan(dag))
    assert not ok
    assert "at least one Task" in reason
