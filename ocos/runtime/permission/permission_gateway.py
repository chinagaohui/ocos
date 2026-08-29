"""Phase 39.3: PermissionGateway — 权限网关主入口。

PermissionGateway 是 Capability Policy Enforcement Layer 的核心。
职责:
    1. 接收 PermissionRequest + PermissionContext
    2. 评估 BuiltinPolicies
    3. 生成 PermissionTrace 审计记录
    4. 返回 PolicyDecision

架构位置 (Phase 39.3):
    ExecutionCheck Stage → ExecutionIntent → PermissionGateway → ExecutionContract → AgentExecutor

分离原则:
    - ExecutionCheck: 发现"需要做什么"
    - PermissionGateway: 判断"是否允许做"
    - Agent: 负责"怎么做"
"""

from __future__ import annotations

from typing import Protocol

from .builtin_policies import BuiltinPolicies
from .permission_request import PermissionContext, PermissionRequest
from .permission_trace import PermissionTrace
from .policy_decision import DecisionResult, PolicyDecision


class PermissionTraceConsumer(Protocol):
    """审计消费者协议 — 将 trace 写入存储。"""

    def consume(self, trace: PermissionTrace) -> None:
        ...


class PermissionGateway:
    """权限网关 — 免疫屏障。

    用法:
        gateway = PermissionGateway()
        decision, trace = gateway.evaluate(request, context)
        if decision.allowed:
            execute(capability)
    """

    def __init__(
        self,
        policies: BuiltinPolicies | None = None,
        trace_consumers: list[PermissionTraceConsumer] | None = None,
    ):
        self._policies = policies or BuiltinPolicies()
        self._trace_consumers: list[PermissionTraceConsumer] = trace_consumers or []
        self._trace_buffer: list[PermissionTrace] = []

    def evaluate(
        self,
        request: PermissionRequest,
        context: PermissionContext | None = None,
    ) -> tuple[PolicyDecision, PermissionTrace]:
        """评估权限请求并生成审计记录。

        Args:
            request: 权限请求
            context: 认知上下文 (optional for unit-test standalone)

        Returns:
            (decision, trace) — 决策 + 审计记录
        """
        context = context or PermissionContext()

        decision = self._policies.evaluate(request)
        trace = PermissionTrace.record(request, context, decision)

        # 审计记录
        if decision.audit_required:
            self._trace_buffer.append(trace)
            for consumer in self._trace_consumers:
                consumer.consume(trace)

        return decision, trace

    @property
    def trace_count(self) -> int:
        return len(self._trace_buffer)

    def flush_traces(self) -> list[PermissionTrace]:
        """导出并清空审计缓冲。"""
        traces = list(self._trace_buffer)
        self._trace_buffer.clear()
        return traces

    def last_trace(self) -> PermissionTrace | None:
        return self._trace_buffer[-1] if self._trace_buffer else None
