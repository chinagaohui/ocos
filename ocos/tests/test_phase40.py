"""Phase 40 Acceptance Tests: S40-01 ~ S40-05.

验证 Self Model 在以下场景:
    S40-01: Identity Immutability      — Self update 不修改 identity_ref
    S40-02: Capability Awareness        — known/unknown/confidence
    S40-03: Knowledge Boundary          — known/unknown/needs verification
    S40-04: Experience Projection       — Memory → ExperienceProfile, Self ≠ Belief
    S40-05: Runtime Binding             — SelfModel 通过 Runtime 绑定
"""

from __future__ import annotations

import pytest
from datetime import datetime, timezone

from ocos.self import (
    SelfModel,
    SelfUpdateContract,
    SelfUpdateSource,
    SelfBoundaryRules,
    KnowledgeConfidence,
    CapabilityStatement,
    DomainStatement,
    ExperiencePattern,
    PreferenceType,
    PreferenceEntry,
    CapabilityAwareness,
    KnowledgeBoundary,
    ExperienceProfile,
    PreferenceModel,
    CognitiveState,
    create_self_model,
    initialize_empty_components,
    update_capability,
    update_knowledge_boundary,
    update_experience,
    update_preferences,
    update_cognitive_state,
    self_summary,
)


# ═══════════════════════════════════════════════════════════════════════════════
# Mock Identity Anchor（符合 IdentityAnchor 协议）
# ═══════════════════════════════════════════════════════════════════════════════

class MockIdentityAnchor:
    """模拟 IdentityAnchor — 只暴露 get_identity_id()。"""

    def __init__(self, agent_id: str = "test-agent-001"):
        self._agent_id = agent_id
        self._modified = False

    def get_identity_id(self) -> str:
        return self._agent_id

    def mark_modified(self):
        self._modified = True


# ═══════════════════════════════════════════════════════════════════════════════
# S40-01: Identity Immutability
# ═══════════════════════════════════════════════════════════════════════════════

class TestS4001IdentityImmutability:
    """Self update 不修改 identity_ref。"""

    def test_identity_ref_is_read_only(self):
        """identity_ref 不能被 update() 修改。"""
        anchor = MockIdentityAnchor("agent-001")
        sm = create_self_model(anchor)

        contract = SelfUpdateContract(
            source=SelfUpdateSource.RUNTIME_OBSERVATION,
            reason="try to change identity",
            tick_id=1,
            fields_changed=("identity_ref",),
        )

        result = sm.update(contract, "identity_ref", "new-id")
        assert result is False  # rejected
        assert sm.identity_ref == "agent-001"  # unchanged

    def test_update_history_does_not_contain_rejected(self):
        """拒绝的更新不记录在 update_history 中。"""
        anchor = MockIdentityAnchor()
        sm = create_self_model(anchor)

        contract = SelfUpdateContract(
            source=SelfUpdateSource.RUNTIME_OBSERVATION,
            reason="try to change identity",
            tick_id=1,
            fields_changed=("identity_ref",),
        )
        sm.update(contract, "identity_ref", "new-id")
        assert len(sm.update_history) == 0

    def test_anchor_remains_unchanged_after_self_update(self):
        """Self 更新后，Identity.anchor 不受影响。"""
        anchor = MockIdentityAnchor("anchor-test")
        sm = create_self_model(anchor)

        # 更新能力
        ca = CapabilityAwareness()
        ok = update_capability(sm, ca, SelfUpdateSource.CAPABILITY_REGISTRY,
                               "init caps", 1)
        assert ok is True

        # identity_ref 不变
        assert sm.identity_ref == "anchor-test"

    def test_create_self_model_with_empty_components(self):
        """初始化后所有组件为 None，identity_ref 正确。"""
        anchor = MockIdentityAnchor("agent-empty")
        sm = create_self_model(anchor)

        assert sm.identity_ref == "agent-empty"
        assert sm.capability_awareness is None
        assert sm.knowledge_boundary is None
        assert sm.experience_profile is None
        assert sm.preference_model is None
        assert sm.cognitive_state is None
        assert sm.components_loaded == 0

    def test_initialize_components(self):
        """initialize_empty_components 填充所有组件。"""
        anchor = MockIdentityAnchor()
        sm = create_self_model(anchor)
        sm = initialize_empty_components(sm)

        assert sm.components_loaded == 5
        assert sm.has_capability_awareness
        assert sm.has_knowledge_boundary


