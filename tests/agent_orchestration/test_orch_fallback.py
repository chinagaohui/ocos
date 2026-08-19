"""Phase 28 — Gate Tests: FallbackHandler。

验证:
  28-F01: no_retry — 失败即返回
  28-F02: retry_3x — 成功或失败
  28-F03: retry_with_fallback — 降级到备选
"""

import pytest
from ocos.agent_orchestration.fallback import FallbackHandler
from ocos.agent_orchestration.registry import AgentDescriptor


def _agent(aid: str) -> AgentDescriptor:
    return AgentDescriptor(agent_id=aid, agent_type="writer",
                            capabilities=("generation",))


def _always_ok(agent_id: str) -> tuple[bool, str | None]:
    return True, None


def _always_fail(agent_id: str) -> tuple[bool, str | None]:
    return False, f"error from {agent_id}"


def _flaky(agent_id: str) -> tuple[bool, str | None]:
    # 用 counter 控制成功时机
    _flaky.calls += 1
    if _flaky.calls >= 3:
        return True, None
    return False, f"attempt {_flaky.calls} failed"


_flaky.calls = 0


# ── 28-F01: no_retry ─────────────────────────────────────────────

def test_no_retry_success():
    h = FallbackHandler()
    r = h.execute_with_policy(_always_ok, _agent("A1"), None, "no_retry")
    assert r.success
    assert r.attempt == 1


def test_no_retry_failure():
    h = FallbackHandler()
    r = h.execute_with_policy(_always_fail, _agent("A1"), None, "no_retry")
    assert not r.success
    assert r.attempt == 1


# ── 28-F02: retry_3x ────────────────────────────────────────────

def test_retry_3x_eventually_succeeds():
    h = FallbackHandler()
    _flaky.calls = 0
    r = h.execute_with_policy(_flaky, _agent("A1"), None, "retry_3x")
    assert r.success
    assert r.attempt == 3


def test_retry_3x_all_fail():
    h = FallbackHandler()
    r = h.execute_with_policy(_always_fail, _agent("A1"), None, "retry_3x")
    assert not r.success
    assert r.attempt == 3


# ── 28-F03: retry_with_fallback ──────────────────────────────────

def test_retry_with_fallback_primary_succeeds():
    h = FallbackHandler()
    r = h.execute_with_policy(
        _always_ok, _agent("A1"), _agent("A2"), "retry_with_fallback",
    )
    assert r.success
    assert r.agent_id == "A1"
    assert not r.fallback_used


def test_retry_with_fallback_falls_back():
    h = FallbackHandler()
    r = h.execute_with_policy(
        _always_fail, _agent("A1"), _agent("A2"), "retry_with_fallback",
    )
    # A1 fails 3 times → fallback to A2
    assert r.agent_id == "A2"
    assert r.fallback_used


def test_fallback_log():
    h = FallbackHandler()
    h.execute_with_policy(_always_fail, _agent("A1"), _agent("A2"),
                          "retry_with_fallback")
    assert len(h.log) >= 1  # at least the fallback result
