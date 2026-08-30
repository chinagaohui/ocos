"""R4-A: 执行回路 — DecisionBridge (自治决策 → 真实任务执行铰链)。"""

from ocos.execution.bridge import (
    ActionVerdict,
    BridgeReport,
    DecisionBridge,
)

__all__ = ["DecisionBridge", "BridgeReport", "ActionVerdict"]
