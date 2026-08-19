"""Phase 28 — Gate Tests: AgentSelector。

验证:
  28-S01: select best agent (by success_rate)
  28-S02: select by capability match
  28-S03: no available agent → None
  28-S04: select_fallback excludes primary
  28-S05: busy agents excluded
"""

import pytest
from ocos.agent_orchestration.registry import AgentDescriptor, AgentRegistry
from ocos.agent_orchestration.selector import AgentSelector
from ocos.planning.models import Task


def _selector() -> AgentSelector:
    r = AgentRegistry()
    r.register(AgentDescriptor(agent_id="A1", agent_type="writer",
                                capabilities=("generation", "modification"),
                                success_rate=0.95))
    r.register(AgentDescriptor(agent_id="A2", agent_type="writer",
                                capabilities=("generation",),
                                success_rate=0.85))
    r.register(AgentDescriptor(agent_id="A3", agent_type="reviewer",
                                capabilities=("analysis",),
                                success_rate=0.90))
    return AgentSelector(r)


def _task(task_type: str = "create", agent_type: str = "writer") -> Task:
    return Task(
        id="T1", goal_id="G1", description="test",
        task_type=task_type, agent_type=agent_type,
    )


# ── 28-S01: select best agent ────────────────────────────────────

def test_select_best_agent():
    s = _selector()
    task = _task()
    agent = s.select(task)
    assert agent is not None
    assert agent.agent_id == "A1"  # highest success_rate


# ── 28-S02: capability matching ──────────────────────────────────

def test_capability_match_narrows_selection():
    s = _selector()
    # task_type="modify" → capability "modification"
    task = _task(task_type="modify")
    agent = s.select(task)
    assert agent is not None
    # A1 has modification capability, A2 only generation
    assert agent.agent_id == "A1"


# ── 28-S03: no available agent ───────────────────────────────────

def test_no_available_agent():
    r = AgentRegistry()
    r.register(AgentDescriptor(agent_id="A1", agent_type="writer",
                                capabilities=("generation",),
                                status="busy"))
    s = AgentSelector(r)
    assert s.select(_task()) is None


# ── 28-S04: select_fallback ──────────────────────────────────────

def test_select_fallback_excludes_primary():
    s = _selector()
    task = _task()
    fallback = s.select_fallback(task, exclude_id="A1")
    assert fallback is not None
    assert fallback.agent_id == "A2"


def test_no_fallback_when_only_one():
    r = AgentRegistry()
    r.register(AgentDescriptor(agent_id="A1", agent_type="writer",
                                capabilities=("generation",)))
    s = AgentSelector(r)
    assert s.select_fallback(_task(), exclude_id="A1") is None
