"""Phase 27 — Gate Tests: StrategyEngine。

验证:
  27-S01: sequential strategy for linear chain
  27-S02: parallel strategy for independent tasks
  27-S03: priority_driven for mixed structure
  27-S04: strategy based on dependencies
  27-S05: parallel width validation
"""

from ocos.planning.strategy import StrategyEngine
from ocos.planning.models import Task, TaskDAG, ExecutionStrategy, MAX_PARALLEL_WIDTH


def _mkdag(*task_ids: str) -> TaskDAG:
    dag = TaskDAG()
    for tid in task_ids:
        dag.add_task(Task(
            id=tid, goal_id="G1", description=f"task {tid}",
            task_type="execute", agent_type="writer",
        ))
    return dag


# ── 27-S01: sequential strategy ─────────────────────────────────────

def test_sequential_for_linear_chain():
    dag = _mkdag("A", "B", "C")
    dag.add_edge("A", "B")
    dag.add_edge("B", "C")
    assert StrategyEngine.select(dag) == ExecutionStrategy.SEQUENTIAL


# ── 27-S02: parallel strategy ───────────────────────────────────────

def test_parallel_for_independent_tasks():
    dag = _mkdag("A", "B", "C")
    # no edges → all parallel
    assert StrategyEngine.select(dag) == ExecutionStrategy.PARALLEL


# ── 27-S03: priority_driven for mixed ───────────────────────────────

def test_priority_driven_for_diamond():
    dag = _mkdag("A", "B", "C", "D")
    dag.add_edge("A", "B")
    dag.add_edge("A", "C")
    dag.add_edge("B", "D")
    dag.add_edge("C", "D")
    assert StrategyEngine.select(dag) == ExecutionStrategy.PRIORITY_DRIVEN


# ── 27-S04: strategy explain ────────────────────────────────────────

def test_strategy_explain():
    dag = _mkdag("A", "B")
    dag.add_edge("A", "B")
    explanation = StrategyEngine.explain(dag)
    assert "串行" in explanation or "sequential" in explanation.lower()


def test_parallel_explain():
    dag = _mkdag("A", "B")
    explanation = StrategyEngine.explain(dag)
    assert "并行" in explanation or "parallel" in explanation.lower()


# ── 27-S05: parallel width validation ───────────────────────────────

def test_validate_parallel_width_ok():
    dag = _mkdag("A", "B")
    ok, msg = StrategyEngine.validate_parallel_width(dag)
    assert ok


def test_validate_parallel_width_exceeded():
    dag = _mkdag(*[f"T{i}" for i in range(MAX_PARALLEL_WIDTH + 2)])
    ok, msg = StrategyEngine.validate_parallel_width(dag)
    assert not ok