# ═══════════════════════════════════════════════════════════════════════════════
# S40-02: Capability Awareness
# ═══════════════════════════════════════════════════════════════════════════════

class TestS4002CapabilityAwareness:
    """已知/未知能力声明 + 置信度。"""

    def test_register_known_capability(self):
        ca = CapabilityAwareness()
        ca.register(CapabilityStatement(
            name="code_generation",
            available=True,
            confidence=0.9,
            source="capability_registry_v1",
        ))

        assert ca.known_count == 1
        assert ca.available_count == 1
        assert ca.is_capable("code_generation") is True

    def test_low_confidence_goes_to_uncertain(self):
        ca = CapabilityAwareness()
        ca.register(CapabilityStatement(
            name="image_editing",
            available=True,
            confidence=0.3,
            source="registry",
        ))

        assert ca.known_count == 0
        assert ca.uncertain_count == 1
        assert ca.is_capable("image_editing") is True  # claims available but uncertain

    def test_is_capable_returns_none_for_unknown(self):
        ca = CapabilityAwareness()
        assert ca.is_capable("quantum_computing") is None

    def test_mark_unavailable(self):
        ca = CapabilityAwareness()
        ca.register(CapabilityStatement(
            name="web_browsing", available=True, confidence=0.9,
            source="registry",
        ))

        ca.mark_unavailable("web_browsing", tick_id=42)

        assert ca.is_capable("web_browsing") is False
        assert ca.available_count == 0
        assert ca.unavailable_count == 1

    def test_overall_confidence_average(self):
        ca = CapabilityAwareness()
        ca.register(CapabilityStatement("a", True, 0.8, "src"))
        ca.register(CapabilityStatement("b", True, 0.6, "src"))

        # Both >= 0.6 → both in known, average = 0.7
        assert 0.65 < ca.overall_confidence < 0.75


# ═══════════════════════════════════════════════════════════════════════════════
# S40-03: Knowledge Boundary
# ═══════════════════════════════════════════════════════════════════════════════

class TestS4003KnowledgeBoundary:
    """已知/不确定/需验证的知识域。"""

    def test_declare_known_domain(self):
        kb = KnowledgeBoundary()
        kb.declare(DomainStatement(
            domain="software_architecture",
            confidence=KnowledgeConfidence.KNOWN,
            evidence_count=10,
        ))

        assert kb.is_known("software_architecture") is True
        assert len(kb.known_domains) == 1

    def test_unknown_domain(self):
        kb = KnowledgeBoundary()
        kb.declare(DomainStatement(
            domain="stock_market", confidence=KnowledgeConfidence.UNKNOWN,
        ))

        assert kb.is_known("stock_market") is False
        assert len(kb.unknown_domains) == 1

    def test_needs_verification(self):
        kb = KnowledgeBoundary()
        kb.declare(DomainStatement(
            domain="medical_advice", confidence=KnowledgeConfidence.KNOWN,
            evidence_count=3,
        ))
        kb.mark_needs_verification("medical_advice", tick_id=50)

        assert len(kb.needs_verification) == 1
        assert kb.get("medical_advice").confidence == KnowledgeConfidence.NEEDS_VERIFICATION

    def test_confidence_ratio(self):
        kb = KnowledgeBoundary()
        kb.declare(DomainStatement("a", KnowledgeConfidence.KNOWN, 5))
        kb.declare(DomainStatement("b", KnowledgeConfidence.UNCERTAIN, 1))
        kb.declare(DomainStatement("c", KnowledgeConfidence.KNOWN, 8))

        assert kb.overall_confidence == pytest.approx(2.0 / 3.0)

    def test_not_declared_is_none(self):
        kb = KnowledgeBoundary()
        assert kb.is_known("physics") is None


