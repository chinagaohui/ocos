"""Phase 26 — Gate Tests: GoalTracker。

验证:
  26-K01: start → progress 0.0
  26-K02: update → progress 正确
  26-K03: complete → 100% + is_complete
  26-K04: track multiple goals
"""

import time
import pytest
from ocos.goal.tracker import GoalTracker
from ocos.goal.models import GoalDomain, GoalSource, UserGoal


def _goal(gid: str = "G-1") -> UserGoal:
    return UserGoal(
        id=gid,
        raw_input="写小说",
        objective="创作",
        domain=GoalDomain.WRITING,
        source=GoalSource.HUMAN,
        caller="orchestrator",
    )


# ── 26-K01: start ──────────────────────────────────────────────────

def test_start_initializes_progress():
    tracker = GoalTracker()
    g = _goal()
    tracker.start(g)
    assert tracker.get_progress("G-1") == 0.0
    assert tracker.is_started("G-1")
    assert not tracker.is_complete("G-1")


def test_unstarted_goal_progress_zero():
    tracker = GoalTracker()
    assert tracker.get_progress("G-99") == 0.0
    assert not tracker.is_started("G-99")


# ── 26-K02: update ─────────────────────────────────────────────────

def test_update_progress():
    tracker = GoalTracker()
    g = _goal()
    tracker.start(g)
    tracker.update("G-1", 0.5, "half done")
    assert tracker.get_progress("G-1") == 0.5
    assert "half done" in tracker.get_notes("G-1")[-1]


def test_update_progress_invalid_range():
    tracker = GoalTracker()
    with pytest.raises(ValueError, match="progress"):
        tracker.update("G-1", 1.5)


def test_update_without_note():
    tracker = GoalTracker()
    g = _goal()
    tracker.start(g)
    tracker.update("G-1", 0.3)
    assert tracker.get_progress("G-1") == 0.3


# ── 26-K03: complete ───────────────────────────────────────────────

def test_complete_sets_full_progress():
    tracker = GoalTracker()
    g = _goal()
    tracker.start(g)
    tracker.update("G-1", 0.8)
    tracker.complete("G-1", "done!")
    assert tracker.get_progress("G-1") == 1.0
    assert tracker.is_complete("G-1")
    assert "done!" in tracker.get_notes("G-1")[-1]


def test_complete_without_note():
    tracker = GoalTracker()
    g = _goal()
    tracker.start(g)
    tracker.complete("G-1")
    assert tracker.is_complete("G-1")


# ── 26-K04: multiple goals ─────────────────────────────────────────

def test_track_multiple_goals():
    tracker = GoalTracker()
    g1 = _goal("G-1")
    g2 = _goal("G-2")
    tracker.start(g1)
    tracker.start(g2)
    tracker.update("G-1", 0.7)
    tracker.update("G-2", 0.3)
    assert tracker.get_progress("G-1") == 0.7
    assert tracker.get_progress("G-2") == 0.3


def test_get_elapsed():
    tracker = GoalTracker()
    g = _goal()
    tracker.start(g)
    elapsed = tracker.get_elapsed("G-1")
    assert elapsed is not None
    assert elapsed >= 0.0


def test_get_elapsed_unstarted():
    tracker = GoalTracker()
    assert tracker.get_elapsed("G-99") is None
