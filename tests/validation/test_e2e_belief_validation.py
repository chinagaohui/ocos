"""Level 4 — E2E Test: Belief __post_init__ Validation Chain.

验证 Belief 直接构造器校验：
  - confidence ∈ [0.0, 1.0]
  - uncertainty ∈ [0.0, 1.0]
  - confidence + uncertainty ≤ 1.0
  - confidence > 0 → evidence_ids 非空
  - frozen=True 不变式保持
"""

import pytest
from datetime import datetime, timezone
from ocos.memory.belief.models import Belief, BeliefStatus


# ── Helper ─────────────────────────────────────────────────────────────────

def _make_belief(**overrides):
    """工厂：用默认值 + 覆盖创建 Belief。"""
    defaults = {
        "id": "B-TEST",
        "statement": "test statement",
        "source_knowledge_ids": (),
        "evidence_ids": ("ev-1",),
        "confidence": 0.5,
        "uncertainty": 0.3,
        "scope": {},
        "status": BeliefStatus.ACTIVE,
        "created_at": datetime.now(timezone.utc),
        "last_updated": datetime.now(timezone.utc),
    }
    defaults.update(overrides)
    return Belief(**defaults)


# ── 4-E2: Confidence Range ──────────────────────────────────────────────

def test_confidence_must_be_in_range():
    """confidence 必须在 [0.0, 1.0] 范围内。"""
    # Valid: 调整 uncertainty 保持 sum ≤ 1.0
    for c in [0.0, 0.5, 1.0]:
        b = _make_belief(id=f"B-C-{c}", confidence=c, uncertainty=0.0)
        assert b.confidence == c

    # Invalid: < 0
    with pytest.raises(ValueError, match="must be"):
        _make_belief(id="B-C-NEG", confidence=-0.1)

    # Invalid: > 1
    with pytest.raises(ValueError, match="must be"):
        _make_belief(id="B-C-HI", confidence=1.5)

    print("PASS: confidence range [0.0, 1.0]")


def test_uncertainty_must_be_in_range():
    """uncertainty 必须在 [0.0, 1.0] 范围内。"""
    for u in [0.0, 0.5, 1.0]:
        b = _make_belief(id=f"B-U-{u}", uncertainty=u, confidence=0.0)
        assert b.uncertainty == u

    with pytest.raises(ValueError, match="must be"):
        _make_belief(id="B-U-NEG", uncertainty=-0.1, confidence=0.0)

    with pytest.raises(ValueError, match="must be"):
        _make_belief(id="B-U-HI", uncertainty=1.5, confidence=0.0)

    print("PASS: uncertainty range [0.0, 1.0]")


# ── 4-E3: Evidence Requirement ──────────────────────────────────────────

def test_confidence_positive_requires_evidence():
    """confidence > 0 时必须有至少一个 evidence_id。"""
    # Valid: confidence > 0, has evidence
    b = _make_belief(id="B-EV-OK", confidence=0.8, uncertainty=0.2, evidence_ids=("e-1",))
    assert b.confidence > 0
    assert len(b.evidence_ids) > 0

    # Valid: confidence = 0, no evidence needed (uncertainty must be ≤ 1-sum)
    b_zero = _make_belief(id="B-EV-ZERO", confidence=0.0, uncertainty=1.0, evidence_ids=())
    assert b_zero.confidence == 0.0

    # Invalid: confidence > 0, no evidence
    with pytest.raises(ValueError, match="evidence_id"):
        _make_belief(id="B-EV-MISSING", confidence=0.5, evidence_ids=())

    print("PASS: evidence required when confidence > 0")


# ── 4-E5: Frozen Immutability ──────────────────────────────────────────

def test_belief_is_frozen_dataclass():
    """Belief 是 frozen=True，不可变。"""
    b = _make_belief(id="B-FRZ")
    # frozen=True 的 dataclass 的 __setattr__ 会抛出 FrozenInstanceError
    from dataclasses import FrozenInstanceError
    with pytest.raises(FrozenInstanceError):
        b.confidence = 0.9

    # 但可以替换整个对象（正常用法）
    b2 = _make_belief(id="B-FRZ-2", confidence=0.9, uncertainty=0.1)
    assert b2.confidence == 0.9
    assert b2 is not b

    print("PASS: Belief is frozen")


# ── 4-E6: Factory create() still works ──────────────────────────────────

def test_factory_create_produces_valid_belief():
    """工厂方法 create() 产出合法 Belief，不受 __post_init__ 干扰。"""
    b = Belief.create(
        statement="factory-created",
        source_knowledge_ids=[],
        evidence_ids=["e-1", "e-2"],
        confidence=0.85,
        uncertainty=0.10,
    )
    assert b.statement == "factory-created"
    assert b.confidence == 0.85
    assert b.uncertainty == 0.10
    assert b.evidence_ids == ("e-1", "e-2")
    assert b.status == BeliefStatus.ACTIVE
    print("PASS: factory create() works with __post_init__")


# ── 4-E7: Confidence zero allows empty evidence ────────────────────────

def test_zero_confidence_allows_empty_evidence():
    """confidence=0 时允许 evidence_ids 为空（尚未确认的信念）。"""
    b = _make_belief(
        id="B-ZERO",
        confidence=0.0,
        uncertainty=1.0,
        evidence_ids=(),
    )
    assert b.confidence == 0.0
    assert b.evidence_ids == ()
    print("PASS: zero confidence + empty evidence OK")
