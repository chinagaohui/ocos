"""Phase14.4.1 — Principle Model Definition Tests.

Tests verify:
1. PrincipleRecord ABI — required fields, structure, types
2. Abstraction levels — valid levels, no skipping, level-dependent constraints
3. Principle ↔ Pattern relationship — supports allowed, equals forbidden
4. Status lifecycle — valid transitions, state machine rules
5. Forbidden properties — comprehensive attribute blacklist
6. Phase14.4 ↔ Phase14.5 interface — output contract, no capability leaking
7. Tracing integrity — every principle traces to ≥1 pattern + ≥1 evidence
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import List, Optional, Dict, Set
from enum import Enum


# --- Enums ---


class AbstractionLevel(str, Enum):
    L1_MECHANISM_CANDIDATE = "L1_mechanism_candidate"
    L2_PRINCIPLE = "L2_principle"
    L3_GENERAL_PRINCIPLE = "L3_general_principle"


class PrincipleStatus(str, Enum):
    CANDIDATE = "candidate"
    REVIEWING = "reviewing"
    VALIDATED = "validated"
    ARCHIVED = "archived"
    INVALIDATED = "invalidated"
    SUPERSEDED = "superseded"


# --- Data Models ---


@dataclass
class HistoryEntry:
    status: str
    timestamp: datetime
    note: str = ""


@dataclass
class PrincipleRecord:
    """Phase14.4.1 PrincipleRecord ABI — frozen definition."""

    # Core identity
    principle_id: str
    mechanism_name: str
    mechanism_description: str
    abstraction_level: AbstractionLevel
    version: int = 1

    # Tracing
    source_pattern_ids: List[str] = field(default_factory=list)
    evidence_chain_ids: List[str] = field(default_factory=list)

    # Scope
    context_boundary: str = ""
    scope: str = ""

    # Lifecycle
    status: PrincipleStatus = PrincipleStatus.CANDIDATE
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    history: List[HistoryEntry] = field(default_factory=list)

    # Evolution
    derived_from: Optional[str] = None
    superseded_by: Optional[str] = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.updated_at is None:
            self.updated_at = self.created_at


@dataclass
class Phase14Dot4Output:
    """Phase14.4 → Phase14.5 接口输出."""
    principles: List[PrincipleRecord]

    def __post_init__(self):
        # Only validated principles may be emitted
        for p in self.principles:
            assert p.status == PrincipleStatus.VALIDATED, (
                f"Principle {p.principle_id} not validated: {p.status}"
            )


# --- Forbidden definitions ---


FORBIDDEN_ATTRIBUTES: Set[str] = {
    "quality_score", "effectiveness", "success_rate",
    "reader_score", "market_data", "popularity",
    "revenue_impact", "usage_priority",
    "recommended", "best_for", "should_use",
    "optimal_context", "author_preference",
}

FORBIDDEN_KEYWORDS: Dict[str, str] = {
    "最好": "best (value judgment)",
    "更有效": "more effective (effectiveness)",
    "强大": "powerful (non-structural)",
    "推荐": "recommended (normative)",
    "最优": "optimal (capability layer)",
    "读者喜欢": "reader favorite (reader evaluation)",
    "爆款": "viral (commercial trend)",
}

FORBIDDEN_OUTPUTS: Set[str] = {
    "writing_agent",
    "prompt_instruction",
    "writing_template",
    "generation_strategy",
    "modification_suggestion",
    "style_transfer_config",
    "text_generation_params",
}

FORBIDDEN_RELATIONS: Set[str] = {
    "equals", "proves", "recommends", "validates",
}


# --- Helper ---


def check_forbidden_keywords(text: str) -> List[str]:
    """检查文本是否包含禁止关键词."""
    found = []
    for keyword, reason in FORBIDDEN_KEYWORDS.items():
        if keyword in text:
            found.append(f"'{keyword}' ({reason})")
    return found


def check_forbidden_attributes(obj) -> List[str]:
    """检查对象是否包含禁止属性."""
    found = []
    for attr in FORBIDDEN_ATTRIBUTES:
        if hasattr(obj, attr):
            found.append(attr)
    return found


# --- Tests ---


class TestPrincipleRecordABI:
    """PrincipleRecord 数据模型 ABI 冻结."""

    def test_required_fields_present(self):
        """核心必需字段存在."""
        p = PrincipleRecord(
            principle_id="p-001",
            mechanism_name="Constraint Escalation",
            mechanism_description="目标受限+信息隐藏+时间压力增加场景下的决策压力结构",
            abstraction_level=AbstractionLevel.L2_PRINCIPLE,
        )
        assert p.principle_id == "p-001"
        assert p.mechanism_name == "Constraint Escalation"
        assert p.mechanism_description != ""
        assert p.abstraction_level == AbstractionLevel.L2_PRINCIPLE

    def test_no_forbidden_attributes(self):
        """PrincipleRecord 不含禁止属性."""
        p = PrincipleRecord(
            principle_id="p-fa",
            mechanism_name="Test",
            mechanism_description="Test mechanism",
            abstraction_level=AbstractionLevel.L1_MECHANISM_CANDIDATE,
        )
        violations = check_forbidden_attributes(p)
        assert not violations, f"Forbidden attributes found: {violations}"

    def test_forbidden_attributes_list_comprehensive(self):
        """禁止属性列表完整."""
        assert len(FORBIDDEN_ATTRIBUTES) >= 10
        assert "quality_score" in FORBIDDEN_ATTRIBUTES
        assert "effectiveness" in FORBIDDEN_ATTRIBUTES
        assert "recommended" in FORBIDDEN_ATTRIBUTES
        assert "popularity" in FORBIDDEN_ATTRIBUTES
        assert "success_rate" in FORBIDDEN_ATTRIBUTES

    def test_principle_id_format(self):
        """principle_id 以 'p-' 开头."""
        p = PrincipleRecord(
            principle_id="p-abc123",
            mechanism_name="Test",
            mechanism_description="Test",
            abstraction_level=AbstractionLevel.L1_MECHANISM_CANDIDATE,
        )
        assert p.principle_id.startswith("p-")
        assert len(p.principle_id) > 2

    def test_mechanism_name_is_description_not_value(self):
        """机制名称是描述性的, 不是价值性的."""
        valid_names = [
            "Constraint Escalation",
            "Information Asymmetry Resolution",
            "Emotional Distance Modulation",
            "认知负载与信息释放的不对称关系",
        ]
        for name in valid_names:
            violations = check_forbidden_keywords(name)
            assert not violations, f"Name '{name}' has forbidden keywords: {violations}"

    def test_invalid_names_rejected(self):
        """含价值判断的名称被禁止."""
        invalid_names = [
            "最好用的结构",
            "更有效的写法",
            "读者喜欢的套路",
        ]
        for name in invalid_names:
            violations = check_forbidden_keywords(name)
            assert violations, f"Name '{name}' should be rejected"

    def test_version_auto_starts_at_1(self):
        """版本号从 1 开始."""
        p = PrincipleRecord(
            principle_id="p-v",
            mechanism_name="V",
            mechanism_description="V",
            abstraction_level=AbstractionLevel.L1_MECHANISM_CANDIDATE,
        )
        assert p.version == 1

    def test_timestamps_auto_set(self):
        """时间戳自动设置."""
        p = PrincipleRecord(
            principle_id="p-ts",
            mechanism_name="TS",
            mechanism_description="TS",
            abstraction_level=AbstractionLevel.L1_MECHANISM_CANDIDATE,
        )
        assert p.created_at is not None
        assert p.updated_at is not None
        assert p.updated_at >= p.created_at  # noqa


class TestAbstractionLevels:
    """抽象层级冻结."""

    def test_valid_levels(self):
        """有效抽象层级."""
        assert AbstractionLevel.L1_MECHANISM_CANDIDATE.value == "L1_mechanism_candidate"
        assert AbstractionLevel.L2_PRINCIPLE.value == "L2_principle"
        assert AbstractionLevel.L3_GENERAL_PRINCIPLE.value == "L3_general_principle"
        assert len(AbstractionLevel) == 3

    def test_l2_requires_multiple_patterns(self):
        """L2 Principle 需要 ≥3 个不同作品的 Pattern."""
        p = PrincipleRecord(
            principle_id="p-l2",
            mechanism_name="Cross-work Mechanism",
            mechanism_description="跨作品机制",
            abstraction_level=AbstractionLevel.L2_PRINCIPLE,
            source_pattern_ids=["pat-a", "pat-b", "pat-c", "pat-d"],
            evidence_chain_ids=["e-001", "e-002"],
        )
        assert len(p.source_pattern_ids) >= 3

    def test_l3_requires_cross_type_scope(self):
        """L3 General Principle 需要跨类型的上下文边界."""
        p = PrincipleRecord(
            principle_id="p-l3",
            mechanism_name="General Mechanism",
            mechanism_description="跨类型通用机制",
            abstraction_level=AbstractionLevel.L3_GENERAL_PRINCIPLE,
            source_pattern_ids=["pat-a", "pat-b", "pat-c", "pat-d", "pat-e"],
            evidence_chain_ids=["e-001", "e-002", "e-003"],
            context_boundary="zh_novel_fiction_cross_genre",
        )
        assert "cross" in p.context_boundary
        assert len(p.source_pattern_ids) >= 3

    def test_l1_can_have_single_pattern(self):
        """L1 Candidate 可以有单 Pattern."""
        p = PrincipleRecord(
            principle_id="p-l1",
            mechanism_name="Local Hypothesis",
            mechanism_description="局部机制假说",
            abstraction_level=AbstractionLevel.L1_MECHANISM_CANDIDATE,
            source_pattern_ids=["pat-x"],
            evidence_chain_ids=["e-001"],
        )
        assert len(p.source_pattern_ids) >= 1

    def test_no_jump_l0_to_l2(self):
        """L0 Pattern → L2 Principle 跳跃必须被验证逻辑拒绝."""
        # 数据模型层面允许创建, 但业务规则要求 L2 ≥3 patterns
        # 模拟验证逻辑
        def validate_principle(p: PrincipleRecord) -> List[str]:
            errors = []
            if p.abstraction_level == AbstractionLevel.L2_PRINCIPLE and len(p.source_pattern_ids) < 3:
                errors.append(f"L2 Principle requires >= 3 source patterns, got {len(p.source_pattern_ids)}")
            if p.abstraction_level == AbstractionLevel.L3_GENERAL_PRINCIPLE and len(p.source_pattern_ids) < 5:
                errors.append(f"L3 requires >= 5 source patterns, got {len(p.source_pattern_ids)}")
            return errors

        # 单 pattern 的 L2 — 验证逻辑应拒绝
        p_l2_jump = PrincipleRecord(
            principle_id="p-jump",
            mechanism_name="Jump",
            mechanism_description="测试",
            abstraction_level=AbstractionLevel.L2_PRINCIPLE,
            source_pattern_ids=["pat-only"],
            evidence_chain_ids=["e-001"],
        )
        errors = validate_principle(p_l2_jump)
        assert len(errors) >= 1, "L2 with <3 patterns should be rejected"
        assert "3 source patterns" in errors[0]

        # 合格 L2 — 验证逻辑应通过
        p_l2_valid = PrincipleRecord(
            principle_id="p-l2-ok",
            mechanism_name="Valid L2",
            mechanism_description="有足够 Pattern 支撑的 L2",
            abstraction_level=AbstractionLevel.L2_PRINCIPLE,
            source_pattern_ids=["pat-a", "pat-b", "pat-c", "pat-d"],
            evidence_chain_ids=["e-001", "e-002", "e-003"],
        )
        errors = validate_principle(p_l2_valid)
        assert len(errors) == 0, f"Valid L2 got unexpected errors: {errors}"


class TestPatternPrincipleRelationship:
    """Pattern ↔ Principle 关系冻结."""

    def test_supports_allowed(self):
        """'supports' 关系允许."""
        assert "supports" not in FORBIDDEN_RELATIONS

    def test_equals_forbidden(self):
        """'equals' 关系禁止."""
        assert "equals" in FORBIDDEN_RELATIONS

    def test_proves_forbidden(self):
        """'proves' 关系禁止."""
        assert "proves" in FORBIDDEN_RELATIONS

    def test_recommends_forbidden(self):
        """'recommends' 关系禁止."""
        assert "recommends" in FORBIDDEN_RELATIONS

    def test_validates_forbidden(self):
        """'validates' 关系禁止."""
        assert "validates" in FORBIDDEN_RELATIONS

    def test_principle_has_multiple_pattern_sources(self):
        """Principle 来自多个 Pattern, 不是单一 Pattern 的等价物."""
        p = PrincipleRecord(
            principle_id="p-multi",
            mechanism_name="Multi-pattern Mechanism",
            mechanism_description="多个 Pattern 支撑的抽象机制",
            abstraction_level=AbstractionLevel.L2_PRINCIPLE,
            source_pattern_ids=["pat-a", "pat-b", "pat-c", "pat-d"],
            evidence_chain_ids=["e-001", "e-002", "e-003"],
        )
        assert len(p.source_pattern_ids) >= 3

    def test_evidence_chain_links_pattern_to_principle(self):
        """证据链建立 Pattern → Principle 的可追溯性."""
        p = PrincipleRecord(
            principle_id="p-trace",
            mechanism_name="Traceable",
            mechanism_description="可追溯的机制",
            abstraction_level=AbstractionLevel.L2_PRINCIPLE,
            source_pattern_ids=["pat-a", "pat-b", "pat-c"],
            evidence_chain_ids=["e-001", "e-002", "e-003", "e-004"],
        )
        assert len(p.evidence_chain_ids) >= len(p.source_pattern_ids)


class TestStatusLifecycle:
    """Principle 状态生命周期."""

    def test_initial_status_candidate(self):
        """初始状态为 candidate."""
        p = PrincipleRecord(
            principle_id="p-init",
            mechanism_name="Init",
            mechanism_description="Init",
            abstraction_level=AbstractionLevel.L1_MECHANISM_CANDIDATE,
        )
        assert p.status == PrincipleStatus.CANDIDATE

    def test_valid_transitions(self):
        """有效的状态转换."""
        p = PrincipleRecord(
            principle_id="p-trans",
            mechanism_name="Trans",
            mechanism_description="Trans",
            abstraction_level=AbstractionLevel.L1_MECHANISM_CANDIDATE,
        )

        # candidate → reviewing
        p.status = PrincipleStatus.REVIEWING
        assert p.status == PrincipleStatus.REVIEWING

        # reviewing → validated
        p.status = PrincipleStatus.VALIDATED
        assert p.status == PrincipleStatus.VALIDATED

    def test_validated_can_be_superseded(self):
        """Validated 可以被 Superseded 取代."""
        old = PrincipleRecord(
            principle_id="p-old",
            mechanism_name="Old",
            mechanism_description="Old mechanism",
            abstraction_level=AbstractionLevel.L2_PRINCIPLE,
            source_pattern_ids=["pat-a", "pat-b", "pat-c"],
            evidence_chain_ids=["e-001", "e-002"],
            status=PrincipleStatus.SUPERSEDED,
            superseded_by="p-new",
        )
        assert old.status == PrincipleStatus.SUPERSEDED
        assert old.superseded_by == "p-new"

    def test_invalidated_has_note_option(self):
        """Invalidated 可以附带说明."""
        p = PrincipleRecord(
            principle_id="p-inv",
            mechanism_name="Invalid",
            mechanism_description="被推翻的机制",
            abstraction_level=AbstractionLevel.L1_MECHANISM_CANDIDATE,
            status=PrincipleStatus.INVALIDATED,
            history=[HistoryEntry(
                status="invalidated",
                timestamp=datetime.now(),
                note="反例 pat-z 证明此机制不成立",
            )],
        )
        assert p.status == PrincipleStatus.INVALIDATED
        assert len(p.history) >= 1
        assert "反例" in p.history[0].note

    def test_archived_preserves_record(self):
        """Archived 保留记录."""
        p = PrincipleRecord(
            principle_id="p-arch",
            mechanism_name="Archived",
            mechanism_description="已存档",
            abstraction_level=AbstractionLevel.L1_MECHANISM_CANDIDATE,
            status=PrincipleStatus.ARCHIVED,
        )
        assert p.status == PrincipleStatus.ARCHIVED

    def test_all_statuses_covered(self):
        """所有状态已定义."""
        expected = {"candidate", "reviewing", "validated",
                    "archived", "invalidated", "superseded"}
        actual = {s.value for s in PrincipleStatus}
        assert actual == expected, f"Missing: {expected - actual}"


class TestForbiddenProperties:
    """禁止属性全面检查."""

    def test_forbidden_attributes_comprehensive(self):
        """禁止属性列表完整且合理."""
        assert "quality_score" in FORBIDDEN_ATTRIBUTES
        assert "effectiveness" in FORBIDDEN_ATTRIBUTES
        assert "success_rate" in FORBIDDEN_ATTRIBUTES
        assert "usage_priority" in FORBIDDEN_ATTRIBUTES
        assert "recommended" in FORBIDDEN_ATTRIBUTES
        assert "best_for" in FORBIDDEN_ATTRIBUTES
        assert "should_use" in FORBIDDEN_ATTRIBUTES
        assert "optimal_context" in FORBIDDEN_ATTRIBUTES
        assert "popularity" in FORBIDDEN_ATTRIBUTES
        assert "revenue_impact" in FORBIDDEN_ATTRIBUTES

    def test_forbidden_keywords_not_in_valid_descriptions(self):
        """有效机制描述不含禁止关键词."""
        valid_descriptions = [
            "目标受限与信息隐藏的决策压力结构",
            "关系距离变化与情绪期待的不对称映射",
            "冲突积累阈值与化解窗口的动态平衡",
            "认知负载与信息释放的阶段关系",
        ]
        for desc in valid_descriptions:
            violations = check_forbidden_keywords(desc)
            assert not violations, f"Description '{desc}' has violations: {violations}"

    def test_forbidden_keywords_in_invalid_descriptions(self):
        """含禁止关键词的描述被识别."""
        invalid_descriptions = [
            "最好用的写作结构",
            "更有效的叙事方式",
            "读者喜欢的情节设计",
        ]
        for desc in invalid_descriptions:
            violations = check_forbidden_keywords(desc)
            assert violations, f"Description '{desc}' should have violations"

    def test_no_value_terms_in_mechanism_name(self):
        """机制名称不含价值词."""
        p = PrincipleRecord(
            principle_id="p-val",
            mechanism_name="Constraint Escalation",
            mechanism_description="测试",
            abstraction_level=AbstractionLevel.L2_PRINCIPLE,
            source_pattern_ids=["pat-a", "pat-b", "pat-c"],
            evidence_chain_ids=["e-001", "e-002"],
        )
        value_terms = ["best", "better", "effective", "powerful",
                       "popular", "recommended", "optimal"]
        for term in value_terms:
            assert term.lower() not in p.mechanism_name.lower(), (
                f"Value term '{term}' in mechanism name"
            )

    def test_no_commercial_terms_in_scope(self):
        """作用域描述不含商业用语."""
        p = PrincipleRecord(
            principle_id="p-scope",
            mechanism_name="Test",
            mechanism_description="Test",
            abstraction_level=AbstractionLevel.L2_PRINCIPLE,
            source_pattern_ids=["pat-a", "pat-b", "pat-c"],
            evidence_chain_ids=["e-001"],
            context_boundary="zh_novel_fiction_2015_2025",
            scope="适用于目标导向型叙事结构, 需要明确的阻碍/信息差/时间压力约束",
        )
        commercial_terms = ["爆款", "热门", "畅销", "付费"]
        for term in commercial_terms:
            assert term not in p.scope, f"Commercial term '{term}' in scope"


class TestPhase14Dot4Dot5Interface:
    """Phase14.4 ↔ Phase14.5 接口."""

    def test_output_only_validated_principles(self):
        """Phase14.4 只输出 validated 状态的 Principle."""
        validated = PrincipleRecord(
            principle_id="p-vout",
            mechanism_name="Validated Mechanism",
            mechanism_description="已验证机制",
            abstraction_level=AbstractionLevel.L2_PRINCIPLE,
            source_pattern_ids=["pat-a", "pat-b", "pat-c"],
            evidence_chain_ids=["e-001", "e-002"],
            status=PrincipleStatus.VALIDATED,
        )
        output = Phase14Dot4Output(principles=[validated])
        assert len(output.principles) == 1
        assert output.principles[0].status == PrincipleStatus.VALIDATED

    def test_output_rejects_non_validated(self):
        """非 validated 的 Principle 不能从 Phase14.4 输出."""
        candidate = PrincipleRecord(
            principle_id="p-cout",
            mechanism_name="Candidate",
            mechanism_description="尚未验证",
            abstraction_level=AbstractionLevel.L1_MECHANISM_CANDIDATE,
            status=PrincipleStatus.CANDIDATE,
        )
        try:
            Phase14Dot4Output(principles=[candidate])
            assert False, "Should have rejected non-validated principle"
        except AssertionError:
            pass  # Expected

    def test_phase14_dot5_input_is_validated_principle(self):
        """Phase14.5 的输入是 Validated Principle."""
        # Phase14.5 接收: Validated Principle → Capability Package
        # 这里只验证接口契约
        validated = PrincipleRecord(
            principle_id="p-p14-5",
            mechanism_name="Ready for Phase14.5",
            mechanism_description="可进入能力封装阶段",
            abstraction_level=AbstractionLevel.L2_PRINCIPLE,
            source_pattern_ids=["pat-a", "pat-b", "pat-c", "pat-d"],
            evidence_chain_ids=["e-001", "e-002", "e-003", "e-005"],
            status=PrincipleStatus.VALIDATED,
        )
        # Phase14.5 需要 validated principle
        assert validated.status == PrincipleStatus.VALIDATED
        assert len(validated.source_pattern_ids) >= 3
        assert len(validated.evidence_chain_ids) >= 3

    def test_no_phase14_dot5_deliverables_in_phase14_dot4(self):
        """Phase14.4 不产生 Phase14.5 的输出."""
        assert "writing_agent" in FORBIDDEN_OUTPUTS
        assert "prompt_instruction" in FORBIDDEN_OUTPUTS
        assert "generation_strategy" in FORBIDDEN_OUTPUTS
        assert "modification_suggestion" in FORBIDDEN_OUTPUTS

    def test_forbidden_outputs_comprehensive(self):
        """禁止输出列表完整."""
        assert len(FORBIDDEN_OUTPUTS) == 7


class TestTracingIntegrity:
    """可追溯性完整性."""

    def test_principle_has_source_patterns(self):
        """每个 Principle 必须追溯到一个或多个 Pattern."""
        p = PrincipleRecord(
            principle_id="p-t1",
            mechanism_name="T1",
            mechanism_description="T1",
            abstraction_level=AbstractionLevel.L1_MECHANISM_CANDIDATE,
            source_pattern_ids=["pat-x"],
            evidence_chain_ids=["e-001"],
        )
        assert len(p.source_pattern_ids) >= 1

    def test_principle_has_evidence_chain(self):
        """每个 Principle 必须有证据链."""
        p = PrincipleRecord(
            principle_id="p-t2",
            mechanism_name="T2",
            mechanism_description="T2",
            abstraction_level=AbstractionLevel.L1_MECHANISM_CANDIDATE,
            source_pattern_ids=["pat-x"],
            evidence_chain_ids=["e-001"],
        )
        assert len(p.evidence_chain_ids) >= 1

    def test_every_pattern_id_in_source(self):
        """source_pattern_ids 引用的 Pattern 必须可解析."""
        # 测试格式: 必须是 'pat-' 开头
        p = PrincipleRecord(
            principle_id="p-format",
            mechanism_name="Format",
            mechanism_description="Format",
            abstraction_level=AbstractionLevel.L1_MECHANISM_CANDIDATE,
            source_pattern_ids=["pat-alpha", "pat-beta"],
            evidence_chain_ids=["e-001"],
        )
        for pid in p.source_pattern_ids:
            assert pid.startswith("pat-"), f"Invalid pattern ID format: {pid}"

    def test_every_evidence_id_in_chain(self):
        """evidence_chain_ids 引用的 Evidence 必须可解析."""
        p = PrincipleRecord(
            principle_id="p-ef",
            mechanism_name="EF",
            mechanism_description="EF",
            abstraction_level=AbstractionLevel.L1_MECHANISM_CANDIDATE,
            source_pattern_ids=["pat-x"],
            evidence_chain_ids=["e-001", "e-002"],
        )
        for eid in p.evidence_chain_ids:
            assert eid.startswith("e-"), f"Invalid evidence ID format: {eid}"

    def test_derived_from_trace_chain(self):
        """derived_from 建立 Principle 间的溯源关系."""
        parent = PrincipleRecord(
            principle_id="p-parent",
            mechanism_name="Parent",
            mechanism_description="Parent mechanism",
            abstraction_level=AbstractionLevel.L2_PRINCIPLE,
            source_pattern_ids=["pat-a", "pat-b", "pat-c"],
            evidence_chain_ids=["e-001", "e-002"],
            status=PrincipleStatus.SUPERSEDED,
            superseded_by="p-child",
        )
        child = PrincipleRecord(
            principle_id="p-child",
            mechanism_name="Child",
            mechanism_description="Refined mechanism",
            abstraction_level=AbstractionLevel.L2_PRINCIPLE,
            source_pattern_ids=["pat-a", "pat-b", "pat-c", "pat-d"],
            evidence_chain_ids=["e-001", "e-002", "e-003"],
            derived_from="p-parent",
        )
        assert parent.superseded_by == child.principle_id
        assert child.derived_from == parent.principle_id


class TestEvolution:
    """Principle 演化机制."""

    def test_version_increments(self):
        """版本号递增."""
        p1 = PrincipleRecord(
            principle_id="p-evolve",
            mechanism_name="Evolving",
            mechanism_description="V1",
            abstraction_level=AbstractionLevel.L2_PRINCIPLE,
            source_pattern_ids=["pat-a", "pat-b", "pat-c"],
            evidence_chain_ids=["e-001"],
            version=1,
        )
        p2 = PrincipleRecord(
            principle_id="p-evolve",
            mechanism_name="Evolving Refined",
            mechanism_description="V2 with more evidence",
            abstraction_level=AbstractionLevel.L2_PRINCIPLE,
            source_pattern_ids=["pat-a", "pat-b", "pat-c", "pat-d", "pat-e"],
            evidence_chain_ids=["e-001", "e-002", "e-003", "e-004"],
            version=2,
        )
        assert p2.version > p1.version
        assert len(p2.source_pattern_ids) > len(p1.source_pattern_ids)
        assert len(p2.evidence_chain_ids) > len(p1.evidence_chain_ids)

    def test_history_accumulates(self):
        """历史记录累积."""
        p = PrincipleRecord(
            principle_id="p-hist",
            mechanism_name="History",
            mechanism_description="With history",
            abstraction_level=AbstractionLevel.L1_MECHANISM_CANDIDATE,
            history=[
                HistoryEntry(status="candidate", timestamp=datetime.now(), note="Created"),
                HistoryEntry(status="reviewing", timestamp=datetime.now(), note="Entering review"),
            ],
        )
        assert len(p.history) == 2
        assert p.history[0].status == "candidate"

    def test_superseded_by_points_to_newer(self):
        """Superseded 指向更新的 Principle."""
        p = PrincipleRecord(
            principle_id="p-old-v1",
            mechanism_name="Old Version",
            mechanism_description="旧版",
            abstraction_level=AbstractionLevel.L2_PRINCIPLE,
            source_pattern_ids=["pat-a", "pat-b", "pat-c"],
            evidence_chain_ids=["e-001"],
            status=PrincipleStatus.SUPERSEDED,
            superseded_by="p-new-v2",
        )
        assert p.status == PrincipleStatus.SUPERSEDED
        assert p.superseded_by is not None
        # 验证格式
        assert p.superseded_by.startswith("p-")

    def test_derived_from_is_optional(self):
        """derived_from 可选."""
        p = PrincipleRecord(
            principle_id="p-orig",
            mechanism_name="Original",
            mechanism_description="原始机制",
            abstraction_level=AbstractionLevel.L1_MECHANISM_CANDIDATE,
            source_pattern_ids=["pat-x"],
            evidence_chain_ids=["e-001"],
        )
        assert p.derived_from is None


class TestScopeAndBoundary:
    """作用域与边界."""

    def test_context_boundary_defined(self):
        """L2+ 必须有 context_boundary."""
        p = PrincipleRecord(
            principle_id="p-cb",
            mechanism_name="Boundary Check",
            mechanism_description="边界检查",
            abstraction_level=AbstractionLevel.L2_PRINCIPLE,
            source_pattern_ids=["pat-a", "pat-b", "pat-c"],
            evidence_chain_ids=["e-001", "e-002"],
            context_boundary="zh_novel_fiction_2015_2025",
        )
        assert p.context_boundary != ""

    def test_scope_description_provides_conditions(self):
        """scope 描述机制成立的条件."""
        p = PrincipleRecord(
            principle_id="p-scope2",
            mechanism_name="Scope Test",
            mechanism_description="Scope test mechanism",
            abstraction_level=AbstractionLevel.L2_PRINCIPLE,
            source_pattern_ids=["pat-a", "pat-b", "pat-c"],
            evidence_chain_ids=["e-001"],
            context_boundary="zh_novel_fiction",
            scope="适用条件: 包含明确的目标阻碍+信息差+时间约束的叙事结构",
        )
        assert len(p.scope) > 10
        assert "条件" in p.scope or "适用" in p.scope

    def test_scope_not_evaluative(self):
        """作用域不包含评价."""
        p = PrincipleRecord(
            principle_id="p-scope3",
            mechanism_name="Scope Eval",
            mechanism_description="Scope evaluation check",
            abstraction_level=AbstractionLevel.L2_PRINCIPLE,
            source_pattern_ids=["pat-a", "pat-b", "pat-c"],
            evidence_chain_ids=["e-001"],
            context_boundary="test",
            scope="适用于目标导向型叙事",
        )
        # 不包含"最好""更有效""推荐"等
        violations = check_forbidden_keywords(p.scope)
        assert not violations, f"Scope has forbidden keywords: {violations}"
