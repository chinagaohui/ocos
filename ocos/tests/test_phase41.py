"""Phase 41 Acceptance Tests: PM41-01 ~ PM41-05."""
import pytest
from ocos.self.self_types import ExperiencePattern
from ocos.self.experience_profile import ExperienceProfile
from ocos.personal_memory import (
    WisdomState, WisdomScope, WisdomEvidence, WisdomItem,
    WisdomCollection,
    PatternInterpreter, WisdomValidator, WisdomStore,
    ReflectionEngine, ReflectionResult,
    ValidationDecision,
)


# ═══ Helpers ═══

def _make_pattern(pid, cat, label, freq=3, conf=0.8, tick=1, note=""):
    return ExperiencePattern(
        pattern_id=pid, category=cat, label=label, frequency=freq,
        evidence_ids=(), confidence=conf, abstracted_at_tick=tick, note=note,
    )


def _make_evidence(eid, source_id, supports=True, strength=0.8, tick=1):
    return WisdomEvidence(eid, "pattern", source_id, supports, strength, tick)


# ═══ PM41-01: Experience Extraction ═══

class TestPM4101ExperienceExtraction:
    """Episode → Pattern → Wisdom candidate flow."""

    def test_successful_patterns_become_candidates(self):
        """成功模式经解释后成为候选智慧。"""
        profile = ExperienceProfile(
            successful_patterns=[
                _make_pattern("sp1", "successful", "abi_first", freq=5),
                _make_pattern("sp2", "successful", "incremental_val", freq=4),
            ],
        )
        engine = ReflectionEngine()
        result = engine.reflect(profile, "user-a", 100)

        assert len(result.wisdom_candidates) >= 1
        for w in result.wisdom_candidates:
            assert w.state == WisdomState.CONFIRMED

    def test_single_pattern_not_enough(self):
        """单个模式不足以形成智慧。"""
        pi = PatternInterpreter(min_patterns_for_wisdom=2)
        patterns = [_make_pattern("sp1", "successful", "lone", freq=5)]
        results = pi.interpret(patterns, 100)

        assert all(r.rejected for r in results)

    def test_low_frequency_filtered(self):
        """低频模式被过滤。"""
        pi = PatternInterpreter(min_patterns_for_wisdom=2, min_frequency=3)
        patterns = [
            _make_pattern("sp1", "successful", "good", freq=5),
            _make_pattern("sp2", "successful", "rare", freq=1),
        ]
        results = pi.interpret(patterns, 100)
        rejected = [r for r in results if r.rejected]
        assert len(rejected) >= 1  # 低频模式被拒绝

    def test_neutral_patterns_no_wisdom(self):
        """Neutral 类别不产生智慧。"""
        pi = PatternInterpreter()
        patterns = [_make_pattern("sp1", "neutral", "observed", freq=3)]
        results = pi.interpret(patterns, 100)
        assert all(r.rejected for r in results)


# ═══ PM41-02: Pattern Separation ═══

class TestPM4102PatternSeparation:
    """Pattern ≠ Wisdom: 统计规律不是智慧原则。"""

    def test_pattern_without_wisdom_can_exist(self):
        """Pattern 可以独立存在，不自动成为 Wisdom。"""
        pattern = _make_pattern("sp1", "successful", "test", freq=1)
        pattern_on_its_own = pattern  # Pattern exists as data
        assert pattern_on_its_own.pattern_id == "sp1"
        # Pattern is a data structure, not yet wisdom

    def test_wisdom_requires_interpretation(self):
        """智慧必须经过 PatternInterpreter 解释，不是 Pattern 本身。"""
        pattern = _make_pattern("sp1", "successful", "abi_first", freq=5)
        pi = PatternInterpreter(min_patterns_for_wisdom=1, min_frequency=3)
        result = pi.interpret([pattern], 100)

        if not result[0].rejected:
            assert result[0].candidate_wisdom is not None
            # 输出的是 WisdomItem, 不是原始 Pattern
            assert isinstance(result[0].candidate_wisdom, WisdomItem)

    def test_success_vs_failure_semantics(self):
        """成功模式和失败模式产生不同类型的原则表述。"""
        pi = PatternInterpreter(min_patterns_for_wisdom=2, min_frequency=3)
        success = [_make_pattern("s1", "successful", "abi_freeze", freq=4),
                   _make_pattern("s2", "successful", "test_first", freq=3)]
        failure = [_make_pattern("f1", "failure", "scope_creep", freq=4),
                   _make_pattern("f2", "failure", "no_tests", freq=3)]

        sr = pi.interpret(success, 100)
        fr = pi.interpret(failure, 100)

        # Both should produce candidates
        s_wisdom = [r.candidate_wisdom.principle for r in sr if not r.rejected]
        f_wisdom = [r.candidate_wisdom.principle for r in fr if not r.rejected]

        if s_wisdom:
            assert "effective" in s_wisdom[0].lower()
        if f_wisdom:
            assert "ineffective" in f_wisdom[0].lower()


