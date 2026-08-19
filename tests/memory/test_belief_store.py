"""Phase 24.4-C — Gate Tests: BeliefStore + Query。

验证:
  24.4-C-01: save + get roundtrip
  24.4-C-02: weaken / invalidate / archive 生命周期
  24.4-C-03: query_by_status
  24.4-C-04: query_by_confidence
  24.4-C-05: query_by_domain
  24.4-C-06: query_by_lineage
  24.4-C-07: get_all_active
  24.4-C-08: count_by_status
  24.4-C-09: empty store
  24.4-C-10: save 幂等 (OR REPLACE)
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT))

from ocos.memory.belief.models import Belief, BeliefStatus, Evidence
from ocos.memory.belief.store import BeliefStore
from ocos.memory.belief.evidence import EvidenceBinding
from ocos.memory.semantic.models import KnowledgeEntry, KnowledgeScope


# ── Helpers ──────────────────────────────────────────────────────────────────


def _belief(
    statement: str = "资源不足时任务完成概率下降",
    confidence: float = 0.85,
    uncertainty: float = 0.15,
    domain: str = "resource_management",
    status: BeliefStatus = BeliefStatus.ACTIVE,
) -> Belief:
    return Belief.create(
        statement=statement,
        source_knowledge_ids=["KNW-001"],
        evidence_ids=["EVD-001", "EVD-002", "EVD-003"],
        confidence=confidence,
        uncertainty=uncertainty,
        scope={"domain": domain, "preconditions": ["cpu>80%"]},
    )


def _setup_store() -> BeliefStore:
    store = BeliefStore(":memory:")
    store.initialize()
    return store


# ── 24.4-C-01: save + get ────────────────────────────────────────────────────


def test_save_and_get_roundtrip() -> None:
    """保存后 roundtrip 获取一致。"""
    store = _setup_store()
    belief = _belief(statement="复杂任务需要精确指令")

    store.save(belief)
    retrieved = store.get(belief.id)

    assert retrieved is not None
    assert retrieved.id == belief.id
    assert retrieved.statement == belief.statement
    assert list(retrieved.source_knowledge_ids) == list(belief.source_knowledge_ids)
    assert list(retrieved.evidence_ids) == list(belief.evidence_ids)
    assert retrieved.confidence == belief.confidence
    assert retrieved.uncertainty == belief.uncertainty
    assert retrieved.status == belief.status
    assert retrieved.scope == belief.scope


def test_get_nonexistent() -> None:
    """不存在 → None。"""
    store = _setup_store()
    assert store.get("BLF-NOT-EXISTS") is None


# ── 24.4-C-02: 生命周期 ──────────────────────────────────────────────────────


def test_weaken_lifecycle() -> None:
    """weaken → WEAKENED, uncertainty↑"""
    store = _setup_store()
    belief = _belief()
    store.save(belief)

    result = store.weaken(belief.id)
    assert result is not None
    assert result.status == BeliefStatus.WEAKENED
    assert result.uncertainty > belief.uncertainty

    # 持久化生效
    retrieved = store.get(belief.id)
    assert retrieved.status == BeliefStatus.WEAKENED


def test_invalidate_lifecycle() -> None:
    """invalidate → INVALIDATED, is_active=False"""
    store = _setup_store()
    belief = _belief()
    store.save(belief)

    result = store.invalidate(belief.id)
    assert result is not None
    assert result.status == BeliefStatus.INVALIDATED
    assert not result.is_active

    retrieved = store.get(belief.id)
    assert not retrieved.is_active


def test_archive_lifecycle() -> None:
    """archive → ARCHIVED"""
    store = _setup_store()
    belief = _belief()
    store.save(belief)

    result = store.archive(belief.id)
    assert result is not None
    assert result.status == BeliefStatus.ARCHIVED

    retrieved = store.get(belief.id)
    assert retrieved.status == BeliefStatus.ARCHIVED


def test_lifecycle_on_nonexistent() -> None:
    """不存在的 Belief → 生命周期操作返回 None。"""
    store = _setup_store()
    assert store.weaken("NOPE") is None
    assert store.invalidate("NOPE") is None
    assert store.archive("NOPE") is None


# ── 24.4-C-03: query_by_status ───────────────────────────────────────────────


def test_query_by_status_active() -> None:
    """按 ACTIVE 状态查询。"""
    store = _setup_store()
    for i in range(3):
        store.save(_belief(confidence=0.8 + i * 0.05))
    store.save(_belief(confidence=0.4))  # auto WEAKENED

    active = store.query_by_status(BeliefStatus.ACTIVE)
    assert len(active) == 3


def test_query_by_status_weakened() -> None:
    """按 WEAKENED 查询 (低 confidence 自动)。"""
    store = _setup_store()
    store.save(_belief(confidence=0.3))
    store.save(_belief(confidence=0.85))

    weakened = store.query_by_status(BeliefStatus.WEAKENED)
    assert len(weakened) == 1

    active = store.query_by_status(BeliefStatus.ACTIVE)
    assert len(active) == 1


# ── 24.4-C-04: query_by_confidence ───────────────────────────────────────────


def test_query_by_confidence_range() -> None:
    """按置信度范围查询。"""
    store = _setup_store()
    for c in [0.6, 0.7, 0.8, 0.9]:
        store.save(_belief(confidence=c))

    high = store.query_by_confidence(min_confidence=0.8)
    assert len(high) == 2

    mid = store.query_by_confidence(min_confidence=0.6, max_confidence=0.7)
    assert len(mid) == 2


def test_query_by_confidence_desc_order() -> None:
    """按 confidence 降序返回。"""
    store = _setup_store()
    store.save(_belief(confidence=0.6))
    store.save(_belief(confidence=0.9))
    store.save(_belief(confidence=0.7))

    results = store.query_by_confidence()
    assert results[0].confidence >= results[1].confidence >= results[2].confidence


# ── 24.4-C-05: query_by_domain ───────────────────────────────────────────────


def test_query_by_domain() -> None:
    """按 domain 查询。"""
    store = _setup_store()
    store.save(_belief(domain="resource", confidence=0.9))
    store.save(_belief(domain="resource", confidence=0.8))
    store.save(_belief(domain="context", confidence=0.7))

    resource = store.query_by_domain("resource")
    assert len(resource) == 2

    context = store.query_by_domain("context")
    assert len(context) == 1


def test_query_by_domain_no_match() -> None:
    """不存在的 domain → 空。"""
    store = _setup_store()
    assert len(store.query_by_domain("nonexistent")) == 0


# ── 24.4-C-06: query_by_lineage ──────────────────────────────────────────────


def test_query_by_lineage() -> None:
    """按 Knowledge ID 追溯。"""
    store = _setup_store()
    b1 = Belief.create(
        statement="test1",
        source_knowledge_ids=["KNW-A", "KNW-B"],
        evidence_ids=["EVD-001", "EVD-002", "EVD-003"],
        confidence=0.8,
        uncertainty=0.2,
        scope={"domain": "test"},
    )
    b2 = Belief.create(
        statement="test2",
        source_knowledge_ids=["KNW-B", "KNW-C"],
        evidence_ids=["EVD-004", "EVD-005", "EVD-006"],
        confidence=0.7,
        uncertainty=0.3,
        scope={"domain": "test"},
    )
    store.save(b1)
    store.save(b2)

    from_knw_a = store.query_by_lineage("KNW-A")
    assert len(from_knw_a) == 1
    assert from_knw_a[0].id == b1.id

    from_knw_b = store.query_by_lineage("KNW-B")
    assert len(from_knw_b) == 2


# ── 24.4-C-07: get_all_active ────────────────────────────────────────────────


def test_get_all_active() -> None:
    """get_all_active 返回所有活跃 Belief。"""
    store = _setup_store()
    for _ in range(5):
        store.save(_belief(confidence=0.8))
    store.save(_belief(confidence=0.3))  # WEAKENED

    active = store.get_all_active()
    assert len(active) == 5

    # 按 confidence 降序
    for i in range(len(active) - 1):
        assert active[i].confidence >= active[i + 1].confidence


def test_get_all_active_empty() -> None:
    """无活跃 Belief → 空列表。"""
    store = _setup_store()
    assert store.get_all_active() == []


# ── 24.4-C-08: count_by_status ───────────────────────────────────────────────


def test_count_by_status() -> None:
    """统计各状态 Belief 数量。"""
    store = _setup_store()
    store.save(_belief(confidence=0.8))
    store.save(_belief(confidence=0.85))
    store.save(_belief(confidence=0.3))
    store.save(_belief(confidence=0.9))

    counts = store.count_by_status()
    assert counts["active"] == 3
    assert counts["weakened"] == 1


# ── 24.4-C-09: empty store ───────────────────────────────────────────────────


def test_empty_store_all_operations_safe() -> None:
    """空 store 所有操作安全。"""
    store = _setup_store()

    assert store.get("any") is None
    assert store.get_all_active() == []
    assert store.query_by_status(BeliefStatus.ACTIVE) == []
    assert store.query_by_confidence() == []
    assert store.query_by_domain("any") == []
    assert store.query_by_lineage("any") == []
    assert store.count_by_status() == {}
    assert store.weaken("any") is None
    assert store.invalidate("any") is None
    assert store.archive("any") is None


# ── 24.4-C-10: 幂等 ─────────────────────────────────────────────────────────


def test_save_idempotent() -> None:
    """save 幂等 — OR REPLACE 语义。"""
    store = _setup_store()
    belief = _belief(confidence=0.8)
    store.save(belief)

    # 修改后重新保存
    updated = belief.weaken()
    store.save(updated)

    retrieved = store.get(belief.id)
    assert retrieved.status == BeliefStatus.WEAKENED

    # 只有一条记录
    all_active = store.query_by_status(BeliefStatus.WEAKENED)
    assert len(all_active) == 1


# ── 边界: Query 不产生 Goal ──────────────────────────────────────────────────


def test_query_methods_no_side_effects() -> None:
    """查询方法纯读取，不产生 Goal/Self/Behavior。"""
    store = _setup_store()
    store.save(_belief())

    # 所有查询方法只是返回数据
    result = store.query_by_domain("resource_management")
    assert isinstance(result, list)

    # get_all_active 是纯读取
    active = store.get_all_active()
    assert isinstance(active, list)

    # Store 本身无 Goal / Self 引用
    assert not hasattr(store, "goal")
    assert not hasattr(store, "priority")
    assert not hasattr(store, "identity")
