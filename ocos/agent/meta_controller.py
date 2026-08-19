"""MetaController — 向后兼容别名。

Phase 22-D: 已重命名为 ExecutiveController。
此模块保留作为过渡期兼容性别名，指向新文件。
新代码请 import: from ocos.agent.executive_controller import ExecutiveController
"""

from ocos.agent.executive_controller import (  # noqa: F401
    ExecutiveController,
    MetaController,           # 旧名别名
    CycleRecord,
    IntentAnalysis,
    Strategy,
    CapabilityPlan,
)
