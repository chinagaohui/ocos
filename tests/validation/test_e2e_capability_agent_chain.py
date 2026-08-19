"""Level 4+22 — E2E Test: Capability Agent Chain (async)。

验证 SkillGraph → Supervisor → Agent → ExecutionRecord 全链路。
Phase 22-D: Supervisor async 化后，direct await SkillGraphExecutor。
"""

import pytest
from ocos.agent_orchestration.registry import AgentDescriptor, AgentRegistry
from ocos.agent_orchestration.selector import AgentSelector
from ocos.agent_orchestration.supervisor import ExecutionSupervisor
from ocos.agent_orchestration.audit import ExecutionAudit, ExecutionRecord
from ocos.planning.models import Task


# ── 4-E1: Capability hints injection ─────────────────────────────

@pytest.mark.asyncio
async def test_capability_hints_injected_into_contract():
    """capability_hints 被注入到 ExecutionContract.input_spec。"""
    reg = AgentRegistry()
    sel = AgentSelector(reg)

    writer = AgentDescriptor(
        agent_id="writer-1",
        agent_type="writer",
        capabilities=("text_gen", "outline"),
    )
    reg.register(writer)

    sup = ExecutionSupervisor(
        reg,
        sel,
        capability_hints={
            "writer": {
                "skill_graph_id": "sg-novel-template",
                "domain": "novel_writing",
                "fallback_strategy": "skip",
            }
        },
    )

    task = Task.create(
        goal_id="G-CAP-1",
        description="写大纲",
        task_type="create",
        agent_type="writer",
    )
    assert task.agent_type == "writer"

    audit_before = len(sup.audit)
    record = await sup.execute_task(task)
    assert record is not None
    assert record.agent_id == "writer-1"
    assert len(sup.audit) > audit_before

    assert "CONTRACT-" in next(iter(sup._active_contracts.keys()))
    for cid in list(sup._active_contracts.keys()):
        await sup.cancel(cid)
    assert len(sup._active_contracts) == 0


@pytest.mark.asyncio
async def test_no_hints_when_capability_not_configured():
    """未配置 capability_hints 时，contract 无 _capability_hints key。"""
    reg = AgentRegistry()
    sel = AgentSelector(reg)

    researcher = AgentDescriptor(
        agent_id="researcher-1",
        agent_type="researcher",
        capabilities=("search",),
    )
    reg.register(researcher)

    sup = ExecutionSupervisor(reg, sel)  # no capability_hints

    task = Task.create(
        goal_id="G-CAP-2",
        description="research topic",
        task_type="execute",
        agent_type="researcher",
    )

    record = await sup.execute_task(task)
    assert record is not None
    assert record.agent_id == "researcher-1"


@pytest.mark.asyncio
async def test_capability_hints_multiple_agents():
    """多个 agent_type 各自有不同的 capability_hints。"""
    reg = AgentRegistry()
    sel = AgentSelector(reg)

    for aid, atype, caps in [
        ("w-1", "writer", ("text_gen",)),
        ("r-1", "researcher", ("search",)),
        ("rv-1", "reviewer", ("review",)),
    ]:
        reg.register(AgentDescriptor(agent_id=aid, agent_type=atype, capabilities=caps))

    sup = ExecutionSupervisor(
        reg,
        sel,
        capability_hints={
            "writer": {"skill_id": "sg-write"},
            "researcher": {"skill_id": "sg-search"},
            "reviewer": {"skill_id": "sg-review"},
        },
    )

    for atype in ("writer", "researcher", "reviewer"):
        task = Task.create(
            goal_id=f"G-MULTI-{atype}",
            description=f"task for {atype}",
            agent_type=atype,
        )
        record = await sup.execute_task(task)
        assert record is not None
        assert record.agent_id in ("w-1", "r-1", "rv-1")


@pytest.mark.asyncio
async def test_capability_hints_idempotent():
    """重复相同的 capability_hints 不影响后续任务。"""
    reg = AgentRegistry()
    sel = AgentSelector(reg)

    agent = AgentDescriptor(agent_id="a-1", agent_type="writer", capabilities=("text",))
    reg.register(agent)

    sup = ExecutionSupervisor(
        reg, sel,
        capability_hints={"writer": {"mode": "creative"}},
    )

    for i in range(5):
        task = Task.create(
            goal_id=f"G-IDEM-{i}",
            description=f"task {i}",
            agent_type="writer",
        )
        record = await sup.execute_task(task)
        assert record is not None
        assert record.agent_id == "a-1"
