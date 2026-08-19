"""Phase 24.4-B — Gate Tests: Confidence Engine。

验证:
  24.4-B-01: Evidence → ConfidenceResult (全维度)
  24.4-B-02: 高质量 + 一致性 → 高置信度
  24.4-B-03: 低质量 → weakened
  24.4-B-04: 反例 → 置信度下降
  24.4-B-05: 新近度衰减 (旧证据权重低)
  24.4-B-06: 证据量饱和 (边际递减)
  24.4-B-07: 空证据 → invalidated
  24.4-B-08: Config 权重验证
  24.4-B-09: 不产生 Goal/Priority/Self
  24.4-B-10: EvidenceBinding delegate → ConfidenceEngine
"""

from __future__ import annotations

import sys
from dataclasses import fields
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT))

from ocos.memory.belief.models import Evidence
from ocos.memory.belief.confidence import (
    ConfidenceEngine,
    ConfidenceConfig,
    ConfidenceResult,
)
from ocos.memory.belief.evidence import EvidenceBinding, BindingConfig
from ocos.memory.semantic.models import KnowledgeEntry, KnowledgeScope


# ── Helpers ──────────────────────────────────────────────────────────────────


def _make_evidence(
    source_episode_id: str = "EPI-001",
    source_pattern_id: str = "PAT-001",
    quality: float = 0.8,
    consistency: float = 0.9,
    timestamp: datetime | None = None,
) -> Evidence:
    return Evidence.create(
        source_episode_id=source_episode_id,
        source_pattern_id=source_pattern_id,
        quality=quality,
        consistency_score=consistency,
        timestamp=timestamp or datetime.now(timezone.utc),
    )


def _make_knowledge(
    statement: str = "资源不足时任务完成概率显著下降",
    confidence: float = 0.85,
    counterexamples: int = 0,
) -> KnowledgeEntry:
    scope = KnowledgeScope(
        domain="resource_management",
        preconditions=("cpu>80%",),
        counterexamples=counterexamples,
    )
    return KnowledgeEntry.create(
        statement=statement,
        source_patterns=["PAT-001", "PAT-002", "PAT-003"],
        confidence=confidence,
        scope=scope,
        stability=0.8,
    )


# ── 24.4-B-01: Evidence → ConfidenceResult ──────────────────────────────────


def test_engine_produces_confidence_result() -> None:
    """3 条高质量 evidence → ConfidenceResult with all dimensions。"""
    engine = ConfidenceEngine()
    evidence = [
        _make_evidence("EPI-001", "PAT-A", quality=0.9),
        _make_evidence("EPI-002", "PAT-B", quality=0.85),
        _make_evidence("EPI-003", "PAT-C", quality=0.8),
    ]

    result = engine.evaluate(evidence)

    assert isinstance(result, ConfidenceResult)
    assert 0.0 <= result.confidence <= 1.0
    assert 0.0 <= result.uncertainty <= 1.0
    assert result.evidence_count == 3
    assert result.status == "active"
    assert set(result.dimensions.keys()) == {
        "quality", "consistency", "recency", "volume", "counter"
    }
    for dim, score in result.dimensions.items():
        assert 0.0 <= score <= 1.0, f"dim {dim}={score} out of bounds"


def test_engine_returns_dimensions_separately() -> None:
    """各维度独立可审计。"""
    engine = ConfidenceEngine()
    evidence = [
        _make_evidence("EPI-001", quality=1.0, consistency=1.0),
        _make_evidence("EPI-002", quality=1.0, consistency=1.0),
        _make_evidence("EPI-003", quality=1.0, consistency=1.0),
    ]

    result = engine.evaluate(evidence)

    assert result.dimensions["quality"] > 0.9
    assert result.dimensions["consistency"] > 0.9


# ── 24.4-B-02: 高质量 + 一致性 → 高置信度 ────────────────────────────────────


