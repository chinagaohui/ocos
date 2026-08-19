"""GoalStack — 6 级目标栈。

GoalStack 管理从 MISSION 到 ACTION 的 6 级目标层级。
支持 push / pop / peek / get_active / get_highest_priority。

Phase 21: 可选 GoalSQLiteStore 持久化 —— push/pop/cancel 时自动同步。
"""

from __future__ import annotations

import threading
from typing import Optional, TYPE_CHECKING

from ocos.agent.goal_types import Goal, GoalLevel, GoalStatus

if TYPE_CHECKING:
    from ocos.agent.goal_store import GoalSQLiteStore


class GoalStack:
    """6 级目标栈。

    每级一个栈。push 时根据 level 放入对应栈。
    peek 返回当前最高优先级的 ACTIVE 目标。

    Phase 21: 若提供 store，所有写操作自动同步持久化。
    """

    def __init__(self, store: GoalSQLiteStore | None = None) -> None:
        self._stacks: dict[GoalLevel, list[Goal]] = {
            level: [] for level in GoalLevel
        }
        self._lock = threading.Lock()
        self._store = store

    # ── Phase 21: Store access ───────────────────────────────────────────────

    @property
    def store(self) -> GoalSQLiteStore | None:
        return self._store

    def set_store(self, store: GoalSQLiteStore | None) -> None:
        """设置/替换持久化 store。"""
        self._store = store

    def restore_from_store(self) -> int:
        """从 store 恢复 ACTIVE/PENDING 目标。返回恢复数量。"""
        if self._store is None:
            return 0
        goals = self._store.load_active()
        with self._lock:
            for goal in goals:
                self._stacks[goal.level].append(goal)
        return len(goals)

    # ── Operations ───────────────────────────────────────────────────────────

    def push(self, goal: Goal) -> None:
        """压入目标。"""
        with self._lock:
            goal.status = GoalStatus.ACTIVE
            self._stacks[goal.level].append(goal)
        # Phase 21: persist
        if self._store:
            self._store.save(goal)

    def pop(self) -> Optional[Goal]:
        """弹出当前 level 的最高优先级目标。"""
        with self._lock:
            for level in sorted(GoalLevel, key=lambda x: x.value):
                stack = self._stacks[level]
                if stack:
                    goal = stack.pop()
                    goal.status = GoalStatus.COMPLETED
                    # Phase 21: persist status change
                    if self._store:
                        self._store.save(goal)
                    return goal
            return None

    def peek(self) -> Optional[Goal]:
        """查看当前最高优先级目标（不移除）。"""
        with self._lock:
            for level in sorted(GoalLevel, key=lambda x: x.value):
                stack = self._stacks[level]
                if stack:
                    return stack[-1]
            return None

    def get_active(self) -> list[Goal]:
        """获取所有 ACTIVE 状态的目标。"""
        with self._lock:
            result = []
            for stack in self._stacks.values():
                for goal in stack:
                    if goal.status == GoalStatus.ACTIVE:
                        result.append(goal)
            return result

    def get_highest_priority(self) -> Optional[Goal]:
        """获取当前优先级最高的目标。"""
        with self._lock:
            max_priority: float = -1.0
            best: Optional[Goal] = None
            for stack in self._stacks.values():
                for goal in stack:
                    if goal.status == GoalStatus.ACTIVE and goal.priority > max_priority:
                        max_priority = goal.priority
                        best = goal
            return best

    def cancel(self, goal_id: str) -> bool:
        """取消指定 ID 的目标。"""
        with self._lock:
            for stack in self._stacks.values():
                for goal in stack:
                    if goal.goal_id == goal_id and goal.status == GoalStatus.ACTIVE:
                        goal.status = GoalStatus.CANCELLED
                        if self._store:
                            self._store.save(goal)
                        return True
            return False

    def depth(self) -> int:
        """总目标数。"""
        with self._lock:
            return sum(len(stack) for stack in self._stacks.values())

    def clear(self) -> None:
        """清空所有目标。"""
        with self._lock:
            for stack in self._stacks.values():
                stack.clear()
