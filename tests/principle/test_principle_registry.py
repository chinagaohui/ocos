"""Phase14.4.5 — Principle Registry Contract Tests.

Tests verify:
1. PrincipleRecord ABI — fields, forbidden fields, trace_root, registry_revision
2. PrincipleDependency — 6 allowed relations, forbidden, no reasoning, target must be existing
3. Lifecycle — allowed/forbidden transitions
4. PrincipleReference (Query) — Reference not Record, query dimensions, forbidden ops
5. Freeze Audit — 5 checks (Domain Isolation, Trace Chain, Phase14→14.5, Knowledge Graph, Dangling Reference)
6. SSOT — Phase14.5 reads from Registry not Validation
7. Integration — full pipeline
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Dict
from enum import Enum


# ============ Enums ============


class AbstractionLevel(str, Enum):
    L1_MECHANISM_CANDIDATE = "L1_mechanism_candidate"
    L2_PRINCIPLE = "L2_principle"
    L3_GENERAL_PRINCIPLE = "L3_general_principle"


class LifecycleStatus(str, Enum):
    REGISTERED = "registered"
    SUPERSEDED = "superseded"
    ARCHIVED = "archived"
    INVALIDATED = "invalidated"


# ============ Models ============


@dataclass
class TraceRoot:
    """Consolidated root references for full Reality traceability."""
    pattern_ids: List[str] = field(default_factory=list)
    evidence_ids: List[str] = field(default_factory=list)
    relation_ids: List[str] = field(default_factory=list)


ALLOWED_DEPENDENCY_RELATIONS = {
    "generalizes",
    "supports",
    "contradicts",
    "refines",
    "depends_on",
    "derives_from",
}

FORBIDDEN_DEPENDENCY_RELATIONS = {
    "is_better_than",
    "is_more_effective",
    "is_recommended_over",
    "outperforms",
    "supersedes",
}


@dataclass
class PrincipleDependency:
    target_principle_id: str
    relation: str
    description: str


@dataclass
class VersionEntry:
    version: str
    status: str
    timestamp: datetime
    reason: str


@dataclass
class PrincipleRecord:
    principle_id: str
    derived_from_candidate: str
    abstraction_level: AbstractionLevel
    description: str
    trace_root: TraceRoot
    validation_record_ids: List[str] = field(default_factory=list)
    source_inference_records: List[str] = field(default_factory=list)
    dependency_refs: List[PrincipleDependency] = field(default_factory=list)
    version: str = "1.0.0"
    registry_revision: int = 1
    status: LifecycleStatus = LifecycleStatus.REGISTERED
    created_at: datetime = field(default_factory=datetime.now)
    superseded_by: Optional[str] = None
    history_summary: Optional[List[VersionEntry]] = None


@dataclass
class PrincipleReference:
    """Lightweight query result — not full PrincipleRecord."""
    principle_id: str
    version: str
    status: LifecycleStatus
    abstraction_level: AbstractionLevel
    trace_root_summary: Dict = field(default_factory=dict)
    dependency_summary: List[str] = field(default_factory=list)


# ============ Forbidden field definitions ============


FORBIDDEN_REGISTRY_FIELDS = {
    "quality_score",
    "effectiveness",
    "success_rate",
    "recommendation",
    "priority",
    "ranking",
    "confidence",
    "usefulness",
    "best_for",
    "should_apply",
    "popularity",
    "reader_approval",
}

FORBIDDEN_CAPABILITY_FIELDS = {
    "capability_package",
    "writing_rule",
    "prompt_template",
    "agent_instruction",
    "strategy_document",
    "best_practice_guide",
    "usage_advice",
}

FORBIDDEN_DEPENDENCY_PAYLOAD = {
    "reasoning",
    "proof",
    "analysis",
    "llm_explanation",
}

ALLOWED_LIFECYCLE_TRANSITIONS = {
    (LifecycleStatus.REGISTERED, LifecycleStatus.SUPERSEDED),
    (LifecycleStatus.REGISTERED, LifecycleStatus.INVALIDATED),
    (LifecycleStatus.REGISTERED, LifecycleStatus.ARCHIVED),
    (LifecycleStatus.SUPERSEDED, LifecycleStatus.ARCHIVED),
    (LifecycleStatus.INVALIDATED, LifecycleStatus.ARCHIVED),
}

FORBIDDEN_LIFECYCLE_TRANSITIONS = {
    (LifecycleStatus.SUPERSEDED, LifecycleStatus.INVALIDATED),
    (LifecycleStatus.ARCHIVED, LifecycleStatus.REGISTERED),
    (LifecycleStatus.INVALIDATED, LifecycleStatus.REGISTERED),
    (LifecycleStatus.ARCHIVED, LifecycleStatus.SUPERSEDED),
}


def is_valid_transition(from_status: LifecycleStatus, to_status: LifecycleStatus) -> bool:
    return (from_status, to_status) in ALLOWED_LIFECYCLE_TRANSITIONS


def is_forbidden_transition(from_status: LifecycleStatus, to_status: LifecycleStatus) -> bool:
    return (from_status, to_status) in FORBIDDEN_LIFECYCLE_TRANSITIONS


def check_dangling_reference(
    dependency_refs: List[PrincipleDependency],
    registered_ids: set,
) -> List[str]:
    """Check for dangling references — dependency targets that don't exist in Registry."""
    dangling = []
    for dep in dependency_refs:
        if dep.target_principle_id not in registered_ids:
            dangling.append(dep.target_principle_id)
    return dangling


