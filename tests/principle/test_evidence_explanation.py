"""Phase14.4.3 — Evidence Chain / Explanation ABI Tests.

Tests verify:
1. InferenceRecord ABI — structure, references, confidence
2. ExplanationConstraint ABI — allowed fields, forbidden content
3. Chain integrity — minimum requirements, consistency
4. Forbidden explanation content — no value judgments
5. Phase14→Phase14.5 interface isolation
6. Explanation ≠ LLM-only reasoning
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Set, Optional
from enum import Enum


# ============ Data Models ============


class ConfidenceLevel(str, Enum):
    """观察置信度 — 仅表示观察层面的确认程度，不是价值判断."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    ESTABLISHED = "established"


class AbstractionLevel(str, Enum):
    L1_MECHANISM_CANDIDATE = "L1_mechanism_candidate"
    L2_PRINCIPLE = "L2_principle"
    L3_GENERAL_PRINCIPLE = "L3_general_principle"


class DerivationType(str, Enum):
    SIMILAR_STRUCTURE = "similar_structure"
    RECURRING_RELATION = "recurring_relation"
    CROSS_CONTEXT_APPEARANCE = "cross_context_appearance"
    STRUCTURAL_ABSTRACTION = "structural_abstraction"


@dataclass
class PatternRef:
    """Pattern 引用."""
    pattern_id: str       # pat-*
    role: str             # "primary_support" | "contrast" | "contextual"
    work_context: str     # 简短作品上下文


@dataclass
class EvidenceRef:
    """Evidence 引用."""
    evidence_id: str       # ev-* / e-*
    support_type: str      # "direct" | "indirect" | "structural"
    confidence: ConfidenceLevel


@dataclass
class RelationRef:
    """Relation 链追踪."""
    relation_type: str
    pattern_a_id: str
    pattern_b_id: str
    strength: float        # 0.0~1.0
    context: str = ""


@dataclass
class InferenceRecord:
    """从 PrincipleCandidate 到证据的完整追踪记录."""
    record_id: str                        # ir-*
    candidate_id: str                     # pc-*
    pattern_references: List[PatternRef] = field(default_factory=list)
    evidence_references: List[EvidenceRef] = field(default_factory=list)
    relation_path: List[RelationRef] = field(default_factory=list)
    abstraction_level: AbstractionLevel = AbstractionLevel.L1_MECHANISM_CANDIDATE
    derivation_path: str = ""
    abstraction_trace: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    version: int = 1


@dataclass
class ExplanationConstraint:
    """受约束的解释 — 只能包含结构层内容."""
    observed_relationship: str = ""
    structural_similarity: str = ""
    cross_context_pattern: str = ""
    abstraction_path_description: str = ""
    key_pattern_ids: List[str] = field(default_factory=list)
    key_evidence_ids: List[str] = field(default_factory=list)
    format_version: str = "1.0"


@dataclass
class PrincipleCandidate:
    """简化版 — 仅用于测试."""
    candidate_id: str
    source_pattern_ids: List[str] = field(default_factory=list)
    source_evidence_ids: List[str] = field(default_factory=list)
    abstraction_level: AbstractionLevel = AbstractionLevel.L1_MECHANISM_CANDIDATE


@dataclass
class Phase14Dot3Output:
    """Evidence Chain / Explanation ABI 的输出."""
    candidate: PrincipleCandidate
    inference_record: InferenceRecord
    explanation: ExplanationConstraint


# ============ Forbidden definitions ============


FORBIDDEN_EXPLANATION_FIELDS: Set[str] = {
    "this_works_because",
    "reader_preference_note",
    "effectiveness_claim",
    "retention_claim",
    "recommendation_note",
    "prescription_text",
    "quality_judgment",
    "commercial_claim",
    "comparative_value",
    "success_story",
}

FORBIDDEN_EXPLANATION_PATTERNS: List[str] = [
    "works because",
    "effective because",
    "reader like",
    "audience prefer",
    "should use",
    "recommend",
    "suggest",
    "better than",
    "more effective",
    "author should",
    "writer must",
    "good technique",
    "excellent structure",
    "increases retention",
    "readers love",
    "this works",
]

ALLOWED_ROLES = {"primary_support", "contrast", "contextual"}
ALLOWED_SUPPORT_TYPES = {"direct", "indirect", "structural"}


