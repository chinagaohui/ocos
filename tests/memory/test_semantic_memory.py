"""Phase 24.3-B — Gate Tests: Semantic Memory Store。

验证:
  24.3-B-01: Validated Pattern → KnowledgeEntry
  24.3-B-02: Rejected Pattern 不可升级
  24.3-B-03: source_pattern lineage 保存
  24.3-B-04: confidence 正确记录
  24.3-B-05: scope 必填
  24.3-B-06: counterexample 可追踪
  24.3-B-07: Knowledge 无 Self 字段
  24.3-B-08: KnowledgeValidator 拦截 Self 语义
  24.3-B-09: Pattern → Knowledge 单向 (frozen)
  24.3-B-10: SemanticStore 查询 (domain/confidence/stability/lineage)
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT))

from ocos.memory.semantic.models import (
    KnowledgeEntry,
    KnowledgeScope,
    KnowledgeStatus,
)
from ocos.memory.semantic.validator import KnowledgeValidator
from ocos.memory.semantic.store import SemanticStore


# ── Helpers ──────────────────────────────────────────────────────────────────


def _make_knowledge(
    statement: str = "在高 CPU 负载下，实时任务超时概率显著增加",
    patterns: list[str] | None = None,
    confidence: float = 0.85,
    stability: float = 0.8,
    domain: str = "resource_management",
    preconditions: tuple[str, ...] = ("cpu>80%",),
    limitations: tuple[str, ...] = ("不适用于离线批处理任务",),
    counterexamples: int = 0,
) -> KnowledgeEntry:
    scope = KnowledgeScope(
        domain=domain,
        preconditions=preconditions,
        limitations=limitations,
        counterexamples=counterexamples,
    )
    # 用 _pat 避免 [] 被 or 短路：None→默认，否则用 caller 值（含 []）
    _pat = patterns if patterns is not None else ["PAT-001", "PAT-002", "PAT-003"]
    return KnowledgeEntry.create(
        statement=statement,
        source_patterns=_pat,
        confidence=confidence,
        scope=scope,
        stability=stability,
    )


def _new_store() -> SemanticStore:
    store = SemanticStore(":memory:")
    store.initialize()
    return store


# ── 24.3-B-01: Pattern → KnowledgeEntry ─────────────────────────────────────


def test_pattern_to_knowledge_creation() -> None:
    """create() 工厂方法应正确生成 KnowledgeEntry。"""
    entry = _make_knowledge()
    assert entry.id.startswith("KNW-")
    assert entry.statement
    assert "CPU" in entry.statement
    assert len(entry.source_patterns) == 3
    assert entry.confidence == 0.85
    assert entry.stability == 0.8
    assert entry.status == KnowledgeStatus.ACTIVE
    assert entry.is_active
    assert entry.scope.domain == "resource_management"
    assert not entry.scope.has_counterexamples()
    assert entry.counterexample_count == 0
    assert "KNW-" in entry.summary()


def test_unstable_knowledge_auto_status() -> None:
    """stability < 0.6 → 自动 UNSTABLE。"""
    entry = _make_knowledge(stability=0.4)
    assert entry.status == KnowledgeStatus.UNSTABLE
    assert entry.is_unstable


# ── 24.3-B-02: Rejected Pattern 不可升级 ────────────────────────────────────


def test_validator_rejects_empty_statement() -> None:
    """空 statement → validator 拒绝。"""
    entry = _make_knowledge(statement="")
    passed, violations, status = KnowledgeValidator.validate(entry)
    assert not passed
    assert status == KnowledgeStatus.DEPRECATED
    assert any("empty statement" in v for v in violations)


# ── 24.3-B-03: source_pattern lineage ────────────────────────────────────────


def test_lineage_preserved() -> None:
    """source_patterns 完整保存。"""
    patterns = ["PAT-001", "PAT-004", "PAT-008"]
    entry = _make_knowledge(patterns=patterns)
    assert list(entry.source_patterns) == patterns


def test_validator_rejects_empty_lineage() -> None:
    """空 source_patterns → validator 拒绝。"""
    entry = _make_knowledge(patterns=[])
    passed, violations, status = KnowledgeValidator.validate(entry)
    assert not passed
    assert any("lineage" in v.lower() for v in violations)


# ── 24.3-B-04: confidence 正确记录 ───────────────────────────────────────────


def test_confidence_recorded() -> None:
    entry = _make_knowledge(confidence=0.72)
    assert entry.confidence == 0.72


# ── 24.3-B-05: scope 必填 ────────────────────────────────────────────────────


def test_validator_rejects_empty_domain() -> None:
    """scope.domain 为空 → validator 拒绝。"""
    entry = _make_knowledge(domain="")
    passed, violations, status = KnowledgeValidator.validate(entry)
    assert not passed
    assert any("domain" in v for v in violations)


# ── 24.3-B-06: counterexample 可追踪 ─────────────────────────────────────────


def test_counterexample_tracking() -> None:
    """counterexamples > 0 → audit 记录 + status → UNSTABLE。"""
    scope = KnowledgeScope(
        domain="test",
        preconditions=("x>0",),
        counterexamples=2,
    )
    entry = KnowledgeEntry.create(
        statement="条件 X 导致结果 Y",
        source_patterns=["PAT-001"],
        confidence=0.8,
        scope=scope,
        stability=0.7,
    )
    assert entry.counterexample_count == 2
    assert entry.scope.has_counterexamples()

    passed, violations, status = KnowledgeValidator.validate(entry)
    assert violations  # 反例被检测
    assert any("counterexamples" in v.lower() for v in violations)
    assert status == KnowledgeStatus.UNSTABLE


# ── 24.3-B-07: 无 Self 字段 ──────────────────────────────────────────────────


def test_knowledge_entry_no_self_fields() -> None:
    """KnowledgeEntry 字段名不含 Self 相关词。"""
    from dataclasses import fields as dc_fields
    field_names = {f.name for f in dc_fields(KnowledgeEntry)}
    forbidden = {"self", "identity", "personality", "persona", "value", "mission", "owner"}
    overlap = field_names & forbidden
    assert len(overlap) == 0, f"KnowledgeEntry has forbidden fields: {overlap}"


# ── 24.3-B-08: Validator 拦截 Self 语义 ──────────────────────────────────────


def test_validator_rejects_first_person() -> None:
    """statement 含 "I am" → 拒绝。"""
    entry = _make_knowledge(statement="I am a system that fails under load")
    passed, violations, _ = KnowledgeValidator.validate(entry)
    assert not passed
    assert any("first-person" in v for v in violations)


def test_validator_rejects_identity_cn() -> None:
    """statement 含 "我是一个" → 拒绝。"""
    entry = _make_knowledge(statement="我是一个不适合高并发的系统")
    passed, violations, _ = KnowledgeValidator.validate(entry)
    assert not passed


def test_validator_rejects_belief_language() -> None:
    """statement 含 "应该" → 拒绝 (Belief, 非 Knowledge)。"""
    entry = _make_knowledge(statement="系统应该始终避免高负载")
    passed, violations, _ = KnowledgeValidator.validate(entry)
    assert not passed
    assert any("belief" in v for v in violations)


def test_validator_accepts_clean_knowledge() -> None:
    """干净的 Knowledge → 通过验证。"""
    entry = _make_knowledge()
    passed, violations, status = KnowledgeValidator.validate(entry)
    assert passed
    assert status == KnowledgeStatus.ACTIVE
    assert len(violations) == 0


# ── 24.3-B-09: Pattern → Knowledge 单向 ─────────────────────────────────────


def test_knowledge_entry_is_immutable() -> None:
    """KnowledgeEntry 是 frozen dataclass。"""
    entry = _make_knowledge()
    with pytest.raises(Exception):
        entry.confidence = 0.5  # type: ignore[misc]


def test_supersede_creates_new_entry() -> None:
    """supersede 创建新版本，不修改原对象。"""
    old = _make_knowledge(patterns=["PAT-001"])
    new = old.supersede(new_pattern_ids=["PAT-002"], new_confidence=0.9)

    # 原对象不变
    assert old.confidence == 0.85
    assert old.revision == 1
    assert list(old.source_patterns) == ["PAT-001"]

    # 新版本
    assert new.revision == 2
    assert new.confidence == 0.9
    assert "PAT-001" in new.source_patterns
    assert "PAT-002" in new.source_patterns
    assert new.id != old.id


# ── 24.3-B-10: SemanticStore 查询 ────────────────────────────────────────────


def test_store_save_and_get() -> None:
    store = _new_store()
    entry = _make_knowledge()
    store.save(entry)
    assert store.count() == 1

    retrieved = store.get(entry.id)
    assert retrieved is not None
    assert retrieved.id == entry.id
    assert retrieved.statement == entry.statement


def test_query_by_domain() -> None:
    store = _new_store()
    e1 = _make_knowledge(domain="networking")
    e2 = _make_knowledge(domain="resource_management")
    e3 = _make_knowledge(domain="networking", confidence=0.6)

    for e in [e1, e2, e3]:
        store.save(e)

    results = store.query_by_domain("networking")
    assert len(results) == 2
    assert all(e.scope.domain == "networking" for e in results)
    # 按 confidence DESC
    assert results[0].confidence >= results[1].confidence


def test_query_by_confidence() -> None:
    store = _new_store()
    store.save(_make_knowledge(confidence=0.9))
    store.save(_make_knowledge(confidence=0.4))

    results = store.query_by_confidence(min_confidence=0.5)
    assert len(results) == 1
    assert results[0].confidence == 0.9


def test_query_by_stability() -> None:
    store = _new_store()
    store.save(_make_knowledge(stability=0.9))
    store.save(_make_knowledge(stability=0.3))

    results = store.query_by_stability(min_stability=0.5)
    assert len(results) == 1
    assert results[0].stability == 0.9


def test_query_by_lineage() -> None:
    store = _new_store()
    store.save(_make_knowledge(patterns=["PAT-001", "PAT-002"]))
    store.save(_make_knowledge(patterns=["PAT-003", "PAT-004"]))

    results = store.query_by_lineage("PAT-001")
    assert len(results) == 1
    assert list(results[0].source_patterns) == ["PAT-001", "PAT-002"]


def test_deprecate() -> None:
    store = _new_store()
    entry = _make_knowledge()
    store.save(entry)

    assert store.deprecate(entry.id) is True
    retrieved = store.get(entry.id)
    assert retrieved is not None
    assert retrieved.status == KnowledgeStatus.DEPRECATED


def test_get_all_active() -> None:
    store = _new_store()
    e1 = _make_knowledge()
    e2 = _make_knowledge(stability=0.4)  # UNSTABLE
    store.save(e1)
    store.save(e2)

    active = store.get_all_active()
    assert len(active) == 1
    assert active[0].status == KnowledgeStatus.ACTIVE


def test_query_by_status() -> None:
    store = _new_store()
    e1 = _make_knowledge()
    store.save(e1)
    store.deprecate(e1.id)

    deprecated = store.query_by_status(KnowledgeStatus.DEPRECATED)
    assert len(deprecated) == 1


# ── 边界案例 ──────────────────────────────────────────────────────────────────


def test_store_empty() -> None:
    store = _new_store()
    assert store.count() == 0
    assert store.get("nonexistent") is None
    assert store.get_all_active() == []


def test_scope_summary() -> None:
    scope = KnowledgeScope(
        domain="test_domain",
        preconditions=("cond1", "cond2"),
        limitations=("lim1",),
        counterexamples=0,
    )
    summary = scope.summary()
    assert "test_domain" in summary
    assert "counter=0" in summary


def test_knowledge_roundtrip_json() -> None:
    """JSON 字段 (source_patterns, preconditions, limitations) 正确往返。"""
    store = _new_store()
    scope = KnowledgeScope(
        domain="resource",
        preconditions=("cpu>80%", "mem<10%"),
        limitations=("not for batch",),
        counterexamples=1,
    )
    entry = KnowledgeEntry.create(
        statement="低资源 → 超时",
        source_patterns=["PAT-001", "PAT-002"],
        confidence=0.75,
        scope=scope,
        stability=0.7,
    )
    store.save(entry)

    retrieved = store.get(entry.id)
    assert retrieved is not None
    assert list(retrieved.source_patterns) == ["PAT-001", "PAT-002"]
    assert tuple(retrieved.scope.preconditions) == ("cpu>80%", "mem<10%")
    assert tuple(retrieved.scope.limitations) == ("not for batch",)