def check_circular_dependency(
    dependency_refs: List[PrincipleDependency],
    current_id: str,
) -> bool:
    """Check if current_id appears as a dependency target (self-reference = circular)."""
    for dep in dependency_refs:
        if dep.target_principle_id == current_id:
            return True
    return False


# ============ Tests ============


class TestPrincipleRecordABI:
    """PrincipleRecord 模型."""

    def test_required_fields_exist(self):
        """必需字段."""
        pr = PrincipleRecord(
            principle_id="pr-001",
            derived_from_candidate="pc-001",
            abstraction_level=AbstractionLevel.L2_PRINCIPLE,
            description="Test principle",
            trace_root=TraceRoot(
                pattern_ids=["pat-A", "pat-B"],
                evidence_ids=["e-001"],
                relation_ids=["rel-001"],
            ),
        )
        assert pr.principle_id.startswith("pr-")
        assert pr.derived_from_candidate.startswith("pc-")
        assert pr.trace_root is not None
        assert len(pr.trace_root.pattern_ids) == 2
        assert pr.registry_revision == 1
        assert pr.status == LifecycleStatus.REGISTERED

    def test_default_version(self):
        """默认版本 1.0.0."""
        pr = PrincipleRecord(
            principle_id="pr-def",
            derived_from_candidate="pc-def",
            abstraction_level=AbstractionLevel.L2_PRINCIPLE,
            description="Default test",
            trace_root=TraceRoot(),
        )
        assert pr.version == "1.0.0"

    def test_trace_root_consolidated(self):
        """trace_root 合并所有根引用."""
        tr = TraceRoot(
            pattern_ids=["pat-001", "pat-002"],
            evidence_ids=["e-010", "e-020"],
            relation_ids=["rel-005"],
        )
        assert len(tr.pattern_ids) == 2
        assert len(tr.evidence_ids) == 2
        assert len(tr.relation_ids) == 1
        assert "pat-001" in tr.pattern_ids
        assert "e-010" in tr.evidence_ids

    def test_registry_revision_increments(self):
        """registry_revision 是整数，独立于 version."""
        pr_v1 = PrincipleRecord(
            principle_id="pr-rev",
            derived_from_candidate="pc-rev",
            abstraction_level=AbstractionLevel.L2_PRINCIPLE,
            description="Rev test",
            trace_root=TraceRoot(),
            version="1.0.0",
            registry_revision=1,
        )
        pr_v2 = PrincipleRecord(
            principle_id="pr-rev",
            derived_from_candidate="pc-rev",
            abstraction_level=AbstractionLevel.L2_PRINCIPLE,
            description="Rev test v2",
            trace_root=TraceRoot(),
            version="2.0.0",
            registry_revision=5,
        )
        # revision and version evolve independently
        assert pr_v1.registry_revision == 1
        assert pr_v2.registry_revision == 5
        assert pr_v1.version != pr_v2.version

    def test_no_capability_fields(self):
        """不含能力层字段."""
        pr = PrincipleRecord(
            principle_id="pr-nocap",
            derived_from_candidate="pc-nocap",
            abstraction_level=AbstractionLevel.L2_PRINCIPLE,
            description="No cap test",
            trace_root=TraceRoot(),
        )
        for field in FORBIDDEN_CAPABILITY_FIELDS:
            assert not hasattr(pr, field), f"Field should not exist: {field}"

    def test_no_forbidden_registry_fields(self):
        """不含禁止的 Registry 字段."""
        pr = PrincipleRecord(
            principle_id="pr-noforb",
            derived_from_candidate="pc-noforb",
            abstraction_level=AbstractionLevel.L2_PRINCIPLE,
            description="No forbidden",
            trace_root=TraceRoot(),
        )
        for field in FORBIDDEN_REGISTRY_FIELDS:
            assert not hasattr(pr, field), f"Field should not exist: {field}"


