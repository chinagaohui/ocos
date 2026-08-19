"""Phase 30 集成测试: Attention Model。

覆盖:
  30a1: shift_focus() — 切换焦点、拒绝低位切换
  30a2: release_focus() — 释放焦点 → IDLE
  30a3: enqueue/dequeue — 优先级排序队列
  30a4: queue overflow — 队列满时保留高优先级
  30a5: tick/fatigue — 疲劳积累与衰减
  30a6: auto_mode — 疲劳触发模式降级
  30b1: calculate_priority — urgency_boost × relevance
  30b2: mode transitions — FOCUSED → SCANNING → IDLE
  30b3: lifecycle mode mapping — WAKE/THINK/SLEEP/...
  30b4: snapshot — 完整状态快照
  30b5: history — 切换记录保存
  30b6: force shift — force=True 跳过成本检查
"""
import pytest

from ocos.capability.attention import (
    AttentionManager,
    AttentionMode,
    AttentionSnapshot,
    FocusTarget,
    QueueItem,
    TargetType,
)


# ── 30a1: shift_focus ───────────────────────────────────────────────────


class TestShiftFocus:
    def test_shift_to_new_target(self):
        am = AttentionManager()
        target = FocusTarget(TargetType.USER_INPUT, "msg-1", priority=0.9)
        ok = am.shift_focus(target)
        assert ok
        assert am.focus is not None
        assert am.focus.target_id == "msg-1"
        assert am.focus.target_type == TargetType.USER_INPUT

    def test_shift_count_increments(self):
        am = AttentionManager()
        am.shift_focus(FocusTarget(TargetType.USER_INPUT, "a", priority=0.9))
        assert am.switch_count == 1
        am.shift_focus(FocusTarget(TargetType.GOAL, "b", priority=0.9))
        assert am.switch_count == 2

    def test_shift_saves_history(self):
        am = AttentionManager()
        am.shift_focus(FocusTarget(TargetType.USER_INPUT, "first", priority=0.9))
        am.shift_focus(FocusTarget(TargetType.GOAL, "second", priority=0.9))
        assert len(am.history) == 1
        assert am.history[0]["target_id"] == "first"
        assert am.history[0]["reason"] == "switched"

    def test_force_shift_bypasses_cost(self):
        am = AttentionManager()
        # Focus on user input (high importance to interrupt)
        am.shift_focus(FocusTarget(TargetType.USER_INPUT, "important"))
        # Try to shift to low-priority timed event — should be rejected normally
        low = FocusTarget(TargetType.TIMED_EVENT, "background", priority=0.1)
        ok = am.shift_focus(low)
        assert not ok  # rejected: cost (interrupt USER_INPUT = 0.5) > benefit (0.1)
        assert am.focus.target_id == "important"  # unchanged

        # force bypasses
        ok = am.shift_focus(low, force=True)
        assert ok
        assert am.focus.target_id == "background"

    def test_shift_fatigue_cost(self):
        am = AttentionManager()
        am.shift_focus(FocusTarget(TargetType.USER_INPUT, "a", priority=0.9))
        pre_fatigue = am.fatigue
        am.shift_focus(FocusTarget(TargetType.GOAL, "b", priority=0.9))
        assert am.fatigue > pre_fatigue  # +0.02 switch cost


# ── 30a2: release_focus ────────────────────────────────────────────────


class TestReleaseFocus:
    def test_release_returns_old(self):
        am = AttentionManager()
        am.shift_focus(FocusTarget(TargetType.USER_INPUT, "x"))
        old = am.release_focus()
        assert old is not None
        assert old.target_id == "x"
        assert am.focus is None

    def test_release_sets_idle(self):
        am = AttentionManager()
        am.shift_focus(FocusTarget(TargetType.USER_INPUT, "x"))
        am.release_focus()
        assert am.mode == AttentionMode.IDLE

    def test_release_none_when_no_focus(self):
        am = AttentionManager()
        assert am.release_focus() is None


# ── 30a3: enqueue/dequeue ──────────────────────────────────────────────


class TestQueue:
    def test_enqueue_single(self):
        am = AttentionManager()
        item = QueueItem(item_id="q1", priority=0.5, urgency=1.0)
        ok = am.enqueue(item)
        assert ok
        assert am.queue_size == 1

    def test_dequeue_best_priority(self):
        am = AttentionManager()
        am.enqueue(QueueItem(item_id="low", priority=0.2, urgency=1.0))
        am.enqueue(QueueItem(item_id="high", priority=0.9, urgency=1.0))
        am.enqueue(QueueItem(item_id="mid", priority=0.5, urgency=1.0))
        best = am.dequeue_best()
        assert best.item_id == "high"
        assert am.queue_size == 2

    def test_dequeue_empty(self):
        am = AttentionManager()
        assert am.dequeue_best() is None

    def test_clear_queue(self):
        am = AttentionManager()
        am.enqueue(QueueItem(item_id="a"))
        am.enqueue(QueueItem(item_id="b"))
        am.clear_queue()
        assert am.queue_size == 0

    def test_final_priority_with_urgency(self):
        item = QueueItem(item_id="x", priority=0.5, urgency=2.0)
        assert item.final_priority == 1.0  # 0.5 * 2.0


