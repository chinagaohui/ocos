"""S3.9: _tick_errors 自增回归（白皮书 P2）。

step 结果含 error 字段时 _tick_errors 自增——
稳定性报告 error_rate 不再恒 0，high_error_rate 漂移旗标可触发。
"""

from __future__ import annotations

import pytest


class TestTickErrorAccounting:
    def test_step_error_increments_counter(self, tmp_path, monkeypatch):
        monkeypatch.setenv("OCOS_DB_PATH", str(tmp_path / "t.db"))
        from ocos.agent.agent_runtime import AgentRuntime
        rt = AgentRuntime.__new__(AgentRuntime)
        # 最小字段集（避免走 __init__ 全量装配）
        import threading
        rt._tick_errors = 0
        rt._lock = threading.RLock()
        step_log: list = []
        rt._record_step_result(step_log, {"step": "x", "error": "boom"})
        rt._record_step_result(step_log, {"step": "y"})  # 无 error 不计
        assert rt._tick_errors == 1
        assert len(step_log) == 2

    def test_stability_report_reflects_errors(self, tmp_path, monkeypatch):
        """注入错误 step 后 get_stability_report 的 errors>0。"""
        monkeypatch.setenv("OCOS_DB_PATH", str(tmp_path / "t.db"))
        from ocos.agent.agent_runtime import AgentRuntime
        import time as _time
        rt = AgentRuntime.__new__(AgentRuntime)
        rt._tick_errors = 0
        rt._tick_latencies = []
        rt._boot_time = _time.time()
        rt._cycle_count = 200  # >100 触发 error_rate 判定
        rt._lock = __import__("threading").RLock()
        class _Mem:
            working_count = 0
            long_term_count = 0
        class _Beliefs:
            belief_count = 0
        rt.memory = _Mem()
        rt.beliefs = _Beliefs()
        rt._memory_hub = None
        # 模拟大量错误（50/200 = 25% > 10% 阈值）
        rt._tick_errors = 50
        report = rt.get_stability_report()
        assert report["stability"]["errors"] == 50
        assert "high_error_rate" in report["stability"]["drift_flags"]