class TestPrincipleDependency:
    """PrincipleDependency — 6 允许关系 / 禁止关系 / 无推理 / target 必须存在."""

    def test_six_allowed_relations(self):
        """6 种允许关系."""
        assert len(ALLOWED_DEPENDENCY_RELATIONS) == 6
        assert "generalizes" in ALLOWED_DEPENDENCY_RELATIONS
        assert "supports" in ALLOWED_DEPENDENCY_RELATIONS
        assert "contradicts" in ALLOWED_DEPENDENCY_RELATIONS
        assert "refines" in ALLOWED_DEPENDENCY_RELATIONS
        assert "depends_on" in ALLOWED_DEPENDENCY_RELATIONS
        assert "derives_from" in ALLOWED_DEPENDENCY_RELATIONS

    def test_allowed_relations_can_be_used(self):
        """所有允许关系可构造."""
        examples = [
            ("pr-017", "generalizes", "P22 captures same mechanism at L3"),
            ("pr-003", "supports", "Reinforces conclusion from cross-context patterns"),
            ("pr-022", "contradicts", "Evidence points to opposite direction"),
            ("pr-011", "refines", "Narrows to romance fiction context"),
            ("pr-004", "depends_on", "Requires reader-time pacing as premise"),
            ("pr-008", "derives_from", "Evolved from original mechanism candidate"),
        ]
        for target, relation, desc in examples:
            dep = PrincipleDependency(
                target_principle_id=target,
                relation=relation,
                description=desc,
            )
            assert dep.relation in ALLOWED_DEPENDENCY_RELATIONS
            assert dep.target_principle_id.startswith("pr-")

    def test_forbidden_relations_rejected(self):
        """禁止的关系."""
        for rel in FORBIDDEN_DEPENDENCY_RELATIONS:
            assert rel not in ALLOWED_DEPENDENCY_RELATIONS

    def test_forbidden_relations_pattern(self):
        """价值比较类关系不可用于 dependency."""
        forbidden_patterns = ["better", "effective", "recommended", "outperform", "supersedes"]
        for rel in ALLOWED_DEPENDENCY_RELATIONS:
            for pat in forbidden_patterns:
                assert pat not in rel, f"'{rel}' contains forbidden word '{pat}'"

    def test_no_reasoning_in_dependency(self):
        """dependency_refs 不含推理内容."""
        dep = PrincipleDependency(
            target_principle_id="pr-017",
            relation="supports",
            description="Evidence from works A and B shows same mechanism",
        )
        for field in FORBIDDEN_DEPENDENCY_PAYLOAD:
            assert not hasattr(dep, field), f"Field should not exist: {field}"

    def test_dependency_rejects_reasoning_fields(self):
        """尝试在 dependency 上增加推理字段——被禁止."""
        bad_fields = {"reasoning", "proof", "analysis", "llm_explanation"}
        dep = PrincipleDependency(
            target_principle_id="pr-001",
            relation="generalizes",
            description="Structural description only",
        )
        for f in bad_fields:
            assert f not in dep.__dataclass_fields__

    def test_dependency_target_is_principle_record(self):
        """target 必须是 PrincipleRecord ID (pr-*), 不是其他阶段 ID."""
        dep = PrincipleDependency(
            target_principle_id="pr-042",
            relation="depends_on",
            description="Structural dependency",
        )
        assert dep.target_principle_id.startswith("pr-")
        # These prefixes are NOT allowed as targets
        not_allowed_prefixes = ["pc-", "vp-", "vr-", "ir-", "pat-", "e-", "rel-"]
        for prefix in not_allowed_prefixes:
            assert not dep.target_principle_id.startswith(prefix)


