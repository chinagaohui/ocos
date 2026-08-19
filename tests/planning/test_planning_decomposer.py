"""Phase 27 — Gate Tests: TaskDecomposer。

验证:
  27-D01: decompose writing goal → 大纲→章节链
  27-D02: decompose analysis goal
  27-D03: decompose research goal
  27-D04: decompose development goal
  27-D05: constraint transfer to Task
  27-D06: agent_type assignment
  27-D07: budget enforcement
"""

import pytest
from ocos.planning.decomposer import TaskDecomposer
from ocos.planning.models import MAX_DAG_DEPTH, MAX_PARALLEL_WIDTH
from ocos.goal.models import GoalDomain, GoalSource, UserGoal


def _goal(domain: GoalDomain, constraints: tuple = ()) -> UserGoal:
    return UserGoal(
        id="G-test",
        raw_input="test",
        objective="test",
        domain=domain,
        constraints=constraints,
        source=GoalSource.HUMAN,
        caller="orchestrator",
    )


# ── 27-D01: decompose writing goal ──────────────────────────────────

def test_decompose_writing_goal():
    g = _goal(GoalDomain.WRITING, ("5万字",))
    dag = TaskDecomposer.decompose(g)
    tasks = dag.tasks
    assert len(tasks) >= 3
    assert any("写大纲" in t.description for t in tasks.values())
    assert any("章" in t.description for t in tasks.values())


def test_decompose_writing_goal_topological():
    g = _goal(GoalDomain.WRITING)
    dag = TaskDecomposer.decompose(g)
    order = dag.topological_order()
    # 大纲应该在最前面
    first_desc = dag.tasks[order[0]].description
    assert "大纲" in first_desc


# ── 27-D02: decompose analysis goal ─────────────────────────────────

def test_decompose_analysis_goal():
    g = _goal(GoalDomain.ANALYSIS)
    dag = TaskDecomposer.decompose(g)
    assert len(dag.tasks) >= 2
    order = dag.topological_order()
    first_desc = dag.tasks[order[0]].description
    assert "收集" in first_desc or "数据" in first_desc


# ── 27-D03: decompose research goal ─────────────────────────────────

def test_decompose_research_goal():
    g = _goal(GoalDomain.RESEARCH)
    dag = TaskDecomposer.decompose(g)
    assert len(dag.tasks) >= 2
    order = dag.topological_order()
    first_desc = dag.tasks[order[0]].description
    assert "文献" in first_desc or "调研" in first_desc


# ── 27-D04: decompose development goal ──────────────────────────────

def test_decompose_development_goal():
    g = _goal(GoalDomain.DEVELOPMENT)
    dag = TaskDecomposer.decompose(g)
    assert len(dag.tasks) >= 2
    order = dag.topological_order()
    first_desc = dag.tasks[order[0]].description
    assert "设计" in first_desc or "架构" in first_desc


# ── 27-D05: constraint transfer ─────────────────────────────────────

def test_constraint_transfer_to_task():
    g = _goal(GoalDomain.WRITING, ("5万字", "主角AI工程师"))
    dag = TaskDecomposer.decompose(g)
    first_task = dag.topological_order()[0]
    desc = dag.tasks[first_task].description
    # 约束已写入描述
    assert "5万字" in desc or "AI" in desc


# ── 27-D06: agent_type assignment ───────────────────────────────────

def test_agent_type_assignment():
    g = _goal(GoalDomain.WRITING)
    dag = TaskDecomposer.decompose(g)
    agent_types = {t.agent_type for t in dag.tasks.values()}
    assert "writer" in agent_types
    assert "reviewer" in agent_types


# ── 27-D07: budget enforcement ──────────────────────────────────────

def test_budget_enforcement_no_warnings():
    """串行模板应在预算内。"""
    g = _goal(GoalDomain.WRITING)
    dag = TaskDecomposer.decompose(g)
    groups = dag.parallel_groups()
    assert len(groups) <= MAX_DAG_DEPTH
    for group in groups:
        assert len(group) <= MAX_PARALLEL_WIDTH
