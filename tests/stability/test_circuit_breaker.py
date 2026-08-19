"""CircuitBreaker 测试。"""
from __future__ import annotations

import time

import pytest

from ocos.stability.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerError,
    CircuitBreakerRegistry,
    CircuitState,
)


class TestCircuitBreaker:
    def test_initial_state(self):
        """初始状态为 CLOSED。"""
        cb = CircuitBreaker("test", failure_threshold=3, recovery_timeout=0.1)
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 0

    def test_call_success(self):
        """成功调用不改变状态。"""
        cb = CircuitBreaker("test")
        result = cb.call(lambda: "ok")
        assert result == "ok"
        assert cb.state == CircuitState.CLOSED

    def test_call_failure_trips(self):
        """连续失败触发熔断。"""
        cb = CircuitBreaker("test", failure_threshold=3, recovery_timeout=60)

        def failing():
            raise ValueError("fail")

        with pytest.raises(ValueError):
            cb.call(failing)
        assert cb.state == CircuitState.CLOSED

        with pytest.raises(ValueError):
            cb.call(failing)
        assert cb.state == CircuitState.CLOSED

        with pytest.raises(ValueError):
            cb.call(failing)
        assert cb.state == CircuitState.OPEN

    def test_open_blocks_calls(self):
        """OPEN 状态拒绝调用。"""
        cb = CircuitBreaker("test", failure_threshold=1, recovery_timeout=60)

        with pytest.raises(ValueError):
            cb.call(lambda: (_ for _ in ()).throw(ValueError("fail")))  # type: ignore

        assert cb.state == CircuitState.OPEN
        with pytest.raises(CircuitBreakerError):
            cb.call(lambda: "should not reach")

    def test_half_open_recovers(self):
        """HALF_OPEN 下成功调用恢复到 CLOSED。"""
        cb = CircuitBreaker("test", failure_threshold=1, recovery_timeout=0.05)

        with pytest.raises(ValueError):
            cb.call(lambda: (_ for _ in ()).throw(ValueError("fail")))  # type: ignore

        assert cb.state == CircuitState.OPEN
        time.sleep(0.06)

        result = cb.call(lambda: "recovered")
        assert result == "recovered"
        assert cb.state == CircuitState.CLOSED

    def test_half_open_fails_again(self):
        """HALF_OPEN 下失败回到 OPEN。"""
        cb = CircuitBreaker("test", failure_threshold=2, recovery_timeout=0.05)

        for _ in range(2):
            with pytest.raises(ValueError):
                cb.call(lambda: (_ for _ in ()).throw(ValueError("fail")))  # type: ignore

        assert cb.state == CircuitState.OPEN
        time.sleep(0.06)

        with pytest.raises(ValueError):
            cb.call(lambda: (_ for _ in ()).throw(ValueError("fail")))  # type: ignore

        assert cb.state == CircuitState.OPEN  # 回到 OPEN

    def test_record_success_and_failure(self):
        """手动记录成功和失败。"""
        cb = CircuitBreaker("test", failure_threshold=2, recovery_timeout=60)
        cb.record_failure()
        assert cb.failure_count == 1
        cb.record_success()
        assert cb.failure_count == 0  # 连续成功重置

    def test_reset(self):
        """reset 恢复到 CLOSED。"""
        cb = CircuitBreaker("test", failure_threshold=1, recovery_timeout=60)
        with pytest.raises(ValueError):
            cb.call(lambda: (_ for _ in ()).throw(ValueError("fail")))  # type: ignore

        assert cb.state == CircuitState.OPEN
        cb.reset()
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 0


class TestCircuitBreakerRegistry:
    def test_register_and_get(self):
        """注册和获取断路器。"""
        cb = CircuitBreaker("my_breaker")
        CircuitBreakerRegistry.register("my_breaker", cb)
        assert CircuitBreakerRegistry.get("my_breaker") is cb
        assert CircuitBreakerRegistry.get("nonexistent") is None

    def test_stats(self):
        """stats 返回所有断路器状态。"""
        CircuitBreakerRegistry.clear()
        cb1 = CircuitBreaker("a")
        cb2 = CircuitBreaker("b")
        CircuitBreakerRegistry.register("a", cb1)
        CircuitBreakerRegistry.register("b", cb2)
        stats = CircuitBreakerRegistry.stats()
        assert stats["a"] == CircuitState.CLOSED
        assert stats["b"] == CircuitState.CLOSED

    def test_clear(self):
        """clear 清空注册表。"""
        CircuitBreakerRegistry.register("x", CircuitBreaker("x"))
        CircuitBreakerRegistry.clear()
        assert CircuitBreakerRegistry.get("x") is None
