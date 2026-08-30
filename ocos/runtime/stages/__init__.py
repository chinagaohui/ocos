"""Phase 39.2: Pipeline Stage Implementations — 最小化，无 AI。

每个 Stage 实现 TickStage 协议。GAP-P2-2 (2026-08-29) 后 8 个 Stage
全部为真实现；"占位"描述已过时。可选依赖缺省 = 诚实降级，非占位:
    ① EventIngestion    — 注入 EventBus 的积压事件 drain（缺省 None → 空事件）
    ② Attention          — 注意力评分/切换（CandidateCollector + ScoringEngine）
    ③ MemorySync         — MemoryHub 状态快照注入 TickContext
    ④ GoalMaintenance    — Goal 状态刷新 (仅 refresh, 禁止 create)
    ⑤ ExecutionCheck     — 可选 TaskDAG resolve_ready 候选 + PermissionGateway 过滤
                           （pipeline 默认不传 DAG → 空候选，诚实降级）
    ⑥ ResultCollection   — ExecutionManager 最近执行历史转发
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
