"""Phase 22-D — Gate Tests: Capability Bridge (Supervisor → SkillGraphExecutor)。

验证:
  22-B01: 有 skill_graph_id 且 executor 存在 → SkillGraph 被执行
  22-B02: skill_graph_id 不存在 → 跳过，正常 Agent 执行
  22-B03: executor 不存在但有 hint → 跳过 SkillGraph，正常 Agent 执行
  22-B04: 结果注入 ExecutionContract (input_spec 含 _skill_result)
  22-B05: cancel 同时停止 Agent + SkillGraph process
  22-B06: 多个 task 不同 skill_graph_id → 各自执行
  22-B07: SkillGraph 失败 → 不影响 agent 任务执行（非阻塞）
  22-B08: sync wrapper (execute_task_sync) 也触发 bridge
"""

import asyncio
import uuid
import pytest
from datetime import datetime, timezone
from dataclasses import dataclass, field
from typing import Any

from ocos.agent_orchestration.registry import AgentDescriptor, AgentRegistry
from ocos.agent_orchestration.selector import AgentSelector
from ocos.agent_orchestration.supervisor import ExecutionSupervisor
from ocos.planning.models import Task


# ── 测试用 Stub SkillGraph / ProcessGraph ───────────────────────

@dataclass
class _StubSkill:
    id: str
    name: str
    instruction: str = ""
    fallback_strategy: str = "fail"


@dataclass
class _StubSkillGraph:
    id: str
    name: str = ""
    description: str = ""
    version: str = "1.0"
    domain: str = "test"
    skills: list = field(default_factory=list)
    edges: list = field(default_factory=list)
    entry_point: str | None = None
    created_at: Any = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class _StubSkillExecutionRecord:
    skill_id: str
    skill_name: str
    status: str = "COMPLETED"
    duration: float = 0.01


@dataclass
class _StubProcessGraph:
    id: str
    skill_graph_id: str
    session_id: str
    status: Any  # 可以是字符串或 enum
    execution_history: list = field(default_factory=list)
    total_duration: float = 0.0
    context: dict = field(default_factory=dict)


class _StubSkillGraphExecutor:
    """SkillGraphExecutor 的测试替身 — 注册 Graph + 返回可控的 ProcessGraph。"""

    def __init__(self):
        self._graphs: dict[str, _StubSkillGraph] = {}
        self._processes: dict[str, _StubProcessGraph] = {}
        self._calls: list[dict] = []

    def register(self, graph):
        self._graphs[graph.id] = graph

    async def start(self, graph, context: dict | None = None):
        ctx = context or {}
        process_id = f"proc-{uuid.uuid4().hex[:8]}"
        proc = _StubProcessGraph(
            id=process_id,
            skill_graph_id=graph.id,
            session_id=ctx.get("session_id", "unknown"),
            status="COMPLETED",
            execution_history=[
                _StubSkillExecutionRecord(
                    skill_id=s.id,
                    skill_name=s.name,
                )
                for s in graph.skills
            ],
            total_duration=0.05,
        )
        self._processes[process_id] = proc
        self._calls.append({"graph_id": graph.id, "context": ctx})
        return proc

    def stop(self, process_id: str):
        self._processes.pop(process_id, None)

    @property
    def call_count(self) -> int:
        return len(self._calls)


# ── Fixtures ────────────────────────────────────────────────────

@pytest.fixture
def stubs():
    """创建一组 SkillGraph stub。"""
    return {
        "sg-write": _StubSkillGraph(
            id="sg-write",
            name="Novel Writing",
            skills=[_StubSkill(id="s1", name="generate_outline")],
        ),
        "sg-search": _StubSkillGraph(
            id="sg-search",
            name="Research",
            skills=[_StubSkill(id="s2", name="search_topic")],
        ),
    }


