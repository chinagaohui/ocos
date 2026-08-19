"""Phase 23 — Skill Graph 异步执行器。

核心设计:
  1. 所有执行方法 async def（为未来异步 Engine 预留）
  2. Kahn 拓扑排序确保依赖顺序
  3. Fallback 策略（防 Workflow 退化）
  4. Meta Controller 干预信号（asyncio.Event）

Fallback 策略:
  - "abort": 失败即停止 Process（默认，Workflow 行为）
  - "retry": 重试 max_retries 次，指数退避
  - "skip": 跳过该 Skill，Process 继续（关键：此策略区分 SkillGraph ≠ Workflow）
  - "fallback:<id>": 切换到备用 Skill
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Optional

# 2026-08-17 健康化（Phase 22 G1.7 合规）：Bridge 仅 master_agent 私有——
# 这里只做类型标注（TYPE_CHECKING），不产生运行时导入耦合；
# bridge 实例由调用方注入（依赖倒置）。
if TYPE_CHECKING:
    from ocos.agent.cognitive_bridge import BridgeResult, CognitiveBridge

from ocos.capability.models import (
    CyclicDependencyError,
    ProcessGraph,
    Skill,
    SkillExecutionRecord,
    SkillGraph,
    SkillStatus,
)


class SkillGraphExecutor:
    """Skill Graph 异步执行器。

    用法:
        # bridge 由 MasterAgent 注入（不在此构造——G1.7 Bridge 私有）
        executor = SkillGraphExecutor(bridge)
        process = await executor.start(skill_graph, context={...})
    """

    def __init__(
        self,
        bridge: "CognitiveBridge",
        meta_controller: Optional[Any] = None,
    ):
        self._bridge = bridge
        self._meta_controller = meta_controller
        self._running_processes: dict[str, ProcessGraph] = {}
        self._stop_events: dict[str, asyncio.Event] = {}

    # ── 启动 / 停止 ─────────────────────────────────────────────────────

    async def start(
        self,
        skill_graph: SkillGraph,
        context: Optional[dict[str, Any]] = None,
    ) -> ProcessGraph:
        """启动 Skill Graph 执行。

        Args:
            skill_graph: 要执行的 SkillGraph
            context: 执行上下文（session_id, goal_id 等）

        Returns:
            执行完成的 ProcessGraph
        """
        ctx = context or {}
        stop_event = asyncio.Event()

        process = ProcessGraph(
            id=f"process-{uuid.uuid4().hex[:8]}",
            skill_graph_id=skill_graph.id,
            session_id=ctx.get(
                "session_id", f"session-{uuid.uuid4().hex[:8]}"
            ),
            status=SkillStatus.RUNNING,
            start_time=datetime.now(timezone.utc),
            context=ctx,
        )

        self._running_processes[process.id] = process
        self._stop_events[process.id] = stop_event

        try:
            await self._execute_skills(process, skill_graph, stop_event)
        except Exception as e:
            process.status = SkillStatus.FAILED
            process.error_log.append({
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
        finally:
            now = datetime.now(timezone.utc)
            process.last_update = now
            if process.start_time:
                process.total_duration = (
                    now - process.start_time
                ).total_seconds()
            self._running_processes.pop(process.id, None)
            self._stop_events.pop(process.id, None)

        if process.status not in (
            SkillStatus.FAILED,
            SkillStatus.CANCELLED,
        ):
            process.status = SkillStatus.COMPLETED

        return process

    def stop(self, process_id: str) -> bool:
        """Meta Controller 发送停止信号。

        Returns:
            True 如果找到了对应的 process
        """
        if process_id in self._stop_events:
            self._stop_events[process_id].set()
            return True
        return False

    def get_process(self, process_id: str) -> Optional[ProcessGraph]:
        """查询正在运行的 Process。"""
        return self._running_processes.get(process_id)

    # ── 内部执行 ────────────────────────────────────────────────────────

    async def _execute_skills(
        self,
        process: ProcessGraph,
        skill_graph: SkillGraph,
        stop_event: asyncio.Event,
    ) -> None:
        """按拓扑顺序执行所有 Skill。"""
        # 验证 SkillGraph
        violations = skill_graph.validate()
        if violations:
            process.status = SkillStatus.FAILED
            process.error_log.append({
                "error": f"SkillGraph validation failed: {violations}",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            return

        try:
            order = skill_graph.get_dependency_order()
        except CyclicDependencyError as e:
            process.status = SkillStatus.FAILED
            process.error_log.append({
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            return

        # 按拓扑序执行
        for skill_id in order:
            # 检查停止信号
            if stop_event.is_set():
                process.status = SkillStatus.CANCELLED
                process.error_log.append({
                    "error": "Execution cancelled by stop signal",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
                break

            skill = skill_graph.get_skill(skill_id)
            if skill is None:
                continue

            # 执行单个 Skill（含 Fallback）
            record = await self._execute_skill_with_fallback(
                skill, process, stop_event
            )
            process.add_record(record)

            if record.status == SkillStatus.FAILED:
                # 以下策略在失败时标记 Process 为 FAILED:
                #   - abort: 默认，立即停止
                #   - retry: 所有重试已耗尽
                #   - fallback:<id>: 备用 Skill 也失败了
                if skill.fallback_strategy in ("abort", "retry"):
                    process.status = SkillStatus.FAILED
                    break
                elif skill.fallback_strategy.startswith("fallback:"):
                    # fallback 也失败了（已记录在 record 中）
                    process.status = SkillStatus.FAILED
                    break

            # Meta Controller 监控
            if self._meta_controller:
                intervention = self._meta_controller.monitor(process)
                if hasattr(intervention, "decision"):
                    if intervention.decision == "abort":
                        process.status = SkillStatus.FAILED
                        process.error_log.append({
                            "error": f"MetaController abort: {intervention.interventions}",
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        })
                        break
                    elif intervention.decision == "warn":
                        process.error_log.append({
                            "warning": intervention.interventions,
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        })

    async def _execute_skill_with_fallback(
        self,
        skill: Skill,
        process: ProcessGraph,
        stop_event: asyncio.Event,
    ) -> SkillExecutionRecord:
        """执行单个 Skill，含 Fallback 逻辑。

        Fallback 策略:
          - "abort": 失败即停止
          - "retry": 重试 max_retries 次（指数退避）
          - "skip": 跳过该 Skill，标记为 SKIPPED
          - "fallback:<id>": 切换到备用 Skill
        """
        retries = 0
        max_retries = (
            skill.max_retries if skill.fallback_strategy == "retry" else 0
        )

        while True:
            # 检查停止信号
            if stop_event.is_set():
                return SkillExecutionRecord(
                    skill_id=skill.id,
                    skill_name=skill.name,
                    status=SkillStatus.CANCELLED,
                    error="Execution cancelled",
                    input=process.context,
                    started_at=datetime.now(timezone.utc),
                    completed_at=datetime.now(timezone.utc),
                )

            record = await self._execute_skill(skill, process.context)
            record.attempt = retries + 1

            if record.status == SkillStatus.COMPLETED:
                return record

            # ── 失败处理 ────────────────────────────────────────────

            # retry
            if retries < max_retries:
                retries += 1
                backoff = 0.1 * (2 ** retries)  # 指数退避
                await asyncio.sleep(backoff)
                continue

            # skip — 关键：失败不停止 Process
            if skill.fallback_strategy == "skip":
                record.status = SkillStatus.SKIPPED
                record.output = {
                    "skipped": True,
                    "original_error": record.error,
                }
                record.completed_at = datetime.now(timezone.utc)
                return record

            # fallback:<id>
            if skill.fallback_strategy.startswith("fallback:"):
                fallback_id = skill.fallback_strategy.split(":", 1)[1]
                fallback_skills: list = process.context.get(
                    "_fallback_skills", []
                )
                fallback_skill = next(
                    (s for s in fallback_skills if s.id == fallback_id), None
                )
                if fallback_skill:
                    fallback_record = (
                        await self._execute_skill_with_fallback(
                            fallback_skill, process, stop_event
                        )
                    )
                    # 保留原始 skill 的元信息，但用 fallback 的结果
                    fallback_record.skill_id = skill.id
                    fallback_record.skill_name = (
                        f"{skill.name} (fallback: {fallback_skill.name})"
                    )
                    return fallback_record

            # abort（默认）
            return record

    async def _execute_skill(
        self, skill: Skill, context: dict[str, Any]
    ) -> SkillExecutionRecord:
        """执行单个 Skill（实际调用 Bridge）。

        注意: Bridge 方法是同步的，不阻塞 Event Loop。
        """
        start = datetime.now(timezone.utc)
        record = SkillExecutionRecord(
            skill_id=skill.id,
            skill_name=skill.name,
            status=SkillStatus.RUNNING,
            input={
                k: context.get(k)
                for k in skill.input_state
                if k in context
            },
            started_at=start,
        )

        try:
            result = self._route_to_engine(skill, context)

            if result.success:
                record.status = SkillStatus.COMPLETED
                record.output = result.data
            else:
                record.status = SkillStatus.FAILED
                record.error = result.message or "; ".join(result.errors)
        except Exception as e:
            record.status = SkillStatus.FAILED
            record.error = str(e)

        record.duration = (
            datetime.now(timezone.utc) - start
        ).total_seconds()
        record.completed_at = datetime.now(timezone.utc)
        return record

    def _route_to_engine(
        self, skill: Skill, context: dict[str, Any]
    ) -> "BridgeResult":
        """路由到对应的 Engine。

        所有调用通过 CognitiveBridge，保持 Phase 22 边界约束。
        """
        capability = skill.required_capability

        if capability == "reasoning":
            return self._bridge.reason(
                premises=context.get("premises"),
            )
        elif capability == "planning":
            return self._bridge.plan(
                strategy=context.get("strategy", "top_down"),
                inputs=context.get("inputs"),
            )
        elif capability == "decision":
            return self._bridge.decide(
                strategy=context.get("strategy", "scoring"),
                options=context.get("options"),
                context=context.get("decision_context"),
            )
        elif capability == "reflection":
            return self._bridge.reflect(
                subject_type=context.get("subject_type", "action_result"),
                subject_id=context.get("subject_id", ""),
                strategy=context.get("strategy", "standard"),
            )
        elif capability == "learning":
            return self._bridge.learn(
                model=context.get("model"),
                examples=context.get("examples"),
                strategy=context.get("strategy", "supervised"),
            )
        else:
            return BridgeResult(
                success=False,
                message=f"Unknown capability: {capability}",
                errors=[f"no handler for capability '{capability}'"],
            )