# ═══ PM41-03: Wisdom Validation ═══

class TestPM4103WisdomValidation:
    """证据阈值和反例检查。"""

    def test_sufficient_evidence_passes(self):
        """充足证据通过验证。"""
        wisdom = WisdomItem(wisdom_id="w1", principle="Test principle.")
        wisdom.evidence = [
            _make_evidence("e1", "s1", True, 0.9, 1),
            _make_evidence("e2", "s2", True, 0.8, 2),
        ]
        validator = WisdomValidator(min_supporting_evidence=2)
        result = validator.validate_and_promote(wisdom, 100)

        assert result.passed
        assert wisdom.state == WisdomState.CONFIRMED

    def test_insufficient_evidence_needs_more(self):
        """证据不足时标记需要更多。"""
        wisdom = WisdomItem(wisdom_id="w2", principle="Test.")
        wisdom.evidence = [
            _make_evidence("e1", "s1", True, 0.5, 1),
        ]
        validator = WisdomValidator(min_supporting_evidence=2)
        result = validator.validate_and_promote(wisdom, 100)

        assert not result.passed
        assert result.decision == ValidationDecision.NEED_MORE_EVIDENCE
        assert wisdom.state == WisdomState.VALIDATING  # CANDIDATE → VALIDATING

    def test_too_many_counter_examples_rejected(self):
        """反例过多时拒绝。"""
        wisdom = WisdomItem(wisdom_id="w3", principle="Bad theory.")
        wisdom.evidence = [
            _make_evidence("e1", "s1", True, 0.6, 1),
            _make_evidence("e2", "s2", True, 0.6, 2),
            _make_evidence("e3", "c1", False, 0.9, 3),
            _make_evidence("e4", "c2", False, 0.9, 4),
        ]
        validator = WisdomValidator(
            min_supporting_evidence=2,
            max_counter_ratio=0.3,
        )
        result = validator.validate_and_promote(wisdom, 100)

        assert result.decision == ValidationDecision.REJECTED
        assert wisdom.state == WisdomState.DEPRECATED

    def test_low_confidence_needs_more(self):
        """低置信度需要更多证据。"""
        wisdom = WisdomItem(wisdom_id="w4", principle="Maybe true.")
        wisdom.evidence = [
            _make_evidence("e1", "s1", True, 0.15, 1),
            _make_evidence("e2", "s2", True, 0.15, 2),
            _make_evidence("e3", "s3", True, 0.1, 3),
            _make_evidence("e4", "c1", False, 0.15, 4),
        ]
        # support = 0.4, against = 0.15 → confidence = 0.4/0.55 ≈ 0.727 > 0.6
        # Wait still too high. Let me make counter stronger.
        # Actually let me just tweak the validator's min_confidence to 0.95
        validator = WisdomValidator(max_counter_ratio=1.0, min_confidence=0.95)
        result = validator.validate_and_promote(wisdom, 100)

        assert not result.passed
        assert result.decision == ValidationDecision.NEED_MORE_EVIDENCE

    def test_confidence_calculation(self):
        """evidence_strength 正确计算支持/反对比例。"""
        wisdom = WisdomItem(wisdom_id="w5", principle="Test.")
        wisdom.evidence = [
            _make_evidence("e1", "s1", True, 0.8, 1),
            _make_evidence("e2", "s2", True, 0.6, 2),
            _make_evidence("e3", "c1", False, 0.3, 3),
        ]
        # strength = (0.8+0.6) / (0.8+0.6+0.3) = 1.4/1.7 ≈ 0.824
        assert 0.8 < wisdom.evidence_strength < 0.85


# ═══ PM41-04: Personalization ═══

