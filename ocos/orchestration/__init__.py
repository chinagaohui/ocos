"""Phase N: Orchestration — Agent 调度层整合。

L2 沉睡支线归档（2026-09-07, 升级方案 v1.0 §L2）:
    dormant=true — 全仓零生产引用（无 daemon/agent/interaction 装配点）。
    调度职责已由 ocos.runtime.scheduler（B3）+ ocos.daemon 目标队列承担，
    本包无独立价值；保留待 L3 MotivationHub 评估是否复用其评分逻辑。
"""

from .engine import (
    OrchestrationEngine,
    OrchestrationState,
    OrchestrationMetrics,
    create_orchestration_engine,
)

__all__ = [
    "OrchestrationEngine",
    "OrchestrationState",
    "OrchestrationMetrics",
    "create_orchestration_engine",
]
