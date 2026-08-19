"""Phase 28 — Agent Orchestration 层。

导入规则:
  ✅ ocos.agent
  ✅ ocos.planning
  ✅ ocos.goal
  ❌ ocos.self (宪法禁止)
"""

from ocos.agent_orchestration.registry import AgentDescriptor, AgentRegistry
from ocos.agent_orchestration.selector import AgentSelector
from ocos.agent_orchestration.contract import ExecutionContract
from ocos.agent_orchestration.supervisor import ExecutionSupervisor
from ocos.agent_orchestration.executor import AgentExecutor
from ocos.agent_orchestration.audit import ExecutionAudit
from ocos.agent_orchestration.fallback import FallbackHandler

__all__ = [
    "AgentDescriptor",
    "AgentRegistry",
    "AgentSelector",
    "ExecutionContract",
    "ExecutionSupervisor",
    "AgentExecutor",
    "ExecutionAudit",
    "FallbackHandler",
]
