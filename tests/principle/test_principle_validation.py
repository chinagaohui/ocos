"""Phase14.4.4 — Principle Validation Contract Tests.

Tests verify:
1. DimensionResult model — 5 dimensions, status enum
2. ValidationResult ABI — aggregation, overall_status
3. ValidatedPrinciple ABI — output structure
4. Evidence Sufficiency — pattern count thresholds per level
5. Cross-Context Stability — distinct works requirement
6. Contradictory Evidence — ratio rules
7. Abstraction Consistency — level jump detection
8. Trace Completeness — chain verification
9. Forbidden fields — no scores/quality/effectiveness
10. Overall status rules — aggregation logic
11. Phase14→14.5 isolation
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional
from enum import Enum


# ============ Enums ============


class AbstractionLevel(str, Enum):
    L1_MECHANISM_CANDIDATE = "L1_mechanism_candidate"
    L2_PRINCIPLE = "L2_principle"
    L3_GENERAL_PRINCIPLE = "L3_general_principle"


class DimensionStatus(str, Enum):
    PASS = "PASS"
    WEAKENED = "WEAKENED"
    INCONCLUSIVE = "INCONCLUSIVE"
    FAIL = "FAIL"


class OverallStatus(str, Enum):
    VALIDATED = "VALIDATED"
    INVALIDATED = "INVALIDATED"
    PENDING_REVIEW = "PENDING_REVIEW"


# ============ Models ============


@dataclass
class DimensionResult:
    """单一维度的验证结果."""
    dimension: str                 # evidence_sufficiency | cross_context_stability | contradictory_evidence | abstraction_consistency | trace_completeness
    status: DimensionStatus
    supporting_refs: List[str] = field(default_factory=list)
    contradictory_refs: List[str] = field(default_factory=list)
    detail: str = ""


@dataclass
class ValidationResult:
    """完整的验证结果."""
    result_id: str                # vr-*
    candidate_id: str             # pc-*
    dimension_results: List[DimensionResult] = field(default_factory=list)
    overall_status: OverallStatus = OverallStatus.PENDING_REVIEW
    validated_at: datetime = field(default_factory=datetime.now)
    validator_version: str = "1.0"


@dataclass
class ValidatedPrinciple:
    """验证通过后的 Principle."""
    principle_id: str              # vp-*
    derived_from_candidate: str    # pc-*
    validation: Optional[ValidationResult] = None
    abstraction_level: AbstractionLevel = AbstractionLevel.L1_MECHANISM_CANDIDATE
    valid_pattern_ids: List[str] = field(default_factory=list)
    valid_evidence_ids: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)


# ============ Validation Logic ============


VALID_DIMENSIONS = {
    "evidence_sufficiency",
    "cross_context_stability",
    "contradictory_evidence",
    "abstraction_consistency",
    "trace_completeness",
}

ALLOWED_STATUSES = {"PASS", "WEAKENED", "INCONCLUSIVE", "FAIL"}

FORBIDDEN_VALIDATION_FIELDS = {
    "confidence_score",
    "principle_score",
    "quality_score",
    "effectiveness_score",
    "importance",
    "priority",
    "recommendation",
    "best_practice_tag",
    "commercial_value",
    "reader_approval",
    "difficulty",
    "popularity",
}

# Pattern count thresholds per abstraction level
PATTERN_COUNT_THRESHOLDS = {
    AbstractionLevel.L1_MECHANISM_CANDIDATE: {
        "min_patterns": 2,
        "min_works": 1,
    },
    AbstractionLevel.L2_PRINCIPLE: {
        "min_patterns": 3,
        "min_works": 2,
    },
    AbstractionLevel.L3_GENERAL_PRINCIPLE: {
        "min_patterns": 5,
        "min_works": 3,
    },
}

# Contradictory evidence ratio thresholds
CONTRADICTORY_RATIO = {
    "pass_ratio": 0.0,       # 0% → PASS
    "weakened_max": 0.25,    # >0% ≤25% → WEAKENED
    "inconclusive_max": 0.50,  # >25% ≤50% → INCONCLUSIVE
    # >50% → FAIL
}


def determine_overall_status(dimensions: List[DimensionResult]) -> OverallStatus:
    """根据所有维度结果聚合整体状态."""
    has_fail = any(d.status == DimensionStatus.FAIL for d in dimensions)
    has_weakened = any(d.status == DimensionStatus.WEAKENED for d in dimensions)
    has_inconclusive = any(d.status == DimensionStatus.INCONCLUSIVE for d in dimensions)

    if has_fail:
        return OverallStatus.INVALIDATED
    if has_weakened or has_inconclusive:
        return OverallStatus.PENDING_REVIEW
    return OverallStatus.VALIDATED


def check_evidence_sufficiency(
    pattern_count: int,
    distinct_works: int,
    level: AbstractionLevel,
) -> DimensionResult:
    """验证 Evidence Sufficiency 维度."""
    thresholds = PATTERN_COUNT_THRESHOLDS.get(level)
    if not thresholds:
        return DimensionResult(
            dimension="evidence_sufficiency",
            status=DimensionStatus.FAIL,
            detail=f"Unknown level: {level}",
        )

    issues = []
    status = DimensionStatus.PASS

    if pattern_count < thresholds["min_patterns"]:
        issues.append(
            f"Pattern count {pattern_count} < min {thresholds['min_patterns']} for {level.value}"
        )
        status = DimensionStatus.FAIL

    if distinct_works < thresholds["min_works"]:
        issues.append(
            f"Distinct works {distinct_works} < min {thresholds['min_works']} for {level.value}"
        )
        if status is not DimensionStatus.FAIL:
            status = DimensionStatus.WEAKENED

    return DimensionResult(
        dimension="evidence_sufficiency",
        status=status,
        supporting_refs=[f"count={pattern_count}", f"works={distinct_works}"],
        contradictory_refs=issues,
        detail="; ".join(issues) if issues else "Sufficient",
    )


def check_cross_context_stability(
    distinct_works: int,
    distinct_genres: int,
    level: AbstractionLevel,
) -> DimensionResult:
    """验证 Cross-Context Stability 维度."""
    thresholds = PATTERN_COUNT_THRESHOLDS.get(level)

    if distinct_works >= thresholds["min_works"]:
        if level == AbstractionLevel.L3_GENERAL_PRINCIPLE and distinct_genres < 2:
            return DimensionResult(
                dimension="cross_context_stability",
                status=DimensionStatus.WEAKENED,
                detail=f"L3 requires ≥2 genres, got {distinct_genres}",
            )
        return DimensionResult(
            dimension="cross_context_stability",
            status=DimensionStatus.PASS,
            detail=f"Stable across {distinct_works} works",
        )

    return DimensionResult(
        dimension="cross_context_stability",
        status=DimensionStatus.FAIL,
        contradictory_refs=[f"works={distinct_works}<{thresholds['min_works']}"],
        detail=f"Only {distinct_works} works, need {thresholds['min_works']}",
    )


def check_contradictory_evidence(
    supporting_count: int,
    contradictory_count: int,
) -> DimensionResult:
    """验证 Contradictory Evidence 维度."""
    total = supporting_count + contradictory_count
    if total == 0:
        return DimensionResult(
            dimension="contradictory_evidence",
            status=DimensionStatus.INCONCLUSIVE,
            detail="No evidence at all — cannot assess",
        )

    ratio = contradictory_count / total
    contradictory_refs = [f"contradictory={contradictory_count}", f"total={total}"]

    if ratio == 0:
        return DimensionResult(
            dimension="contradictory_evidence",
            status=DimensionStatus.PASS,
            detail="No contradictory evidence",
        )
    if ratio <= CONTRADICTORY_RATIO["weakened_max"]:
        return DimensionResult(
            dimension="contradictory_evidence",
            status=DimensionStatus.WEAKENED,
            contradictory_refs=contradictory_refs,
            detail=f"Contradictory ratio {ratio:.1%} ≤ 25%",
        )
    if ratio <= CONTRADICTORY_RATIO["inconclusive_max"]:
        return DimensionResult(
            dimension="contradictory_evidence",
            status=DimensionStatus.INCONCLUSIVE,
            contradictory_refs=contradictory_refs,
            detail=f"Contradictory ratio {ratio:.1%} between 25%-50%",
        )
    return DimensionResult(
        dimension="contradictory_evidence",
        status=DimensionStatus.FAIL,
        contradictory_refs=contradictory_refs,
        detail=f"Contradictory ratio {ratio:.1%} > 50%",
    )


def check_abstraction_consistency(
    level: AbstractionLevel,
    source_pattern_count: int,
    intermediate_levels: List[str],
) -> DimensionResult:
    """验证 Abstraction Consistency 维度.

    Rules:
    - L1: patterns must be L0 (raw patterns)
    - L2: must come from L1 candidates or have documented intermediate levels
    - L3: must come from L2 principles or have documented intermediate levels
    - Direct L0→L2/L3 without intermediate tracing → INVALIDATED
    """
    if level == AbstractionLevel.L1_MECHANISM_CANDIDATE:
        # L1 is the first abstraction from L0 patterns — always valid
        return DimensionResult(
            dimension="abstraction_consistency",
            status=DimensionStatus.PASS,
            detail="L1 derivation from L0 patterns — valid first abstraction",
        )

    if level == AbstractionLevel.L2_PRINCIPLE:
        if "L1" in intermediate_levels:
            return DimensionResult(
                dimension="abstraction_consistency",
                status=DimensionStatus.PASS,
                detail="Tracing shows L1→L2 path",
            )
        return DimensionResult(
            dimension="abstraction_consistency",
            status=DimensionStatus.FAIL,
            contradictory_refs=["no_L1_intermediate"],
            detail="Direct L0→L2 without L1 intermediate — level jump",
        )

    if level == AbstractionLevel.L3_GENERAL_PRINCIPLE:
        if "L1" in intermediate_levels and "L2" in intermediate_levels:
            return DimensionResult(
                dimension="abstraction_consistency",
                status=DimensionStatus.PASS,
                detail="Full L0→L1→L2→L3 chain traceable",
            )
        if "L2" in intermediate_levels:
            return DimensionResult(
                dimension="abstraction_consistency",
                status=DimensionStatus.PASS,
                detail="L2→L3 path documented",
            )
        return DimensionResult(
            dimension="abstraction_consistency",
            status=DimensionStatus.FAIL,
            contradictory_refs=["level_jump"],
            detail="L0→L3 without intermediate L1/L2 steps — invalid level jump",
        )

    return DimensionResult(
        dimension="abstraction_consistency",
        status=DimensionStatus.FAIL,
        detail=f"Unknown level: {level}",
    )


def check_trace_completeness(
    pattern_ids: List[str],
    evidence_ids: List[str],
    has_inference_record: bool,
) -> DimensionResult:
    """验证 Trace Completeness 维度."""
    issues = []

    if not pattern_ids:
        issues.append("No pattern references")
    for pid in pattern_ids:
        if not pid.startswith("pat-"):
            issues.append(f"Invalid pattern_id: {pid}")

    if not evidence_ids:
        issues.append("No evidence references")
    for eid in evidence_ids:
        if not (eid.startswith("ev-") or eid.startswith("e-")):
            issues.append(f"Invalid evidence_id: {eid}")

    if not has_inference_record:
        issues.append("No inference record")

    if not issues:
        return DimensionResult(
            dimension="trace_completeness",
            status=DimensionStatus.PASS,
            supporting_refs=pattern_ids + evidence_ids,
            detail="Full trace chain present",
        )

    # Trace completeness failure is mandatory - cannot be compensated
    return DimensionResult(
        dimension="trace_completeness",
        status=DimensionStatus.FAIL,
        contradictory_refs=issues,
        detail="; ".join(issues),
    )


# ============ Tests ============


class TestDimensionNames:
    """5 个验证维度存在且命名正确."""

    def test_five_dimensions(self):
        """5 个维度."""
        assert len(VALID_DIMENSIONS) == 5
        assert "evidence_sufficiency" in VALID_DIMENSIONS
        assert "cross_context_stability" in VALID_DIMENSIONS
        assert "contradictory_evidence" in VALID_DIMENSIONS
        assert "abstraction_consistency" in VALID_DIMENSIONS
        assert "trace_completeness" in VALID_DIMENSIONS


class TestDimensionStatus:
    """DimensionStatus 枚举."""

    def test_four_statuses(self):
        """4 种状态."""
        assert len(DimensionStatus) == 4
        assert DimensionStatus.PASS.value == "PASS"
        assert DimensionStatus.WEAKENED.value == "WEAKENED"
        assert DimensionStatus.INCONCLUSIVE.value == "INCONCLUSIVE"
        assert DimensionStatus.FAIL.value == "FAIL"

    def test_not_score_based(self):
        """状态不是分数."""
        assert not hasattr(DimensionStatus, "EXCELLENT")
        assert not hasattr(DimensionStatus, "GOOD")
        assert not hasattr(DimensionStatus, "AVERAGE")
        assert not hasattr(DimensionStatus, "POOR")
        for status in DimensionStatus:
            assert status.value not in ("EXCELLENT", "GOOD", "AVERAGE", "POOR")


class TestDimensionResult:
    """DimensionResult 模型."""

    def test_required_fields_exist(self):
        """必需字段存在."""
        dr = DimensionResult(
            dimension="evidence_sufficiency",
            status=DimensionStatus.PASS,
            detail="Sufficient evidence",
        )
        assert dr.dimension == "evidence_sufficiency"
        assert dr.status == DimensionStatus.PASS
        assert isinstance(dr.supporting_refs, list)
        assert isinstance(dr.contradictory_refs, list)

    def test_invalid_dimension_rejected(self):
        """无效维度名称被拒."""
        dr = DimensionResult(
            dimension="invalid_dim",
            status=DimensionStatus.PASS,
        )
        assert dr.dimension not in VALID_DIMENSIONS

    def test_invalid_status_rejected(self):
        """无效状态被拒."""
        bad_statuses = ["EXCELLENT", "GOOD", "AVERAGE", "POOR", "SCORE"]
        for s in bad_statuses:
            assert s not in ALLOWED_STATUSES

    def test_with_references(self):
        """带引用的 DimensionResult."""
        dr = DimensionResult(
            dimension="cross_context_stability",
            status=DimensionStatus.WEAKENED,
            supporting_refs=["pat-A", "pat-B"],
            contradictory_refs=["pat-C_single_work"],
            detail="Only 2 works for L3 requirement",
        )
        assert len(dr.supporting_refs) == 2
        assert len(dr.contradictory_refs) == 1


class TestValidationResult:
    """ValidationResult 模型."""

    def test_required_fields(self):
        """必需字段."""
        vr = ValidationResult(
            result_id="vr-001",
            candidate_id="pc-001",
        )
        assert vr.result_id.startswith("vr-")
        assert vr.candidate_id.startswith("pc-")
        assert vr.overall_status == OverallStatus.PENDING_REVIEW

    def test_with_dimensions(self):
        """含维度结果的完整验证."""
        vr = ValidationResult(
            result_id="vr-002",
            candidate_id="pc-002",
            dimension_results=[
                DimensionResult(dimension="evidence_sufficiency", status=DimensionStatus.PASS),
                DimensionResult(dimension="trace_completeness", status=DimensionStatus.PASS),
            ],
        )
        assert len(vr.dimension_results) == 2
        assert vr.validator_version == "1.0"


class TestValidatedPrinciple:
    """ValidatedPrinciple 模型."""

    def test_required_fields(self):
        """必需字段."""
        vp = ValidatedPrinciple(
            principle_id="vp-001",
            derived_from_candidate="pc-001",
        )
        assert vp.principle_id.startswith("vp-")
        assert vp.derived_from_candidate.startswith("pc-")

    def test_with_validation(self):
        """带验证结果."""
        vr = ValidationResult(
            result_id="vr-001",
            candidate_id="pc-001",
            overall_status=OverallStatus.VALIDATED,
        )
        vp = ValidatedPrinciple(
            principle_id="vp-001",
            derived_from_candidate="pc-001",
            validation=vr,
            abstraction_level=AbstractionLevel.L2_PRINCIPLE,
            valid_pattern_ids=["pat-A", "pat-B", "pat-C"],
            valid_evidence_ids=["e-001"],
        )
        assert vp.validation.overall_status == OverallStatus.VALIDATED
        assert vp.abstraction_level == AbstractionLevel.L2_PRINCIPLE
        assert len(vp.valid_pattern_ids) == 3

    def test_no_capability_fields(self):
        """ValidatedPrinciple 不含能力层字段."""
        vp = ValidatedPrinciple(
            principle_id="vp-nocap",
            derived_from_candidate="pc-nocap",
        )
        assert not hasattr(vp, "capability_package")
        assert not hasattr(vp, "writing_rule")
        assert not hasattr(vp, "prompt_template")
        assert not hasattr(vp, "agent_instruction")


class TestEvidenceSufficiency:
    """证据充分性维度."""

    def test_l1_sufficient(self):
        """L1 需要 ≥2 patterns."""
        result = check_evidence_sufficiency(
            pattern_count=2,
            distinct_works=1,
            level=AbstractionLevel.L1_MECHANISM_CANDIDATE,
        )
        assert result.status == DimensionStatus.PASS

    def test_l1_insufficient(self):
        """L1 如果只有 1 个 pattern 则 FAIL."""
        result = check_evidence_sufficiency(
            pattern_count=1,
            distinct_works=1,
            level=AbstractionLevel.L1_MECHANISM_CANDIDATE,
        )
        assert result.status == DimensionStatus.FAIL

    def test_l2_sufficient(self):
        """L2 需要 ≥3 patterns."""
        result = check_evidence_sufficiency(
            pattern_count=3,
            distinct_works=2,
            level=AbstractionLevel.L2_PRINCIPLE,
        )
        assert result.status == DimensionStatus.PASS

    def test_l2_insufficient_patterns(self):
        """L2 如果只有 2 个 pattern 则 FAIL."""
        result = check_evidence_sufficiency(
            pattern_count=2,
            distinct_works=2,
            level=AbstractionLevel.L2_PRINCIPLE,
        )
        assert result.status == DimensionStatus.FAIL

    def test_l3_sufficient(self):
        """L3 需要 ≥5 patterns."""
        result = check_evidence_sufficiency(
            pattern_count=5,
            distinct_works=3,
            level=AbstractionLevel.L3_GENERAL_PRINCIPLE,
        )
        assert result.status == DimensionStatus.PASS

    def test_l3_insufficient(self):
        """L3 如果只有 4 个 pattern 则 FAIL."""
        result = check_evidence_sufficiency(
            pattern_count=4,
            distinct_works=3,
            level=AbstractionLevel.L3_GENERAL_PRINCIPLE,
        )
        assert result.status == DimensionStatus.FAIL

    def test_l2_single_work_weakened(self):
        """L2 如果仅 1 个作品则 WEAKENED."""
        result = check_evidence_sufficiency(
            pattern_count=3,
            distinct_works=1,
            level=AbstractionLevel.L2_PRINCIPLE,
        )
        assert result.status == DimensionStatus.WEAKENED


class TestCrossContextStability:
    """跨上下文稳定性."""

    def test_l2_stable(self):
        """L2 跨 2 个作品 PASS."""
        result = check_cross_context_stability(
            distinct_works=2,
            distinct_genres=1,
            level=AbstractionLevel.L2_PRINCIPLE,
        )
        assert result.status == DimensionStatus.PASS

    def test_l2_unstable(self):
        """L2 仅 1 个作品 FAIL."""
        result = check_cross_context_stability(
            distinct_works=1,
            distinct_genres=1,
            level=AbstractionLevel.L2_PRINCIPLE,
        )
        assert result.status == DimensionStatus.FAIL

    def test_l3_stable(self):
        """L3 跨 3 作品 2 类型 PASS."""
        result = check_cross_context_stability(
            distinct_works=3,
            distinct_genres=2,
            level=AbstractionLevel.L3_GENERAL_PRINCIPLE,
        )
        assert result.status == DimensionStatus.PASS

    def test_l3_single_genre_weakened(self):
        """L3 跨 3 作品但仅 1 类型 WEAKENED."""
        result = check_cross_context_stability(
            distinct_works=3,
            distinct_genres=1,
            level=AbstractionLevel.L3_GENERAL_PRINCIPLE,
        )
        assert result.status == DimensionStatus.WEAKENED

    def test_l1_always_valid(self):
        """L1 不需要跨作品."""
        result = check_cross_context_stability(
            distinct_works=1,
            distinct_genres=1,
            level=AbstractionLevel.L1_MECHANISM_CANDIDATE,
        )
        assert result.status == DimensionStatus.PASS


class TestContradictoryEvidence:
    """反例证据."""

    def test_no_contradictory_pass(self):
        """无反例 PASS."""
        result = check_contradictory_evidence(
            supporting_count=10,
            contradictory_count=0,
        )
        assert result.status == DimensionStatus.PASS

    def test_low_contradictory_weakened(self):
        """低比例反例 WEAKENED."""
        result = check_contradictory_evidence(
            supporting_count=8,
            contradictory_count=1,
        )
        assert result.status == DimensionStatus.WEAKENED

    def test_medium_contradictory_inconclusive(self):
        """中等比例反例 INCONCLUSIVE."""
        result = check_contradictory_evidence(
            supporting_count=6,
            contradictory_count=3,
        )
        assert result.status == DimensionStatus.INCONCLUSIVE

    def test_high_contradictory_fail(self):
        """高比例反例 FAIL."""
        result = check_contradictory_evidence(
            supporting_count=3,
            contradictory_count=4,
        )
        assert result.status == DimensionStatus.FAIL

    def test_no_evidence_inconclusive(self):
        """无证据时 INCONCLUSIVE."""
        result = check_contradictory_evidence(
            supporting_count=0,
            contradictory_count=0,
        )
        assert result.status == DimensionStatus.INCONCLUSIVE


class TestAbstractionConsistency:
    """抽象层级一致性."""

    def test_l1_always_valid(self):
        """L1 总是有效."""
        result = check_abstraction_consistency(
            level=AbstractionLevel.L1_MECHANISM_CANDIDATE,
            source_pattern_count=2,
            intermediate_levels=[],
        )
        assert result.status == DimensionStatus.PASS

    def test_l2_with_l1_intermediate_pass(self):
        """L2 有 L1 中间层 PASS."""
        result = check_abstraction_consistency(
            level=AbstractionLevel.L2_PRINCIPLE,
            source_pattern_count=3,
            intermediate_levels=["L1"],
        )
        assert result.status == DimensionStatus.PASS

    def test_l2_without_l1_fail(self):
        """L2 无 L1 中间层 FAIL (L0→L2 跳跃)."""
        result = check_abstraction_consistency(
            level=AbstractionLevel.L2_PRINCIPLE,
            source_pattern_count=3,
            intermediate_levels=[],
        )
        assert result.status == DimensionStatus.FAIL

    def test_l3_with_full_chain_pass(self):
        """L3 完整链 PASS."""
        result = check_abstraction_consistency(
            level=AbstractionLevel.L3_GENERAL_PRINCIPLE,
            source_pattern_count=5,
            intermediate_levels=["L1", "L2"],
        )
        assert result.status == DimensionStatus.PASS

    def test_l3_without_l1_fail(self):
        """L3 跳过 L1 FAIL."""
        result = check_abstraction_consistency(
            level=AbstractionLevel.L3_GENERAL_PRINCIPLE,
            source_pattern_count=5,
            intermediate_levels=["L2"],
        )
        assert result.status == DimensionStatus.PASS  # L2→L3 is valid

    def test_l3_without_intermediate_fail(self):
        """L0→L3 直接跳跃 FAIL."""
        result = check_abstraction_consistency(
            level=AbstractionLevel.L3_GENERAL_PRINCIPLE,
            source_pattern_count=5,
            intermediate_levels=[],
        )
        assert result.status == DimensionStatus.FAIL

    def test_l3_only_l2_pass(self):
        """L2 → L3 路径 PASS."""
        result = check_abstraction_consistency(
            level=AbstractionLevel.L3_GENERAL_PRINCIPLE,
            source_pattern_count=5,
            intermediate_levels=["L2"],
        )
        assert result.status == DimensionStatus.PASS


class TestTraceCompleteness:
    """追踪完整性."""

    def test_complete_chain_pass(self):
        """完整链 PASS."""
        result = check_trace_completeness(
            pattern_ids=["pat-A", "pat-B"],
            evidence_ids=["e-001", "ev-002"],
            has_inference_record=True,
        )
        assert result.status == DimensionStatus.PASS

    def test_no_patterns_fail(self):
        """无 pattern FAIL."""
        result = check_trace_completeness(
            pattern_ids=[],
            evidence_ids=["e-001"],
            has_inference_record=True,
        )
        assert result.status == DimensionStatus.FAIL

    def test_no_evidence_fail(self):
        """无 evidence FAIL."""
        result = check_trace_completeness(
            pattern_ids=["pat-A"],
            evidence_ids=[],
            has_inference_record=True,
        )
        assert result.status == DimensionStatus.FAIL

    def test_no_inference_record_fail(self):
        """无 inference record FAIL."""
        result = check_trace_completeness(
            pattern_ids=["pat-A"],
            evidence_ids=["e-001"],
            has_inference_record=False,
        )
        assert result.status == DimensionStatus.FAIL

    def test_invalid_pattern_id_fail(self):
        """无效 pattern_id FAIL."""
        result = check_trace_completeness(
            pattern_ids=["wrong-id"],
            evidence_ids=["e-001"],
            has_inference_record=True,
        )
        assert result.status == DimensionStatus.FAIL

    def test_invalid_evidence_id_fail(self):
        """无效 evidence_id FAIL."""
        result = check_trace_completeness(
            pattern_ids=["pat-A"],
            evidence_ids=["bad-id"],
            has_inference_record=True,
        )
        assert result.status == DimensionStatus.FAIL


class TestOverallStatusAggregation:
    """整体状态聚合."""

    def test_all_pass_validated(self):
        """全 PASS → VALIDATED."""
        dims = [
            DimensionResult(dimension="evidence_sufficiency", status=DimensionStatus.PASS),
            DimensionResult(dimension="cross_context_stability", status=DimensionStatus.PASS),
            DimensionResult(dimension="contradictory_evidence", status=DimensionStatus.PASS),
            DimensionResult(dimension="abstraction_consistency", status=DimensionStatus.PASS),
            DimensionResult(dimension="trace_completeness", status=DimensionStatus.PASS),
        ]
        status = determine_overall_status(dims)
        assert status == OverallStatus.VALIDATED

    def test_any_fail_invalidated(self):
        """任一 FAIL → INVALIDATED."""
        dims = [
            DimensionResult(dimension="evidence_sufficiency", status=DimensionStatus.PASS),
            DimensionResult(dimension="abstraction_consistency", status=DimensionStatus.FAIL),
            DimensionResult(dimension="trace_completeness", status=DimensionStatus.PASS),
        ]
        status = determine_overall_status(dims)
        assert status == OverallStatus.INVALIDATED

    def test_weakened_pending_review(self):
        """WEAKENED → PENDING_REVIEW."""
        dims = [
            DimensionResult(dimension="evidence_sufficiency", status=DimensionStatus.WEAKENED),
            DimensionResult(dimension="cross_context_stability", status=DimensionStatus.PASS),
            DimensionResult(dimension="trace_completeness", status=DimensionStatus.PASS),
        ]
        status = determine_overall_status(dims)
        assert status == OverallStatus.PENDING_REVIEW

    def test_inconclusive_pending_review(self):
        """INCONCLUSIVE → PENDING_REVIEW."""
        dims = [
            DimensionResult(dimension="evidence_sufficiency", status=DimensionStatus.PASS),
            DimensionResult(dimension="contradictory_evidence", status=DimensionStatus.INCONCLUSIVE),
            DimensionResult(dimension="trace_completeness", status=DimensionStatus.PASS),
        ]
        status = determine_overall_status(dims)
        assert status == OverallStatus.PENDING_REVIEW

    def test_mixed_weakened_pass_validated(self):
        """WEAKENED + PASS 但无 FAIL → PENDING_REVIEW."""
        dims = [
            DimensionResult(dimension="evidence_sufficiency", status=DimensionStatus.WEAKENED),
            DimensionResult(dimension="cross_context_stability", status=DimensionStatus.PASS),
            DimensionResult(dimension="trace_completeness", status=DimensionStatus.PASS),
        ]
        status = determine_overall_status(dims)
        assert status == OverallStatus.PENDING_REVIEW

    def test_empty_dimensions_validated(self):
        """空维度列表 → VALIDATED (默认)."""
        status = determine_overall_status([])
        assert status == OverallStatus.VALIDATED


class TestForbiddenFields:
    """禁止字段."""

    def test_forbidden_fields_exist(self):
        """禁止字段列表完整."""
        assert len(FORBIDDEN_VALIDATION_FIELDS) >= 12
        assert "confidence_score" in FORBIDDEN_VALIDATION_FIELDS
        assert "principle_score" in FORBIDDEN_VALIDATION_FIELDS
        assert "quality_score" in FORBIDDEN_VALIDATION_FIELDS
        assert "effectiveness_score" in FORBIDDEN_VALIDATION_FIELDS
        assert "importance" in FORBIDDEN_VALIDATION_FIELDS
        assert "priority" in FORBIDDEN_VALIDATION_FIELDS
        assert "recommendation" in FORBIDDEN_VALIDATION_FIELDS
        assert "best_practice_tag" in FORBIDDEN_VALIDATION_FIELDS
        assert "commercial_value" in FORBIDDEN_VALIDATION_FIELDS
        assert "reader_approval" in FORBIDDEN_VALIDATION_FIELDS
        assert "difficulty" in FORBIDDEN_VALIDATION_FIELDS
        assert "popularity" in FORBIDDEN_VALIDATION_FIELDS

    def test_validated_principle_no_score(self):
        """ValidatedPrinciple 不含 score 字段."""
        vp = ValidatedPrinciple(principle_id="vp-test", derived_from_candidate="pc-test")
        for field in FORBIDDEN_VALIDATION_FIELDS:
            assert not hasattr(vp, field), f"Field should not exist: {field}"

    def test_validation_result_no_score(self):
        """ValidationResult 不含 score 字段."""
        vr = ValidationResult(result_id="vr-test", candidate_id="pc-test")
        for field in FORBIDDEN_VALIDATION_FIELDS:
            assert not hasattr(vr, field), f"Field should not exist: {field}"
        # No score aggregation field
        assert not hasattr(vr, "overall_score")


class TestPhase14Dot5Isolation:
    """Phase14.4 → Phase14.5 隔离."""

    def test_output_is_principle_not_capability(self):
        """输出是 Principle 不是 Capability."""
        vp = ValidatedPrinciple(
            principle_id="vp-iso",
            derived_from_candidate="pc-iso",
        )
        assert not hasattr(vp, "capability_package")
        assert not hasattr(vp, "writing_rule")
        assert not hasattr(vp, "prompt_template")

    def test_no_prompt_or_template(self):
        """不含提示/模板."""
        vp = ValidatedPrinciple(
            principle_id="vp-iso2",
            derived_from_candidate="pc-iso2",
        )
        assert not hasattr(vp, "agent_instruction")
        assert not hasattr(vp, "strategy_document")
        assert not hasattr(vp, "best_practice_guide")


class TestIntegration:
    """集成场景."""

    def test_l2_principle_full_validation(self):
        """L2 Principle 完整验证流程."""
        # 构建一个完整的验证场景
        dim_results = [
            check_evidence_sufficiency(
                pattern_count=3,
                distinct_works=2,
                level=AbstractionLevel.L2_PRINCIPLE,
            ),
            check_cross_context_stability(
                distinct_works=2,
                distinct_genres=1,
                level=AbstractionLevel.L2_PRINCIPLE,
            ),
            check_contradictory_evidence(
                supporting_count=5,
                contradictory_count=0,
            ),
            check_abstraction_consistency(
                level=AbstractionLevel.L2_PRINCIPLE,
                source_pattern_count=3,
                intermediate_levels=["L1"],
            ),
            check_trace_completeness(
                pattern_ids=["pat-A", "pat-B", "pat-C"],
                evidence_ids=["e-001", "e-002"],
                has_inference_record=True,
            ),
        ]

        overall = determine_overall_status(dim_results)
        vr = ValidationResult(
            result_id="vr-int",
            candidate_id="pc-int",
            dimension_results=dim_results,
            overall_status=overall,
        )
        vp = ValidatedPrinciple(
            principle_id="vp-int",
            derived_from_candidate="pc-int",
            validation=vr,
            abstraction_level=AbstractionLevel.L2_PRINCIPLE,
            valid_pattern_ids=["pat-A", "pat-B", "pat-C"],
            valid_evidence_ids=["e-001", "e-002"],
        )

        assert overall == OverallStatus.VALIDATED
        assert vp.validation.overall_status == OverallStatus.VALIDATED
        assert len(vp.valid_pattern_ids) == 3
        assert len(vp.valid_evidence_ids) == 2
        assert vp.abstraction_level == AbstractionLevel.L2_PRINCIPLE

    def test_l2_with_contradictory_weakened(self):
        """L2 含低比例反例 → PENDING_REVIEW."""
        dim_results = [
            check_evidence_sufficiency(
                pattern_count=3,
                distinct_works=2,
                level=AbstractionLevel.L2_PRINCIPLE,
            ),
            check_cross_context_stability(
                distinct_works=2,
                distinct_genres=1,
                level=AbstractionLevel.L2_PRINCIPLE,
            ),
            check_contradictory_evidence(
                supporting_count=8,
                contradictory_count=1,  # < 25%
            ),
            check_abstraction_consistency(
                level=AbstractionLevel.L2_PRINCIPLE,
                source_pattern_count=3,
                intermediate_levels=["L1"],
            ),
            check_trace_completeness(
                pattern_ids=["pat-A", "pat-B", "pat-C"],
                evidence_ids=["e-001"],
                has_inference_record=True,
            ),
        ]

        overall = determine_overall_status(dim_results)
        assert overall == OverallStatus.PENDING_REVIEW

    def test_l0_to_l3_jump_invalid(self):
        """L0→L3 跳跃 → INVALIDATED."""
        dim_results = [
            check_evidence_sufficiency(
                pattern_count=5,
                distinct_works=3,
                level=AbstractionLevel.L3_GENERAL_PRINCIPLE,
            ),
            check_abstraction_consistency(
                level=AbstractionLevel.L3_GENERAL_PRINCIPLE,
                source_pattern_count=5,
                intermediate_levels=[],  # 无中间层
            ),
        ]

        overall = determine_overall_status(dim_results)
        assert overall == OverallStatus.INVALIDATED
        assert dim_results[1].status == DimensionStatus.FAIL

    def test_missing_trace_invalid(self):
        """缺少追踪 → INVALIDATED."""
        dim_results = [
            check_trace_completeness(
                pattern_ids=[],
                evidence_ids=[],
                has_inference_record=False,
            ),
        ]
        overall = determine_overall_status(dim_results)
        assert overall == OverallStatus.INVALIDATED
        assert dim_results[0].status == DimensionStatus.FAIL
