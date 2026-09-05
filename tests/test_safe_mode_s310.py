"""S3.10: PipelineError 兜底 + SAFE_MODE/DEGRADED 降级编排回归
（白皮书 P2-3）。

- 单 stage 失败 → tick_loop 不死，Runtime 进 DEGRADED（跳过 agent driver）
- 连续 3 次失败 → SAFE_MODE（仅心跳 + checkpoint）
- SAFE_MODE 下连续 5 次成功 → 恢复 RUNNING
"""

from __future__ import annotations

import pytest

from ocos.runtime.pipeline import PipelineError
from ocos.runtime.runtime_kernel import RuntimeKernel
from ocos.runtime.runtime_state import RuntimeState


def _failing_kernel(monkeypatch, fail_times: int = 1) -> RuntimeKernel:
    """注入会连续失败 N 次的 stage。"""
    k = RuntimeKernel(runtime_id="s310-test")
    k.start()

    original = k._pipeline.execute_tick
    calls = {"n": 0}

    def flaky(tick_id, runtime_state):
        if calls["n"] < fail_times:
            calls["n"] += 1
            raise PipelineError("Stage GOAL_MAINTENANCE failed at tick")
        return original(tick_id=tick_id, runtime_state=runtime_state)

    monkeypatch.setattr(k._pipeline, "execute_tick", flaky)
    return k


class TestPipelineErrorContainment:
    def test_single_failure_degrades_then_recovers(self, monkeypatch):
        k = _failing_kernel(monkeypatch, fail_times=1)
        try:
            k.tick_loop(max_ticks=5)
            assert k._lifecycle.state == RuntimeState.RUNNING
            # 单次失败曾进 DEGRADED，成功后恢复（tick 不死）
            assert k._tick_count >= 4
        finally:
            k.shutdown(checkpoint=False)

    def test_three_failures_enter_safe_mode(self, monkeypatch):
        k = _failing_kernel(monkeypatch, fail_times=3)
        try:
            k.tick_loop(max_ticks=4)
            assert k._lifecycle.state == RuntimeState.SAFE_MODE
        finally:
            k.shutdown(checkpoint=False)

    def test_loop_survives_and_recovers(self, monkeypatch):
        k = _failing_kernel(monkeypatch, fail_times=3)
        try:
            k.tick_loop(max_ticks=12)
            # SAFE_MODE 连续 5 次成功 → 恢复 RUNNING
            assert k._lifecycle.state == RuntimeState.RUNNING
            assert k._tick_count >= 8
        finally:
            k.shutdown(checkpoint=False)

    def test_degraded_skips_agent_driver(self, monkeypatch):
        """DEGRADED/SAFE_MODE 下 agent driver 不被调用。"""
        k = _failing_kernel(monkeypatch, fail_times=3)
        calls = {"n": 0}
        k.attach_agent_driver(lambda tick_id: calls.__setitem__(
            "n", calls["n"] + 1) or {"ok": True})
        try:
            k.tick_loop(max_ticks=10)
            # driver 调用数 < tick 数（降级 tick 被跳过）
            assert calls["n"] < k._tick_count
        finally:
            k.shutdown(checkpoint=False)