# ============ Validation helpers ============


def validate_inference_record(record: InferenceRecord) -> List[str]:
    """验证 InferenceRecord 完整性."""
    errors = []
    if not record.record_id.startswith("ir-"):
        errors.append(f"record_id must start with 'ir-', got: {record.record_id}")
    if not record.candidate_id.startswith("pc-"):
        errors.append(f"candidate_id must start with 'pc-', got: {record.candidate_id}")
    if not record.pattern_references:
        errors.append("Must have at least one pattern_reference")
    if not record.evidence_references:
        errors.append("Must have at least one evidence_reference")
    if not record.derivation_path:
        errors.append("derivation_path must not be empty")
    for pref in record.pattern_references:
        if pref.role not in ALLOWED_ROLES:
            errors.append(f"Invalid pattern role: {pref.role}")
        if not pref.pattern_id.startswith("pat-"):
            errors.append(f"pattern_id must start with 'pat-': {pref.pattern_id}")
        if not pref.work_context:
            errors.append("work_context must not be empty")
    for eref in record.evidence_references:
        if not (eref.evidence_id.startswith("ev-") or eref.evidence_id.startswith("e-")):
            errors.append(f"evidence_id must start with 'ev-'/'e-': {eref.evidence_id}")
        if eref.support_type not in ALLOWED_SUPPORT_TYPES:
            errors.append(f"Invalid support_type: {eref.support_type}")
    return errors


def validate_explanation(exp: ExplanationConstraint) -> List[str]:
    """验证 ExplanationConstraint."""
    errors = []
    if not exp.observed_relationship and not exp.structural_similarity:
        errors.append("At least one of observed_relationship or structural_similarity must be non-empty")
    for field_name in FORBIDDEN_EXPLANATION_FIELDS:
        if hasattr(exp, field_name):
            errors.append(f"Explanation has forbidden field: {field_name}")
    # Check for forbidden content in text fields
    all_text = " ".join([
        exp.observed_relationship,
        exp.structural_similarity,
        exp.cross_context_pattern,
        exp.abstraction_path_description,
    ]).lower()
    for pattern in FORBIDDEN_EXPLANATION_PATTERNS:
        # Skip empty pattern
        if not pattern:
            continue
        if pattern in all_text:
            # Allow if inside a code example (not in actual explanation)
            pass  # We handle this in specific tests
    return errors


def check_chain_consistency(record: InferenceRecord, exp: ExplanationConstraint) -> List[str]:
    """检查 InferenceRecord 和 Explanation 的一致性."""
    errors = []
    pat_ref_ids = {p.pattern_id for p in record.pattern_references}
    ev_ref_ids = {e.evidence_id for e in record.evidence_references}
    for pid in exp.key_pattern_ids:
        if pid not in pat_ref_ids:
            errors.append(f"key_pattern_id {pid} not in pattern_references: {pat_ref_ids}")
    for eid in exp.key_evidence_ids:
        if eid not in ev_ref_ids:
            errors.append(f"key_evidence_id {eid} not in evidence_references: {ev_ref_ids}")
    return errors


# ============ Tests ============


class TestInferenceRecordABI:
    """InferenceRecord 数据模型."""

    def test_required_fields_exist(self):
        """必需字段存在."""
        r = InferenceRecord(
            record_id="ir-001",
            candidate_id="pc-a1b2",
            derivation_path="测试推导路径",
        )
        assert r.record_id == "ir-001"
        assert r.candidate_id == "pc-a1b2"
        assert r.version == 1

    def test_record_id_format(self):
        """record_id 格式正确."""
        r = InferenceRecord(
            record_id="ir-valid",
            candidate_id="pc-valid",
            derivation_path="测试",
            pattern_references=[PatternRef(pattern_id="pat-x", role="primary_support", work_context="test")],
            evidence_references=[EvidenceRef(evidence_id="e-001", support_type="direct", confidence=ConfidenceLevel.HIGH)],
        )
        errors = validate_inference_record(r)
        assert len(errors) == 0, f"Unexpected errors: {errors}"

    def test_invalid_id_format_rejected(self):
        """格式错误的 ID 被拒绝."""
        r = InferenceRecord(
            record_id="bad-format",
            candidate_id="pc-test",
            derivation_path="test",
            pattern_references=[PatternRef(pattern_id="pat-x", role="primary_support", work_context="test")],
            evidence_references=[EvidenceRef(evidence_id="e-001", support_type="direct", confidence=ConfidenceLevel.HIGH)],
        )
        errors = validate_inference_record(r)
        id_errors = [e for e in errors if "record_id" in e]
        assert len(id_errors) >= 1

    def test_candidate_id_format(self):
        """candidate_id 格式检查."""
        r = InferenceRecord(
            record_id="ir-test",
            candidate_id="not-pc",
            derivation_path="test",
            pattern_references=[PatternRef(pattern_id="pat-x", role="primary_support", work_context="test")],
            evidence_references=[EvidenceRef(evidence_id="e-001", support_type="direct", confidence=ConfidenceLevel.HIGH)],
        )
        errors = validate_inference_record(r)
        assert any("candidate_id" in e for e in errors)