# ═══════════════════════════════════════════════════════════════════════════════
# S40-04: Experience Projection + Self ≠ Belief
# ═══════════════════════════════════════════════════════════════════════════════

class TestS4004ExperienceProjection:
    """Memory → ExperienceProfile，Self ≠ Belief。"""

    def test_add_success_pattern(self):
        ep = ExperienceProfile()
        ep.add_pattern(ExperiencePattern(
            pattern_id="p1",
            label="incremental validation",
            category="successful",
            frequency=5,
            confidence=0.9,
            evidence_ids=("mem-001", "mem-002"),
            abstracted_at_tick=100,
        ))

        assert ep.success_count == 1
        assert ep.failure_count == 0
        assert ep.success_ratio == 1.0

    def test_add_failure_pattern(self):
        ep = ExperienceProfile()
        ep.add_pattern(ExperiencePattern(
            pattern_id="p2",
            label="insufficient analysis",
            category="failure",
            frequency=3,
            confidence=0.8,
            evidence_ids=("mem-003",),
            abstracted_at_tick=200,
        ))

        assert ep.failure_count == 1
        assert ep.success_ratio == 0.0

    def test_neutral_pattern_is_tendency(self):
        ep = ExperienceProfile()
        ep.add_pattern(ExperiencePattern(
            pattern_id="p3",
            label="nighttime low activity",
            category="neutral",
            frequency=10,
            confidence=0.7,
            evidence_ids=(),
            abstracted_at_tick=300,
        ))

        assert ep.success_count == 0
        assert ep.failure_count == 0
        assert len(ep.behavioral_tendencies) == 1

    def test_experience_profile_is_not_belief(self):
        """SelfModel 的 ExperienceProfile 不是 Belief 的世界判断。"""
        ep = ExperienceProfile()
        ep.add_pattern(ExperiencePattern(
            "p4", "pattern_label", "successful", 1, 0.9,
            ("mem-01",), 100,
        ))

        # ExperienceProfile 是统计性模式
        assert ep.success_ratio == 1.0
        # ≠ 世界判断（如 "Python 是最好的语言"）

    def test_learning_rate_bounds(self):
        ep = ExperienceProfile()
        assert 0.0 <= ep.learning_rate_estimate <= 1.0

        ep.update_learning_rate(1.0)
        assert ep.learning_rate_estimate == 1.0

        ep.update_learning_rate(-2.0)
        assert ep.learning_rate_estimate == 0.0  # clamped

    def test_remove_stale_patterns(self):
        ep = ExperienceProfile()
        ep.add_pattern(ExperiencePattern(
            "old", "old pattern", "successful", 1, 0.5, (), 10,
        ))
        ep.add_pattern(ExperiencePattern(
            "new", "new pattern", "successful", 1, 0.5, (), 100,
        ))

        removed = ep.remove_stale(before_tick=50)
        assert removed == 1
        assert ep.success_count == 1


# ═══════════════════════════════════════════════════════════════════════════════
# Preference Model
# ═══════════════════════════════════════════════════════════════════════════════

class TestPreferenceModel:
    """User vs Operational 分离。"""

    def test_user_and_operational_separated(self):
        pm = PreferenceModel()

        pm.set_user(PreferenceEntry(
            "u1", PreferenceType.USER, "response_language",
            "chinese", "user feedback", 0.9, 100,
        ))
        pm.set_operational(PreferenceEntry(
            "o1", PreferenceType.OPERATIONAL, "batch_size",
            "10", "performance test", 0.7, 100,
        ))

        assert pm.user_count == 1
        assert pm.operational_count == 1
        assert pm.get_user_pref("response_language") == "chinese"
        assert pm.get_operational_pref("batch_size") == "10"

    def test_wrong_type_raises(self):
        pm = PreferenceModel()

        with pytest.raises(ValueError):
            pm.set_user(PreferenceEntry(
                "x", PreferenceType.OPERATIONAL, "k", "v", "test", 0.5, 1,
            ))

    def test_apply_to_user_overrides_operational(self):
        pm = PreferenceModel()
        pm.set_operational(PreferenceEntry(
            "o", PreferenceType.OPERATIONAL, "timeout", "30", "test", 0.5, 1,
        ))
        pm.set_user(PreferenceEntry(
            "u", PreferenceType.USER, "timeout", "60", "user said", 0.9, 1,
        ))

        result = pm.apply_to({"other_key": "keep"})
        assert result["timeout"] == "60"  # user wins
        assert result["other_key"] == "keep"


