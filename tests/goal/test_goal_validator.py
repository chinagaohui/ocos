"""Phase 26 — Gate Tests: GoalValidator。

验证:
  26-V01: validate_source — human ok
  26-V02: validate_source — decomposed needs parent
  26-V03: validate_source — reject self
  26-V04: validate_tree — root must be human
  26-V05: validate_tree — circular detection
  26-V06: validate_tree — children must be decomposed
"""

import pytest
from ocos.goal.validator import GoalValidator
from ocos.goal.models import GoalDomain, GoalSource, UserGoal


def _make_goal(
    goal_id: str,
    source: GoalSource = GoalSource.HUMAN,
    parent_id: str | None = None,
) -> UserGoal:
    return UserGoal(
        id=goal_id,
        raw_input="test",
        objective="test",
        domain=GoalDomain.WRITING,
        source=source,
        parent_id=parent_id,
        caller="orchestrator",
    )


# ── 26-V01: human source valid ──────────────────────────────────────

def test_validate_source_human_ok():
    g = _make_goal("G-1", GoalSource.HUMAN)
    ok, reason = GoalValidator.validate_source(g)
    assert ok
    assert reason == "ok"


def test_validate_source_decomposed_needs_parent():
    g = _make_goal("G-2", GoalSource.DECOMPOSED, parent_id=None)
    ok, reason = GoalValidator.validate_source(g)
    assert not ok
    assert "parent_id" in reason


def test_validate_source_decomposed_with_parent_ok():
    g = _make_goal("G-3", GoalSource.DECOMPOSED, parent_id="G-1")
    ok, reason = GoalValidator.validate_source(g)
    assert ok


# ── 26-V03: reject self source (model-level enforcement) ───────────

def test_validate_source_reject_self():
    """UserGoal 构造拒绝 self 来源。"""
    with pytest.raises(ValueError, match="source"):
        UserGoal(
            id="G-99",
            raw_input="self_generated",
            objective="self_generated",
            domain=GoalDomain.WRITING,
            source="self",  # type: ignore
        )


# ── 26-V04: tree root must be human ─────────────────────────────────

def test_validate_tree_root_human_ok():
    root = _make_goal("G-1", GoalSource.HUMAN)
    ok, reason = GoalValidator.validate_tree(root, [])
    assert ok


def test_validate_tree_root_not_human():
    root = _make_goal("G-1", GoalSource.DECOMPOSED, parent_id=None)
    ok, reason = GoalValidator.validate_tree(root, [])
    assert not ok
    assert "human" in reason


# ── 26-V05: children must be decomposed ─────────────────────────────

def test_validate_tree_child_not_decomposed():
    """子目标必须是 decomposed 来源 — init 层拒绝。"""
    root = _make_goal("G-1", GoalSource.HUMAN)
    # model __post_init__ 拒绝 parent_id + non-decomposed
    with pytest.raises(ValueError, match="parent_id"):
        _make_goal("G-2", GoalSource.HUMAN, parent_id="G-1")


def test_validate_tree_child_missing_parent_id():
    root = _make_goal("G-1", GoalSource.HUMAN)
    child = _make_goal("G-2", GoalSource.DECOMPOSED, parent_id=None)
    ok, reason = GoalValidator.validate_tree(root, [child])
    assert not ok
    assert "parent_id" in reason


# ── 26-V06: valid tree ──────────────────────────────────────────────

def test_validate_tree_valid():
    root = _make_goal("G-1", GoalSource.HUMAN)
    child1 = _make_goal("G-2", GoalSource.DECOMPOSED, parent_id="G-1")
    child2 = _make_goal("G-3", GoalSource.DECOMPOSED, parent_id="G-1")
    ok, reason = GoalValidator.validate_tree(root, [child1, child2])
    assert ok