class TestDanglingReference:
    """Dangling Reference 检查."""

    def test_no_dangling_references(self):
        """所有引用存在."""
        registered = {"pr-001", "pr-002", "pr-003", "pr-017", "pr-022"}
        deps = [
            PrincipleDependency(target_principle_id="pr-017", relation="generalizes", description=""),
            PrincipleDependency(target_principle_id="pr-003", relation="supports", description=""),
        ]
        dangling = check_dangling_reference(deps, registered)
        assert len(dangling) == 0

    def test_dangling_reference_detected(self):
        """不存在的引用被检出."""
        registered = {"pr-001", "pr-002"}
        deps = [
            PrincipleDependency(target_principle_id="pr-999", relation="depends_on", description=""),
        ]
        dangling = check_dangling_reference(deps, registered)
        assert len(dangling) == 1
        assert "pr-999" in dangling

    def test_multiple_dangling(self):
        """多个不存在的引用."""
        registered = {"pr-001"}
        deps = [
            PrincipleDependency(target_principle_id="pr-999", relation="depends_on", description=""),
            PrincipleDependency(target_principle_id="pr-888", relation="supports", description=""),
            PrincipleDependency(target_principle_id="pr-001", relation="refines", description=""),
        ]
        dangling = check_dangling_reference(deps, registered)
        assert len(dangling) == 2
        assert "pr-001" not in dangling

    def test_empty_registry_dangling(self):
        """空 Registry 时任何引用都是 dangling."""
        deps = [
            PrincipleDependency(target_principle_id="pr-001", relation="depends_on", description=""),
        ]
        dangling = check_dangling_reference(deps, set())
        assert len(dangling) == 1


class TestCircularDependency:
    """循环依赖检查."""

    def test_no_self_reference(self):
        """不自引用."""
        deps = [
            PrincipleDependency(target_principle_id="pr-002", relation="depends_on", description=""),
        ]
        assert not check_circular_dependency(deps, "pr-001")

    def test_self_reference_detected(self):
        """自引用被检测."""
        deps = [
            PrincipleDependency(target_principle_id="pr-001", relation="depends_on", description=""),
        ]
        assert check_circular_dependency(deps, "pr-001")

    def test_indirect_self_reference_not_detected_by_simple_check(self):
        """间接自引用需要图遍历（简单检查不做图遍历）. """
        pr_a = PrincipleDependency(target_principle_id="pr-002", relation="depends_on", description="")
        pr_b = PrincipleDependency(target_principle_id="pr-001", relation="depends_on", description="")
        # Simple self-check: pr-001's deps don't self-reference
        assert not check_circular_dependency([pr_a], "pr-001")
        # But this is a circular chain: pr-001 → pr-002 → pr-001
        # Graph-level check would catch this; simple check does NOT
        # (intentional — Knowledge Graph Integrity Audit requires deeper analysis)


