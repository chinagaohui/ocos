"""OCOS time_manager 统一时间源测试。"""

import pytest
import time as _time

from ocos.kernel.time_manager import TimeManager


class TestTimeManager:
    def test_default_timeline(self):
        tm = TimeManager()
        assert tm.timeline_id == "default"

    def test_custom_timeline(self):
        tm = TimeManager(timeline_id="test-line")
        assert tm.timeline_id == "test-line"

    def test_cycle_starts_at_zero(self):
        tm = TimeManager()
        assert tm.cycle == 0

    def test_tick_increments(self):
        tm = TimeManager()
        c1 = tm.tick()
        c2 = tm.tick()
        assert c1 == 1
        assert c2 == 2
        assert tm.cycle == 2

    def test_tick_monotonic(self):
        tm = TimeManager()
        cycles = [tm.tick() for _ in range(10)]
        assert cycles == list(range(1, 11))

    def test_reset_cycle(self):
        tm = TimeManager()
        tm.tick()
        tm.tick()
        assert tm.cycle == 2
        tm.reset_cycle()
        assert tm.cycle == 0

    def test_utc_now_format(self):
        now = TimeManager.utc_now()
        assert "T" in now
        assert now.endswith("+00:00") or now.endswith("Z")

    def test_utc_timestamp_is_float(self):
        ts = TimeManager.utc_timestamp()
        assert isinstance(ts, float)
        assert ts > 0

    def test_uptime_positive(self):
        tm = TimeManager()
        assert tm.uptime_seconds >= 0

    def test_format_timestamp(self):
        fmt = TimeManager.format_timestamp(0.0)
        assert "1970" in fmt

    def test_repr_contains_info(self):
        tm = TimeManager(timeline_id="t1")
        tm.tick()
        r = repr(tm)
        assert "t1" in r
        assert "cycle=1" in r
