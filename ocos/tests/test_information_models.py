"""
Phase 17.4 — Information Theory → Code Alignment
测试覆盖：Model（InformationState/SemanticRole/PersistenceLevel/RelationType + Metadata）
"""

from __future__ import annotations

import dataclasses

import pytest

from ocos.models.information import (
    InformationMetadata,
    InformationState,
    PersistenceLevel,
    RelationType,
    SemanticRole,
    UniversalAddress,
)


# ══════════════════════════════════════════════════════════════════════════
# UniversalAddress
# ══════════════════════════════════════════════════════════════════════════

class TestUniversalAddress:

    def test_create(self):
        addr = UniversalAddress(namespace="working", type="goal", id="g123")
        assert addr.namespace == "working"
        assert addr.type == "goal"
        assert addr.id == "g123"
        assert addr.version == 1  # default

    def test_frozen_immutable(self):
        addr = UniversalAddress(namespace="working", type="goal", id="g1")
        with pytest.raises(dataclasses.FrozenInstanceError):
            addr.id = "g2"

    def test_equality(self):
        a1 = UniversalAddress(namespace="k", type="m", id="x")
        a2 = UniversalAddress(namespace="k", type="m", id="x")
        assert a1 == a2

    def test_inequality(self):
        a1 = UniversalAddress(namespace="k", type="m", id="x")
        a2 = UniversalAddress(namespace="k", type="m", id="y")
        assert a1 != a2

    def test_empty_namespace_raises(self):
        with pytest.raises(ValueError, match="namespace"):
            UniversalAddress(namespace="", type="g", id="1")

    def test_empty_type_raises(self):
        with pytest.raises(ValueError, match="type"):
            UniversalAddress(namespace="w", type="", id="1")

    def test_empty_id_raises(self):
        with pytest.raises(ValueError, match="id"):
            UniversalAddress(namespace="w", type="g", id="")

    def test_version_below_one_raises(self):
        with pytest.raises(ValueError, match="version"):
            UniversalAddress(namespace="w", type="g", id="1", version=0)

    def test_version_override(self):
        addr = UniversalAddress(namespace="w", type="g", id="1", version=3)
        assert addr.version == 3


# ══════════════════════════════════════════════════════════════════════════
# InformationState — 统一五态生命周期（INFORMATION_THEORY 第四章）
# ══════════════════════════════════════════════════════════════════════════

class TestInformationState:

    def test_created_to_validated(self):
        assert InformationState.CREATED.can_transition_to(InformationState.VALIDATED)

    def test_created_to_deprecated(self):
        """Created 可被拒绝/废弃。"""
        assert InformationState.CREATED.can_transition_to(InformationState.DEPRECATED)

    def test_validated_to_referenced(self):
        assert InformationState.VALIDATED.can_transition_to(InformationState.REFERENCED)

    def test_validated_to_deprecated(self):
        """Validated 可跳过引用直接弃用。"""
        assert InformationState.VALIDATED.can_transition_to(InformationState.DEPRECATED)

    def test_validated_to_archived(self):
        """Validated 可跳过引用直接归档。"""
        assert InformationState.VALIDATED.can_transition_to(InformationState.ARCHIVED)

    def test_referenced_to_deprecated(self):
        assert InformationState.REFERENCED.can_transition_to(InformationState.DEPRECATED)

    def test_deprecated_to_archived(self):
        assert InformationState.DEPRECATED.can_transition_to(InformationState.ARCHIVED)

    def test_archived_is_terminal(self):
        """ARCHIVED 不可回到任何状态（单向退化）。"""
        assert InformationState.ARCHIVED.is_terminal
        assert not InformationState.ARCHIVED.can_transition_to(InformationState.CREATED)
        assert not InformationState.ARCHIVED.can_transition_to(InformationState.VALIDATED)
        assert not InformationState.ARCHIVED.can_transition_to(InformationState.REFERENCED)
        assert not InformationState.ARCHIVED.can_transition_to(InformationState.DEPRECATED)

    def test_deprecated_not_terminal(self):
        """DEPRECATED 可归档，不是终端。"""
        assert not InformationState.DEPRECATED.is_terminal

    def test_no_reverse_transition(self):
        """不可逆原则——Created 不能回到非 Created 状态后倒回。"""
        assert not InformationState.VALIDATED.can_transition_to(InformationState.CREATED)
        assert not InformationState.REFERENCED.can_transition_to(InformationState.CREATED)
        assert not InformationState.REFERENCED.can_transition_to(InformationState.VALIDATED)

    def test_created_to_referenced_invalid(self):
        """Created 不可跳过 Validated 直接 Referenced。"""
        assert not InformationState.CREATED.can_transition_to(InformationState.REFERENCED)

    def test_created_to_archived_invalid(self):
        """Created 不可跳过 Validated 直接 Archived。"""
        assert not InformationState.CREATED.can_transition_to(InformationState.ARCHIVED)

    def test_referenced_to_archived_invalid(self):
        """Referenced 不可跳过 Deprecated 直接 Archived。"""
        assert not InformationState.REFERENCED.can_transition_to(InformationState.ARCHIVED)

    def test_referenced_to_validated_invalid(self):
        """Referenced 不可回到 Validated。"""
        assert not InformationState.REFERENCED.can_transition_to(InformationState.VALIDATED)

    # ── Legacy backward compat ──────────────────────────────────────

    def test_legacy_draft_resolves_to_created(self):
        assert InformationState("draft") == InformationState.CREATED

    def test_legacy_active_resolves_to_validated(self):
        assert InformationState("active") == InformationState.VALIDATED

    def test_legacy_decayed_resolves_to_deprecated(self):
        assert InformationState("decayed") == InformationState.DEPRECATED

    def test_legacy_promoted_resolves_to_deprecated(self):
        assert InformationState("promoted") == InformationState.DEPRECATED