# ── 30a4: queue overflow ───────────────────────────────────────────────


class TestQueueOverflow:
    def test_queue_max_capacity(self):
        am = AttentionManager()
        for i in range(am.MAX_QUEUE_SIZE):
            am.enqueue(QueueItem(item_id=f"q{i}", priority=float(i) / 20))
        assert am.queue_size == am.MAX_QUEUE_SIZE

    def test_reject_low_priority_overflow(self):
        am = AttentionManager()
        # Fill with medium priority
        for i in range(am.MAX_QUEUE_SIZE):
            am.enqueue(QueueItem(item_id=f"q{i}", priority=0.3, urgency=1.0))
        # Try to add very low priority
        low = QueueItem(item_id="lowest", priority=0.1, urgency=1.0)
        ok = am.enqueue(low)
        assert not ok
        assert am.queue_size == am.MAX_QUEUE_SIZE

    def test_replace_lowest_on_high_priority_overflow(self):
        am = AttentionManager()
        for i in range(am.MAX_QUEUE_SIZE):
            am.enqueue(QueueItem(item_id=f"q{i}", priority=0.3, urgency=1.0))
        high = QueueItem(item_id="urgent", priority=0.9, urgency=2.0)
        ok = am.enqueue(high)
        assert ok
        assert am.queue_size == am.MAX_QUEUE_SIZE  # still 10
        ids = [q.item_id for q in am._queue]
        assert "urgent" in ids


# ── 30a5: fatigue ──────────────────────────────────────────────────────


class TestFatigue:
    def test_fatigue_starts_zero(self):
        am = AttentionManager()
        assert am.fatigue == 0.0

    def test_fatigue_accumulates_focused(self):
        am = AttentionManager()
        am.set_mode(AttentionMode.FOCUSED)
        am.tick(seconds=60)
        # FOCUSED: +0.02/min
        assert 0.015 < am.fatigue < 0.025

    def test_fatigue_recovers_idle(self):
        am = AttentionManager()
        am._fatigue = 0.5
        am.set_mode(AttentionMode.IDLE)
        am.tick(seconds=60)
        # IDLE: -0.05/min → 0.45
        assert 0.44 < am.fatigue < 0.46

    def test_fatigue_clamped_0_1(self):
        am = AttentionManager()
        am._fatigue = -10
        am.tick(seconds=1)
        assert am.fatigue == 0.0
        am._fatigue = 999
        am.tick(seconds=1)
        assert am.fatigue == 1.0

    def test_reset_fatigue(self):
        am = AttentionManager()
        am._fatigue = 0.8
        am.reset_fatigue()
        assert am.fatigue == 0.0


# ── 30a6: auto mode ────────────────────────────────────────────────────


class TestAutoMode:
    def test_auto_mode_idle_when_extreme_fatigue(self):
        am = AttentionManager()
        am.set_mode(AttentionMode.FOCUSED)
        am._fatigue = 0.95  # > 0.9
        new_mode = am.auto_mode()
        assert new_mode == AttentionMode.IDLE

    def test_auto_mode_scanning_when_critical_fatigue(self):
        am = AttentionManager()
        am.set_mode(AttentionMode.FOCUSED)
        am._fatigue = 0.75  # > 0.7
        new_mode = am.auto_mode()
        assert new_mode == AttentionMode.SCANNING

    def test_auto_mode_no_change_when_low_fatigue(self):
        am = AttentionManager()
        am.set_mode(AttentionMode.FOCUSED)
        am._fatigue = 0.3
        new_mode = am.auto_mode()
        assert new_mode == AttentionMode.FOCUSED


# ── 30b1: calculate_priority ───────────────────────────────────────────


