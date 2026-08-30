"""Phase 29 — Digital World Interface 层。

让 OCOS 操作数字环境: 文件/Git/API/搜索/数据库/沙盒。

分工裁决（AUD-F5, 2026-08-30）:
    本包 = 面向"数字世界"语义的宽操作库（默认 dry_run，DLQ 审计）。
    ocos/operations/（Phase 22-E）= 高危操作的安全执行闸门
    （命令黑名单+白名单+路径沙盒+URL 白名单，真实执行），
    定位为 DecisionBridge 高危能力（shell/HTTP）经 ASK 批准后的执行层候选。
    两者分工不合并，接线时按语义选择。

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
