"""Phase 24.1 — Gate Tests: Experience Capture。

验证:
  24.1-01: 完整链路 → COMPLETE
  24.1-02: 不完整链路 → INCOMPLETE（不丢弃）
  24.1-03: Incomplete 可检索
  24.1-04: Source 追踪正确
  24.1-05: ID 格式 EXP-{timestamp}-{uuid}
  24.1-06: 不可变 (frozen dataclass)
  24.1-07: Seal 机制有效
  24.1-08: Self 字段被扫描
  24.1-09: Self 语义被扫描
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT))

from ocos.memory.experience.models import (
    TraceBundle,
    ExperienceCandidate,
    ExperienceStatus,
    ExperienceSource,
)
from ocos.memory.experience.builder import ExperienceBuilder
from ocos.memory.experience.validator import ExperienceValidator


# ── Helpers ──────────────────────────────────────────────────────────────────


def _complete_bundle() -> TraceBundle:
    return TraceBundle(
        observation={"type": "user_query", "content": "帮我分析"},
        reasoning_trace_id="rt-001",
        decision_trace_id="dt-001",
        action_result={"status": "executed"},
        outcome={"success": True, "result": "analysis_complete"},
    )


# ── 24.1-01: 完整链路 → COMPLETE ─────────────────────────────────────────────


def test_build_complete_experience() -> None:
    """五要素齐全的链路应创建 COMPLETE Candidate。"""
    bundle = _complete_bundle()
    builder = ExperienceBuilder()
    candidate = builder.build(bundle, ExperienceSource.DECISION, {})

    assert candidate is not None
    assert candidate.status == ExperienceStatus.COMPLETE
    assert candidate.completeness_score >= 0.8
    assert candidate.id.startswith("EXP-")


# ── 24.1-02: 不完整链路 → INCOMPLETE ─────────────────────────────────────────


def test_build_incomplete_experience() -> None:
    """缺少要素的链路应创建 INCOMPLETE Candidate（不丢弃）。"""
    bundle = TraceBundle(
        observation={"type": "user_query", "content": "帮我分析"},
        reasoning_trace_id="rt-001",
        # decision_trace_id missing
        decision_trace_id="",
        action_result={"status": "executed"},
        outcome={"success": True, "result": "analysis_complete"},
    )
    builder = ExperienceBuilder()
    candidate = builder.build(bundle, ExperienceSource.DECISION, {})

    assert candidate is not None
    assert candidate.status == ExperienceStatus.INCOMPLETE
    assert "decision_trace_id" in (candidate.rejection_reason or "")


# ── 24.1-03: Incomplete 可检索 ───────────────────────────────────────────────


def test_incomplete_retrievable() -> None:
    """INCOMPLETE Candidate 不应丢失，可通过 get_incomplete() 检索。"""
    bundle = TraceBundle(
        observation={"type": "test"},
        reasoning_trace_id="rt-001",
        decision_trace_id="",
        action_result={"status": "executed"},
        outcome={"success": True},
    )
    builder = ExperienceBuilder()
    candidate = builder.build(bundle, ExperienceSource.DECISION, {})

    incomplete = builder.get_incomplete()
    assert len(incomplete) == 1
    assert incomplete[0].id == candidate.id


# ── 24.1-04: Source 追踪 ─────────────────────────────────────────────────────


def test_experience_source_tracking() -> None:
    """不同类型 Source 应被正确记录。"""
    bundle = _complete_bundle()
    builder = ExperienceBuilder()

    c1 = builder.build(bundle, ExperienceSource.DECISION, {})
    c2 = builder.build(bundle, ExperienceSource.REFLECTION, {})
    c3 = builder.build(bundle, ExperienceSource.ANOMALY, {})
    c4 = builder.build(bundle, ExperienceSource.GOAL_COMPLETION, {})

    assert c1.source == ExperienceSource.DECISION
    assert c2.source == ExperienceSource.REFLECTION
    assert c3.source == ExperienceSource.ANOMALY
    assert c4.source == ExperienceSource.GOAL_COMPLETION


# ── 24.1-05: ID 格式 ─────────────────────────────────────────────────────────


def test_experience_id_format() -> None:
    """ID 应遵循 EXP-{YYYYMMDD}-{UUID8} 格式。"""
    bundle = _complete_bundle()
    builder = ExperienceBuilder()
    candidate = builder.build(bundle, ExperienceSource.DECISION, {})

    assert candidate.id.startswith("EXP-")
    parts = candidate.id.split("-")
    # EXP-YYYYMMDD-UUID8
    assert len(parts) == 3, f"Expected 3 parts, got {parts}"
    assert len(parts[1]) == 8, f"Date part should be 8 chars, got {parts[1]}"
    assert len(parts[2]) == 8, f"UUID part should be 8 chars, got {parts[2]}"


def test_experience_id_unique() -> None:
    """连续创建的 Candidate 应有不同 ID。"""
    bundle = _complete_bundle()
    builder = ExperienceBuilder()

    c1 = builder.build(bundle, ExperienceSource.DECISION, {})
    c2 = builder.build(bundle, ExperienceSource.DECISION, {})

    assert c1.id != c2.id


# ── 24.1-06: 不可变 (frozen) ─────────────────────────────────────────────────


def test_experience_immutable() -> None:
    """frozen dataclass 应阻止属性修改。"""
    bundle = _complete_bundle()
    builder = ExperienceBuilder()
    candidate = builder.build(bundle, ExperienceSource.DECISION, {})

    with pytest.raises(Exception):
        candidate.status = ExperienceStatus.REJECTED  # type: ignore[misc]


def test_trace_bundle_immutable() -> None:
    """TraceBundle 也应是 frozen。"""
    bundle = _complete_bundle()

    with pytest.raises(Exception):
        bundle.outcome = {"changed": True}  # type: ignore[misc]


# ── 24.1-07: Seal 机制 ───────────────────────────────────────────────────────


def test_experience_seal() -> None:
    """Seal 应创建新的 Candidate 副本，sealed_at 更新。"""
    bundle = _complete_bundle()
    builder = ExperienceBuilder()
    candidate = builder.build(bundle, ExperienceSource.DECISION, {})

    sealed = builder.seal(candidate.id)
    assert sealed is not None
    assert sealed.sealed_at is not None
    assert sealed.status == candidate.status
    assert sealed.id == candidate.id


def test_seal_returns_none_for_unknown_id() -> None:
    """封存不存在的 ID 应返回 None。"""
    builder = ExperienceBuilder()
    assert builder.seal("nonexistent") is None


# ── 24.1-08: Self 字段扫描 ───────────────────────────────────────────────────


def test_self_field_blocked_in_trace_bundle() -> None:
    """TraceBundle 观察字段中的 'self' 键应被扫描出。"""
    bundle = TraceBundle(
        observation={"type": "user_query", "self": "我应该变得更强"},
        reasoning_trace_id="rt-001",
        decision_trace_id="dt-001",
        action_result={"status": "executed"},
        outcome={"success": True},
    )
    violations = ExperienceValidator.validate_trace_bundle(bundle)
    assert len(violations) > 0
    assert any("forbidden field 'self'" in v for v in violations)


def test_self_field_blocked_in_action_result() -> None:
    """action_result 中的 Self 字段也应被扫描。"""
    bundle = TraceBundle(
        observation={"type": "test"},
        reasoning_trace_id="rt-001",
        decision_trace_id="dt-001",
        action_result={"status": "done", "identity": "writer"},
        outcome={"success": True},
    )
    violations = ExperienceValidator.validate_trace_bundle(bundle)
    assert len(violations) > 0
    assert any("'identity'" in v for v in violations)


def test_clean_bundle_passes_field_scan() -> None:
    """不含 Self 字段的 Bundle 应通过扫描。"""
    bundle = _complete_bundle()
    violations = ExperienceValidator.validate_trace_bundle(bundle)
    assert len(violations) == 0


# ── 24.1-09: Self 语义扫描 ───────────────────────────────────────────────────


def test_self_pattern_blocked() -> None:
    """含有 "I am" 模式的 Candidate 应被语义扫描检测。"""
    bundle = TraceBundle(
        observation={"type": "user_query", "note": "I am tired"},
        reasoning_trace_id="rt-001",
        decision_trace_id="dt-001",
        action_result={"status": "executed"},
        outcome={"success": True},
    )
    builder = ExperienceBuilder()
    candidate = builder.build(bundle, ExperienceSource.DECISION, {})

    violations = ExperienceValidator.scan_for_self_patterns(candidate)
    assert len(violations) > 0
    assert any("self-pattern" in v for v in violations)


def test_self_pattern_blocked_in_context() -> None:
    """context 中的 Self 模式也应被检测。"""
    bundle = _complete_bundle()
    builder = ExperienceBuilder()
    candidate = builder.build(
        bundle,
        ExperienceSource.DECISION,
        context={"note": "I realized that I am different now"},
    )
    violations = ExperienceValidator.scan_for_self_patterns(candidate)
    assert len(violations) > 0


def test_clean_candidate_passes_pattern_scan() -> None:
    """不含 Self 语义的 Candidate 应通过扫描。"""
    bundle = _complete_bundle()
    builder = ExperienceBuilder()
    candidate = builder.build(bundle, ExperienceSource.DECISION, {})

    violations = ExperienceValidator.scan_for_self_patterns(candidate)
    assert len(violations) == 0


# ── Full Validation ──────────────────────────────────────────────────────────


def test_full_validation_clean() -> None:
    """全量验证: 干净 Candidate 应通过。"""
    bundle = _complete_bundle()
    builder = ExperienceBuilder()
    candidate = builder.build(bundle, ExperienceSource.DECISION, {})

    passed, violations = ExperienceValidator.full_validation(candidate)
    assert passed is True
    assert len(violations) == 0


def test_full_validation_dirty() -> None:
    """全量验证: 脏 Candidate 应被检测。"""
    bundle = TraceBundle(
        observation={"type": "user_query", "self": "I am weak"},
        reasoning_trace_id="rt-001",
        decision_trace_id="dt-001",
        action_result={"status": "executed"},
        outcome={"success": True},
    )
    builder = ExperienceBuilder()
    candidate = builder.build(bundle, ExperienceSource.DECISION, {})

    passed, violations = ExperienceValidator.full_validation(candidate)
    assert passed is False
    assert len(violations) > 0


# ── Completness Score ────────────────────────────────────────────────────────


def test_completeness_score_full() -> None:
    """五要素齐全 + Reflection → score >= 1.0。"""
    bundle = TraceBundle(
        observation={"type": "test"},
        reasoning_trace_id="rt-001",
        decision_trace_id="dt-001",
        action_result={"status": "done"},
        outcome={"success": True},
        reflection_trace_id="refl-001",
    )
    builder = ExperienceBuilder()
    candidate = builder.build(bundle, ExperienceSource.DECISION, {})

    assert candidate.completeness_score == 1.0


def test_completeness_score_partial() -> None:
    """缺少要素 → score < 1.0。"""
    bundle = TraceBundle(
        observation={"type": "test"},
        reasoning_trace_id="rt-001",
        decision_trace_id="dt-001",
        action_result={},          # 空 dict — 无效要素
        outcome={"success": True},
    )
    builder = ExperienceBuilder()
    candidate = builder.build(bundle, ExperienceSource.DECISION, {})

    assert candidate.completeness_score < 1.0
    # score = 4/5 = 0.8 (action_result is empty dict, truthy but incomplete)
    assert candidate.status == ExperienceStatus.COMPLETE  # 所有字段都有值


# ── Builder Edge Cases ───────────────────────────────────────────────────────


def test_builder_count() -> None:
    """builder.count() 应正确计数。"""
    bundle = _complete_bundle()
    builder = ExperienceBuilder()

    assert builder.count() == 0
    builder.build(bundle, ExperienceSource.DECISION, {})
    assert builder.count() == 1
    builder.build(bundle, ExperienceSource.REFLECTION, {})
    assert builder.count() == 2


def test_builder_clear() -> None:
    """clear() 应清空所有 Candidate。"""
    bundle = _complete_bundle()
    builder = ExperienceBuilder()
    builder.build(bundle, ExperienceSource.DECISION, {})
    builder.build(bundle, ExperienceSource.REFLECTION, {})

    assert builder.count() == 2
    builder.clear()
    assert builder.count() == 0