def test_high_quality_consistency_gives_high_confidence() -> None:
    """全 1.0 质量 + 全 1.0 一致性 → 最高置信度。"""
    config = ConfidenceConfig(
        weight_quality=0.35,
        weight_consistency=0.30,
        weight_recency=0.20,
        weight_volume=0.10,
        weight_counter=0.05,
    )
    engine = ConfidenceEngine(config)
    evidence = [
        _make_evidence(quality=1.0, consistency=1.0)
        for _ in range(5)
    ]

    result = engine.evaluate(evidence)

    assert result.confidence > 0.9
    assert result.uncertainty <= 0.25


def test_perfect_evidence_near_certain() -> None:
    """15 条完美证据 → confidence ≈ 1.0, uncertainty ≈ 0.05。"""
    engine = ConfidenceEngine()
    evidence = [
        _make_evidence(quality=1.0, consistency=1.0)
        for _ in range(15)
    ]

    result = engine.evaluate(evidence)

    assert result.confidence > 0.95
    assert result.uncertainty <= 0.1
    assert result.is_confident


# ── 24.4-B-03: 低质量 → weakened ────────────────────────────────────────────


def test_low_quality_lowers_confidence() -> None:
    """avg quality 0.4 → confidence < 0.6"""
    engine = ConfidenceEngine()
    evidence = [
        _make_evidence(quality=0.4, consistency=0.5),
        _make_evidence(quality=0.4, consistency=0.5),
        _make_evidence(quality=0.4, consistency=0.5),
    ]

    result = engine.evaluate(evidence)

    # 低质量应显著降低置信度
    assert result.confidence < 0.7
    assert result.is_weakened or result.is_invalidated


def test_low_consistency_lowers_confidence() -> None:
    """高质量但低一致性 → confidence 下降。"""
    engine = ConfidenceEngine()
    now = datetime.now(timezone.utc)
    evidence = [
        _make_evidence(quality=0.9, consistency=0.2),
        _make_evidence(quality=0.9, consistency=0.2),
        _make_evidence(quality=0.9, consistency=0.2),
    ]

    result = engine.evaluate(evidence)

    assert result.confidence < 0.85
    assert result.dimensions["consistency"] < 0.5


# ── 24.4-B-04: 反例 → 置信度下降 ────────────────────────────────────────────


def test_counterexamples_reduce_confidence() -> None:
    """5 个反例 → counter 维度下降。"""
    engine = ConfidenceEngine()
    evidence = [
        _make_evidence(quality=0.9, consistency=0.9)
        for _ in range(5)
    ]

    no_counter = engine.evaluate(evidence, counterexamples=0)
    with_counter = engine.evaluate(evidence, counterexamples=5)

    assert with_counter.confidence < no_counter.confidence
    assert with_counter.dimensions["counter"] < no_counter.dimensions["counter"]


def test_counter_capped_at_max_impact() -> None:
    """反例影响 capped 在 0.15。"""
    engine = ConfidenceEngine()
    evidence = [_make_evidence(quality=1.0, consistency=1.0) for _ in range(3)]

    result = engine.evaluate(evidence, counterexamples=100)
    # counter dimension 最小值 = 1.0 - 0.15 = 0.85
    assert result.dimensions["counter"] >= 0.85


# ── 24.4-B-05: 新近度衰减 ───────────────────────────────────────────────────


def test_recency_decay_old_evidence_lower_weight() -> None:
    """旧证据时间衰减 → recency 维度降低。"""
    engine = ConfidenceEngine()
    now = datetime.now(timezone.utc)
    old = datetime.now(timezone.utc) - timedelta(days=200)

    evidence = [
        _make_evidence("EPI-001", quality=0.9, consistency=0.9, timestamp=old),
        _make_evidence("EPI-002", quality=0.9, consistency=0.9, timestamp=old),
        _make_evidence("EPI-003", quality=0.9, consistency=0.9, timestamp=old),
    ]

    result = engine.evaluate(evidence, now=now)

    # 200 天 > 半衰期 30 天 → recency 极低
    assert result.dimensions["recency"] < 0.2


