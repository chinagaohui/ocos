"""Phase 24.4-A — Gate Tests: Belief Model + Evidence Binding。

验证:
  24.4-A-01: Knowledge + Evidence → Belief
  24.4-A-02: 证据不足拒绝 (n < 3)
  24.4-A-03: 低质量 Evidence 拒绝 (avg_quality < 0.5)
  24.4-A-04: uncertainty 必须存在 (不可 None)
  24.4-A-05: Self 字段污染拒绝
  24.4-A-06: Identity 推导阻断
  24.4-A-07: Goal/Belief 修改阻断
  24.4-A-08: Evidence lineage 可追踪 (Belief→Knowledge→Evidence→Episode)
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT))

from ocos.memory.belief.models import Belief, BeliefStatus, Evidence
from ocos.memory.belief.evidence import EvidenceBinding
from ocos.memory.belief.validator import BeliefValidator
from ocos.memory.semantic.models import KnowledgeEntry, KnowledgeScope


# ── Helpers ──────────────────────────────────────────────────────────────────


def _make_evidence(
    source_episode_id: str = "EPI-001",
    source_pattern_id: str = "PAT-001",
    quality: float = 0.8,
    consistency: float = 0.9,
) -> Evidence:
    return Evidence.create(
        source_episode_id=source_episode_id,
        source_pattern_id=source_pattern_id,
        quality=quality,
        consistency_score=consistency,
    )


def _make_knowledge(
    statement: str = "在低资源环境下，实时任务超时概率显著增加",
    confidence: float = 0.85,
    counterexamples: int = 0,
) -> KnowledgeEntry:
    scope = KnowledgeScope(
        domain="resource_management",
        preconditions=("cpu>80%",),
    )
    return KnowledgeEntry.create(
        statement=statement,
        source_patterns=["PAT-001", "PAT-002", "PAT-003"],
        confidence=confidence,
        scope=scope,
        stability=0.8,
    )


def _evidence_set(n: int = 3, quality: float = 0.8) -> list[Evidence]:
    return [
        _make_evidence(
            source_episode_id=f"EPI-{i:03d}",
            source_pattern_id=f"PAT-{i:03d}",
            quality=quality,
        )
        for i in range(n)
    ]


# ── 24.4-A-01: Knowledge + Evidence → Belief ───────────────────────────────


def test_knowledge_plus_evidence_binds_to_belief() -> None:
    """三个高质量 Evidence + Knowledge → Belief 成功生成。"""
    knowledge = _make_knowledge()
    evidence = _evidence_set(n=3, quality=0.8)

    binding = EvidenceBinding()
    belief = binding.bind(knowledge, evidence)

    assert belief is not None
    assert belief.statement == knowledge.statement
    assert belief.evidence_count == 3
    assert len(belief.source_knowledge_ids) == 1
    assert belief.source_knowledge_ids[0] == knowledge.id
    assert belief.uncertainty is not None
    assert 0.0 <= belief.uncertainty <= 1.0
    assert belief.confidence > 0.0
    assert "BLF-" in belief.summary()


def test_belief_with_many_evidence() -> None:
    """多条证据 (n=6) → confidence 不应盲目提升到 1.0。"""
    knowledge = _make_knowledge(confidence=0.7)
    evidence = _evidence_set(n=6, quality=0.6)

    binding = EvidenceBinding()
    belief = binding.bind(knowledge, evidence)

    assert belief is not None
    # 质量接近阈值，不应暴涨
    assert belief.confidence < 0.95


# ── 24.4-A-02: 证据不足拒绝 ────────────────────────────────────────────────


def test_insufficient_evidence_rejected() -> None:
    """只有 2 条 Evidence → 绑定失败返回 None。"""
    knowledge = _make_knowledge()
    evidence = _evidence_set(n=2, quality=0.8)

    binding = EvidenceBinding()
    result = binding.bind(knowledge, evidence)

    assert result is None


def test_zero_evidence_rejected() -> None:
    """空 Evidence → 绑定失败。"""
    knowledge = _make_knowledge()

    binding = EvidenceBinding()
    result = binding.bind(knowledge, [])

    assert result is None


# ── 24.4-A-03: 低质量 Evidence 拒绝 ────────────────────────────────────────


def test_low_quality_evidence_rejected() -> None:
    """avg_quality = 0.4 < 0.5 → 拒绝。"""
    knowledge = _make_knowledge()
    evidence = _evidence_set(n=3, quality=0.4)

    binding = EvidenceBinding()
    result = binding.bind(knowledge, evidence)

    assert result is None


def test_mixed_quality_must_pass_threshold() -> None:
    """混合质量，均值 >= 0.5 → 通过。"""
    knowledge = _make_knowledge()
    evidence = [
        _make_evidence(quality=0.9),
        _make_evidence(quality=0.4),
        _make_evidence(quality=0.5),  # avg = 0.6
    ]

    binding = EvidenceBinding()
    result = binding.bind(knowledge, evidence)

    assert result is not None


# ── 24.4-A-04: uncertainty 必须存在 ─────────────────────────────────────────


def test_uncertainty_not_none() -> None:
    """所有 Belief 的 uncertainty 不可为 None。"""
    knowledge = _make_knowledge()
    evidence = _evidence_set(n=3, quality=0.8)

    binding = EvidenceBinding()
    belief = binding.bind(knowledge, evidence)

    assert belief is not None
    assert belief.uncertainty is not None
    assert isinstance(belief.uncertainty, float)
    assert 0.0 <= belief.uncertainty <= 1.0


def test_empty_evidence_max_uncertainty() -> None:
    """空 evidence → ConfidenceEngine 返回 uncertainty=1.0。"""
    from ocos.memory.belief.confidence import ConfidenceEngine
    engine = ConfidenceEngine()
    result = engine.evaluate([])
    assert result.uncertainty == 1.0


# ── 24.4-A-05: Self 字段污染拒绝 ───────────────────────────────────────────


def test_belief_no_self_fields() -> None:
    """Belief 字段名不含 self/identity/value/goal..."""
    from dataclasses import fields as dc_fields
    field_names = {f.name for f in dc_fields(Belief)}
    forbidden = {
        "self", "identity", "personality", "persona",
        "value", "mission", "character", "owner",
        "preference", "goal_owner", "goal",
    }
    overlap = field_names & forbidden
    assert len(overlap) == 0, f"Belief has forbidden fields: {overlap}"


# ── 24.4-A-06: Identity 推导阻断 ────────────────────────────────────────────


def test_validator_rejects_first_person() -> None:
    """statement 含 "I am" → validator 拒绝。"""
    knowledge = _make_knowledge(
        statement="I am a system that fails under high load",
    )
    evidence = _evidence_set(n=3)
    binding = EvidenceBinding()
    belief = binding.bind(knowledge, evidence)

    assert belief is not None
    passed, violations = BeliefValidator.validate(belief, evidence)
    assert not passed
    assert any("first-person" in v for v in violations)


def test_validator_rejects_identity_cn() -> None:
    """statement 含 "我是一个" → validator 拒绝。"""
    knowledge = _make_knowledge(statement="我是一个不适合高并发的系统")
    evidence = _evidence_set(n=3)
    binding = EvidenceBinding()
    belief = binding.bind(knowledge, evidence)

    assert belief is not None
    passed, violations = BeliefValidator.validate(belief, evidence)
    assert not passed


# ── 24.4-A-07: Goal/Belief 修改阻断 ──────────────────────────────────────────


def test_validator_rejects_deontic() -> None:
    """statement 含 "应该" → validator 拒绝。"""
    knowledge = _make_knowledge(statement="系统应该始终避免高负载")
    evidence = _evidence_set(n=3)
    binding = EvidenceBinding()
    belief = binding.bind(knowledge, evidence)

    assert belief is not None
    passed, violations = BeliefValidator.validate(belief, evidence)
    assert not passed
    assert any("deontic" in v for v in violations)


# ── 24.4-A-08: Evidence lineage 可追踪 ───────────────────────────────────────


def test_evidence_lineage_traceable() -> None:
    """Belief → Knowledge → Evidence → Episode 完整可追溯。"""
    knowledge = _make_knowledge()
    evidence = [
        Evidence.create("EPI-001", "PAT-A", quality=0.9),
        Evidence.create("EPI-005", "PAT-B", quality=0.85),
        Evidence.create("EPI-009", "PAT-C", quality=0.8),
    ]

    binding = EvidenceBinding()
    belief = binding.bind(knowledge, evidence)

    assert belief is not None

    # Belief → Knowledge
    assert knowledge.id in belief.source_knowledge_ids

    # Belief → Evidence
    assert len(belief.evidence_ids) == 3
    for e in evidence:
        assert e.id in belief.evidence_ids

    # Evidence → Episode
    episode_ids = {e.source_episode_id for e in evidence}
    assert episode_ids == {"EPI-001", "EPI-005", "EPI-009"}

    # Evidence → Pattern
    pattern_ids = {e.source_pattern_id for e in evidence}
    assert pattern_ids == {"PAT-A", "PAT-B", "PAT-C"}


def test_evidence_lineage_full_chain() -> None:
    """完整链路: Belief.source_knowledge_ids → Knowledge → Pattern → Evidence → Episode。"""
    knowledge = _make_knowledge()
    evidence = [
        Evidence.create("EPI-100", "PAT-100", quality=0.9),
        Evidence.create("EPI-200", "PAT-200", quality=0.85),
        Evidence.create("EPI-300", "PAT-300", quality=0.8),
    ]

    binding = EvidenceBinding()
    belief = binding.bind(knowledge, evidence)

    assert belief is not None
    # 每一环都存在
    assert len(belief.source_knowledge_ids) == 1
    assert len(belief.evidence_ids) == 3
    # source_pattern_ids 在 Knowledge 中
    assert len(knowledge.source_patterns) == 3


# ── 模型基础 ──────────────────────────────────────────────────────────────────


def test_belief_is_immutable() -> None:
    """Belief 是 frozen dataclass。"""
    belief = Belief.create(
        statement="测试",
        source_knowledge_ids=["KNW-001"],
        evidence_ids=["EVD-001", "EVD-002", "EVD-003"],
        confidence=0.8,
        uncertainty=0.2,
    )
    with pytest.raises(Exception):
        belief.confidence = 0.5  # type: ignore[misc]


def test_belief_weaken() -> None:
    """weaken() 返回 WEAKENED 状态的新对象。"""
    belief = Belief.create(
        statement="测试",
        source_knowledge_ids=["KNW-001"],
        evidence_ids=["EVD-001", "EVD-002", "EVD-003"],
        confidence=0.8,
        uncertainty=0.2,
    )
    weakened = belief.weaken()
    assert weakened.status == BeliefStatus.WEAKENED
    assert weakened.uncertainty > belief.uncertainty
    assert belief.status == BeliefStatus.ACTIVE  # 原对象不变


def test_belief_invalidate() -> None:
    """invalidate() 返回 INVALIDATED。"""
    belief = Belief.create(
        statement="测试",
        source_knowledge_ids=["KNW-001"],
        evidence_ids=["EVD-001", "EVD-002", "EVD-003"],
        confidence=0.8,
        uncertainty=0.2,
    )
    invalidated = belief.invalidate()
    assert invalidated.status == BeliefStatus.INVALIDATED
    assert not invalidated.is_active
    assert belief.is_active  # 原对象不变


def test_low_confidence_auto_weakened() -> None:
    """confidence < 0.6 → 自动 WEAKENED。"""
    belief = Belief.create(
        statement="测试",
        source_knowledge_ids=["KNW-001"],
        evidence_ids=["EVD-001", "EVD-002", "EVD-003"],
        confidence=0.4,
        uncertainty=0.6,
    )
    assert belief.status == BeliefStatus.WEAKENED


# ── Validator 边界 ────────────────────────────────────────────────────────────


def test_validator_accepts_clean_belief() -> None:
    """干净的 Belief → 通过验证。"""
    knowledge = _make_knowledge()
    evidence = _evidence_set(n=3, quality=0.8)
    binding = EvidenceBinding()
    belief = binding.bind(knowledge, evidence)

    assert belief is not None
    passed, violations = BeliefValidator.validate(belief, evidence)
    assert passed
    assert len(violations) == 0


def test_validator_rejects_evidence_count_mismatch() -> None:
    """evidence_ids 数量与实际 evidence 不一致 → 拒绝。"""
    knowledge = _make_knowledge()
    evidence = _evidence_set(n=3, quality=0.8)

    # 手动构造 belief 但只给 2 条 evidence
    belief = Belief.create(
        statement=knowledge.statement,
        source_knowledge_ids=[knowledge.id],
        evidence_ids=["EVD-001", "EVD-002", "EVD-003"],  # 3 IDs
        confidence=0.8,
        uncertainty=0.2,
    )
    # 但只传 2 条实际 evidence
    passed, violations = BeliefValidator.validate(belief, evidence[:2])
    assert not passed
    assert any("mismatch" in v for v in violations)


def test_evidence_quality_bounds() -> None:
    """Evidence quality 被 clamp 到 [0.0, 1.0]。"""
    e1 = _make_evidence(quality=1.5)
    e2 = _make_evidence(quality=-0.5)
    assert e1.quality == 1.0
    assert e2.quality == 0.0


def test_evidence_is_high_quality() -> None:
    """quality >= 0.5 → is_high_quality。"""
    assert _make_evidence(quality=0.8).is_high_quality is True
    assert _make_evidence(quality=0.3).is_high_quality is False