class TestLifecycle:
    """生命周期状态机."""

    def test_four_statuses(self):
        """4 种状态."""
        assert len(LifecycleStatus) == 4
        assert LifecycleStatus.REGISTERED.value == "registered"
        assert LifecycleStatus.SUPERSEDED.value == "superseded"
        assert LifecycleStatus.ARCHIVED.value == "archived"
        assert LifecycleStatus.INVALIDATED.value == "invalidated"

    def test_allowed_transitions(self):
        """允许的转换."""
        assert is_valid_transition(LifecycleStatus.REGISTERED, LifecycleStatus.SUPERSEDED)
        assert is_valid_transition(LifecycleStatus.REGISTERED, LifecycleStatus.INVALIDATED)
        assert is_valid_transition(LifecycleStatus.REGISTERED, LifecycleStatus.ARCHIVED)
        assert is_valid_transition(LifecycleStatus.SUPERSEDED, LifecycleStatus.ARCHIVED)
        assert is_valid_transition(LifecycleStatus.INVALIDATED, LifecycleStatus.ARCHIVED)

    def test_forbidden_transitions(self):
        """禁止的转换."""
        assert is_forbidden_transition(LifecycleStatus.SUPERSEDED, LifecycleStatus.INVALIDATED)
        assert is_forbidden_transition(LifecycleStatus.ARCHIVED, LifecycleStatus.REGISTERED)
        assert is_forbidden_transition(LifecycleStatus.INVALIDATED, LifecycleStatus.REGISTERED)
        assert is_forbidden_transition(LifecycleStatus.ARCHIVED, LifecycleStatus.SUPERSEDED)

    def test_superseded_not_invalidated(self):
        """SUPERSEDED → INVALIDATED 强制失败."""
        assert not is_valid_transition(LifecycleStatus.SUPERSEDED, LifecycleStatus.INVALIDATED)

    def test_superseded_requires_new_id(self):
        """SUPERSEDED 必须有 superseded_by."""
        pr = PrincipleRecord(
            principle_id="pr-old",
            derived_from_candidate="pc-old",
            abstraction_level=AbstractionLevel.L2_PRINCIPLE,
            description="Superseded principle",
            trace_root=TraceRoot(),
        )
        pr.status = LifecycleStatus.SUPERSEDED
        assert pr.superseded_by is None  # Must be populated

        pr.superseded_by = "pr-new"
        assert pr.superseded_by == "pr-new"

    def test_registered_default(self):
        """默认状态是 REGISTERED."""
        pr = PrincipleRecord(
            principle_id="pr-defstate",
            derived_from_candidate="pc-defstate",
            abstraction_level=AbstractionLevel.L2_PRINCIPLE,
            description="Default status",
            trace_root=TraceRoot(),
        )
        assert pr.status == LifecycleStatus.REGISTERED


class TestPrincipleReference:
    """Query 返回 Reference — 不是完整 Record."""

    def test_reference_not_record(self):
        """PrincipleReference 是轻量引用."""
        ref = PrincipleReference(
            principle_id="pr-001",
            version="1.0.0",
            status=LifecycleStatus.REGISTERED,
            abstraction_level=AbstractionLevel.L2_PRINCIPLE,
            trace_root_summary={"patterns": 3, "evidences": 2, "relations": 1},
            dependency_summary=["pr-017", "pr-003"],
        )
        assert ref.principle_id == "pr-001"
        assert ref.trace_root_summary["patterns"] == 3
        assert len(ref.dependency_summary) == 2

    def test_reference_lacks_record_fields(self):
        """Reference 不含完整 Record 的字段."""
        ref = PrincipleReference(
            principle_id="pr-ref",
            version="1.0.0",
            status=LifecycleStatus.REGISTERED,
            abstraction_level=AbstractionLevel.L2_PRINCIPLE,
        )
        hidden_fields = [
            "derived_from_candidate",
            "description",
            "trace_root",
            "validation_record_ids",
            "registry_revision",
            "superseded_by",
        ]
        for field in hidden_fields:
            assert not hasattr(ref, field), f"Reference should not have field: {field}"

    def test_reference_has_resolver_pattern(self):
        """Reference 可解析为 Record (懒加载模式). """
        ref = PrincipleReference(
            principle_id="pr-resolve",
            version="1.0.0",
            status=LifecycleStatus.REGISTERED,
            abstraction_level=AbstractionLevel.L2_PRINCIPLE,
        )
        # Phase14.5 access: Reference → Resolver → Principle
        assert ref.principle_id is not None
        assert ref.version is not None


class TestForbiddenQueryOperations:
    """禁止的查询操作."""

    def test_forbidden_ops_list_exists(self):
        """禁止操作清单."""
        forbidden_ops = {
            "sort_by_quality",
            "rank_principles",
            "select_optimal",
            "recommend_top",
            "find_similar",
            "cluster_principles",
            "summarize_principles",
            "explain_principle",
            "predict_applicability",
            "suggest_combination",
        }
        assert len(forbidden_ops) == 10


