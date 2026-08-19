"""Phase 24-E: Goal lifecycle maintenance 测试。

覆盖:
  24e1: maintenance() 自主清理
  24e2: Goal 状态机完整性
"""
import pytest

from ocos.goal.tree import GoalTree
from ocos.goal.models import UserGoal, GoalSource, GoalStatus, GoalDomain


def _make_root() -> UserGoal:
    return UserGoal(
        id="root",
        raw_input="Test root goal",
        objective="Root objective",
        domain=GoalDomain.ANALYSIS,
        source=GoalSource.HUMAN,
        caller="goal_parser",
    )


def _make_child(parent_id: str, child_id: str, status: GoalStatus = GoalStatus.ACTIVE) -> UserGoal:
    return UserGoal(
        id=child_id,
        raw_input=f"Child {child_id} input",
        objective=f"Child of {parent_id}",
        domain=GoalDomain.ANALYSIS,
        source=GoalSource.DECOMPOSED,
        parent_id=parent_id,
        status=status,
        caller="goal_parser",
    )


# ── 24e1: maintenance() ────────────────────────────────────────


class TestGoalMaintenance:
    def test_removes_completed_child(self):
        tree = GoalTree(root=_make_root())
        tree.add_child("root", _make_child("root", "c1", status=GoalStatus.COMPLETED))
        assert "c1" in [c.id for c in tree.get_children("root")]

        result = tree.maintenance()
        assert result["removed"] >= 1
        assert "c1" not in [c.id for c in tree.get_children("root")]

    def test_removes_abandoned_child(self):
        tree = GoalTree(root=_make_root())
        tree.add_child("root", _make_child("root", "c2", status=GoalStatus.ABANDONED))
        result = tree.maintenance()
        assert result["removed"] >= 1

    def test_preserves_active_child(self):
        tree = GoalTree(root=_make_root())
        tree.add_child("root", _make_child("root", "active", status=GoalStatus.ACTIVE))
        tree.add_child("root", _make_child("root", "done", status=GoalStatus.COMPLETED))

        result = tree.maintenance()
        children = tree.get_children("root")
        assert "active" in [c.id for c in children]
        assert "done" not in [c.id for c in children]

    def test_cascading_removal_partial_tree(self):
        """部分子树完成 → 仅移除终端态子节点及其后代"""
        tree = GoalTree(root=_make_root())
        # c1 ACTIVE with a grandchild
        c1 = _make_child("root", "c1", status=GoalStatus.ACTIVE)
        tree.add_child("root", c1)
        tree.add_child("c1", _make_child("c1", "grand", status=GoalStatus.ACTIVE))
        # c2 COMPLETED (no children, terminal)
        tree.add_child("root", _make_child("root", "c2", status=GoalStatus.COMPLETED))

        tree.maintenance()
        # c1 + grand survive (ACTIVE)
        assert "c1" in [c.id for c in tree.get_children("root")]
        # c2 removed (COMPLETED, terminal)
        assert "c2" not in [c.id for c in tree.get_children("root")]

    def test_empty_tree_returns_zero(self):
        tree = GoalTree(root=_make_root())
        result = tree.maintenance()
        assert result["removed"] == 0

    def test_all_completed_returns_empty(self):
        tree = GoalTree(root=_make_root())
        tree.add_child("root", _make_child("root", "c1", status=GoalStatus.COMPLETED))
        tree.add_child("root", _make_child("root", "c2", status=GoalStatus.ABANDONED))

        tree.maintenance()
        assert tree.get_children("root") == []


# ── 24e2: Goal 状态机 ──────────────────────────────────────────


class TestGoalStateMachine:
    def test_all_states_defined(self):
        """5 种唯一状态（ABANDONED 是 CANCELLED 的别名）"""
        states = {GoalStatus.PENDING, GoalStatus.ACTIVE,
                  GoalStatus.COMPLETED, GoalStatus.CANCELLED,
                  GoalStatus.FAILED}
        assert len(states) == 5

    def test_terminal_states(self):
        assert GoalStatus.COMPLETED.is_terminal
        assert GoalStatus.CANCELLED.is_terminal
        assert GoalStatus.ABANDONED.is_terminal

    def test_pending_to_active(self):
        assert GoalStatus.PENDING.can_transition_to(GoalStatus.ACTIVE)

    def test_active_to_completed(self):
        assert GoalStatus.ACTIVE.can_transition_to(GoalStatus.COMPLETED)

    def test_active_to_abandoned(self):
        assert GoalStatus.ACTIVE.can_transition_to(GoalStatus.ABANDONED)

    def test_terminal_cannot_transition(self):
        assert not GoalStatus.COMPLETED.can_transition_to(GoalStatus.ACTIVE)
        assert not GoalStatus.CANCELLED.can_transition_to(GoalStatus.PENDING)

    def test_count_by_status(self):
        tree = GoalTree(root=_make_root())
        tree.add_child("root", _make_child("root", "c1", status=GoalStatus.ACTIVE))
        tree.add_child("root", _make_child("root", "c2", status=GoalStatus.COMPLETED))

        counts = tree.count_by_status()
        assert counts["ACTIVE"] == 1
        assert counts["COMPLETED"] == 1
        # root is PENDING by default
        assert counts["PENDING"] == 1
