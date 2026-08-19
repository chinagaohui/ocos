"""Phase 46: Cognitive Operating Loop Integration — 认知运行循环集成。

将 Phase 39-45 所有器官连接成稳定运行的个人智能循环。

不是制造新器官——而是让已有器官协同工作，形成完整的认知生命循环。

完整闭环:
    Perception → Attention → Context → Decision → Action → Learning → Memory
         ↑                                                        │
         └──────────────────── (next tick) ───────────────────────┘

核心边界:
    CL46-01: Loop ≠ Autonomy       — 循环是协同机制，不是自我设定目标
    CL46-02: Health ≠ Self-Rewrite — 发现问题 ≠ 重新定义自身
    CL46-03: Perception ≠ Truth    — 感知是信号，不是客观事实
    CL46-04: Learning ≠ Drift      — 学习有边界，不漂移 Identity/Constitution
"""

from ocos.cognitive_loop.loop_types import (
    LoopPhase,
    TickOutcome,
    LoopContext,
    HealthSignal,
    ModuleHealth,
    CognitiveHealthReport,
)
from ocos.cognitive_loop.perception_bridge import (
    PerceptionMode, PerceptionEvent, PerceptionBridge,
)
from ocos.cognitive_loop.attention_coordinator import (
    AttentionFocus, AttentionCoordinator,
)
from ocos.cognitive_loop.context_synchronizer import ContextSynchronizer
from ocos.cognitive_loop.decision_pipeline import DecisionPipeline
from ocos.cognitive_loop.action_controller import (
    ActionOutcome, ActionController,
)
from ocos.cognitive_loop.learning_coordinator import (
    ConsolidationResult, LearningCoordinator,
)
from ocos.cognitive_loop.health_monitor import HealthMonitor
from ocos.cognitive_loop.loop_orchestrator import LoopOrchestrator

__all__ = [
    # Types
    "LoopPhase",
    "TickOutcome",
    "LoopContext",
    "HealthSignal",
    "ModuleHealth",
    "CognitiveHealthReport",
    "PerceptionMode",
    "PerceptionEvent",
    "ActionOutcome",
    "ConsolidationResult",
    # Bridges & Coordinators
    "PerceptionBridge",
    "AttentionCoordinator",
    "AttentionFocus",
    "ContextSynchronizer",
    "DecisionPipeline",
    "ActionController",
    "LearningCoordinator",
    # System
    "HealthMonitor",
    "LoopOrchestrator",
]