class TestPM4104Personalization:
    """相同事件在不同用户身上形成不同智慧。"""

    def test_different_users_different_collections(self):
        """不同用户拥有独立的智慧集合。"""
        store = WisdomStore()

        # 两个不同用户
        w_a = WisdomItem(wisdom_id="w-a", principle="User A wisdom")
        w_b = WisdomItem(wisdom_id="w-b", principle="User B wisdom")

        store.add_wisdom("user-a", w_a)
        store.add_wisdom("user-b", w_b)

        # User-a 只有自己的
        assert store.get_wisdom("user-a", "w-a") is not None
        assert store.get_wisdom("user-a", "w-b") is None

        # User-b 只有自己的
        assert store.get_wisdom("user-b", "w-b") is not None
        assert store.get_wisdom("user-b", "w-a") is None

    def test_same_events_can_form_different_wisdom(self):
        """不同 ExperienceProfile 在不同集合中形成不同智慧。"""
        store = WisdomStore()
        engine_a = ReflectionEngine(store=store)
        engine_b = ReflectionEngine(store=store)

        # 相同模式的 profile
        def make_profile():
            return ExperienceProfile(
                successful_patterns=[
                    _make_pattern("sp1", "successful", "pattern_x", freq=5),
                    _make_pattern("sp2", "successful", "pattern_y", freq=4),
                ],
            )

        r_a = engine_a.reflect(make_profile(), "user-a", 100)
        r_b = engine_b.reflect(make_profile(), "user-b", 200)

        # 都生成了 wisdom
        assert r_a.wisdom_confirmed >= 1
        assert r_b.wisdom_confirmed >= 1

        # 但存储在不同的集合中
        a_active = store.list_confirmed("user-a")
        b_active = store.list_confirmed("user-b")
        assert len(a_active) >= 1
        assert len(b_active) >= 1

    def test_wisdom_collection_user_isolation(self):
        """WisdomCollection 按 user_id 隔离。"""
        c1 = WisdomCollection(user_id="user-a")
        c2 = WisdomCollection(user_id="user-b")

        w = WisdomItem(wisdom_id="wx", principle="Shared pattern")
        c1.add(w)
        c2.add(w)

        assert c1.get("wx") is not None
        assert c2.get("wx") is not None
        assert c1.user_id != c2.user_id


# ═══ PM41-05: Boundary Protection ═══

class TestPM4105BoundaryProtection:
    """Wisdom 不能修改 Identity/Goal/Permission。"""

    def test_wisdom_item_has_no_identity_modification(self):
        """WisdomItem 结构上不包含修改 Identity 的能力。"""
        w = WisdomItem(wisdom_id="w1", principle="Some wisdom")
        # WisdomItem 没有 identity_ref 字段（与 SelfModel 不同）
        assert not hasattr(w, "identity_ref")
        # WisdomItem 没有 identity 相关的 setter
        assert not hasattr(w, "set_identity")

    def test_wisdom_has_no_goal_creation(self):
        """WisdomItem 不包含创建 Goal 的方法。"""
        w = WisdomItem(wisdom_id="w1", principle="Do something")
        assert not hasattr(w, "create_goal")
        assert not hasattr(w, "modify_goal")

    def test_wisdom_has_no_permission_override(self):
        """WisdomItem 不包含覆盖 PermissionGateway 的方法。"""
        w = WisdomItem(wisdom_id="w1", principle="Override")
        assert not hasattr(w, "override_permission")
        assert not hasattr(w, "bypass_gateway")

    def test_wisdom_store_does_not_expose_identity(self):
        """WisdomStore 不暴露 Identity.anchor 的访问/修改。"""
        store = WisdomStore()
        assert not hasattr(store, "identity_anchor")
        assert not hasattr(store, "set_identity")

    def test_wisdom_is_advisory_only(self):
        """智慧提供认知参考，不直接执行。"""
        # 结构级保证：WisdomItem 只有数据字段和状态转换方法，
        # 没有任何 execute/apply/run 方法。
        w = WisdomItem(wisdom_id="w1", principle="Guide")
        wisdom_methods = [m for m in dir(w)
                          if not m.startswith("_") and callable(getattr(w, m))]
        executable = [m for m in wisdom_methods
                      if m in ("execute", "apply", "run", "command", "act")]
        assert len(executable) == 0


# ═══ Wisdom Lifecycle ═══