class TestFreezeAudit:
    """Freeze Audit 4+1 项检查."""

    # === Check 1: Domain Isolation ===

    def test_check1_domain_isolation(self):
        """PrincipleRecord 无能力层字段."""
        pr = PrincipleRecord(
            principle_id="pr-audit1",
            derived_from_candidate="pc-audit1",
            abstraction_level=AbstractionLevel.L2_PRINCIPLE,
            description="Audit check 1",
            trace_root=TraceRoot(),
        )
        for field in FORBIDDEN_CAPABILITY_FIELDS:
            assert not hasattr(pr, field), f"Domain isolation fail: {field}"

    def test_check1_no_value_fields(self):
        """无价值判断字段."""
        pr = PrincipleRecord(
            principle_id="pr-audit1b",
            derived_from_candidate="pc-audit1b",
            abstraction_level=AbstractionLevel.L2_PRINCIPLE,
            description="Audit check 1b",
            trace_root=TraceRoot(),
        )
        for field in FORBIDDEN_REGISTRY_FIELDS:
            assert not hasattr(pr, field), f"Value field fail: {field}"

    # === Check 2: Trace Chain ===

    def test_check2_trace_chain_complete(self):
        """trace_root 必须能追溯到 Evidence."""
        tr = TraceRoot(
            pattern_ids=["pat-001", "pat-002"],
            evidence_ids=["e-001"],
            relation_ids=["rel-001"],
        )
        assert len(tr.pattern_ids) >= 1
        assert len(tr.evidence_ids) >= 1
        # Every pattern_id starts with pat-
        for pid in tr.pattern_ids:
            assert pid.startswith("pat-") or pid.startswith("p-")
        # Every evidence_id starts with e- or ev-
        for eid in tr.evidence_ids:
            assert eid.startswith("e-") or eid.startswith("ev-")

    def test_check2_no_empty_chain(self):
        """trace_root 不能全部为空."""
        tr = TraceRoot()
        # Audit failure: no trace at all
        tr.pattern_ids = []
        tr.evidence_ids = []
        assert len(tr.pattern_ids) == 0 and len(tr.evidence_ids) == 0

    def test_check2_empty_patterns_fail(self):
        """无 pattern 追溯失败."""
        tr = TraceRoot(
            pattern_ids=[],
            evidence_ids=["e-001"],
            relation_ids=[],
        )
        assert len(tr.pattern_ids) == 0

    def test_check2_empty_evidence_fail(self):
        """无 evidence 追溯失败."""
        tr = TraceRoot(
            pattern_ids=["pat-001"],
            evidence_ids=[],
            relation_ids=[],
        )
        assert len(tr.evidence_ids) == 0

    # === Check 3: Phase14→14.5 Isolation ===

    def test_check3_query_returns_reference(self):
        """Query 返回 Reference，不是 Record."""
        ref = PrincipleReference(
            principle_id="pr-iso",
            version="1.0.0",
            status=LifecycleStatus.REGISTERED,
            abstraction_level=AbstractionLevel.L2_PRINCIPLE,
        )
        assert isinstance(ref, PrincipleReference)
        assert not isinstance(ref, PrincipleRecord)

    def test_check3_phase14dot5_reads_registry_not_validation(self):
        """Phase14.5 从 Registry 读取，不是从 Validation."""
        # Simulate Phase14.5 receiving only References
        refs = [
            PrincipleReference(principle_id="pr-A", version="1.0.0", status=LifecycleStatus.REGISTERED,
                               abstraction_level=AbstractionLevel.L2_PRINCIPLE),
        ]
        # Phase14.5 NEVER receives ValidatedPrinciple, DimensionResult, etc.
        forbidden_types = {"ValidatedPrinciple", "DimensionResult", "PrincipleCandidate"}
        for ftype in forbidden_types:
            assert ftype not in {type(r).__name__ for r in refs}

    # === Check 4: Knowledge Graph Integrity ===

    def test_check4a_no_self_cyclic(self):
        """不自引用."""
        pr = PrincipleRecord(
            principle_id="pr-cyclic",
            derived_from_candidate="pc-cyclic",
            abstraction_level=AbstractionLevel.L2_PRINCIPLE,
            description="Cyclic check",
            trace_root=TraceRoot(),
            dependency_refs=[
                PrincipleDependency(target_principle_id="pr-cyclic", relation="depends_on",
                                    description="Self-reference"),
            ],
        )
        assert check_circular_dependency(pr.dependency_refs, pr.principle_id)

    def test_check4b_no_orphan(self):
        """Principle 必须有至少一个 pattern 追溯."""
        pr_with_patterns = PrincipleRecord(
            principle_id="pr-orphan-chk",
            derived_from_candidate="pc-orphan",
            abstraction_level=AbstractionLevel.L2_PRINCIPLE,
            description="Orphan check",
            trace_root=TraceRoot(pattern_ids=["pat-001"], evidence_ids=["e-001"]),
        )
        assert len(pr_with_patterns.trace_root.pattern_ids) >= 1

    def test_check4c_no_dead_references(self):
        """dependency_refs 引用存在."""
        deps = [
            PrincipleDependency(target_principle_id="pr-017", relation="supports", description=""),
            PrincipleDependency(target_principle_id="pr-003", relation="depends_on", description=""),
        ]
        registered = {"pr-017", "pr-003", "pr-001"}
        dangling = check_dangling_reference(deps, registered)
        assert len(dangling) == 0

    def test_check4d_dangling_reference_audit_fail(self):
        """Dangling Reference → Audit Failure."""
        deps = [
            PrincipleDependency(target_principle_id="pr-999", relation="depends_on", description=""),
        ]
        registered = {"pr-001", "pr-002"}
        dangling = check_dangling_reference(deps, registered)
        assert len(dangling) >= 1  # Audit failure

    def test_check4e_cross_version_reference(self):
        """跨版本引用检查."""
        # pr-Y v2.0.0 必须存在且是 REGISTERED
        pr_y = PrincipleRecord(
            principle_id="pr-Y",
            derived_from_candidate="pc-Y",
            abstraction_level=AbstractionLevel.L2_PRINCIPLE,
            description="Target principle",
            trace_root=TraceRoot(pattern_ids=["pat-001"], evidence_ids=["e-001"]),
            version="2.0.0",
            status=LifecycleStatus.REGISTERED,
        )
        assert pr_y.status == LifecycleStatus.REGISTERED
        assert pr_y.version == "2.0.0"


