"""Phase 21 — Thread Safety Tests: TaskDAG.

验证 TaskDAG 的 RLock 保护:
  - 并发 add_task 不产生重复或丢失
  - 并发读写操作安全
"""

import pytest
import threading
import time

from ocos.planning.models import Task, TaskDAG


def _task(task_id: str, goal_id: str = "g1") -> Task:
    return Task(
        id=task_id,
        goal_id=goal_id,
        description=f"Task {task_id}",
        task_type="execute",
        agent_type="writer",
    )


def test_taskdag_has_lock():
    """TaskDAG 初始化后 _lock 存在且为 RLock。"""
    dag = TaskDAG()
    assert hasattr(dag, "_lock")
    assert isinstance(dag._lock, type(threading.RLock()))


def test_concurrent_add_task():
    """多线程并发 add_task：所有 task 正确添加无重复。"""
    dag = TaskDAG()
    n = 30
    errors = []

    def add(i):
        try:
            dag.add_task(_task(f"T-{i}"))
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=add, args=(i,)) for i in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(errors) == 0, f"Unexpected errors: {errors}"
    assert len(dag.tasks) == n


def test_concurrent_add_edges():
    """并发 add_edge 不破坏 DAG 结构。"""
    dag = TaskDAG()
    for i in range(20):
        dag.add_task(_task(f"T-{i}"))
    errors = []

    def add_edge(i):
        try:
            dag.add_edge(f"T-{i}", f"T-{i + 1}")
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=add_edge, args=(i,)) for i in range(19)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(errors) == 0
    assert len(dag.edges) == 19


def test_concurrent_read_write():
    """并发读写混合操作安全。"""
    dag = TaskDAG()
    for i in range(5):
        dag.add_task(_task(f"T-{i}"))
    dag.add_edge("T-0", "T-1")
    dag.add_edge("T-1", "T-2")

    errors = []
    stop = threading.Event()

    def writer():
        for i in range(10, 30):
            try:
                dag.add_task(_task(f"T-{i}"))
            except Exception as e:
                errors.append(e)
        stop.set()

    def reader():
        while not stop.is_set():
            try:
                dag.validate_acyclic()
                dag.topological_order()
                dag.parallel_groups()
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
