"""Phase 25.3 — Gate Tests: 数据结构 (models.py)。

验证:
  25.3-M01: CapabilityState frozen
  25.3-M02: CapabilityState confidence 范围 [0.0, 1.0]
  25.3-M03: PRESET_LIMITATIONS 有 5 个预设
  25.3-M04: MaturitySnapshot 维度完整 (7 维度)
  25.3-M05: SelfModel 不包含 personality/goal/value 字段
  25.3-M06: SelfModel frozen
  25.3-M07: CapabilityName.domain 映射正确
  25.3-M08: SelfModel.has_preset_limitations()
"""

import pytest
from datetime import datetime, timezone

from ocos.self.models import (
    CapabilityDomain,
    CapabilityName,
    CapabilityState,
    Limitation,
    MaturitySnapshot,
    SelfModel,
    PRESET_LIMITATIONS,
    MATURITY_DIMENSIONS,
)


def _now():
    return datetime.now(timezone.utc)


# ── 25.3-M01: CapabilityState frozen ─────────────────────────────────────

def test_capability_state_frozen():
    cs = CapabilityState(
        name=CapabilityName.TEXT_UNDERSTANDING,
        confidence_score=0.85,
        belief_ids=("BLF-001",),
        evidence_summary="基于3条Belief",
        last_updated=_now(),
        status="active",
    )
    with pytest.raises(Exception):
        cs.confidence_score = 0.9  # type: ignore[misc]


# ── 25.3-M02: CapabilityState confidence 范围 ───────────────────────────

def test_capability_state_confidence_range():
    with pytest.raises(ValueError, match=r"\[0\.0, 1\.0\]"):
        CapabilityState(
            name=CapabilityName.TEXT_UNDERSTANDING,
            confidence_score=1.5,
            belief_ids=(),
            evidence_summary="",
            last_updated=_now(),
        )
    with pytest.raises(ValueError, match=r"\[0\.0, 1\.0\]"):
        CapabilityState(
            name=CapabilityName.TEXT_UNDERSTANDING,
            confidence_score=-0.1,
            belief_ids=(),
            evidence_summary="",
            last_updated=_now(),
        )


def test_capability_state_invalid_status():
    with pytest.raises(ValueError, match="status must be one of"):
        CapabilityState(
            name=CapabilityName.TEXT_UNDERSTANDING,
            confidence_score=0.5,
            belief_ids=(),
            evidence_summary="",
            last_updated=_now(),
            status="invalid-status",
        )


def test_capability_name_domain_mapping():
    """25.3-M07: CapabilityName → domain 映射正确。"""
    assert CapabilityName.TEXT_UNDERSTANDING.domain == CapabilityDomain.COGNITION
    assert CapabilityName.PATTERN_RECOGNITION.domain == CapabilityDomain.COGNITION
    assert CapabilityName.SIMULATION.domain == CapabilityDomain.COGNITION
    assert CapabilityName.EXPERIENCE_RECALL.domain == CapabilityDomain.MEMORY
    assert CapabilityName.BOUNDARY_AWARENESS.domain == CapabilityDomain.SELF
    assert CapabilityName.LIMITATION_AWARENESS.domain == CapabilityDomain.SELF


# ── 25.3-M03: PRESET_LIMITATIONS ─────────────────────────────────────────

def test_preset_limitations_exist():
    assert len(PRESET_LIMITATIONS) == 5
    descriptions = {l.description for l in PRESET_LIMITATIONS}
    assert "不能创建新目标" in descriptions
    assert "不能修改 IdentityBoundary" in descriptions
    assert "不能写入 Memory" in descriptions
    assert "不能访问物理世界" in descriptions
    assert "不能自行获取网络权限" in descriptions


def test_limitation_valid_category():
    with pytest.raises(ValueError):
        Limitation(
            description="test",
            category="invalid",
            severity="hard",
            evidence_belief_ids=(),
            acknowledged_at=_now(),
        )


def test_limitation_frozen():
    lim = Limitation(
        description="test",
        category="architectural",
        severity="hard",
        evidence_belief_ids=(),
        acknowledged_at=_now(),
    )
    with pytest.raises(Exception):
        lim.severity = "soft"  # type: ignore[misc]


# ── 25.3-M04: MaturitySnapshot 维度 ─────────────────────────────────────

def test_maturity_dimensions_complete():
    assert len(MATURITY_DIMENSIONS) == 7
    for dim in ("theory", "governance", "runtime", "subject", "cortex", "memory", "self"):
        assert dim in MATURITY_DIMENSIONS


def test_maturity_snapshot_missing_dimension():
    with pytest.raises(ValueError, match="Missing maturity dimension"):
        MaturitySnapshot(
            current_phase="phase25",
            phase_history=("phase25",),
            dimensions={"theory": 0.9},  # 缺少其他维度
            capability_count=0,
            limitation_count=0,
            snapshot_at=_now(),
        )