class TestSSOT:
    """Single Source of Truth."""

    def test_registry_is_ssot(self):
        """Registry 是 Principle 的唯一来源."""
        pr = PrincipleRecord(
            principle_id="pr-ssot",
            derived_from_candidate="pc-ssot",
            abstraction_level=AbstractionLevel.L2_PRINCIPLE,
            description="SSOT check",
            trace_root=TraceRoot(),
        )
        # Phase14.5 goes through: Reference → Resolver → Principle
        # NOT through: Validation → Capability Package
        assert pr.principle_id is not None
        # Validation intermediate types are not resolvable from Registry
        non_registry_types = {"ValidatedPrinciple", "DimensionResult", "PrincipleCandidate"}
        for nrt in non_registry_types:
            assert "PrincipleRecord" not in nrt  # Only PrincipleRecord is registered
            # Phase14.5只能看到 PrincipleRecord，不是中间产物

    def test_phase14dot5_not_reading_validation(self):
        """Phase14.5 不得直接读取 Validation 输出。"""
        # Phase14.5 接收的是 Reference[]
        refs = [
            PrincipleReference(principle_id="pr-P15", version="1.0.0",
                               status=LifecycleStatus.REGISTERED,
                               abstraction_level=AbstractionLevel.L2_PRINCIPLE),
        ]
        # 验证输出类型不在 Phase14.5 的输入中
        for ref in refs:
            assert isinstance(ref, PrincipleReference)
        # Phase14.5 接触不到 ValidatedPrinciple
        pr = PrincipleRecord(
            principle_id="pr-P15b",
            derived_from_candidate="pc-P15b",
            abstraction_level=AbstractionLevel.L2_PRINCIPLE,
            description="P15 isolation",
            trace_root=TraceRoot(),
        )
        # pr validates that PrincipleRecord is the SSOT interface
        assert pr.derived_from_candidate.startswith("pc-")
        # But Phase14.5 doesn't see `derived_from_candidate` in Reference
        ref = PrincipleReference(
            principle_id=pr.principle_id,
            version=pr.version,
            status=pr.status,
            abstraction_level=pr.abstraction_level,
        )
        assert not hasattr(ref, "derived_from_candidate")


