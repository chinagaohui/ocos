"""Phase 28 — Gate Tests: AgentRegistry。

验证:
  28-R01: register_agent
  28-R02: find_by_type
  28-R03: find_by_capability
  28-R04: get_available_only
  28-R05: unregister
  28-R06: update_status
"""

import pytest
from ocos.agent_orchestration.registry import AgentDescriptor, AgentRegistry


@pytest.fixture
def registry() -> AgentRegistry:
    r = AgentRegistry()
    r.register(AgentDescriptor(agent_id="A1", agent_type="writer",
                                capabilities=("generation", "modification")))
    r.register(AgentDescriptor(agent_id="A2", agent_type="reviewer",
                                capabilities=("analysis", "verification"),
                                success_rate=0.85))
    return r


# ── 28-R01: register ─────────────────────────────────────────────

def test_register_agent():
    r = AgentRegistry()
    d = AgentDescriptor(agent_id="A1", agent_type="writer",
                         capabilities=("generation",))
    r.register(d)
    assert len(r) == 1


def test_register_duplicate_rejected(registry):
    with pytest.raises(ValueError, match="already registered"):
        registry.register(AgentDescriptor(
            agent_id="A1", agent_type="writer",
            capabilities=("generation",),
        ))


# ── 28-R02: find_by_type ─────────────────────────────────────────

def test_find_by_type(registry):
    writers = registry.find_by_type("writer")
    assert len(writers) == 1
    assert writers[0].agent_id == "A1"


def test_find_by_type_no_match(registry):
    assert registry.find_by_type("nonexistent") == []


# ── 28-R03: find_by_capability ───────────────────────────────────

def test_find_by_capability(registry):
    result = registry.find_by_capability("generation")
    assert len(result) == 1
    assert result[0].agent_id == "A1"


# ── 28-R04: get_available_only ───────────────────────────────────

def test_get_available_only(registry):
    agent = registry.get_available("writer")
    assert agent is not None
    assert agent.status == "available"


def test_get_available_busy_not_returned(registry):
    registry.update_status("A1", "busy")
    assert registry.get_available("writer") is None


# ── 28-R05: unregister ───────────────────────────────────────────

def test_unregister(registry):
    registry.unregister("A1")
    assert len(registry) == 1
    assert registry.find_by_type("writer") == []


def test_unregister_not_found(registry):
    with pytest.raises(KeyError, match="not found"):
        registry.unregister("X99")


# ── 28-R06: update_status ────────────────────────────────────────

def test_update_status(registry):
    registry.update_status("A1", "busy")
    a = registry.find_by_type("writer")[0]
    assert a.status == "busy"
