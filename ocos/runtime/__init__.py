"""OCOS Runtime — Phase 39.3 Permission Integration.

Package: ocos.runtime
Version: 39.3
Status: RuntimeKernel + TickPipeline + PermissionGateway.

Exports:
    RuntimeKernel       — 心跳引擎 (start/run/stop/shutdown)
    RuntimeLoop         — 运行时主循环 (Phase M)
    Tick                — 不可变心跳帧
    TickPipeline        — 8 阶段编排引擎
    RuntimeState        — 生命周期状态
    LifecycleManager    — 状态转换控制
    CheckpointEngine    — 持久化快照
    RecoveryEngine      — 崩溃恢复
    CapabilityPolicyProvider — 策略提供者 (接入 PermissionGateway)
"""

from .capability_policy import CapabilityPolicyProvider
from .checkpoint import CheckpointEngine, CheckpointRecord
from .lifecycle import LifecycleManager, InvalidTransitionError
from .recovery_engine import RecoveryEngine, RecoveryResult
from .recovery.recovery_manager import RecoveryManager
from .runtime_kernel import RuntimeKernel
from .runtime_loop import RuntimeLoop, LoopMetrics, create_runtime_loop
from .runtime_state import RuntimeState, ALLOWED_TRANSITIONS
from .tick import Tick, tick_id_generator
from .pipeline import TickPipeline
from .pipeline_protocol import PipelineStage, TickStage
from .tick_context import TickContext

__all__ = [
    "RuntimeKernel",
    "RuntimeLoop",
    "LoopMetrics",
    "create_runtime_loop",
    "Tick",
    "TickPipeline",
    "TickStage",
    "TickContext",
    "PipelineStage",
    "RuntimeState",
    "LifecycleManager",
    "CheckpointEngine",
    "CheckpointRecord",
    "RecoveryEngine",
    "RecoveryResult",
    "RecoveryManager",
    "CapabilityPolicyProvider",
    "ALLOWED_TRANSITIONS",
    "tick_id_generator",
    "InvalidTransitionError",
]
