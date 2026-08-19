"""
M0.5 测试 — Knowledge Promotion Rules。
"""

import pytest

from ocos.knowledge.knowledge_ontology import (
    KnowledgeLevel,
    KnowledgeStatus,
    KnowledgeUnit,
)
from ocos.knowledge.promotion_rules import (
    DEFAULT_TRIGGERS,
    PromotionPolicy,
    PromotionRuleEngine,
    PromotionTrigger,
    PromotionTriggerType,
)


# ── 触发条件 ───────────────────────────────────────────────────────────────


class TestDefaultTriggers:
    def test_observation_has_repetition_trigger(self):
        triggers = DEFAULT_TRIGGERS[KnowledgeLevel.OBSERVATION]
        assert any(t.trigger_type == PromotionTriggerType.REPETITION for t in triggers)

    def test_policy_has_no_triggers(self):
        assert DEFAULT_TRIGGERS[KnowledgeLevel.POLICY] == []

    def test_pattern_has_governance_trigger(self):
        triggers = DEFAULT_TRIGGERS[KnowledgeLevel.PATTERN]
        assert any(t.trigger_type == PromotionTriggerType.GOVERNANCE for t in triggers)

    def test_principle_has_governance_trigger(self):
        triggers = DEFAULT_TRIGGERS[KnowledgeLevel.PRINCIPLE]
        assert any(t.trigger_type == PromotionTriggerType.GOVERNANCE for t in triggers)

    def test_all_levels_have_triggers_in_defaults(self):
        for level in KnowledgeLevel:
            assert level in DEFAULT_TRIGGERS


class TestPromotionTrigger:
    def test_create_repetition_trigger(self):
        t = PromotionTrigger(
            trigger_type=PromotionTriggerType.REPETITION,
            threshold=5,
            description="test",
        )
        assert t.threshold == 5
        assert t.trigger_type == PromotionTriggerType.REPETITION


# ── 提升策略 ───────────────────────────────────────────────────────────────


class TestPromotionPolicy:
    def test_default_policy_allows_observation_to_evidence(self):
        policy = PromotionPolicy.default_for_level(
            KnowledgeLevel.OBSERVATION, KnowledgeLevel.EVIDENCE
        )
        unit = KnowledgeUnit(
            level=KnowledgeLevel.OBSERVATION,
            status=KnowledgeStatus.ACTIVE,
        )
        ok, errors = policy.evaluate(unit, source="pattern_detector")
        assert ok is True
        assert errors == []

    def test_default_policy_blocks_candidate_status(self):
        policy = PromotionPolicy.default_for_level(
            KnowledgeLevel.OBSERVATION, KnowledgeLevel.EVIDENCE
        )
        unit = KnowledgeUnit(
            level=KnowledgeLevel.OBSERVATION,
            status=KnowledgeStatus.CANDIDATE,
        )
        ok, errors = policy.evaluate(unit, source="pattern_detector")
        assert ok is False
        assert any("ACTIVE 或 VERIFIED" in e for e in errors)

    def test_default_policy_blocks_unauthorized_source(self):
        policy = PromotionPolicy(
            allowed_sources=["governance"],
        )
        unit = KnowledgeUnit(status=KnowledgeStatus.ACTIVE)
        ok, errors = policy.evaluate(unit, source="unknown_module")
        assert ok is False
        assert any("未被授权" in e for e in errors)

    def test_pattern_to_principle_requires_governance(self):
        policy = PromotionPolicy.default_for_level(
            KnowledgeLevel.PATTERN, KnowledgeLevel.PRINCIPLE
        )
        assert policy.requires_governance is True
        unit = KnowledgeUnit(
            level=KnowledgeLevel.PATTERN,
            status=KnowledgeStatus.ACTIVE,
        )
        # 无 governance 审批
        ok, errors = policy.evaluate(unit, source="governance")
        assert ok is False
        assert any("Governance 审批" in e for e in errors)

    def test_governance_approved_passes(self):
        policy = PromotionPolicy.default_for_level(
            KnowledgeLevel.PATTERN, KnowledgeLevel.PRINCIPLE
        )
        unit = KnowledgeUnit(
            level=KnowledgeLevel.PATTERN,
            status=KnowledgeStatus.ACTIVE,
        )
        ok, errors = policy.evaluate(
            unit,
            source="governance",
            context={"governance_approved": True},
        )
        assert ok is True


