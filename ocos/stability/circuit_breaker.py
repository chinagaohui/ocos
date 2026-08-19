"""CircuitBreaker — 断路器模式实现。

状态机：
  CLOSED (正常) → failure_threshold 次失败 → OPEN (熔断)
  OPEN → recovery_timeout 后 → HALF_OPEN (半开)
  HALF_OPEN → 测试请求成功 → CLOSED
  HALF_OPEN → 测试请求失败 → OPEN
"""

from __future__ import annotations

import time
import threading
from enum import Enum
from functools import wraps
from typing import Any, Callable, Optional


class CircuitState(str, Enum):
    CLOSED = "closed"         # 正常 — 调用通过
    OPEN = "open"             # 熔断 — 调用直接失败
    HALF_OPEN = "half_open"   # 半开 — 允许测试请求


class CircuitBreaker:
    """断路器。

    Args:
        name: 断路器名称。
        failure_threshold: 触发熔断的连续失败次数。
        recovery_timeout: OPEN 到 HALF_OPEN 的等待秒数。
        half_open_max_requests: HALF_OPEN 状态允许的测试请求数。
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        half_open_max_requests: int = 3,
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_requests = half_open_max_requests

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time: float = 0.0
        self._half_open_requests = 0
        self._lock = threading.Lock()

    @property
    def state(self) -> CircuitState:
        return self._state

    @property
    def failure_count(self) -> int:
        return self._failure_count

    def call(self, fn: Callable, *args: Any, **kwargs: Any) -> Any:
        """执行受保护调用。自动管理断路器状态。"""
        with self._lock:
            self._check_transition()

            if self._state == CircuitState.OPEN:
                raise CircuitBreakerError(f"Circuit '{self.name}' is OPEN")

            if self._state == CircuitState.HALF_OPEN:
                if self._half_open_requests >= self.half_open_max_requests:
                    raise CircuitBreakerError(
                        f"Circuit '{self.name}' is HALF_OPEN (max test requests reached)"
                    )
                self._half_open_requests += 1

        try:
            result = fn(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise

    def record_success(self) -> None:
        """手动记录成功。"""
        with self._lock:
            self._on_success()

    def record_failure(self) -> None:
        """手动记录失败。"""
        with self._lock:
            self._on_failure()

    def reset(self) -> None:
        """重置断路器到 CLOSED 状态。"""
        with self._lock:
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            self._half_open_requests = 0

    # ── 内部 ───────────────────────────────────────────────────────────────────

    def _check_transition(self) -> None:
        """检查是否需要从 OPEN 过渡到 HALF_OPEN。"""
        if self._state == CircuitState.OPEN:
            elapsed = time.time() - self._last_failure_time
            if elapsed >= self.recovery_timeout:
                self._state = CircuitState.HALF_OPEN
                self._half_open_requests = 0

    def _on_success(self) -> None:
        if self._state == CircuitState.HALF_OPEN:
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            self._half_open_requests = 0
        elif self._state == CircuitState.CLOSED:
            self._failure_count = 0  # 连续成功重置计数器

    def _on_failure(self) -> None:
        self._failure_count += 1
        self._last_failure_time = time.time()
        if self._state == CircuitState.HALF_OPEN:
            self._state = CircuitState.OPEN
        elif self._state == CircuitState.CLOSED:
            if self._failure_count >= self.failure_threshold:
                self._state = CircuitState.OPEN


class CircuitBreakerError(Exception):
    """断路器拒绝调用时抛出。"""


class CircuitBreakerRegistry:
    """全局断路器注册表。"""

    _breakers: dict[str, CircuitBreaker] = {}

    @classmethod
    def get(cls, name: str) -> Optional[CircuitBreaker]:
        return cls._breakers.get(name)

    @classmethod
    def register(cls, name: str, breaker: CircuitBreaker) -> None:
        cls._breakers[name] = breaker

    @classmethod
    def stats(cls) -> dict[str, CircuitState]:
        return {name: breaker.state for name, breaker in cls._breakers.items()}

    @classmethod
    def clear(cls) -> None:
        cls._breakers.clear()
