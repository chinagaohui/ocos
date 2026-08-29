"""Phase 24 — PlanValidator: 计划验证 + 模拟执行。

职责:
  1. 验证 TaskDAG 结构合法性（环检测、依赖完整性）
  2. 验证每个 Task 的 agent_type 是否有可用 Agent
  3. 模拟执行 TaskDAG（返回预期结果，不实际运行）

合并: PlanValidator + Simulator 共享同一接口，通过 mode='validate'/'simulate' 切换。
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Any

from ocos.planning.models import Plan, TaskDAG, VALID_AGENT_TYPES

if TYPE_CHECKING:
    pass  # AgentRegistry 通过鸭子类型访问


# ── Validation Report ──────────────────────────────────────────────────────


class ValidationSeverity(Enum):
    """验证问题严重度。"""
    ERROR = "error"      # 阻塞——不可执行
    WARNING = "warning"  # 可执行但有问题
    INFO = "info"        # 仅供参考


@dataclass(frozen=True)
class ValidationIssue:
    """单个验证问题。"""
    code: str                          # 问题代码（如 "DAG-01", "CAP-03"）
    severity: ValidationSeverity
    task_id: str | None                # 关联的任务 ID（全局问题时为 None）
    message: str
    suggestion: str = ""


@dataclass
class PlanValidationReport:
    """计划验证报告。"""
    report_id: str
    plan_id: str
    valid: bool                        # 无 ERROR 级问题
    issues: list[ValidationIssue] = field(default_factory=list)
    task_count: int = 0
    edge_count: int = 0
    available_agent_types: list[str] = field(default_factory=list)
    simulated_execution_order: list[str] = field(default_factory=list)  # 模拟执行拓扑序
    verified_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def errors(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == ValidationSeverity.ERROR]

    @property
    def warnings(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == ValidationSeverity.WARNING]

    def add_error(self, code: str, message: str, task_id: str | None = None, suggestion: str = ""):
        self.issues.append(ValidationIssue(code, ValidationSeverity.ERROR, task_id, message, suggestion))
        self.valid = False

    def add_warning(self, code: str, message: str, task_id: str | None = None, suggestion: str = ""):
        self.issues.append(ValidationIssue(code, ValidationSeverity.WARNING, task_id, message, suggestion))

    def summary(self) -> str:
        return (
            f"PlanValidationReport(report_id={self.report_id}, "
            f"valid={self.valid}, errors={len(self.errors)}, "
            f"warnings={len(self.warnings)}, tasks={self.task_count})"
        )


# ── PlanValidator ──────────────────────────────────────────────────────────


class PlanValidator:
    """计划验证器 — 验证 + 模拟执行，共享同一接口。

    用法:
        validator = PlanValidator(registry=agent_registry)
        report = validator.validate(dag)       # 仅验证
        report = validator.simulate(dag)        # 验证 + 模拟拓扑执行
    """

    def __init__(self, registry: Any = None) -> None:
        self._registry = registry

    # ── 公开方法 ────────────────────────────────────────────────────────

    def validate(self, dag: TaskDAG) -> PlanValidationReport:
        """验证 TaskDAG 结构合法性。不模拟执行。"""
        return self._run_checks(dag, simulate=False)

    def simulate(self, dag: TaskDAG) -> PlanValidationReport:
        """验证 + 模拟拓扑执行顺序。"""
        return self._run_checks(dag, simulate=True)

    # ── 内部 ────────────────────────────────────────────────────────────

    def _run_checks(self, dag: TaskDAG, simulate: bool) -> PlanValidationReport:
        report = PlanValidationReport(
            report_id=f"PVR-{uuid.uuid4().hex[:8].upper()}",
            plan_id=f"plan-{uuid.uuid4().hex[:6]}",
            valid=True,
            task_count=len(dag.tasks),
            edge_count=len(dag.edges),
        )

        # 获取可用 agent types
        if self._registry is not None:
            try:
                descriptors = self._registry.list_all()
                report.available_agent_types = sorted(set(d.agent_type for d in descriptors))
            except (AttributeError, TypeError):
                report.available_agent_types = sorted(VALID_AGENT_TYPES)
        else:
            report.available_agent_types = sorted(VALID_AGENT_TYPES)

        # 1. 结构检查
        self._check_dag_structure(dag, report)

        # 2. 能力检查
        self._check_capability_coverage(dag, report)

        # 3. 依赖检查
        self._check_dependencies(dag, report)

        # 4. 模拟执行（如果要求）
        if simulate and report.valid:
            report.simulated_execution_order = self._simulate_topological_order(dag)

        return report

    # ── DAG 结构检查 ──────────────────────────────────────────────────

    def _check_dag_structure(self, dag: TaskDAG, report: PlanValidationReport) -> None:
        """检查 DAG 结构合法性。"""
        # DAG-01: 空 DAG
        if not dag.tasks:
            report.add_warning("DAG-01", "TaskDAG contains no tasks")
            report.valid = False
            return

        # DAG-02: 环检测
        cycle = self._detect_cycle(dag)
        if cycle:
            report.add_error(
                "DAG-02",
                f"circular dependency detected: {' → '.join(cycle)}",
                suggestion="break the cycle by removing or reordering edges",
            )
            report.valid = False

        # DAG-03: 边引用完整性
        for from_id, to_id in dag.edges:
            if from_id not in dag.tasks:
                report.add_error("DAG-03", f"edge references missing task: from={from_id}", task_id=from_id)
            if to_id not in dag.tasks:
                report.add_error("DAG-03", f"edge references missing task: to={to_id}", task_id=to_id)

        # DAG-04: 孤岛任务检测（无入度也无出度的任务）
        in_degree: dict[str, int] = {tid: 0 for tid in dag.tasks}
        out_degree: dict[str, int] = {tid: 0 for tid in dag.tasks}
        for from_id, to_id in dag.edges:
            in_degree[to_id] = in_degree.get(to_id, 0) + 1
            out_degree[from_id] = out_degree.get(from_id, 0) + 1

        for tid in dag.tasks:
            if in_degree.get(tid, 0) == 0 and out_degree.get(tid, 0) == 0 and len(dag.tasks) > 1:
                report.add_warning(
                    "DAG-04",
                    f"isolated task (no dependencies): {tid}",
                    task_id=tid,
                    suggestion="connect to other tasks or mark as root",
                )

    # ── 能力检查 ───────────────────────────────────────────────────────

    def _check_capability_coverage(self, dag: TaskDAG, report: PlanValidationReport) -> None:
        """检查每个 Task 的 agent_type 是否可用。"""
        available = set(report.available_agent_types)

        for tid, task in dag.tasks.items():
            # CAP-01: agent_type 是否在有效集合中
            if task.agent_type not in VALID_AGENT_TYPES:
                report.add_error(
                    "CAP-01",
                    f"invalid agent_type '{task.agent_type}'",
                    task_id=tid,
                    suggestion=f"use one of: {sorted(VALID_AGENT_TYPES)}",
                )
                continue

            # CAP-02: agent_type 是否有可用 Agent（仅 registry 存在时）
            if self._registry and task.agent_type not in available:
                report.add_error(
                    "CAP-02",
                    f"no available agent for type '{task.agent_type}'",
                    task_id=tid,
                    suggestion=f"register an agent of type '{task.agent_type}'",
                )

            # CAP-03: retry_policy 合法性
            valid_retries = {"no_retry", "retry_3x", "retry_with_fallback"}
            if task.retry_policy not in valid_retries:
                report.add_warning(
                    "CAP-03",
                    f"unknown retry_policy '{task.retry_policy}'",
                    task_id=tid,
                    suggestion=f"use one of: {sorted(valid_retries)}",
                )

    # ── 依赖检查 ───────────────────────────────────────────────────────

    def _check_dependencies(self, dag: TaskDAG, report: PlanValidationReport) -> None:
        """检查任务依赖完整性。"""
        all_ids = set(dag.tasks.keys())

        for tid, task in dag.tasks.items():
            for dep_id in task.inputs:
                # DEP-01: 依赖的任务不存在
                if dep_id not in all_ids:
                    report.add_error(
                        "DEP-01",
                        f"depends on non-existent task '{dep_id}'",
                        task_id=tid,
                        suggestion="add the missing task or remove the dependency",
                    )

        # DEP-02: Task.inputs 与 dag.edges 一致性
        explicit_edges: set[tuple[str, str]] = set(dag.edges)
        implicit_edges: set[tuple[str, str]] = set()
        for tid, task in dag.tasks.items():
            for dep_id in task.inputs:
                implicit_edges.add((dep_id, tid))

        # edges 中存在但 inputs 中没有的
        for from_id, to_id in explicit_edges - implicit_edges:
            if from_id in all_ids and to_id in all_ids:
                report.add_warning(
                    "DEP-02",
                    f"edge {from_id}→{to_id} not reflected in Task.inputs",
                    task_id=to_id,
                )

    # ── 拓扑排序模拟 ───────────────────────────────────────────────────

    def _simulate_topological_order(self, dag: TaskDAG) -> list[str]:
        """模拟拓扑执行顺序。使用 Kahn 算法。"""
        in_degree: dict[str, int] = {tid: 0 for tid in dag.tasks}
        adjacency: dict[str, list[str]] = {tid: [] for tid in dag.tasks}

        for from_id, to_id in dag.edges:
            in_degree[to_id] = in_degree.get(to_id, 0) + 1
            adjacency.setdefault(from_id, []).append(to_id)

        # Kahn 算法
        queue = sorted(tid for tid, deg in in_degree.items() if deg == 0)
        order: list[str] = []

        while queue:
            node = queue.pop(0)
            order.append(node)
            for neighbor in adjacency.get(node, []):
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)
                    queue.sort()  # 确定性顺序

        return order

    # ── 环检测 ─────────────────────────────────────────────────────────

    @staticmethod
    def _detect_cycle(dag: TaskDAG) -> list[str] | None:
        """检测并返回一个环的路径，无环返回 None。"""
        visited: set[str] = set()
        path: list[str] = []
        path_set: set[str] = set()

        adjacency: dict[str, list[str]] = {tid: [] for tid in dag.tasks}
        for from_id, to_id in dag.edges:
            adjacency.setdefault(from_id, []).append(to_id)

        def dfs(node: str) -> list[str] | None:
            if node in path_set:
                # 找到环：从第一个出现位置到 ending
                idx = path.index(node)
                return path[idx:] + [node]
            if node in visited:
                return None

            visited.add(node)
            path.append(node)
            path_set.add(node)

            for neighbor in adjacency.get(node, []):
                cycle = dfs(neighbor)
                if cycle:
                    return cycle

            path.pop()
            path_set.discard(node)
            return None

        for tid in dag.tasks:
            cycle = dfs(tid)
            if cycle:
                return cycle

        return None


# ── Plan 级合法性检查 (GAP-P3-6 并入, 原 planning/validator.py) ─────────────

def validate_plan(plan: Plan) -> tuple[bool, str]:
    """验证 Plan 级合法性 (Phase 27 Gate 检查)。

    GAP-P3-6: 由 planning/validator.py 的 PlanValidator.validate
    并入。验证对象为 Plan (goal_id/DAG 无环/非空/时长), 与
    PlanValidator.validate(dag) 的 DAG 级验证互补。
    """
    # 1. Plan 必须关联 Goal
    if not plan.goal_id:
        return False, "Plan must reference a Goal"
    # 2. DAG 必须无环
    if not plan.dag.validate_acyclic():
        return False, "DAG contains cycles"
    # 3. DAG 不能为空
    if not plan.dag.tasks:
        return False, "DAG must contain at least one Task"
    # 4. 估算总时长 > 0
    if plan.estimated_total_duration <= 0:
        return False, "estimated_total_duration must be positive"
    return True, "ok"


def validate_no_self_module() -> None:
    """Gateway check: ocos.planning 不导入 ocos.self。

    GAP-P3-6: 由 planning/validator.py 并入。真正的检查由
    ocos/tests/test_import_rules.py 完成。
    """
    pass
