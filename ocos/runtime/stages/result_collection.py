"""Stage ⑥: Result Collection — 收集执行结果。

39.2: stub → GAP-P2-2 接线：从 ExecutionManager 收集最近执行结果。

GAP-P2-2 决策（记录于 docs/OCOS_AUDIT_KERNEL.md）:
RuntimeKernel 不持有 ExecutionManager 实例（agent/execution_manager 属于
AgentRuntime 侧）；stage 收敛为转发语义——注入 execution_manager 后取
get_history() 作为 execution_results 注入 context（只读转发，不消费、
不清空历史）。无注入 → 空（降级）。
"""

from __future__ import annotations

from typing import Any, Optional

from ..pipeline_protocol import TickStage
from ..tick_context import TickContext


class ResultCollectionStage:
    """结果收集阶段。"""

    name = "RESULT_COLLECTION"

    def __init__(self, execution_manager: Any = None, history_limit: int = 20) -> None:
        """注入 ExecutionManager（ocos/agent/execution_manager.ExecutionManager）。"""
        self._execution_manager = execution_manager
        self._history_limit = history_limit

    def execute(self, context: TickContext) -> TickContext:
        """转发 ExecutionManager 最近执行历史（GAP-P2-2 接线）。"""
        if self._execution_manager is not None:
            results = tuple(
                self._execution_manager.get_history(limit=self._history_limit)
            )
        else:
            results = ()
        return context.with_updates(
            execution_results=results
        ).with_stage_trace(self.name)
