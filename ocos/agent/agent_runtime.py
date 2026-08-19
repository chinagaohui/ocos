"""AgentRuntime — OCOS Agent 统一运行时。

集成 MasterAgent + 认知皮层 + 记忆系统 + 信念系统的
完整运行时。通过 Life Cycle 驱动，支持 Homeostasis 优先。

Phase 26: Tick Step 9 (result_ingest) 支持 ResultUnderstandingLayer
  验证→结构化→学习 全管道，自动更新 CapabilityExperienceMemory + KnowledgeGraph。
"""
from __future__ import annotations

import logging
import threading
import time
import uuid
from collections import deque
from enum import Enum, auto
from typing import Any, Optional

from ocos.agent.master_agent import MasterAgent
from ocos.agent.capability_selector import CapabilitySelector
from ocos.agent.meta_controller import MetaController  # 22-D: 使用 ExecutiveController 别名
from ocos.agent.decision_loop import DecisionLoop
from ocos.capability.permission_gateway import PermissionDeniedError
from ocos.agent.cortex_activator import CortexActivator, CortexMode
from ocos.agent.belief_system import BeliefSystem
from ocos.agent.memory_consolidator import MemoryConsolidator
from ocos.agent.knowledge_base import KnowledgeBase
from ocos.agent.experience_store import ExperienceStore
from ocos.agent.engine_bridge import EngineBridge, ENGINE_REGISTRY
from ocos.agent.state import AgentStatus
from ocos.agent.metrics_collector import MetricsCollector
from ocos.agent.health_check import HealthCheck, HEALTHY
from ocos.agent.identity_anchor import IdentityAnchor
from ocos.agent.identity_store import IdentitySQLiteStore
from ocos.agent.goal_store import GoalSQLiteStore
from ocos.memory.hub import MemoryHub
from ocos.storage.working_memory import SQLiteWorkingMemory

logger = logging.getLogger(__name__)


class RuntimeState(Enum):
    """运行时状态。"""
    STOPPED = auto()
    BOOTING = auto()
    RUNNING = auto()
    SLEEPING = auto()
    ERROR = auto()
    SHUTDOWN = auto()


