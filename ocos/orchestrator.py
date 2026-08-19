"""ORCHESTRATOR — 能力编排系统命名空间桥接。

Orchestrator 根据 Goal 和 Attention 选择并调度 Capability，
管理执行流程、超时和结果聚合。
此文件从 ocos.capability.orchestrator 重新导出核心类，
提供 `from ocos.orchestrator import CapabilityOrchestrator` 的便捷导入路径。
"""

from ocos.capability.orchestrator import (
    OrchestrationResult,
    DispatchResult,
    CapabilityOrchestrator,
)

__all__ = [
    "OrchestrationResult",
    "DispatchResult",
    "CapabilityOrchestrator",
]
