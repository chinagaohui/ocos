"""Level 4 — E2E Test: SQLite Connection Lifecycle.

验证 3 个 Memory Store 的 context manager：
  - __enter__ / __exit__ 正确工作
  - with 退出后连接关闭
  - 异常传播时不静默吞异常
  - initialize() + close() 仍可用
"""

import pytest
from ocos.memory.belief.store import BeliefStore
from ocos.memory.episode.store import EpisodeStore
from ocos.memory.semantic.store import SemanticStore


# ── 4-E8: Context Manager Basics ──────────────────────────────────────────


def test_belief_store_context_manager():
    """BeliefStore 支持 with statement。"""
    with BeliefStore() as store:
        assert store._conn is not None
        assert isinstance(store, BeliefStore)
    # 退出后连接关闭
    assert store._conn is None
    print("PASS: BeliefStore context manager")


def test_episode_store_context_manager():
    """EpisodeStore 支持 with statement。"""
    with EpisodeStore() as store:
        assert store._conn is not None
    assert store._conn is None
    print("PASS: EpisodeStore context manager")


def test_semantic_store_context_manager():
    """SemanticStore 支持 with statement。"""
    with SemanticStore() as store:
        assert store._conn is not None
    assert store._conn is None
    print("PASS: SemanticStore context manager")


# ── 4-E9: Exception Propagation ──────────────────────────────────────────


def test_store_context_manager_propagates_exception():
    """with 块中抛异常时，不静默吞异常，连接仍关闭。"""
    store = BeliefStore()  # 在 try 之前声明
    try:
        with store as bs:
            assert bs._conn is not None
            raise RuntimeError("simulated failure")
    except RuntimeError as e:
        assert str(e) == "simulated failure"
    # 异常后连接仍关闭
    assert store._conn is None
    print("PASS: exception propagated, connection closed")

    store2 = EpisodeStore()
    try:
        with store2 as es:
            assert es._conn is not None
            raise ValueError("episode error")
    except ValueError:
        pass
    assert store2._conn is None


# ── 4-E10: Backward Compat (initialize/close) ────────────────────────────


def test_manual_initialize_close_still_works():
    """initialize() + close() 仍然可用（向后兼容）。"""
    bs = BeliefStore()
    assert bs._conn is None
    bs.initialize()
    assert bs._conn is not None
    bs.close()
    assert bs._conn is None
    print("PASS: manual initialize/close")

    es = EpisodeStore()
    es.initialize()
    es.close()
    assert es._conn is None

    ss = SemanticStore()
    ss.initialize()
    ss.close()
    assert ss._conn is None


# ── 4-E11: Nested Context Managers ──────────────────────────────────────


def test_nested_context_managers():
    """嵌套使用多个 Store 互不干扰。"""
    with BeliefStore() as bs:
        with EpisodeStore() as es:
            with SemanticStore() as ss:
                assert bs._conn is not None
                assert es._conn is not None
                assert ss._conn is not None
                # 三个不同的连接
                assert bs._conn is not es._conn
                assert es._conn is not ss._conn
    assert bs._conn is None
    assert es._conn is None
    assert ss._conn is None
    print("PASS: nested context managers")


# ── 4-E12: Double close is safe ─────────────────────────────────────────


def test_double_close_is_safe():
    """重复 close() 不抛异常（幂等）。"""
    bs = BeliefStore()
    bs.initialize()
    bs.close()
    bs.close()  # 第二次应该安全
    assert bs._conn is None
    print("PASS: double close is safe")