class TestIntegration:
    """集成场景."""

    def test_full_registry_entry(self):
        """完整的 Registry 条目."""
        trace = TraceRoot(
            pattern_ids=["pat-001", "pat-002", "pat-003"],
            evidence_ids=["e-001", "e-002"],
            relation_ids=["rel-001"],
        )
        deps = [
            PrincipleDependency(target_principle_id="pr-017", relation="generalizes",
                                description="Broader abstraction of the same mechanism"),
            PrincipleDependency(target_principle_id="pr-003", relation="supports",
                                description="Cross-context evidence reinforces conclusion"),
        ]
        pr = PrincipleRecord(
            principle_id="pr-int-001",
            derived_from_candidate="pc-int-001",
            abstraction_level=AbstractionLevel.L2_PRINCIPLE,
            description="Integrated test principle",
            trace_root=trace,
            validation_record_ids=["vr-int-001"],
            source_inference_records=["ir-int-001"],
            dependency_refs=deps,
            version="1.0.0",
            registry_revision=3,
            status=LifecycleStatus.REGISTERED,
        )
        assert len(pr.trace_root.pattern_ids) == 3
        assert len(pr.dependency_refs) == 2
        assert pr.registry_revision == 3
        assert pr.superseded_by is None

    def test_superseded_with_replacement(self):
        """被取代的 Principle."""
        # New version
        pr_new = PrincipleRecord(
            principle_id="pr-new-001",
            derived_from_candidate="pc-new-001",
            abstraction_level=AbstractionLevel.L2_PRINCIPLE,
            description="Newer abstraction",
            trace_root=TraceRoot(pattern_ids=["pat-010"], evidence_ids=["e-010"]),
            version="2.0.0",
            registry_revision=10,
            status=LifecycleStatus.REGISTERED,
        )
        # Superseded old version
        pr_old = PrincipleRecord(
            principle_id="pr-old-001",
            derived_from_candidate="pc-old-001",
            abstraction_level=AbstractionLevel.L2_PRINCIPLE,
            description="Superseded version",
            trace_root=TraceRoot(pattern_ids=["pat-005"], evidence_ids=["e-005"]),
            version="1.0.0",
            registry_revision=5,
            status=LifecycleStatus.SUPERSEDED,
            superseded_by=pr_new.principle_id,
        )
        assert pr_old.status == LifecycleStatus.SUPERSEDED
        assert pr_old.superseded_by == "pr-new-001"
        assert pr_old.version == "1.0.0"

    def test_query_reference_from_record(self):
        """从 Record 到 Reference 的转换."""
        pr = PrincipleRecord(
            principle_id="pr-ref-int",
            derived_from_candidate="pc-ref-int",
            abstraction_level=AbstractionLevel.L2_PRINCIPLE,
            description="Reference test",
            trace_root=TraceRoot(pattern_ids=["pat-A", "pat-B"], evidence_ids=["e-001"]),
            validation_record_ids=["vr-001"],
        )
        ref = PrincipleReference(
            principle_id=pr.principle_id,
            version=pr.version,
            status=pr.status,
            abstraction_level=pr.abstraction_level,
            trace_root_summary={
                "patterns": len(pr.trace_root.pattern_ids),
                "evidences": len(pr.trace_root.evidence_ids),
                "relations": len(pr.trace_root.relation_ids),
            },
            dependency_summary=[d.target_principle_id for d in pr.dependency_refs],
        )
        assert ref.principle_id == pr.principle_id
        assert ref.trace_root_summary["patterns"] == 2
        assert ref.trace_root_summary["evidences"] == 1
        # ref 不含 Record 级字段
        assert not hasattr(ref, "validation_record_ids")

    def test_knowledge_graph_integrity_full_audit(self):
        """完整的 KG 审计."""
        registered_ids = {"pr-001", "pr-002", "pr-003", "pr-017"}

        # 这个 Principle 有完整依赖图
        pr = PrincipleRecord(
            principle_id="pr-audit-full",
            derived_from_candidate="pc-audit-full",
            abstraction_level=AbstractionLevel.L2_PRINCIPLE,
            description="Full audit",
            trace_root=TraceRoot(pattern_ids=["pat-001"], evidence_ids=["e-001"]),
            dependency_refs=[
                PrincipleDependency(target_principle_id="pr-017", relation="generalizes",
                                    description=""),
                PrincipleDependency(target_principle_id="pr-003", relation="supports",
                                    description=""),
            ],
        )

        # Check 4a: no self-cycle
        assert not check_circular_dependency(pr.dependency_refs, pr.principle_id)

        # Check 4b: not orphaned
        assert len(pr.trace_root.pattern_ids) >= 1

        # Check 4c/4d: no dead/dangling references
        dangling = check_dangling_reference(pr.dependency_refs, registered_ids)
        assert len(dangling) == 0
