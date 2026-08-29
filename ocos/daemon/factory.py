"""ocos.daemon.factory — 生产装配层（P1-B import 规则合规）。

将 CLI 入口的组件组装逻辑下沉到 daemon 包，使
ocos.interaction.cli.commands 只依赖 ocos.daemon 门面，
不再直连 agent/capability/runtime 内核组件（宪法 import 规则）。

用法:
    from ocos.daemon.factory import build_master_agent
    agent = build_master_agent(agent_id="ocos")
"""

from __future__ import annotations


def build_master_agent(agent_id: str):
    """组装真实组件 MasterAgent — 全部生产实现，零 Mock。"""
    from ocos.agent.capability_manager import CapabilityManager
    from ocos.agent.execution_manager import ExecutionManager
    from ocos.agent.goal_stack import GoalStack
    from ocos.agent.intent import Intent
    from ocos.agent.master_agent import MasterAgent
    from ocos.agent.state import AgentState
    from ocos.capability.attention import CognitiveAttentionController
    from ocos.runtime.context_manager import WorkingMemory
    from ocos.self.identity_boundary import IdentityBoundary

    return MasterAgent(
        agent_id=agent_id,
        identity=IdentityBoundary.create_default(),
        goal_stack=GoalStack(),
        intent=Intent(),
        attention=CognitiveAttentionController(),
        working_memory=WorkingMemory(),
        capability_manager=CapabilityManager(),
        execution_manager=ExecutionManager(),
        state=AgentState(),
    )
