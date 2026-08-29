"""Stage ⑦: Learning Trigger — 学习信号触发。

39.2: 发出 LEARNING_REQUIRED 信号，不执行学习。
Experience→Pattern→Knowledge 固化属于 MemoryHub Phase。
"""

from __future__ import annotations

from ..pipeline_protocol import TickStage
from ..tick_context import TickContext


class LearningTriggerStage:
    """学习触发阶段。

    39.2: 检查是否满足学习条件，触发信号。
    不执行 Memory Consolidation。
    """

    name = "LEARNING_TRIGGER"

    def execute(self, context: TickContext) -> TickContext:
        # 39.2: 无学习条件判断
        signals = ()
        return context.with_updates(
            learning_signals=signals
        ).with_stage_trace(self.name)
