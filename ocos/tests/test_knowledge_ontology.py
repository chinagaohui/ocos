"""
M0 测试 — Knowledge Ontology。
"""

import pytest

from ocos.knowledge.knowledge_ontology import (
    ELEVATION_MATRIX,
    STATUS_TRANSITIONS,
    ElevationRecord,
    KnowledgeLevel,
    KnowledgeStatus,
    KnowledgeUnit,
    can_elevate,
    can_transition,
    get_elevation_targets,
    get_level_index,
    get_next_statuses,
    is_higher_level,
    validate_elevation,
)


# ── Enum 完整性 ─────────────────────────────────────────────────────────────


class TestKnowledgeLevel:
    def test_has_5_levels(self):
        assert len(KnowledgeLevel) == 5

    def test_ordered_from_low_to_high(self):
        levels = list(KnowledgeLevel)
        assert levels == [
            KnowledgeLevel.OBSERVATION,
            KnowledgeLevel.EVIDENCE,
            KnowledgeLevel.PATTERN,
            KnowledgeLevel.PRINCIPLE,
            KnowledgeLevel.POLICY,
        ]


class TestKnowledgeStatus:
    def test_has_5_statuses(self):
        assert len(KnowledgeStatus) == 5

    def test_status_values(self):
        assert KnowledgeStatus.CANDIDATE.value == "candidate"
        assert KnowledgeStatus.VERIFIED.value == "verified"
        assert KnowledgeStatus.ACTIVE.value == "active"
        assert KnowledgeStatus.DEPRECATED.value == "deprecated"
        assert KnowledgeStatus.ARCHIVED.value == "archived"


# ── 提升关系 ───────────────────────────────────────────────────────────────


class TestElevationMatrix:
    def test_observation_can_elevate_to_evidence(self):
        assert can_elevate(KnowledgeLevel.OBSERVATION, KnowledgeLevel.EVIDENCE)

    def test_evidence_can_elevate_to_pattern(self):
        assert can_elevate(KnowledgeLevel.EVIDENCE, KnowledgeLevel.PATTERN)

    def test_pattern_can_elevate_to_principle(self):
        assert can_elevate(KnowledgeLevel.PATTERN, KnowledgeLevel.PRINCIPLE)

    def test_principle_can_elevate_to_policy(self):
        assert can_elevate(KnowledgeLevel.PRINCIPLE, KnowledgeLevel.POLICY)

    def test_policy_cannot_elevate(self):
        assert get_elevation_targets(KnowledgeLevel.POLICY) == []

    def test_cannot_skip_levels(self):
        assert not can_elevate(KnowledgeLevel.OBSERVATION, KnowledgeLevel.PATTERN)
        assert not can_elevate(KnowledgeLevel.OBSERVATION, KnowledgeLevel.POLICY)
        assert not can_elevate(KnowledgeLevel.EVIDENCE, KnowledgeLevel.PRINCIPLE)
        assert not can_elevate(KnowledgeLevel.PATTERN, KnowledgeLevel.POLICY)

    def test_cannot_elevate_down(self):
        assert not can_elevate(KnowledgeLevel.PATTERN, KnowledgeLevel.EVIDENCE)
        assert not can_elevate(KnowledgeLevel.POLICY, KnowledgeLevel.PRINCIPLE)

    def test_level_index_ordering(self):
        assert get_level_index(KnowledgeLevel.OBSERVATION) == 0
        assert get_level_index(KnowledgeLevel.EVIDENCE) == 1
        assert get_level_index(KnowledgeLevel.PATTERN) == 2
        assert get_level_index(KnowledgeLevel.PRINCIPLE) == 3
        assert get_level_index(KnowledgeLevel.POLICY) == 4

    def test_is_higher_level(self):
        assert is_higher_level(KnowledgeLevel.POLICY, KnowledgeLevel.OBSERVATION)
        assert is_higher_level(KnowledgeLevel.PRINCIPLE, KnowledgeLevel.PATTERN)
        assert not is_higher_level(KnowledgeLevel.EVIDENCE, KnowledgeLevel.PATTERN)
        assert not is_higher_level(KnowledgeLevel.OBSERVATION, KnowledgeLevel.OBSERVATION)

    def test_elevation_matrix_five_entries(self):
        assert len(ELEVATION_MATRIX) == 5


# ── 状态机 ─────────────────────────────────────────────────────────────────


