"""RetryPolicy — 引擎调用重试与断路器机制。

设计原则：
- 纯函数式配置（RetryPolicy 为不可变数据类）
- 断路器状态在每个引擎实例中独立维护
- 指数退避：base_delay × 2^attempt + jitter
"""

from __future__ import annotations

import random
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable


class CircuitState(Enum):
    CLOSED = auto()       # 正常运行
    OPEN = auto()         # 熔断开启 — 快速失败
    HALF_OPEN = auto()    # 半开 — 允许单次试探


class CircuitBreakerOpenError(RuntimeError):
    """断路器开启时抛出的快速失败异常。"""
    pass


@dataclass
class CircuitBreakerState:
    """断路器运行时状态。"""
    state: CircuitState = CircuitState.CLOSED
    failure_count: int = 0
    last_failure_time: float = 0.0
    success_count_since_open: int = 0
    half_open_attempted: bool = False

    def reset(self) -> None:
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time = 0.0
        self.success_count_since_open = 0
        self.half_open_attempted = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "state": self.state.name,
            "failure_count": self.failure_count,
            "last_failure_time": round(self.last_failure_time, 2) if self.last_failure_time else 0.0,
            "success_count_since_open": self.success_count_since_open,
        }


@dataclass
class RetryPolicy:
    """重试策略配置（不可变）。"""
    max_retries: int = 3  # -1 = 无限重试
    base_delay: float = 0.5     # 秒
    max_delay: float = 30.0     # 秒
    jitter: float = 0.1         # ±jitter 秒
    circuit_breaker_enabled: bool = True
    failure_threshold: int = 5       # 连续失败 N 次后开启断路器
    half_open_timeout: float = 30.0  # 30 秒后尝试半开
    half_open_success_threshold: int = 2  # 半开后连续成功 N 次关断

    def backoff_delay(self, attempt: int) -> float:
        """计算第 attempt 次重试的延迟（0-indexed）。"""
        delay = self.base_delay * (2 ** attempt)
        delay = min(delay, self.max_delay)
        jitter_amount = random.uniform(-self.jitter, self.jitter)
        return max(0.1, delay + jitter_amount)


def safe_execute(
    fn: Callable[[], dict[str, Any]],
    cb_state: CircuitBreakerState,
    policy: RetryPolicy = RetryPolicy(),
    logger: Any = None,  # noqa: ANN401
    engine_name: str = "engine",
) -> dict[str, Any]:
    """安全执行引擎调用。

    Args:
        fn: 无参可调用目标（闭包预先绑定参数）
        cb_state: 断路器状态（跨调用保持）
        policy: 重试策略
        logger: 可选的 logger
        engine_name: 日志中显示的引擎名

    Returns:
        引擎调用的结果 dict

    Raises:
        CircuitBreakerOpenError: 断路器开启时
    """
    _logger = logger or __import__("logging").getLogger(__name__)

    # ── 断路器检查 ────────────────────────────────────────────
    if policy.circuit_breaker_enabled:
        now = time.monotonic()
        if cb_state.state == CircuitState.OPEN:
            elapsed = now - cb_state.last_failure_time
            if elapsed < policy.half_open_timeout:
                raise CircuitBreakerOpenError(
                    f"Circuit breaker OPEN for {engine_name} "
                    f"({elapsed:.1f}s < {policy.half_open_timeout}s timeout)"
                )
            # 超时 → 半开试探
            cb_state.state = CircuitState.HALF_OPEN
            cb_state.half_open_attempted = True
            _logger.info(f"{engine_name}: circuit HALF_OPEN, probing...")

    # ── 重试执行 ──────────────────────────────────────────────
    last_error: Exception | None = None
    result: dict[str, Any] | None = None

    max_attempts = policy.max_retries + 1  # +1 为首次
    if policy.max_retries < 0:
        max_attempts = -1  # 无限

    attempt = 0
    while max_attempts < 0 or attempt < max_attempts:
        try:
            result = fn()

            if result.get("success", False):
                # 成功：关断断路器
                if policy.circuit_breaker_enabled:
                    if cb_state.state == CircuitState.HALF_OPEN:
                        cb_state.success_count_since_open += 1
                        if cb_state.success_count_since_open >= policy.half_open_success_threshold:
                            cb_state.reset()
                            _logger.info(f"{engine_name}: circuit CLOSED after {cb_state.success_count_since_open} successes")
                    else:
                        cb_state.failure_count = 0
                return result

            # 引擎返回 success=False → 当做失败处理
            raise RuntimeError(result.get("message", "Unknown engine error"))

        except CircuitBreakerOpenError:
            raise  # 快速失败，不重试
        except Exception as e:
            last_error = e
            attempt += 1

            # 记录断路器状态
            if policy.circuit_breaker_enabled:
                cb_state.failure_count += 1
                cb_state.last_failure_time = time.monotonic()
                if cb_state.failure_count >= policy.failure_threshold:
                    cb_state.state = CircuitState.OPEN
                    _logger.warning(
                        f"{engine_name}: circuit OPEN after "
                        f"{cb_state.failure_count} failures"
                    )
                    break  # 不再重试

            if max_attempts >= 0 and attempt >= max_attempts:
                break

            # 退避等待
            delay = policy.backoff_delay(attempt - 1)
            _logger.debug(f"{engine_name}: retry {attempt}/{policy.max_retries} in {delay:.1f}s: {e}")
            time.sleep(delay)

    # 所有重试用尽
    error_msg = str(last_error) if last_error else "Max retries exceeded"
    return {"success": False, "message": f"{engine_name} failed: {error_msg}"}