def test_maturity_dimension_value_range_error():
    """维度值超出 [0.0, 1.0] → ValueError。"""
    dims = {d: 0.5 for d in MATURITY_DIMENSIONS}
    dims["theory"] = 1.5  # 超出范围
    with pytest.raises(ValueError, match=r"\[0\.0, 1\.0\]"):
        MaturitySnapshot(
            current_phase="phase25",
            phase_history=("phase25",),
            dimensions=dims,
            capability_count=0,
            limitation_count=0,
            snapshot_at=_now(),
        )


# ── 25.3-M05: SelfModel 不含 personality 字段 ───────────────────────────

def test_selfmodel_no_personality_fields():
    """SelfModel 字段不应包含任何人格/情感/偏好相关名称。"""
    from dataclasses import fields as dc_fields
    field_names = {f.name for f in dc_fields(SelfModel)}
    forbidden_field_names = {
        "personality", "persona", "emotion", "feelings",
        "preference", "preferences", "value", "values",
        "goal", "goals", "narrative", "identity",
        "like", "dislike", "should", "want", "desire",
    }
    overlap = field_names & forbidden_field_names
    assert not overlap, f"SelfModel has forbidden field names: {overlap}"


# ── 25.3-M06: SelfModel frozen ───────────────────────────────────────────

def test_selfmodel_frozen():
    ms = MaturitySnapshot(
        current_phase="phase25",
        phase_history=("phase25",),
        dimensions={d: 0.5 for d in MATURITY_DIMENSIONS},
        capability_count=0,
        limitation_count=5,
        snapshot_at=_now(),
    )
    sm = SelfModel(
        model_id="SM-TEST",
        version=1,
        capability_states=(),
        limitations=PRESET_LIMITATIONS,
        maturity=ms,
        statement="当前系统是一个信息处理系统",
        created_at=_now(),
        previous_version_id=None,
        governor_approval_id="REC-001",
    )
    with pytest.raises(Exception):
        sm.version = 2  # type: ignore[misc]


def test_selfmodel_invalid_version():
    ms = MaturitySnapshot(
        current_phase="phase25",
        phase_history=("phase25",),
        dimensions={d: 0.5 for d in MATURITY_DIMENSIONS},
        capability_count=0,
        limitation_count=5,
        snapshot_at=_now(),
    )
    with pytest.raises(ValueError, match="version must be >= 1"):
        SelfModel(
            model_id="SM-TEST",
            version=0,
            capability_states=(),
            limitations=PRESET_LIMITATIONS,
            maturity=ms,
            statement="当前系统是一个信息处理系统",
            created_at=_now(),
            previous_version_id=None,
            governor_approval_id="REC-001",
        )


# ── 25.3-M08: SelfModel.has_preset_limitations ──────────────────────────

def test_has_preset_limitations():
    ms = MaturitySnapshot(
        current_phase="phase25",
        phase_history=("phase25",),
        dimensions={d: 0.5 for d in MATURITY_DIMENSIONS},
        capability_count=0,
        limitation_count=5,
        snapshot_at=_now(),
    )
    sm = SelfModel(
        model_id="SM-TEST",
        version=1,
        capability_states=(),
        limitations=PRESET_LIMITATIONS,
        maturity=ms,
        statement="当前系统是一个信息处理系统",
        created_at=_now(),
        previous_version_id=None,
        governor_approval_id="REC-001",
    )
    assert sm.has_preset_limitations()
    assert sm.limitations_by_severity("hard") == tuple(
        l for l in PRESET_LIMITATIONS if l.severity == "hard"
    )


def test_capability_names():
    ms = MaturitySnapshot(
        current_phase="phase25",
        phase_history=("phase25",),
        dimensions={d: 0.5 for d in MATURITY_DIMENSIONS},
        capability_count=2,
        limitation_count=5,
        snapshot_at=_now(),
    )
    caps = (
        CapabilityState(
            name=CapabilityName.TEXT_UNDERSTANDING,
            confidence_score=0.8,
            belief_ids=(),
            evidence_summary="",
            last_updated=_now(),
        ),
        CapabilityState(
            name=CapabilityName.BOUNDARY_AWARENESS,
            confidence_score=0.6,
            belief_ids=(),
            evidence_summary="",
            last_updated=_now(),
        ),
    )
    sm = SelfModel(
        model_id="SM-TEST",
        version=1,
        capability_states=caps,
        limitations=PRESET_LIMITATIONS,
        maturity=ms,
        statement="当前系统是一个信息处理系统",
        created_at=_now(),
        previous_version_id=None,
        governor_approval_id="REC-001",
    )
    names = sm.capability_names()
    assert "text-understanding" in names
    assert "boundary-awareness" in names