class TestStatusMachine:
    def test_candidate_can_transition_to_verified(self):
        assert can_transition(KnowledgeStatus.CANDIDATE, KnowledgeStatus.VERIFIED)

    def test_candidate_can_transition_to_deprecated(self):
        assert can_transition(KnowledgeStatus.CANDIDATE, KnowledgeStatus.DEPRECATED)

    def test_active_can_transition_to_deprecated(self):
        assert can_transition(KnowledgeStatus.ACTIVE, KnowledgeStatus.DEPRECATED)

    def test_deprecated_can_reactivate(self):
        assert can_transition(KnowledgeStatus.DEPRECATED, KnowledgeStatus.ACTIVE)

    def test_archived_cannot_transition(self):
        assert get_next_statuses(KnowledgeStatus.ARCHIVED) == []

    def test_cannot_skip_to_active_from_candidate(self):
        assert not can_transition(KnowledgeStatus.CANDIDATE, KnowledgeStatus.ACTIVE)

    def test_cannot_go_back_from_verified(self):
        assert not can_transition(KnowledgeStatus.VERIFIED, KnowledgeStatus.CANDIDATE)

    def test_all_transition_defined(self):
        """每个状态至少有一条可转换路径（除了 ARCHIVED）。"""
        for status in KnowledgeStatus:
            if status != KnowledgeStatus.ARCHIVED:
                assert len(get_next_statuses(status)) >= 1


# ── 知识单元 ├──────────────────────────────────────────────────────────────


class TestKnowledgeUnit:
    def test_create_observation(self):
        unit = KnowledgeUnit(
            level=KnowledgeLevel.OBSERVATION,
            content={"text": "机器人捡起红色方块"},
            source="vision_sensor",
        )
        assert unit.level == KnowledgeLevel.OBSERVATION
        assert unit.status == KnowledgeStatus.CANDIDATE
        assert unit.version == 1
        assert unit.unit_id != ""

    def test_create_policy(self):
        unit = KnowledgeUnit(
            level=KnowledgeLevel.POLICY,
            status=KnowledgeStatus.ACTIVE,
            content={"rule": "always_sort_by_color"},
            source="governance",
            version=3,
        )
        assert unit.level == KnowledgeLevel.POLICY
        assert unit.status == KnowledgeStatus.ACTIVE
        assert unit.version == 3

    def test_unique_ids(self):
        u1 = KnowledgeUnit()
        u2 = KnowledgeUnit()
        assert u1.unit_id != u2.unit_id

    def test_parent_id_tracking(self):
        parent = KnowledgeUnit()
        child = KnowledgeUnit(
            level=KnowledgeLevel.EVIDENCE,
            parent_id=parent.unit_id,
        )
        assert child.parent_id == parent.unit_id


class TestElevationRecord:
    def test_create_elevation_record(self):
        record = ElevationRecord(
            unit_id="u1",
            from_level=KnowledgeLevel.OBSERVATION,
            to_level=KnowledgeLevel.EVIDENCE,
            reason="观察到 3 次相同行为",
            promoted_by="pattern_detector",
        )
        assert record.from_level == KnowledgeLevel.OBSERVATION
        assert record.to_level == KnowledgeLevel.EVIDENCE
        assert record.reason == "观察到 3 次相同行为"


class TestValidateElevation:
    def test_valid_elevation(self):
        unit = KnowledgeUnit(
            level=KnowledgeLevel.OBSERVATION,
            status=KnowledgeStatus.ACTIVE,
        )
        ok, errors = validate_elevation(unit, KnowledgeLevel.EVIDENCE)
        assert ok is True
        assert errors == []

    def test_invalid_level_skip(self):
        unit = KnowledgeUnit(
            level=KnowledgeLevel.OBSERVATION,
            status=KnowledgeStatus.ACTIVE,
        )
        ok, errors = validate_elevation(unit, KnowledgeLevel.PATTERN)
        assert ok is False
        assert any("不可从" in e for e in errors)

    def test_invalid_status(self):
        unit = KnowledgeUnit(
            level=KnowledgeLevel.OBSERVATION,
            status=KnowledgeStatus.CANDIDATE,  # 不是 ACTIVE 或 VERIFIED
        )
        ok, errors = validate_elevation(unit, KnowledgeLevel.EVIDENCE)
        assert ok is False
        assert any("ACTIVE 或 VERIFIED" in e for e in errors)
