"""Phase 27 — Gate Tests: Planning Models。

验证:
  27-M01: Task frozen
  27-M02: TaskStatus lifecycle
  27-M03: DAG topological order
  27-M04: DAG parallel groups
  27-M05: DAG cycle detection
  27-M06: Plan frozen + validation
"""

import pytest
from ocos.planning.models import (
    Task,
    TaskDAG,
    TaskStatus,
    ExecutionStrategy,
    Plan,
    MAX_DAG_DEPTH,
    MAX_PARALLEL_WIDTH,
)


# ── 27-M01: Task frozen ──────────────────────────────────────────────

def test_task_frozen():
    t = Task(id="T1", goal_id="G1", description="写大纲",
             task_type="create", agent_type="writer")
    with pytest.raises(Exception):
        t.description = "改"  # type: ignore


def test_task_create_factory():
    t = Task.create(goal_id="G1", description="写大纲", task_type="create")
    assert t.id.startswith("TASK-")
    assert t.goal_id == "G1"
    assert t.task_type == "create"
    assert t.priority == 1


def test_task_empty_fields_rejected():
    with pytest.raises(ValueError, match="goal_id"):
        Task(id="T1", goal_id="", description="x", task_type="create", agent_type="writer")
    with pytest.raises(ValueError, match="description"):
        Task(id="T1", goal_id="G1", description="", task_type="create", agent_type="writer")


# ── 27-M02: TaskStatus lifecycle ─────────────────────────────────────

def test_task_status_transitions():
    assert TaskStatus.PENDING.can_transition_to(TaskStatus.READY)
    assert TaskStatus.READY.can_transition_to(TaskStatus.RUNNING)
    assert TaskStatus.RUNNING.can_transition_to(TaskStatus.COMPLETED)
    assert TaskStatus.RUNNING.can_transition_to(TaskStatus.FAILED)
    assert TaskStatus.FAILED.can_transition_to(TaskStatus.READY)  # retry
    assert not TaskStatus.COMPLETED.can_transition_to(TaskStatus.FAILED)


def test_task_status_terminal():
    assert TaskStatus.COMPLETED.is_terminal
    assert TaskStatus.FAILED.is_terminal
    assert not TaskStatus.RUNNING.is_terminal


# ── 27-M03: DAG topological order ───────────────────────────────────

def test_dag_linear_topological_order():
    dag = TaskDAG()
    t1 = Task.create("G1", "task1")
    t2 = Task.create("G1", "task2")
    t3 = Task.create("G1", "task3")
    dag.add_task(t1)
    dag.add_task(t2)
    dag.add_task(t3)
    dag.add_edge(t1.id, t2.id)
    dag.add_edge(t2.id, t3.id)
    order = dag.topological_order()
    assert order == [t1.id, t2.id, t3.id]


def test_dag_diamond_topological_order():
    dag = TaskDAG()
    t1 = Task.create("G1", "start")
    t2 = Task.create("G1", "left")
    t3 = Task.create("G1", "right")
    t4 = Task.create("G1", "end")
    dag.add_task(t1)
    dag.add_task(t2)
    dag.add_task(t3)
    dag.add_task(t4)
    dag.add_edge(t1.id, t2.id)
    dag.add_edge(t1.id, t3.id)
    dag.add_edge(t2.id, t4.id)
    dag.add_edge(t3.id, t4.id)
    order = dag.topological_order()
    assert order[0] == t1.id
    assert order[3] == t4.id
    assert set(order[1:3]) == {t2.id, t3.id}


# ── 27-M04: DAG parallel groups ──────────────────────────────────────

def test_dag_parallel_groups():
    dag = TaskDAG()
    t1 = Task.create("G1", "root")
    t2 = Task.create("G1", "child1")
    t3 = Task.create("G1", "child2")
    dag.add_task(t1)
    dag.add_task(t2)
    dag.add_task(t3)
    dag.add_edge(t1.id, t2.id)
    dag.add_edge(t1.id, t3.id)
    groups = dag.parallel_groups()
    assert len(groups) == 2
    assert groups[0] == [t1.id]
    assert set(groups[1]) == {t2.id, t3.id}


# ── 27-M05: DAG cycle detection ──────────────────────────────────────

def test_dag_cycle_detected():
    dag = TaskDAG()
    t1 = Task.create("G1", "a")
    t2 = Task.create("G1", "b")
    t3 = Task.create("G1", "c")
    dag.add_task(t1)
    dag.add_task(t2)
    dag.add_task(t3)
    dag.add_edge(t1.id, t2.id)
    dag.add_edge(t2.id, t3.id)
    dag.add_edge(t3.id, t1.id)  # cycle
    assert not dag.validate_acyclic()


def test_dag_no_cycle():
    dag = TaskDAG()
    t1 = Task.create("G1", "a")
    t2 = Task.create("G1", "b")
    dag.add_task(t1)
    dag.add_task(t2)
    dag.add_edge(t1.id, t2.id)
    assert dag.validate_acyclic()


# ── 27-M06: Plan frozen + validation ─────────────────────────────────

def test_plan_frozen():
    dag = TaskDAG()
    p = Plan(
        plan_id="P1",
        goal_id="G1",
        dag=dag,
        strategy=ExecutionStrategy.SEQUENTIAL,
        estimated_total_duration=300,
    )
    with pytest.raises(Exception):
        p.plan_id = "P2"  # type: ignore


def test_plan_empty_fields_rejected():
    dag = TaskDAG()
    with pytest.raises(ValueError, match="plan_id"):
        Plan(plan_id="", goal_id="G1", dag=dag,
             strategy=ExecutionStrategy.SEQUENTIAL, estimated_total_duration=300)
    with pytest.raises(ValueError, match="goal_id"):
        Plan(plan_id="P1", goal_id="", dag=dag,
             strategy=ExecutionStrategy.SEQUENTIAL, estimated_total_duration=300)


# ── 27-M07: Topology budgets ─────────────────────────────────────────

def test_max_dag_depth():
    assert MAX_DAG_DEPTH == 5


def test_max_parallel_width():
    assert MAX_PARALLEL_WIDTH == 4
