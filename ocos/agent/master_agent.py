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

import threading
import uuid
from typing import Any, Optional

from ocos.agent.state import AgentState, AgentStatus
from ocos.agent.lifecycle import LifecycleManager, LifecyclePhase, MicroState
from ocos.agent.control_loop import ControlLoop
from ocos.agent.cognitive_bridge import CognitiveBridge, BridgeResult
from ocos.agent.goal_types import Goal, GoalLevel, GoalOriginLevel
from ocos.goal.factory import ConstitutionViolationError
from ocos.goal.enforcer import GoalOriginEnforcer
from ocos.kernel.abi import Observation


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
        self._experience_builder = experience_builder
        self._episode_store = episode_store

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
            except Exception:
                pass  # Constitution 错误不应阻塞决策

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
        self._last_action_result = action_result
        return action_result

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

        self._control_loop.wake_from_sleep()
        return consolidation

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