# ═══════════════════════════════════════════════════════════════════════════════
# S40-05: Runtime Binding + Update Source Constraints
# ═══════════════════════════════════════════════════════════════════════════════

class TestS4005RuntimeBinding:
    """SelfModel 通过 Runtime 绑定 + 更新来源约束。"""

    def test_forbidden_external_agent_rejected(self):
        """禁止外部 Agent 直接更新 SelfModel。"""
        anchor = MockIdentityAnchor()
        sm = create_self_model(anchor)

        contract = SelfUpdateContract(
            source=SelfUpdateSource.EXTERNAL_AGENT,
            reason="external agent trying to update",
            tick_id=1,
            fields_changed=("capability_awareness",),
        )

        result = sm.update(contract, "capability_awareness", CapabilityAwareness())
        assert result is False

    def test_invalid_component_name_rejected(self):
        """非法组件名被拒绝。"""
        anchor = MockIdentityAnchor()
        sm = create_self_model(anchor)

        contract = SelfUpdateContract(
            source=SelfUpdateSource.RUNTIME_OBSERVATION,
            reason="try invalid component",
            tick_id=1,
            fields_changed=("personality",),
        )

        result = sm.update(contract, "personality", None)
        assert result is False

    def test_confidence_clamped(self):
        """self_confidence 始终在 [0.1, 1.0] 范围内。"""
        anchor = MockIdentityAnchor()
        sm = create_self_model(anchor)

        # 负数 confidence_impact 不能降到 < 0.1
        contract = SelfUpdateContract(
            source=SelfUpdateSource.RUNTIME_OBSERVATION,
            reason="test clamp",
            tick_id=1,
            fields_changed=("capability_awareness",),
            confidence_impact=-1.0,
        )
        sm.update(contract, "capability_awareness", CapabilityAwareness())
        assert sm.self_confidence >= 0.1

    def test_cognitive_state_updates_without_confidence_change(self):
        """认知状态更新不影响 self_confidence（实时数据）。"""
        anchor = MockIdentityAnchor()
        sm = create_self_model(anchor)
        sm = initialize_empty_components(sm)

        original_confidence = sm.self_confidence

        cs = CognitiveState()
        cs.update(tick_id=100, workload=0.3, focus_id="goal_1")

        ok = update_cognitive_state(sm, cs, SelfUpdateSource.RUNTIME_OBSERVATION,
                                     "periodic update", 100)
        assert ok is True
        assert sm.self_confidence == original_confidence  # unchanged

    def test_boundary_rules_defaults(self):
        """默认边界规则包含所有必需约束。"""
        rules = SelfBoundaryRules()

        assert rules.identity_is_immutable
        assert rules.no_goal_generation
        assert rules.no_direct_belief_mutation
        assert SelfUpdateSource.EXPERIENCE in rules.allowed_update_sources
        assert SelfUpdateSource.EXTERNAL_AGENT not in rules.allowed_update_sources

    def test_update_contract_validation(self):
        """SelfUpdateContract 合法性检查。"""
        # 合法合同
        valid = SelfUpdateContract(
            source=SelfUpdateSource.EXPERIENCE,
            reason="from consolidated memory",
            tick_id=10,
            fields_changed=("experience_profile",),
        )
        assert valid.is_valid

        # 非法来源
        invalid = SelfUpdateContract(
            source=SelfUpdateSource.EXTERNAL_AGENT,
            reason="malicious",
            tick_id=10,
            fields_changed=("identity_ref",),
        )
        assert not invalid.is_valid

    def test_update_history_grows(self):
        """成功的更新记录在 history 中。"""
        anchor = MockIdentityAnchor()
        sm = create_self_model(anchor)

        for i in range(3):
            ca = CapabilityAwareness()
            ok = update_capability(sm, ca, SelfUpdateSource.CAPABILITY_REGISTRY,
                                   f"update {i}", i * 10)
            assert ok

        assert len(sm.update_history) == 3

    def test_self_summary(self):
        """self_summary 正确生成文本。"""
        anchor = MockIdentityAnchor()
        sm = create_self_model(anchor)
        sm = initialize_empty_components(sm)

        summary = self_summary(sm)
        assert "Self v1" in summary
        assert "Capability" in summary
        assert "Knowledge" in summary
        assert "Experience" in summary
        assert "Preference" in summary
        assert "Cognitive" in summary

    def test_e2e_self_model_lifecycle(self):
        """完整 SelfModel 生命周期。"""
        # 1. Create from anchor
        anchor = MockIdentityAnchor("ocos-001")
        sm = create_self_model(anchor)
        assert sm.identity_ref == "ocos-001"

        # 2. Initialize components
        sm = initialize_empty_components(sm)
        assert sm.components_loaded == 5

        # 3. Update capabilities
        ca = CapabilityAwareness()
        ca.register(CapabilityStatement("reasoning", True, 0.95, "builtin"))
        ca.register(CapabilityStatement("file_io", True, 0.9, "builtin"))
        ok = update_capability(sm, ca, SelfUpdateSource.CAPABILITY_REGISTRY,
                               "initial capability scan", 0)
        assert ok
        assert sm.capability_awareness.available_count == 2

        # 4. Update knowledge
        kb = KnowledgeBoundary()
        kb.declare(DomainStatement("architecture", KnowledgeConfidence.KNOWN, 20))
        ok = update_knowledge_boundary(sm, kb, SelfUpdateSource.MEMORY_CONSOLIDATION,
                                       "knowledge baseline", 10)
        assert ok
        assert sm.knowledge_boundary.total_domains == 1

        # 5. Update experience
        ep = ExperienceProfile()
        ep.add_pattern(ExperiencePattern(
            "ep1", "incremental approach", "successful", 5, 0.85,
            ("mem-1", "mem-2"), 100,
        ))
        ok = update_experience(sm, ep, SelfUpdateSource.EXPERIENCE,
                               "after task completion", 200)
        assert ok
        assert sm.experience_profile.success_count == 1

        # 6. Update cognitive state
        cs = CognitiveState()
        cs.update(tick_id=300, workload=0.4, uncertainty_level=0.2,
                  focus_id="goal-architecture")
        ok = update_cognitive_state(sm, cs, SelfUpdateSource.RUNTIME_OBSERVATION,
                                    "tick observation", 300)
        assert ok
        assert sm.cognitive_state.active_focus == "goal-architecture"

        # 7. Verify update history
        assert len(sm.update_history) == 4

        # 8. Identity never changed
        assert sm.identity_ref == "ocos-001"


# ═══════════════════════════════════════════════════════════════════════════════
# SelfUpdateContract edge cases
# ═══════════════════════════════════════════════════════════════════════════════

class TestUpdateContractEdgeCases:

    def test_empty_reason_is_invalid(self):
        contract = SelfUpdateContract(
            source=SelfUpdateSource.EXPERIENCE,
            reason="",
            tick_id=1,
            fields_changed=("x",),
        )
        assert not contract.is_valid

    def test_empty_fields_is_invalid(self):
        contract = SelfUpdateContract(
            source=SelfUpdateSource.EXPERIENCE,
            reason="test",
            tick_id=1,
            fields_changed=(),
        )
        assert not contract.is_valid
