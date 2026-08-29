"""Phase 39.2: TickPipeline — 心跳编排引擎。

TickPipeline = 编排层，不是智能层。
按固定顺序调用 8 个 Stage，形成不可变流水线。

职责:
    - 按 PipelineStage 顺序执行各个 Stage
    - 每个 Stage: TickContext → TickContext (不可变)
    - Stage 失败 → SAFE MODE transition signal
    - 记录 stage trace 以便 replay

禁止:
    - Pipeline 不思考、不决策、不生成 Goal
    - 不 import ocos.self / ocos.runtime.runtime_kernel
"""

from __future__ import annotations

import time
from typing import Any, Callable, Optional

from .pipeline_protocol import PipelineStage, TickStage
from .stages import (
    AttentionStage,
    CheckpointDecisionStage,
    EventIngestionStage,
    ExecutionCheckStage,
    GoalMaintenanceStage,
    LearningTriggerStage,
    MemorySyncStage,
    ResultCollectionStage,
)
from .tick_context import TickContext, create_tick_context


class PipelineError(Exception):
    """Pipeline 执行异常。"""


class TickPipeline:
    """Tick Pipeline 编排器。

    39.2: 固定 8 阶段顺序，不可配置。
    39.3: PermissionGateway 在此接入。

    用法:
        pipeline = TickPipeline()
        ctx = pipeline.execute_tick(tick_id=1, runtime_state="running")
        print(ctx.stage_traces)
        # ('EVENT_INGESTION', 'ATTENTION', ..., 'CHECKPOINT_DECISION')
    """

    # 冻结的 Stage 顺序 (按 PipelineStage 数值排序)
    STAGE_ORDER: tuple[PipelineStage, ...] = tuple(
        sorted(PipelineStage, key=lambda s: s.value)
    )

    def __init__(self):
        self._stages: dict[PipelineStage, TickStage] = {
            PipelineStage.EVENT_INGESTION: EventIngestionStage(),
            PipelineStage.ATTENTION: AttentionStage(),
            PipelineStage.MEMORY_SYNC: MemorySyncStage(),
            PipelineStage.GOAL_MAINTENANCE: GoalMaintenanceStage(),
            PipelineStage.EXECUTION_CHECK: ExecutionCheckStage(),
            PipelineStage.RESULT_COLLECTION: ResultCollectionStage(),
            PipelineStage.LEARNING_TRIGGER: LearningTriggerStage(),
            PipelineStage.CHECKPOINT_DECISION: CheckpointDecisionStage(),
        }
        # 39.2: 可注册自定义 Stage（测试用）
        self._overrides: dict[PipelineStage, TickStage] = {}
        # 39.3 (P1-C): Agent driver — 注入式业务体驱动，不改变 Stage 冻结顺序。
        # driver 在 8 个 stage 之后、COMPLETE 之前执行；未 attach 时为空心跳。
        self._agent_driver: Optional[Callable[[int], dict[str, Any]]] = None
        self._last_agent_result: Optional[dict[str, Any]] = None

    def attach_agent_driver(self, driver: Optional[Callable[[int], dict[str, Any]]]) -> None:
        """注入 Agent 业务驱动（P1-C 循环收敛）。

        driver(tick_id) → dict。Pipeline 每 tick 在 8 个 stage 后调用一次。
        注入式设计: Pipeline 不 import ocos.agent，保持 R39-203 隔离。
        """
        self._agent_driver = driver

    @property
    def last_agent_result(self) -> Optional[dict[str, Any]]:
        """最近一次 agent driver 的执行结果（未 attach 时为 None）。"""
        return self._last_agent_result

    def register_stage(self, stage_enum: PipelineStage, stage: TickStage):
        """注册/覆盖 Stage（测试/扩展用）。"""
        self._overrides[stage_enum] = stage

    def _get_stage(self, stage_enum: PipelineStage) -> TickStage:
        return self._overrides.get(stage_enum, self._stages[stage_enum])

    def execute_tick(
        self,
        tick_id: int,
        runtime_state: str = "running",
    ) -> TickContext:
        """执行一次完整心跳。

        Args:
            tick_id: 当前 tick 序号
            runtime_state: RuntimeState 值

        Returns:
            最终的 TickContext（包含所有 stage trace）

        Pipeline 顺序 (冻结):
            EVENT_INGESTION → ATTENTION → MEMORY_SYNC → GOAL_MAINTENANCE →
            EXECUTION_CHECK → RESULT_COLLECTION → LEARNING_TRIGGER →
            CHECKPOINT_DECISION
        """
        ctx = create_tick_context(
            tick_id=tick_id,
            runtime_state=runtime_state,
        )

        for stage_enum in self.STAGE_ORDER:
            stage = self._get_stage(stage_enum)
            try:
                ctx = stage.execute(ctx)
            except Exception as e:
                raise PipelineError(
                    f"Stage {stage_enum.name} failed at tick {tick_id}: {e}"
                ) from e

        # 39.3 (P1-C): Agent driver — 业务体驱动（8 stage 之后、COMPLETE 之前）。
        # 未 attach 时跳过，保持空系统心跳语义（R39-202）。
        if self._agent_driver is not None:
            try:
                self._last_agent_result = self._agent_driver(tick_id)
            except Exception as e:
                raise PipelineError(
                    f"Agent driver failed at tick {tick_id}: {e}"
                ) from e

        # Mark completion
        ctx = ctx.with_updates(completed_at=time.time()).with_stage_trace("COMPLETE")

        return ctx

    @property
    def stage_count(self) -> int:
        return len(self.STAGE_ORDER)

    def stage_names(self) -> tuple[str, ...]:
        return tuple(s.name for s in self.STAGE_ORDER)
