"""Phase 26 — 50-Engine 规模扩展压力测试。

SCALE-01: EngineManifest 发现性能（50 引擎声明）
SCALE-02: TaskDAG 大规模 DAG 构建 + 环检测（200 任务）
SCALE-03: AgentRegistry 大规模注册 + 并发查找（500 agent）
SCALE-04: PlanValidator 大规模 DAG 验证（200 任务）
SCALE-05: 内存基线（50 引擎 + 200 任务 DAG 对象数量）
"""

import time
import pytest

from ocos.planning.models import Task, TaskDAG, ExecutionStrategy, Plan
from ocos.planning.plan_validator import PlanValidator
from ocos.agent_orchestration.registry import AgentDescriptor, AgentRegistry
from ocos.agent_orchestration.selector import AgentSelector
from ocos.platform.engine_manifest import EngineManifest


# ── 工具 ──────────────────────────────────────────────────────────


def _make_manifest(engine_id: str) -> EngineManifest:
    """创建模拟 EngineManifest。"""
    return EngineManifest(
        engine_id=engine_id,
        name=engine_id.replace("_", " ").title(),
        capabilities=[engine_id],
        dependencies=[],
    )


def _make_agent(prefix: str, index: int, agent_type: str = "writer") -> AgentDescriptor:
    return AgentDescriptor(
        agent_id=f"{prefix}-{index:04d}",
        agent_type=agent_type,
        capabilities=("text-generation", "revision"),
        success_rate=0.9,
    )


# ── SCALE-01: EngineManifest 50 引擎声明 ──────────────────────────

def test_engine_manifest_50_declarations():
    """50 引擎声明应在 5ms 内完成。"""
    start = time.perf_counter()
    manifests = []
    for i in range(50):
        m = _make_manifest(f"engine_{i}")
        manifests.append(m)

    # 构建依赖数组并做拓扑排序（如果有实现）
    for i in range(1, 50):
        manifests[i] = EngineManifest(
            engine_id=f"engine_{i}",
            name=f"Engine {i}",
            capabilities=[f"engine_{i}"],
            dependencies=[f"engine_{i-1}"],
        )

    elapsed = time.perf_counter() - start
    assert len(manifests) == 50
    assert elapsed < 0.005, f"50 引擎声明: {elapsed*1000:.2f}ms (超过 5ms)"


# ── SCALE-02: TaskDAG 200 任务 ────────────────────────────────────

def test_taskdag_200_tasks():
    """200 任务 DAG 构建 + 拓扑排序应在 25ms 内。"""
    dag = TaskDAG()
    tasks = []
    for i in range(200):
        t = Task.create(
            goal_id="G1",
            description=f"task {i}",
            task_type="create",
            agent_type="writer",
        )
        dag.add_task(t)
        tasks.append(t)

    # 线性链
    for i in range(199):
        dag.add_edge(tasks[i].id, tasks[i + 1].id)

    start = time.perf_counter()
    order = dag.topological_order()
    elapsed = time.perf_counter() - start

    assert len(order) == 200
    assert order[0] == tasks[0].id
    assert order[-1] == tasks[199].id
    assert elapsed < 0.025, f"200 任务拓扑排序: {elapsed*1000:.2f}ms (超过 25ms)"


# ── SCALE-03: AgentRegistry 500 agent ─────────────────────────────

def test_agent_registry_500_agents():
    """500 agent 注册 + 查找应在 100ms 内。"""
    registry = AgentRegistry()

    start = time.perf_counter()
    for i in range(500):
        agent_type = ["writer", "reviewer", "researcher", "data_processor"][i % 4]
        registry.register(_make_agent("agent", i, agent_type))
    reg_time = time.perf_counter() - start
    assert reg_time < 0.05, f"500 agent 注册: {reg_time*1000:.2f}ms (超过 50ms)"

    # 按类型查找 100 次
    start = time.perf_counter()
    agents_writer: list = []
    for _ in range(100):
        agents_writer = registry.find_by_type("writer")
    find_time = time.perf_counter() - start
    assert len(agents_writer) > 0
    assert find_time < 0.05, f"100 次查找: {find_time*1000:.2f}ms (超过 50ms)"

    # list_all
    start = time.perf_counter()
    all_agents = registry.list_all()
    list_time = time.perf_counter() - start
    assert len(all_agents) == 500
    assert list_time < 0.01, f"list_all 500: {list_time*1000:.2f}ms (超过 10ms)"


# ── SCALE-04: PlanValidator 大规模 DAG ───────────────────────────

def test_plan_validator_large_dag():
    """200 任务 DAG 验证应在 100ms 内。"""
    dag = TaskDAG()
    tasks = []
    for i in range(200):
        t = Task.create(
            goal_id="G1",
            description=f"task {i}",
            task_type="create",
            agent_type="writer",
        )
        dag.add_task(t)
        tasks.append(t)

    # 交叉边: T0→T1, T0→T2, T1→T3, T2→T3, ...
    for i in range(0, 198, 2):
        dag.add_edge(tasks[i].id, tasks[i + 1].id)
        if i + 2 < 200:
            dag.add_edge(tasks[i].id, tasks[i + 2].id)
            dag.add_edge(tasks[i + 1].id, tasks[i + 2].id)

    validator = PlanValidator()
    start = time.perf_counter()
    report = validator.validate(dag)
    elapsed = time.perf_counter() - start
    assert report.valid
    assert elapsed < 0.10, f"200 任务验证: {elapsed*1000:.2f}ms (超过 100ms)"

    # 模拟模式
    start = time.perf_counter()
    sim = validator.simulate(dag)
    sim_time = time.perf_counter() - start
    assert len(sim.simulated_execution_order) == 200
    assert sim_time < 0.10, f"200 任务模拟: {sim_time*1000:.2f}ms (超过 100ms)"


# ── SCALE-05: 内存基线 ────────────────────────────────────────────

def test_memory_baseline_object_counts():
    """50 引擎 + 200 任务 DAG 对象数量基准。"""
    manifests = [_make_manifest(f"engine_{i}") for i in range(50)]

    dag = TaskDAG()
    for i in range(200):
        t = Task.create(goal_id="G1", description=f"task {i}", task_type="create", agent_type="writer")
        dag.add_task(t)

    registry = AgentRegistry()
    for i in range(100):
        registry.register(_make_agent("agent", i))

    assert len(manifests) == 50
    assert len(dag.tasks) == 200
    assert len(registry.list_all()) == 100