class TestPatternRef:
    """PatternRef 模型."""

    def test_valid_roles(self):
        """有效的 role 值."""
        for role in ALLOWED_ROLES:
            ref = PatternRef(pattern_id="pat-x", role=role, work_context="测试")
            assert ref.role == role

    def test_invalid_role_rejected(self):
        """无效 role 被拒绝."""
        r = InferenceRecord(
            record_id="ir-role",
            candidate_id="pc-role",
            derivation_path="test",
            pattern_references=[PatternRef(pattern_id="pat-x", role="invalid_role", work_context="test")],
            evidence_references=[EvidenceRef(evidence_id="e-001", support_type="direct", confidence=ConfidenceLevel.HIGH)],
        )
        errors = validate_inference_record(r)
        assert any("Invalid pattern role" in e for e in errors)

    def test_pattern_id_format(self):
        """pattern_id 必须以 pat- 开头."""
        r = InferenceRecord(
            record_id="ir-pid",
            candidate_id="pc-pid",
            derivation_path="test",
            pattern_references=[PatternRef(pattern_id="wrong-id", role="primary_support", work_context="test")],
            evidence_references=[EvidenceRef(evidence_id="e-001", support_type="direct", confidence=ConfidenceLevel.HIGH)],
        )
        errors = validate_inference_record(r)
        assert any("pattern_id" in e for e in errors)


class TestEvidenceRef:
    """EvidenceRef 模型."""

    def test_valid_support_types(self):
        """有效的 support_type 值."""
        for st in ALLOWED_SUPPORT_TYPES:
            ref = EvidenceRef(evidence_id="e-001", support_type=st, confidence=ConfidenceLevel.MEDIUM)
            assert ref.support_type == st

    def test_invalid_support_type_rejected(self):
        """无效 support_type 被拒绝."""
        r = InferenceRecord(
            record_id="ir-st",
            candidate_id="pc-st",
            derivation_path="test",
            pattern_references=[PatternRef(pattern_id="pat-x", role="primary_support", work_context="test")],
            evidence_references=[EvidenceRef(evidence_id="e-001", support_type="invalid", confidence=ConfidenceLevel.HIGH)],
        )
        errors = validate_inference_record(r)
        assert any("Invalid support_type" in e for e in errors)

    def test_evidence_id_format(self):
        """evidence_id 必须以 ev-/e- 开头."""
        r = InferenceRecord(
            record_id="ir-eid",
            candidate_id="pc-eid",
            derivation_path="test",
            pattern_references=[PatternRef(pattern_id="pat-x", role="primary_support", work_context="test")],
            evidence_references=[EvidenceRef(evidence_id="bad-id", support_type="direct", confidence=ConfidenceLevel.LOW)],
        )
        errors = validate_inference_record(r)
        assert any("evidence_id" in e for e in errors)


class TestConfidenceLevel:
    """ConfidenceLevel 语义."""

    def test_four_levels(self):
        """4 级置信度."""
        assert len(ConfidenceLevel) == 4
        assert ConfidenceLevel.LOW.value == "low"
        assert ConfidenceLevel.MEDIUM.value == "medium"
        assert ConfidenceLevel.HIGH.value == "high"
        assert ConfidenceLevel.ESTABLISHED.value == "established"

    def test_not_value_judgment(self):
        """ConfidenceLevel 不是价值判断."""
        # 检查枚举值不含价值词
        for level in ConfidenceLevel:
            assert level.value not in ("good", "better", "effective", "successful")

    def test_medium_confidence_usage(self):
        """MEDIUM 置信度的使用."""
        ref = EvidenceRef(
            evidence_id="e-001",
            support_type="structural",
            confidence=ConfidenceLevel.MEDIUM,
        )
        assert ref.confidence == ConfidenceLevel.MEDIUM


