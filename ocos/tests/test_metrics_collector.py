"""MetricsCollector 单元测试。"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from ocos.agent.metrics_collector import (
    EngineMetrics,
    MetricsCollector,
)


class TestEngineMetrics:
    """单个引擎指标。"""

    def test_init(self):
        m = EngineMetrics("writer")
        assert m.engine_name == "writer"
        assert m.total_calls == 0

    def test_record_success(self):
        m = EngineMetrics("planner")
        m.record(success=True, latency_ms=150.0)
        assert m.total_calls == 1
        assert m.success_calls == 1
        assert m.failed_calls == 0
        assert round(m.avg_latency_ms, 1) == 150.0
        assert m.max_latency_ms == 150.0

    def test_record_failure(self):
        m = EngineMetrics("writer")
        m.record(success=False, latency_ms=5000.0)
        assert m.total_calls == 1
        assert m.success_calls == 0
        assert m.failed_calls == 1
        assert round(m.success_rate, 3) == 0.0

    def test_record_multiple(self):
        m = EngineMetrics("reasoner")
        m.record(success=True, latency_ms=50.0)
        m.record(success=True, latency_ms=100.0)
        m.record(success=False, latency_ms=200.0)
        assert m.total_calls == 3
        assert m.success_calls == 2
        assert m.failed_calls == 1
        assert round(m.avg_latency_ms, 1) == 116.7  # (50+100+200)/3
        assert m.min_latency_ms == 50.0
        assert m.max_latency_ms == 200.0

    def test_to_dict(self):
        m = EngineMetrics("writer")
        m.record(success=True, latency_ms=100.0)
        d = m.to_dict()
        assert d["engine_name"] == "writer"
        assert d["total_calls"] == 1
        assert d["success_rate"] == 1.0

    def test_reset(self):
        m = EngineMetrics("planner")
        m.record(success=True, latency_ms=50.0)
        m.reset()
        assert m.total_calls == 0
        assert m.min_latency_ms == 0.0
        assert m.max_latency_ms == 0.0


class TestMetricsCollector:
    """聚合收集器。"""

    def test_for_engine_creates(self):
        c = MetricsCollector()
        m = c.for_engine("writer")
        assert isinstance(m, EngineMetrics)
        assert m.engine_name == "writer"

    def test_for_engine_reuses(self):
        c = MetricsCollector()
        m1 = c.for_engine("writer")
        m2 = c.for_engine("writer")
        assert m1 is m2

    def test_measure_context_success(self):
        c = MetricsCollector()
        import time
        with c.measure("writer") as ctx:
            time.sleep(0.001)  # 确保 timer tick
        assert ctx.success is True
        assert ctx.latency_ms > 0
        m = c.for_engine("writer")
        assert m.total_calls == 1
        assert m.success_calls == 1

    def test_measure_context_failure(self):
        c = MetricsCollector()

        class TestError(Exception):
            pass

        with pytest.raises(TestError):
            with c.measure("writer"):
                raise TestError("fail")
        m = c.for_engine("writer")
        assert m.total_calls == 1
        assert m.failed_calls == 1

    def test_snapshot_structure(self):
        c = MetricsCollector()
        import time
        with c.measure("planner"):
            time.sleep(0.001)
        with c.measure("writer"):
            time.sleep(0.001)
        snap = c.snapshot()
        assert snap["engine_count"] == 2
        assert "planner" in snap["engines"]
        assert "writer" in snap["engines"]
        assert snap["total_calls"] == 2
        assert snap["total_failures"] == 0
        assert snap["uptime_seconds"] >= 0

    def test_reset_all(self):
        c = MetricsCollector()
        with c.measure("planner"):
            pass
        c.reset_all()
        snap = c.snapshot()
        assert snap["total_calls"] == 0
        assert len(snap["engines"]) == 1  # 保留注册

    def test_runs_in_parallel(self):
        """验证线程安全（生产环境可能多线程）。"""
        import threading

        c = MetricsCollector()
        n_threads = 10
        calls_per_thread = 100

        def worker():
            for _ in range(calls_per_thread):
                with c.measure("shared"):
                    pass

        threads = [threading.Thread(target=worker) for _ in range(n_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        m = c.for_engine("shared")
        assert m.total_calls == n_threads * calls_per_thread
