"""Phase 21 — Thread Safety Tests: AgentRegistry.

验证 AgentRegistry 的 RLock 保护:
  - 并发 register 不产生重复或丢失
  - 并发读写操作安全
"""

import pytest
import threading
import time

from ocos.agent_orchestration.registry import AgentDescriptor, AgentRegistry


def _desc(agent_id: str, agent_type: str = "writer") -> AgentDescriptor:
    return AgentDescriptor(
        agent_id=agent_id,
        agent_type=agent_type,
        capabilities=("generation",),
    )


def test_registry_has_lock():
    """AgentRegistry 初始化后 _lock 存在且为 RLock。"""
    reg = AgentRegistry()
    assert hasattr(reg, "_lock")
    assert isinstance(reg._lock, type(threading.RLock()))


def test_concurrent_register():
    """多线程并发 register：所有 Agent 正确注册无重复。"""
    reg = AgentRegistry()
    n = 30
    errors = []

    def register(i):
        try:
            reg.register(_desc(f"A-{i}"))
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=register, args=(i,)) for i in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(errors) == 0, f"Unexpected errors: {errors}"
    assert len(reg) == n


def test_concurrent_update_status():
    """并发 update_status 不破坏 registry 一致性。"""
    reg = AgentRegistry()
    for i in range(10):
        reg.register(_desc(f"A-{i}", "writer" if i < 5 else "reviewer"))
    errors = []

    def update(i):
        try:
            reg.update_status(f"A-{i}", "busy")
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=update, args=(i,)) for i in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(errors) == 0
    available = reg.get_available("writer")
    assert available is None  # all writers set to busy


def test_concurrent_read_write():
    """并发读写混合操作安全。"""
    reg = AgentRegistry()
    for i in range(5):
        reg.register(_desc(f"A-{i}"))

    errors = []
    stop = threading.Event()

    def writer():
        for i in range(10, 30):
            try:
                reg.register(_desc(f"A-{i}"))
            except Exception as e:
                errors.append(e)
        stop.set()

    def reader():
        while not stop.is_set():
            try:
                reg.list_all()
                reg.find_by_type("writer")
                reg.find_by_capability("generation")
                reg.get_available("writer")
                len(reg)
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
    assert len(reg) >= 5