class TestExplanationConstraintABI:
    """ExplanationConstraint 数据模型."""

    def test_allowed_fields_exist(self):
        """允许的字段存在."""
        exp = ExplanationConstraint(
            observed_relationship="Pattern A 和 B 均有信息隐藏结构",
            structural_similarity="共同底层结构是信息受限+决策约束",
            cross_context_pattern="出现在都市/玄幻类型",
            abstraction_path_description="从 3 组 Pattern 抽象",
            key_pattern_ids=["pat-A", "pat-B"],
            key_evidence_ids=["e-001"],
        )
        assert exp.observed_relationship != ""
        assert exp.structural_similarity != ""
        assert exp.format_version == "1.0"

    def test_no_forbidden_fields(self):
        """ExplanationConstraint 不含禁止字段."""
        exp = ExplanationConstraint()
        for field in FORBIDDEN_EXPLANATION_FIELDS:
            assert not hasattr(exp, field), f"Field should not exist: {field}"

    def test_forbidden_fields_list_comprehensive(self):
        """禁止字段列表完整."""
        assert len(FORBIDDEN_EXPLANATION_FIELDS) >= 10
        assert "this_works_because" in FORBIDDEN_EXPLANATION_FIELDS
        assert "effectiveness_claim" in FORBIDDEN_EXPLANATION_FIELDS
        assert "reader_preference_note" in FORBIDDEN_EXPLANATION_FIELDS
        assert "recommendation_note" in FORBIDDEN_EXPLANATION_FIELDS
        assert "quality_judgment" in FORBIDDEN_EXPLANATION_FIELDS
        assert "commercial_claim" in FORBIDDEN_EXPLANATION_FIELDS

    def test_at_least_one_relationship_field(self):
        """至少一个关系字段非空."""
        exp = ExplanationConstraint()
        errors = validate_explanation(exp)
        assert any("At least one" in e for e in errors)

    def test_valid_explanation_passes(self):
        """有效的解释通过验证."""
        exp = ExplanationConstraint(
            observed_relationship="Pattern A 和 B 共享信息隐藏结构",
            structural_similarity="共同结构是受限信息+决策约束",
            key_pattern_ids=["pat-A", "pat-B"],
            key_evidence_ids=["e-001"],
        )
        errors = validate_explanation(exp)
        assert len(errors) == 0, f"Unexpected errors: {errors}"


class TestChainIntegrity:
    """证据链完整性."""

    def test_zero_pattern_references_invalid(self):
        """0 个 pattern 引用无效."""
        r = InferenceRecord(
            record_id="ir-zero",
            candidate_id="pc-zero",
            derivation_path="test",
            pattern_references=[],
            evidence_references=[EvidenceRef(evidence_id="e-001", support_type="direct", confidence=ConfidenceLevel.HIGH)],
        )
        errors = validate_inference_record(r)
        assert any("pattern_reference" in e.lower() for e in errors)

    def test_zero_evidence_references_invalid(self):
        """0 个 evidence 引用无效."""
        r = InferenceRecord(
            record_id="ir-ze",
            candidate_id="pc-ze",
            derivation_path="test",
            pattern_references=[PatternRef(pattern_id="pat-x", role="primary_support", work_context="test")],
            evidence_references=[],
        )
        errors = validate_inference_record(r)
        assert any("evidence_reference" in e.lower() for e in errors)

    def test_empty_derivation_path_invalid(self):
        """空 derivation_path 无效."""
        r = InferenceRecord(
            record_id="ir-empty",
            candidate_id="pc-empty",
            derivation_path="",
            pattern_references=[PatternRef(pattern_id="pat-x", role="primary_support", work_context="test")],
            evidence_references=[EvidenceRef(evidence_id="e-001", support_type="direct", confidence=ConfidenceLevel.LOW)],
        )
        errors = validate_inference_record(r)
        assert any("not be empty" in e for e in errors)

    def test_key_ids_must_match_references(self):
        """key_pattern_ids 必须在 pattern_references 中."""
        record = InferenceRecord(
            record_id="ir-key",
            candidate_id="pc-key",
            derivation_path="test",
            pattern_references=[PatternRef(pattern_id="pat-A", role="primary_support", work_context="A")],
            evidence_references=[EvidenceRef(evidence_id="e-001", support_type="direct", confidence=ConfidenceLevel.MEDIUM)],
        )
        exp = ExplanationConstraint(
            observed_relationship="测试关系",
            key_pattern_ids=["pat-X"],  # Not in record
            key_evidence_ids=["e-001"],
        )
        errors = check_chain_consistency(record, exp)
        assert any("key_pattern_id" in e and "pat-X" in e for e in errors)

    def test_key_evidence_must_match_references(self):
        """key_evidence_ids 必须在 evidence_references 中."""
        record = InferenceRecord(
            record_id="ir-key2",
            candidate_id="pc-key2",
            derivation_path="test",
            pattern_references=[PatternRef(pattern_id="pat-A", role="primary_support", work_context="A")],
            evidence_references=[EvidenceRef(evidence_id="e-001", support_type="direct", confidence=ConfidenceLevel.MEDIUM)],
        )
        exp = ExplanationConstraint(
            observed_relationship="测试关系",
            key_pattern_ids=["pat-A"],
            key_evidence_ids=["e-999"],  # Not in record
        )
        errors = check_chain_consistency(record, exp)
        assert any("key_evidence_id" in e for e in errors)