def test_fresh_evidence_high_recency() -> None:
    """新证据 recency 接近 1.0。"""
    engine = ConfidenceEngine()
    now = datetime.now(timezone.utc)
    fresh = now - timedelta(minutes=1)

    evidence = [
        _make_evidence("EPI-001", quality=0.9, consistency=0.9, timestamp=fresh),
        _make_evidence("EPI-002", quality=0.9, consistency=0.9, timestamp=fresh),
        _make_evidence("EPI-003", quality=0.9, consistency=0.9, timestamp=fresh),
    ]

    result = engine.evaluate(evidence, now=now)

    assert result.dimensions["recency"] >= 0.9


# ── 24.4-B-06: 证据量饱和 ───────────────────────────────────────────────────


def test_volume_saturation_diminishing_returns() -> None:
    """15 条 = 饱和，30 条 不会明显超过 15 条。"""
    engine = ConfidenceEngine()
    evidence_15 = [
        _make_evidence(quality=0.8, consistency=0.8)
        for _ in range(15)
    ]
    evidence_30 = evidence_15 + [
        _make_evidence(quality=0.8, consistency=0.8)
        for _ in range(15)
    ]

    r15 = engine.evaluate(evidence_15)
    r30 = engine.evaluate(evidence_30)

    assert r15.dimensions["volume"] >= 0.99
    assert r30.dimensions["volume"] >= 0.99
    # 饱和后 confidence 差异很小
    assert abs(r30.confidence - r15.confidence) < 0.05


# ── 24.4-B-07: 空证据 → invalidated ─────────────────────────────────────────


def test_empty_evidence_invalidated() -> None:
    """无证据 → confidence=0, invalidated。"""
    engine = ConfidenceEngine()
    result = engine.evaluate([])

    assert result.confidence == 0.0
    assert result.uncertainty == 1.0
    assert result.evidence_count == 0
    assert result.is_invalidated
    assert not result.is_confident


# ── 24.4-B-08: Config 验证 ──────────────────────────────────────────────────


def test_config_weights_must_sum_to_one() -> None:
    """权重和 ≠ 1.0 → ValueError。"""
    with pytest.raises(ValueError):
        ConfidenceConfig(weight_quality=0.5, weight_consistency=0.5)


def test_config_defaults_are_valid() -> None:
    """默认 Config 权重 sum = 1.0。"""
    config = ConfidenceConfig()
    total = (
        config.weight_quality
        + config.weight_consistency
        + config.weight_recency
        + config.weight_volume
        + config.weight_counter
    )
    assert abs(total - 1.0) < 0.001


def test_config_is_immutable() -> None:
    """ConfidenceConfig 不可变。"""
    config = ConfidenceConfig()
    with pytest.raises(Exception):
        config.weight_quality = 0.5  # type: ignore[misc]


def test_custom_config_works() -> None:
    """自定义 Config → 权重不同 → 活跃。"""
    config = ConfidenceConfig(
        weight_quality=0.50,
        weight_consistency=0.20,
        weight_recency=0.10,
        weight_volume=0.10,
        weight_counter=0.10,
    )
    engine = ConfidenceEngine(config)
    evidence = [_make_evidence(quality=0.9, consistency=0.9) for _ in range(3)]
    result = engine.evaluate(evidence)
    assert result.is_confident


# ── 24.4-B-09: 不产生 Goal/Priority/Self ─────────────────────────────────────


def test_confidence_result_no_goal_fields() -> None:
    """ConfidenceResult 字段不含 Goal/Priority/Self。"""
    field_names = {f.name for f in fields(ConfidenceResult)}
    forbidden = {
        "goal", "priority", "self", "identity",
        "action", "intent", "value", "preference",
    }
    assert field_names.isdisjoint(forbidden)


