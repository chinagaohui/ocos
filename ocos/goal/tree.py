"""Phase 26 — GoalTree: 层级目标分解管理。

宪法约束:
  - max_depth = 3
  - 所有子目标 source = decomposed
  - 叶子节点可执行
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field

from ocos.goal.models import GoalSource, GoalStatus, GoalDomain, UserGoal


MAX_GOAL_TREE_DEPTH = 3


@dataclass
class GoalTree:
    """Goal 层级树。

    管理 UserGoal 的父子关系，支持分解、遍历、完成检测。
    线程安全：所有公开方法由 self._lock 保护。
    """

    root: UserGoal
    children: dict[str, list[UserGoal]] = field(default_factory=dict)
    max_depth: int = MAX_GOAL_TREE_DEPTH

    def __post_init__(self):
        if self.root.source != GoalSource.HUMAN:
            raise ValueError("root must be human-sourced")
        object.__setattr__(self, "_lock", threading.RLock())

    # ── core ──────────────────────────────────────────────────────

    def add_child(self, parent_id: str, child: UserGoal) -> None:
        """添加子目标。

        Raises:
            ValueError: 来源不合法、父目标不存在、深度超限
        """
        with self._lock:
            # 验证 child source
            if child.source != GoalSource.DECOMPOSED:
                raise ValueError(
                    f"child must be decomposed, got {child.source}"
                )
            # 验证 parent 存在
            parent = self._find(parent_id)
            if parent is None:
                raise ValueError(f"parent {parent_id} not found in tree")
            # 验证 parent 非终端态
            if parent.status.is_terminal:
                raise ValueError(
                    f"cannot add child to terminal goal {parent_id}"
                )
            # 验证深度
            depth = self._depth_of(parent_id)
            if depth >= self.max_depth:
                raise ValueError(
                    f"depth {depth + 1} exceeds max_depth {self.max_depth}"
                )
            # 验证 child 的 parent_id 匹配
            if child.parent_id != parent_id:
                raise ValueError("child.parent_id must match parent_id argument")

            self.children.setdefault(parent_id, []).append(child)

    def get_children(self, parent_id: str) -> list[UserGoal]:
        """获取子目标列表。"""
        with self._lock:
            return list(self.children.get(parent_id, []))

    def get_leaves(self) -> list[UserGoal]:
        """获取所有叶子节点（无子节点且状态非终端）。"""
        with self._lock:
            all_nodes = [self.root]
            for clist in self.children.values():
                all_nodes.extend(clist)

            parent_ids = set(self.children.keys())
            return [
                n for n in all_nodes
                if n.id not in parent_ids and not n.status.is_terminal
            ]

    def is_complete(self) -> bool:
        """整棵树已完成（root 终端态 或 所有叶子终端态）。"""
        with self._lock:
            if self.root.status.is_terminal:
                return True
            leaves = self.get_leaves()
            if not leaves:
                return True
            return all(leaf.status.is_terminal for leaf in leaves)

    def all_goals(self) -> list[UserGoal]:
        """返回树中所有 goal。"""
        with self._lock:
            result = [self.root]
            for clist in self.children.values():
                result.extend(clist)
            return result

    def get_depth(self, goal_id: str) -> int:
        """获取 goal 在树中的深度（root=0）。"""
        with self._lock:
            return self._depth_of(goal_id)

    # ── Phase 24-E: goal lifecycle maintenance ───────────────────

    def maintenance(self) -> dict[str, int]:
        """24e1: 自主清理已完成/放弃/过期的 Goal 及子树。

        对每个终端态 Goal（COMPLETED / ABANDONED / CANCELLED / FAILED），
        移除该节点及其所有后代。

        Returns:
            {removed: N, retained: M}
        """
        with self._lock:
            removed = 0
            # 收集终端态 goal IDs
            terminal_ids: set[str] = set()
            for goal in self.all_goals():
                if goal.status.is_terminal:
                    terminal_ids.add(goal.id)

            # 收集所有受影响的 ID（终端节点+其所有后代）
            to_remove: set[str] = set()
            for tid in terminal_ids:
                to_remove.add(tid)
                to_remove.update(self._descendant_ids(tid))

            # 移除 children dict 中的条目
            for goal_id in list(self.children.keys()):
                if goal_id in to_remove:
                    del self.children[goal_id]
                    removed += 1

            # 也移除子条目
            for parent_id in list(self.children.keys()):
                before = len(self.children[parent_id])
                self.children[parent_id] = [
                    c for c in self.children[parent_id]
                    if c.id not in to_remove
                ]
                removed += before - len(self.children[parent_id])

            retained = len(list(self.children.keys()))
            return {"removed": removed, "retained": retained}

    def count_by_status(self) -> dict[str, int]:
        """24e2: 状态机统计 — 各状态 Goal 数量。"""
        with self._lock:
            counts: dict[str, int] = {}
            for goal in self.all_goals():
                s = goal.status.name
                counts[s] = counts.get(s, 0) + 1
            return counts

    def _descendant_ids(self, goal_id: str) -> set[str]:
        """收集 goal_id 的所有后代 IDs。"""
        result: set[str] = set()
        if goal_id not in self.children:
            return result
        for child in self.children[goal_id]:
            result.add(child.id)
            result.update(self._descendant_ids(child.id))
        return result

    # ── internal ──────────────────────────────────────────────────

    def _find(self, goal_id: str) -> UserGoal | None:
        if self.root.id == goal_id:
            return self.root
        for clist in self.children.values():
            for c in clist:
                if c.id == goal_id:
                    return c
        return None

    def _depth_of(self, goal_id: str) -> int:
        if self.root.id == goal_id:
            return 0
        for parent_id, clist in self.children.items():
            for c in clist:
                if c.id == goal_id:
                    return self._depth_of(parent_id) + 1
                # check grandchildren
                if c.id in self.children:
                    d = self._child_depth(c.id, goal_id, 1)
                    if d >= 0:
                        return self._depth_of(parent_id) + d
        return -1

    def _child_depth(self, parent_id: str, target_id: str, depth: int) -> int:
        if parent_id == target_id:
            return depth
        if parent_id not in self.children:
            return -1
        for c in self.children[parent_id]:
            d = self._child_depth(c.id, target_id, depth + 1)
            if d >= 0:
                return d
        return -1
