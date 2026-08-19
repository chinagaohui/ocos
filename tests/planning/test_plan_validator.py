"""Phase 24 — Gate Tests: PlanValidator（计划验证 + 模拟执行）。

验证:
  PV01: 空 DAG → warning
  PV02: 有效 DAG → pass
  PV03: 环检测 → error
  PV04: 依赖缺失 → error
  PV05: 无效 agent_type → error
  PV06: 模拟拓扑排序
  PV07: 边+inputs 一致性 → warning
  PV08: 孤岛任务 → warning
  PV09: registry 集成
  PV10: 完整验证 + 模拟
"""

import pytest

from ocos.planning.models import Task, TaskDAG, VALID_AGENT_TYPES
from ocos.planning.plan_validator import (
    PlanValidator,
    PlanValidationReport,
    ValidationSeverity,
    ValidationIssue,
)


# ── PV01: 空 DAG ────────────────────────────────────────────────────────

def test_empty_dag_warning():
    validator = PlanValidator()
    dag = TaskDAG()
    report = validator.validate(dag)
    assert not report.valid
    assert any(i.code == "DAG-01" for i in report.warnings)


# ── PV02: 有效 DAG ────────────────────────────────────────────────────

def test_valid_dag_passes():
    validator = PlanValidator()
    dag = TaskDAG()
    t1 = Task.create(goal_id="G1", description="write intro", task_type="create", agent_type="writer")
    t2 = Task.create(goal_id="G1", description="review intro", task_type="analyze", agent_type="reviewer")
    dag.add_task(t1)
    dag.add_task(t2)
    dag.add_edge(t1.id, t2.id)

    report = validator.validate(dag)
    assert report.valid
    assert len(report.errors) == 0


# ── PV03: 环检测 ──────────────────────────────────────────────────────

def test_circular_dependency_error():
    validator = PlanValidator()
    dag = TaskDAG()
    t1 = Task.create(goal_id="G1", description="task A", task_type="create", agent_type="writer")
    t2 = Task.create(goal_id="G1", description="task B", task_type="create", agent_type="writer")
    t3 = Task.create(goal_id="G1", description="task C", task_type="create", agent_type="writer")
    dag.add_task(t1)
    dag.add_task(t2)
    dag.add_task(t3)
    # A → B → C → A (cycle)
    dag.add_edge(t1.id, t2.id)
    dag.add_edge(t2.id, t3.id)
    dag.add_edge(t3.id, t1.id)

    report = validator.validate(dag)
    assert not report.valid
    assert any(i.code == "DAG-02" for i in report.errors)


# ── PV04: 依赖缺失 ────────────────────────────────────────────────────

def test_missing_dependency_error():
    validator = PlanValidator()
    dag = TaskDAG()
    t1 = Task.create(goal_id="G1", description="task 1", task_type="create", agent_type="writer")
    # t2 depends on non-existent t_missing
    t2 = Task(
        id="TASK-missing-dep",
        goal_id="G1",
        description="task 2",
        task_type="review",
        agent_type="reviewer",
        inputs=("NONEXISTENT",),
    )
    dag.add_task(t1)
    dag.add_task(t2)

    report = validator.validate(dag)
    assert not report.valid
    assert any(i.code == "DEP-01" for i in report.errors)


# ── PV05: 无效 agent_type ─────────────────────────────────────────────

def test_invalid_agent_type_error():
    """PlanValidator.CAP-01: 捕获无效 agent_type（绕过 Task.__post_init__）。"""
    validator = PlanValidator()
    dag = TaskDAG()
    # 绕过 Task 构造验证以测试 PlanValidator 的 CAP-01 路径
    t1 = Task.__new__(Task)
    object.__setattr__(t1, "id", "TASK-bad-type")
    object.__setattr__(t1, "goal_id", "G1")
    object.__setattr__(t1, "description", "bad type task")
    object.__setattr__(t1, "task_type", "create")
    object.__setattr__(t1, "agent_type", "superhero")
    object.__setattr__(t1, "inputs", ())
    object.__setattr__(t1, "estimated_duration", 60)
    object.__setattr__(t1, "priority", 3)
    object.__setattr__(t1, "retry_policy", "retry_3x")
    dag.add_task(t1)

    report = validator.validate(dag)
    assert not report.valid
    assert any(i.code == "CAP-01" for i in report.errors)


# ── PV06: 模拟拓扑排序 ──────────────────────────────────────────────

