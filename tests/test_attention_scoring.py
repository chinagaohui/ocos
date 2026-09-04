"""OCOS attention scoring engine 测试。"""

import pytest
from ocos.attention.scoring import AttentionScoringEngine
from ocos.attention.attention_types import (
    AttentionCandidate,
    AttentionScoringWeights,
    AttentionState,
    InertiaPolicy,
    FocusType,
)


class TestAttentionScoringEngine:
    @pytest.fixture
    def engine(self):
        return AttentionScoringEngine()

    def test_score_single(self, engine):
        candidate = AttentionCandidate(
            candidate_id="c1",
            candidate_type=FocusType.GOAL,
            goal_importance=0.8,
            urgency=0.7,
            context_relevance=0.9,
            user_preference=0.6,
        )
        score = engine.score(candidate)
        assert 0.0 <= score <= 1.0
        assert score > 0.0

    def test_score_clamped_to_zero(self, engine):
        candidate = AttentionCandidate(
            candidate_id="c1",
            candidate_type=FocusType.GOAL,
            goal_importance=0.0,
            urgency=0.0,
            context_relevance=0.0,
            user_preference=0.0,
        )
        score = engine.score(candidate)
        assert score >= 0.0

    def test_score_clamped_to_one(self, engine):
        candidate = AttentionCandidate(
            candidate_id="c1",
            candidate_type=FocusType.GOAL,
            goal_importance=1.0,
            urgency=1.0,
            context_relevance=1.0,
            user_preference=1.0,
        )
        score = engine.score(candidate)
        assert score <= 1.0

    def test_score_all(self, engine):
        candidates = [
            AttentionCandidate(
                candidate_id=f"c{i}",
                candidate_type=FocusType.GOAL,
                goal_importance=0.5 + i * 0.1,
                urgency=0.5,
                context_relevance=0.5,
                user_preference=0.5,
            )
            for i in range(3)
        ]
        scored = engine.score_all(candidates)
        assert len(scored) == 3
        # Verify all scores are valid and within bounds
        for _, score in scored:
            assert 0.0 <= score <= 1.0
        # Scores should be different for different candidates
        assert len(set(s[1] for s in scored)) > 1

    def test_select_empty_candidates(self, engine):
        result = engine.select([], current_state=None, current_tick=1)
        assert result.selected_candidate is None
        assert result.switched is False
        assert result.switch_reason == "no candidates"

    def test_select_no_current_focus(self, engine):
        candidate = AttentionCandidate(
            candidate_id="c1",
            candidate_type=FocusType.GOAL,
            goal_importance=0.8,
            urgency=0.5,
            context_relevance=0.5,
            user_preference=0.5,
        )
        result = engine.select([candidate], current_state=None, current_tick=1)
        assert result.switched is True
        assert result.selected_candidate.candidate_id == "c1"
        assert result.new_state is not None
        assert result.new_state.focus_id == "c1"

    def test_select_same_focus_keeps_it(self, engine):
        initial = AttentionState(
            focus_id="c1",
            focus_type=FocusType.GOAL,
            focus_priority=0.8,
            start_tick=0,
        )
        candidate = AttentionCandidate(
            candidate_id="c1",
            candidate_type=FocusType.GOAL,
            goal_importance=0.8,
            urgency=0.5,
            context_relevance=0.5,
            user_preference=0.5,
        )
        result = engine.select([candidate], current_state=initial, current_tick=5)
        assert result.switched is False
        assert result.switch_reason == "same focus"

    def test_select_switch_with_inertia(self, engine):
        initial = AttentionState(
            focus_id="c1",
            focus_type=FocusType.GOAL,
            focus_priority=0.3,
            start_tick=0,
            last_switch_tick=0,
        )
        high_priority = AttentionCandidate(
            candidate_id="c2",
            candidate_type=FocusType.EVENT,
            goal_importance=0.9,
            urgency=0.95,
            context_relevance=0.5,
            user_preference=0.5,
        )
        result = engine.select([high_priority], current_state=initial, current_tick=10)
        assert result.switched is True
        assert result.new_state.focus_id == "c2"

    def test_select_respects_inertia(self, engine):
        inertia = InertiaPolicy(switch_threshold=3.0, minimum_focus_duration=20)
        test_engine = AttentionScoringEngine(inertia=inertia)
        initial = AttentionState(
            focus_id="c1",
            focus_type=FocusType.GOAL,
            focus_priority=0.5,
            start_tick=5,
            last_switch_tick=0,
        )
        # Slightly better candidate - should NOT switch due to inertia
        better = AttentionCandidate(
            candidate_id="c2",
            candidate_type=FocusType.GOAL,
            goal_importance=0.55,
            urgency=0.5,
            context_relevance=0.5,
            user_preference=0.5,
        )
        result = test_engine.select([better], current_state=initial, current_tick=10)
        assert result.switched is False

    def test_trace_enabled(self, engine):
        candidate = AttentionCandidate(
            candidate_id="c1",
            candidate_type=FocusType.GOAL,
            goal_importance=0.8,
            urgency=0.5,
            context_relevance=0.5,
            user_preference=0.5,
        )
        result = engine.select([candidate], current_state=None, current_tick=1)
        assert result.trace is not None

    def test_trace_disabled(self):
        engine = AttentionScoringEngine(enable_trace=False)
        candidate = AttentionCandidate(
            candidate_id="c1",
            candidate_type=FocusType.GOAL,
            goal_importance=0.8,
            urgency=0.5,
            context_relevance=0.5,
            user_preference=0.5,
        )
        result = engine.select([candidate], current_state=None, current_tick=1)
        assert result.trace is None

    def test_custom_weights(self):
        weights = AttentionScoringWeights(
            goal_importance=0.4,
            urgency=0.3,
            context_relevance=0.2,
            user_preference=0.1,
        )
        engine = AttentionScoringEngine(weights=weights)
        candidate = AttentionCandidate(
            candidate_id="c1",
            candidate_type=FocusType.GOAL,
            goal_importance=1.0,
            urgency=0.0,
            context_relevance=0.0,
            user_preference=0.0,
        )
        score = engine.score(candidate)
        assert score > 0.0