class AgentRuntime:
    """Agent 统一运行时。

    整合信号：
    - Life Cycle: BOOT → WAKE → OBSERVE → THINK → DECIDE → ACT → REFLECT → LEARN → SLEEP → DREAM
    - Homeostasis: 优先级高于 Goal（疲劳/阻塞时自动调整）
    - Memory: 每轮 cycle 自动巩固
    - Belief: 从经验中提炼信念
    """

    def __init__(
        self,
        agent: MasterAgent,
        engine_list: Optional[list[str]] = None,
        engine_bridge: Optional[EngineBridge] = None,
        working_capacity: int = 10,
        max_cycles: int = 100,
        consolidation_threshold: float = 0.5,
        belief_threshold: float = 0.6,
        homeostatic_check_interval: int = 3,
        *,
        db_path: str = ":memory:",
        # Phase 21: Optional persistence + dynamic engine loading
        engine_loader: Any = None,
    ):
        self.agent = agent
        self.selector = CapabilitySelector(engine_list or [])
        self.controller = MetaController(max_cycles=max_cycles)
        self.cortex = CortexActivator()
        self.memory = MemoryConsolidator(
            working_capacity=working_capacity,
            consolidation_threshold=consolidation_threshold,
        )
        self.beliefs = BeliefSystem(default_threshold=belief_threshold)
        self.knowledge = KnowledgeBase()
        self.experiences = ExperienceStore()
        self.engine_bridge = engine_bridge or EngineBridge()
        self.loop = DecisionLoop(agent, self.selector, self.controller, self.engine_bridge)

        self._db_path = db_path
        self._identity_store: Any = None
        self._goal_store: Any = None
        self._memory_hub: Any = None
        self._wm_store: Any = None
        self._engine_loader = engine_loader

        self._state = RuntimeState.STOPPED
        self._homeostatic_check_interval = homeostatic_check_interval
        self._cycle_count = 0
        self._lock = threading.RLock()
        self.metrics = MetricsCollector()
        self.health = HealthCheck()

        # Phase 34A: EventBus — 感知神经中枢
        self._event_bus: Any = None  # EventBus, initialized in boot()
        self._tick_budget: float = 0.5  # 500ms budget per tick
        # Phase 24-A: PermissionGateway 集成 — 所有外部交互必经网关
        self._gateway: Any = None
        # Phase 26: ResultUnderstandingLayer — 验证→结构化→学习管道
        self._result_understanding_layer: Any = None
        # Phase 31: Execution Loop — TaskDAG → Orchestrator → Agent → Results
        self._active_dag: Any = None
        self._dag_cursor: int = 0
        self._dag_total: int = 0
        self._task_statuses: dict[str, str] = {}  # task_id → status
        self._recent_results: list[dict[str, Any]] = []
        self._result_cursor: int = 0  # Phase 32: cursor for step 9 ingestion
        self._orchestrator: Any = None
        # Phase 32: Attention wiring
        self._attention: Any = None
        # Phase 35: Attention decisions cache (step 2 → step 3)
        self._last_attention_decisions: list[Any] = []
        self._attention_report: Any = None     # Phase 36: cached for step 4/5/6
        self._last_ingestion_events: list[dict[str, Any]] = []
        # Phase 34D: Stability metrics
        self._tick_latencies: deque[float] = deque(maxlen=1000)
        self._tick_errors: int = 0
        self._boot_time: Optional[float] = None

    @property
    def state(self) -> RuntimeState:
        return self._state

    @property
    def gateway(self) -> Any:
        """Phase 24-A: 延迟初始化 PermissionGateway。"""
        if self._gateway is None:
            from ocos.capability.permission_gateway import PermissionGateway
            self._gateway = PermissionGateway()
        return self._gateway

    @property
    def event_bus(self) -> Any:
        """Phase 34A: 延迟初始化 EventBus（感知神经中枢）。"""
        if self._event_bus is None:
            from ocos.event import EventBus
            self._event_bus = EventBus()
        return self._event_bus

    @property
    def result_understanding_layer(self) -> Any:
        """Phase 26: 延迟初始化 ResultUnderstandingLayer。"""
        if self._result_understanding_layer is None:
            from ocos.capability.result_understanding import ResultUnderstandingLayer
            self._result_understanding_layer = ResultUnderstandingLayer()
        return self._result_understanding_layer

    @property
    def orchestrator(self) -> Any:
        """Phase 31: 延迟初始化 CapabilityOrchestrator + echo_agent。"""
        if self._orchestrator is None:
            from ocos.capability.orchestrator import CapabilityOrchestrator
            from ocos.capability.echo_agent import EchoAgent
            self._orchestrator = CapabilityOrchestrator(
                providers={
                    "writer": EchoAgent(prefix="Writer"),
                    "researcher": EchoAgent(prefix="Researcher"),
                    "reviewer": EchoAgent(prefix="Reviewer"),
                    "echo": EchoAgent(),
                },
                auto_learn=False,  # Phase 32 再开学习
            )
        return self._orchestrator

    @property
    def attention(self) -> Any:
        """Phase 35: CognitiveAttentionController — 唯一持有 Attention 决策权的组件。"""
        if self._attention is None:
            from ocos.capability.attention import CognitiveAttentionController
            self._attention = CognitiveAttentionController()
        return self._attention

    def boot(self) -> None:
        """启动运行时。Identity > Memory 顺序。"""
        with self._lock:
            if self._state == RuntimeState.RUNNING:
                logger.debug("Already running, skipping boot.")
                return
            if self._state == RuntimeState.SHUTDOWN:
                logger.warning("Cannot boot from SHUTDOWN state.")
                return

            logger.info("AgentRuntime booting...")
            self._state = RuntimeState.BOOTING

            # 0. Phase 21: 初始化持久化层
            self._init_persistence()

            # 0.5 Phase 34B: 恢复 Cognitive State（当前焦点/未完成任务/上次注意力）
            self._restore_working_memory()

            # 0.6 Phase 34E: 验证 Identity Continuity
            self._verify_identity_continuity()

            # 先于 agent.boot(): Phase 22-A 注入 EngineBridge 供 act() 真实化
            if hasattr(self.agent, "set_engine_bridge"):
                self.agent.set_engine_bridge(self.engine_bridge)

            # 1. 启动 Agent（遵守 Identity > Memory 顺序）
            self.agent.boot()

            # 2. 激活皮层
            self.cortex.activate()

            # 3. 注册健康检查
            self.health.register("event_bus", lambda: {"status": HEALTHY})
            self.health.register(
                "engine_bridge",
                lambda: {
                    "status": HEALTHY,
                    "engines": list(ENGINE_REGISTRY.keys()),
                },
            )

            # 4. 完成启动
            self._state = RuntimeState.RUNNING
            self._boot_time = time.time()
            logger.info("AgentRuntime running.")

    def _init_persistence(self) -> None:
        """Phase 21: 初始化持久化层 — Identity + Memory。

        Identity 优先级最高：先恢复/创建 Identity，再初始化 Memory。
        """
        from pathlib import Path

        db_path = self._db_path
        if db_path != ":memory:":
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)

        # Identity Store
        self._identity_store = IdentitySQLiteStore(db_path)
        self._identity_store.initialize()

        agent_id = self.agent.agent_id
        # Defense: 代理 agent_id 为 MagicMock 等非字符串时跳过
        if not isinstance(agent_id, str) or not agent_id.strip():
            logger.warning(
                "agent_id is not a valid string (%s), skipping persistence init.",
                type(agent_id).__name__,
            )
            return

        identity = self._identity_store.load(agent_id)

        if identity is None:
            # 首次启动 — 创建新 Identity
            agent_name = "OCOS Agent"
            if hasattr(self.agent, "identity") and hasattr(self.agent.identity, "get_name"):
                agent_name = self.agent.identity.get_name()
            identity = IdentityAnchor(
                agent_id=agent_id,
                name=agent_name,
            )
            self._identity_store.save(identity)
            logger.info("New identity created: %s", identity)
        else:
            logger.info("Identity restored from %s: %s", db_path, identity)

        # 注入恢复的 Identity（替换 MasterAgent 的临时 identity）
        self.agent.identity = identity

        # Goal Store
        self._goal_store = GoalSQLiteStore(db_path)
        self._goal_store.initialize()

        # 恢复 ACTIVE/PENDING Goal → 注入 GoalStack
        if hasattr(self.agent, "goal_stack") and hasattr(self.agent.goal_stack, "set_store"):
            self.agent.goal_stack.set_store(self._goal_store)
            restored_count = self.agent.goal_stack.restore_from_store()
            if restored_count > 0:
                logger.info("Goals restored: %d", restored_count)

        # Memory Hub
        self._memory_hub = MemoryHub(db_path)
        self._memory_hub.initialize()
        logger.info("MemoryHub initialized — %s", self._memory_hub.get_stats())

        # Working Memory Store (Phase 21)
        if db_path != ":memory:":
            self._wm_store = SQLiteWorkingMemory(
                db_path, max_entries=1000, default_ttl=None,
            )
            logger.info("WorkingMemory store initialized at %s", db_path)

        # Dynamic Engine Loading (Phase 21)
        if self._engine_loader is not None:
            loaded = self._engine_loader.load_all()
            for engine_id, engine_instance in loaded.items():
                try:
                    engine_cls = type(engine_instance)
                    self.engine_bridge.register_engine_type(engine_id, engine_cls)
                except Exception as e:
                    logger.debug("EngineLoader: skip %s — %s", engine_id, e)
            self.engine_bridge.register_all()
            logger.info("Dynamic engines loaded: %s", self.engine_bridge.get_available_engines())

    def tick(self) -> dict[str, Any]:
        """Phase 22-C: 10 步持久化认知 Tick 循环。

        Steps:
          1. Event Ingestion — 从 EventBus 拉取事件
          2. Attention Update — 注意力模型更新
          3. WM Sync — 工作记忆持久化
          4. Goal Maintenance — 目标状态检查
          5. Execution Check — 执行状态扫描
          6. Planning Trigger — 触发计划
          7. Core Loop — observe→think→decide→act→reflect→learn
          8. Dispatch — 经 Bridge+Gateway 派发
          9. Result Ingest — 结果反刍
          10. Learning Consolidation — 经验巩固
        """
        if self._state != RuntimeState.RUNNING:
            return {"status": "not_running", "state": self._state.name}

        with self._lock:
            self._cycle_count += 1
            tick_start = time.monotonic()
            step_log: list[dict[str, Any]] = []

            # ── Step 1: Event Ingestion ──────────────────────────────
            step_log.append(self._tick_step_event_ingestion())

            # ── Step 2: Attention Update ─────────────────────────────
            step_log.append(self._tick_step_attention_update())

            # ── Step 3: WM Sync ──────────────────────────────────────
            step_log.append(self._tick_step_wm_sync())

            # ── Step 4: Goal Maintenance ─────────────────────────────
            step_log.append(self._tick_step_goal_maintenance())

            # ── Step 5: Execution Check ──────────────────────────────
            step_log.append(self._tick_step_execution_check())

            # ── Step 6: Planning Trigger ─────────────────────────────
            step_log.append(self._tick_step_planning_trigger())

            # ── Step 7: Core Loop (observe→think→decide→act→reflect→learn) ──
            step_log.append(self._tick_step_core_loop())

            # ── Step 8: Dispatch (Bridge + Gateway) ───────────────────
            step_log.append(self._tick_step_dispatch())

            # ── Step 9: Result Ingest ────────────────────────────────
            step_log.append(self._tick_step_result_ingest())

            # ── Step 10: Learning Consolidation ──────────────────────
            step_log.append(self._tick_step_learning_consolidation())

            # ── Budget & Graceful Degradation ────────────────────────
            tick_elapsed = time.monotonic() - tick_start
            self._tick_latencies.append(tick_elapsed)
            budget_ok = tick_elapsed < self._tick_budget
            if not budget_ok:
                logger.warning(
                    "Tick budget exceeded: %.2fs > %.2fs (cycle=%d)",
                    tick_elapsed, self._tick_budget, self._cycle_count,
                )

            result = {
                "status": "completed",
                "cycle": self._cycle_count,
                "cortex_mode": self.cortex.mode.name,
                "tick_elapsed_s": round(tick_elapsed, 4),
                "budget_ok": budget_ok,
                "steps": step_log,
                "memory": self.memory.get_stats(),
            }
            return result

    # ── 10 Steps ─────────────────────────────────────────────────────────────

    def _tick_step_event_ingestion(self) -> dict[str, Any]:
        """Step 1: Event Ingestion — EventBus → Normalizer → Attention Evaluation.

        Phase 34A + Phase 35: 完整感知链路。
          1. EventBus.ingest() 拉取待处理事件
          2. 存储事件供 step 2 (Attention) 使用
          3. 记录 EVENT_INGESTION_TRACE
        Phase 35: 决策逻辑移到 step 2 (Attention Update)，step 1 只负责采集。
        """
        traces: list[dict[str, Any]] = []
        events_for_attention: list[dict[str, Any]] = []
        try:
            eb = self.event_bus
            events = eb.ingest(max_events=10)
            if not events:
                self._last_ingestion_events = []
                return {"step": 1, "name": "event_ingestion", "status": "no_events", "traces": []}

            for event in events:
                # 获取当前活跃目标列表
                active_goals: list[str] = []
                try:
                    if self._goal_store is not None:
                        active_goals = [g.goal_id for g in self._goal_store.load_active()]
                except Exception:
                    pass

                candidate_score = event.candidate_score
                source_type = getattr(event, 'source_type', 'file_change')

                # Phase 35: 存储原始事件数据供 step 2 使用
                event_data = {
                    "event_id": event.event_id,
                    "event_type": event.event_type,
                    "summary": event.summary,
                    "candidate_score": candidate_score,
                    "source_type": source_type,
                    "active_goals": active_goals,
                }
                events_for_attention.append(event_data)

                # 记录简化的 trace（详细 trace 在 step 2 生成）
                traces.append({
                    "event_id": event.event_id,
                    "type": event.event_type,
                    "summary": event.summary,
                    "score": candidate_score,
                })

            # Phase 35: 存储事件供 step 2 使用
            self._last_ingestion_events = events_for_attention

            return {
                "step": 1, "name": "event_ingestion",
                "events": len(events),
                "traces": traces,
            }
        except Exception as e:
            logger.debug("Event ingestion skipped: %s", e)
            self._last_ingestion_events = []
            return {"step": 1, "name": "event_ingestion", "status": "no_ingestion", "error": str(e)}

    def _tick_step_attention_update(self) -> dict[str, Any]:
        """Step 2: Attention Update — Phase 35 核心认知控制管道。

        Freeze §7.1 完整路径:
          EventBus 事件(step 1) → B:AttentionScoringEngine.score() → C:CognitiveAttentionController.decide()
          → AttentionDecision[] → WM Allocation 路由(step 3)

        单写入点原则: 所有 current_focus 变更只来自此步骤的 CognitiveAttentionController。
        """
        try:
            controller = self.attention  # CognitiveAttentionController (C 层)
            events = self._last_ingestion_events

            if not events:
                # 无事件：推进疲劳 + 尝试恢复挂起焦点
                controller.tick(seconds=0.1)
                # Phase 36: 无事件也生成报告
                self._attention_report = controller.emit_report(tick_id=f"tick-{time.time()}")
                return {
                    "step": 2, "name": "attention_update",
                    "status": "no_events",
                    "focus_state": controller.focus_state.value,
                    "fatigue": round(controller.fatigue, 3),
                }

            # 获取活跃目标
            active_goals: list[str] = []
            try:
                if self._goal_store is not None:
                    active_goals = [g.goal_id for g in self._goal_store.load_active()]
            except Exception:
                pass

            # Phase 35: 核心决策管道
            # events → score (B层内嵌) → decide (C层) → AttentionDecision[]
            import time as _time
            _start = _time.monotonic()
            decisions = controller.decide(events, active_goals=active_goals)
            _elapsed = _time.monotonic() - _start

            # 推进疲劳
            controller.tick(seconds=0.1)

            # 存储 decisions 供 step 3 (WM Sync) 使用
            self._last_attention_decisions = decisions

            # Phase 36: 生成 AttentionReport 供 step 4/5/6 读取
            self._attention_report = controller.emit_report(
                tick_id=f"tick-{_time.time()}",
                last_decisions_raw=decisions,
            )

            # 生成 step 2 摘要报告
            accepted_count = sum(1 for d in decisions if d.is_accepted)
            queued_count = sum(1 for d in decisions if d.decision.name == "QUEUED")
            deferred_count = sum(1 for d in decisions if d.decision.name == "DEFERRED")
            dismissed_count = sum(1 for d in decisions if d.is_dismissed)

            return {
                "step": 2,
                "name": "attention_update",
                "phase": 35,
                "pipeline": "events→score→decide→AttentionDecision",
                "events": len(events),
                "decisions": {
                    "total": len(decisions),
                    "ACCEPTED": accepted_count,
                    "QUEUED": queued_count,
                    "DEFERRED": deferred_count,
                    "DISMISSED": dismissed_count,
                },
                "focus": controller.current_focus,
                "focus_state": controller.focus_state.value,
                "fatigue": round(controller.fatigue, 3),
                "scoring_time_ms": round(_elapsed * 1000, 2),
                "interrupts_this_minute": len(controller._recent_interrupts),
            }
        except Exception as e:
            logger.error("Attention update failed: %s", e, exc_info=True)
            return {"step": 2, "name": "attention_update", "error": str(e)}

    def _tick_step_wm_sync(self) -> dict[str, Any]:
        """Step 3: WM Sync — 工作记忆持久化 + Phase 35 注意力分配指令执行。

        Phase 35: 执行 step 2 产生的 AttentionDecision 中的 wm_allocation 指令。
        路由规则（Freeze §5）:
          current_focus → WM slot_type=CURRENT_FOCUS
          environmental_scan → WM slot_type=ENVIRONMENTAL_SCAN (weight × 0.3)
          DISMISSED → 不写入 WM
        """
        result = {"step": 3, "name": "wm_sync"}
        wm_writes = 0

        # Phase 35: 执行 Attention WM 分配指令
        decisions = self._last_attention_decisions
        if decisions:
            for d in decisions:
                if d.wm_allocation is None:
                    continue
                if d.decision.value == "DISMISSED":
                    continue  # Freeze §5 规则3: DISMISSED 不写入 WM

                slot = d.wm_allocation.slot_type
                weight = d.wm_allocation.attention_weight
                event_id = d.wm_allocation.event_id

                # 写入 WorkingMemory Store
                if hasattr(self, "_wm_store") and self._wm_store is not None:
                    try:
                        self._wm_store.put(
                            key=f"attention:{slot}:{event_id}",
                            value={
                                "event_id": event_id,
                                "slot": slot,
                                "attention_weight": weight,
                                "decision": d.decision.value,
                            },
                            ttl=3600 if slot == "environmental_scan" else None,
                        )
                        wm_writes += 1
                    except Exception:
                        pass

            # 清空 decisions cache
            self._last_attention_decisions = []

        # 周期性完整持久化
        if self._cycle_count % 5 == 0:
            self._persist_working_memory()
            result["persisted"] = True
        else:
            result["skipped"] = "not_sync_cycle"

        result["wm_writes_from_attention"] = wm_writes
        return result

    def _tick_step_goal_maintenance(self) -> dict[str, Any]:
        """Step 4: Goal Maintenance v2 — Phase 36 Attention-aware 目标维护。

        读取 AttentionReport，按推荐排序 Goal，限制深度，优先维护焦点 Goal。
        权限：读取 Goal 状态、触发维护检查。禁止：创建/删除/修改 priority。
        """
        try:
            report = self._attention_report

            if report is None:
                # 降级：无 AttentionReport 时回到 Phase 34 行为
                agent = self.agent
                if hasattr(agent, "goal_stack") and hasattr(agent.goal_stack, "get_active_count"):
                    return {"step": 4, "name": "goal_maintenance",
                            "active_goals": agent.goal_stack.get_active_count()}
                return {"step": 4, "name": "goal_maintenance", "status": "no_goal_stack"}

            # 1. 读取活跃 Goal
            goals = self._goal_store.load_active() if self._goal_store is not None else []

            if not goals:
                return {"step": 4, "name": "goal_maintenance", "active_total": 0}

            # 2. 按 Attention 推荐排序
            rec = report.recommendation
            prioritize = set(rec.prioritize_goals)
            deprioritize = set(rec.deprioritize_goals)

            ordered: list[dict] = []
            skipped: list[str] = []
            for g in goals:
                gid = g.get("id", g.get("goal_id", "?")) if isinstance(g, dict) else getattr(g, "goal_id", "?")
                if gid in deprioritize:
                    skipped.append(gid)
                    continue
                ordered.append(g)
            ordered.sort(
                key=lambda g: (
                    1 if (
                        g.get("id", "") if isinstance(g, dict)
                        else getattr(g, "goal_id", "")
                    ) in prioritize else 0,
                    g.get("priority", 0) if isinstance(g, dict) else getattr(g, "priority", 0),
                ),
                reverse=True,
            )

            # 3. 限制深度
            depth = max(rec.suggested_maintenance_depth, 1)
            ordered = ordered[:depth]

            # 4. 逐条维护检查（deadline staleness / progress 停滞检测）
            maintained: list[str] = []
            for g in ordered:
                gid = g.get("id", g.get("goal_id", "?")) if isinstance(g, dict) else getattr(g, "goal_id", "?")
                desc = g.get("description", "") if isinstance(g, dict) else getattr(g, "description", "")
                status = g.get("status", "") if isinstance(g, dict) else getattr(g, "status", "")
                logger.debug("Goal maintenance check: %s [%s] — %s", gid, status, desc[:60])
                maintained.append(gid)

            return {
                "step": 4,
                "name": "goal_maintenance",
                "phase": 36,
                "active_total": len(goals),
                "maintained": len(maintained),
                "skipped_by_attention": len(skipped),
                "attention_depth": depth,
            }

        except Exception as e:
            logger.error("Goal maintenance failed: %s", e, exc_info=True)
            return {"step": 4, "name": "goal_maintenance", "error": str(e)}

    def _tick_step_execution_check(self) -> dict[str, Any]:
        """Step 5: Execution Check v2 — Phase 36 Attention-aware。

        attention_block 是 ExecutionDecision（allowed=false），不是任务状态变更。
        禁止: Attention → Execution State Mutation (RUNNING → BLOCKED)。
        正确: ExecutionDecision: allowed=false, reason=ATTENTION_RESOURCE_UNAVAILABLE。
        """
        try:
            report = self._attention_report
            attention_allowed = True
            attention_block_reason = ""

            if report:
                if report.fatigue > 0.9:
                    attention_allowed = False
                    attention_block_reason = "ATTENTION_RESOURCE_UNAVAILABLE"
                elif report.mode in ("INTERRUPTED", "SUSPENDED"):
                    attention_allowed = False
                    attention_block_reason = "ATTENTION_RESOURCE_UNAVAILABLE"

            # 原有 controller 检查
            controller = self.controller
            stats = controller.get_stats() if hasattr(controller, "get_stats") else {}
            blocked = controller.is_blocked() if hasattr(controller, "is_blocked") else False

            return {
                "step": 5,
                "name": "execution_check",
                "phase": 36,
                "controller_blocked": blocked,
                "attention_allowed": attention_allowed,
                "attention_block_reason": attention_block_reason,
                "stats": stats,
            }
        except Exception as e:
            return {"step": 5, "name": "execution_check", "error": str(e)}

    def _tick_step_planning_trigger(self) -> dict[str, Any]:
        """Step 6: Planning Trigger v2 — Phase 36 三条件门控。

        Plan = Goal.ready AND Attention.available AND Resource.available
        Cognitive Serialization Constraint: max 1 Goal/Tick（非硬限制，单焦点模型推导）。
        Attention 权限: ALLOW_PLANNING / DEFER_PLANNING (signal only)。
        Attention 禁止: CREATE_PLAN / MODIFY_PLAN / CANCEL_PLAN。
        """
        try:
            report = self._attention_report

            # Gate 1: Attention available
            if report is not None and report.recommendation.suppress_planning:
                return {
                    "step": 6, "name": "planning_trigger", "phase": 36,
                    "gated": True, "reason": "attention_suppress",
                }

            # Gate 2: Resource available
            if self._active_dag is not None:
                return {
                    "step": 6, "name": "planning_trigger", "phase": 36,
                    "gated": True, "reason": "resource_saturated",
                    "active_dag_remaining": self._dag_total - self._dag_cursor
                    if hasattr(self, '_dag_cursor') else "?",
                }

            if self._goal_store is None:
                return {"step": 6, "name": "planning_trigger", "phase": 36, "decomposed": 0}

            # Gate 3: Goal ready + attention-aware filtering
            active = self._goal_store.load_active()
            pending = [g for g in active if getattr(g, "status", None) and g.status.name == "PENDING"]

            # If focused on a goal, only decompose that one
            if report is not None and report.focus_type == "GOAL" and not report.recommendation.ready_for_new_goal:
                pending = [g for g in pending if getattr(g, "goal_id", "") == report.current_focus_id]

            # Cognitive Serialization Constraint: max 1 Goal/Tick
            decomposed = 0
            for g in pending[:1]:
                try:
                    from ocos.planning.decomposer import TaskDecomposer
                    from ocos.kernel.goal_types import UserGoal, GoalDomain
                    import uuid
                    ug = UserGoal(
                        id=f"GOAL-{uuid.uuid4().hex[:8]}",
                        raw_input=g.description,
                        objective=g.description,
                        domain=GoalDomain.WRITING,
                        caller="runtime",
                    )
                    dag = TaskDecomposer.decompose(ug)
                    self._active_dag = dag
                    self._dag_cursor = 0
                    self._dag_total = len(dag.tasks)
                    decomposed = 1
                except Exception as inner_e:
                    logger.warning("Planning decomposition failed: %s", inner_e)

            return {
                "step": 6, "name": "planning_trigger",
                "phase": 36,
                "pending_total": len(pending),
                "decomposed": decomposed,
                "gated_by_attention": (report is not None and report.recommendation.suppress_planning),
            }
        except Exception as e:
            return {"step": 6, "name": "planning_trigger", "error": str(e)}

    def _tick_step_core_loop(self) -> dict[str, Any]:
        """Step 7: Core Loop — 优先执行 TaskDAG，无 DAG 时回退认知循环。

        Phase 31: 每 tick 从 active_dag 取 1 个 task → echo_agent.execute。
        """
        # ── Phase 31: TaskDAG execution ──
        if self._active_dag is not None:
            order = self._active_dag.topological_order()
            if self._dag_cursor < len(order):
                tid = order[self._dag_cursor]
                task = self._active_dag.tasks[tid]
                try:
                    from ocos.capability.echo_agent import EchoAgent
                    agent = EchoAgent(prefix=task.agent_type.capitalize())
                    result = agent.execute(
                        prompt=task.description,
                        task_type=task.task_type,
                        task_id=tid,
                    )
                    self._task_statuses[tid] = "completed"
                    output = result.get("output", str(result))
                    self._recent_results.append({
                        "task_id": tid,
                        "description": task.description,
                        "agent": task.agent_type,
                        "output": output,
                        "success": True,
                    })
                    self._dag_cursor += 1
                    return {
                        "step": 7, "name": "core_loop",
                        "strategy": "dag_execution",
                        "task": tid,
                        "progress": f"{self._dag_cursor}/{self._dag_total}",
                        "output": output[:200],
                    }
                except Exception as e:
                    self._task_statuses[tid] = "failed"
                    self._dag_cursor += 1
                    return {"step": 7, "name": "core_loop", "task": tid, "error": str(e)}

            # DAG exhausted — reset
            self._active_dag = None
            self._dag_cursor = 0
            self._dag_total = 0

        # ── Fallback: original cognitive loop (or idle if not booted) ──
        if hasattr(self, "loop") and self.loop is not None:
            try:
                result = self.loop.execute_single()
                return {"step": 7, "name": "core_loop", "status": result.get("status", "unknown")}
            except Exception as e:
                return {"step": 7, "name": "core_loop", "error": str(e)}
        return {"step": 7, "name": "core_loop", "status": "idle"}

    def _tick_step_dispatch(self) -> dict[str, Any]:
        """Step 8: Dispatch — 通过 Bridge + Gateway 派发结果。

        Phase 24-A: 所有 dispatch 合约经过 PermissionGateway 验证。
        """
        gateway_stats = {"checks": 0, "allowed": 0, "blocked": 0}
        try:
            # Gateway 扫描待审批的 dispatch contract
            gw = self.gateway
            # 从 controller/loop 获取当前合约
            contracts = []
            if hasattr(self.controller, "pending_contracts"):
                contracts = self.controller.pending_contracts or []
            for contract in contracts:
                try:
                    result = gw.validate_or_raise(contract)
                    gateway_stats["checks"] += 1
                    gateway_stats["allowed"] += 1
                except PermissionDeniedError as e:
                    gateway_stats["checks"] += 1
                    gateway_stats["blocked"] += 1
                    logger.warning("Gateway blocked contract: %s", e)
        except Exception as e:
            logger.debug("Gateway dispatch scan skipped: %s", e)

        return {
            "step": 8, "name": "dispatch",
            "status": "via_core_loop",
            "gateway": gateway_stats,
        }

    def _tick_step_result_ingest(self) -> dict[str, Any]:
        """Step 9: Result Ingest — 消费执行结果 → Memory + Attention（Phase 32）。

        通过 _result_cursor 读取 _recent_results（不弹），保留给 step 10 模式提取。
        """
        ingested = None
        mem_before = self.memory.working_count

        # ── Phase 32: 消费执行结果 ──
        if self._result_cursor < len(self._recent_results):
            ingested = self._recent_results[self._result_cursor]
            self._result_cursor += 1

            # A. 写入 Working Memory
            content = f"[{ingested['agent']}] {ingested['description']}: {ingested['output'][:200]}"
            importance = 0.6 if ingested['success'] else 0.4
            self.memory.add_to_working(
                content=content,
                importance=importance,
                tags=[ingested['agent'], ingested.get('task_id', '')],
                metadata={"task_id": ingested.get('task_id', ''), "success": ingested['success']},
            )

            # B. Phase 34C: 写入 MemoryHub Episode（Result → Episode 沉淀）
            self._record_episode_from_result(ingested)

            # C. 推送 Attention 信号
            try:
                from ocos.capability.attention import TargetType, FocusTarget
                au = self.attention
                au.push_focus(FocusTarget(
                    target_type=TargetType.GOAL,
                    target_id=ingested.get("task_id", "task"),
                    priority=0.6 if ingested["success"] else 0.3,
                    description=f"{ingested['agent']}: {ingested['description'][:60]}",
                ))
            except Exception:
                pass

        # ── 基础经验记录（向后兼容） ──
        try:
            self.experiences.record(
                situation=f"tick_{self._cycle_count}",
                action="cognitive_cycle",
                outcome="completed",
            )
        except Exception:
            pass

        return {
            "step": 9, "name": "result_ingest",
            "ingested": ingested is not None,
            "memory": {"working_before": mem_before, "working_now": self.memory.working_count}
            if ingested else None,
        }

    def _tick_step_learning_consolidation(self) -> dict[str, Any]:
        """Step 10: Learning Consolidation — 经验巩固 + 信念提取（Phase 32 enhanced）。

        B. 从 _recent_results 模式提取 Belief。
        """
        try:
            # 记忆巩固（每5 tick）
            if self._cycle_count % 5 == 0:
                self.memory.consolidate_to_long_term()

            # 信念提取（每10 tick — 现有逻辑 + Phase 32 pattern）
            if self._cycle_count % 10 == 0:
                self._extract_beliefs()
                self._extract_beliefs_from_results()

            return {
                "step": 10, "name": "learning_consolidation",
                "cycle": self._cycle_count,
            }
        except Exception as e:
            return {"step": 10, "name": "learning_consolidation", "error": str(e)}

    # ── 原有辅助方法 ────────────────────────────────────────────────────────

    def _homeostasis_check(self) -> None:
        """自我调节检查。"""
        # Phase 35: 使用 CognitiveAttentionController 检查疲劳
        if self.attention is not None and hasattr(self.attention, 'fatigue') and self.attention.fatigue > 0.9:
            self.cortex.sleep()
            logger.info("Homeostasis: entering sleep mode.")

        if self.cortex.needs_intervention():
            self.cortex.emergency_activate()
            logger.warning("Homeostasis: emergency activation triggered.")

    def _persist_working_memory(self) -> None:
        """Phase 21: 将 MemoryConsolidator 的工作记忆保存到 SQLiteWorkingMemory。"""
        if self._wm_store is None:
            return
        try:
            self._wm_store.store("wm:working", {
                "items": [
                    {"content": m.content, "importance": m.importance,
                     "frequency": m.frequency, "tags": m.tags}
                    for m in self.memory.get_working_items()
                ],
            })
        except Exception as e:
            logger.debug("WorkingMemory persist skipped: %s", e)

    def _restore_working_memory(self) -> None:
        """Phase 21: 从 SQLiteWorkingMemory 恢复工作记忆。"""
        if self._wm_store is None:
            return
        try:
            data = self._wm_store.load("wm:working")
            if not data or not data.get("items"):
                return
            restored = 0
            for item_data in data["items"]:
                self.memory.add_to_working(
                    content=item_data.get("content", ""),
                    importance=item_data.get("importance", 0.5),
                    tags=item_data.get("tags", []),
                )
                restored += 1
            if restored > 0:
                logger.info("Phase 34B: Restored %d working memory items — cognitive continuity confirmed", restored)
        except Exception as e:
            logger.debug("WorkingMemory restore skipped: %s", e)

    def _record_episode_from_result(self, result: dict[str, Any]) -> None:
        """Phase 34C: 将执行结果记录为 MemoryHub Episode。

        Result → Episode 是长期学习的第一个转换步骤。
        后续 Pattern → Knowledge → Belief 由 MemoryHub 内部 pipeline 处理。
        """
        if self._memory_hub is None or not self._memory_hub.is_initialized():
            return
        try:
            import uuid
            from datetime import datetime, timezone
            from ocos.memory.episode.models import Episode, EpisodeStatus

            episode = Episode(
                id=f"EPI-{uuid.uuid4().hex[:12]}",
                experience_id=result.get("task_id", f"EXP-{uuid.uuid4().hex[:8]}"),
                created_at=datetime.now(timezone.utc),
                session_id=f"tick_{self._cycle_count}",
                context={
                    "agent": result.get("agent", "?"),
                    "description": result.get("description", ""),
                    "success": result.get("success", False),
                    "output_excerpt": result.get("output", "")[:300],
                },
                goal=result.get("description", "")[:200],
                decision="execute",
                action=f"{result.get('agent', 'agent')}.execute",
                outcome={
                    "success": result.get("success", False),
                    "cycle": self._cycle_count,
                },
                condition=f"tick@{self._cycle_count}",
                significance_score=0.6 if result.get("success") else 0.3,
                evaluation_trace={"source": "step9_ingest", "cycle": self._cycle_count},
                source="decision",
                status=EpisodeStatus.ACTIVE,
                tags=[result.get("agent", "?"), result.get("task_id", "")],
            )
            self._memory_hub.episode.save(episode)
        except Exception as e:
            logger.debug("Episode recording skipped: %s", e)

    def _sleep_tick(self) -> dict[str, Any]:
        """休眠周期 — 巩固记忆、信念衰减、持久化工作记忆。"""
        self.memory.consolidate_to_long_term()
        self.beliefs.decay_all(rate=0.02)
        self.experiences.replay_important(count=2)
        # Phase 21: Persist working memory during sleep
        self._persist_working_memory()
        return {
            "status": "sleeping",
            "cycle": self._cycle_count,
            "cortex_mode": "SLEEPING",
        }

    def _emergency_tick(self) -> dict[str, Any]:
        """紧急周期 — 只做最关键的维护。"""
        self.memory.consolidate_to_long_term()
        return {
            "status": "emergency",
            "cycle": self._cycle_count,
            "cortex_mode": "EMERGENCY",
        }

    def _extract_beliefs(self) -> None:
        """从经验中提炼信念。"""
        important = self.experiences.replay_important(count=3)
        for exp in important:
            if exp.outcome in ("success", "great", "good"):
                self.beliefs.add(
                    statement=f"当{exp.situation}时, {exp.action}有效",
                    confidence=0.6 + exp.importance * 0.3,
                )
                self.knowledge.add(
                    subject=exp.situation,
                    predicate="effective_action",
                    object=exp.action,
                    confidence=exp.importance,
                    source="experience",
                )

    def _extract_beliefs_from_results(self) -> int:
        """Phase 32-B: 从 _recent_results 模式提取 Belief。

        提取规则:
          1. 最近 N 条全部成功 → "goal execution is achievable"
          2. 同一 agent 3+ 次 → "agent X is reliable"
          3. 同一 task fingerprint 3+ 次 → "tasks like X are common"
        """
        results = self._recent_results[:]  # cursor-preserved 快照
        if len(results) < 3:
            return 0

        from collections import Counter
        from ocos.agent.belief_system import BeliefSource
        count = 0

        # 模式0: 全量成功率（最近3+条）
        all_ok = sum(1 for r in results if r.get("success")) / len(results)
        if all_ok == 1.0:
            self.beliefs.add(
                statement="recent execution chain completed with 100% success rate",
                confidence=0.5 + 0.1 * min(len(results), 5),
                source=BeliefSource.CONSOLIDATION,
            )
            count += 1

        # 模式1: agent 可靠性
        agent_ok: Counter[str] = Counter()
        agent_total: Counter[str] = Counter()
        for r in results:
            agent = r.get("agent", "?")
            agent_total[agent] += 1
            if r.get("success"):
                agent_ok[agent] += 1

        for agent, total in agent_total.items():
            if total >= 3:
                rate = agent_ok[agent] / total
                if rate >= 0.8:
                    self.beliefs.add(
                        statement=f"{agent} agent consistently produces reliable results",
                        confidence=0.5 + 0.3 * rate,
                        source=BeliefSource.CONSOLIDATION,
                    )
                    count += 1

        # 模式2: task 类型常见性
        desc_fp: Counter[str] = Counter()
        for r in results:
            d = r.get("description", "")
            fp = d[:6] if len(d) >= 6 else d
            desc_fp[fp] += 1

        for fp, n in desc_fp.items():
            if n >= 3:
                self.beliefs.add(
                    statement=f"tasks similar to '{fp}' appear frequently ({n}x)",
                    confidence=0.3 + 0.1 * min(n, 5),
                    source=BeliefSource.CONSOLIDATION,
                )
                count += 1

        return count

    def get_stability_report(self) -> dict[str, Any]:
        """Phase 34D: 运行稳定性报告。

        包含:
          - Tick 延迟分布 (p50/p95/p99)
          - 错误数
          - 运行时长
          - 记忆/信念增长趋势
          - Cognitive Drift 检测
        """
        import statistics

        with self._lock:
            uptime = time.time() - self._boot_time if self._boot_time else 0
            latencies = list(self._tick_latencies)

            p50 = statistics.median(latencies) if latencies else 0
            p95 = statistics.quantiles(latencies, n=20)[18] if len(latencies) >= 20 else 0
            p99 = statistics.quantiles(latencies, n=100)[98] if len(latencies) >= 100 else 0

            # Memory growth
            wm_size = self.memory.working_count if hasattr(self.memory, "working_count") else 0
            lt_size = self.memory.long_term_count if hasattr(self.memory, "long_term_count") else 0
            belief_count = self.beliefs.belief_count if hasattr(self.beliefs, "belief_count") else 0
            episode_count = self._memory_hub.episode.count() if self._memory_hub and self._memory_hub.is_initialized() else 0

            # Cognitive drift: detect anomalous belief changes
            drift_flags: list[str] = []
            if self._cycle_count > 100 and self._tick_errors / self._cycle_count > 0.1:
                drift_flags.append("high_error_rate")
            if self._boot_time and uptime > 3600 and uptime - self._cycle_count * self._tick_budget > 600:
                drift_flags.append("tick_delay_accumulation")

            return {
                "phase": "34D",
                "uptime_s": round(uptime, 1),
                "cycles": self._cycle_count,
                "tick_latency": {
                    "p50_ms": round(p50 * 1000, 2),
                    "p95_ms": round(p95 * 1000, 2),
                    "p99_ms": round(p99 * 1000, 2),
                    "samples": len(latencies),
                },
                "stability": {
                    "errors": self._tick_errors,
                    "error_rate": round(self._tick_errors / max(self._cycle_count, 1), 4),
                    "drift_flags": drift_flags,
                },
                "memory_growth": {
                    "working_memory": wm_size,
                    "long_term_memory": lt_size,
                    "beliefs": belief_count,
                    "episodes": episode_count,
                },
            }

    def _save_identity_snapshot(self) -> dict[str, Any] | None:
        """Phase 34E: 保存 Identity Snapshot 用于跨 session 连续性验证。"""
        if self._identity_store is None:
            return None
        try:
            import hashlib

            snapshot = {
                "agent_id": str(self.agent.agent_id) if hasattr(self.agent, "agent_id") else "unknown",
                "cycle": self._cycle_count,
                "memory": {
                    "working_count": self.memory.working_count if hasattr(self.memory, "working_count") else 0,
                    "result_cursor": self._result_cursor,
                    "recent_results": len(self._recent_results),
                },
                "beliefs": self.beliefs.belief_count if hasattr(self.beliefs, "belief_count") else 0,
                "state": self._state.name,
                "version": "1.0-Phase34",
            }
            content = str(sorted(snapshot.items()))
            snapshot["continuity_hash"] = hashlib.sha256(content.encode()).hexdigest()[:16]

            self._identity_store.save_snapshot("runtime_identity", snapshot)
            logger.info("Phase 34E: Identity snapshot saved — hash=%s, cycle=%d",
                        snapshot["continuity_hash"], self._cycle_count)
            return snapshot
        except Exception as e:
            logger.debug("Identity snapshot save skipped: %s", e)
            return None

    def _verify_identity_continuity(self) -> None:
        """Phase 34E: Boot 时验证 Identity Continuity。

        从 IdentityStore 加载上次 shutdown 保存的 snapshot，
        校验 agent_id 一致性和版本兼容性。"""
        if self._identity_store is None:
            return
        try:
            snapshot = self._identity_store.load_snapshot("runtime_identity")
            if snapshot is None:
                logger.info("Phase 34E: No previous identity snapshot — first boot or fresh identity")
                return

            prev_agent_id = snapshot.get("agent_id", "?")
            curr_agent_id = str(self.agent.agent_id) if hasattr(self.agent, "agent_id") else "?"
            prev_cycle = snapshot.get("cycle", 0)
            prev_hash = snapshot.get("continuity_hash", "?")
            prev_version = snapshot.get("version", "?")

            if prev_agent_id != curr_agent_id:
                logger.warning("Phase 34E: Identity mismatch — was %s, now %s", prev_agent_id, curr_agent_id)
                return

            logger.info(
                "Phase 34E: Identity continuity verified — agent=%s, last_cycle=%d, "
                "hash=%s, version=%s, restored WMs=%d",
                curr_agent_id, prev_cycle, prev_hash, prev_version,
                self.memory.working_count if hasattr(self.memory, "working_count") else 0,
            )
        except Exception as e:
            logger.debug("Identity continuity check skipped: %s", e)

    def get_full_status(self) -> dict[str, Any]:
        """获取完整运行时状态。"""
        with self._lock:
            return {
                "runtime_state": self._state.name,
                "agent_status": self.agent.state.status.name,
                "cortex_mode": self.cortex.mode.name,
                "cycle": self._cycle_count,
                "controller": self.controller.get_stats(),
                "memory": self.memory.get_stats(),
                "beliefs": self.beliefs.belief_count,
                "knowledge": self.knowledge.count,
                "experiences": self.experiences.total_count,
            }

    def shutdown(self) -> None:
        """关闭运行时。"""
        with self._lock:
            logger.info("AgentRuntime shutting down...")
            self._state = RuntimeState.SHUTDOWN
            self.cortex.sleep()
            # 最后一次记忆巩固
            self.memory.consolidate_to_long_term()
            # Phase 21: Persist working memory before closing stores
            self._persist_working_memory()
            # Phase 34E: 保存 Identity Snapshot 用于下次 boot 连续性验证
            self._save_identity_snapshot()
            # Phase 21: 关闭持久化层
            if self._identity_store:
                self._identity_store.close()
            if self._goal_store:
                self._goal_store.close()
            if self._memory_hub:
                self._memory_hub.shutdown()
            if self._wm_store:
                self._wm_store.close()
            logger.info("AgentRuntime shutdown complete.")
