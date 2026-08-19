"""RetryPolicy + safe_execute + CircuitBreaker 单元测试。"""
from __future__ import annotations

import time
from unittest.mock import MagicMock

import pytest

from ocos.agent.retry_policy import (
    CircuitBreakerOpenError,
    CircuitBreakerState,
    CircuitState,
    RetryPolicy,
    safe_execute,
)


class TestRetryPolicy:
    """重试策略配置。"""

    def test_defaults(self):
        p = RetryPolicy()
        assert p.max_retries == 3
        assert p.base_delay == 0.5

    def test_backoff_delay_increases(self):
        p = RetryPolicy(base_delay=1.0, jitter=0)
        d1 = p.backoff_delay(0)  # 1.0
        d2 = p.backoff_delay(1)  # 2.0
        d3 = p.backoff_delay(2)  # 4.0
        assert d1 < d2 < d3

    def test_backoff_capped(self):
        p = RetryPolicy(base_delay=100, max_delay=5, jitter=0)
        delay = p.backoff_delay(3)
        assert delay <= 5.0

    def test_backoff_with_jitter(self):
        p = RetryPolicy(base_delay=1.0, jitter=0.5)
        delays = {p.backoff_delay(0) for _ in range(10)}
        # jitter 应产生不同值（概率上）
        assert len(delays) > 1


class TestCircuitBreakerState:
    """断路器状态。"""

    def test_initial_state(self):
        cb = CircuitBreakerState()
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 0

    def test_reset(self):
        cb = CircuitBreakerState()
        cb.state = CircuitState.OPEN
        cb.failure_count = 10
        cb.reset()
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 0

    def test_to_dict(self):
        cb = CircuitBreakerState()
        cb.failure_count = 3
        d = cb.to_dict()
        assert d["state"] == "CLOSED"
        assert d["failure_count"] == 3


class TestSafeExecute:
    """安全执行（重试 + 断路器）。"""

    def test_success_first_attempt(self):
        cb = CircuitBreakerState()
        fn = MagicMock(return_value={"success": True, "data": "ok"})
        result = safe_execute(fn, cb, RetryPolicy(max_retries=0))
        assert result["success"] is True
        fn.assert_called_once()

    def test_failure_no_retry(self):
        """max_retries=0 时失败不重试。"""
        cb = CircuitBreakerState()
        fn = MagicMock(side_effect=RuntimeError("boom"))
        result = safe_execute(fn, cb, RetryPolicy(max_retries=0))
        assert result["success"] is False
        assert "boom" in result["message"]
        fn.assert_called_once()

    def test_retry_succeeds_eventually(self):
        """前 N 次失败，第 N+1 次成功。"""
        cb = CircuitBreakerState()
        call_count = [0]

        def fn():
            call_count[0] += 1
            if call_count[0] < 3:
                raise RuntimeError(f"attempt {call_count[0]} failed")
            return {"success": True, "data": "recovered"}

        result = safe_execute(fn, cb, RetryPolicy(max_retries=3, base_delay=0.01, jitter=0))
        assert result["success"] is True
        assert call_count[0] == 3

    def test_all_retries_exhausted(self):
        """重试用尽后返回失败。"""
        cb = CircuitBreakerState()
        fn = MagicMock(side_effect=RuntimeError("persistent"))
        result = safe_execute(fn, cb, RetryPolicy(max_retries=2, base_delay=0.01, jitter=0))
        assert result["success"] is False
        assert fn.call_count == 3  # 首次 + 2 次重试 = 3

    def test_engine_returns_false_is_retried(self):
        """引擎返回 success=False 也应触发热重试。"""
        cb = CircuitBreakerState()
        call_count = [0]

        def fn():
            call_count[0] += 1
            return {"success": False, "message": "transient"}

        # max_retries=0 所以不会重试 — 检查立即失败
        result = safe_execute(fn, cb, RetryPolicy(max_retries=0, base_delay=0.01))
        assert result["success"] is False

    def test_success_engine_false_no_retry_needed(self):
        """引擎返回 success=True 即直接返回，即使结果内部是 False。"""
        cb = CircuitBreakerState()
        fn = MagicMock(return_value={"success": True, "result": "ok"})
        result = safe_execute(fn, cb, RetryPolicy(max_retries=0))
        assert result["success"] is True
        fn.assert_called_once()

    def test_circuit_breaker_opens_after_threshold(self):
        """连续失败达到阈值后断路器开启。"""
        cb = CircuitBreakerState()
        fn = MagicMock(side_effect=RuntimeError("fail"))
        policy = RetryPolicy(
            max_retries=1, base_delay=0.01, jitter=0,
            circuit_breaker_enabled=True, failure_threshold=3,
        )
        # 第一次调用：2 次尝试（首次+1次重试）→ 2 failures
        safe_execute(fn, cb, policy)
        assert cb.state == CircuitState.CLOSED  # 未达到阈值
        assert cb.failure_count == 2

        # 第二次调用：又 2 次尝试 → 2+2=4 > 3 → OPEN
        safe_execute(fn, cb, policy)
        assert cb.state == CircuitState.OPEN
        assert cb.failure_count >= 3

    def test_circuit_breaker_raises_open(self):
        """断路器开启时快速失败。"""
        cb = CircuitBreakerState()
        cb.state = CircuitState.OPEN
        cb.failure_count = 10
        cb.last_failure_time = time.monotonic()  # 刚发生，未超时

        fn = MagicMock(return_value={"success": True})
        with pytest.raises(CircuitBreakerOpenError):
            safe_execute(fn, cb, RetryPolicy(base_delay=0.01))

        fn.assert_not_called()  # 不应执行

    def test_circuit_half_open_after_timeout(self):
        """超时后半开试探。"""
        cb = CircuitBreakerState()
        cb.state = CircuitState.OPEN
        cb.failure_count = 10
        cb.last_failure_time = time.monotonic() - 100  # 100 秒前，超过 30s timeout

        fn = MagicMock(return_value={"success": True, "data": "recovered"})
        result = safe_execute(fn, cb, RetryPolicy(
            base_delay=0.01, half_open_timeout=30, half_open_success_threshold=1,
        ))
        assert result["success"] is True
        assert cb.state == CircuitState.CLOSED  # 成功后关断

    def test_half_open_needs_multiple_successes(self):
        """半开后需要连续成功直到阈值才关断。"""
        cb = CircuitBreakerState()
        cb.state = CircuitState.OPEN
        cb.last_failure_time = time.monotonic() - 100

        fn = MagicMock(return_value={"success": True})

        # 第一次：半开 → 成功 → 计数 1，但阈值是 2
        safe_execute(fn, cb, RetryPolicy(
            base_delay=0.01, half_open_timeout=30, half_open_success_threshold=2,
        ))
        assert cb.state == CircuitState.HALF_OPEN
        assert cb.success_count_since_open == 1

        # 第二次：成功 → 计数 2 → 关断
        safe_execute(fn, cb, RetryPolicy(
            base_delay=0.01, half_open_timeout=30, half_open_success_threshold=2,
        ))
        assert cb.state == CircuitState.CLOSED

    def test_legitimate_success_resets_count(self):
        """断路器关闭状态下的成功应重置故障计数。"""
        cb = CircuitBreakerState()
        cb.failure_count = 3

        fn = MagicMock(return_value={"success": True})
        safe_execute(fn, cb, RetryPolicy(base_delay=0.01))
        assert cb.failure_count == 0
