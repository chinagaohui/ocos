"""Phase 45: Capability Nervous System — 能力神经系统。

OCOS 控制身体的神经系统。

不是"工具调用"——而是:
    决策 → 选择能力 → 路由 → 适配 → 权限 → 执行 → 理解 → 验证 → 记忆

从 Phase 44 吸收的器官经由此系统被组织化调度。

核心边界:
    CNS45-01: Capability ≠ Authority        — 能力只是执行接口
    CNS45-02: Selector ≠ Decision            — 能力选择不替代决策
    CNS45-03: Agent ≠ Cognitive Entity       — 外部Agent是能力提供者
    CNS45-04: Execution ≠ Learning           — Result→Interpretation→Validation→Memory
"""

from ocos.capability.capability_types import (
    CapabilityType,
    CapabilityState,
    ExecutorKind,
    Capability,
    CapabilityMatch,
    SelectionResult,
    ExecutionRequest,
    ExecutionStatus,
    RawResult,
    InterpretedResult,
)

from ocos.capability.capability_registry import CapabilityRegistry
from ocos.capability.capability_graph import CapabilityGraph
from ocos.capability.capability_selector import CapabilitySelector
from ocos.capability.capability_router import CapabilityRouter
from ocos.capability.adapter_manager import AdapterManager
from ocos.capability.lifecycle_manager import LifecycleManager
from ocos.capability.execution_bridge import ExecutionBridge
from ocos.capability.result_interpreter import ResultInterpreter

__all__ = [
    # Types
    "CapabilityType",
    "CapabilityState",
    "ExecutorKind",
    "Capability",
    "CapabilityMatch",
    "SelectionResult",
    "ExecutionRequest",
    "ExecutionStatus",
    "RawResult",
    "InterpretedResult",
    # Engines
    "CapabilityRegistry",
    "CapabilityGraph",
    "CapabilitySelector",
    "CapabilityRouter",
    "AdapterManager",
    "LifecycleManager",
    "ExecutionBridge",
    "ResultInterpreter",
]
