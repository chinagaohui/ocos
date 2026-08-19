"""Phase 21 — Thread Safety Tests: GoalTree.

验证 GoalTree 的 RLock 保护:
  - 并发 add_child 不产生数据损坏
  - 并发读写操作安全
"""

import pytest
import threading
import time

from ocos.goal.tree import GoalTree
from ocos.goal.models import GoalDomain, GoalSource, GoalStatus, UserGoal


def _root() -> UserGoal:
    return UserGoal(
        id="G-root",
        raw_input="写小说",
        objective="创作小说",
        domain=GoalDomain.WRITING,
        source=GoalSource.HUMAN,
        caller="orchestrator",
    )


def _child(parent_id: str, child_id: str) -> UserGoal:
    return UserGoal(
        id=child_id,
        raw_input=f"子任务 {child_id}",
        objective=f"子任务 {child_id}",
        domain=GoalDomain.WRITING,
        source=GoalSource.DECOMPOSED,
        parent_id=parent_id,
        caller="orchestrator",
    )


def test_goal_tree_has_lock():
    """GoalTree 初始化后 _lock 存在且为 RLock。"""
    tree = GoalTree(_root())
    assert hasattr(tree, "_lock")
    assert isinstance(tree._lock, type(threading.RLock()))


def test_concurrent_add_child_same_parent():
    """多线程向同一父节点并发 add_child：最终子节点数正确。"""
    tree = GoalTree(_root())
    n = 20
    errors = []

    def add_child(i):
        try:
            c = _child("G-root", f"G-{i}")
            tree.add_child("G-root", c)
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=add_child, args=(i,)) for i in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(errors) == 0, f"Unexpected errors: {errors}"
    children = tree.get_children("G-root")
    assert len(children) == n


def test_concurrent_read_write():
    """一个线程写 + 多线程读：不发生异常或数据损坏。"""
    tree = GoalTree(_root())
    errors = []
    stop = threading.Event()

    def writer():
        for i in range(30):
            try:
                c = _child("G-root", f"G-w-{i}")
                tree.add_child("G-root", c)
            except Exception as e:
                errors.append(e)
        stop.set()

    def reader():
        while not stop.is_set():
            try:
                tree.get_children("G-root")
                tree.get_leaves()
                tree.is_complete()
                tree.all_goals()
                tree.get_depth("G-root")
            except Exception as e:
                errors.append(e)
            time.sleep(0.001)

    w = threading.Thread(target=writer)
    readers = [threading.Thread(target=reader) for _ in range(3)]
    w.start()
    for r in readers:
        r.start()
    w.join()
    for r in readers:
        r.join()

    assert len(errors) == 0, f"Unexpected errors: {errors}"
    assert len(tree.get_children("G-root")) == 30
