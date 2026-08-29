"""OCOS Runtime Recovery — Phase 39.4 Cognitive Recovery & Continuity.

恢复子系统: Runtime 完整化的最后一块基础设施。
从"可运行系统"进入"可长期存在系统"。

Modules:
    RuntimeSnapshot      — 系统生命状态快照
    EventReplay          — 事件日志 + 重放引擎
    ExecutionRecovery    — 执行账本 + 去重
    PermissionRecovery   — 待审批持久化
    IntegrityVerifier    — 恢复前一致性检查
    CognitiveStateRestore — 完整恢复流程
    RecoveryManager      — 编排所有子系统的总入口
"""

from .cognitive_restore import CognitiveStateRestore, RestoreResult
from .event_replay import CognitiveEvent, EventLog, EventReplayEngine, EventType
from .execution_recovery import ExecutionLedger, ExecutionRecord, ExecutionStatus
from .integrity_verifier import IntegrityReport, IntegrityVerifier
from .permission_recovery import ApprovalStatus, ApprovalStore, PendingApproval
from .recovery_manager import RecoveryManager
from .runtime_snapshot import RuntimeSnapshot, SnapshotReason, SnapshotStore

__all__ = [
    "RecoveryManager",
    "RuntimeSnapshot",
    "SnapshotReason",
    "SnapshotStore",
    "CognitiveEvent",
    "EventType",
    "EventLog",
    "EventReplayEngine",
    "ExecutionRecord",
    "ExecutionStatus",
    "ExecutionLedger",
    "PendingApproval",
    "ApprovalStatus",
    "ApprovalStore",
    "IntegrityReport",
    "IntegrityVerifier",
    "CognitiveStateRestore",
    "RestoreResult",
]
