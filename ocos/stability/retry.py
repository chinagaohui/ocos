"""Retry — 重试与超时策略。

RetryPolicy: 声明式重试配置
retry(): 装饰器
timeout(): 超时装饰器
"""

from __future__ import annotations

import time
import functools
import threading
from typing import Any, Callable, Optional, TypeVar

F = TypeVar("F", bound=Callable[..., Any])


class RetryPolicy:
    """重试策略。

    支持指数退避和最大重试次数。
    """

    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 0.5,
        max_delay: float = 30.0,
        backoff_multiplier: float = 2.0,
        retryable_exceptions: tuple[type[Exception], ...] = (Exception,),
    ):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.backoff_multiplier = backoff_multiplier
        self.retryable_exceptions = retryable_exceptions

    def execute(self, fn: Callable, *args: Any, **kwargs: Any) -> Any:
        """执行函数并重试。"""
        last_exception: Optional[Exception] = None
        for attempt in range(self.max_retries + 1):
            try:
                return fn(*args, **kwargs)
            except self.retryable_exceptions as e:
                last_exception = e
                if attempt < self.max_retries:
                    delay = min(
                        self.base_delay * (self.backoff_multiplier ** attempt),
                        self.max_delay,
                    )
                    time.sleep(delay)
        raise last_exception  # type: ignore

    def __call__(self, fn: Callable) -> Callable:
        """作为装饰器使用。"""

        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            return self.execute(fn, *args, **kwargs)

        return wrapper


def retry(
    max_retries: int = 3,
    base_delay: float = 0.5,
    max_delay: float = 30.0,
    backoff_multiplier: float = 2.0,
    retryable_exceptions: tuple[type[Exception], ...] = (Exception,),
) -> Callable[[F], F]:
    """重试装饰器快捷方式。"""
    policy = RetryPolicy(
        max_retries=max_retries,
        base_delay=base_delay,
        max_delay=max_delay,
        backoff_multiplier=backoff_multiplier,
        retryable_exceptions=retryable_exceptions,
    )
    return policy  # type: ignore


class TimeoutError(Exception):
    """执行超时。"""


def timeout(seconds: float) -> Callable[[F], F]:
    """超时装饰器（使用 threading.Timer 实现）。"""

    def decorator(fn: F) -> F:
        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            result: list[Any] = [None]
            exception: list[Optional[Exception]] = [None]
            completed = threading.Event()

            def target():
                try:
                    result[0] = fn(*args, **kwargs)
                except Exception as e:
                    exception[0] = e
                finally:
                    completed.set()

            thread = threading.Thread(target=target, daemon=True)
            thread.start()
            finished = completed.wait(timeout=seconds)

            if not finished:
                raise TimeoutError(
                    f"Function '{fn.__name__}' timed out after {seconds}s"
                )
            if exception[0] is not None:
                raise exception[0]  # type: ignore
            return result[0]

        return wrapper  # type: ignore

    return decorator