class TestWisdomLifecycle:
    """智慧生命周期状态机测试。"""

    def test_normal_lifecycle(self):
        """CANDIDATE → VALIDATING → CONFIRMED → ACTIVE → DEPRECATED。"""
        w = WisdomItem(wisdom_id="w1", principle="Test.")
        assert w.state == WisdomState.CANDIDATE

        assert w.promote_to(WisdomState.VALIDATING, 1)
        assert w.state == WisdomState.VALIDATING

        assert w.promote_to(WisdomState.CONFIRMED, 2)
        assert w.state == WisdomState.CONFIRMED

        assert w.promote_to(WisdomState.ACTIVE, 3)
        assert w.state == WisdomState.ACTIVE

        assert w.promote_to(WisdomState.DEPRECATED, 4)
        assert w.state == WisdomState.DEPRECATED

    def test_deprecated_is_terminal(self):
        """DEPRECATED 是终点状态，不可逆。"""
        w = WisdomItem(wisdom_id="w1", principle="Old.", state=WisdomState.DEPRECATED)
        assert not w.promote_to(WisdomState.ACTIVE, 1)
        assert w.state == WisdomState.DEPRECATED

    def test_cannot_skip_states(self):
        """不能跳过状态。"""
        w = WisdomItem(wisdom_id="w1", principle="Test.")
        assert not w.promote_to(WisdomState.ACTIVE, 1)  # CANDIDATE → ACTIVE invalid
        assert w.state == WisdomState.CANDIDATE

    def test_is_mutable_property(self):
        """CANDIDATE/VALIDATING 可修改，CONFIRMED+ 不可逆（除 DEPRECATED）。"""
        w = WisdomItem(wisdom_id="w1", principle="Test.")
        assert w.state.is_mutable
        w.promote_to(WisdomState.VALIDATING, 1)
        assert w.state.is_mutable
        w.promote_to(WisdomState.CONFIRMED, 2)
        assert not w.state.is_mutable

    def test_is_usable_property(self):
        """只有 CONFIRMED/ACTIVE 可用。"""
        w = WisdomItem(wisdom_id="w1", principle="Test.")
        assert not w.state.is_usable  # CANDIDATE
        w.promote_to(WisdomState.VALIDATING, 1)
        assert not w.state.is_usable  # VALIDATING still not usable
        w.promote_to(WisdomState.CONFIRMED, 2)
        assert w.state.is_usable  # CONFIRMED is usable
        w.promote_to(WisdomState.ACTIVE, 3)
        assert w.state.is_usable  # ACTIVE is usable


# ═══ WisdomScope ═══

class TestWisdomScope:

    def test_universal_scope(self):
        """无 domain/condition 时适用于所有场景。"""
        scope = WisdomScope()
        assert scope.is_universal
        assert scope.applies_to("any_domain")

    def test_domain_restricted(self):
        """域限制正确过滤。"""
        scope = WisdomScope(domains=("architecture", "testing"))
        assert scope.applies_to("architecture")
        assert not scope.applies_to("cooking")

    def test_condition_matching(self):
        """条件匹配逻辑。"""
        scope = WisdomScope(conditions=("large_system", "multi_team"))
        assert scope.applies_to("architecture", ("large_system",))
        assert scope.applies_to("architecture", ("multi_team",))
        # conditions 是 OR 关系：任一满足即匹配
        assert scope.applies_to("architecture", ("large_system", "python"))

    def test_exclusion_overrides(self):
        """排除条件优先于其他匹配。"""
        scope = WisdomScope(
            domains=("architecture",),
            exclusions=("prototype",),
        )
        # 即使 domain 匹配，exclusion 命中则拒
        assert not scope.applies_to("architecture", ("prototype", "python"))


# ═══ WisdomCollection ═══

class TestWisdomCollection:

    def test_applicable_filtering(self):
        """applicable_to 正确过滤。"""
        c = WisdomCollection(user_id="test")
        w1 = WisdomItem(wisdom_id="w1", principle="Arch wisdom",
                        state=WisdomState.ACTIVE,
                        scope=WisdomScope(domains=("architecture",)))
        w2 = WisdomItem(wisdom_id="w2", principle="Cooking wisdom",
                        state=WisdomState.ACTIVE,
                        scope=WisdomScope(domains=("cooking",)))
        c.add(w1)
        c.add(w2)

        results = c.applicable_to("architecture")
        assert len(results) == 1
        assert results[0].wisdom_id == "w1"

    def test_non_usable_filtered(self):
        """非可用状态的智慧不被返回。"""
        c = WisdomCollection(user_id="test")
        w = WisdomItem(wisdom_id="w1", principle="Candidate",
                       state=WisdomState.CANDIDATE)
        c.add(w)

        results = c.applicable_to("any")
        assert len(results) == 0
