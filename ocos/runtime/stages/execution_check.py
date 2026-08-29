"""Stage ⑤: Execution Check — 检查可执行任务。

39.2: 发现 execution_candidates，不调用 Agent。
Agent 调度属于后续 Phase。
"""

from __future__ import annotations

from ..pipeline_protocol import TickStage
from ..tick_context import TickContext


class ExecutionCheckStage:
    """执行检查阶段。

    允许:
        ✅ 检查是否有 pending task
        ✅ 生成 execution_candidates

    禁止:
        ❌ 调用 Agent.execute()
        ❌ 修改任务参数

    39.2: stub → GAP-P2-2 接线: 注入 TaskDAG 后 resolve_ready() 生成
    execution_candidates（ocos/task 首个生产消费者）。
    """

    name = "EXECUTION_CHECK"

    def __init__(self, gateway=None, task_dag=None):
        """39.3: 可选注入 PermissionGateway；GAP-P2-2: 可选注入 TaskDAG。

        如果不提供 gateway，执行检查只生成 candidates 不做权限过滤。
        Pipeline 负责在 candidates 生成后调用 gateway。
        不提供 task_dag → 无候选（降级）。
        """
        self._gateway = gateway
        self._task_dag = task_dag

    def execute(self, context: TickContext) -> TickContext:
        if self._task_dag is not None:
            candidates = tuple(self._task_dag.resolve_ready())
        else:
            candidates = ()

        # 39.3: 如果有 gateway 且有 candidates，过滤
        if self._gateway is not None and candidates:
            from ..permission import PermissionRequest, PermissionContext, Caller
            filtered = []
            for cand in candidates:
                req = PermissionRequest(
                    capability_id=getattr(cand, "capability_id", "unknown"),
                    action=getattr(cand, "action", "execute"),
                    caller=Caller.OCOS_EXECUTIVE,
                )
                ctx_p = PermissionContext(tick_id=context.tick_id)
                decision, _ = self._gateway.evaluate(req, ctx_p)
                if decision.allowed:
                    filtered.append(cand)
            candidates = tuple(filtered)

        return context.with_updates(
            execution_candidates=candidates
        ).with_stage_trace(self.name)