# ── 规则引擎 ───────────────────────────────────────────────────────────────


class TestPromotionRuleEngine:
    def test_register_custom_policy(self):
        engine = PromotionRuleEngine()
        policy = PromotionPolicy(allowed_sources=["custom"])
        engine.register_policy(
            KnowledgeLevel.OBSERVATION,
            KnowledgeLevel.EVIDENCE,
            policy,
        )
        assert engine.get_policy(
            KnowledgeLevel.OBSERVATION, KnowledgeLevel.EVIDENCE
        ) is policy

    def test_can_promote_valid(self):
        engine = PromotionRuleEngine()
        engine.load_default_policies()
        unit = KnowledgeUnit(
            level=KnowledgeLevel.OBSERVATION,
            status=KnowledgeStatus.ACTIVE,
        )
        ok, errors = engine.can_promote(
            unit, KnowledgeLevel.EVIDENCE, source="pattern_detector"
        )
        assert ok is True

    def test_can_promote_invalid_level_skip(self):
        engine = PromotionRuleEngine()
        engine.load_default_policies()
        unit = KnowledgeUnit(
            level=KnowledgeLevel.OBSERVATION,
            status=KnowledgeStatus.ACTIVE,
        )
        ok, errors = engine.can_promote(
            unit, KnowledgeLevel.PATTERN, source="pattern_detector"
        )
        assert ok is False
        assert any("不可从" in e for e in errors)

    def test_can_promote_without_default_policies(self):
        """未加载默认策略时，引擎仍使用 PromotionPolicy.default_for_level 进行检查。"""
        engine = PromotionRuleEngine()
        unit = KnowledgeUnit(
            level=KnowledgeLevel.OBSERVATION,
            status=KnowledgeStatus.ACTIVE,
        )
        # 使用默认策略允许的 source
        ok, errors = engine.can_promote(
            unit, KnowledgeLevel.EVIDENCE, source="manual"
        )
        assert ok is True

    def test_check_trigger_repetition(self):
        engine = PromotionRuleEngine()
        unit = KnowledgeUnit(level=KnowledgeLevel.OBSERVATION)
        triggered, reason = engine.check_trigger(unit, repetition_count=5)
        assert triggered is True
        assert "重复次数" in reason

    def test_check_trigger_not_met(self):
        engine = PromotionRuleEngine()
        unit = KnowledgeUnit(level=KnowledgeLevel.OBSERVATION)
        triggered, reason = engine.check_trigger(unit, repetition_count=1)
        assert triggered is False

    def test_check_trigger_confidence(self):
        engine = PromotionRuleEngine()
        unit = KnowledgeUnit(level=KnowledgeLevel.EVIDENCE)
        triggered, reason = engine.check_trigger(unit, confidence=0.8)
        assert triggered is True

    def test_check_trigger_governance(self):
        engine = PromotionRuleEngine()
        unit = KnowledgeUnit(level=KnowledgeLevel.PATTERN)
        triggered, reason = engine.check_trigger(
            unit, governance_approved=True
        )
        assert triggered is True

    def test_load_default_policies(self):
        engine = PromotionRuleEngine()
        engine.load_default_policies()
        # 应该有 4 个策略（5 个层级 → 4 条提升路径）
        count = 0
        for s in KnowledgeLevel:
            for t in KnowledgeLevel:
                if engine.get_policy(s, t):
                    count += 1
        assert count == 4

    def test_pattern_governance_policy_full_flow(self):
        engine = PromotionRuleEngine()
        engine.load_default_policies()
        unit = KnowledgeUnit(
            level=KnowledgeLevel.PATTERN,
            status=KnowledgeStatus.ACTIVE,
        )
        # 无 governance → 拒绝
        ok, _ = engine.can_promote(
            unit, KnowledgeLevel.PRINCIPLE, source="governance"
        )
        assert ok is False

        # 有 governance → 通过
        ok, _ = engine.can_promote(
            unit,
            KnowledgeLevel.PRINCIPLE,
            source="governance",
            context={"governance_approved": True},
        )
        assert ok is True
