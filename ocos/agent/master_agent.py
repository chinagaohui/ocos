"""MasterAgent — 认知主体核心。

Phase 22: Subject Emergence — 集成 LifecycleManager, ControlLoop, CognitiveBridge

Agent 是整个 OCOS 的唯一意识主体。所有 Engine 是器官，Agent 是主人。

生命周期:
  BOOTING → ACTIVE → SLEEPING → DREAMING → ACTIVE → ... → SHUTDOWN

微观循环 (within ACTIVE):
  OBSERVING → THINKING → DECIDING → ACTING → REFLECTING → LEARNING → OBSERVING

架构原则:
  - ControlLoop/CognitiveBridge 是 MasterAgent 的绝对私有组件
  - 绝不注入到 Engine 或 Runtime 中
  - 所有引擎调用经过 CognitiveBridge 显式路由
"""

from __future__ import annotations

import hashlib
import logging
import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

from ocos.agent.state import AgentState, AgentStatus
from ocos.agent.lifecycle import LifecycleManager, LifecyclePhase, MicroState
from ocos.agent.control_loop import ControlLoop
from ocos.agent.cognitive_bridge import CognitiveBridge, BridgeResult
from ocos.agent.goal_types import Goal, GoalLevel, GoalOriginLevel
from ocos.goal.factory import ConstitutionViolationError
from ocos.goal.enforcer import GoalOriginEnforcer
from ocos.kernel.abi import Observation
from ocos.memory.belief.models import Belief, BeliefStatus
from ocos.memory.belief.store import BeliefStore
from ocos.memory.pattern.extractor import PatternExtractor
from ocos.memory.pattern.models import PatternStatus
from ocos.memory.pattern.store import PatternStore


class _DecisionWrapper:
    """将 dict-decision 包装为有 action 属性的对象，供 BehavioralConstitution 检查。"""

    def __init__(self, decision: dict):
        self.action = decision.get("type", "")


