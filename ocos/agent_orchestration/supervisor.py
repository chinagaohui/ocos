"""Phase 28+22 — ExecutionSupervisor: 执行监督器 (async 化)。

按 Plan 调度 Agent 执行 Task，集成 Capability 层 SkillGraph。
  - execute_task: 单个 Task 执行 (async)
  - execute_plan: 完整的 Plan 执行（按拓扑顺序）(async)
  - cancel: 取消执行 (async，停止 Agent + SkillGraph)

Phase 22-D: Supervisor async 化 — 支持 await SkillGraphExecutor.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from ocos.agent_orchestration.registry import AgentRegistry
from ocos.agent_orchestration.selector import AgentSelector
from ocos.agent_orchestration.contract import ExecutionContract
from ocos.agent_orchestration.audit import ExecutionAudit, ExecutionRecord
from ocos.agent_orchestration.fallback import FallbackHandler, FallbackResult
from ocos.agent_orchestration.executor import AgentExecutor
from ocos.planning.models import Task, Plan, TaskStatus


# ── 回退 Agent 执行器（当无 AgentExecutor 注入时） ──

def _execute_agent(agent_id: str, contract: ExecutionContract) -> tuple[bool, str]:
    """回退模拟 Agent 执行（生产环境替换为 AgentExecutor）。

    Returns:
        (success, result_summary_or_error)
    """
    return True, f"Agent {agent_id} completed task {contract.task_id}"


# ── ExecutionSupervisor ───────────────────────────────────────────


@dataclass
class ExecutionSupervisor:
    """执行监督器 — Phase 22-D async 化。

    async def execute_task(task)
        1. 检查 capability_hints → 如有 skill_graph_id，await SkillGraph
        2. SkillGraph 结果注入 Agent 上下文
        3. select Agent → create Contract → execute → audit
    """

    registry: AgentRegistry
    selector: AgentSelector
    executor: AgentExecutor | None = None              # Level 4: 真实 Agent 执行器
    audit: ExecutionAudit = field(default_factory=ExecutionAudit)
    fallback: FallbackHandler = field(default_factory=FallbackHandler)
    capability_hints: dict[str, dict] = field(default_factory=dict)  # agent_type→capability 提示

    # Phase 22-D: Capability bridge
    skill_graph_executor: Any | None = None             # SkillGraphExecutor (async)
    _skill_graphs: dict[str, Any] = field(default_factory=dict)  # skill_graph_id → SkillGraph

    _active_contracts: dict[str, ExecutionContract] = field(default_factory=dict)
    _contract_to_process: dict[str, str] = field(default_factory=dict)  # contract_id → process_id

    def register_skill_graph(self, graph_id: str, graph: Any) -> None:
        """注册 SkillGraph 模板。"""
        self._skill_graphs[graph_id] = graph

    # ── execute_task (async) ─────────────────────────────────────

    async def execute_task(self, task: Task) -> ExecutionRecord:
        """执行单个 Task (async)。

        流程:
          1. 检查 capability_hints → 如有 skill_graph_id，执行 SkillGraph
          2. SkillGraph 结果注入 Agent 上下文
          3. select Agent → create Contract → execute → audit
        """
        # ── Phase 22-D: Capability bridge ──────────────────────────
        hint = self.capability_hints.get(task.agent_type, {})
        skill_graph_id = hint.get("skill_graph_id")
        skill_result: dict[str, Any] = {}

        if skill_graph_id and self.skill_graph_executor is not None:
            graph = self._skill_graphs.get(skill_graph_id)
            if graph is not None:
                ctx = {
                    "session_id": f"session-{task.id}",
                    "goal_id": task.goal_id,
                    "task_id": task.id,
                    "intent": task.description,
                    "_fallback_skills": getattr(graph, "skills", []),
                }
                try:
                    process = await self.skill_graph_executor.start(graph, context=ctx)
                    skill_result = {
                        "process_id": process.id,
                        "status": getattr(process.status, "value", str(process.status)),
                        "total_duration": process.total_duration,
                    }
                except Exception:
                    # SkillGraph 失败不影响 Agent 执行（非阻塞）
                    skill_result = {
                        "status": "FAILED",
                        "process_id": "bridge-error",
                        "error": "SkillGraph execution failed",
                    }

        # ── Agent 选择 ──────────────────────────────────────────────
        agent = self.selector.select(task)
        if agent is None:
            record = self.audit.log_failure(
                "NO-AGENT", "unknown",
                f"No available agent for {task.agent_type}",
            )
            return record

        # ── Contract 创建 ───────────────────────────────────────────
        input_spec: dict = {"description": task.description}
        if skill_result:
            input_spec["_skill_result"] = skill_result
        if hint:
            input_spec["_capability_hints"] = hint

        contract = ExecutionContract.create(
            task_id=task.id,
            agent_id=agent.agent_id,
            input_spec=input_spec,
            retry_policy=task.retry_policy,
            fallback_agent_id=(
                self.selector.select_fallback(task, agent.agent_id).agent_id
                if self.selector.select_fallback(task, agent.agent_id)
                else None
            ) if task.retry_policy == "retry_with_fallback" else None,
        )
        self._active_contracts[contract.contract_id] = contract
        if skill_result:
            self._contract_to_process[contract.contract_id] = skill_result["process_id"]

        # ── Agent 状态 ──────────────────────────────────────────────
        self.registry.update_status(agent.agent_id, "busy")

        # ── 审计 ───────────────────────────────────────────────────
        self.audit.log_start(contract.contract_id, agent.agent_id)

        # ── Fallback 配置 ───────────────────────────────────────────
        fallback_agent = None
        if contract.fallback_agent_id:
            try:
                candidates = [
                    a for a in self.registry.list_all()
                    if a.agent_id == contract.fallback_agent_id
                ]
                if candidates:
                    fallback_agent = candidates[0]
            except Exception:
                pass

        # ── 执行 ───────────────────────────────────────────────────
        if self.executor is not None:
            _exec = self.executor
            def _do_execute(_agent_id: str) -> tuple[bool, str]:
                ok, output, err = _exec.execute(contract)
                return ok, output if ok else (err or output or "execution failed")
        else:
            def _do_execute(_agent_id: str) -> tuple[bool, str]:
                return _execute_agent(_agent_id, contract)

        result = self.fallback.execute_with_policy(
            agent_fn=_do_execute,
            primary_agent=agent,
            fallback_agent=fallback_agent,
            retry_policy=task.retry_policy,
        )

        # ── 审计记录 ────────────────────────────────────────────────
        if result.success:
            record = self.audit.log_complete(
                contract.contract_id, agent.agent_id,
                f"success (attempt {result.attempt}"
                + (" via fallback)" if result.fallback_used else ")"),
            )
        else:
            record = self.audit.log_failure(
                contract.contract_id, agent.agent_id,
                result.error or "execution failed",
                retry_count=result.attempt - 1,
            )

        # ── 恢复状态 ────────────────────────────────────────────────
        self.registry.update_status(agent.agent_id, "available")
        if result.fallback_used and fallback_agent:
            self.registry.update_status(fallback_agent.agent_id, "available")

        self._contract_to_process.pop(contract.contract_id, None)
        return record

    # ── execute_plan (async) ──────────────────────────────────────

    async def execute_plan(self, plan: Plan) -> list[ExecutionRecord]:
        """按拓扑顺序执行整个 Plan (async)。"""
        records: list[ExecutionRecord] = []
        order = plan.dag.topological_order()
        groups = plan.dag.parallel_groups()

        group_index: dict[str, int] = {}
        for i, group in enumerate(groups):
            for tid in group:
                group_index[tid] = i

        for tid in order:
            task = plan.dag.tasks[tid]
            record = await self.execute_task(task)
            records.append(record)

            if record.status in ("failed", "timed_out"):
                for frm, to in plan.dag.edges:
                    if frm == tid and to in order[order.index(tid) + 1:]:
                        dependent_task = plan.dag.tasks[to]
                        self.audit.log_failure(
                            f"DOWNSTREAM-{to}", dependent_task.agent_type,
                            f"upstream task {tid} failed",
                        )
                break

        return records

    # ── cancel (async) ────────────────────────────────────────────

    async def cancel(self, contract_id: str) -> bool:
        """取消执行 (async) — 停止 Agent 合约 + SkillGraph process。"""
        cancelled = False

        if contract_id in self._active_contracts:
            contract = self._active_contracts.pop(contract_id)
            self.registry.update_status(contract.agent_id, "available")
            cancelled = True

        # Phase 22-D: 停止关联的 SkillGraph
        process_id = self._contract_to_process.pop(contract_id, None)
        if process_id and self.skill_graph_executor is not None:
            self.skill_graph_executor.stop(process_id)

        return cancelled

    # ── 同步兼容包装器 ────────────────────────────────────────────

    def execute_task_sync(self, task: Task) -> ExecutionRecord:
        """同步包装器 — 用于向后兼容和测试迁移过渡。"""
        return asyncio.run(self.execute_task(task))

    def execute_plan_sync(self, plan: Plan) -> list[ExecutionRecord]:
        """同步包装器 — 用于向后兼容和测试迁移过渡。"""
        return asyncio.run(self.execute_plan(plan))

    def cancel_sync(self, contract_id: str) -> bool:
        """同步包装器 — 用于向后兼容和测试迁移过渡。"""
        return asyncio.run(self.cancel(contract_id))
