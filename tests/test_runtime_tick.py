"""OCOS runtime tick 确定性测试。

Tick 是 OCOS 最小时间单元，必须满足：
1. 单调递增 ID
2. frozen dataclass（不可变）
3. tick_id >= 1 约束
4. TickContext 不可变流水线语义
"""

import time
from datetime import datetime, timezone

import pytest

from ocos.runtime.tick import Tick, tick_id_generator
from ocos.runtime.tick_context import TickContext, create_tick_context


class TestTickImmutable:
    """Tick 是不可变数据帧。"""

    def test_create_tick(self):
        tick = Tick(tick_id=1, state="RUNNING")
        assert tick.tick_id == 1
        assert tick.state == "RUNNING"
        assert tick.checkpoint_id is None
        assert isinstance(tick.timestamp, datetime)

    def test_tick_is_frozen(self):
        tick = Tick(tick_id=1)
        with pytest.raises((TypeError, AttributeError)):
            tick.tick_id = 2  # frozen dataclass 禁止修改

    def test_tick_id_must_be_positive(self):
        with pytest.raises(ValueError, match="tick_id must be >= 1"):
            Tick(tick_id=0)
        with pytest.raises(ValueError, match="tick_id must be >= 1"):
            Tick(tick_id=-1)

    def test_tick_id_one_allowed(self):
        tick = Tick(tick_id=1)
        assert tick.tick_id == 1

    def test_ticks_with_same_fields_are_equal(self):
        """相同字段值（含显式 timestamp）的 tick 相等。"""
        ts = datetime(2026, 1, 1, tzinfo=timezone.utc)
        t1 = Tick(tick_id=1, timestamp=ts, state="RUNNING", checkpoint_id=None)
        t2 = Tick(tick_id=1, timestamp=ts, state="RUNNING", checkpoint_id=None)
        assert t1 == t2

    def test_ticks_differ_by_state_not_equal(self):
        t1 = Tick(tick_id=1, state="RUNNING")
        t2 = Tick(tick_id=1, state="SUSPENDED")
        assert t1 != t2


class TestTickContextImmutable:
    """TickContext 是不可变流水线载体。"""

    def test_create_context(self):
        ctx = create_tick_context(tick_id=1, runtime_state="RUNNING")
        assert ctx.tick_id == 1
        assert ctx.runtime_state == "RUNNING"
        assert ctx.events == ()
        assert ctx.started_at > 0

    def test_context_is_frozen(self):
        ctx = create_tick_context(tick_id=1, runtime_state="RUNNING")
        with pytest.raises((TypeError, AttributeError)):
            ctx.tick_id = 2

    def test_with_updates_returns_new_instance(self):
        ctx = create_tick_context(tick_id=1, runtime_state="RUNNING")
        updated = ctx.with_updates(events=("e1",), memory_changes=("m1",))
        # 原实例不变
        assert ctx.events == ()
        # 新实例包含更新
        assert updated.events == ("e1",)
        assert updated.memory_changes == ("m1",)
        # tick_id 保留
        assert updated.tick_id == 1

    def test_with_stage_trace_appends(self):
        ctx = create_tick_context(tick_id=1, runtime_state="RUNNING")
        ctx2 = ctx.with_stage_trace("PERCEIVE")
        ctx3 = ctx2.with_stage_trace("DECIDE")
        assert ctx.stage_traces == ()
        assert ctx2.stage_traces == ("PERCEIVE",)
        assert ctx3.stage_traces == ("PERCEIVE", "DECIDE")

    def test_to_dict_comprehensive(self):
        ctx = create_tick_context(
            tick_id=5,
            runtime_state="RUNNING",
            started_at=100.0,
        )
        ctx = ctx.with_updates(
            events=("e1", "e2"),
            stage_traces=("PERCEIVE", "DECIDE"),
            checkpoint_decision=True,
        )
        d = ctx.to_dict()
        assert d["tick_id"] == 5
        assert d["runtime_state"] == "RUNNING"
        assert d["events_count"] == 2
        assert d["checkpoint_decision"] is True
        assert d["stage_traces"] == ["PERCEIVE", "DECIDE"]


class TestTickDeterminism:
    """相同 tick_id + 相同 state 产生相同对象。"""

    def test_deterministic_by_fields(self):
        """排除 timestamp 后，tick 由字段值唯一确定。"""
        ts = datetime(2026, 1, 1, tzinfo=timezone.utc)
        t1 = Tick(tick_id=10, timestamp=ts, state="RUNNING", checkpoint_id=None)
        t2 = Tick(tick_id=10, timestamp=ts, state="RUNNING", checkpoint_id=None)
        assert t1 == t2
        assert hash(t1) == hash(t2)

    def test_different_state_different_object(self):
        t1 = Tick(tick_id=1, state="RUNNING")
        t2 = Tick(tick_id=1, state="SUSPENDED")
        assert t1 != t2

    def test_tick_counter_monotonic(self):
        gen = tick_id_generator(start=1)
        ids = [next(gen) for _ in range(100)]
        assert ids == list(range(1, 101))
        for i in range(1, len(ids)):
            assert ids[i] > ids[i - 1]


class TestTickContextStages:
    """TickPipeline 各阶段 trace 记录验证。"""

    def test_stage_traces_order_preserved(self):
        ctx = create_tick_context(tick_id=1, runtime_state="RUNNING")
        stages = ("PERCEIVE", "EVALUATE", "DECIDE", "ACT", "LEARN")
        for s in stages:
            ctx = ctx.with_stage_trace(s)
        assert ctx.stage_traces == stages

    def test_checkpoint_decision_flag(self):
        ctx = create_tick_context(tick_id=1, runtime_state="RUNNING")
        assert ctx.checkpoint_decision is False
        ctx2 = ctx.with_updates(checkpoint_decision=True)
        assert ctx2.checkpoint_decision is True

    def test_empty_events_default(self):
        ctx = create_tick_context(tick_id=1, runtime_state="IDLE")
        assert ctx.events == ()
        assert ctx.execution_results == ()
        assert ctx.learning_signals == ()


class TestTickTimestamp:
    """Tick timestamp 字段行为。"""

    def test_timestamp_is_utc(self):
        tick = Tick(tick_id=1)
        assert tick.timestamp.tzinfo is not None
        offset = tick.timestamp.utcoffset()
        assert offset == timezone.utc.utcoffset(datetime.now())

    def test_timestamp_auto_generated(self):
        """不传 timestamp 时自动生成。"""
        before = time.time()
        tick = Tick(tick_id=1)
        after = time.time()
        ts = tick.timestamp.timestamp()
        assert before <= ts <= after