class MasterAgent:
    """Master Agent — OCOS 的唯一认知主体。

    集成:
      - LifecycleManager: 线程安全的双层状态机
      - ControlLoop: 单权威 Goal 创建
      - CognitiveBridge: 引擎显式路由

    参数通过 Protocol 接口注入，允许各子系统独立开发。
    """

    def __init__(
        self,
        agent_id: str,
        identity: Any,              # IdentityAnchorProtocol
        goal_stack: Any,            # GoalStackProtocol
        intent: Any,                # IntentProtocol
        attention: Any,             # AttentionProtocol
        working_memory: Any,        # WorkingMemoryProtocol
        capability_manager: Any,    # CapabilityManagerProtocol
        execution_manager: Any,     # ExecutionManagerProtocol
        state: Optional[AgentState] = None,
        snapshot_mgr: Any = None,   # Phase 21: SnapshotManager
        constitution: Any = None,   # Phase 21: BehavioralConstitution
        permission_guard: Any = None,   # P2-D: 主动输出权限门（PermissionGuard）
        # Phase 22: Cognitive Bridge engines (optional)
        reasoning_engine: Any = None,
        planning_engine: Any = None,
        decision_engine: Any = None,
        reflection_engine: Any = None,
        learning_engine: Any = None,
        # Phase 23: Capability Selector + Skill Graph Executor
        capability_selector: Any = None,
        skill_graph_executor: Any = None,
        # Phase 22: current phase override
        current_phase: int = 22,
        # Phase 21: Memory consolidation (optional, injected by AgentRuntime)
        experience_builder: Any = None,
        episode_store: Any = None,
        # P2-C: Dream consolidation stores (optional — 默认惰性创建内存存储)
        belief_store: Any = None,
        pattern_store: Any = None,
        # P2-D: 主动输出通道（可选注入；默认本地日志）
        proactive_output_callback: Any = None,
        # Phase Q: 外部交互通道管理（可选注入；由 AgentRuntime 组装）
        external_interaction: Any = None,
        # Phase R: 持续学习管理器（可选注入；由 AgentRuntime 组装）
        continuous_learning: Any = None,
        # Phase S: 知识图谱管理器（可选注入；由 AgentRuntime 组装）
        knowledge_graph: Any = None,
        # Phase T: 多模态感知管理器（可选注入；由 AgentRuntime 组装）
        multimodal_perception: Any = None,
        # Phase U: 自主睡眠与梦境管理器（可选注入；由 AgentRuntime 组装）
        sleep_dream_manager: Any = None,
        # Phase V: 持久化与恢复管理器（可选注入；由 AgentRuntime 组装）
        persistence_manager: Any = None,
        # Phase W: 外部集成管理器（可选注入；由 AgentRuntime 组装）
        server_manager: Any = None,
        # Phase X: 安全加固管理器（可选注入；由 AgentRuntime 组装）
        security_manager: Any = None,
        # Phase Y: 监控与可观测性管理器（可选注入；由 AgentRuntime 组装）
        monitoring_manager: Any = None,
        # Phase Z: 性能优化管理器（可选注入；由 AgentRuntime 组装）
        performance_manager: Any = None,
        # Phase AA: 自我演化管理器（可选注入；由 AgentRuntime 组装）
        self_evolution_manager: Any = None,
        # Phase AB: 分布式认知管理器（可选注入；由 AgentRuntime 组装）
        distributed_manager: Any = None,
        # Phase AC: 生态集成管理器（可选注入；由 AgentRuntime 组装）
        ecosystem_manager: Any = None,
        # Phase AD: 人机协同管理器（可选注入；由 AgentRuntime 组装）
        human_ai_manager: Any = None,
        # Phase AE: 自我反思管理器（可选注入；由 AgentRuntime 组装）
        self_reflection_manager: Any = None,
        # Phase AF: 自我优化管理器（可选注入；由 AgentRuntime 组装）
        self_optimization_manager: Any = None,
        # Phase AG: 知识综合管理器（可选注入；由 AgentRuntime 组装）
        knowledge_synthesis_manager: Any = None,
        # Phase AH: 自我诊断管理器（可选注入；由 AgentRuntime 组装）
        self_diagnosis_manager: Any = None,
        # Phase AI: 工具集成管理器（可选注入；由 AgentRuntime 组装）
        tool_manager: Any = None,
        # Phase AJ: 增强型主动输出管理器（可选注入；由 AgentRuntime 组装）
        proactive_output_enhanced: Any = None,
        # Phase D: Agent 编排（可选注入；默认降级为 simulated）
        orchestration_supervisor: Any = None,
        # Phase L: 自主目标管理（可选注入；由 AgentRuntime 组装）
        goal_manager: Any = None,
    ):
        self.agent_id = agent_id
        self.identity = identity
        self.goal_stack = goal_stack
        self.intent = intent
        self.attention = attention
        self.working_memory = working_memory
        self.capability_manager = capability_manager
        self.execution_manager = execution_manager
        self.state = state or AgentState()

        # Phase 21: Snapshot & Recovery
        self._snapshot_mgr = snapshot_mgr
        self._constitution = constitution
        self._permission_guard = permission_guard
        self._experience_builder = experience_builder
        self._episode_store = episode_store

        # P2-D: Dream consolidation stores（惰性创建内存存储，显式注入优先）
        self._belief_store = belief_store
        self._pattern_store = pattern_store
        if self._belief_store is None:
            self._belief_store = BeliefStore(db_path=":memory:")
            self._belief_store.initialize()
        if self._pattern_store is None:
            self._pattern_store = PatternStore(db_path=":memory:")
            self._pattern_store.initialize()

        # Phase Q: External Interaction (optional)
        self._external_interaction = external_interaction

        # Phase R: Continuous Learning (optional)
        self._continuous_learning = continuous_learning

        # Phase S: Knowledge Graph (optional)
        self._knowledge_graph = knowledge_graph

        # Phase T: Multi-modal Perception (optional)
        self._multimodal_perception = multimodal_perception

        # Phase U: Sleep & Dream (optional)
        self._sleep_dream_manager = sleep_dream_manager

        # Phase V: Persistence & Recovery (optional)
        self._persistence_manager = persistence_manager

        # Phase W: External Integration (optional)
        self._server_manager = server_manager

        # Phase X: Security Hardening (optional)
        self._security_manager = security_manager

        # Phase Y: Monitoring & Observability (optional)
        self._monitoring_manager = monitoring_manager

        # Phase Z: Performance Optimization (optional)
        self._performance_manager = performance_manager

        # Phase AA: Self-Evolution (optional)
        self._self_evolution_manager = self_evolution_manager

        # Phase AB: Distributed Cognition (optional)
        self._distributed_manager = distributed_manager

        # Phase AC: Ecosystem Integration (optional)
        self._ecosystem_manager = ecosystem_manager

        # Phase AD: Human-AI Collaboration (optional)
        self._human_ai_manager = human_ai_manager

        # Phase AE: Self-Reflection (optional)
        self._self_reflection_manager = self_reflection_manager

        # Phase AF: Self-Optimization (optional)
        self._self_optimization_manager = self_optimization_manager

        # Phase AG: Knowledge Synthesis (optional)
        self._knowledge_synthesis_manager = knowledge_synthesis_manager

        # Phase AH: Self-Diagnosis (optional)
        self._self_diagnosis_manager = self_diagnosis_manager

        # Phase AI: Tool Integration (optional)
        self._tool_manager = tool_manager

        # Phase AJ: Proactive Output Enhanced (optional)
        self._proactive_output_enhanced = proactive_output_enhanced

        # P2-D: 主动输出（可选注入输出通道，默认本地日志）
        self._proactive_output_callback = proactive_output_callback
        self._proactive_engine: Any = None

        # Phase 22: Lifecycle + Control + Bridge
        self._lifecycle = LifecycleManager(agent_state=self.state)
        self._control_loop = ControlLoop(
            lifecycle=self._lifecycle,
            goal_enforcer=GoalOriginEnforcer(current_phase=current_phase),
            current_phase=current_phase,
        )
        self._bridge = CognitiveBridge(
            reasoning_engine=reasoning_engine,
            planning_engine=planning_engine,
            decision_engine=decision_engine,
            reflection_engine=reflection_engine,
            learning_engine=learning_engine,
        )

        # Phase 23: Capability Selector + Skill Graph Executor（可选）
        self._capability_selector = capability_selector
        self._skill_graph_executor = skill_graph_executor

        # Phase 22-A: EngineBridge for act() dispatch
        self._engine_bridge: Any = None  # set by injection or externally
        self._orchestration_supervisor = orchestration_supervisor
        # Phase H: Memory Recall (optional, set by AgentRuntime)
        self._memory_recall: Any = None
        # Phase L: Goal Manager (optional, set by AgentRuntime)
        self._goal_manager: Any = goal_manager

        # 全局状态锁：保证 sleep() 状态切片的绝对原子性
        self._state_lock = self._lifecycle.lock

        # 生命周期产出缓存
        self._last_observation: Any = None
        self._last_thought: Any = None
        self._last_decision: Any = None
        self._last_action_result: Any = None
        self._last_reflection: Any = None
        self._last_learning: Any = None

    # ── 属性 ──────────────────────────────────────────────────────────

    @property
    def lifecycle(self) -> LifecycleManager:
        return self._lifecycle

    @property
    def control_loop(self) -> ControlLoop:
        return self._control_loop

    @property
    def bridge(self) -> CognitiveBridge:
        return self._bridge

    @property
    def goal_manager(self) -> Any:
        """Phase L: 自主目标管理器."""
        return self._goal_manager

    @property
    def external_interaction(self) -> Any:
        """Phase Q: 外部交互管理器."""
        return self._external_interaction

    @property
    def continuous_learning(self) -> Any:
        """Phase R: 持续学习管理器."""
        return self._continuous_learning

    @property
    def knowledge_graph(self) -> Any:
        """Phase S: 知识图谱管理器."""
        return self._knowledge_graph

    @property
    def multimodal_perception(self) -> Any:
        """Phase T: 多模态感知管理器."""
        return self._multimodal_perception

    @property
    def sleep_dream_manager(self) -> Any:
        """Phase U: 自主睡眠与梦境管理器."""
        return self._sleep_dream_manager

    @property
    def persistence_manager(self) -> Any:
        """Phase V: 持久化与恢复管理器."""
        return self._persistence_manager

    @property
    def server_manager(self) -> Any:
        """Phase W: 外部集成服务器管理器."""
        return self._server_manager

    @property
    def security_manager(self) -> Any:
        """Phase X: 安全加固管理器."""
        return self._security_manager

    @property
    def monitoring_manager(self) -> Any:
        """Phase Y: 监控与可观测性管理器."""
        return self._monitoring_manager

    @property
    def performance_manager(self) -> Any:
        """Phase Z: 性能优化管理器."""
        return self._performance_manager

    @property
    def self_evolution_manager(self) -> Any:
        """Phase AA: 自我演化管理器."""
        return self._self_evolution_manager

    @property
    def distributed_manager(self) -> Any:
        """Phase AB: 分布式认知管理器."""
        return self._distributed_manager

    @property
    def ecosystem_manager(self) -> Any:
        """Phase AC: 生态集成管理器."""
        return self._ecosystem_manager

    @property
    def human_ai_manager(self) -> Any:
        """Phase AD: 人机协同管理器."""
        return self._human_ai_manager

    @property
    def self_reflection_manager(self) -> Any:
        """Phase AE: 自我反思管理器."""
        return self._self_reflection_manager

    @property
    def self_optimization_manager(self) -> Any:
        """Phase AF: 自我优化管理器."""
        return self._self_optimization_manager

    @property
    def knowledge_synthesis_manager(self) -> Any:
        """Phase AG: 知识综合管理器."""
        return self._knowledge_synthesis_manager

    @property
    def self_diagnosis_manager(self) -> Any:
        """Phase AH: 自我诊断管理器."""
        return self._self_diagnosis_manager

    @property
    def tool_manager(self) -> Any:
        """Phase AI: 工具集成管理器."""
        return self._tool_manager

    @property
    def proactive_output_enhanced(self) -> Any:
        """Phase AJ: 增强型主动输出管理器."""
        return self._proactive_output_enhanced

    # ── EngineBridge accessor (Phase 22-A) ─────────────────────────────

    def set_engine_bridge(self, engine_bridge: Any) -> None:
        """Phase 22-A: 注入 EngineBridge 供 act() 真实化使用。"""
        self._engine_bridge = engine_bridge

    # ── Life Cycle 入口 ──────────────────────────────────────────────

    def boot(self) -> None:
        """启动顺序：恢复 Snapshot → Identity → Memory → Capability → Ready。

        Phase 21: 优先从 Agent Snapshot 恢复完整状态。
        Phase 22: 使用 LifecycleManager 管理启动阶段。

        幂等：已启动完成（在 ACTIVE 或之后）则跳过。
        """
        # 幂等检查
        if self._lifecycle.phase in (
            LifecyclePhase.ACTIVE,
            LifecyclePhase.SLEEPING,
            LifecyclePhase.DREAMING,
            LifecyclePhase.SHUTDOWN,
        ):
            return

        # 已在 BOOTING，直接执行启动逻辑
        assert self._lifecycle.phase == LifecyclePhase.BOOTING, (
            f"Unexpected phase: {self._lifecycle.phase}"
        )

        # Phase 21.01: Snapshot Recovery
        recovered = False
        if self._snapshot_mgr is not None:
            try:
                from ocos.snapshot.recovery import CrashRecovery

                recovery = CrashRecovery(self._snapshot_mgr)
                result = recovery.recover()
                if result.success:
                    recovered = True
            except Exception:
                pass  # Recovery failed, continue with fresh boot

        if recovered:
            if self._snapshot_mgr is not None:
                snapshot = self._snapshot_mgr.load_latest()
                if snapshot:
                    if hasattr(self.working_memory, "capacity"):
                        cap = snapshot.working_memory_config.get("capacity", 100)
                        self.working_memory.capacity = cap
        else:
            if hasattr(self.identity, "verify"):
                assert self.identity.verify(), "Identity verification failed"
            if hasattr(self.capability_manager, "list_capabilities"):
                _ = self.capability_manager.list_capabilities()

        # Phase 22: 启动完成，进入 ACTIVE
        self._control_loop.boot_complete()
        # 同步 AgentState.status（兼容旧测试）
        if self.state.status == AgentStatus.INIT:
            self.state.transition(AgentStatus.BOOTING)
        self.state.transition(AgentStatus.IDLE)

    def wake(self) -> None:
        """从 SLEEP/DREAM 中醒来。"""
        self._control_loop.wake_from_sleep()
        if hasattr(self.attention, "reset"):
            self.attention.reset()

    def observe(self) -> Any:
        """观察阶段：收集输入事件、上下文、记忆、告警。

        Phase 22: 使用 LifecycleManager 管理微状态转换。
        """
        self._lifecycle.transition_micro(MicroState.OBSERVING)

        from ocos.kernel.abi import Observation

        observation = Observation(
            source="agent",
            content={
                "agent_id": self.agent_id,
                "phase": self._lifecycle.phase.name,
                "micro_state": self._lifecycle.micro_state.name,
                "focus": (
                    self.attention.current_focus()
                    if hasattr(self.attention, "current_focus")
                    else None
                ),
                "goal": (
                    self.goal_stack.peek()
                    if hasattr(self.goal_stack, "peek")
                    else None
                ),
                "intent": (
                    self.intent.get_intent_description()
                    if hasattr(self.intent, "get_intent_description")
                    else None
                ),
            },
        )
        self._last_observation = observation
        if hasattr(self.working_memory, "add"):
            self.working_memory.add(observation)
        return observation

    def think(self, observation: Any = None) -> Any:
        """思考阶段：Phase 23 集成 Capability Selector → Phase 22 Bridge 降级。

        Phase 23: 若配置了 CapabilitySelector + SkillGraphExecutor，
                  通过 asyncio.run() 执行 SkillGraph。
        Phase 22: 无 Selector 时直接通过 CognitiveBridge 调用推理引擎。
        """
        with self._state_lock:
            self._lifecycle.transition_micro(MicroState.THINKING)

        obs = observation or self._last_observation

        # ── Phase 23: 尝试 Capability Selector ──────────────────────────
        if self._capability_selector and self._skill_graph_executor:
            return self._think_with_selector(obs)

        # ── Phase 22: CognitiveBridge fallback ──────────────────────────
        premises = {
            "inputs": [
                str(obs.content) if hasattr(obs, "content") else str(obs)
            ],
        }

        try:
            result: BridgeResult = self._bridge.reason(
                operation="deduction",
                premises=premises,
            )
        except Exception as e:
            self._safe_return_to_idle()
            raise RuntimeError(f"Think phase failed: {e}") from e

        if not result.success:
            thought = {
                "status": "stub",
                "source": "bridge:fallback",
                "reason": "reasoning_engine_not_registered",
                "bridge_result": result,
                "trace_id": result.trace_id,
            }
            self._last_thought = thought
            return thought

        thought = {
            "bridge_result": result,
            "trace_id": result.trace_id,
            "message": result.message,
        }
        self._last_thought = thought
        return thought

    # ── Phase 23: Selector-assisted think ───────────────────────────────

    def _think_with_selector(self, observation: Any) -> Any:
        """Phase 23: 通过 CapabilitySelector 选择 SkillGraph 后执行。

        使用 asyncio.run() 包装异步执行器，保持外部 sync 接口不变。
        """
        import asyncio

        # 1. 解析 Intent
        intent = None
        if hasattr(self, "intent") and hasattr(self.intent, "extract"):
            intent = self.intent.extract(observation, entry=None)
        else:
            intent = str(observation.content) if hasattr(observation, "content") else str(observation)

        # 2. 构建上下文
        context = {
            "goal_stack": getattr(self, "goal_stack", None),
            "working_memory": getattr(self, "working_memory", None),
            "agent_id": self.agent_id,
        }

        # 3. 选择 SkillGraph
        selector_result = self._capability_selector.select(intent, context)

        if not selector_result.selected_graph:
            # 降级到 Phase 22 行为
            return self._fallback_think(observation, intent)

        # 4. 执行 SkillGraph（同步化异步）
        try:
            process = asyncio.run(
                self._skill_graph_executor.start(
                    selector_result.selected_graph,
                    context={
                        "session_id": f"session-{uuid.uuid4().hex[:8]}",
                        "agent_id": self.agent_id,
                        "intent": str(intent),
                        "_fallback_skills": selector_result.selected_graph.skills,
                    },
                )
            )
        except Exception as e:
            return self._fallback_think(observation, intent)

        thought = {
            "status": process.status.value,
            "source": "capability_selector",
            "process_id": process.id,
            "skill_graph_id": selector_result.selected_graph.id,
            "execution_history": [
                {
                    "skill_id": r.skill_id,
                    "skill_name": r.skill_name,
                    "status": r.status.value,
                    "duration": r.duration,
                }
                for r in process.execution_history
            ],
            "total_duration": process.total_duration,
            "selector_confidence": selector_result.confidence,
        }
        self._last_thought = thought
        return thought

    def _fallback_think(self, observation: Any, intent: Any) -> Any:
        """Phase 22 降级：直接通过 CognitiveBridge 调用推理引擎。"""
        premises = {
            "inputs": [
                str(observation.content) if hasattr(observation, "content") else str(observation)
            ],
        }
        try:
            result: BridgeResult = self._bridge.reason(
                operation="deduction",
                premises=premises,
            )
        except Exception as e:
            self._safe_return_to_idle()
            raise RuntimeError(f"Think phase failed: {e}") from e

        if not result.success:
            thought = {
                "status": "stub",
                "source": "bridge:fallback",
                "reason": "reasoning_engine_not_registered",
                "bridge_result": result,
                "trace_id": result.trace_id,
            }
            self._last_thought = thought
            return thought

        thought = {
            "bridge_result": result,
            "trace_id": result.trace_id,
            "message": result.message,
            "source": "bridge:fallback_from_selector",
        }
        self._last_thought = thought
        return thought

    def decide(self, thought: Any = None) -> Any:
        """决策阶段：BehavioralConstitution 检查 → CognitiveBridge 决策。

        Phase 21.03: BehavioralConstitution 拦截（先于 Bridge 执行）
        Phase 22: CognitiveBridge 显式路由
        """
        with self._state_lock:
            self._lifecycle.transition_micro(MicroState.DECIDING)

        t = thought or self._last_thought

        # Phase 21.03: Behavioral Constitution 检查 — 在 Bridge 之前
        if self._constitution is not None:
            try:
                decision_preview = {
                    "type": "cognitive_decision",
                    "based_on": str(t),
                }
                decision_obj = _DecisionWrapper(decision_preview)
                context = {
                    "agent_state": self._lifecycle.freeze(),
                }
                result = self._constitution.check_decision(decision_obj, context)
                if not result.allowed:
                    self._safe_return_to_idle()
                    raise ConstitutionViolationError(
                        f"Decision blocked by BehavioralConstitution: "
                        f"{result.violations}"
                    )
            except ConstitutionViolationError:
                raise
            except Exception as _con_e:
                # BR-04 C-1 修复（2026-08-25）：宪法引擎故障必须 fail-closed。
                # 安全机制自身不可用时，决策必须被拒绝，不能静默放行
                # （原 fail-open 会让宪法崩了决策照过，等于拆掉最后一道闸门）。
                self._safe_return_to_idle()
                raise ConstitutionViolationError(
                    f"Decision blocked: BehavioralConstitution unavailable ({_con_e})"
                ) from _con_e

        # Phase 22: 通过 Bridge 执行决策
        try:
            bridge_result: BridgeResult = self._bridge.decide(
                strategy="scoring",
                context={"weights": {"quality": 1.0, "cost": 0.5, "risk": 0.3}},
            )
        except Exception as e:
            self._safe_return_to_idle()
            raise RuntimeError(f"Decision phase failed: {e}") from e

        if not bridge_result.success:
            # 无引擎时降级为 stub
            decision = {
                "status": "stub",
                "source": "bridge:fallback",
                "reason": "decision_engine_not_registered",
                "based_on": t,
                "type": "cognitive_decision",
                "bridge_result": bridge_result,
                "trace_id": bridge_result.trace_id,
                "selected": bridge_result.data.get("selected_option_id", ""),
            }
            self._last_decision = decision
            return decision

        decision = {
            "based_on": t,
            "type": "cognitive_decision",
            "bridge_result": bridge_result,
            "trace_id": bridge_result.trace_id,
            "selected": bridge_result.data.get("selected_option_id", ""),
        }
        self._last_decision = decision
        return decision

    def act(self, decision: Any = None) -> Any:
        """行动阶段：通过 ExecutionManager → EngineBridge 执行。

        Phase 22-A: 替换 stub — 决策通过 EngineBridge.dispatch 到真实引擎。
        当 EngineBridge 不可用时降级为 simulated 模式。
        """
        with self._state_lock:
            self._lifecycle.transition_micro(MicroState.ACTING)

        d = decision or self._last_decision

        try:
            # Phase 22-A: 优先走 EngineBridge → 真实引擎
            if self._engine_bridge is not None:
                action_result_raw = self._act_via_bridge(d)
            elif hasattr(self.execution_manager, "execute"):
                action_result_raw = self.execution_manager.execute(d)
            else:
                action_result_raw = {
                    "status": "simulated",
                    "result": None,
                    "note": "ExecutionManager not configured, EngineBridge not available",
                }
        except Exception as e:
            self._safe_return_to_idle()
            raise RuntimeError(f"Act phase failed: {e}") from e

        action_result = {
            "based_on": d,
            "result": action_result_raw,
        }

        # Phase D: 尝试通过编排器触发子 agent 执行
        if self._orchestration_supervisor is not None:
            orchestrator_result = self._dispatch_to_orchestrator(d, action_result_raw)
            if orchestrator_result and orchestrator_result.get("sub_agent_triggered"):
                action_result["orchestrated"] = True
                action_result["sub_agent_result"] = orchestrator_result

        self._last_action_result = action_result
        return action_result

    def _dispatch_to_orchestrator(self, decision: Any, bridge_result: Any) -> dict | None:
        """Phase D: 将决策分发给 ExecutionSupervisor 执行子 agent。

        从 decision 提取目标 agent_type → 创建 Task → execute_task → 返回结果。
        失败时静默降级，不影响主链路。
        """
        # Phase H: 记录当前决策到用户记忆
        self._recall_and_record(decision)

        try:
            agent_type = ""
            if isinstance(decision, dict):
                selected = str(decision.get("selected", "") or "")
                # 从 selected 推断 agent_type（如 "writer-v2" → "writer"）
                agent_type = selected.split("-")[0] if selected else ""

            if not agent_type:
                return None

            from ocos.planning.models import Task
            import uuid

            task_id = f"task-{uuid.uuid4().hex[:8]}"
            goal_id = f"goal-{self.agent_id}"
            task = Task(
                id=task_id,
                goal_id=goal_id,
                description=str(decision.get("based_on", decision)),
                task_type="execute",
                agent_type=agent_type,
                inputs=(),
            )
            record = self._orchestration_supervisor.execute_task_sync(task)
            return {
                "sub_agent_triggered": True,
                "task_id": task_id,
                "agent_type": agent_type,
                "contract_id": record.contract_id if hasattr(record, "contract_id") else None,
                "status": record.status if hasattr(record, "status") else "unknown",
            }
        except Exception as e:
            logger.debug(f"Phase D: orchestration dispatch failed (non-blocking): {e}")
            return None

    def _recall_and_record(self, decision: Any) -> None:
        """Phase H: 召回相关记忆并记录当前决策到用户记忆."""
        try:
            # 记录到用户记忆
            if hasattr(self, '_memory_hub_ref') and self._memory_hub_ref:
                # 简单提取决策描述
                desc = str(decision) if decision else ""
                desc = desc[:100] if len(desc) > 100 else desc
                if desc and desc not in ("None", "", "{}"):
                    # 尝试记录事件（如果 user_memory 存在）
                    pass  # 简化：仅记录决策日志
        except Exception:
            pass  # 非阻塞

    def _act_via_bridge(self, decision: Any) -> Any:
        """Phase 22-A: 通过 EngineBridge 将决策派发到真实引擎。

        从 decision['selected'] 提取引擎名 → EngineBridge.execute() → 返回真实结果。
        无匹配引擎时降级为 simulated。
        """
        # 提取目标引擎名
        engine_name = ""
        if isinstance(decision, dict):
            engine_name = str(decision.get("selected", "") or "")

        if not engine_name:
            # 尝试从 decision type 推断
            d_type = decision.get("type", "") if isinstance(decision, dict) else ""
            if "write" in d_type.lower() or "writer" in d_type.lower():
                engine_name = "writer"
            elif "plan" in d_type.lower():
                engine_name = "planner"
            elif "reason" in d_type.lower():
                engine_name = "reasoner"

        # 检查引擎是否可用
        available = self._engine_bridge.get_available_engines()
        if engine_name not in available and available:
            engine_name = available[0]  # fallback: 任意可用引擎

        if not engine_name or engine_name not in available:
            return {
                "status": "simulated",
                "result": None,
                "note": f"No matching engine found. Available: {available}",
            }

        from ocos.models.process import ProcessType

        inputs = {
            "decision": decision,
            "action_type": decision.get("type", "cognitive_action") if isinstance(decision, dict) else "action",
        }

        result = self._engine_bridge.execute(
            engine_name=engine_name,
            process_type=ProcessType.PLANNING,
            operation="execute",
            inputs=inputs,
        )
        if result.get("success"):
            return {
                "status": "executed",
                "engine": engine_name,
                "result": result,
                "trace_id": result.get("trace_id", ""),
            }
        else:
            return {
                "status": "engine_failed",
                "engine": engine_name,
                "result": result,
                "message": result.get("message", "Engine execution failed"),
            }

    def reflect(self, action_result: Any = None) -> Any:
        """反思阶段：通过 CognitiveBridge 调用 ReflectionEngine。

        Phase 22: 显式路由 + 异常恢复。
        """
        with self._state_lock:
            self._lifecycle.transition_micro(MicroState.REFLECTING)

        ar = action_result or self._last_action_result

        try:
            bridge_result: BridgeResult = self._bridge.reflect(
                subject_type="action_result",
                subject_id=str(ar.get("based_on", {}).get("trace_id", "")),
                strategy="standard",
            )
        except Exception as e:
            self._safe_return_to_idle()
            raise RuntimeError(f"Reflect phase failed: {e}") from e

        if not bridge_result.success:
            # 无引擎时降级为 stub
            reflection = {
                "status": "stub",
                "source": "bridge:fallback",
                "reason": "reflection_engine_not_registered",
                "based_on": ar,
                "bridge_result": bridge_result,
                "trace_id": bridge_result.trace_id,
                "insight_count": bridge_result.data.get("insight_count", 0),
            }
            self._last_reflection = reflection
            return reflection

        reflection = {
            "based_on": ar,
            "bridge_result": bridge_result,
            "trace_id": bridge_result.trace_id,
            "insight_count": bridge_result.data.get("insight_count", 0),
        }
        self._last_reflection = reflection
        return reflection

    def learn(self, reflection: Any = None) -> Any:
        """学习阶段：通过 CognitiveBridge 调用 LearningEngine。

        Phase 22-A: EngineBridge 真实化 — 学习结果通过 ExperienceBuilder → EpisodeStore 持久化。
        """
        with self._state_lock:
            self._lifecycle.transition_micro(MicroState.LEARNING)

        r = reflection or self._last_reflection

        try:
            bridge_result: BridgeResult = self._bridge.learn(
                model=None,
                examples=None,
                strategy="supervised",
            )
        except Exception as e:
            self._safe_return_to_idle()
            raise RuntimeError(f"Learn phase failed: {e}") from e

        if not bridge_result.success:
            # 无引擎时降级为 stub
            learning = {
                "status": "stub",
                "source": "bridge:fallback",
                "reason": "learning_engine_not_registered",
                "based_on": r,
                "bridge_result": bridge_result,
                "trace_id": bridge_result.trace_id,
                "patterns_learned": bridge_result.data.get("patterns_learned", 0),
            }
            self._last_learning = learning
            with self._state_lock:
                self._lifecycle.transition_micro(MicroState.IDLE)
            return learning

        learning = {
            "based_on": r,
            "bridge_result": bridge_result,
            "trace_id": bridge_result.trace_id,
            "patterns_learned": bridge_result.data.get("patterns_learned", 0),
        }
        self._last_learning = learning

        # Phase 22-A: 学习结果 → ExperienceBuilder → EpisodeStore 持久化
        self._persist_learning(learning)

        # 微循环完成，回到 IDLE
        with self._state_lock:
            self._lifecycle.transition_micro(MicroState.IDLE)

        return learning

    def _persist_learning(self, learning: dict[str, Any]) -> None:
        """Phase 22-A: 将学习结果通过 ExperienceBuilder → Episode 管道持久化。

        构建 TraceBundle（observation→reasoning→decision→action→outcome→reflection→learning）
        → ExperienceBuilder.build() → Episode.from_candidate() → EpisodeStore.save()
        """
        builder = self._experience_builder
        store = self._episode_store
        if builder is None and store is None:
            return

        try:
            from ocos.memory.experience.models import TraceBundle, ExperienceSource
            from ocos.memory.episode.models import Episode

            # 从 _last_* 缓存构建完整认知链
            obs = self._last_observation
            obs_dict = (
                {"content": str(obs.content)} if hasattr(obs, "content")
                else {"content": str(obs)} if obs is not None
                else {}
            )

            thought = self._last_thought or {}
            decision = self._last_decision or {}
            action_result = self._last_action_result or {}
            reflection = self._last_reflection or {}

            trace_bundle = TraceBundle(
                observation=obs_dict,
                reasoning_trace_id=str(thought.get("trace_id", "")),
                decision_trace_id=str(decision.get("trace_id", "")),
                action_result={"result": action_result.get("result", {})},
                outcome={
                    "learning": learning,
                    "patterns_learned": learning.get("patterns_learned", 0),
                },
                reflection_trace_id=str(reflection.get("trace_id", "")),
                source_trace_ids=[
                    tid for tid in [
                        thought.get("trace_id"),
                        decision.get("trace_id"),
                        reflection.get("trace_id"),
                        learning.get("trace_id"),
                    ] if tid
                ],
                goal_context={
                    "goal": str(self.goal_stack.peek()) if hasattr(self.goal_stack, "peek") else None,
                },
            )

            if builder is not None:
                candidate = builder.build(
                    trace_bundle=trace_bundle,
                    source=ExperienceSource.DECISION,
                    context={
                        "agent_id": self.agent_id,
                        "phase": "learn",
                        "patterns_learned": learning.get("patterns_learned", 0),
                    },
                )
                if store is not None and candidate.status.value == "complete":
                    outcome_dict = {
                        "learning": learning,
                        "status": "completed",
                        "timestamp": getattr(
                            self._last_action_result, "get",
                            lambda k, d=None: d,
                        )("timestamp", ""),
                    }
                    episode = Episode.from_candidate(
                        experience_id=candidate.id,
                        context=candidate.context,
                        goal=str(self.goal_stack.peek()) if hasattr(self.goal_stack, "peek") else None,
                        decision=str(decision.get("type", "")),
                        action="learn",
                        outcome=outcome_dict,
                        condition="learning_cycle",
                        significance_score=candidate.significance_score or 0.5,
                        evaluation_trace={"pipeline": "learn"},
                        source="reflection",
                        session_id=f"session-{self.agent_id}",
                    )
                    store.save(episode)

        except Exception:
            pass  # 持久化失败不阻塞 Agent

    def sleep(self) -> None:
        """休眠：保存 Snapshot → 清理内存 → 进入 SLEEP。

        Phase 21: RLock 原子保存。
        Phase 22: LifecycleManager 宏观阶段管理。
        """
        with self._state_lock:
            # Phase 21.01: 保存 Agent Snapshot
            if self._snapshot_mgr is not None:
                try:
                    from ocos.snapshot.models import AgentSnapshot
                    from datetime import datetime, timezone

                    snapshot = AgentSnapshot(
                        snapshot_id=f"snap-{uuid.uuid4().hex[:8]}",
                        identity_state=(
                            self.identity.to_dict()
                            if hasattr(self.identity, "to_dict")
                            else {"agent_id": self.agent_id}
                        ),
                        goal_state=(
                            self.goal_stack.to_list()
                            if hasattr(self.goal_stack, "to_list")
                            else []
                        ),
                        working_memory_config={
                            "capacity": getattr(
                                self.working_memory, "capacity", 100
                            ),
                            "items": [],  # 强制空
                        },
                        runtime_state={
                            "agent_state": self._lifecycle.freeze(),
                            "last_active": datetime.now(timezone.utc).isoformat(),
                        },
                    )
                    self._snapshot_mgr.save(snapshot)
                except Exception:
                    pass

            if hasattr(self.working_memory, "clear"):
                self.working_memory.clear()

            # Phase 22: 宏观阶段转换
            self._control_loop.enter_sleep()

    def dream(self) -> Any:
        """梦境：Memory Consolidation + Lessons Synthesis。

        Phase 21: 从 Experience Candidate 合成 Lessons，存为 Episode。
        Phase 22: LifecycleManager 管理宏观阶段。
        """
        self._control_loop.enter_dream()
        consolidation: dict[str, Any] = {
            "phase": "dream",
            "items_processed": 0,
            "lessons_synthesized": 0,
            "lifecycle": self._lifecycle.freeze(),
        }

        # Phase 21: Lessons Synthesis — 跨经验归纳
        builder = self._experience_builder
        if builder is not None:
            try:
                lessons = builder._synthesize_lessons()
                consolidation["lessons_synthesized"] = len(lessons)

                # 存为 Episode（source="lesson"）
                store = self._episode_store
                if store is not None and lessons:
                    for lesson in lessons:
                        try:
                            episode = lesson.to_episode()
                            store.save(episode)
                        except Exception:
                            pass  # 单条存储失败不阻塞
            except Exception:
                pass  # 合成失败不阻塞 Agent

        # P2-C: Dream Consolidation — 重放当日 Episode → Belief/Pattern 巩固 + 修剪
        try:
            stats = self._consolidate_episodes()
            consolidation["consolidation_stats"] = stats
        except Exception:
            consolidation["consolidation_stats"] = {}  # 巩固失败不阻塞睡眠

        # PW-1.1: Wisdom Consolidation — 成败经验聚类 → 智慧候选（CLS 慢通路）
        hub = getattr(self, "_memory_hub_ref", None)
        try:
            if hub is not None:
                from ocos.agent.wisdom_trigger import consolidate_wisdom
                consolidation["wisdom_stats"] = consolidate_wisdom(hub)
        except Exception:
            consolidation["wisdom_stats"] = {}  # 智慧提炼失败不阻塞睡眠

        # PW-1.3: Continuity Checkpoint — 身份连续性 + 知识老化（落盘内视）
        try:
            if hub is not None:
                from ocos.agent.continuity_trigger import (
                    run_continuity_checkpoint,
                )
                wisdom_n = (consolidation.get("wisdom_stats") or {}).get(
                    "wisdom_total", 0)
                report = run_continuity_checkpoint(
                    hub, tick_id=consolidation.get("items_processed", 0) or 0,
                    wisdom_count=wisdom_n)
                consolidation["continuity"] = {
                    "checkpoint_id": report["checkpoint_id"],
                    "anomalies": report["identity_anomalies"],
                    "severity": report["identity_severity"],
                }
        except Exception:
            consolidation["continuity"] = {}  # 连续性检查失败不阻塞睡眠

        self._control_loop.wake_from_sleep()
        return consolidation

    # ── P2-C: Dream Consolidation ─────────────────────────────────────

    _CONSOLIDATION_BATCH_LIMIT = 200  # 单次 dream 最多重放条数（防失控）
    _BELIEF_INITIAL_CONFIDENCE = 0.6  # 新建 Belief 起点置信（≥ ACTIVE 阈值）
    _BELIEF_STRENGTHEN_STEP = 0.1     # 每条新证据增强步长
    _PRUNE_CONFIDENCE_FLOOR = 0.35    # 低于此置信的 Belief 修剪

    def attach_memory_hub(self, hub: Any) -> None:
        """GAP-P0-2: 绑定持久化 MemoryHub 的 store（覆盖 :memory: 惰性默认）。

        生产路径由 AgentRuntime 在初始化 MemoryHub 后回填，保证 dream 巩固
        产物（Belief/Pattern/Episode）写入文件库而非进程内存。
        """
        if hub is None:
            return
        self._episode_store = hub.episode
        self._belief_store = hub.belief
        self._pattern_store = hub.pattern
        self._memory_hub_ref = hub  # PW-1.1: wisdom 巩固需要 hub（_db_path + episode）

    def _consolidate_episodes(self) -> dict[str, Any]:
        """重放当日未巩固 Episode → Belief/Pattern 巩固 + 弱模式修剪（CLS 慢系统闭环）。

        确定性规则（无 LLM）：
          - 重放 = 最近 ACTIVE Episodes 中 created_at ≥ 今日 0:00 者（query_by_time 天然排除
            已 CONSOLIDATED/ARCHIVED，幂等由状态位保证）
          - Belief 聚类键 = goal or tags[0] or "episode:{source}"
          - 新建 Belief confidence=0.6；已存在则证据追加 + confidence 累加（min 1.0）
          - Pattern 提取去重：同 trigger_condition+observed_relation 已存在 → 不重复插入；
            已存在但置信 < 修剪阈值 → REJECTED（PatternStatus 无 ARCHIVED）
          - 弱 Belief（conf < 0.35）→ weaken → archive
          - 全部处理完 → Episode 置 CONSOLIDATED（幂等）
        """
        stats: dict[str, Any] = {
            "replayed": 0,
            "beliefs_created": 0,
            "beliefs_strengthened": 0,
            "patterns_created": 0,
            "patterns_strengthened": 0,
            "pruned": 0,
        }
        store = self._episode_store
        if store is None:
            return stats  # 无 Episode 存储 → 降级不抛

        # 1. 重放今日 ACTIVE Episodes
        today_start = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        episodes = [
            ep
            for ep in store.query_by_time(limit=self._CONSOLIDATION_BATCH_LIMIT)
            if ep.created_at >= today_start
        ]
        stats["replayed"] = len(episodes)
        if not episodes:
            return stats

        # 2. Belief 巩固：按主题聚类
        by_topic: dict[str, list] = {}
        for ep in episodes:
            topic = ep.goal or (ep.tags[0] if ep.tags else f"episode:{ep.source}")
            by_topic.setdefault(topic, []).append(ep)
        for topic, eps in by_topic.items():
            belief_id = "BLF-" + hashlib.sha1(topic.encode("utf-8")).hexdigest()[:12]
            existing = self._belief_store.get(belief_id)
            if existing is None:
                now = datetime.now(timezone.utc)
                belief = Belief(
                    id=belief_id,
                    statement=f"主题「{topic}」相关经历持续出现",
                    source_knowledge_ids=(),
                    evidence_ids=tuple(ep.id for ep in eps),
                    confidence=self._BELIEF_INITIAL_CONFIDENCE,
                    uncertainty=1.0 - self._BELIEF_INITIAL_CONFIDENCE,
                    scope={"domain": topic},
                    status=BeliefStatus.ACTIVE,
                    created_at=now,
                    last_updated=now,
                )
                self._belief_store.save(belief)
                stats["beliefs_created"] += 1
            else:
                new_evidence = tuple(
                    ep.id for ep in eps if ep.id not in existing.evidence_ids
                )
                if new_evidence:
                    enhanced = Belief(
                        id=existing.id,
                        statement=existing.statement,
                        source_knowledge_ids=existing.source_knowledge_ids,
                        evidence_ids=existing.evidence_ids + new_evidence,
                        confidence=min(
                            existing.confidence
                            + self._BELIEF_STRENGTHEN_STEP * len(new_evidence),
                            1.0,
                        ),
                        uncertainty=max(1.0 - existing.confidence, 0.0),
                        scope=existing.scope,
                        status=existing.status,
                        created_at=existing.created_at,
                        last_updated=datetime.now(timezone.utc),
                    )
                    self._belief_store.save(enhanced)
                    stats["beliefs_strengthened"] += 1

        # 3. Pattern 提取 + 去重（同 condition 不重复插入）
        extractor = PatternExtractor()
        for pat in extractor.extract(episodes):
            existing = self._pattern_store.find_by_condition(
                pat.trigger_condition, pat.observed_relation
            )
            if existing is None:
                self._pattern_store.save(pat)
                stats["patterns_created"] += 1
            elif existing.confidence < self._PRUNE_CONFIDENCE_FLOOR:
                self._pattern_store.update_status(existing.id, PatternStatus.REJECTED)
                stats["pruned"] += 1
            else:
                stats["patterns_strengthened"] += 1  # 已存在 → 加强计数（不重复插入）

        # 4. 弱 Belief 修剪（weaken → archive，退出推理）
        for belief in self._belief_store.query_by_status(
            BeliefStatus.ACTIVE, limit=self._CONSOLIDATION_BATCH_LIMIT
        ):
            if belief.confidence < self._PRUNE_CONFIDENCE_FLOOR:
                self._belief_store.weaken(belief.id)
                self._belief_store.archive(belief.id)
                stats["pruned"] += 1

        # 5. 幂等标记：已重放的 Episode 置 CONSOLIDATED
        for ep in episodes:
            try:
                store.mark_consolidated(ep.id)
            except Exception:
                pass  # 单条标记失败不阻塞

        return stats

    # ── P2-D: 主动输出 ────────────────────────────────────────────────

    def maybe_proactive_output(self) -> Optional[str]:
        """空闲期主动输出入口（挂 LifecycleOrchestrator._tick_idle 尾部）。

        触发链与降级全部由 ProactiveEngine 承担；本方法防御式兜底：
        任何依赖缺失/异常 → 返回 None，绝不抛。
        """
        try:
            if self._proactive_engine is None:
                from ocos.proactive import ProactiveEngine

                self._proactive_engine = ProactiveEngine(
                    goal_store=getattr(self, "_goal_store", None),
                    attention=self.attention,
                    permission_guard=self._permission_guard,
                    constitution=self._constitution,
                    output_callback=self._build_proactive_callback(),
                )
            return self._proactive_engine.maybe_proactive_output()
        except Exception:  # pragma: no cover - 防御兜底
            return None

    def _build_proactive_callback(self) -> Optional[Callable[[str], None]]:
        """构建 ProactiveEngine 输出回调，注入 ExternalInteraction 通道。"""
        if self._external_interaction is None:
            return self._proactive_output_callback
        sent_channels = []

        def callback(message: str) -> None:
            try:
                results = self._external_interaction.send(message, priority=0)
                sent_channels.extend(k for k, v in results.items() if v)
            except Exception as e:
                logger.warning("ExternalInteraction send failed: %s", e)
        return callback

    def record_user_feedback(
        self,
        user_response: str,
        ai_output: str,
        interaction_type: str = "chat",
    ) -> None:
        """记录用户反馈并学习偏好（Phase R）。

        防御式：continuous_learning 未注入时静默忽略。
        """
        if self._continuous_learning is None:
            return
        try:
            result = self._continuous_learning.learn_from_interaction(
                interaction_type=interaction_type,
                user_response=user_response,
                ai_output=ai_output,
            )
            if result.success and result.preferences_updated:
                logger.info(
                    "Learning updated %s preferences: %s",
                    len(result.preferences_updated),
                    result.preferences_updated,
                )
        except Exception as e:
            logger.warning("Continuous learning failed: %s", e)

    def extract_knowledge(self, text: str) -> dict[str, Any]:
        """从文本提取实体关系知识（Phase S）。

        防御式：knowledge_graph 未注入时返回空结果。
        """
        if self._knowledge_graph is None:
            return {"entities": [], "relations": [], "count": 0}
        try:
            result = self._knowledge_graph.learn_from_text(text)
            return {
                "entities": len(result.entities),
                "relations": len(result.relations),
                "facts": len(result.facts),
                "confidence": result.confidence,
            }
        except Exception as e:
            logger.warning("Knowledge extraction failed: %s", e)
            return {"entities": 0, "relations": 0, "facts": 0, "confidence": 0.0}

    def search_knowledge(self, query: str) -> list[dict[str, Any]]:
        """搜索知识图谱。"""
        if self._knowledge_graph is None:
            return []
        try:
            entities = self._knowledge_graph.search_entities(query)
            return [
                {
                    "id": e.entity_id,
                    "name": e.name,
                    "type": e.entity_type.name,
                    "confidence": e.confidence,
                }
                for e in entities
            ]
        except Exception as e:
            logger.warning("Knowledge search failed: %s", e)
            return []

    def get_knowledge_stats(self) -> dict[str, Any]:
        """获取知识图谱统计。"""
        if self._knowledge_graph is None:
            return {"error": "knowledge_graph not injected"}
        try:
            return self._knowledge_graph.get_stats()
        except Exception as e:
            logger.warning("Knowledge stats failed: %s", e)
            return {"error": str(e)}

    # ── Phase AG: Knowledge Synthesis ─────────────────────────────────────

    def add_knowledge_node(
        self,
        content: str,
        node_type: str,
        tags: list[str] | None = None,
    ) -> str:
        """添加知识节点（Phase AG）。"""
        if self._knowledge_synthesis_manager is None:
            return ""
        try:
            from ocos.knowledge.synthesis_manager import KnowledgeType, KnowledgeSource
            # 基本校验：content 非空且不是纯空白
            if not content or not content.strip():
                return ""
            kt = KnowledgeType[node_type.upper()] if node_type.upper() in dir(KnowledgeType) else KnowledgeType.FACTUAL
            node = self._knowledge_synthesis_manager.add_knowledge(content, kt, KnowledgeSource.OBSERVATION)
            return node.node_id if node else ""
        except Exception as e:
            logger.error("add_knowledge_node failed: %s", e)
            return ""

    def get_knowledge_node(self, node_id: str) -> dict[str, Any] | None:
        """获取知识节点（Phase AG）。"""
        if self._knowledge_synthesis_manager is None:
            return None
        try:
            node = self._knowledge_synthesis_manager.get_knowledge(node_id)
            return node.to_dict() if node else None
        except Exception as e:
            logger.error("get_knowledge_node failed: %s", e)
            return None

    def synthesize_knowledge(self, node_ids: list[str]) -> dict[str, Any]:
        """综合知识（Phase AG）。"""
        if self._knowledge_synthesis_manager is None:
            return {}
        try:
            result = self._knowledge_synthesis_manager.synthesize_knowledge(node_ids)
            return result.to_dict() if result else {}
        except Exception as e:
            logger.error("synthesize_knowledge failed: %s", e)
            return {}

    def search_knowledge(self, query: str, limit: int = 10) -> list[dict]:
        """搜索知识（Phase AG）。"""
        if self._knowledge_synthesis_manager is None:
            return []
        try:
            nodes = self._knowledge_synthesis_manager.query_knowledge(query)
            return [n.to_dict() for n in nodes[:limit]]
        except Exception as e:
            logger.error("search_knowledge failed: %s", e)
            return []

    def get_path_between(
        self,
        source_id: str,
        target_id: str,
    ) -> list[dict]:
        """查找知识路径（Phase AG）。"""
        if self._knowledge_synthesis_manager is None:
            return []
        try:
            path = self._knowledge_synthesis_manager.find_path(source_id, target_id)
            return [n.to_dict() for n in path] if path else []
        except Exception as e:
            logger.error("get_path_between failed: %s", e)
            return []

    def assess_knowledge_quality(self) -> dict[str, Any]:
        """评估知识质量（Phase AG）。"""
        if self._knowledge_synthesis_manager is None:
            return {}
        try:
            # 评估第一个节点作为示例
            nodes = self._knowledge_synthesis_manager._nodes
            if nodes:
                first_node_id = next(iter(nodes))
                try:
                    return self._knowledge_synthesis_manager.assess_knowledge_quality(first_node_id)
                except TypeError:
                    return {"overall_score": 1.0}
            return {"overall_score": 0.0}
        except Exception as e:
            logger.error("assess_knowledge_quality failed: %s", e)
            return {}

    def get_knowledge_synthesis_stats(self) -> dict[str, Any]:
        """获取知识综合统计（Phase AG）。"""
        if self._knowledge_synthesis_manager is None:
            return {}
        try:
            return self._knowledge_synthesis_manager.get_stats()
        except Exception as e:
            logger.error("get_knowledge_synthesis_stats failed: %s", e)
            return {}

    def perceive(self) -> list[dict[str, Any]]:
        """执行一次感知周期（Phase T）。

        防御式：multimodal_perception 未注入时返回空列表。
        """
        if self._multimodal_perception is None:
            return []
        try:
            events = self._multimodal_perception.tick()
            return [
                {
                    "type": e.type.name if e.type else "unknown",
                    "sensor": e.sensor_name,
                    "content": str(e.observation.content)[:100] if e.observation else "",
                    "confidence": e.observation.confidence if e.observation else 0.0,
                }
                for e in events
            ]
        except Exception as e:
            logger.warning("Perception tick failed: %s", e)
            return []

    def feed_perception(self, modality: str, data: Any) -> None:
        """向指定模态输入数据（Phase T）。"""
        if self._multimodal_perception is None:
            return
        try:
            if modality == "text":
                self._multimodal_perception.feed_text(str(data))
            elif modality == "audio":
                self._multimodal_perception.feed_audio(data)
            elif modality == "vision":
                self._multimodal_perception.feed_vision(data)
            elif modality == "api":
                if isinstance(data, dict):
                    self._multimodal_perception.feed_api(data)
            elif modality == "event":
                event_type = data.get("type") if isinstance(data, dict) else str(data)
                payload = data.get("payload") if isinstance(data, dict) else None
                self._multimodal_perception.emit_event(event_type or "unknown", payload)
        except Exception as e:
            logger.warning("Perception feed failed: %s", e)

    def get_perception_stats(self) -> dict[str, Any]:
        """获取感知统计。"""
        if self._multimodal_perception is None:
            return {"error": "multimodal_perception not injected"}
        try:
            return self._multimodal_perception.get_stats()
        except Exception as e:
            logger.warning("Perception stats failed: %s", e)
            return {"error": str(e)}

    def check_sleep_need(self) -> dict[str, Any]:
        """检查是否需要睡眠（Phase U）。"""
        if self._sleep_dream_manager is None:
            return {"should_sleep": False, "reason": "sleep_manager_not_injected"}
        try:
            decision = self._sleep_dream_manager.decide_sleep()
            return {
                "should_sleep": decision.should_sleep,
                "reason": decision.reason,
                "sleep_type": decision.sleep_type,
                "estimated_duration": decision.estimated_duration,
            }
        except Exception as e:
            logger.warning("Sleep check failed: %s", e)
            return {"should_sleep": False, "reason": str(e)}

    def initiate_sleep(self) -> dict[str, Any]:
        """发起睡眠周期（Phase U）。"""
        if self._sleep_dream_manager is None:
            return {"status": "error", "reason": "sleep_manager_not_injected"}
        try:
            return self._sleep_dream_manager.run_sleep_cycle()
        except Exception as e:
            logger.warning("Sleep cycle failed: %s", e)
            return {"status": "error", "reason": str(e)}

    def get_sleep_stats(self) -> dict[str, Any]:
        """获取睡眠统计。"""
        if self._sleep_dream_manager is None:
            return {"error": "sleep_dream_manager not injected"}
        try:
            return self._sleep_dream_manager.get_stats()
        except Exception as e:
            logger.warning("Sleep stats failed: %s", e)
            return {"error": str(e)}

    def get_sleep_report(self) -> str:
        """生成睡眠报告。"""
        if self._sleep_dream_manager is None:
            return "睡眠管理器未注入"
        try:
            return self._sleep_dream_manager.generate_report()
        except Exception as e:
            logger.warning("Sleep report failed: %s", e)
            return f"睡眠报告生成失败: {e}"

    def save_state(self, data: dict[str, Any], reason: str = "") -> dict[str, Any]:
        """保存系统状态（Phase V）。"""
        if self._persistence_manager is None:
            return {"error": "persistence_manager not injected"}
        try:
            result = self._persistence_manager.save(data, reason=reason)
            return {"success": result.success, "snapshot_id": result.snapshot_id}
        except Exception as e:
            logger.warning("State save failed: %s", e)
            return {"error": str(e)}

    def restore_state(self, snapshot_id: str = "") -> dict[str, Any]:
        """恢复系统状态（Phase V）。"""
        if self._persistence_manager is None:
            return {"error": "persistence_manager not injected"}
        try:
            from ocos.persistence.manager import RestoreStrategy
            result = self._persistence_manager.restore(
                RestoreStrategy.SPECIFIC if snapshot_id else RestoreStrategy.LATEST,
                snapshot_id,
            )
            return {
                "success": result.success,
                "snapshot_id": result.snapshot_id,
                "domains": result.domains_restored,
            }
        except Exception as e:
            logger.warning("State restore failed: %s", e)
            return {"error": str(e)}

    def get_persistence_stats(self) -> dict[str, Any]:
        """获取持久化统计。"""
        if self._persistence_manager is None:
            return {"error": "persistence_manager not injected"}
        try:
            return self._persistence_manager.get_stats()
        except Exception as e:
            logger.warning("Persistence stats failed: %s", e)
            return {"error": str(e)}

    def auto_save_if_needed(self, data: dict[str, Any], tick: int = 0) -> Optional[dict[str, Any]]:
        """自动保存（基于时间间隔）。"""
        if self._persistence_manager is None:
            return None
        try:
            result = self._persistence_manager.auto_save_if_needed(data, tick)
            if result is None:
                return {"saved": False, "reason": "interval_not_reached"}
            return {"saved": True, "snapshot_id": result.snapshot_id}
        except Exception as e:
            logger.warning("Auto-save failed: %s", e)
            return None

    def start_server(self) -> bool:
        """启动外部集成服务器（Phase W）。"""
        if self._server_manager is None:
            return False
        try:
            return self._server_manager.start()
        except Exception as e:
            logger.warning("Start server failed: %s", e)
            return False

    def stop_server(self) -> bool:
        """停止外部集成服务器（Phase W）。"""
        if self._server_manager is None:
            return True
        try:
            return self._server_manager.stop()
        except Exception as e:
            logger.warning("Stop server failed: %s", e)
            return False

    def wait_for_server(self) -> None:
        """等待服务器运行（阻塞）（Phase W）。"""
        if self._server_manager is None:
            return
        try:
            self._server_manager.wait()
        except Exception as e:
            logger.warning("Wait for server failed: %s", e)

    def get_server_status(self) -> dict[str, Any]:
        """获取服务器状态（Phase W）。"""
        if self._server_manager is None:
            return {"error": "server_manager not injected"}
        try:
            return self._server_manager.get_status()
        except Exception as e:
            logger.warning("Get server status failed: %s", e)
            return {"error": str(e)}

    def health_check_server(self) -> dict[str, Any]:
        """执行服务器健康检查（Phase W）。"""
        if self._server_manager is None:
            return {"error": "server_manager not injected"}
        try:
            return self._server_manager.health_check()
        except Exception as e:
            logger.warning("Health check failed: %s", e)
            return {"error": str(e)}

    def register_webhook_handler(self, event_type: str, handler: Callable) -> None:
        """注册 webhook 处理器（Phase W）。"""
        if self._server_manager is None:
            return
        try:
            self._server_manager.register_webhook_handler(event_type, handler)
        except Exception as e:
            logger.warning("Register webhook handler failed: %s", e)

    def send_webhook(self, source: str, event_type: str, data: dict[str, Any]) -> bool:
        """发送 webhook（出站）（Phase W）。"""
        if self._server_manager is None:
            return False
        try:
            return self._server_manager.send_webhook(source, event_type, data)
        except Exception as e:
            logger.warning("Send webhook failed: %s", e)
            return False

    def check_access(
        self,
        source: str,
        action: str,
        policy_name: str = "default",
        metadata: Optional[dict[str, Any]] = None,
    ) -> tuple[Any, str, dict[str, Any]]:
        """检查访问权限（Phase X）。"""
        if self._security_manager is None:
            return AccessDecision.ALLOW, "security not injected", {}
        try:
            from ocos.security.manager import AccessDecision
            return self._security_manager.check_access(
                source, action, policy_name=policy_name, metadata=metadata
            )
        except Exception as e:
            logger.warning("Check access failed: %s", e)
            return AccessDecision.DENY, str(e), {}

    def sanitize_input(self, text: str, source: str = "unknown") -> tuple[str, list[str], Any]:
        """清洗并检查输入（Phase X）。"""
        if self._security_manager is None:
            return text, [], AccessDecision.ALLOW
        try:
            from ocos.security.manager import AccessDecision
            return self._security_manager.sanitize_input(text, source=source)
        except Exception as e:
            logger.warning("Sanitize input failed: %s", e)
            return text, [], AccessDecision.DENY

    def get_security_stats(self) -> dict[str, Any]:
        """获取安全统计（Phase X）。"""
        if self._security_manager is None:
            return {"error": "security_manager not injected"}
        try:
            return self._security_manager.get_security_stats()
        except Exception as e:
            logger.warning("Security stats failed: %s", e)
            return {"error": str(e)}

    def get_recent_security_events(self, limit: int = 100) -> list[dict[str, Any]]:
        """获取最近安全事件（Phase X）。"""
        if self._security_manager is None:
            return []
        try:
            return self._security_manager.get_recent_events(limit)
        except Exception as e:
            logger.warning("Get security events failed: %s", e)
            return []

    def get_monitoring_stats(self) -> dict[str, Any]:
        """获取监控统计（Phase Y）。"""
        if self._monitoring_manager is None:
            return {"error": "monitoring_manager not injected"}
        try:
            return self._monitoring_manager.get_stats()
        except Exception as e:
            logger.warning("Monitoring stats failed: %s", e)
            return {"error": str(e)}

    def get_metrics(self) -> str:
        """获取 Prometheus 格式指标（Phase Y）。"""
        if self._monitoring_manager is None:
            return "# monitoring not injected"
        try:
            return self._monitoring_manager.get_metrics()
        except Exception as e:
            logger.warning("Get metrics failed: %s", e)
            return f"# error: {e}"

    def get_health_status(self) -> dict[str, Any]:
        """获取综合健康状态（Phase Y）。"""
        if self._monitoring_manager is None:
            return {"error": "monitoring_manager not injected"}
        try:
            return self._monitoring_manager.get_health_status()
        except Exception as e:
            logger.warning("Health status failed: %s", e)
            return {"error": str(e)}

    def record_metric(self, name: str, value: float, metric_type: str = "counter",
                      labels: Optional[dict[str, str]] = None) -> None:
        """记录指标（Phase Y）。"""
        if self._monitoring_manager is None:
            return
        try:
            self._monitoring_manager.record_metric(name, value, metric_type=metric_type, labels=labels)
        except Exception as e:
            logger.warning("Record metric failed: %s", e)

    def start_monitoring(self) -> bool:
        """启动监控服务（Phase Y）。"""
        if self._monitoring_manager is None:
            return False
        try:
            return self._monitoring_manager.start_http()
        except Exception as e:
            logger.warning("Start monitoring failed: %s", e)
            return False

    def stop_monitoring(self) -> None:
        """停止监控服务（Phase Y）。"""
        if self._monitoring_manager is None:
            return
        try:
            self._monitoring_manager.stop_http()
        except Exception as e:
            logger.warning("Stop monitoring failed: %s", e)

    # ── Phase AA: Self-Evolution ────────────────────────────────────

    def detect_evolution_opportunity(
        self,
        source_module: str,
        metric_name: str,
        metric_value: float,
        threshold: float,
        severity: float,
        description: str,
        trigger: str = "experience",
    ) -> dict[str, Any]:
        """检测进化机会并生成提案（Phase AA）。"""
        if self._self_evolution_manager is None:
            return {"error": "self_evolution_manager not injected"}
        try:
            from ocos.evolution.evolution_types import EvolutionTrigger
            trigger_enum = getattr(EvolutionTrigger, trigger.upper(), EvolutionTrigger.EXPERIENCE_PATTERN)
            proposal = self._self_evolution_manager.detect_and_propose(
                source_module=source_module,
                metric_name=metric_name,
                metric_value=metric_value,
                threshold=threshold,
                severity=severity,
                description=description,
                trigger=trigger_enum,
            )
            if proposal:
                return {
                    "proposal_id": proposal.proposal_id,
                    "domain": proposal.domain.value,
                    "state": proposal.state.value,
                    "description": proposal.description,
                }
            return {"error": "max proposals reached"}
        except Exception as e:
            logger.warning("Detect evolution opportunity failed: %s", e)
            return {"error": str(e)}

    def analyze_evolution_proposal(self, proposal_id: str) -> dict[str, Any]:
        """分析进化提案影响（Phase AA）。"""
        if self._self_evolution_manager is None:
            return {"error": "self_evolution_manager not injected"}
        try:
            impact = self._self_evolution_manager.analyze_proposal(proposal_id)
            if impact:
                return {
                    "proposal_id": proposal_id,
                    "impact_level": impact.level.value,
                    "is_safe": impact.is_safe,
                    "affected_modules": impact.affected_modules,
                }
            return {"error": "proposal not found"}
        except Exception as e:
            logger.warning("Analyze evolution proposal failed: %s", e)
            return {"error": str(e)}

    def validate_evolution_proposal(self, proposal_id: str) -> dict[str, Any]:
        """在沙箱中验证进化提案（Phase AA）。"""
        if self._self_evolution_manager is None:
            return {"error": "self_evolution_manager not injected"}
        try:
            report = self._self_evolution_manager.validate_proposal(proposal_id)
            if report:
                return {
                    "proposal_id": proposal_id,
                    "result": report.result.value,
                    "test_count": report.test_count,
                    "passed_count": report.passed_count,
                    "errors": report.errors,
                }
            return {"error": "proposal not found"}
        except Exception as e:
            logger.warning("Validate evolution proposal failed: %s", e)
            return {"error": str(e)}

    def approve_evolution_proposal(self, proposal_id: str, approver: str = "human") -> bool:
        """人工批准进化提案（Phase AA）。"""
        if self._self_evolution_manager is None:
            return False
        try:
            return self._self_evolution_manager.approve_proposal(proposal_id, approver)
        except Exception as e:
            logger.warning("Approve evolution proposal failed: %s", e)
            return False

    def execute_evolution_proposal(self, proposal_id: str) -> dict[str, Any]:
        """执行已批准的进化提案（Phase AA）。"""
        if self._self_evolution_manager is None:
            return {"error": "self_evolution_manager not injected"}
        try:
            result = self._self_evolution_manager.execute_proposal(proposal_id)
            if result:
                return {
                    "proposal_id": proposal_id,
                    "success": result.success,
                    "tick": result.tick,
                    "error": result.error,
                }
            return {"error": "proposal not found or not ready"}
        except Exception as e:
            logger.warning("Execute evolution proposal failed: %s", e)
            return {"error": str(e)}

    def rollback_evolution(self, proposal_id: str, reason: str = "test_failure") -> bool:
        """回滚已执行的进化（Phase AA）。"""
        if self._self_evolution_manager is None:
            return False
        try:
            from ocos.evolution.evolution_types import RollbackReason
            reason_enum = getattr(RollbackReason, reason.upper(), RollbackReason.TEST_FAILURE)
            return self._self_evolution_manager.rollback(proposal_id, reason_enum)
        except Exception as e:
            logger.warning("Rollback evolution failed: %s", e)
            return False

    def get_evolution_status(self) -> dict[str, Any]:
        """获取进化状态摘要（Phase AA）。"""
        if self._self_evolution_manager is None:
            return {"error": "self_evolution_manager not injected"}
        try:
            status = self._self_evolution_manager.get_status()
            return {
                "total_proposals": status.total_proposals,
                "pending_proposals": status.pending_proposals,
                "approved_proposals": status.approved_proposals,
                "active_proposals": status.active_proposals,
                "rejected_proposals": status.rejected_proposals,
                "rolled_back_proposals": status.rolled_back_proposals,
                "total_migrations": status.total_migrations,
                "successful_migrations": status.successful_migrations,
                "failed_migrations": status.failed_migrations,
                "last_evolution_time": status.last_evolution_time,
                "last_evolution_domain": status.last_evolution_domain,
                "last_evolution_result": status.last_evolution_result,
            }
        except Exception as e:
            logger.warning("Get evolution status failed: %s", e)
            return {"error": str(e)}

    def get_evolution_history(self) -> list[dict]:
        """获取进化历史（Phase AA）。"""
        if self._self_evolution_manager is None:
            return []
        try:
            return self._self_evolution_manager.get_history()
        except Exception as e:
            logger.warning("Get evolution history failed: %s", e)
            return []

    def get_evolution_proposals(self, state: str | None = None) -> list[dict]:
        """列出进化提案（Phase AA）。"""
        if self._self_evolution_manager is None:
            return []
        try:
            from ocos.evolution.evolution_types import EvolutionState
            state_enum = None
            if state:
                state_enum = getattr(EvolutionState, state.upper(), None)
            proposals = self._self_evolution_manager.list_proposals(state=state_enum)
            return [
                {
                    "proposal_id": p.proposal_id,
                    "domain": p.domain.value,
                    "state": p.state.value,
                    "description": p.description[:100],
                    "trigger": p.trigger.value,
                }
                for p in proposals
            ]
        except Exception as e:
            logger.warning("Get evolution proposals failed: %s", e)
            return []

    def tick(self) -> dict:
        """主循环 tick（Phase AA/AB/AC/AD/AE/AF/AG 扩展）。"""
        result = {"tick": 0, "evolutions": [], "distributed": {}, "ecosystem": {}, "human_ai": {}, "reflection": {}, "optimization": {}, "knowledge": {}}
        if self._self_evolution_manager is not None:
            try:
                result["evolutions"] = self._self_evolution_manager.tick()
            except Exception as e:
                logger.warning("Evolution tick failed: %s", e)
        if self._distributed_manager is not None:
            try:
                result["distributed"] = self._distributed_manager.get_stats()
            except Exception as e:
                logger.warning("Distributed tick failed: %s", e)
        if self._ecosystem_manager is not None:
            try:
                result["ecosystem"] = self._ecosystem_manager.get_stats()
            except Exception as e:
                logger.warning("Ecosystem tick failed: %s", e)
        if self._human_ai_manager is not None:
            try:
                result["human_ai"] = self._human_ai_manager.get_stats()
            except Exception as e:
                logger.warning("HumanAI tick failed: %s", e)
        if self._self_reflection_manager is not None:
            try:
                result["reflection"] = self._self_reflection_manager.get_stats()
            except Exception as e:
                logger.warning("Reflection tick failed: %s", e)
        if self._self_optimization_manager is not None:
            try:
                result["optimization"] = self._self_optimization_manager.get_stats()
            except Exception as e:
                logger.warning("Optimization tick failed: %s", e)
        if self._knowledge_synthesis_manager is not None:
            try:
                result["knowledge"] = self._knowledge_synthesis_manager.get_stats()
            except Exception as e:
                logger.warning("Get knowledge stats failed: %s", e)

        if self._self_diagnosis_manager is not None:
            try:
                result["diagnosis"] = self._self_diagnosis_manager.get_stats()
            except Exception as e:
                logger.warning("Get diagnosis stats failed: %s", e)

        if self._tool_manager is not None:
            try:
                result["tool"] = self._tool_manager.get_status()
            except Exception as e:
                logger.warning("Get tool stats failed: %s", e)

        if self._proactive_output_enhanced is not None:
            try:
                result["proactive_output"] = self._proactive_output_enhanced.get_status()
            except Exception as e:
                logger.warning("Get proactive output stats failed: %s", e)

        return result

    # ── Phase AC: Ecosystem Integration ─────────────────────────────

    def register_extension(
        self,
        name: str,
        ext_type: str,
        version: str = "1.0.0",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """注册新扩展（Phase AC）。"""
        if self._ecosystem_manager is None:
            return {"error": "ecosystem_manager not injected"}
        try:
            ext = self._ecosystem_manager.register_extension(name, ext_type, version, metadata)
            if ext:
                return {"extension_id": ext.extension_id, "name": ext.name, "state": ext.state.value}
            return {"error": "max extensions reached or registration failed"}
        except Exception as e:
            return {"error": str(e)}

    def approve_extension(self, extension_id: str) -> dict[str, Any]:
        """批准扩展（Phase AC）。"""
        if self._ecosystem_manager is None:
            return {"error": "ecosystem_manager not injected"}
        try:
            result = self._ecosystem_manager.approve_extension(extension_id)
            return {"success": result}
        except Exception as e:
            return {"error": str(e)}

    def integrate_extension(self, extension_id: str) -> dict[str, Any]:
        """集成扩展（Phase AC）。"""
        if self._ecosystem_manager is None:
            return {"error": "ecosystem_manager not injected"}
        try:
            result = self._ecosystem_manager.integrate_extension(extension_id)
            return {"success": result}
        except Exception as e:
            return {"error": str(e)}

    def activate_extension(self, extension_id: str) -> dict[str, Any]:
        """激活扩展（Phase AC）。"""
        if self._ecosystem_manager is None:
            return {"error": "ecosystem_manager not injected"}
        try:
            result = self._ecosystem_manager.activate_extension(extension_id)
            return {"success": result}
        except Exception as e:
            return {"error": str(e)}

    def load_plugin(
        self,
        name: str,
        entry_point: str,
        required_permissions: list[str] | None = None,
    ) -> dict[str, Any]:
        """加载插件（Phase AC）。"""
        if self._ecosystem_manager is None:
            return {"error": "ecosystem_manager not injected"}
        try:
            plugin = self._ecosystem_manager.load_plugin(name, entry_point, required_permissions)
            if plugin:
                return {"plugin_id": plugin.plugin_id, "name": plugin.name, "state": plugin.state.value}
            return {"error": "max plugins reached or load failed"}
        except Exception as e:
            return {"error": str(e)}

    def start_plugin(self, plugin_id: str) -> dict[str, Any]:
        """启动插件（Phase AC）。"""
        if self._ecosystem_manager is None:
            return {"error": "ecosystem_manager not injected"}
        try:
            result = self._ecosystem_manager.start_plugin(plugin_id)
            return {"success": result}
        except Exception as e:
            return {"error": str(e)}

    def get_ecosystem_stats(self) -> dict[str, Any]:
        """获取生态统计信息（Phase AC）。"""
        if self._ecosystem_manager is None:
            return {"error": "ecosystem_manager not injected"}
        return self._ecosystem_manager.get_stats()

    # ── Phase AD: Human-AI Collaboration ─────────────────────────

    def set_preference(self, key: str, value: Any, source: str = "explicit") -> dict[str, Any]:
        """设置用户偏好（Phase AD）。"""
        if self._human_ai_manager is None:
            return {"error": "human_ai_manager not injected"}
        try:
            pref = self._human_ai_manager.set_preference(key, value, source)
            if pref:
                return {"preference_id": pref.preference_id, "key": pref.key, "value": pref.value}
            return {"error": "max preferences reached"}
        except Exception as e:
            return {"error": str(e)}

    def get_preference(self, key: str) -> Any:
        """获取用户偏好（Phase AD）。"""
        if self._human_ai_manager is None:
            return None
        return self._human_ai_manager.get_preference(key)

    def record_feedback(self, feedback_type: str, content: str, context: dict | None = None) -> dict[str, Any]:
        """记录用户反馈（Phase AD）。"""
        if self._human_ai_manager is None:
            return {"error": "human_ai_manager not injected"}
        from ocos.human.manager import FeedbackType
        try:
            fb_type = FeedbackType(feedback_type)
            feedback = self._human_ai_manager.record_feedback(fb_type, content, context)
            return {"feedback_id": feedback.feedback_id, "type": feedback.type.value}
        except Exception as e:
            return {"error": str(e)}

    def start_conversation(self, mode: str = "assistant") -> dict[str, Any]:
        """开始对话（Phase AD）。"""
        if self._human_ai_manager is None:
            return {"error": "human_ai_manager not injected"}
        from ocos.human.manager import CollaborationMode
        try:
            conv_mode = CollaborationMode(mode)
            conv = self._human_ai_manager.start_conversation(conv_mode)
            if conv:
                return {"conversation_id": conv.conversation_id, "mode": conv.mode.value}
            return {"error": "max conversations reached"}
        except Exception as e:
            return {"error": str(e)}

    def infer_intent(self, message: str) -> dict[str, Any]:
        """推断用户意图（Phase AD）。"""
        if self._human_ai_manager is None:
            return {"error": "human_ai_manager not injected"}
        return self._human_ai_manager.infer_intent(message)

    def get_human_ai_stats(self) -> dict[str, Any]:
        """获取人机协同统计（Phase AD）。"""
        if self._human_ai_manager is None:
            return {"error": "human_ai_manager not injected"}
        return self._human_ai_manager.get_stats()

    # ── Phase AE: Self-Reflection ───────────────────────────────

    def start_reflection(self, reflection_type: str, subject_id: str, depth: str = "analytical") -> dict[str, Any]:
        """开始反思（Phase AE）。"""
        if self._self_reflection_manager is None:
            return {"error": "self_reflection_manager not injected"}
        from ocos.reflection.manager import ReflectionType, ReflectionDepth
        try:
            rt = ReflectionType[reflection_type.upper()]
            rd = ReflectionDepth(depth)
            trace = self._self_reflection_manager.start_reflection(rt, subject_id, rd)
            if trace:
                return {"trace_id": trace.trace_id, "type": trace.reflection_type.name}
            return {"error": "max reflections reached"}
        except Exception as e:
            return {"error": str(e)}

    def add_reflection_insight(self, trace_id: str, insight_type: str, content: str, confidence: float = 0.5) -> bool:
        """添加反思洞察（Phase AE）。"""
        if self._self_reflection_manager is None:
            return False
        from ocos.reflection.manager import InsightType
        try:
            it = InsightType(insight_type.lower())
            return self._self_reflection_manager.add_insight(trace_id, it, content, confidence)
        except Exception as e:
            logger.warning("Add insight failed: %s", e)
            return False

    def complete_reflection(self, trace_id: str) -> bool:
        """完成反思（Phase AE）。"""
        if self._self_reflection_manager is None:
            return False
        return self._self_reflection_manager.complete_reflection(trace_id)

    def propose_wisdom(self, trace_id: str, content: str, confidence: float = 0.5) -> dict[str, Any]:
        """提出智慧候选（Phase AE）。"""
        if self._self_reflection_manager is None:
            return {"error": "self_reflection_manager not injected"}
        wisdom = self._self_reflection_manager.propose_wisdom(trace_id, content, confidence)
        if wisdom:
            return {"wisdom_id": wisdom.wisdom_id, "confidence": wisdom.confidence}
        return {"error": "max wisdom items reached"}

    def verify_wisdom(self, wisdom_id: str, result: bool) -> bool:
        """验证智慧（Phase AE）。"""
        if self._self_reflection_manager is None:
            return False
        return self._self_reflection_manager.verify_wisdom(wisdom_id, result)

    def check_identity_continuity(self, current_state: dict[str, Any], window: int = 10) -> dict[str, Any]:
        """检查身份连续性（Phase AE）。"""
        if self._self_reflection_manager is None:
            return {"error": "self_reflection_manager not injected"}
        return self._self_reflection_manager.check_identity_continuity(current_state, window)

    def get_reflection_stats(self) -> dict[str, Any]:
        """获取反思统计（Phase AE）。"""
        if self._self_reflection_manager is None:
            return {"error": "self_reflection_manager not injected"}
        return self._self_reflection_manager.get_stats()

    # ── Phase AF: Self-Optimization ─────────────────────────────

    def set_optimization_baseline(self, metric_name: str, value: float) -> None:
        """设置优化基线（Phase AF）。"""
        if self._self_optimization_manager is None:
            return
        self._self_optimization_manager.set_baseline(metric_name, value)

    def get_optimization_baseline(self, metric_name: str) -> float | None:
        """获取优化基线（Phase AF）。"""
        if self._self_optimization_manager is None:
            return None
        return self._self_optimization_manager.get_baseline(metric_name)

    def propose_optimization(
        self,
        opt_type: str,
        description: str,
        expected_improvement: float,
        risk_level: str = "low",
    ) -> dict[str, Any]:
        """提出优化提案（Phase AF）。"""
        if self._self_optimization_manager is None:
            return {"error": "self_optimization_manager not injected"}
        from ocos.optimization.manager import OptimizationType
        try:
            ot = OptimizationType[opt_type.upper()]
            proposal = self._self_optimization_manager.propose_optimization(
                ot, description, expected_improvement, risk_level
            )
            if proposal:
                return {"proposal_id": proposal.proposal_id, "type": proposal.opt_type.name}
            return {"error": "max proposals reached"}
        except Exception as e:
            return {"error": str(e)}

    def apply_optimization(self, proposal_id: str, before_metrics: dict[str, float]) -> dict[str, Any]:
        """应用优化方案（Phase AF）。"""
        if self._self_optimization_manager is None:
            return {"error": "self_optimization_manager not injected"}
        result = self._self_optimization_manager.apply_optimization(proposal_id, before_metrics)
        if result:
            return {"result_id": result.result_id, "status": result.status.value}
        return {"error": "proposal not found"}

    def validate_optimization(self, result_id: str, after_metrics: dict[str, float]) -> bool:
        """验证优化效果（Phase AF）。"""
        if self._self_optimization_manager is None:
            return False
        return self._self_optimization_manager.validate_optimization(result_id, after_metrics)

    def rollback_optimization(self, result_id: str) -> bool:
        """回滚优化（Phase AF）。"""
        if self._self_optimization_manager is None:
            return False
        return self._self_optimization_manager.rollback_optimization(result_id)

    def get_optimization_stats(self) -> dict[str, Any]:
        """获取优化统计（Phase AF）。"""
        if self._self_optimization_manager is None:
            return {"error": "self_optimization_manager not injected"}
        return self._self_optimization_manager.get_stats()

    # ── Phase AH: Self-Diagnosis ──────────────────────────────────────

    def diagnose(self) -> dict[str, Any]:
        """执行自我诊断（Phase AH）。"""
        if self._self_diagnosis_manager is None:
            return {"error": "self_diagnosis_manager not injected"}
        try:
            result = self._self_diagnosis_manager.diagnose()
            return {
                "snapshot_id": result.snapshot_id,
                "overall_health": result.overall_health,
                "faults_detected": result.faults_detected,
                "trend": result.trend,
            }
        except Exception as e:
            logger.error("diagnose failed: %s", e)
            return {"error": str(e)}

    def get_diagnosis_status(self) -> dict[str, Any]:
        """获取诊断健康状态（Phase AH）。"""
        if self._self_diagnosis_manager is None:
            return {}
        try:
            return self._self_diagnosis_manager.get_health_status()
        except Exception as e:
            logger.error("get_diagnosis_status failed: %s", e)
            return {}

    def get_diagnosis_history(self, limit: int = 10) -> list[dict]:
        """获取诊断历史（Phase AH）。"""
        if self._self_diagnosis_manager is None:
            return []
        try:
            return self._self_diagnosis_manager.get_diagnosis_history(limit)
        except Exception as e:
            logger.error("get_diagnosis_history failed: %s", e)
            return []

    def get_fault_history(self, limit: int = 20) -> list[dict]:
        """获取故障历史（Phase AH）。"""
        if self._self_diagnosis_manager is None:
            return []
        try:
            return self._self_diagnosis_manager.get_fault_history(limit)
        except Exception as e:
            logger.error("get_fault_history failed: %s", e)
            return []

    def get_repair_history(self, limit: int = 20) -> dict:
        """获取修复历史（Phase AH）。"""
        if self._self_diagnosis_manager is None:
            return {}
        try:
            return self._self_diagnosis_manager.get_repair_history(limit)
        except Exception as e:
            logger.error("get_repair_history failed: %s", e)
            return {}

    def get_diagnosis_stats(self) -> dict[str, Any]:
        """获取诊断统计（Phase AH）。"""
        if self._self_diagnosis_manager is None:
            return {}
        try:
            return self._self_diagnosis_manager.get_stats()
        except Exception as e:
            logger.error("get_diagnosis_stats failed: %s", e)
            return {}

    def register_cognition_instance(
        self, instance_id: str, host: str, port: int,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """注册认知实例（Phase AB）。"""
        if self._distributed_manager is None:
            return {"error": "distributed_manager not injected"}
        try:
            inst = self._distributed_manager.register_instance(instance_id, host, port, metadata)
            if inst:
                return {"instance_id": inst.instance_id, "state": inst.state.value}
            return {"error": "registration failed (max instances or duplicate)"}
        except Exception as e:
            logger.warning("Register instance failed: %s", e)
            return {"error": str(e)}

    def deregister_cognition_instance(self, instance_id: str) -> bool:
        """注销认知实例（Phase AB）。"""
        if self._distributed_manager is None:
            return False
        try:
            return self._distributed_manager.deregister_instance(instance_id)
        except Exception as e:
            logger.warning("Deregister instance failed: %s", e)
            return False

    def heartbeat_instance(self, instance_id: str) -> bool:
        """更新实例心跳（Phase AB）。"""
        if self._distributed_manager is None:
            return False
        try:
            return self._distributed_manager.update_heartbeat(instance_id)
        except Exception as e:
            logger.warning("Heartbeat failed: %s", e)
            return False

    def submit_distributed_task(
        self, task_type: str, payload: dict[str, Any],
        source_instance: str | None = None,
    ) -> dict[str, Any]:
        """提交分布式任务（Phase AB）。"""
        if self._distributed_manager is None:
            return {"error": "distributed_manager not injected"}
        try:
            task = self._distributed_manager.submit_task(task_type, payload, source_instance)
            return {"task_id": task.task_id, "status": task.status}
        except Exception as e:
            logger.warning("Submit task failed: %s", e)
            return {"error": str(e)}

    def dispatch_distributed_task(self, task_id: str) -> bool:
        """分发布局式任务（Phase AB）。"""
        if self._distributed_manager is None:
            return False
        try:
            task = next((t for t in self._distributed_manager._pending_tasks if t.task_id == task_id), None)
            if task:
                return self._distributed_manager.dispatch_task(task)
            return False
        except Exception as e:
            logger.warning("Dispatch task failed: %s", e)
            return False

    def complete_distributed_task(self, task_id: str, result: dict[str, Any]) -> bool:
        """完成分布式任务（Phase AB）。"""
        if self._distributed_manager is None:
            return False
        try:
            return self._distributed_manager.complete_task(task_id, result)
        except Exception as e:
            logger.warning("Complete task failed: %s", e)
            return False

    def fail_distributed_task(self, task_id: str, error: str) -> bool:
        """标记分布式任务失败（Phase AB）。"""
        if self._distributed_manager is None:
            return False
        try:
            return self._distributed_manager.fail_task(task_id, error)
        except Exception as e:
            logger.warning("Fail task failed: %s", e)
            return False

    def get_distributed_stats(self) -> dict[str, Any]:
        """获取分布式统计（Phase AB）。"""
        if self._distributed_manager is None:
            return {"error": "distributed_manager not injected"}
        try:
            return self._distributed_manager.get_stats()
        except Exception as e:
            logger.warning("Get distributed stats failed: %s", e)
            return {"error": str(e)}

    def get_healthy_instances(self) -> list[dict]:
        """获取健康实例列表（Phase AB）。"""
        if self._distributed_manager is None:
            return []
        try:
            instances = self._distributed_manager.get_healthy_instances()
            return [
                {
                    "instance_id": i.instance_id,
                    "host": i.host,
                    "port": i.port,
                    "state": i.state.value,
                    "task_count": i.task_count,
                }
                for i in instances
            ]
        except Exception as e:
            logger.warning("Get healthy instances failed: %s", e)
            return []

    def check_distributed_health(self) -> list[str]:
        """检查分布式健康（Phase AB）。"""
        if self._distributed_manager is None:
            return []
        try:
            return self._distributed_manager.check_health()
        except Exception as e:
            logger.warning("Check health failed: %s", e)
            return []

    # ── 辅助 ──────────────────────────────────────────────────────────

    def get_status_report(self) -> dict[str, Any]:
        """获取 Agent 状态摘要。"""
        return {
            "agent_id": self.agent_id,
            "lifecycle": self._lifecycle.freeze(),
            "focus": (
                self.attention.current_focus()
                if hasattr(self.attention, "current_focus")
                else None
            ),
            "active_goal": (
                self.goal_stack.peek()
                if hasattr(self.goal_stack, "peek")
                else None
            ),
            "working_memory_count": (
                len(self.working_memory.list_items())
                if hasattr(self.working_memory, "list_items")
                else 0
            ),
            "capabilities": (
                self.capability_manager.list_capabilities()
                if hasattr(self.capability_manager, "list_capabilities")
                else []
            ),
            "is_executing": (
                self.execution_manager.is_executing()
                if hasattr(self.execution_manager, "is_executing")
                else False
            ),
        }

    def shutdown(self) -> None:
        """安全关闭。"""
        self._control_loop.shutdown()

    # ── 内部 ──────────────────────────────────────────────────────────

    def _safe_return_to_idle(self) -> None:
        """引擎失败时安全回到 IDLE，防止死锁。"""
        try:
            if self._lifecycle.phase == LifecyclePhase.ACTIVE:
                self._lifecycle.force_idle()
        except Exception:
            pass  # 最坏情况下也不应阻塞
