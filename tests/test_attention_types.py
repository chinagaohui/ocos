"""OCOS attention_types 注意力类型测试。

Phase 39.5 Attention ABI 不变式：
    Attention ≠ Desire — 不产生欲望
    Focus ≠ Goal — 焦点是当前关注，Goal 是用户意图
    InertiaPolicy 切换阈值
"""

import pytest

from ocos.attention.attention_types import (
    FocusType,
    AttentionState,
    AttentionCandidate,
    InertiaPolicy,
    AttentionTrace,
    AttentionScoringWeights,
    FocusSelectionResult,
)


class TestFocusType:
    def test_three_types(self):
        vals = {t.value for t in FocusType}
        assert vals == {"goal", "event", "maintenance"}


class TestAttentionState:
    def test_defaults(self):
        s = AttentionState()
        assert s.focus_id is None
        assert s.is_focused is False
        assert s.focus_duration == 0

    def test_focused(self):
        s = AttentionState(focus_id="G1", focus_type=FocusType.GOAL,
                           focus_priority=0.8, start_tick=10)
        assert s.is_focused is True

    def test_focus_duration(self):
        s = AttentionState(start_tick=5, interrupted_tick=10)
        assert s.focus_duration == 5

    def test_focus_duration_no_interrupt(self):
        s = AttentionState(start_tick=5, interrupted_tick=None)
        # interrupted_tick is None → uses start_tick → duration = 0
        assert s.focus_duration == 0

    def test_to_dict_roundtrip(self):
        s = AttentionState(
            focus_id="G1", focus_type=FocusType.EVENT,
            focus_priority=0.7, start_tick=1,
            context_refs=("ref1", "ref2"),
            total_focus_changes=3,
        )
        d = s.to_dict()
        s2 = AttentionState.from_dict(d)
        assert s2.focus_id == "G1"
        assert s2.focus_type == FocusType.EVENT
        assert s2.context_refs == ("ref1", "ref2")
        assert s2.total_focus_changes == 3

    def test_from_dict_missing_fields(self):
        s = AttentionState.from_dict({})
        assert s.focus_id is None
        assert s.focus_type is None
        assert s.focus_priority == 0.0


class TestAttentionCandidate:
    def test_defaults(self):
        c = AttentionCandidate(candidate_id="C1", candidate_type=FocusType.GOAL)
        assert c.summary == ""
        assert c.goal_importance == 0.0
        assert c.source == ""

    def test_custom(self):
        c = AttentionCandidate(
            candidate_id="G-001",
            candidate_type=FocusType.GOAL,
            summary="write novel",
            goal_importance=0.9,
            urgency=0.7,
            source="goal_tree",
        )
        assert c.goal_importance == 0.9
        assert c.source == "goal_tree"


class TestInertiaPolicy:
    @pytest.fixture
    def policy(self):
        return InertiaPolicy()

    def test_default_values(self, policy):
        assert policy.minimum_focus_duration == 3
        assert policy.switch_threshold == 1.3
        assert policy.cooldown_ticks == 5

    def test_switch_when_no_current_focus(self, policy):
        should, reason = policy.should_switch(
            current_priority=0.0,
            candidate_priority=0.5,
            focus_duration=3,  # >= minimum_focus_duration
            ticks_since_last_switch=10,  # >= cooldown_ticks
        )
        assert should is True
        assert "no current focus" in reason

    def test_no_switch_when_duration_not_met(self, policy):
        should, reason = policy.should_switch(
            current_priority=0.8,
            candidate_priority=0.9,
            focus_duration=2,  # < minimum_focus_duration (3)
            ticks_since_last_switch=10,
        )
        assert should is False
        assert "focus_duration" in reason

    def test_no_switch_when_cooldown_active(self, policy):
        should, reason = policy.should_switch(
            current_priority=0.8,
            candidate_priority=0.9,
            focus_duration=5,
            ticks_since_last_switch=3,  # < cooldown_ticks (5)
        )
        assert should is False
        assert "cooldown" in reason

    def test_no_switch_when_ratio_below_threshold(self, policy):
        should, reason = policy.should_switch(
            current_priority=1.0,
            candidate_priority=1.2,  # ratio = 1.2 < 1.3
            focus_duration=5,
            ticks_since_last_switch=10,
        )
        assert should is False
        assert "ratio" in reason

    def test_switch_when_ratio_above_threshold(self, policy):
        should, reason = policy.should_switch(
            current_priority=1.0,
            candidate_priority=1.5,  # ratio = 1.5 >= 1.3
            focus_duration=5,
            ticks_since_last_switch=10,
        )
        assert should is True
        assert "ratio" in reason

    def test_custom_policy(self):
        p = InertiaPolicy(
            minimum_focus_duration=5,
            switch_threshold=2.0,
            cooldown_ticks=10,
        )
        assert p.minimum_focus_duration == 5
        assert p.switch_threshold == 2.0


class TestAttentionTrace:
    def test_defaults(self):
        t = AttentionTrace()
        assert t.tick_id == 0
        assert t.reason == ""
        assert t.trace_id != ""  # auto-generated

    def test_custom(self):
        t = AttentionTrace(
            tick_id=42,
            previous_focus_id="G1",
            new_focus_id="G2",
            reason="interrupt",
            switch_ratio=1.5,
            candidates_evaluated=3,
        )
        assert t.tick_id == 42
        assert t.reason == "interrupt"
        d = t.to_dict()
        assert d["tick_id"] == 42
        assert d["reason"] == "interrupt"


class TestAttentionScoringWeights:
    def test_default_weights_sum_to_one(self):
        w = AttentionScoringWeights()
        total = w.goal_importance + w.urgency + w.context_relevance + w.user_preference
        assert abs(total - 1.0) < 0.001

    def test_invalid_weights_rejected(self):
        with pytest.raises(ValueError, match="Weights must sum to 1.0"):
            AttentionScoringWeights(
                goal_importance=0.5,
                urgency=0.5,
                context_relevance=0.5,
                user_preference=0.5,
            )

    def test_custom_valid_weights(self):
        w = AttentionScoringWeights(
            goal_importance=0.4,
            urgency=0.3,
            context_relevance=0.2,
            user_preference=0.1,
        )
        assert w.goal_importance == 0.4
        total = w.goal_importance + w.urgency + w.context_relevance + w.user_preference
        assert abs(total - 1.0) < 0.001


class TestFocusSelectionResult:
    def test_defaults(self):
        r = FocusSelectionResult(tick_id=1)
        assert r.selected_candidate is None
        assert r.switched is False
        assert r.candidates_evaluated == 0

    def test_with_switch(self):
        from ocos.attention.attention_types import AttentionState, AttentionCandidate
        c = AttentionCandidate(candidate_id="G1", candidate_type=FocusType.GOAL)
        s = AttentionState(focus_id="G1", focus_type=FocusType.GOAL)
        r = FocusSelectionResult(
            tick_id=10,
            selected_candidate=c,
            new_state=s,
            switched=True,
            switch_reason="high priority",
            candidates_evaluated=3,
        )
        assert r.switched is True
        assert r.switch_reason == "high priority"
        assert r.candidates_evaluated == 3
