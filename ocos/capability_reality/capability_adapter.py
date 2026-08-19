"""Phase 55: CapabilityAdapter — 抽象适配器基类。

CR55-02: Adapter Isolation — 适配器崩溃不影响主脑。

每个真实适配器:
    1. 注册到 CapabilityRegistry
    2. 描述自身能力 (CapabilityDescriptor)
    3. 提供 validate() — 执行前验证
    4. 提供 execute() — 沙盒执行
    5. 报告健康状态 (health_check)
    6. 记录事件到 EventLifecycle (CR55-03)
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Callable

from ocos.capability_reality.adapter_types import (
    CapabilityDescriptor, AdapterStatus, AdapterHealth,
    ExecutionContext, ExecutionResult, ExecutionStatus,
    AdapterConfig,
)


@dataclass
class CapabilityAdapter(ABC):
    """适配器基类 — 所有真实能力适配器的抽象。

    子类只需实现 _do_execute() 和 _do_health_check()。
    """

    descriptor: CapabilityDescriptor
    config: AdapterConfig = field(default_factory=AdapterConfig)
    status: AdapterStatus = field(default_factory=lambda: AdapterStatus(adapter_id=""))
    on_event: Callable | None = None  # 事件回调 for CR55-03

    def __post_init__(self):
        if self.status.adapter_id != self.descriptor.name:
            self.status.adapter_id = self.descriptor.name

    @abstractmethod
    def _do_execute(self, ctx: ExecutionContext) -> object:
        """实际执行逻辑 — 子类实现。"""
        ...

    @abstractmethod
    def _do_health_check(self) -> AdapterHealth:
        """健康检查 — 子类实现。"""
        ...

    def execute(self, ctx: ExecutionContext) -> ExecutionResult:
        """带安全包装的执行。

        包装逻辑:
            1. 超时保护
            2. 异常隔离 (CR55-02)
            3. 状态更新
        """
        import time as _time

        ctx.started_at = _time.time()
        t0 = _time.time()

        try:
            self.status.total_executions += 1
            output = self._do_execute(ctx)
            elapsed = (_time.time() - t0) * 1000

            result = ExecutionResult(
                context=ctx,
                status=ExecutionStatus.SUCCESS,
                output=output,
                duration_ms=elapsed,
            )
            self.status.last_success = _time.time()
            self.status.avg_latency_ms = (
                (self.status.avg_latency_ms * (self.status.total_executions - 1) + elapsed)
                / self.status.total_executions
            )
            self.status.health = AdapterHealth.HEALTHY

        except TimeoutError:
            elapsed = (_time.time() - t0) * 1000
            result = ExecutionResult(
                context=ctx,
                status=ExecutionStatus.TIMEOUT,
                error=f"timeout after {ctx.timeout}s",
                duration_ms=elapsed,
            )
            self.status.total_failures += 1
            self.status.last_failure = _time.time()

        except Exception as e:
            elapsed = (_time.time() - t0) * 1000
            result = ExecutionResult(
                context=ctx,
                status=ExecutionStatus.FAILED,
                error=str(e),
                duration_ms=elapsed,
            )
            self.status.total_failures += 1
            self.status.last_failure = _time.time()
            # CR55-02: 异常不传播，标记为 DEGRADED
            if self.status.failure_rate > 0.5:
                self.status.health = AdapterHealth.DEGRADED

        if self.on_event:
            try:
                self.on_event(result)
            except Exception:
                pass  # 事件记录失败不阻塞

        return result

    def health_check(self) -> AdapterHealth:
        """执行健康检查并更新状态。"""
        import time as _time
        try:
            self.status.health = self._do_health_check()
        except Exception:
            self.status.health = AdapterHealth.FAILED
        self.status.last_check = _time.time()
        return self.status.health

    def validate(self, ctx: ExecutionContext) -> bool:
        """执行前验证。返回 False = 拒绝执行。"""
        # 检查超时
        if ctx.timeout <= 0 or ctx.timeout > 300:
            return False
        # 检查沙盒
        if not ctx.sandboxed and self.descriptor.risk_level >= 4:
            return False
        # 检查权限
        for perm in self.descriptor.permissions:
            if perm not in self.config.permissions:
                return False
        return True

    def register_to(self, registry) -> None:
        """注册自身到 CapabilityRegistry。"""
        from ocos.capability_reality.capability_registry import CapabilityRegistry
        if isinstance(registry, CapabilityRegistry):
            registry.register(self.descriptor, executor=self.execute)


__all__ = ["CapabilityAdapter"]
