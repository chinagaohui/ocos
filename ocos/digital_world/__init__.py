"""Phase 29 — Digital World Interface 层。

让 OCOS 操作数字环境: 文件/Git/API/搜索/数据库/沙箱。

宪法约束:
  1. ALL_OPERATIONS_AUDITED
  2. SINGLE_AUTHORITY (MasterAgent 审批)
  3. NO_PHYSICAL_WORLD
  4. FAILURE_TO_DLQ
  5. RESOURCE_LIMITS

导入规则:
  ✅ ocos.agent
  ✅ ocos.planning
  ❌ ocos.self (宪法禁止)
"""

from ocos.digital_world.base import DigitalOperation, OperationResult, AuditRecord
from ocos.digital_world.auditor import OperationAuditor
from ocos.digital_world.dlq import DeadLetterQueue, DLQEntry

__all__ = [
    "DigitalOperation",
    "OperationResult",
    "AuditRecord",
    "OperationAuditor",
    "DeadLetterQueue",
    "DLQEntry",
]
