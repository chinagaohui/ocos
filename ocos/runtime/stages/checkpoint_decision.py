"""Stage ⑧: Checkpoint Decision — 检查点决策。

39.2: 根据 tick_id 和条件决定是否创建 checkpoint。
继承 39.1 的每 10 tick checkpoint 策略。
"""

from __future__ import annotations

from ..pipeline_protocol import TickStage
from ..tick_context import TickContext


class CheckpointDecisionStage:
    """Checkpoint 决策阶段。

    39.2: 保持简单的周期性 checkpoint 策略。
    Decision → RuntimeKernel 执行 (由 Pipeline 返回 flag)。
    """

    name = "CHECKPOINT_DECISION"

    def execute(self, context: TickContext) -> TickContext:
        # 每 10 tick 或 shutdown 时 checkpoint
        should_checkpoint = (context.tick_id % 10 == 0)
        return context.with_updates(
            checkpoint_decision=should_checkpoint
        ).with_stage_trace(self.name)