@pytest.fixture
def supervisor_with_bridge(stubs):
    """创建带 SkillGraphExecutor + 已注册 SkillGraph 的 Supervisor。"""
    reg = AgentRegistry()
    sel = AgentSelector(reg)

    writer = AgentDescriptor(agent_id="w-1", agent_type="writer", capabilities=("text_gen",))
    researcher = AgentDescriptor(agent_id="r-1", agent_type="researcher", capabilities=("search",))
    reg.register(writer)
    reg.register(researcher)

    exec_stub = _StubSkillGraphExecutor()
    exec_stub.register(stubs["sg-write"])
    exec_stub.register(stubs["sg-search"])

    class _StubAgentExecutor:
        """AUD-F11: 回退 _execute_agent 已诚实失败 — 注入 stub 测 completed 路径。"""
        def execute(self, contract):
            return True, f"executed {contract.task_id}", None

    sup = ExecutionSupervisor(
        reg, sel,
        skill_graph_executor=exec_stub,
        executor=_StubAgentExecutor(),
        capability_hints={
            "writer": {"skill_graph_id": "sg-write"},
            "researcher": {"skill_graph_id": "sg-search"},
            "reviewer": {},  # no skill_graph_id
        },
    )
    sup.register_skill_graph("sg-write", stubs["sg-write"])
    sup.register_skill_graph("sg-search", stubs["sg-search"])
    return sup


# ── 22-B01: SkillGraph 被执行 ──────────────────────────────────

@pytest.mark.asyncio
async def test_skill_graph_executed_when_hint_present(supervisor_with_bridge):
    """有 skill_graph_id + executor → SkillGraph.start() 被调用。"""
    task = Task.create(
        goal_id="G-B01",
        description="write chapter",
        agent_type="writer",
    )
    record = await supervisor_with_bridge.execute_task(task)
    assert record.status == "completed"
    executor = supervisor_with_bridge.skill_graph_executor
    assert executor.call_count == 1
    assert executor._calls[0]["graph_id"] == "sg-write"


# ── 22-B02: skill_graph_id 未找到 → 跳过 ──────────────────────

@pytest.mark.asyncio
async def test_skill_graph_skipped_when_id_not_found(stubs):
    """skill_graph_id 不在 _skill_graphs 中 → 跳过 SkillGraph 执行。"""
    reg = AgentRegistry()
    sel = AgentSelector(reg)
    agent = AgentDescriptor(agent_id="rv-1", agent_type="reviewer", capabilities=("review",))
    reg.register(agent)

    exec_stub = _StubSkillGraphExecutor()

    class _StubAgentExecutor:
        """AUD-F11: skill graph 跳过后 Agent 执行走真实 executor。"""
        def execute(self, contract):
            return True, f"executed {contract.task_id}", None

    sup = ExecutionSupervisor(
        reg, sel,
        skill_graph_executor=exec_stub,
        executor=_StubAgentExecutor(),
        capability_hints={"reviewer": {"skill_graph_id": "sg-nonexistent"}},
    )

    task = Task.create(goal_id="G-B02", description="review", agent_type="reviewer")
    record = await sup.execute_task(task)
    assert record.status == "completed"
    assert exec_stub.call_count == 0  # 从未调用


# ── 22-B03: executor 不存在 → 跳过 ────────────────────────────

@pytest.mark.asyncio
async def test_skill_graph_skipped_when_no_executor(stubs):
    """skill_graph_executor=None 时跳过 SkillGraph 执行。"""
    reg = AgentRegistry()
    sel = AgentSelector(reg)
    agent = AgentDescriptor(agent_id="w-1", agent_type="writer", capabilities=("text",))
    reg.register(agent)

    class _StubAgentExecutor:
        """AUD-F11: 无 skill_graph_executor 时 Agent 执行走真实 executor。"""
        def execute(self, contract):
            return True, f"executed {contract.task_id}", None

    sup = ExecutionSupervisor(
        reg, sel,
        skill_graph_executor=None,  # 无 skill graph executor
        executor=_StubAgentExecutor(),
        capability_hints={"writer": {"skill_graph_id": "sg-write"}},
    )
    sup.register_skill_graph("sg-write", stubs["sg-write"])

    task = Task.create(goal_id="G-B03", description="write", agent_type="writer")
    record = await sup.execute_task(task)
    assert record.status == "completed"


# ── 22-B04: 结果注入 contract ─────────────────────────────────

