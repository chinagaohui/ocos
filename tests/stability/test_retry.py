"""RetryPolicy、retry 装饰器、timeout 装饰器测试。"""
from __future__ import annotations

import time

import pytest

from ocos.stability.retry import RetryPolicy, retry, timeout, TimeoutError


class TestRetryPolicy:
    def test_execute_success(self):
        """成功执行不重试。"""
        policy = RetryPolicy(max_retries=3)
        counter = [0]

        def fn():
            counter[0] += 1
            return "ok"

        result = policy.execute(fn)
        assert result == "ok"
        assert counter[0] == 1  # 仅执行一次

    def test_execute_retry_on_failure(self):
        """失败后重试。"""
        policy = RetryPolicy(max_retries=2, base_delay=0.01)
        counter = [0]

        def fn():
            counter[0] += 1
            if counter[0] < 3:
                raise ValueError("not yet")
            return "success"

        result = policy.execute(fn)
        assert result == "success"
        assert counter[0] == 3  # 2次失败 + 1次成功

    def test_execute_exhaust_retries(self):
        """耗尽重试次数后抛出原异常。"""
        policy = RetryPolicy(max_retries=2, base_delay=0.01)
        counter = [0]

        def fn():
            counter[0] += 1
            raise ValueError("always fail")

        with pytest.raises(ValueError):
            policy.execute(fn)
        assert counter[0] == 3  # 1次原始 + 2次重试

    def test_retryable_exceptions_filter(self):
        """只对指定异常重试。"""
        policy = RetryPolicy(
            max_retries=2,
            base_delay=0.01,
            retryable_exceptions=(ValueError,),
        )

        def fn():
            raise TypeError("not retryable")

        with pytest.raises(TypeError):
            policy.execute(fn)


class TestRetryDecorator:
    def test_retry_decorator(self):
        """装饰器正常工作。"""
        counter = [0]

        @retry(max_retries=2, base_delay=0.01)
        def unreliable():
            counter[0] += 1
            if counter[0] < 2:
                raise ValueError("not yet")
            return "done"

        result = unreliable()
        assert result == "done"
        assert counter[0] == 2


class TestTimeout:
    def test_timeout_success(self):
        """正常执行不超时。"""

        @timeout(1.0)
        def fast():
            return "ok"

        assert fast() == "ok"

    def test_timeout_exception(self):
        """函数抛出异常，正常传播。"""

        @timeout(1.0)
        def raises():
            raise ValueError("expected")

        with pytest.raises(ValueError):
            raises()

    def test_timeout_raises(self):
        """超时抛出 TimeoutError。"""

        @timeout(0.05)
        def slow():
            time.sleep(1.0)
            return "done"

        with pytest.raises(TimeoutError):
            slow()