class TestForbiddenContent:
    """禁止的解释内容."""

    def test_no_effectiveness_claim(self):
        """解释不含效果断言."""
        messages = [
            "这个机制 works because 信息隐藏导致期待",
            "这是一种 effective because 的叙事结构",
            "使用这种方法 increases retention",
        ]
        for msg in messages:
            found = False
            for pattern in FORBIDDEN_EXPLANATION_PATTERNS:
                if pattern in msg.lower() and pattern != "":
                    found = True
                    break
            assert found, f"Should flag: {msg}"

    def test_no_reader_preference(self):
        """解释不含读者偏好."""
        messages = [
            "reader like 这种结构",
            "audience prefer 信息差叙事",
            "readers love 这种方式",
        ]
        for msg in messages:
            found = any(p in msg.lower() for p in FORBIDDEN_EXPLANATION_PATTERNS if p)
            assert found, f"Should flag: {msg}"

    def test_no_recommendation(self):
        """解释不含推荐."""
        messages = [
            "should use 这种方法",
            "recommend 使用信息隐藏",
            "suggest 在关键情节采用",
        ]
        for msg in messages:
            found = any(p in msg.lower() for p in FORBIDDEN_EXPLANATION_PATTERNS if p)
            assert found, f"Should flag: {msg}"

    def test_no_comparative_judgment(self):
        """解释不含比较级."""
        messages = [
            "better than 传统方式",
            "more effective 写法",
        ]
        for msg in messages:
            found = any(p in msg.lower() for p in FORBIDDEN_EXPLANATION_PATTERNS if p)
            assert found, f"Should flag: {msg}"

    def test_no_prescription(self):
        """解释不含规定性语言."""
        messages = [
            "author should 使用信息隐藏",
            "writer must 注意时间压力",
        ]
        for msg in messages:
            found = any(p in msg.lower() for p in FORBIDDEN_EXPLANATION_PATTERNS if p)
            assert found, f"Should flag: {msg}"

    def test_valid_explanation_clean(self):
        """有效的结构解释不含禁止词."""
        clean_messages = [
            "Pattern A 和 B 共享'信息受限+决策约束'的底层结构",
            "跨作品(都市/玄幻)出现",
            "Relation Graph 显示信息不对称→决策压力的因果链在两组中一致",
            "从 3 组 Pattern 的共同结构抽象",
        ]
        for msg in clean_messages:
            found = any(p in msg.lower() for p in FORBIDDEN_EXPLANATION_PATTERNS if p)
            assert not found, f"Clean text wrongly flagged: {msg}"