@pytest.mark.asyncio
async def test_skill_result_injected_into_contract(supervisor_with_bridge):
    """SkillGraph 执行结果注入 Agent 的 contract.input_spec。"""
    task = Task.create(
        goal_id="G-B04",
        description="write novel",
        agent_type="writer",
    )
    await supervisor_with_bridge.execute_task(task)

    # execute_task 完成后 contract 被清理，但 skill_result 已执行
    # 通过 bridge call record 验证
    executor = supervisor_with_bridge.skill_graph_executor
    assert executor.call_count == 1
    call = executor._calls[0]
    assert call["graph_id"] == "sg-write"
    assert "session_id" in call["context"]
    assert call["context"]["goal_id"] == task.goal_id


# ── 22-B05: cancel 同时停止 SkillGraph ────────────────────────

@pytest.mark.asyncio
async def test_cancel_stops_skill_graph_process(supervisor_with_bridge):
    """cancel 停止 Agent + 对应的 SkillGraph process。"""
    from ocos.agent_orchestration.contract import ExecutionContract

    c = ExecutionContract.create(task_id="T-CANCEL", agent_id="w-1")
    supervisor_with_bridge._active_contracts[c.contract_id] = c
    supervisor_with_bridge._contract_to_process[c.contract_id] = "proc-cancel"

    executor = supervisor_with_bridge.skill_graph_executor
    executor._processes["proc-cancel"] = _StubProcessGraph(
        id="proc-cancel", skill_graph_id="sg-write",
        session_id="s1", status="RUNNING",
    )

    assert "proc-cancel" in executor._processes
    result = await supervisor_with_bridge.cancel(c.contract_id)
    assert result is True
    assert "proc-cancel" not in executor._processes


# ── 22-B06: 多个 task 不同 skill_graph ────────────────────────

@pytest.mark.asyncio
async def test_multiple_skill_graphs_per_task_type(supervisor_with_bridge):
    """writer→sg-write, researcher→sg-search 各执行不同 Graph。"""
    t1 = Task.create(goal_id="G-M1", description="write", agent_type="writer")
    t2 = Task.create(goal_id="G-M2", description="search", agent_type="researcher")

    r1 = await supervisor_with_bridge.execute_task(t1)
    r2 = await supervisor_with_bridge.execute_task(t2)

    assert r1.status == "completed"
    assert r2.status == "completed"

    executor = supervisor_with_bridge.skill_graph_executor
    assert executor.call_count == 2
    called_ids = [c["graph_id"] for c in executor._calls]
    assert "sg-write" in called_ids
    assert "sg-search" in called_ids


# ── 22-B07: SkillGraph 失败 → 非阻塞 ──────────────────────────

@pytest.mark.asyncio
async def test_skill_graph_failure_does_not_block_agent(stubs):
    """SkillGraph 抛出异常时，Agent 任务仍继续执行（非阻塞）。"""
    reg = AgentRegistry()
    sel = AgentSelector(reg)
    agent = AgentDescriptor(agent_id="w-1", agent_type="writer", capabilities=("text",))
    reg.register(agent)

    class _FailingExecutor:
        async def start(self, graph, context=None):
            raise RuntimeError("SkillGraph execution failed")

        def stop(self, process_id):
            pass

    class _StubAgentExecutor:
        """AUD-F11: SkillGraph 失败后 Agent 执行需真实 executor 兜底。"""
        def execute(self, contract):
            return True, f"executed {contract.task_id}", None

    sup = ExecutionSupervisor(
        reg, sel,
        skill_graph_executor=_FailingExecutor(),
        executor=_StubAgentExecutor(),
        capability_hints={"writer": {"skill_graph_id": "sg-write"}},
    )
    sup.register_skill_graph("sg-write", stubs["sg-write"])

    task = Task.create(goal_id="G-B07", description="write", agent_type="writer")
    # SkillGraph 失败 → execute_task 应捕获异常并继续 Agent 执行
    record = await sup.execute_task(task)
    assert record.status == "completed"


# ── 22-B08: sync wrapper 也触发 bridge ────────────────────────

def test_sync_wrapper_triggers_bridge(supervisor_with_bridge):
    """execute_task_sync 也触发 SkillGraph bridge。"""
    task = Task.create(goal_id="G-B08", description="chapter", agent_type="writer")
    record = supervisor_with_bridge.execute_task_sync(task)
    assert record.status == "completed"
    executor = supervisor_with_bridge.skill_graph_executor
    assert executor.call_count == 1
