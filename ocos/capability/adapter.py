"""Phase 23-A — CapabilityAdapter 协议统一 (§4.4 #6)。

扩展 EngineAdapter：提供统一的 Capability 执行协议，
支持同步/异步、本地/远程、重试/降级策略。

与 EngineAdapter 的关系:
  EngineAdapter 是底层封装（直接调用 engine.execute），
  CapabilityAdapter 是上层协议（增加重试、降级、监控）。
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Optional

from ocos.logging import get_logger

logger = get_logger(__name__)


# ── 枚举/常量 ────────────────────────────────────────────────────────────────


class AdapterStatus(str, Enum):
    IDLE = "IDLE"
    RUNNING = "RUNNING"
    DEGRADED = "DEGRADED"
    ERROR = "ERROR"


class RetryPolicy(str, Enum):
    """重试策略。"""
    NONE = "none"           # 不重试
    FIXED = "fixed"         # 固定间隔
    EXPONENTIAL = "exponential"  # 指数退避
    LINEAR = "linear"       # 线性递增


@dataclass
class AdapterResult:
    """统一的适配器执行结果。"""
    success: bool
    capability_id: str = ""
    provider_id: str = ""
    output: dict[str, Any] = field(default_factory=dict)
    error: str = ""
    attempt: int = 1
    duration_ms: float = 0.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


# ── CapabilityAdapter ─────────────────────────────────────────────────────────


class CapabilityAdapter:
    """统一能力适配器 — 包装一个提供者实例并提供协议层。

    职责:
      - 归一化调用接口（同步）
      - 重试逻辑（可配置策略）
      - 降级回调
      - 执行指标收集
    """

    def __init__(
        self,
        capability_id: str,
        provider_id: str,
        instance: Any = None,
        *,
        retry_policy: RetryPolicy = RetryPolicy.NONE,
        max_retries: int = 0,
        retry_base_delay: float = 1.0,
        timeout: float = 30.0,
        fallback: Callable[[dict[str, Any]], AdapterResult] | None = None,
    ):
        self.capability_id = capability_id
        self.provider_id = provider_id
        self._instance = instance
        self._status = AdapterStatus.IDLE
        self._retry_policy = retry_policy
        self._max_retries = max_retries
        self._retry_base_delay = retry_base_delay
        self._timeout = timeout
        self._fallback = fallback
        self._call_count = 0
        self._error_count = 0
        self._last_error: str = ""

    @property
    def status(self) -> AdapterStatus:
        return self._status

    @property
    def instance(self) -> Any:
        return self._instance

    # ── 执行 ───────────────────────────────────────────────────────────────

    def execute(self, inputs: dict[str, Any] | None = None) -> AdapterResult:
        """执行能力（含重试 + 降级）。"""
        inputs = inputs or {}
        attempt = 0
        last_error = ""

        self._status = AdapterStatus.RUNNING
        start = time.monotonic()

        while attempt <= self._max_retries:
            attempt += 1
            try:
                if self._instance is None:
                    raise RuntimeError(f"No instance for {self.capability_id}")

                # 尝试调用 .execute() 方法
                if hasattr(self._instance, "execute"):
                    raw = self._instance.execute(**inputs)
                elif callable(self._instance):
                    raw = self._instance(**inputs)
                else:
                    raise TypeError(f"Provider {self.provider_id} has no execute() or __call__")

                self._status = AdapterStatus.IDLE if self._error_count == 0 else AdapterStatus.DEGRADED
                self._call_count += 1
                return AdapterResult(
                    success=True,
                    capability_id=self.capability_id,
                    provider_id=self.provider_id,
                    output=raw if isinstance(raw, dict) else {"result": raw},
                    attempt=attempt,
                    duration_ms=(time.monotonic() - start) * 1000,
                )

            except Exception as e:
                last_error = str(e)
                self._error_count += 1
                self._last_error = last_error
                logger.warning("CapabilityAdapter[%s] attempt %d/%d failed: %s",
                               self.capability_id, attempt, self._max_retries + 1, e)

                if attempt <= self._max_retries:
                    delay = self._compute_delay(attempt)
                    if delay > 0:
                        time.sleep(delay)

        # 所有重试失败 → 降级
        self._status = AdapterStatus.ERROR
        if self._fallback is not None:
            logger.info("CapabilityAdapter[%s] invoking fallback", self.capability_id)
            try:
                return self._fallback(inputs)
            except Exception as fe:
                logger.error("Fallback also failed: %s", fe)
                last_error = f"fallback failed: {fe}"

        return AdapterResult(
            success=False,
            capability_id=self.capability_id,
            provider_id=self.provider_id,
            error=last_error,
            attempt=attempt,
            duration_ms=(time.monotonic() - start) * 1000,
        )

    def _compute_delay(self, attempt: int) -> float:
        if self._retry_policy == RetryPolicy.FIXED:
            return self._retry_base_delay
        elif self._retry_policy == RetryPolicy.EXPONENTIAL:
            return self._retry_base_delay * (2 ** (attempt - 1))
        elif self._retry_policy == RetryPolicy.LINEAR:
            return self._retry_base_delay * attempt
        return 0.0
