"""Phase M: RuntimeLoop 单元测试。"""

import time
from datetime import datetime
from unittest.mock import MagicMock

import pytest

from ocos.runtime.runtime_loop import RuntimeLoop, LoopMetrics, LoopState


class FakeRuntime:
    """模拟 AgentRuntime 用于测试。"""

    def __init__(self, tick_delay: float = 0.001, fail_after: int = 0):
        self.tick_delay = tick_delay
        self.fail_after = fail_after
        self.tick_count = 0
        self._should_fail = False

    def tick(self) -> dict:
        self.tick_count += 1
        if self._should_fail and self.tick_count > self.fail_after:
            raise RuntimeError(f"Simulated failure at tick {self.tick_count}")
        if self.tick_delay > 0:
            time.sleep(self.tick_delay)
        return {"tick": self.tick_count, "status": "ok"}


class TestRuntimeLoopCore:
    """核心功能测试。"""

    def test_create_loop(self):
        runtime = FakeRuntime()
        loop = RuntimeLoop(runtime, interval=0.01, name="test-loop")
        assert loop.state == LoopState.STOPPED
        assert loop.name == "test-loop"

    def test_run_for_ticks(self):
        runtime = FakeRuntime(tick_delay=0.001)
        loop = RuntimeLoop(runtime, interval=0.001, max_ticks=10, name="test-run")

        metrics = loop.run_for(10)

        assert metrics.total_ticks == 10
        assert loop.state == LoopState.STOPPED
        assert metrics.last_tick_id == 10
        assert metrics.uptime_seconds >= 0

    def test_run_zero_ticks(self):
        runtime = FakeRuntime()
        loop = RuntimeLoop(runtime, name="test-zero")
        metrics = loop.run_for(0)
        assert metrics.total_ticks == 0

    def test_run_negative_ticks(self):
        runtime = FakeRuntime()
        loop = RuntimeLoop(runtime, name="test-neg")
        metrics = loop.run_for(-5)
        assert metrics.total_ticks == 0

    def test_hooks(self):
        runtime = FakeRuntime(tick_delay=0.001)
        loop = RuntimeLoop(runtime, interval=0.001, max_ticks=3, name="test-hooks")

        start_called = []
        stop_called = []
        tick_calls = []

        def on_start(l):
            start_called.append(True)

        def on_stop(l):
            stop_called.append(True)

        def on_tick(tid, result):
            tick_calls.append((tid, result))

        loop.on_start(on_start).on_stop(on_stop).on_tick(on_tick)
        loop.run_for(3)

        assert len(start_called) == 1
        assert len(stop_called) == 1
        assert len(tick_calls) == 3
        assert tick_calls[0] == (1, {"tick": 1, "status": "ok"})
        assert tick_calls[2] == (3, {"tick": 3, "status": "ok"})

    def test_error_hook(self):
        runtime = FakeRuntime(tick_delay=0.001, fail_after=1)
        runtime._should_fail = True
        loop = RuntimeLoop(runtime, interval=0.001, max_ticks=3, name="test-error")

        errors = []

        def on_error(tid, exc):
            errors.append((tid, exc))

        loop.on_error(on_error)
        loop.run_for(3)

        assert len(errors) > 0
        assert isinstance(errors[0][1], RuntimeError)

    def test_metrics_tracking(self):
        runtime = FakeRuntime(tick_delay=0.001)
        loop = RuntimeLoop(runtime, interval=0.001, max_ticks=5, name="test-metrics")

        loop.run_for(5)
        metrics = loop.metrics

        assert metrics.total_ticks == 5
        assert metrics.failed_ticks == 0
        assert metrics.last_tick_id == 5
        assert metrics.avg_tick_duration_ms > 0
        assert metrics.ticks_per_second > 0

    def test_failed_tick_metrics(self):
        runtime = FakeRuntime(tick_delay=0.001, fail_after=2)
        runtime._should_fail = True
        loop = RuntimeLoop(runtime, interval=0.001, max_ticks=5, name="test-fail-metrics")

        loop.run_for(5)
        metrics = loop.metrics

        assert metrics.total_ticks == 5
        assert metrics.failed_ticks > 0


class TestLoopMetrics:
    """LoopMetrics 测试。"""

    def test_initial_state(self):
        metrics = LoopMetrics()
        assert metrics.total_ticks == 0
        assert metrics.failed_ticks == 0
        assert metrics.uptime_seconds == 0.0
        assert metrics.ticks_per_second == 0.0

    def test_record_tick(self):
        metrics = LoopMetrics()
        metrics.started_at = time.time() - 1.0

        for i in range(5):
            metrics.record_tick(10.0, i + 1, datetime.now())

        assert metrics.total_ticks == 5
        assert metrics.last_tick_id == 5
        assert metrics.avg_tick_duration_ms == 10.0

    def test_uptime_calculation(self):
        metrics = LoopMetrics()
        metrics.started_at = time.time() - 5.0
        assert metrics.uptime_seconds == pytest.approx(5.0, abs=0.5)

    def test_tps_calculation(self):
        metrics = LoopMetrics()
        metrics.started_at = time.time() - 10.0
        metrics.total_ticks = 100
        assert metrics.ticks_per_second == pytest.approx(10.0, abs=0.5)


class TestRuntimeLoopAsync:
    """异步模式测试。"""

    @pytest.mark.asyncio
    async def test_async_run(self):
        runtime = FakeRuntime(tick_delay=0.001)
        loop = RuntimeLoop(runtime, interval=0.001, max_ticks=5, name="test-async")

        await loop.async_start()
        metrics = await loop.async_run(max_ticks=5)

        assert metrics.total_ticks == 5
        await loop.async_stop()

    @pytest.mark.asyncio
    async def test_async_context(self):
        runtime = FakeRuntime(tick_delay=0.001)
        loop = RuntimeLoop(runtime, interval=0.001, max_ticks=5, name="test-async-ctx")

        async with loop.async_context():
            metrics = await loop.async_run(max_ticks=5)
            assert metrics.total_ticks == 5


class TestFactory:
    """工厂函数测试。"""

    def test_create_runtime_loop(self):
        from ocos.runtime import create_runtime_loop
        
        runtime = FakeRuntime()
        loop = create_runtime_loop(runtime, interval=0.1, name="factory-test")
        
        assert isinstance(loop, RuntimeLoop)
        assert loop.name == "factory-test"
        assert loop._runtime is runtime
