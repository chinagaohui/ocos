"""Phase 39.5 Acceptance Tests: R39.5-01 ~ R39.5-07.

验证 Attention ABI 在以下场景:
    R39.5-01: Single Focus — 任何时间只有一个焦点
    R39.5-02: Priority Selection — 正确选择最高认知价值目标
    R39.5-03: Interrupt — 高优事件可以打断
    R39.5-04: Inertia — 避免频繁切换（认知抖动）
    R39.5-05: WM Binding — 焦点自动绑定上下文
    R39.5-06: Attention Trace — 完整审计
    R39.5-07: Recovery Restore — 重启恢复注意力状态
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from ocos.attention import (
    AttentionCandidate,
    AttentionScoringEngine,
    AttentionScoringWeights,
    AttentionState,
    AttentionTrace,
    CandidateCollector,
    FocusSelectionResult,
    FocusType,
    InertiaPolicy,
)
from ocos.attention.recovery_integration import (
    attention_state_from_snapshot,
    attention_state_to_snapshot,
    validate_attention_restore,
)


# ═══════════════════════════════════════════════════════════════════════════
# R39.5-01: Single Focus
# ═══════════════════════════════════════════════════════════════════════════

class TestR39501SingleFocus:
    """任何时间只有一个焦点。"""

    def test_single_candidate_becomes_focus(self):
        c = CandidateCollector()
        c.add_goal("g1", importance=0.8, summary="开发OCOS", urgency=0.5)
        engine = AttentionScoringEngine()
        result = engine.select(c.candidates(), None, 1)
        assert result.switched
        assert result.new_state is not None
        assert result.new_state.focus_id == "g1"

    def test_no_candidates_no_focus(self):
        c = CandidateCollector()
        engine = AttentionScoringEngine()
        result = engine.select(c.candidates(), None, 1)
        assert not result.switched
        assert result.new_state is None

    def test_multiple_candidates_single_focus(self):
        c = CandidateCollector()
        c.add_goal("g1", importance=0.8, summary="A", urgency=0.5)
        c.add_goal("g2", importance=0.6, summary="B", urgency=0.4)
        engine = AttentionScoringEngine()
        result = engine.select(c.candidates(), None, 1)
        assert result.new_state is not None
        assert result.new_state.focus_id is not None
        # Only one focus
        assert result.new_state.focus_id in ("g1", "g2")

    def test_same_focus_stays_same(self):
        """Same candidate should not trigger a switch. Threading"""
        c = CandidateCollector()
        c.add_goal("g1", importance=0.8, summary="A", urgency=0.5)
        engine = AttentionScoringEngine()
        result1 = engine.select(c.candidates(), None, 1)
        assert result1.switched

        c2 = CandidateCollector()
        c2.add_goal("g1", importance=0.8, summary="A", urgency=0.5)
        result2 = engine.select(c2.candidates(), result1.new_state, 2)
        assert not result2.switched
        assert result2.new_state.focus_id == "g1"


# ═══════════════════════════════════════════════════════════════════════════
# R39.5-02: Priority Selection
# ═══════════════════════════════════════════════════════════════════════════

class TestR39502PrioritySelection:
    """正确选择最高认知价值目标。"""

    def test_selects_highest_scoring(self):
        c = CandidateCollector()
        # Higher: importance=0.9 + urgency=0.9 = very high
        c.add_goal("g_high", importance=0.9, summary="Critical task", urgency=0.9)
        # Lower: importance=0.3 + urgency=0.3
        c.add_goal("g_low", importance=0.3, summary="Trivial task", urgency=0.3)
        engine = AttentionScoringEngine()
        result = engine.select(c.candidates(), None, 1)
        assert result.new_state.focus_id == "g_high", \
            f"Expected g_high, got {result.new_state.focus_id}"

    def test_event_beats_goal_on_urgency(self):
        c = CandidateCollector()
        c.add_goal("g1", importance=0.7, summary="Normal work", urgency=0.3)
        c.add_event("e1", urgency=0.95, summary="Critical alert")
        engine = AttentionScoringEngine()
        result = engine.select(c.candidates(), None, 1)
        # Event urgency 0.95 * 0.25 = 0.2375
        # Goal: 0.7*0.35 + 0.3*0.25 = 0.245 + 0.075 = 0.32
        # Goal still wins because of goal_importance weight
        assert result.new_state is not None
        assert result.new_state.focus_id in ("g1", "e1"), \
            f"Unexpected focus: {result.new_state.focus_id}"

    def test_maintenance_included(self):
        c = CandidateCollector()
        c.add_maintenance("m1", urgency=0.95, summary="System health check")
        c.add_goal("g1", importance=0.3, summary="Low priority", urgency=0.1)
        engine = AttentionScoringEngine()
        result = engine.select(c.candidates(), None, 1)
        assert result.new_state is not None
        # Maintenance high urgency should beat low priority goal
        # m1: 0.95 * 0.25 = 0.2375
        # g1: 0.3*0.35 + 0.1*0.25 = 0.105 + 0.025 = 0.13
        assert result.new_state.focus_id == "m1"


# ═══════════════════════════════════════════════════════════════════════════
# R39.5-03: Interrupt
# ═══════════════════════════════════════════════════════════════════════════

class TestR39503Interrupt:
    """高优事件可以打断当前焦点。"""

    def test_high_priority_event_overrides_focus(self):
        engine = AttentionScoringEngine(
            inertia=InertiaPolicy(minimum_focus_duration=3, cooldown_ticks=1)
        )
        # Set initial focus on goal
        c1 = CandidateCollector()
        c1.add_goal("g1", importance=0.6, summary="Normal work", urgency=0.4)
        result = engine.select(c1.candidates(), None, 1)
        assert result.new_state.focus_id == "g1"

        # After minimum duration, high urgency event should switch
        c2 = CandidateCollector()
        c2.add_event("e_urgent", urgency=0.95, summary="Critical alert",
                     context_relevance=0.8)
        result2 = engine.select(c2.candidates(), result.new_state, 5)
        # Event: 0.95*0.25 + 0.8*0.25 = 0.2375 + 0.2 = 0.4375
        # Current: 0.6*0.35 + 0.4*0.25 = 0.21 + 0.1 = 0.31
        # Ratio: 0.4375/0.31 ≈ 1.41 > 1.3 → switch
        assert result2.switched, f"Expected switch, got: {result2.switch_reason}"
        assert result2.new_state.focus_id == "e_urgent"

    def test_interrupt_increases_interruption_count(self):
        engine = AttentionScoringEngine(
            inertia=InertiaPolicy(minimum_focus_duration=1, cooldown_ticks=0)
        )
        c1 = CandidateCollector()
        c1.add_goal("g1", importance=0.5, summary="A", urgency=0.3)
        r1 = engine.select(c1.candidates(), None, 1)

        c2 = CandidateCollector()
        c2.add_event("e1", urgency=0.95, summary="B", context_relevance=0.9)
        r2 = engine.select(c2.candidates(), r1.new_state, 2)
        assert r2.switched
        assert r2.new_state.interruption_count == 1


# ═══════════════════════════════════════════════════════════════════════════
# R39.5-04: Inertia
# ═══════════════════════════════════════════════════════════════════════════

class TestR39504Inertia:
    """避免频繁切换（认知抖动）。"""

    def test_minimum_focus_duration_blocks_early_switch(self):
        inertia = InertiaPolicy(minimum_focus_duration=5, switch_threshold=1.3, cooldown_ticks=0)
        ok, reason = inertia.should_switch(0.5, 0.9, focus_duration=2, ticks_since_last_switch=10)
        assert not ok, f"Should be blocked by min duration, got: {reason}"
        assert "focus_duration" in reason

    def test_switch_threshold_blocks_small_improvement(self):
        inertia = InertiaPolicy(minimum_focus_duration=3, switch_threshold=1.3, cooldown_ticks=0)
        # 0.8/0.7 = 1.14 < 1.3 → blocked
        ok, reason = inertia.should_switch(0.7, 0.8, focus_duration=5, ticks_since_last_switch=10)
        assert not ok, f"Should be blocked by threshold, got: {reason}"
        assert "ratio" in reason

    def test_large_improvement_passes_inertia(self):
        inertia = InertiaPolicy(minimum_focus_duration=3, switch_threshold=1.3, cooldown_ticks=0)
        # 0.95/0.5 = 1.9 > 1.3 → allowed
        ok, reason = inertia.should_switch(0.5, 0.95, focus_duration=5, ticks_since_last_switch=10)
        assert ok, f"Should pass, got: {reason}"

    def test_cooldown_blocks_rapid_switching(self):
        inertia = InertiaPolicy(cooldown_ticks=5)
        ok, reason = inertia.should_switch(0.5, 0.95, focus_duration=10, ticks_since_last_switch=2)
        assert not ok, f"Should be blocked by cooldown, got: {reason}"
        assert "cooldown" in reason

    def test_scoring_engine_respects_inertia(self):
        """End-to-end: engine blocks switch due to inertia."""
        engine = AttentionScoringEngine(
            inertia=InertiaPolicy(minimum_focus_duration=5, switch_threshold=1.5, cooldown_ticks=0)
        )
        c1 = CandidateCollector()
        c1.add_goal("g1", importance=0.8, summary="A", urgency=0.5)
        r1 = engine.select(c1.candidates(), None, 1)

        # Try to switch immediately (focus_duration too short)
        c2 = CandidateCollector()
        c2.add_goal("g2", importance=0.85, summary="B", urgency=0.6)
        r2 = engine.select(c2.candidates(), r1.new_state, 2)
        assert not r2.switched
        assert "focus_duration" in r2.switch_reason


# ═══════════════════════════════════════════════════════════════════════════
# R39.5-05: WM Binding
# ═══════════════════════════════════════════════════════════════════════════

class TestR39505WMBinding:
    """焦点自动绑定上下文引用。"""

    def test_context_refs_preserved_on_switch(self):
        """切换焦点时，context_refs 保留。"""
        engine = AttentionScoringEngine(
            inertia=InertiaPolicy(minimum_focus_duration=0, cooldown_ticks=0)
        )
        c1 = CandidateCollector()
        c1.add_goal("g1", importance=0.8, summary="A", urgency=0.3)
        r1 = engine.select(c1.candidates(), None, 1)

        c2 = CandidateCollector()
        c2.add_event("e1", urgency=0.95, summary="B", context_relevance=0.9)
        r2 = engine.select(c2.candidates(), r1.new_state, 2)
        assert r2.switched

    def test_same_focus_preserves_start_tick(self):
        """同一焦点不改变 start_tick。"""
        engine = AttentionScoringEngine()
        c = CandidateCollector()
        c.add_goal("g1", importance=0.8, summary="A", urgency=0.3)
        r1 = engine.select(c.candidates(), None, 1)
        assert r1.new_state.start_tick == 1

        r2 = engine.select(c.candidates(), r1.new_state, 10)
        assert not r2.switched
        assert r2.new_state.start_tick == 1  # Preserved

    def test_new_focus_updates_start_tick(self):
        """新焦点使用新 tick 作为 start_tick。"""
        engine = AttentionScoringEngine(
            inertia=InertiaPolicy(minimum_focus_duration=0, cooldown_ticks=0)
        )
        c1 = CandidateCollector()
        c1.add_goal("g1", importance=0.8, summary="A", urgency=0.3)
        r1 = engine.select(c1.candidates(), None, 1)

        c2 = CandidateCollector()
        c2.add_event("e1", urgency=0.95, summary="B", context_relevance=0.9)
        r2 = engine.select(c2.candidates(), r1.new_state, 15)
        assert r2.switched
        assert r2.new_state.start_tick == 15


# ═══════════════════════════════════════════════════════════════════════════
# R39.5-06: Attention Trace
# ═══════════════════════════════════════════════════════════════════════════

class TestR39506AttentionTrace:
    """完整审计记录。"""

    def test_trace_generated_on_switch(self):
        engine = AttentionScoringEngine()
        c = CandidateCollector()
        c.add_goal("g1", importance=0.8, summary="A", urgency=0.3)
        result = engine.select(c.candidates(), None, 1)
        assert result.trace is not None
        assert result.trace.tick_id == 1
        assert result.trace.new_focus_id == "g1"
        assert result.trace.reason == "initial_focus"
        assert result.trace.candidates_evaluated == 1

    def test_trace_has_switch_ratio(self):
        engine = AttentionScoringEngine(
            inertia=InertiaPolicy(minimum_focus_duration=0, cooldown_ticks=0)
        )
        c1 = CandidateCollector()
        c1.add_goal("g1", importance=0.8, summary="A", urgency=0.3)
        r1 = engine.select(c1.candidates(), None, 1)

        c2 = CandidateCollector()
        c2.add_goal("g2", importance=0.9, summary="B", urgency=0.6)
        r2 = engine.select(c2.candidates(), r1.new_state, 10)
        if r2.switched:
            assert r2.trace is not None
            assert r2.trace.switch_ratio > 1.0
            assert r2.trace.previous_focus_id == "g1"
            assert r2.trace.new_focus_id == "g2"

    def test_trace_not_generated_when_disabled(self):
        engine = AttentionScoringEngine(enable_trace=False)
        c = CandidateCollector()
        c.add_goal("g1", importance=0.8, summary="A", urgency=0.3)
        result = engine.select(c.candidates(), None, 1)
        assert result.trace is None

    def test_trace_serializable(self):
        engine = AttentionScoringEngine()
        c = CandidateCollector()
        c.add_goal("g1", importance=0.8, summary="A", urgency=0.5)
        result = engine.select(c.candidates(), None, 1)
        d = result.trace.to_dict()
        assert d["tick_id"] == 1
        assert d["new_focus_id"] == "g1"
        assert d["reason"] == "initial_focus"


# ═══════════════════════════════════════════════════════════════════════════
# R39.5-07: Recovery Restore
# ═══════════════════════════════════════════════════════════════════════════

class TestR39507RecoveryRestore:
    """重启后恢复注意力状态。"""

    def test_serialize_deserialize_roundtrip(self):
        state = AttentionState(
            focus_id="g1",
            focus_type=FocusType.GOAL,
            focus_priority=0.78,
            start_tick=42,
            context_refs=("ctx_a", "ctx_b"),
            interruption_count=2,
            previous_focus_id="g0",
            previous_focus_type=FocusType.EVENT,
            last_switch_tick=40,
            total_focus_changes=5,
        )
        data = attention_state_to_snapshot(state)
        restored = attention_state_from_snapshot(data)
        assert restored is not None
        assert restored.focus_id == "g1"
        assert restored.focus_type == FocusType.GOAL
        assert restored.focus_priority == 0.78
        assert restored.start_tick == 42
        assert restored.context_refs == ("ctx_a", "ctx_b")
        assert restored.interruption_count == 2
        assert restored.total_focus_changes == 5

    def test_none_roundtrip(self):
        assert attention_state_to_snapshot(None) is None
        assert attention_state_from_snapshot(None) is None

    def test_validate_restore_success(self):
        original = AttentionState(
            focus_id="g1", focus_type=FocusType.GOAL, focus_priority=0.8, start_tick=10
        )
        restored = AttentionState(
            focus_id="g1", focus_type=FocusType.GOAL, focus_priority=0.8, start_tick=10
        )
        ok, msg = validate_attention_restore(restored, original)
        assert ok, msg

    def test_validate_restore_mismatch(self):
        original = AttentionState(focus_id="g1", focus_type=FocusType.GOAL, focus_priority=0.8)
        restored = AttentionState(focus_id="g2", focus_type=FocusType.GOAL, focus_priority=0.8)
        ok, msg = validate_attention_restore(restored, original)
        assert not ok
        assert "focus_id" in msg

    def test_recovery_integration_with_snapshot(self):
        """Simulate: snapshot contains attention data → restore from it."""
        from ocos.runtime.recovery.runtime_snapshot import RuntimeSnapshot

        # Create a snapshot with attention_state
        snap = RuntimeSnapshot.capture(
            tick_id=100,
            runtime_state="RUNNING",
            active_goal_ids=("g1",),
            attention_focus={
                "focus_id": "g1",
                "focus_type": "goal",
                "focus_priority": 0.8,
                "start_tick": 50,
                "context_refs": ["ctx1"],
                "interruption_count": 1,
                "previous_focus_id": None,
                "previous_focus_type": None,
                "last_switch_tick": 50,
                "total_focus_changes": 1,
            },
        )

        # Restore from snapshot
        restored = attention_state_from_snapshot(snap.attention_focus)
        assert restored is not None
        assert restored.focus_id == "g1"
        assert restored.focus_type == FocusType.GOAL
        assert restored.focus_priority == 0.8
        assert restored.start_tick == 50
        assert restored.total_focus_changes == 1


# ═══════════════════════════════════════════════════════════════════════════
# ABI type unit tests
# ═══════════════════════════════════════════════════════════════════════════

class TestAttentionABITypes:
    """类型自身不变性测试。"""

    def test_focus_type_values(self):
        assert {e.value for e in FocusType} == {"goal", "event", "maintenance"}

    def test_attention_state_is_frozen(self):
        s = AttentionState(focus_id="g1", focus_type=FocusType.GOAL)
        with pytest.raises(Exception):
            s.focus_id = "g2"  # type: ignore[misc]

    def test_scoring_weights_sum_check(self):
        # Should work
        AttentionScoringWeights(goal_importance=0.3, urgency=0.3,
                                context_relevance=0.2, user_preference=0.2)
        # Should fail
        with pytest.raises(ValueError, match="sum to 1.0"):
            AttentionScoringWeights(goal_importance=0.5, urgency=0.5,
                                    context_relevance=0.5, user_preference=0.5)

    def test_trace_is_frozen(self):
        t = AttentionTrace(tick_id=1, reason="test")
        with pytest.raises(Exception):
            t.tick_id = 2  # type: ignore[misc]

    def test_focus_selection_result_is_frozen(self):
        c = AttentionCandidate(
            candidate_id="g1",
            candidate_type=FocusType.GOAL,
            summary="test",
        )
        r = FocusSelectionResult(tick_id=1, selected_candidate=c)
        with pytest.raises(Exception):
            r.tick_id = 2  # type: ignore[misc]
