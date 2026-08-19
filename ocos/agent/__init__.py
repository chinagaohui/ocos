"""OCOS Agent — 认知主体包。

Agent 是整个 OCOS 的唯一意识主体。所有 Engine 是器官，Agent 是主人。

内置子系统：
- AgentState — Agent 状态机（INIT→BOOT→IDLE→...→SHUTDOWN）
- MasterAgent — 认知核心（boot/wake/observe/think/decide/act/reflect/learn/sleep/dream）
- IdentityAnchor — 身份锚点（BOOT 顺序第一个）
- GoalStack — 6 级目标栈（MISSION→LONG→MID→SHORT→TASK→ACTION）
- Goal (types) — 目标类型定义
- Intent — 意图提取
- Attention — 注意力管理器
- AgentWorkingMemory — 工作记忆（意识内容）
- EpisodeMemory — 情景记忆（经历片段）
- CapabilityManager — 能力列表
- ExecutionManager — 执行跟踪
- LifeCycleOrchestrator — 生命周期编排器
"""

from ocos.agent.state import AgentState, AgentStatus
from ocos.agent.master_agent import MasterAgent
from ocos.agent.interfaces import (
    IdentityAnchorProtocol,
    GoalStackProtocol,
    IntentProtocol,
    AttentionProtocol,
    WorkingMemoryProtocol,
    CapabilityManagerProtocol,
    ExecutionManagerProtocol,
)
from ocos.agent.goal_types import Goal, GoalLevel, GoalStatus
from ocos.agent.goal_stack import GoalStack
from ocos.agent.intent import Intent
from ocos.agent.attention import Attention, FocusMode
from ocos.agent.working_memory import AgentWorkingMemory, WorkItem
from ocos.agent.episode_memory import EpisodeMemory, Episode
from ocos.agent.capability_manager import CapabilityManager
from ocos.agent.execution_manager import ExecutionManager
from ocos.agent.identity_anchor import IdentityAnchor
from ocos.agent.life_cycle_orchestrator import LifeCycleOrchestrator, TickResult
from ocos.agent.capability_selector import CapabilitySelector
from ocos.agent.meta_controller import MetaController
from ocos.agent.decision_loop import DecisionLoop
from ocos.agent.cortex_activator import CortexActivator, CortexMode
from ocos.agent.belief_system import BeliefSystem, BeliefSource, Belief
from ocos.agent.memory_consolidator import MemoryConsolidator, MemoryLevel, MemoryItem
from ocos.agent.knowledge_base import KnowledgeBase, KnowledgeTriple
from ocos.agent.experience_store import ExperienceStore, Experience
from ocos.agent.agent_runtime import AgentRuntime, RuntimeState
from ocos.agent.engine_bridge import EngineBridge, EngineAdapter

__all__ = [
    # State
    "AgentState",
    "AgentStatus",
    # Core
    "MasterAgent",
    # Protocols
    "IdentityAnchorProtocol",
    "GoalStackProtocol",
    "IntentProtocol",
    "AttentionProtocol",
    "WorkingMemoryProtocol",
    "CapabilityManagerProtocol",
    "ExecutionManagerProtocol",
    # Goals
    "Goal",
    "GoalLevel",
    "GoalStatus",
    "GoalStack",
    # Intent
    "Intent",
    # Attention
    "Attention",
    "FocusMode",
    # Memory
    "AgentWorkingMemory",
    "WorkItem",
    "EpisodeMemory",
    "Episode",
    # Management
    "CapabilityManager",
    "ExecutionManager",
    # Identity
    "IdentityAnchor",
    # Life Cycle
    "LifeCycleOrchestrator",
    "TickResult",
    # Cog Cortex
    "CapabilitySelector",
    "MetaController",
    "DecisionLoop",
    "CortexActivator",
    "CortexMode",
    # Memory & Belief
    "BeliefSystem",
    "BeliefSource",
    "Belief",
    "MemoryConsolidator",
    "MemoryLevel",
    "MemoryItem",
    "KnowledgeBase",
    "KnowledgeTriple",
    "ExperienceStore",
    "Experience",
    # Agent Runtime
    "AgentRuntime",
    "RuntimeState",
    "EngineBridge",
    "EngineAdapter",
]
