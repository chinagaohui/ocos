"""Phase 39.2: Tick Pipeline Stage ABI — 不可变流水线协议。

定义 Pipeline Stage 的边界契约。每个 Stage:
    - 输入: TickContext
    - 输出: 新的 TickContext
    - 约束: 不持有任何引用（无状态 Stage），不 import RuntimeKernel/Agent/Self

8 阶段固定顺序 (RUNTIME_ABI §Tick Pipeline):
    ① EVENT_INGESTION     — 外部/内部/定时器事件读取
    ② ATTENTION           — 注意力快照 (当前焦点)
    ③ MEMORY_SYNC         — 工作记忆同步
    ④ GOAL_MAINTENANCE    — Goal 状态刷新 (禁止创建新 Goal)
    ⑤ EXECUTION_CHECK     — 检查可执行任务 (不调用 Agent)
    ⑥ RESULT_COLLECTION   — 收集执行结果
    ⑦ LEARNING_TRIGGER    — 学习信号触发 (不执行学习)
    ⑧ CHECKPOINT_DECISION — checkpoint 决策

Governance Freeze (Phase 38):
    - Stage ④ GOAL_MAINTENANCE: 仅 refresh(), 禁止 create()
    - Stage ⑤ EXECUTION_CHECK: 不调用 Agent
    - 所有 Stage 不得 import ocos.self
"""

from __future__ import annotations

from enum import Enum
from typing import Protocol, runtime_checkable

from .tick_context import TickContext


# ═══════════════════════════════════════════════════════════════════════════
# Pipeline Stage Order (frozen)
# ═══════════════════════════════════════════════════════════════════════════

class PipelineStage(Enum):
    """Tick Pipeline 8 阶段冻结顺序。"""
    EVENT_INGESTION = 1
    ATTENTION = 2
    MEMORY_SYNC = 3
    GOAL_MAINTENANCE = 4
    EXECUTION_CHECK = 5
    RESULT_COLLECTION = 6
    LEARNING_TRIGGER = 7
    CHECKPOINT_DECISION = 8

    @property
    def next(self) -> PipelineStage | None:
        stages = list(PipelineStage)
        idx = stages.index(self)
        return stages[idx + 1] if idx + 1 < len(stages) else None


# ═══════════════════════════════════════════════════════════════════════════
# Stage ABI (Protocol)
# ═══════════════════════════════════════════════════════════════════════════

@runtime_checkable
class TickStage(Protocol):
    """Pipeline Stage 接口协议。

    每个 Stage 必须实现:
        - name: 阶段标识
        - execute(context) -> TickContext: 不可变转换
    """

    name: str

    def execute(self, context: TickContext) -> TickContext:
        """执行此 Stage 并返回更新后的 TickContext。

        约束:
            - 不得修改传入的 context (传入的是 frozen)
            - 必须返回新的 TickContext
            - 不得 import ocos.runtime.runtime_kernel (防止循环)
            - 不得 import ocos.self (Identity Sovereignty)
        """
        ...
