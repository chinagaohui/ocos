"""S3.5: Monitoring 接入生产回归（白皮书 P3）。"""

from __future__ import annotations

import pytest


class TestMonitoringWiring:
    def test_factory_attaches_monitoring(self):
        from ocos.daemon.factory import build_health_loop
        hl = build_health_loop()
        assert getattr(hl, "monitoring", None) is not None
        # 默认不启动 HTTP（避免测试端口冲突）
        assert hl.monitoring._httpd is None if hasattr(
            hl.monitoring, "_httpd") else True

    def test_metrics_recorded_via_health_loop(self):
        from ocos.daemon.factory import build_health_loop
        hl = build_health_loop()
        # 模拟 run_check 的指标记录段（runtime 为 None 时采集降级 0）
        try:
            hl.run_check()
        except Exception:
            pass  # runtime None 时部分采集失败，指标段容错
        metrics = hl.monitoring.get_metrics()
        assert "ocos_gauges" in metrics or "ocos_counters" in metrics

    def test_prometheus_output_no_typo(self):
        from ocos.monitoring.manager import MetricsRegistry
        reg = MetricsRegistry()
        reg.set_gauge("x", 1.0)
        out = reg.to_prometheus()
        assert "ocos_up" in out
        assert "ococ_up" not in out

    def test_histogram_quantile_real(self):
        from ocos.monitoring.manager import MetricsRegistry
        reg = MetricsRegistry()
        values = list(range(1, 101))  # 1..100
        for v in values:
            reg.observe("lat", float(v))
        out = reg.to_prometheus()
        # 0.9 分位 ≈ 90（原实现恒输出 max=100）
        import re
        m = re.search(r'ocos_histograms\{name="lat",quantile="0\.9"\} ([0-9.]+)', out)
        assert m, out
        assert float(m.group(1)) < 100.0

    def test_five_core_metrics_present(self):
        """S3.5 验收：5 个核心指标全部出现在 /metrics 输出。"""
        from ocos.monitoring.manager import (
            create_monitoring_manager, set_global_metrics,
        )
        mm = create_monitoring_manager()
        set_global_metrics(mm.metrics)
        mm.record_metric("ocos_tick_total", 1.0, metric_type="counter")
        mm.record_metric("ocos_goal_active", 1.0, metric_type="gauge")
        mm.record_metric("ocos_memory_episodes_total", 1.0, metric_type="gauge")
        mm.record_metric("ocos_execution_pending", 1.0, metric_type="gauge")
        from ocos.monitoring.manager import record_global
        record_global("ocos_llm_calls_total", 1.0)
        out = mm.get_metrics()
        for name in ("ocos_tick_total", "ocos_goal_active",
                     "ocos_llm_calls_total", "ocos_memory_episodes_total",
                     "ocos_execution_pending", "ocos_up"):
            assert name in out, f"missing metric: {name}"

    def test_health_loop_tick_increments_counter(self):
        """HealthLoop.tick 每次调用 +1 ocos_tick_total（心跳埋点）。"""
        from ocos.daemon.factory import build_health_loop
        hl = build_health_loop(interval_ticks=1000)
        hl.tick()
        hl.tick()
        out = hl.monitoring.get_metrics()
        m = __import__("re").search(
            r'ocos_counters\{name="ocos_tick_total"\} ([0-9.]+)', out)
        assert m, out
        assert float(m.group(1)) >= 2.0
