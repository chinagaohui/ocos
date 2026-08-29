"""Phase 39.2: Pipeline Stage Implementations — 最小化，无 AI。

每个 Stage 实现 TickStage 协议。39.2 只建立 Pipeline 骨架:
    ① EventIngestion    — EventBus 接入占位
    ② Attention          — 注意力快照占位
    ③ MemorySync         — 工作记忆同步占位
    ④ GoalMaintenance    — Goal 状态刷新 (仅 refresh, 禁止 create)
    ⑤ ExecutionCheck     — 执行候选检查 (不调用 Agent)
    ⑥ ResultCollection   — 结果收集占位
    ⑦ LearningTrigger    — 学习信号触发 (不执行学习)
    ⑧ CheckpointDecision — checkpoint 决策

Governance:
    - Stage ④: SHALL NOT create Goal
    - Stage ⑤: SHALL NOT call Agent
    - All: SHALL NOT import ocos.self / ocos.runtime.runtime_kernel
"""

from .attention import AttentionStage
from .checkpoint_decision import CheckpointDecisionStage
from .event_ingestion import EventIngestionStage
from .execution_check import ExecutionCheckStage
from .goal_maintenance import GoalMaintenanceStage
from .learning_trigger import LearningTriggerStage
from .memory_sync import MemorySyncStage
from .result_collection import ResultCollectionStage

__all__ = [
    "EventIngestionStage",
    "AttentionStage",
    "MemorySyncStage",
    "GoalMaintenanceStage",
    "ExecutionCheckStage",
    "ResultCollectionStage",
    "LearningTriggerStage",
    "CheckpointDecisionStage",
]