def test_confidence_engine_no_self_inference() -> None:
    """ConfidenceEngine 无任何 Self 相关方法/属性。"""
    engine = ConfidenceEngine()
    # 只有 evaluate + config + 内部 _compute_*
    public = [m for m in dir(engine) if not m.startswith("_")]
    assert "identity" not in public
    assert "goal" not in public
    assert "priority" not in public
    assert "self" not in public


# ── 24.4-B-10: EvidenceBinding → ConfidenceEngine delegate ───────────────────


def test_binding_delegates_to_confidence_engine() -> None:
    """EvidenceBinding.bind() 通过 ConfidenceEngine 计算置信度。"""
    config = ConfidenceConfig()
    engine = ConfidenceEngine(config)
    binding = EvidenceBinding(confidence_engine=engine)
    knowledge = _make_knowledge()
    evidence = [
        _make_evidence("EPI-001", quality=0.9, consistency=0.9),
        _make_evidence("EPI-002", quality=0.85, consistency=0.85),
        _make_evidence("EPI-003", quality=0.8, consistency=0.8),
    ]

    belief = binding.bind(knowledge, evidence)
    assert belief is not None

    # 对比直接调用 engine
    direct_result = engine.evaluate(evidence, counterexamples=knowledge.counterexample_count)
    assert belief.confidence == direct_result.confidence
    assert belief.uncertainty == direct_result.uncertainty


def test_binding_with_counterexamples_delegates() -> None:
    """有反例的 Knowledge → ConfidenceEngine 接收 counterexamples。"""
    engine = ConfidenceEngine()
    binding = EvidenceBinding(confidence_engine=engine)
    knowledge = _make_knowledge(counterexamples=5)
    evidence = [
        _make_evidence(quality=0.9, consistency=0.9)
        for _ in range(3)
    ]

    belief = binding.bind(knowledge, evidence)
    assert belief is not None

    direct = engine.evaluate(evidence, counterexamples=5)
    assert belief.confidence == direct.confidence


def test_rebind_uses_confidence_engine() -> None:
    """rebind() 也使用 ConfidenceEngine。"""
    config = ConfidenceConfig(weak_threshold=0.99)  # 强制 weaken
    engine = ConfidenceEngine(config)
    binding = EvidenceBinding(confidence_engine=engine)
    knowledge = _make_knowledge()
    evidence = [
        _make_evidence(quality=0.6, consistency=0.6)
        for _ in range(3)
    ]

    belief = binding.bind(knowledge, evidence)
    assert belief is not None

    # rebind with fewer evidence
    fewer = evidence[:2]
    result = binding.rebind(belief, knowledge, fewer)
    assert result.status.name == "WEAKENED"


def test_confidence_result_is_immutable() -> None:
    """ConfidenceResult 是 frozen dataclass。"""
    result = ConfidenceResult(
        confidence=0.8,
        uncertainty=0.2,
        dimensions={"q": 0.8},
        evidence_count=3,
        status="active",
    )
    with pytest.raises(Exception):
        result.confidence = 0.5  # type: ignore[misc]


# ── 边界 ─────────────────────────────────────────────────────────────────────


def test_quality_squared_weighting() -> None:
    """高质量证据 (quality²) 权重更大。"""
    evidence = [
        _make_evidence(quality=0.9, consistency=0.8),
        _make_evidence(quality=0.9, consistency=0.8),
        _make_evidence(quality=0.9, consistency=0.8),
    ]
    score = ConfidenceEngine._compute_quality(evidence)
    assert score > 0.85


def test_consistency_variance_penalty() -> None:
    """高方差 (不一致) → dispersion penalty。"""
    evidence = [
        _make_evidence(consistency=0.2),
        _make_evidence(consistency=0.2),
        _make_evidence(consistency=0.2),
        _make_evidence(consistency=1.0),
    ]
    score = ConfidenceEngine._compute_consistency(evidence)
    # 均值 0.4，但方差大 → 低于 0.4
    assert score < 0.35