def test_simulate_topological_order():
    validator = PlanValidator()
    dag = TaskDAG()
    t1 = Task.create(goal_id="G1", description="write", task_type="create", agent_type="writer")
    t2 = Task.create(goal_id="G1", description="review", task_type="analyze", agent_type="reviewer")
    t3 = Task.create(goal_id="G1", description="publish", task_type="execute", agent_type="data_processor")
    dag.add_task(t1)
    dag.add_task(t2)
    dag.add_task(t3)
    dag.add_edge(t1.id, t2.id)
    dag.add_edge(t2.id, t3.id)

    report = validator.simulate(dag)
    assert report.valid
    assert len(report.simulated_execution_order) == 3
    # t1 应在 t2 之前，t2 在 t3 之前
    order = report.simulated_execution_order
    assert order.index(t1.id) < order.index(t2.id) < order.index(t3.id)


# ── PV07: 边 + inputs 不一致 → warning ───────────────────────────────

def test_edge_inputs_consistency_warning():
    validator = PlanValidator()
    dag = TaskDAG()
    t1 = Task.create(goal_id="G1", description="source", task_type="create", agent_type="writer")
    t2 = Task.create(goal_id="G1", description="target", task_type="create", agent_type="writer")
    dag.add_task(t1)
    dag.add_task(t2)
    # edge 存在但 t2.inputs 中未声明 t1 → warning
    dag.add_edge(t1.id, t2.id)

    report = validator.validate(dag)
    assert report.valid  # 警告不影响 validity
    assert any(i.code == "DEP-02" and i.severity == ValidationSeverity.WARNING for i in report.warnings)


# ── PV08: 孤岛任务 → warning ─────────────────────────────────────────

def test_isolated_task_warning():
    validator = PlanValidator()
    dag = TaskDAG()
    t1 = Task.create(goal_id="G1", description="source", task_type="create", agent_type="writer")
    t2 = Task.create(goal_id="G1", description="target", task_type="create", agent_type="writer")
    t3 = Task.create(goal_id="G1", description="island", task_type="execute", agent_type="data_processor")
    dag.add_task(t1)
    dag.add_task(t2)
    dag.add_task(t3)
    dag.add_edge(t1.id, t2.id)

    report = validator.validate(dag)
    assert any(i.code == "DAG-04" for i in report.warnings)


# ── PV09: registry 集成 ──────────────────────────────────────────────

def test_registry_integration():
    from ocos.agent_orchestration.registry import AgentRegistry, AgentDescriptor

    registry = AgentRegistry()
    # 注册一个 writer agent
    registry.register(AgentDescriptor(
        agent_id="writer-001",
        agent_type="writer",
        capabilities=("text-generation",),
    ))

    validator = PlanValidator(registry=registry)
    dag = TaskDAG()
    t1 = Task.create(goal_id="G1", description="write", task_type="create", agent_type="writer")
    t2 = Task.create(goal_id="G1", description="review", task_type="analyze", agent_type="reviewer")
    dag.add_task(t1)
    dag.add_task(t2)

    report = validator.validate(dag)
    # reviewer type 未注册 → CAP-02 error
    assert not report.valid
    assert any(i.code == "CAP-02" for i in report.errors)
    assert "reviewer" in report.available_agent_types or "writer" in report.available_agent_types


# ── PV10: 完整验证+模拟 ──────────────────────────────────────────────

def test_full_validate_and_simulate():
    validator = PlanValidator()
    dag = TaskDAG()
    t1 = Task.create(goal_id="G1", description="step 1", task_type="create", agent_type="writer")
    t2 = Task.create(goal_id="G1", description="step 2", task_type="analyze", agent_type="researcher", inputs=(t1.id,))
    t3 = Task.create(goal_id="G1", description="step 3", task_type="execute", agent_type="writer")
    dag.add_task(t1)
    dag.add_task(t2)
    dag.add_task(t3)
    dag.add_edge(t1.id, t2.id)

    report = validator.simulate(dag)
    assert report.valid
    assert report.task_count == 3
    assert report.edge_count == 1
    assert len(report.simulated_execution_order) == 3
    assert t1.id in report.simulated_execution_order
    assert report.simulated_execution_order.index(t1.id) < report.simulated_execution_order.index(t2.id)


# ── PV11: ValidationIssue 结构 ────────────────────────────────────────

def test_validation_issue_frozen():
    issue = ValidationIssue(
        code="DAG-01",
        severity=ValidationSeverity.ERROR,
        task_id=None,
        message="empty dag",
    )
    assert issue.code == "DAG-01"
    assert issue.severity == ValidationSeverity.ERROR


# ── PV12: PlanValidationReport summary ────────────────────────────────

def test_report_summary():
    report = PlanValidationReport(
        report_id="PVR-test",
        plan_id="plan-test",
        valid=True,
        task_count=3,
    )
    summary = report.summary()
    assert "valid=True" in summary
    assert "tasks=3" in summary