# ══════════════════════════════════════════════════════════════════════════
# SemanticRole — 七类语义角色（INFORMATION_THEORY 第三章）
# ══════════════════════════════════════════════════════════════════════════

class TestSemanticRole:

    def test_legacy_fact_resolves_to_observation(self):
        assert SemanticRole("fact") == SemanticRole.OBSERVATION

    def test_legacy_intent_resolves_to_goal(self):
        assert SemanticRole("intent") == SemanticRole.GOAL

    def test_legacy_reasoning_resolves_to_memory(self):
        assert SemanticRole("reasoning") == SemanticRole.MEMORY

    def test_legacy_preference_resolves_to_policy(self):
        assert SemanticRole("preference") == SemanticRole.POLICY


# ══════════════════════════════════════════════════════════════════════════
# PersistenceLevel — 四层持久化（INFORMATION_THEORY 第三章）
# ══════════════════════════════════════════════════════════════════════════

class TestPersistenceLevel:

    def test_legacy_ephemeral_resolves_to_transient(self):
        assert PersistenceLevel("ephemeral") == PersistenceLevel.TRANSIENT

    def test_legacy_session_resolves_to_persistent(self):
        assert PersistenceLevel("session") == PersistenceLevel.PERSISTENT

    def test_legacy_workspace_resolves_to_persistent(self):
        assert PersistenceLevel("workspace") == PersistenceLevel.PERSISTENT


# ══════════════════════════════════════════════════════════════════════════
# RelationType — 三大类关系（INFORMATION_THEORY 第六章）
# ══════════════════════════════════════════════════════════════════════════

class TestRelationType:

    def test_legacy_references_resolves_to_part_of(self):
        assert RelationType("references") == RelationType.PART_OF


# ══════════════════════════════════════════════════════════════════════════
# InformationMetadata
# ══════════════════════════════════════════════════════════════════════════

class TestInformationMetadata:

    def test_defaults(self):
        addr = UniversalAddress(namespace="w", type="g", id="1")
        meta = InformationMetadata(address=addr)
        assert meta.state == InformationState.CREATED
        assert meta.semantic_role == SemanticRole.OBSERVATION
        assert meta.persistence_level == PersistenceLevel.TRANSIENT
        assert meta.importance == 0.5
        assert meta.tags == ()
        assert meta.ttl is None

    def test_custom_values(self):
        addr = UniversalAddress(namespace="k", type="m", id="m1")
        meta = InformationMetadata(
            address=addr,
            state=InformationState.VALIDATED,
            semantic_role=SemanticRole.KNOWLEDGE,
            persistence_level=PersistenceLevel.STABLE,
            importance=0.9,
            ttl=3600,
            source="test",
        )
        assert meta.state == InformationState.VALIDATED
        assert meta.semantic_role == SemanticRole.KNOWLEDGE
        assert meta.persistence_level == PersistenceLevel.STABLE
        assert meta.importance == 0.9
        assert meta.ttl == 3600
        assert meta.source == "test"

    def test_invalid_importance_negative(self):
        addr = UniversalAddress(namespace="w", type="g", id="1")
        with pytest.raises(ValueError, match="importance"):
            InformationMetadata(address=addr, importance=-0.1)

    def test_invalid_importance_over_one(self):
        addr = UniversalAddress(namespace="w", type="g", id="1")
        with pytest.raises(ValueError, match="importance"):
            InformationMetadata(address=addr, importance=1.1)

    def test_ttl_negative_raises(self):
        addr = UniversalAddress(namespace="w", type="g", id="1")
        with pytest.raises(ValueError, match="ttl"):
            InformationMetadata(address=addr, ttl=-1)

    def test_tags_as_tuple(self):
        addr = UniversalAddress(namespace="w", type="g", id="1")
        meta = InformationMetadata(address=addr, tags=("fast", "critical"))
        assert meta.tags == ("fast", "critical")

    def test_frozen(self):
        addr = UniversalAddress(namespace="w", type="g", id="1")
        meta = InformationMetadata(address=addr)
        with pytest.raises(dataclasses.FrozenInstanceError):
            meta.state = InformationState.CREATED


# ══════════════════════════════════════════════════════════════════════════
# Enum 完整性检查（对齐 INFORMATION_THEORY 定义）
# ══════════════════════════════════════════════════════════════════════════

class TestEnumCoverage:

    def test_all_information_states(self):
        states = {e.value for e in InformationState}
        expected = {"created", "validated", "referenced", "deprecated", "archived"}
        assert states == expected

    def test_all_semantic_roles(self):
        roles = {e.value for e in SemanticRole}
        expected = {
            "observation", "memory", "knowledge",
            "goal", "identity", "policy", "decision",
        }
        assert roles == expected

    def test_all_persistence_levels(self):
        levels = {e.value for e in PersistenceLevel}
        expected = {"transient", "persistent", "stable", "immutable"}
        assert levels == expected

    def test_all_relation_types(self):
        types = {e.value for e in RelationType}
        expected = {
            # Structural
            "part_of", "contains", "derived_from", "supports",
            # Semantic
            "contradicts", "similar_to", "refines",
            # Temporal
            "before", "after", "causes", "correlated_with",
        }
        assert types == expected