class TestCalculatePriority:
    def test_base_only(self):
        am = AttentionManager()
        target = FocusTarget(TargetType.USER_INPUT, "x")
        p = am.calculate_priority(target, urgency_boost=1.0, relevance=1.0)
        assert p == 1.0  # USER_INPUT base = 1.0

    def test_with_urgency(self):
        am = AttentionManager()
        target = FocusTarget(TargetType.GOAL, "y")
        p = am.calculate_priority(target, urgency_boost=1.5, relevance=1.0)
        assert p == 1.0  # 0.7 * 1.5 * 1.0 = 1.05 → clamped to 1.0

    def test_with_relevance(self):
        am = AttentionManager()
        target = FocusTarget(TargetType.EVENT, "z")  # base 0.5
        p = am.calculate_priority(target, urgency_boost=1.0, relevance=0.5)
        assert p == 0.25  # 0.5 * 1.0 * 0.5

    def test_clamped_to_1(self):
        am = AttentionManager()
        target = FocusTarget(TargetType.USER_INPUT, "x")
        p = am.calculate_priority(target, urgency_boost=1.5, relevance=1.0)
        assert p <= 1.0


# ── 30b2: mode transitions ─────────────────────────────────────────────


class TestModeTransitions:
    def test_initial_idle(self):
        am = AttentionManager()
        assert am.mode == AttentionMode.IDLE

    def test_shift_auto_scanning(self):
        am = AttentionManager()
        am.shift_focus(FocusTarget(TargetType.USER_INPUT, "x"))
        assert am.mode == AttentionMode.SCANNING

    def test_set_mode_manual(self):
        am = AttentionManager()
        am.set_mode(AttentionMode.FOCUSED)
        assert am.mode == AttentionMode.FOCUSED
        am.set_mode(AttentionMode.DISTRIBUTED)
        assert am.mode == AttentionMode.DISTRIBUTED


# ── 30b3: lifecycle mapping ────────────────────────────────────────────


class TestLifecycleMapping:
    def test_wake_to_scanning(self):
        am = AttentionManager()
        am.set_mode_for_lifecycle("WAKE")
        assert am.mode == AttentionMode.SCANNING

    def test_think_to_focused(self):
        am = AttentionManager()
        am.set_mode_for_lifecycle("THINK")
        assert am.mode == AttentionMode.FOCUSED

    def test_sleep_to_idle(self):
        am = AttentionManager()
        am.shift_focus(FocusTarget(TargetType.GOAL, "x"))
        am.set_mode_for_lifecycle("SLEEP")
        assert am.mode == AttentionMode.IDLE
        assert am.focus is None  # focus released

    def test_unknown_stage_default(self):
        am = AttentionManager()
        am.set_mode_for_lifecycle("BOGUS_STAGE")
        # mode unchanged from default
        assert am.mode == AttentionMode.IDLE


# ── 30b4: snapshot ─────────────────────────────────────────────────────


class TestSnapshot:
    def test_default_snapshot(self):
        am = AttentionManager()
        snap = am.snapshot()
        assert isinstance(snap, AttentionSnapshot)
        assert snap.mode == AttentionMode.IDLE
        assert snap.focus is None
        assert snap.fatigue == 0.0
        assert snap.switch_count == 0

    def test_active_snapshot(self):
        am = AttentionManager()
        am.shift_focus(FocusTarget(TargetType.USER_INPUT, "x"))
        am.enqueue(QueueItem(item_id="q", priority=0.9))
        snap = am.snapshot()
        assert snap.focus is not None
        assert snap.focus.target_id == "x"
        assert snap.queue_length == 1
        assert snap.top_queue_item is not None


# ── 30b5: history ──────────────────────────────────────────────────────


class TestHistory:
    def test_history_records(self):
        am = AttentionManager()
        am.shift_focus(FocusTarget(TargetType.USER_INPUT, "a", priority=0.9))
        am.shift_focus(FocusTarget(TargetType.GOAL, "b", priority=0.9))
        am.shift_focus(FocusTarget(TargetType.REFLECTION, "c", priority=0.9))
        assert len(am.history) == 2
        assert am.history[0]["reason"] == "switched"
        assert am.history[1]["reason"] == "switched"

    def test_max_history(self):
        am = AttentionManager()
        for i in range(60):
            am.shift_focus(FocusTarget(TargetType.USER_INPUT, str(i)), force=True)
        assert len(am.history) <= am.MAX_HISTORY


# ── 30b6: TargetType base_priority ─────────────────────────────────────


class TestTargetTypePriorities:
    def test_user_input_is_1(self):
        target = FocusTarget(TargetType.USER_INPUT, "x")
        assert target.base_priority == 1.0

    def test_anomaly_is_high(self):
        target = FocusTarget(TargetType.ANOMALY, "x")
        assert target.base_priority == 0.9

    def test_timed_event_is_low(self):
        target = FocusTarget(TargetType.TIMED_EVENT, "x")
        assert target.base_priority == 0.4

    def test_focus_duration(self):
        target = FocusTarget(TargetType.USER_INPUT, "x")
        assert target.duration_seconds >= 0
