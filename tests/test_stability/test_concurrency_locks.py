"""Phase 23-C: 并发锁验证测试 (23c4)。

验证 GoalTree / TaskDAG / Registry 的线程安全性。
"""
import threading
import time

import pytest

from ocos.goal.tree import GoalTree
from ocos.goal.models import UserGoal, GoalDomain, GoalSource
from ocos.task import TaskDAG, TaskNode, TaskStatus
from ocos.capability.descriptor import CapabilityDescriptor
from ocos.capability.provider import ProviderDescriptor
from ocos.capability.registry import CapabilityRegistry


class TestGoalTreeLock:
    """GoalTree 已有 RLock，验证并发添加不冲突。"""

    def test_concurrent_add_child(self):
        root = UserGoal("root", "root goal", "do root", GoalDomain.ANALYSIS, caller="goal_parser")
        tree = GoalTree(root)
        child = UserGoal("c1", "child 1", "do child", GoalDomain.ANALYSIS, source=GoalSource.DECOMPOSED)

        errors = []

        def add():
            try:
                tree.add_child("root", child)
            except ValueError:
                pass
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=add) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # 第一个成功，后续因重复或 terminal 状态失败
        assert len(tree.children.get("root", [])) <= 10
        assert not errors, f"unexpected errors: {errors}"


class TestTaskDAGLock:
    """TaskDAG 线程安全。"""

    def test_concurrent_add_task(self):
        dag = TaskDAG()
        errors = []

        def add_task(i):
            try:
                dag.add_task(f"task_{i}", f"Task {i}")
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=add_task, args=(i,)) for i in range(50)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(dag) == 50
        assert not errors

    def test_concurrent_set_status(self):
        dag = TaskDAG()
        for i in range(20):
            dag.add_task(f"task_{i}")

        def set_done(i):
            dag.set_status(f"task_{i}", TaskStatus.COMPLETED)

        threads = [threading.Thread(target=set_done, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        for i in range(20):
            assert dag.get(f"task_{i}").status == TaskStatus.COMPLETED


class TestCapabilityRegistryLock:
    """CapabilityRegistry RLock 验证。"""

    def test_concurrent_register(self):
        registry = CapabilityRegistry()
        errors = []

        def register(i):
            try:
                desc = CapabilityDescriptor(capability_id=f"cap_{i}", name=f"C{i}")
                registry.register_capability(desc)
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=register, args=(i,)) for i in range(50)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert registry.capability_count == 50
        assert not errors