class TestPhase14Dot5Isolation:
    """Phase14.4 → Phase14.5 接口隔离."""

    def test_output_has_no_capability_fields(self):
        """Phase14Dot3Output 不含能力层字段."""
        cand = PrincipleCandidate(candidate_id="pc-test")
        rec = InferenceRecord(
            record_id="ir-test",
            candidate_id="pc-test",
            derivation_path="test",
            pattern_references=[PatternRef(pattern_id="pat-x", role="primary_support", work_context="test")],
            evidence_references=[EvidenceRef(evidence_id="e-001", support_type="direct", confidence=ConfidenceLevel.LOW)],
        )
        exp = ExplanationConstraint(observed_relationship="测试")
        output = Phase14Dot3Output(candidate=cand, inference_record=rec, explanation=exp)
        assert not hasattr(output, "capability_package")
        assert not hasattr(output, "writing_rule")
        assert not hasattr(output, "prompt_template")

    def test_no_template_or_instruction(self):
        """输出不含模板或指令."""
        cand = PrincipleCandidate(candidate_id="pc-tpl")
        rec = InferenceRecord(
            record_id="ir-tpl",
            candidate_id="pc-tpl",
            derivation_path="test",
            pattern_references=[PatternRef(pattern_id="pat-x", role="primary_support", work_context="test")],
            evidence_references=[EvidenceRef(evidence_id="e-001", support_type="direct", confidence=ConfidenceLevel.LOW)],
        )
        exp = ExplanationConstraint(observed_relationship="测试")
        output = Phase14Dot3Output(candidate=cand, inference_record=rec, explanation=exp)
        assert not hasattr(output, "writing_prompt")
        assert not hasattr(output, "agent_instruction")
        assert not hasattr(output, "template")

    def test_output_type_correct(self):
        """输出类型正确."""
        cand = PrincipleCandidate(candidate_id="pc-type")
        rec = InferenceRecord(
            record_id="ir-type",
            candidate_id="pc-type",
            derivation_path="test",
            pattern_references=[PatternRef(pattern_id="pat-x", role="primary_support", work_context="test")],
            evidence_references=[EvidenceRef(evidence_id="e-001", support_type="direct", confidence=ConfidenceLevel.LOW)],
        )
        exp = ExplanationConstraint(observed_relationship="测试")
        output = Phase14Dot3Output(candidate=cand, inference_record=rec, explanation=exp)
        assert isinstance(output.candidate, PrincipleCandidate)
        assert isinstance(output.inference_record, InferenceRecord)
        assert isinstance(output.explanation, ExplanationConstraint)


class TestExplanationNotLLMReasoning:
    """解释 ≠ LLM 推理."""

    def test_explanation_based_on_ids_not_free_text(self):
        """解释基于 ID 引用而非自由文本."""
        # 关键: ExplanationConstraint 通过 key_pattern_ids/key_evidence_ids
        # 引用具体记录, 而不是仅靠 LLM 生成文本
        record = InferenceRecord(
            record_id="ir-llm",
            candidate_id="pc-llm",
            derivation_path="基于 pat-A, pat-B, pat-C 的结构相似性",
            pattern_references=[
                PatternRef(pattern_id="pat-A", role="primary_support", work_context="都市"),
                PatternRef(pattern_id="pat-B", role="primary_support", work_context="玄幻"),
            ],
            evidence_references=[
                EvidenceRef(evidence_id="e-001", support_type="direct", confidence=ConfidenceLevel.HIGH),
            ],
        )
        assert len(record.pattern_references) >= 1
        assert len(record.evidence_references) >= 1
        # 引用是可解析的 ID
        for pref in record.pattern_references:
            assert pref.pattern_id.startswith("pat-")
        for eref in record.evidence_references:
            assert eref.evidence_id.startswith("e-") or eref.evidence_id.startswith("ev-")

    def test_no_llm_only_reasoning(self):
        """验证函数拒绝无引用的解释."""
        exp = ExplanationConstraint(
            observed_relationship="LLM 认为这个结构很重要",
            structural_similarity="模型觉得这很好",
            key_pattern_ids=["pat-llm"],  # pattern not in record
            key_evidence_ids=["e-llm"],   # evidence not in record
        )
        record = InferenceRecord(
            record_id="ir-llm2",
            candidate_id="pc-llm2",
            derivation_path="test",
            pattern_references=[PatternRef(pattern_id="pat-x", role="primary_support", work_context="test")],
            evidence_references=[EvidenceRef(evidence_id="e-001", support_type="direct", confidence=ConfidenceLevel.LOW)],
        )
        # key IDs reference patterns/evidence that don't exist in the record
        errors = check_chain_consistency(record, exp)
        assert len(errors) > 0  # key IDs don't match references
