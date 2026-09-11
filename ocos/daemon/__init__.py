"""Phase 33: ResidentRuntime — 常驻模式 daemon wrapper。

用法:
  from ocos.daemon.resident_runtime import ResidentRuntime
  rt = ResidentRuntime(agent, tick_interval=5.0)
  rt.start()
  rt.submit_goal("设计秒杀系统", domain=GoalDomain.DEVELOPMENT)
  # ... daemon 在后台每 5s tick 一次，自动分解+执行+记忆回写 ...
  rt.stop()

线程模型:
  - _tick_thread: 定时触发 RuntimeKernel.tick_loop(max_ticks=1)（P1-C 循环收敛）
  - 认知循环唯一宿主 = RuntimeKernel；AgentRuntime.tick 经 kernel driver 注入
  - 目标队列: thread-safe deque，tick step 6 自动消费
  - 优雅关闭: threading.Event + 最大等待 30s
"""

from __future__ import annotations

import json
import logging
import os
import re
import threading
import time
from datetime import datetime, timezone
from collections import deque
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Optional

logger = logging.getLogger(__name__)

# OPS: SIGUSR1 → 全线程栈转储到 stderr（journal）— 挂起/卡死时的生产诊断手段，
# 无需 ptrace/root（py-spy 在受限环境不可用时仍可定位卡点）
try:
    import faulthandler
    import signal as _signal
    faulthandler.register(_signal.SIGUSR1, all_threads=True)
except (ImportError, ValueError, OSError):   # 非主线程注册等场景静默跳过
    pass


class DaemonState(Enum):
    STOPPED = auto()
    STARTING = auto()
    RUNNING = auto()
    STOPPING = auto()


@dataclass
class QueuedGoal:
    """提交到 daemon 队列的目标。"""
    description: str
    domain: str = "development"  # development / research / writing / analysis
    caller: str = "daemon"
    submitted_at: float = field(default_factory=time.time)


class ResidentRuntime:
    """常驻运行时 — 包装 AgentRuntime 为后台 daemon。

    tick_interval: 两次 tick 之间的间隔（秒），默认 5s。
    max_idle_cycles: 连续无目标 tick 数后降速（0=不降速），默认 0。
    """

    def __init__(
        self,
        agent: Any,
        db_path: str,  # GAP-P0-2: 必传 — 杜绝伪持久化（默认 :memory: 曾致巩固产物进程退出即丢）
        tick_interval: float = 5.0,
        max_cycles: int = 10_000,
        max_idle_cycles: int = 0,
        kernel: Optional[Any] = None,
        health_loop: Optional[Any] = None,  # GAP-P1-2: 周期健康体检（daemon.health_loop.HealthLoop）
        perception_pipeline: Optional[Any] = None,  # AUD-F1: 感知管线（perception.pipeline.PerceptionPipeline）
    ) -> None:
        from ocos.agent.agent_runtime import AgentRuntime
        self._runtime: AgentRuntime = AgentRuntime(
            agent=agent,
            max_cycles=max_cycles,
            db_path=db_path,
        )
        # 收敛裁决 P3（2026-09-08）: Learning/Consolidation Service — dream
        # 巩固触发编排的唯一宿主（原 daemon._run_dream_cycle 语义迁入）。
        self._consolidation = None
        try:
            from ocos.daemon.consolidation_service import LearningConsolidationService
            self._consolidation = LearningConsolidationService(db_path)
        except Exception as e:
            logger.warning("ConsolidationService unavailable: %s", e)
        # 收敛裁决 P2（2026-09-08）：LifeCycleOrchestrator 已归档
        # （ocos/_archive/agent/）——疲劳检测/主动输出本就由 tick 直接实现，
        # shutdown 语义并入 stop()（原 orchestrator.shutdown 仅转发
        # agent.shutdown()）。见 docs/COGNITIVE_RUNTIME_CONVERGENCE_DECISION_v1.0.md
        # Phase E: 自我演化监控 — 定期检查 SelfModel 是否需要演化。
        # 装配期只置空：memory hub 在 runtime.boot() 才存在，旧装配分支
        # 在 __init__ 期取 hub（恒 None）+ `belief()` 误作方法（property）
        # → 双重失效且静默，自演化检查在生产从未启用（2026-09-07 排查
        # MotivationHub 零提案时发现，同族"装配期捕获 boot 期资源"病灶）。
        # 真实初始化移至 start() 的 boot 之后 — 见 _init_self_monitor()。
        self._self_monitor: Any = None
        self._self_monitor_eligible: bool = False
        # P1-C 循环收敛: 认知循环宿主 = RuntimeKernel（默认自建）。
        # kernel 不 import ocos.agent — AgentRuntime.tick 经 driver 注入。
        if kernel is None:
            from ocos.runtime.runtime_kernel import RuntimeKernel
            # S3.11: 固定 runtime_id（由 agent_id 派生）——旧式 checkpoint
            # 可跨重启命中；OCOS_RUNTIME_ID 环境变量优先
            kernel = RuntimeKernel(
                runtime_id=os.environ.get("OCOS_RUNTIME_ID")
                or f"daemon-{getattr(agent, 'agent_id', 'master')}")
        self._kernel: Any = kernel
        self._health_loop: Optional[Any] = health_loop  # GAP-P1-2
        self._perception_pipeline: Optional[Any] = perception_pipeline  # AUD-F1
        # Phase 4: 默认挂接最小感知链 — ProcessSensor + FileSensor
        # daemon 之前是零传感器 → pipeline.tick() 空转零事件 → Attention/WM 全空转.
        # 现在挂两个最不具侵入性的传感器: 关键进程存活 + 配置目录变化.
        # 外部显式传入 perception_pipeline 时不覆盖 (工厂装配优先级更高).
        if self._perception_pipeline is None:
            try:
                from ocos.daemon.factory import build_perception_pipeline
                from ocos.perception.process_sensor import ProcessSensor
                from ocos.perception.file_sensor import FileSensor
                from ocos.perception.sensor_types import SensorConfig, SensorModality
                import os as _os
                _sensors = [
                    ProcessSensor(
                        config=SensorConfig(
                            sensor_name="process_monitor",
                            poll_interval=15.0,
                            modalities=[SensorModality.ENV],
                        ),
                    ),
                    FileSensor(
                        config=SensorConfig(
                            sensor_name="config_watcher",
                            poll_interval=5.0,
                            modalities=[SensorModality.FILE],
                        ),
                        _watch_paths=[_os.path.expanduser("~/.ocos")],
                    ),
                ]
                self._perception_pipeline = build_perception_pipeline(
                    sensors=_sensors,
                    event_bus=None,  # start() 里会通过 attach_perception_pipeline 注入
                )
                logger.info(
                    "🧠 Phase 4: default perception pipeline wired "
                    "(ProcessSensor + FileSensor[~/.ocos])")
            except Exception as _p4e:
                logger.warning(
                    "🧠 Phase 4: default perception pipeline failed: %s", _p4e)
        # UX-1: 目标认领 — 扫 goals 表认领 CLI 创建的 PENDING 人类目标
        self._domain_goal_store: Any = None
        if db_path and db_path != ":memory:":
            try:
                from ocos.goal.store import GoalStore
                self._domain_goal_store = GoalStore(db_path=db_path)
            except Exception as e:
                logger.warning("GoalStore unavailable, goal claim disabled: %s", e)
        # UX-P2: 用户消息收件箱（ocos say → daemon 消费 → 感知事件）
        # P1-1: dream 巩固周期 — 每 dream_interval_ticks 触发一次睡眠巩固
        # （此前 dream 只挂在 LifeCycleOrchestrator 的 SLEEP 分支，daemon
        #   不经过该编排器 → 生产环境巩固管线从未运转，belief/pattern 恒 0）
        self.dream_interval_ticks: int = 200
        # P0-2/P0-3: 会话状态管理（多实例隔离 + 对话持久化）
        self._session_manager: Any = None
        if db_path and db_path != ":memory:":
            try:
                from ocos.interaction.session_state import SessionManager
                self._session_manager = SessionManager(db_path=db_path)
                if not self._session_manager.acquire_lock():
                    logger.warning("Daemon lock failed — another instance holds db_path %s", db_path)
            except Exception as e:
                logger.warning("SessionManager unavailable: %s", e)
        # PW-4.4: 目标队列背压阈值 + runtime_scheduler PriorityQueue 上电
        self.max_queue_size: int = 50
        self._priority_queue: Any = None
        try:
            from ocos.runtime_scheduler.priority_queue import PriorityQueue
            self._priority_queue = PriorityQueue()
        except Exception as e:
            logger.debug("PriorityQueue unavailable: %s", e)
        self._user_inbox: Any = None
        self._responder: Any = None
        self._last_result_rowid: int = 0    # UX-J: goal_result 增量游标
        self._result_cursor_init: bool = False
        self._result_push_lock = threading.Lock()  # 即时回调与 5-tick 兜底并发推送去重
        # UX-J2 (2026-09-10): retry 去重 — 同 goal 短时间内反复失败不刷屏
        self._recent_goal_push: dict[str, float] = {}  # goal_title_prefix → last_push_ts
        self._goal_retry_counts: dict[str, int] = {}   # goal_title_prefix → retry_count
        if db_path and db_path != ":memory:":
            try:
                from ocos.interaction.inbox import UserInbox
                self._user_inbox = UserInbox(db_path=db_path)
                # UX-J 即时推送: goal_result 落库即刻回调推送（秒级到达 TUI），
                # 5-tick 定时推送保留为兜底
                self._runtime._on_goal_result = self._push_goal_results
            except Exception as e:
                logger.warning("UserInbox unavailable, say channel disabled: %s", e)
            try:
                from ocos.interaction.converse import (ChatResponder,
                                                       make_default_tool_executor)
                # FIX-T3: 注入只读动作执行器 — 对话层可通过 USE| 行取实时数据
                self._responder = ChatResponder(
                    db_path=db_path,
                    session_manager=self._session_manager,
                    tool_executor=make_default_tool_executor(db_path),
                )
            except Exception as e:
                logger.warning("ChatResponder unavailable: %s", e)
        # L2-3: 出站多通道链路（hermes-gateway 等第二出口）— 无配置时
        # 诚实沉默；只分发结果类消息，非结果闲聊仍仅进 outbox。
        self._channel_link: Any = None
        try:
            from ocos.daemon.channel_link import OutboundChannelLink
            self._channel_link = OutboundChannelLink()
        except Exception as e:
            logger.warning("OutboundChannelLink unavailable: %s", e)
        # P5.2 (AGI 计划): Phase 53 主动交互唤醒 — 沉睡器官生产接线。
        # NeedMonitor→AttentionTrigger→Validator→Scheduler 全链由
        # ActiveInteractionEngine 承担；产出经 outbox 进入对话流。
        # 权限双检复用 agent 的 PermissionGuard + 行为宪法（fail-closed）。
        self._active_interaction: Any = None
        try:
            from ocos.daemon.active_interaction import ActiveInteractionEngine

            def _post_proposal(message: str) -> None:
                if self._user_inbox is not None:
                    self._user_inbox.post_outbound(message, kind="proposal")
                    logger.info("Active interaction proposal posted to outbox")
                else:
                    logger.info("[active-interaction] %s", message)
                self._dispatch_result(message)   # L2-3: 提议类附加外发

            self._active_interaction = ActiveInteractionEngine(
                goal_store=self._domain_goal_store,
                output_callback=_post_proposal,
                permission_guard=getattr(agent, "_permission_guard", None),
                constitution=getattr(agent, "_constitution", None),
                db_path=db_path,   # L2-2: 参与度信号数据源
            )
        except Exception as e:
            logger.warning("ActiveInteraction unavailable (Phase 53 passive): %s", e)
        # L3 (升级方案 v1.0): MotivationHub — 自主性涌现（目标自生成）。
        # 信号聚合（lesson/belief 边界/goal_result）→ 评分 → 提案；
        # LEVEL>=1 才提案，低风险 LEVEL>=2 直接进 goals 表，其余待批。
        self._motivation: Any = None
        self._autonomous_inflight: deque = deque()   # 在途自主目标（FIFO 近似配对）
        try:
            from ocos.daemon.motivation import MotivationHub

            def _notify_motivation(message: str) -> None:
                if self._user_inbox is not None:
                    self._user_inbox.post_outbound(message, kind="proposal")
                else:
                    logger.info("[motivation] %s", message)
                self._dispatch_result(message)

            # 根因修复（2026-09-07 生产零提案排查）：LEVEL1 提案走待批通道，
            # 此前 pending_store 未接线 → _propose 走"无落地通道"静默 return，
            # 生产 4 候选全过阈值仍 0 提案。同库 PendingStore 与 bridge 审批侧
            # 共享 pending_actions 表。belief_store 传惰性提供者（memory hub
            # 在 runtime.boot() 才初始化，构造时为 None）——boot 后每次 scan
            # 解析为持久 BeliefStore（有 query_by_confidence）。原先传内存
            # BeliefSystem（query(statement, threshold) 签名不匹配），
            # PROBE 通道 TypeError 被 collect_candidates 吞掉。
            from ocos.execution.pending import PendingStore

            def _belief_provider():
                hub = self.memory_hub
                try:
                    return hub.belief if hub else None   # belief 是 property
                except RuntimeError:        # O-8: hub shutdown 后诚实沉默
                    return None

            self._motivation = MotivationHub(
                db_path=db_path,
                goal_store=self._domain_goal_store,
                pending_store=PendingStore(db_path=db_path),
                belief_store=_belief_provider,
                notify_fn=_notify_motivation,
            )
        except Exception as e:
            logger.warning("MotivationHub unavailable (L3 passive): %s", e)
        # V3 感知-反应（2026-09-07 感知层上电）: StimulusScanner +
        # EventBus — 真实环境刺激（磁盘/内存/失败聚集/目标卡死）
        # → 感知事件 → 低风险 PROBE（与动机候选同通道落地）。
        self._stimulus: Any = None
        self._event_bus: Any = None
        try:
            from ocos.perception.stimulus_scanner import StimulusScanner
            from ocos.perception_bus import EventBus

            self._stimulus = StimulusScanner(db_path=db_path)
            self._event_bus = EventBus()
            logger.info(
                "StimulusScanner initialized — perception wired (V3)")
        except Exception as e:
            logger.warning("StimulusScanner unavailable (V3 passive): %s", e)
        # L4-2 (升级方案 v1.0): 自我模型 — boot 加载实测画像
        # （"我是谁"：能力实测/性格参数/当前专注），每 N tick 校准。
        self._self_model: Any = None
        self._self_model_caps: list[str] = []
        self._self_model_ticks = max(
            1, int(os.environ.get("OCOS_SELF_MODEL_TICKS", "50")))
        try:
            from ocos.self.agent_self_model import AgentSelfModel
            self._self_model = AgentSelfModel(db_path)
            snap = self._self_model.load()
            if snap:
                logger.info("SelfModel boot: v%s hash=%s",
                            snap["version"], snap["content_hash"][:12])
            else:
                logger.info("SelfModel boot: 未校准（首次运行属正常）")
        except Exception as e:
            logger.warning("SelfModel unavailable (L4-2 passive): %s", e)
        try:
            from ocos.capability_reality.adapter_discovery import AdapterDiscovery
            registry, _ = AdapterDiscovery().run()
            self._self_model_caps = [c.descriptor.name
                                     for c in registry.list_all()]
        except Exception:
            pass  # 能力名缺省 → 校准只统计 episode 实测（诚实降级）
        self._tick_interval = tick_interval
        self._max_idle_cycles = max_idle_cycles
        self._state: DaemonState = DaemonState.STOPPED
        self._hb_ticks: int = 0
        self._stop_event = threading.Event()
        self._tick_thread: Optional[threading.Thread] = None
        self._lock = threading.RLock()
        # Phase 33: 目标队列
        self._goal_queue: deque[QueuedGoal] = deque()
        self._goal_submitted: int = 0
        self._goal_processed: int = 0
        self._idle_ticks: int = 0
        # L0-3: 自主行为总闸 — 启动读取，tick 期检测切换（即时生效+审计）
        from ocos.execution.autonomy import get_autonomy_level
        self._db_path = db_path  # dream/审计等共用（原引用为隐式依赖）
        self._autonomy_level: int = get_autonomy_level()
        # L0-5: STOP 神经 — SIGUSR2 软制动（完成当前 tick 后挂起自主活动，
        # 保留对话响应与心跳；ocos stop --soft 触发 / 再次触发恢复）
        self._braked: bool = False

    # ── Public API ────────────────────────────────────────────────────────────

    @property
    def state(self) -> DaemonState:
        return self._state

    @property
    def cycle_count(self) -> int:
        """当前 tick 周期数（与 runtime 同步）。"""
        return self._runtime._cycle_count

    @property
    def memory_hub(self) -> Any:
        """AUD-F1: 暴露 runtime 的 MemoryHub（唯一 store 源），供 run.py
        装配知识平面 SemanticStore 镜像等 — 避免外部窥探 _runtime 私有属性。"""
        return getattr(self._runtime, "_memory_hub", None)

    @property
    def session_manager(self) -> Any:
        """P0-2/P0-3: 暴露会话管理器（对话持久化 + 多实例隔离）."""
        return self._session_manager

    def attach_decision_bridge(self, bridge: Any) -> None:
        """UX-F1: 决策执行铰链挂到内部 AgentRuntime（关键修复 —
        此前 factory 挂到 MasterAgent, AgentRuntime.step7/8 永远看不到 bridge,
        DAG 任务全部走 EchoAgent 假成功）。"""
        self._runtime.attach_decision_bridge(bridge)

    def attach_health_loop(self, health_loop: Any) -> None:
        """GAP-P1-2: 绑定周期健康体检（须在 start() 前调用）。"""
        self._health_loop = health_loop
        bind = getattr(health_loop, "bind", None)
        if bind is not None:
            bind(self._runtime)

    def attach_perception_pipeline(self, pipeline: Any) -> None:
        """AUD-F1: 绑定感知管线（须在 start() 前调用）。

        每个 tick 调一次 pipeline.tick()；无传感器时为零开销零写入
        （PerceptionEngine 无 sensor 返回空事件）。
        Phase 49-B (L3-B): 同时把管线 WorldStore 注入 agent 供认知消费。

        GAP-P1-4 (2026-09-11): 自动注入 self._event_bus 到 pipeline
        （Observation → CognitiveEvent 断链修复后的生产装配闭合）。
        """
        self._perception_pipeline = pipeline

        # GAP-P1-4: 确保 PerceptionPipeline、AgentRuntime、daemon 使用同一 EventBus
        # 三实例 identity 必须一致 — 否则 StimulusScanner 和 FileSensor
        # 的事件进了不同 _pending，永远不会被认知链消费
        if self._event_bus is not None:
            try:
                if hasattr(pipeline, 'set_event_bus'):
                    pipeline.set_event_bus(self._event_bus)
                elif hasattr(pipeline, '_event_bus'):
                    pipeline._event_bus = self._event_bus
                logger.info(
                    "PerceptionPipeline ↔ EventBus wired "
                    "(same instance as daemon._event_bus)")
            except Exception as e:
                logger.warning(
                    "Failed to wire EventBus into PerceptionPipeline: %s", e)

            # GAP-P1-5 (2026-09-11): 同时注入 TickPipeline.EventIngestionStage
            # 生产消费侧 identity — TickPipeline 是生产 tick 的真实 ingest 入口
            # (手动 ingest 能通但生产不走那条路)
            try:
                from ocos.runtime.pipeline_protocol import PipelineStage
                kernel = getattr(self, '_kernel', None)
                if kernel is not None:
                    kernel_pipe = getattr(kernel, '_pipeline', None)
                    if kernel_pipe is not None:
                        ei_stage = kernel_pipe._stages.get(
                            PipelineStage.EVENT_INGESTION)
                        if ei_stage is not None:
                            ei_stage._event_bus = self._event_bus
                            logger.info(
                                "TickPipeline EventIngestionStage ↔ EventBus wired")
            except Exception as e:
                logger.debug(
                    "TickPipeline wiring skipped (not yet assembled): %s", e)

            # AgentRuntime._event_bus 也在这里注入（避免 start() 里单独一处）
            runtime = getattr(self, '_runtime', None)
            if runtime is not None:
                runtime._event_bus = self._event_bus

        # L3-B: agent.world_context() 经此消费世界状态
        world = getattr(pipeline, "world", None)
        agent_obj = getattr(
            getattr(self, "_runtime", None), "agent", None)
        if world is not None and agent_obj is not None and hasattr(
                agent_obj, "set_world_abi"):
            try:
                agent_obj.set_world_abi(world)
            except Exception:
                pass

    def _init_self_monitor(self) -> None:
        """Phase E: SelfMonitor 装配 — 必须在 runtime.boot() 之后调用。

        2026-09-07 修复：旧装配在 __init__ 期执行——memory hub 当时恒为
        None（AgentRuntime.boot() 才建）且 `belief()` 误作方法（实为
        property）→ 双重失效且 debug 级静默，自演化检查在生产从未启用。
        失败如实 warning（不再 debug 级吞掉）。
        """
        if getattr(self, "_self_monitor", None) is not None:
            return                          # 幂等（start 重入不重复装配）
        try:
            hub = self.memory_hub
            belief_store = hub.belief if hub else None   # belief 是 property
            if belief_store is None:
                logger.warning(
                    "SelfMonitor not wired — memory hub unavailable "
                    "(evolution passive)")
                return
            from ocos.self.monitor import SelfMonitor
            from ocos.self.builder import SelfModelBuilder
            from ocos.self.governor import SelfGovernor
            from ocos.self.identity_boundary import IdentityBoundary
            boundary = IdentityBoundary.create_default()
            builder = SelfModelBuilder(belief_store, boundary)
            governor = SelfGovernor(boundary)
            self._self_monitor = SelfMonitor(builder, governor, belief_store)
            # F3: seed 初始 SelfModel — 避免 "no SelfModel" 导致 evolution 检查全 deny
            try:
                initial_model = builder.build()
                self._self_monitor.seed(initial_model)
                logger.info(
                    "SelfMonitor seeded with initial SelfModel "
                    "(version=%d)", initial_model.version)
            except Exception as e:
                logger.debug("initial SelfModel build failed (non-fatal): %s", e)
            self._self_monitor_eligible = True
            logger.info("SelfMonitor initialized — evolution checks enabled")
        except Exception as e:
            logger.warning("SelfMonitor unavailable (evolution passive): %s", e)

    def start(self) -> None:
        """启动 daemon — boot AgentRuntime + RuntimeKernel，启动 tick 线程。

        P1-C: 启动时把 AgentRuntime.tick 注入 kernel 为 agent driver，
        tick 线程经 kernel.tick_loop 驱动（认知循环单一宿主）。
        """
        with self._lock:
            if self._state != DaemonState.STOPPED:
                logger.warning("Daemon already in state %s, ignoring start.", self._state.name)
                return
            self._state = DaemonState.STARTING
            self._stop_event.clear()
            self._runtime.boot()
            # B1 FIX (C1.1-C.2): ONE RUNTIME ONE EVENT BUS — 把 daemon 侧的
            # perception_bus.EventBus 注入 AgentRuntime, 避免两个独立实例
            # (daemon 持有 Instance X 供 StimulusScanner.push, AgentRuntime
            # 延迟初始化 Instance Y 供 tick Step 1 event_ingestion.ingest,
            # 两者不共享队列 → Observe 永远 no_events)
            if self._event_bus is not None:
                self._runtime._event_bus = self._event_bus
            # Phase E: SelfMonitor 装配（boot 后 memory hub 就绪才可能成功）
            self._init_self_monitor()
            # S2.2 (修复方案评审 R3): auto 模式下 ASK 类动作自动执行——
            # 启动时显著警告，生产环境建议 OCOS_APPROVAL_MODE=ask。
            # 全局默认值切换按评审版 Sprint 3 收尾统一执行。
            try:
                from ocos.execution.pending import approval_disabled
                if approval_disabled():
                    print("⚠ OCOS_APPROVAL_MODE=auto：写类/命令类动作将"
                          "自动执行（无人工审批）。生产环境建议设 "
                          "OCOS_APPROVAL_MODE=ask")
                    logger.warning(
                        "OCOS_APPROVAL_MODE=auto — ASK-class actions will "
                        "be auto-executed without human approval; "
                        "production should set OCOS_APPROVAL_MODE=ask")
            except Exception:
                logger.debug("approval mode banner skipped")
            # FIX-VAL3: 启动时回收 stale-ACTIVE 孤儿目标（上进程认领后崩溃遗留）。
            # 必须在 tick 线程启动前执行：运行期调用会错误回收本进程正在执行的目标。
            if self._domain_goal_store is not None:
                try:
                    requeued = self._domain_goal_store.requeue_stale_active()
                    if requeued:
                        logger.info("Requeued %d stale-ACTIVE goal(s) for re-execution.", requeued)
                except Exception:
                    logger.exception("Stale-ACTIVE goal requeue failed")
            # P1-C: kernel boot + agent driver 注入（每 tick 驱动 AgentRuntime.tick）。
            # restart 场景下 kernel 保持 RUNNING，start() 幂等跳过。
            if self._kernel.state.name != "RUNNING":
                self._kernel.start()
            self._kernel.attach_agent_driver(lambda tick_id: self._runtime.tick())
            # TickPipeline.EventIngestionStage 注入已在 attach_perception_pipeline 完成

            # L4-3 (升级方案 v1.0): boot 时 V5 跨重启一致性校验 —
            # 身份参数 hash（锚+宪法）+ 记忆计数断言；漂移即告警。
            try:
                from ocos.daemon.continuity import ContinuityChecker
                identity_params: dict = {}
                agent_obj = getattr(self._runtime, "agent", None)
                anchor = getattr(agent_obj, "identity", None)
                if anchor is not None and hasattr(anchor, "get_born_at"):
                    identity_params = {
                        "agent_id": anchor.get_identity_id(),
                        "born_at": anchor.get_born_at(),
                        "name": anchor.get_name(),
                    }
                self._continuity_checker = ContinuityChecker(self._db_path)
                _v5 = self._continuity_checker.boot_check(
                    identity_params=identity_params)
                if _v5.get("drift") or _v5.get("memory_loss"):
                    msg = ("⚠ V5 连续性校验: "
                           + ("；".join(_v5.get("details", []))
                              or "异常"))
                    self._notify_brake(msg)
                    self._dispatch_result(msg)
            except Exception:
                logger.exception("V5 continuity check failed")
            # 数字生命·启动自省 — 每次启动像人一样先审视自身：采集
            # 系统/GPU/网络/自身状态 + 停机推断，分析后写环境先验
            # （boot_context.json，bridge 注入目标执行）+ 异常条件转
            # 刺激提案（复用升级阶梯/预算/饱和三道闸）+ 报告推对话流。
            # 只读探查 + 失败降级，不阻断启动（网络探测最坏 ~6s）。
            try:
                from ocos.daemon.boot_awareness import run_boot_awareness
                _post = (lambda msg: self._user_inbox.post_outbound(
                    msg, kind="report")
                    if self._user_inbox is not None else None)
                _stim = (lambda stimuli: self._motivation.propose_stimulus(
                    stimuli, self._autonomy_level)
                    if self._motivation is not None else None)
                _boot = run_boot_awareness(
                    self._db_path, post_fn=_post, stimulus_fn=_stim,
                    level=self._autonomy_level)
                logger.info("Boot awareness done: %s",
                            _boot.get("summary_line", "?"))
            except Exception:
                logger.exception("Boot awareness failed")
            self._tick_thread = threading.Thread(
                target=self._tick_loop, name="ocos-daemon", daemon=True,
            )
            self._tick_thread.start()
            self._state = DaemonState.RUNNING
            from ocos.execution.autonomy import LEVEL_DESCRIPTIONS
            logger.info("ResidentRuntime daemon started (interval=%.1fs, "
                        "autonomy_level=%d [%s], braked=%s)",
                        self._tick_interval, self._autonomy_level,
                        LEVEL_DESCRIPTIONS.get(self._autonomy_level, "?"),
                        self._braked)
            # F1: 启动时检查 goal 供给 — 如果 active=0 立即注入一个 follow-up
            try:
                if self._motivation is not None:
                    self._motivation._inject_followup_if_idle()
            except Exception:
                logger.debug("startup followup inject failed", exc_info=True)

    def stop(self, timeout: float = 30.0) -> None:
        """优雅关闭 daemon — 停止 tick 线程，触发 orchestrator 安全关闭。"""
        with self._lock:
            if self._state != DaemonState.RUNNING:
                return
            self._state = DaemonState.STOPPING
        self._stop_event.set()
        if self._tick_thread:
            self._tick_thread.join(timeout=timeout)
        with self._lock:
            # 收敛裁决 P2: 安全关闭 — 原 orchestrator.shutdown 仅转发
            # agent.shutdown()，语义并入此处
            try:
                agent_obj = getattr(self._runtime, "agent", None)
                if agent_obj is not None and hasattr(agent_obj, "shutdown"):
                    agent_obj.shutdown()
            except Exception:
                logger.exception("agent shutdown during stop failed")
            self._state = DaemonState.STOPPED
            logger.info("ResidentRuntime daemon stopped. %d goals processed.", self._goal_processed)

    # ── L0-5: STOP 神经（软制动） ────────────────────────────────────────────

    def brake(self) -> None:
        """软制动 — 完成当前 tick 后挂起自主活动；对话/心跳/自检保留。"""
        with self._lock:
            if self._braked:
                return
            self._braked = True
        from ocos.execution.autonomy import audit_brake
        audit_brake(self._db_path, braked=True)
        self._notify_brake("⏸ 自主活动已制动（STOP 神经）— 对话仍响应，"
                           "发送 SIGUSR2 或 ocos stop --soft --resume 恢复")
        logger.warning("Daemon BRAKED — autonomous activity suspended "
                       "(conversation & heartbeat stay alive)")

    def resume(self) -> None:
        """解除软制动 — 自主活动恢复。"""
        with self._lock:
            if not self._braked:
                return
            self._braked = False
        from ocos.execution.autonomy import audit_brake
        audit_brake(self._db_path, braked=False)
        self._notify_brake("▶ 制动已解除 — 自主活动恢复")
        logger.info("Daemon brake released — autonomous activity resumed")

    def toggle_brake(self) -> bool:
        """SIGUSR2 处理：制动 ↔ 恢复 切换。返回切换后的 braked 状态。"""
        if self._braked:
            self.resume()
        else:
            self.brake()
        return self._braked

    def _notify_brake(self, message: str) -> None:
        """制动状态变更推送 outbox（TUI 可见）— 无 inbox 时仅日志。"""
        try:
            if self._user_inbox is not None:
                self._user_inbox.post_outbound(message, kind="proposal")
        except Exception:
            logger.debug("brake notify failed", exc_info=True)

    def _dispatch_result(self, message: str) -> None:
        """L2-3: 结果类消息附加外发到注册通道（hermes-gateway 等）。

        outbox（TUI 对话流）是主出口、永远先行且不受影响；本方法失败
        静默降级（计数在 channel_link 内部），绝不阻断主流程。
        """
        try:
            if self._channel_link is not None:
                self._channel_link.dispatch(message)
        except Exception:
            logger.debug("channel dispatch failed", exc_info=True)

    def submit_goal(self, description: str, domain: str = "development",
                    priority: int = 2) -> int:
        """提交目标到 daemon 队列（线程安全）。

        PW-4.4 背压: 队列满（max_queue_size）时诚实拒绝（返回 -1）。
        priority 对齐 runtime_scheduler.Priority（0=CRITICAL…3=LOW）。
        返回当前队列长度；被背压拒绝返回 -1。
        """
        with self._lock:
            if len(self._goal_queue) >= self.max_queue_size:
                logger.warning("Goal queue full (%d) — backpressure rejecting: %s",
                               len(self._goal_queue), description[:40])
                return -1
        goal = QueuedGoal(description=description, domain=domain)
        with self._lock:
            self._goal_queue.append(goal)
            self._goal_submitted += 1
            if self._priority_queue is not None:
                try:
                    from ocos.runtime_scheduler.scheduler_types import SchedulerTask
                    self._priority_queue.push(SchedulerTask(
                        task_id=f"GOALQ-{int(time.time() * 1000)}",
                        stage="goal_queue", priority=priority,
                        fn=lambda: description))
                except Exception as e:
                    logger.debug("priority queue push failed: %s", e)
            n = len(self._goal_queue)
            logger.info("Goal queued: %s (domain=%s, priority=%d, queue=%d)",
                        description, domain, priority, n)
            return n

    def get_status(self) -> dict[str, Any]:
        """获取 daemon 状态快照。"""
        with self._lock:
            return {
                "state": self._state.name,
                "cycle": self._runtime._cycle_count,
                "queue_size": len(self._goal_queue),
                "submitted": self._goal_submitted,
                "processed": self._goal_processed,
                "idle_ticks": self._idle_ticks,
                "braked": self._braked,
                "autonomy_level": self._autonomy_level,
                "memory": getattr(self._runtime, "memory", None),
                "beliefs": getattr(self._runtime, "beliefs", None),
            }

    # ── Internal ──────────────────────────────────────────────────────────────

    def _tick_loop(self) -> None:
        """主循环 — 经 RuntimeKernel 定时 tick（认知循环单一宿主），消费目标队列。

        Phase B: 伴生 LifeCycleOrchestrator 负责疲劳检测 + 主动输出触发，
        不替换主认知路径（kernel.tick_loop）以避免双重重跑认知循环。
        L0-3: 每 tick 检测自主级别切换（即时生效 + audit episode + outbox 通知）。
        L0-5: 制动（braked）时挂起全部自主活动 — 只保留对话响应、心跳与自检。
        自愈兜底（2026-09-08）: 循环体最外层 try/except — 子系统各自有
        精细保护，兜底捕获一切残余异常并继续循环。tick 线程死亡 = 心跳
        停更 = 全部自愈循环（自检/修复/动机/目标）同时停摆且进程仍存活
        （systemd Restart=on-failure 不触发）→ 必须在线程级兜底。
        """
        while not self._stop_event.is_set():
          try:
            # L0-3: 自主级别运行期切换检测（ocos autonomy <n> 写覆盖文件）
            try:
                from ocos.execution.autonomy import (
                    audit_level_change, get_autonomy_level)
                lvl = get_autonomy_level()
                if lvl != self._autonomy_level:
                    old = self._autonomy_level
                    self._autonomy_level = lvl
                    audit_level_change(self._db_path, old, lvl,
                                       source="runtime_override")
                    self._notify_brake(
                        f"⚖ 自主级别切换 {old} → {lvl}")
                    logger.warning("Autonomy level changed %d -> %d (audited)",
                                   old, lvl)
            except Exception:
                logger.exception("autonomy level check failed")

            # UX-F3: 心跳落盘（每 5 tick 一次, 降低写盘对 tick 时序的影响）
            self._hb_ticks += 1
            if self._hb_ticks % 5 == 0:
                try:
                    self._write_heartbeat()
                except Exception:
                    pass

            # L0-5: 软制动 — 自主活动全部挂起；对话（inbox 消费）、
            # 心跳与周期自检保留，保证"制动后 tick 停、对话仍答"。
            if not self._braked:
                # UX-J: 目标完成 → 自动回推结果到对话流
                if self._hb_ticks % 5 == 0:
                    try:
                        self._push_goal_results()
                    except Exception:
                        logger.exception("goal result push failed")

                # P1-1: 周期性 dream 巩固（Episode → Belief/Pattern/Wisdom）
                # 使用 ACT-R 产生式规则引擎动态选择要跑的模块
                if self._hb_ticks % max(1, self.dream_interval_ticks) == 0:
                    try:
                        self._run_dream_cycle()
                    except Exception:
                        logger.exception("Dream cycle failed")

                # ── 持续认知循环 (R5 continuous cognition) ────────────
                # 每 60s 做一次: 反思 → LLM验证学习 → 制定计划
                # 独立于 dream cycle (200 ticks ≈ 16min), 时刻保持大脑在工作
                # 用时间戳而非 tick 取模 — agent 执行 goal 时 tick 可能不规律
                try:
                    from datetime import datetime, timezone
                    now_ts = datetime.now(timezone.utc).timestamp()
                    last_cog = getattr(self, "_last_cognition_ts", 0)
                    diff = now_ts - last_cog
                    if diff >= 60 and self._autonomy_level >= 1 and not self._braked:
                        logger.info("🧠 Cognition Loop firing (gap=%.0fs, L%d braked=%s)", diff, self._autonomy_level, self._braked)
                        self._run_continuous_cognition()
                        self._last_cognition_ts = now_ts
                        self._cognition_fail_streak = 0  # 成功 → 清零
                    elif diff > 0:
                        logger.debug("🧠 cognition cooldown: %.0fs since last, need 60s", diff)
                except Exception as e:
                    # U1: 连续失败计数 — 3 轮以上 → 主动告警
                    streak = getattr(self, "_cognition_fail_streak", 0) + 1
                    self._cognition_fail_streak = streak
                    if streak >= 3:
                        logger.critical(
                            "🧠⚠️ Cognition Loop has failed %d consecutive times! "
                            "Last error: %s — cognition is DEGRADED",
                            streak, e,
                        )
                    else:
                        logger.warning("continuous cognition failed (%d/3): %s", streak, e, exc_info=True)

                # Phase 33: 将队列中的目标导入 runtime 的 goal_store
                self._drain_goal_queue()
                # 全自动模式: 待批队列自动通过（ask 模式零开销空转）
                try:
                    self._auto_approve_pending()
                except Exception:
                    logger.exception("auto approve pump failed")
                # B1 管道打通: evolution_artifacts PENDING→APPROVED→goals
                # 用时间戳（秒）做 60s 节流，重启后立即触发一次
                try:
                    import time as _time
                    now_ts = int(_time.time())
                    last = getattr(self, "_last_evol_pump_ts", 0)
                    if now_ts - last >= 60:
                        self._pump_evolution_artifacts()
                        self._last_evol_pump_ts = now_ts
                except Exception:
                    logger.exception("evolution artifacts pump failed")
                # U5: 每日学习摘要推送（每天一次，日期节流）
                try:
                    self._push_daily_learning_summary()
                except Exception:
                    logger.exception("daily learning summary failed")
                # UX-1: 认领 CLI 创建的持久化目标（每 tick 最多 1 个）
                self._claim_persisted_goals()

                # P1-C: 一次认知 tick = kernel.tick_loop(1)（8 空壳 stage + agent driver）
                try:
                    self._kernel.tick_loop(max_ticks=1)
                    self._idle_ticks = 0
                except Exception:
                    logger.exception("Tick failed (cycle=%d)", self._runtime._cycle_count)

                # 收敛裁决 P2: 疲劳检测 + 主动输出 — 直接对 agent 状态检查
                # （原 orchestrator 伴生层已归档，本分支从未经过它）
                if True:
                    try:
                        agent_obj = getattr(self._runtime, "agent", None)
                        attention = getattr(agent_obj, "attention", None) if agent_obj is not None else None
                        if attention is not None and hasattr(attention, "needs_sleep"):
                            if attention.needs_sleep():
                                logger.info("Fatigue detected at tick %d — triggering sleep/dream", self._hb_ticks)
                                try:
                                    self._consolidate()
                                except Exception:
                                    logger.exception("Fatigue dream failed")
                        # 定期主动输出（每 60 tick ≈ 5min @ 5s/tick）
                        # L0-3: 主动输出属自主行为 — LEVEL>=1 才允许
                        if (self._hb_ticks % 60 == 0
                                and self._autonomy_level >= 1):
                            if agent_obj is not None and hasattr(agent_obj, "maybe_proactive_output"):
                                agent_obj.maybe_proactive_output()
                        # P5.2 (AGI 计划): Phase 53 主动交互唤醒 — 空闲期基于
                        # 目标状态（停滞/依赖数据过期）产出交互提议，走 outbox。
                        # L0-3: 提案属自主行为 — LEVEL>=1 才允许（0=零自主）
                        # v2: 间隔从 60→6 tick（≈30s）——让 daemon 快速首次问候
                        if (self._active_interaction is not None
                                and self._hb_ticks % 6 == 0
                                and self._autonomy_level >= 1):
                            try:
                                self._active_interaction.scan_and_interact()
                            except Exception:
                                logger.exception("Active interaction scan failed")
                        # L3: MotivationHub 自主目标扫描（每 120 tick ≈ 10min）。
                        # 提案属自主行为 — LEVEL>=1 才允许；内部再按
                        # LEVEL>=2 + 低风险白名单决定落地通道。
                        if (self._motivation is not None
                                and self._hb_ticks % 120 == 0
                                and self._autonomy_level >= 1):
                            try:
                                stats = self._motivation.scan()
                                if stats.get("proposed"):
                                    logger.info(
                                        "MotivationHub scan: %s", stats)
                            except Exception:
                                logger.exception("Motivation scan failed")

                            # Phase 3-extra: 内生目标生成 (GoalSync Light)
                            # 之前 daemon 只有人工 goal, 零自驱。这里用最简路径:
                            # 从最近 failure_lesson 里自动生成一条探索型目标.
                            # 不调 GoalManager.sync_from_homeostasis (需要完整
                            # RegulateResult 对象 + GoalStore + 门控链),
                            # 直接走 goal 表 INSERT — 和 CLI /goals-from-chat 同路径.
                            try:
                                import sqlite3 as _sqlite3
                                import uuid as _uuid
                                from datetime import datetime, timezone as _tz
                                _db_path = getattr(self, "_db_path", None)
                                if _db_path:
                                    _conn = _sqlite3.connect(_db_path)
                                    # 近 6h failure_lesson 数量 → curiosity 压力
                                    _fl_count = _conn.execute(
                                        "SELECT COUNT(*) FROM episodes "
                                        "WHERE action='failure_lesson' "
                                        "AND created_at >= datetime('now','-6 hours')"
                                    ).fetchone()[0]
                                    # 有没有活跃的 explore goal (避免重复)
                                    _recent_explore = _conn.execute(
                                        "SELECT goal_id FROM goal "
                                        "WHERE (domain='exploration' OR "
                                        "       description LIKE '%工具%' OR "
                                        "       description LIKE '%probe%' OR "
                                        "       description LIKE '%explore%') "
                                        "AND status IN ('pending', 'running') "
                                        "ORDER BY rowid DESC LIMIT 1"
                                    ).fetchone()
                                    _conn.close()

                                    # curiosity 足够 + 没在 explore → 生成
                                    if _fl_count >= 2 and _recent_explore is None:
                                        _gid = f"GOAL-AUTO-{_uuid.uuid4().hex[:8]}"
                                        _desc = (
                                            f"[内生] 环境能力探索: 近 6h 有 {_fl_count} "
                                            f"条 failure_lesson, 先探测宿主机工具可用性 "
                                            f"(curl/python3/wget/git/node/sqlite3), "
                                            f"再选可用工具做一次真实外部任务"
                                        )
                                        try:
                                            _conn2 = _sqlite3.connect(_db_path)
                                            # 写入 goals 表 (daemon scheduler 用),
                                            # 双写 goal 表 (兼容 UX 层).
                                            # metadata 带 domain+autonomous:
                                            #   claim 路径按 metadata.domain 路由管线
                                            #   (之前 '{}' → fallback 误判成 writing)
                                            _now = datetime.now(_tz.utc).isoformat()
                                            _meta = ('{"domain": "development", '
                                                     '"autonomous": true}')
                                            _conn2.execute(
                                                "INSERT OR IGNORE INTO goals "
                                                "(id, description, status, "
                                                "origin_level, authority, "
                                                "created_at, updated_at, "
                                                "priority, metadata, level) "
                                                "VALUES (?, ?, 'PENDING', "
                                                "'SELF', 'AUTONOMOUS', "
                                                "?, ?, 3, ?, 2)",
                                                (_gid, _desc, _now, _now, _meta),
                                            )
                                            _conn2.execute(
                                                "INSERT OR IGNORE INTO goal "
                                                "(goal_id, description, status, "
                                                "domain, created_at, origin_level, "
                                                "authority, level, priority) "
                                                "VALUES (?, ?, 1, 'exploration', "
                                                "?, 'SELF', 'AUTONOMOUS', 2, 3)",
                                                (_gid, _desc, _now),
                                            )
                                            _conn2.commit()
                                            _conn2.close()
                                            logger.info(
                                                "🧠 Phase 3-extra 内生目标生成: "
                                                "goal_id=%s curiosity=%.1f",
                                                _gid, min(_fl_count / 5.0, 1.0))
                                        except Exception as _ie:
                                            logger.debug(
                                                "🧠 endogenous goal insert err: %s", _ie)
                            except Exception as _es_e:
                                logger.debug("🧠 GoalSync-light skipped: %s", _es_e)
                            # V2 行为级验收扫描（REPAIR 完成后 6h 核对
                            # 复发/先验注入 → reflection_adoption_rate）
                            try:
                                vstats = self._motivation.verify_repairs()
                                if vstats.get("checked"):
                                    logger.info("REPAIR verify: %s", vstats)
                            except Exception:
                                logger.exception("REPAIR verify failed")
                        # V3 感知-反应（每 30 tick ≈ 2.5min）: 环境刺激
                        # 扫描 → EventBus 留痕 → 低风险 PROBE 落地。
                        # LEVEL>=1 才允许（0=零自主，与提案语义一致）。
                        if (self._stimulus is not None
                                and self._hb_ticks % 30 == 0
                                and self._autonomy_level >= 1):
                            try:
                                self._perceive()
                            except Exception:
                                logger.exception("Stimulus scan failed")
                    except Exception:
                        pass

                # L4-2: 自我模型校准（每 N tick，默认 50）—
                # 实测画像随行为演进（能力成功率/性格参数/当前专注）
                if (self._self_model is not None
                        and self._hb_ticks % self._self_model_ticks == 0):
                    try:
                        self._self_model.calibrate(
                            capability_names=self._self_model_caps)
                    except Exception:
                        logger.exception("SelfModel calibrate failed")

                # Phase E: 自我演化监控 — 每 120 tick（≈10min）检查一次 SelfModel 是否需要演化
                if self._self_monitor_eligible and self._self_monitor is not None:
                    try:
                        if self._hb_ticks % 120 == 0:
                            result = self._self_monitor.run_once()
                            logger.info("Self evolution check: action=%s message=%s",
                                       result.action.value, result.message)
                    except Exception:
                        logger.debug("SelfMonitor tick failed", exc_info=True)
            elif self._hb_ticks % 60 == 0:
                logger.info("Braked — tick %d suspended (conversation alive)",
                            self._hb_ticks)

            # UX-P2: 消费用户消息（ocos say）— 对话响应在制动期间保持
            self._drain_user_inbox()

            # GAP-P1-2: 周期健康体检（HealthLoop 内部按 interval_ticks 节流）
            if self._health_loop is not None:
                try:
                    self._health_loop.tick()
                except Exception:
                    logger.exception("Health loop tick failed")

            # L2-5: 成长叙事周报（内部按 ISO 周切换节流，其余 tick 零开销）
            if not self._braked and self._hb_ticks % 100 == 0:
                try:
                    from ocos.daemon.growth_narrative import check_week_rollover
                    report = check_week_rollover(self._db_path)
                    if report is not None and self._user_inbox is not None:
                        summary = (f"[成长叙事 第{report.chapter}章"
                                   f"（{report.week_key}）] 本周完成目标 "
                                   f"{report.goals_completed} 个，沉淀经历 "
                                   f"{report.episodes_total} 段"
                                   + (f"，学到 {len(report.lessons)} 条经验"
                                      if report.lessons else ""))
                        self._user_inbox.post_outbound(summary, kind="report")
                        self._dispatch_result(summary)   # V1 主动汇报出口
                except Exception:
                    logger.exception("Growth narrative check failed")

                # 数字生命·自我连续性: 周度身份快照（周键幂等，同周首次
                # tick 落一份）。此前 identity_snapshots 仅优雅 shutdown
                # 路径写入，systemd 下 daemon 从不优雅关闭 → 表恒空。
                if self._runtime is not None:
                    try:
                        snap = self._runtime.save_weekly_identity_snapshot()
                        if snap is not None:
                            logger.info(
                                "Weekly identity snapshot: %s "
                                "(goals_completed=%s, episodes=%s)",
                                snap.get("week_key"),
                                snap.get("goals_completed_this_week"),
                                snap.get("episodes_this_week"))
                    except Exception:
                        logger.exception(
                            "Weekly identity snapshot failed")

                # §3.1: 生命体征日报告（内部按日切换节流，其余 tick 零开销）
                try:
                    from ocos.daemon.vitals_report import check_day_rollover
                    vreport = check_day_rollover(self._db_path)
                    if vreport is not None and self._user_inbox is not None:
                        summary = vreport.summary()
                        self._user_inbox.post_outbound(summary, kind="report")
                        self._dispatch_result(summary)   # V1 主动汇报出口
                except Exception:
                    logger.exception("Vitals daily report check failed")

            # AUD-F1: 感知周期（无传感器时零开销零写入）— 被动感知，
            # 制动期间保留（只记录环境，不触发行为）
            if self._perception_pipeline is not None:
                try:
                    self._perception_pipeline.tick()
                except Exception:
                    logger.exception("Perception pipeline tick failed")

            # 降速逻辑（可选）
            if self._max_idle_cycles > 0 and self._idle_ticks >= self._max_idle_cycles:
                sleep_t = self._tick_interval * 3  # idle 减速
            else:
                sleep_t = self._tick_interval

            # 分段睡眠以响应 stop
            for _t in range(int(sleep_t * 10)):
                if self._stop_event.is_set():
                    break
                time.sleep(0.1)
          except Exception:
            # 自愈兜底: 残余异常不得杀死 tick 线程（线程死亡 = 认知
            # 循环/心跳/全部自愈循环停摆且 systemd 不重启）。记录后
            # 继续下一 tick；连续异常由睡眠自然节流。
            logger.exception("Tick loop residual failure (cycle=%s)",
                             getattr(self._runtime, "_cycle_count", "?"))
            time.sleep(self._tick_interval)

    def _drain_goal_queue(self) -> int:
        """将目标队列中的 goal 导入 runtime 的 goal_store（线程安全）。

        每 tick 最多消费 1 个 goal，避免 goal 风暴压垮 runtime。
        返回导入数量。
        """
        with self._lock:
            if not self._goal_queue:
                return 0
            qg = self._goal_queue.popleft()

        self._import_goal(
            description=qg.description, domain=qg.domain, goal_id=None)
        self._goal_processed += 1
        return 1

    def _import_goal(self, description: str, domain: str,
                     goal_id: str | None, caller: str = "daemon",
                     self_origin: bool = False) -> bool:
        """构造 agent 层 Goal 并写入 runtime._goal_store（Step 6 可消费）。

        UX-1 修复: 此前构造 UserGoal 传入期望 Goal 对象的 save()
        （属性名不匹配 → AttributeError 被吞），队列目标静默丢失。
        L3: self_origin=True 时 origin=SELF（自生成目标的诚实标注）。
        """
        try:
            from ocos.kernel.goal_types import Goal, GoalDomain, GoalLevel
            domain_map = {
                "development": GoalDomain.DEVELOPMENT,
                "research": GoalDomain.RESEARCH,
                "writing": GoalDomain.WRITING,
                "analysis": GoalDomain.ANALYSIS,
            }
            from ocos.kernel.goal_types import GoalOriginLevel, GoalAuthority
            goal = Goal(
                goal_id=goal_id or f"GOAL-DAEMON-{int(time.time() * 1000)}",
                level=GoalLevel.TASK,
                description=description,
                raw_input=description,
                objective=description,
                domain=domain_map.get(domain, GoalDomain.DEVELOPMENT),
                origin_level=(GoalOriginLevel.SELF if self_origin
                              else GoalOriginLevel.HUMAN),   # UX-F4: 用户目标=人类来源
                authority=GoalAuthority.FRAMEWORK,
                caller=caller,   # UX-I: chat 目标 → Step6 单任务直执行
            )
            gs = getattr(self._runtime, "_goal_store", None)
            if gs is not None and hasattr(gs, "save"):
                gs.save(goal)
                logger.info("Goal imported into runtime: %s (%s)",
                            goal.goal_id, domain)
                return True
            logger.warning("No runtime goal_store — goal %s dropped", goal.goal_id)
            return False
        except Exception:
            logger.exception("Failed to import queued goal: %s", description)
            return False

    @staticmethod
    def _classify_goal_domain(description: str) -> str:
        """UX-fix: goals 表 metadata 无 domain 时按描述关键词粗分类.

        之前硬编码 fallback 'writing' → '探测宿主机工具可用性' 被当成
        writing 目标, daemon 开始写大纲/人物设定 (搞笑彩蛋).
        关键词顺序: writing → research → development(命令执行类).
        """
        d = description or ""
        if any(k in d for k in ("写", "大纲", "文章", "润色", "章节", "小说")):
            return "writing"
        if any(k in d for k in ("调研", "学习", "文献", "研究", "总结")):
            return "research"
        if any(k in d for k in ("探测", "探索", "工具", "curl", "API",
                                "命令", "脚本", "git", "执行", "任务")):
            return "development"
        return "development"

    @staticmethod
    def _summarize_goal_result(decision: str, outcome: str) -> str:
        """UX-J2: 把 goal_result 的长 decision 压缩成 ≤200 字的人类可读摘要.

        原始 decision 可能包含 curl 命令、shell 原始输出、重复失败行、
        Markdown 大纲等 4000+ 字符的噪声 — 用户不需要看到这些，
        他们只关心：成功了没 / 做了什么 / 结果怎么样。
        """
        # 1) 首行: 目标标题（从 decision 里所有 ✓/✗ 行提取去重的目标名）
        import re as _re
        lines = decision.strip().split("\n")
        # 收集所有 ✓/✗ 行里的目标名（去重，取第一个非 retry 的）
        goal_title = ""
        seen_titles = set()
        for ln in lines:
            stripped = ln.strip()
            if not stripped or stripped[0] not in ("✓", "✗"):
                continue
            m = _re.match(r"^[✓✗]\s*(.+?)\s*(?:→|$)", stripped)
            if m:
                title = m.group(1)[:60]
                title = _re.sub(r"\s*→\s*retry.*$", "", title).strip()
                if title not in seen_titles:
                    seen_titles.add(title)
                    if not goal_title:
                        goal_title = title
                    if "retry" not in title.lower() and "sqlite" not in title.lower():
                        goal_title = title
                        break
        if not goal_title:
            for ln in lines:
                if ln.strip():
                    goal_title = ln.strip()[:60]
                    break

        # 结果标记优先用 outcome JSON（执行器真值，而非 decision 里可能混的行）
        success_mark = "?"

        # 2) 结果状态: 从 outcome JSON 判断 + 从 decision 尾部找结论
        is_success = "unknown"
        try:
            oc = json.loads(outcome or "{}")
            is_success = "yes" if oc.get("success") else "no"
        except Exception:
            pass

        # 3) 结论行: 找 "【结论摘要】" 后的第一句有意义的话（≤60 字）
        conclusion = ""
        for i, ln in enumerate(lines):
            if "结论" in ln and "摘要" in ln:
                # 往后找 1-3 行非空内容
                for j in range(i + 1, min(i + 5, len(lines))):
                    cl = lines[j].strip().lstrip("*").strip()
                    if cl and len(cl) >= 6:
                        conclusion = _re.sub(r"\s+", " ", cl)[:80]
                        break
                break

        # 4) 简短失败原因（如果失败且有 retry）
        fail_reason = ""
        if is_success == "no":
            for ln in lines[:15]:
                if "sqlite3" in ln:
                    fail_reason = "缺 sqlite3 命令"
                    break
                if "sandbox" in ln.lower():
                    fail_reason = "被沙盒拦截"
                    break
                if "timeout" in ln.lower() or "超时" in ln:
                    fail_reason = "超时"
                    break
            if not fail_reason and "retry scheduled" in decision:
                fail_reason = "重试中"

        # 组装最终摘要 — success_mark 用 outcome 真值（执行器判定，最可信）
        final_mark = "✓" if is_success == "yes" else ("✗" if is_success == "no" else "?")
        parts = [f"{final_mark} {goal_title}"]
        if is_success == "yes":
            parts.append("✓ 成功")
        elif is_success == "no":
            parts.append(f"✗ 失败（{fail_reason or '见详情'}）")
        if conclusion and "大纲" not in conclusion and "原始输出" not in conclusion:
            parts.append(conclusion)

        result = " ".join(p for p in parts if p)
        return result[:200]

    def _push_goal_results(self) -> None:
        """UX-J: 新 goal_result episode → 出站消息（UI 自动弹出结果）.

        UX-J2 (2026-09-10):
          1) decision 摘要化 — 4000 字压缩到 ≤200 字（去掉 curl/原始输出/重复）
          2) retry 去重 — 同 goal 10 分钟内反复失败不刷屏, 只推 "retry #N"
          3) 完整 decision 仍在 DB 里保留审计, 推给用户的是摘要版

        可被两条路径并发调用（即时回调 + 5-tick 兜底），全程持锁
        防止同批 episode 重复推送。
        """
        import time as _time
        if self._user_inbox is None:
            return
        now_ts = _time.time()
        RETRY_WINDOW = 600.0   # 10 分钟内相同 goal 视为 retry
        with self._result_push_lock:
            conn = __import__("sqlite3").connect(
                self._user_inbox._db_path)  # noqa — 只读查询同库
            try:
                if not self._result_cursor_init:
                    # 首次调用: 游标定位到当前最大 rowid（历史不重播），
                    # 之后新增的 goal_result 全部推送（修掉游标 -1 永久抑制的 bug）
                    self._last_result_rowid = conn.execute(
                        "SELECT COALESCE(MAX(rowid), 0) FROM episodes "
                        "WHERE tags LIKE '%goal_result%'").fetchone()[0]
                    self._result_cursor_init = True
                    return
                rows = conn.execute(
                    "SELECT rowid, substr(decision,1,4000), created_at, outcome,"
                    " goal FROM episodes WHERE tags LIKE '%goal_result%' AND rowid > ? "
                    "ORDER BY rowid LIMIT 5",
                    (self._last_result_rowid,)).fetchall()
            finally:
                conn.close()
            for rid, decision, created, outcome, ep_goal in rows:
                # UX-J2 摘要化 + retry 去重
                summary = self._summarize_goal_result(decision, outcome)
                # 提取 goal key (目标标题前 30 字) 用于 retry 去重
                import re as _re
                key_match = _re.search(r"[✓✗]\s*(.{3,40}?)\s*(?:→|$)", summary)
                goal_key = (key_match.group(1) if key_match else summary[:30]).strip()

                last_ts = self._recent_goal_push.get(goal_key, 0)
                retry_cnt = self._goal_retry_counts.get(goal_key, 0) + 1

                if now_ts - last_ts < RETRY_WINDOW and retry_cnt > 1:
                    # 窗口内 retry — 只推简短重试计数（不刷完整摘要）
                    short_text = f"↻ retry #{retry_cnt}: {summary[:100]}"
                    self._user_inbox.post_outbound(short_text)
                else:
                    # 首次或窗口外 — 推完整摘要
                    result_text = f"目标执行完成（{created[11:19]}）：\n{summary}"
                    self._user_inbox.post_outbound(result_text)

                self._recent_goal_push[goal_key] = now_ts
                self._goal_retry_counts[goal_key] = retry_cnt

                # 清理过期条目（> 1 小时）
                stale_keys = [k for k, t in self._recent_goal_push.items()
                              if now_ts - t > 3600]
                for k in stale_keys:
                    self._recent_goal_push.pop(k, None)
                    self._goal_retry_counts.pop(k, None)

                self._dispatch_result(summary)  # L2-3: 结果类附加外发（用摘要版）
                self._last_result_rowid = rid
                # L3 防跑飞: 在途自主目标的结果 → 连续失败计数/自动降级。
                # FIFO 配对为近似（daemon 单线程串行认领），诚实标注于
                # _autonomous_inflight 定义处；outcome.success 是执行器
                # 真值，非自报告。
                # V2 行为级验收: REPAIR 目标完成 → 打点（验收扫描在
                # motivation.verify_repairs，每 120 tick）。无此打点，
                # 复盘永远只是"产出文本"——验收使其成为可观测变更。
                if self._motivation is not None:
                    m = re.search(r"复盘并验证「(.+?)」", decision)
                    if m:
                        try:
                            self._motivation.record_repair_completion(
                                m.group(1), goal_ref=decision[:60])
                        except Exception:
                            logger.debug("repair completion mark failed",
                                         exc_info=True)
                if self._autonomous_inflight:
                    self._autonomous_inflight.popleft()
                    if self._motivation is not None:
                        success = True
                        oc: dict = {}
                        try:
                            oc = json.loads(outcome or "{}")
                            success = bool(oc.get("success", True))
                        except (ValueError, TypeError):
                            pass
                        try:
                            # P0-B: 传 outcome dict + goal，让 motivation 消费
                            # FailureDiagnoser 诊断 non-retryable 失败
                            self._motivation.record_result(
                                success, outcome=oc, goal=ep_goal or "")
                        except Exception:
                            logger.exception("Motivation record_result failed")

    def _consolidate(self) -> None:
        """收敛裁决 P3: dream 巩固统一入口 — 委托 Learning/Consolidation Service。

        service 装配失败时诚实跳过（巩固不可用 ≠ daemon 不可用）。
        """
        if self._consolidation is None:
            logger.debug("consolidation unavailable — dream cycle skipped")
            return
        agent_obj = getattr(self._runtime, "agent", None)
        if agent_obj is None:
            return
        self._consolidation.run_dream_cycle(agent_obj)

    # ── 依赖注入 helpers ────────────────────────────────────────────

    def _run_dream_cycle(self) -> None:
        """ACT-R 产生式规则引擎驱动的 dream cycle.

        旧逻辑: 固定顺序 consolidate → ingest → research → evolve
        新逻辑: ActionSelector.snapshot_state → select_modules → 按 score 排序执行

        好处:
          - L0 braked 时只跑 consolidation (不浪费资源)
          - curiosity 低时 research score 自动降到 0
          - evolve 有 2880 tick cooldown → 自然不会每轮都跑
        """
        from ocos.autonomous.action_selector import ActionSelector

        db_path = getattr(self, "_db_path", None)
        if not db_path:
            return

        # 关键修复: ActionSelector 存成实例变量, 不然每次新建实例
        # → _last_run_ticks 状态全丢 → cooldown 失效
        if not hasattr(self, "_action_selector") or self._action_selector is None:
            self._action_selector = ActionSelector(db_path)
        selector = self._action_selector

        state = selector.snapshot_state()
        state.dream_cycle_tick = True

        cycle = getattr(self._runtime, "_cycle_count", 0)
        selected = selector.select_modules(
            state, cycle_count=cycle, braked=self._braked,
        )

        logger.info(
            "🎭 Dream cycle (cycle=%d): %d modules selected "
            "[state=L%d expl=%d growth=%d gap=%.2f k=%d pending=%d]",
            cycle, len(selected),
            state.autonomy_level, state.curiosity_explore,
            state.curiosity_growth, state.avg_prediction_gap,
            state.knowledge_total, state.pending_evolutions,
        )
        for mod, score in selected:
            try:
                if mod == "consolidation":
                    self._consolidate()
                elif mod == "ingest_experience":
                    self._ingest_experience()
                elif mod == "epistemic_research":
                    self._epistemic_research()
                elif mod == "daily_self_evolution":
                    self._daily_self_evolution()
                logger.info("  ✅ %-25s score=%.2f done", mod, score)
            except Exception:
                logger.exception("  ❌ %s failed", mod)

        # ── ReflectionEngine: 双层反思回环 ──
        # dream cycle 结束后, 用 ReflectionEngine 对本轮
        # ingest + research 摄入的新知识做结构化反思.
        # 反思报告写 evolution_artifacts(PENDING) 等人工审核.
        try:
            self._run_reflection(db_path)
        except Exception:
            logger.exception("ReflectionEngine failed")

    def _run_reflection(self, db_path: str) -> None:
        """ReflectionEngine 双层反思回环 — 挂在 dream cycle 末尾."""
        from ocos.autonomous.reflection_engine import ReflectionEngine

        engine = ReflectionEngine(db_path, ingest_batch_threshold=8, auto_save=True)

        # 取最近 ingest_batch_threshold*2 条知识 (本轮 dream 里 ingest + research 刚写的)
        import sqlite3
        c = sqlite3.connect(db_path)
        rows = c.execute(
            "SELECT rowid FROM knowledge ORDER BY rowid DESC LIMIT 16"
        ).fetchall()
        c.close()
        if not rows:
            return

        report = engine.add_batch([str(r[0]) for r in rows])
        if report is None:
            report = engine.reflect_now()
        if report:
            logger.info(
                "  🔄 ReflectionEngine: batch=%d fills_gaps=%d conflicts=%d "
                "deepen_topics=%d gaps_resolved=%d gaps_remaining=%d → saved as PENDING",
                report.batch_size, len(report.fills_gaps),
                len(report.conflicts), len(report.deepen_topics),
                report.gaps_resolved, len(report.gaps_remaining),
            )

    def _build_ingestor(self, db_path: str) -> "UnifiedIngestor":
        """构建完整注入的 UnifiedIngestor (KnowledgeRegistry + SemanticStore + AccessMatrix).

        让 ingest 真正落到 knowledge SQL 表，而不是空操作。
        """
        from ocos.learning.unified_ingestor import UnifiedIngestor
        try:
            from ocos.memory.semantic.store import SemanticStore
            from ocos.knowledge.store.registry import (
                KnowledgeRegistry, AccessMatrix,
            )
            from ocos.knowledge.store.ontology import KnowledgeLevel

            semantic_store = SemanticStore(db_path=db_path)
            semantic_store.initialize()
            access_matrix = AccessMatrix()
            # F2: 给所有会调 ingest 的 owner 都加写权限
            for lvl in KnowledgeLevel:
                for owner in ("daemon_experience", "epistemic_llm",
                              "epistemic_web", "epistemic_research",
                              "daily_self_evolution", "reflection_engine"):
                    access_matrix.set_permission(
                        owner, lvl, can_read=True, can_write=True,
                    )
            registry = KnowledgeRegistry(
                semantic_store=semantic_store,
                access_matrix=access_matrix,
            )
            return UnifiedIngestor(
                knowledge_registry=registry,
                db_path=db_path,
            )
        except Exception:
            logger.warning(
                "Full ingestor injection failed — fallback to plain",
                exc_info=True,
            )
            return UnifiedIngestor(db_path=db_path)

    @staticmethod
    def _build_researcher() -> "WebResearcher":
        """构建注入 SearchOps 的 WebResearcher (DuckDuckGo, 无需 key)."""
        from ocos.learning.channels.web_researcher import WebResearcher
        try:
            from ocos.operations.search_ops import SearchOps
            return WebResearcher(search_ops=SearchOps(), max_results=5)
        except Exception:
            return WebResearcher()

    @staticmethod
    def _build_tutor() -> "LLMTutor":
        """构建注入 TextGenerator 的 LLMTutor.

        TextGenerator() 空构造能自动读 ~/.ocos/config.json 的 DeepSeek key.
        """
        from ocos.learning.channels.llm_tutor import LLMTutor
        try:
            from ocos.engines.text_generator import TextGenerator
            tg = TextGenerator()
            if not tg.available:
                logger.info("LLMTutor: TextGenerator not available (no LLM key)")
                return LLMTutor()  # 无 generator → ask() 返回空
            return LLMTutor(text_generator=tg)
        except Exception:
            return LLMTutor()

    # ── R5: 持续认知循环 (continuous cognition loop) ──────────────────

    def _ensure_cognition_consumed_table(self, db_path: str) -> None:
        """P0-B: 幂等消费记录表 — 确保同一 reflection 只被完整处理一次."""
        import sqlite3
        try:
            conn = sqlite3.connect(db_path)
            conn.execute(
                "CREATE TABLE IF NOT EXISTS cognition_consumed ("
                "  reflection_key TEXT PRIMARY KEY,"
                "  source TEXT NOT NULL,"
                "  consumed_at TEXT NOT NULL,"
                "  knowledge_rowid INTEGER"
                ")"
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_cog_consumed_at ON cognition_consumed(consumed_at)")
            # P0-B 清理: 保留 7 天内的记录（防止表无限增长）
            conn.execute("DELETE FROM cognition_consumed WHERE consumed_at < datetime('now','-7 days')")
            # Phase 2: 向后兼容 — 旧表没有 knowledge_rowid, 懒加列
            try:
                conn.execute("ALTER TABLE cognition_consumed ADD COLUMN knowledge_rowid INTEGER")
            except Exception:
                pass
            conn.commit()
            conn.close()
        except Exception as e:
            logger.debug("🧠 cogni_ensure_table err: %s", e)

    @staticmethod
    def _make_consumption_key(reflection_point: dict) -> str:
        """P0-B: 生成幂等消费键 — (source + question_prefix + hint_prefix + episode_rowid)."""
        import hashlib
        src = reflection_point.get("source", "unknown")
        q = reflection_point.get("question", "")[:60]
        h = reflection_point.get("hint", "")[:40]
        # V3-fix: 加入 episode_rowid 防止不同 rowid 截断碰撞
        eid = reflection_point.get("_consumed_episode_rowid") or reflection_point.get("_knowledge_rowid") or ""
        raw = f"{src}|{q}|{h}|{eid}"
        digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]
        return f"R:{digest}"

    def _is_consumed(self, db_path: str, key: str) -> bool:
        """P0-B: 检查某 reflection_key 是否已被完整消费过."""
        import sqlite3
        try:
            conn = sqlite3.connect(db_path)
            row = conn.execute(
                "SELECT 1 FROM cognition_consumed WHERE reflection_key = ?", (key,)
            ).fetchone()
            conn.close()
            return row is not None
        except Exception:
            return False

    def _mark_consumed(self, db_path: str, key: str, source: str,
                       knowledge_rowid: int | None = None,
                       consumed_episode_rowid: int | None = None) -> None:
        """P0-B + Phase 2 + Phase 2-bugfix: 标记某 reflection_key 为已消费.

        Phase 2: 如果 reflection 是从 knowledge 表 pick 的, 同时存
        knowledge_rowid, 让 (c) 分支能排除已处理的 knowledge rowid.

        Phase 2-bugfix: 如果 reflection 是从 episodes 表 pick 的 (b'),
        同时存 consumed_episode_rowid, 让 (b') 分支能排除已处理的
        failure_lesson episode rowid.
        """
        import sqlite3
        from datetime import datetime, timezone
        try:
            conn = sqlite3.connect(db_path)
            if knowledge_rowid is not None or consumed_episode_rowid is not None:
                conn.execute(
                    "INSERT OR IGNORE INTO cognition_consumed"
                    "(reflection_key, source, consumed_at, "
                    "knowledge_rowid, consumed_episode_rowid) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (key, source, datetime.now(timezone.utc).isoformat(),
                     knowledge_rowid, consumed_episode_rowid),
                )
            else:
                conn.execute(
                    "INSERT OR IGNORE INTO cognition_consumed"
                    "(reflection_key, source, consumed_at) "
                    "VALUES (?, ?, ?)",
                    (key, source, datetime.now(timezone.utc).isoformat()),
                )
            conn.commit()
            conn.close()
        except Exception as e:
            logger.debug("🧠 cogni_mark_consumed err: %s", e)

    def _run_continuous_cognition(self) -> None:
        """每 ≈ 60s 做一次: 反思 → LLM验证学习 → 制定计划.

        P0-B (2026-09-11): 加 consumption_key 幂等闸 —
          同一 reflection (source+question+hint) 只能被完整处理一次,
          防止每 60s 重复 pick 同一条 knowledge → 重复 LLM 调用 →
          重复 knowledge 写入 → 重复 plan 生成, 污染 knowledge 表.

        不动 Step①②③ 的功能逻辑, 只在入口处做幂等拦截.
        功能 re-host 到 AgentRuntime 主链是 C1 scope, P0-B 不涉及.
        """
        import sqlite3
        from datetime import datetime, timezone
        db_path = getattr(self, "_db_path", None)
        logger.debug("🧠 cogni_enter db_path=%s", db_path)
        if not db_path:
            logger.debug("🧠 cogni_skip — no db_path")
            return

        # P0-B: 确保幂等消费表存在
        self._ensure_cognition_consumed_table(db_path)

        # ── 限频 LLM 调用 (60s 内只调一次) ──
        now_ts = datetime.now(timezone.utc).timestamp()
        last_ts = getattr(self, "_last_llm_cognition_ts", 0)
        llm_throttle_ok = (now_ts - last_ts) >= 60

        # ═══════════════════════════════════════════════════════════
        # Step ①: 反思 — 从最近的 gap / failed episode / new pattern 里挑
        # ═══════════════════════════════════════════════════════════
        reflection_point = self._pick_reflection_point(db_path)
        if not reflection_point:
            # 没什么值得反思的 → 也输出心跳日志让人类知道大脑在跳
            logger.debug("🧠 cognition heartbeat — nothing new to reflect")
            return

        logger.info("🧠 Cognition Loop Step① reflection: %s", reflection_point.get("question", "")[:80])

        # ── P0-B: 幂等消费闸 ──
        consumption_key = self._make_consumption_key(reflection_point)
        logger.info(
            "🧠 cogni_step15 — about to check idempotent gate "
            "(key=%s source=%s)",
            consumption_key, reflection_point.get("source", ""),
        )
        if self._is_consumed(db_path, consumption_key):
            logger.debug(
                "🧠 cogni_idempotent_skip — reflection already consumed "
                "(key=%s source=%s)",
                consumption_key, reflection_point.get("source", ""),
            )
            return  # ← P0-B: 直接返回, 不调 LLM, 不写 knowledge, 不生成 plan

        # ═══════════════════════════════════════════════════════════
        # Step ②: LLM 验证学习 — 把反思疑问喂给 LLMTutor
        # ═══════════════════════════════════════════════════════════
        llm_findings = ""
        if llm_throttle_ok:
            try:
                tutor = self._build_tutor()
                question = reflection_point.get("question", "")
                if question and tutor is not None:
                    resp = tutor.ask(question)
                    if resp and resp.success:
                        llm_findings = resp.answer or ""
                        logger.info("🧠 Cognition Loop Step② LLM verified: %s", llm_findings[:100])
                        # 限频更新
                        self._last_llm_cognition_ts = now_ts
                        # 沉淀到 knowledge
                        try:
                            ingestor = self._build_ingestor(db_path=db_path)
                            if ingestor is not None and llm_findings:
                                from ocos.learning.unified_ingestor import IngestArtifact, SourceChannel
                                art = IngestArtifact(
                                    channel=SourceChannel.LLM_QA,
                                    content=f"Q: {question}\nA: {llm_findings[:500]}",
                                    title=f"Cognition Loop: {question[:60]}",
                                    confidence=0.65,
                                    metadata={"reflection_point": reflection_point.get("source", "")},
                                    knowledge_type="concept",
                                )
                                result = ingestor.ingest(art, owner="epistemic_llm")
                                logger.debug("🧠 cogni_ingest result=%s", result)
                                # ingest 可能返回 IngestResult 对象或 dict
                                stored_count = 0
                                if hasattr(result, 'status'):
                                    # IngestResult 对象
                                    if result.status.value == "stored":
                                        stored_count = 1
                                elif isinstance(result, dict):
                                    stored_count = result.get("stored", 0)
                                elif isinstance(result, list):
                                    stored_count = sum(1 for r in result
                                                       if hasattr(r,'status') and r.status.value=="stored"
                                                       or isinstance(r,dict) and r.get("status")=="stored")
                                if stored_count > 0:
                                    logger.info("🧠 Cognition Loop Step② stored knowledge +%d", stored_count)
                        except Exception as e:
                            logger.debug("🧠 cogni_ingest err: %s", e)
            except Exception as e:
                logger.debug("LLM cognition step failed: %s", e)

        # ═══════════════════════════════════════════════════════════
        # Step ③: 制定计划 — 写 mini-plan + 注入 follow-up goal
        # ═══════════════════════════════════════════════════════════
        try:
            plan = self._build_plan_from_reflection(reflection_point, llm_findings, db_path)
            if plan:
                logger.info("🧠 Cognition Loop Step③ plan generated: %s", plan.get("title", "")[:80])
                # 写 PENDING evolution artifact (需人工审核)
                try:
                    from ocos.evolution.artifacts import EvolutionArtifactStore, EvolutionArtifact, ArtifactType
                    store = EvolutionArtifactStore(db_path=db_path)
                    art = EvolutionArtifact.new(
                        type=ArtifactType.PLAN,
                        title=plan["title"],
                        summary=plan["summary"],
                        content=plan["content"],
                        confidence=0.6,
                        source_agent="continuous_cognition",
                        tags=["cognition_loop", "auto_generated", "mini_plan"],
                        risk_level="LOW",
                        human_review_required=True,
                    )
                    store.save(art)
                    logger.info("🧠 Cognition Loop Step③ saved PENDING plan → %s", art.artifact_id)
                except Exception as e:
                    logger.debug("🧠 cogni_plan_save failed: %s", e)
        except Exception as e:
            logger.debug("🧠 cogni_plan_step failed: %s", e)

        # ── P0-B: 标记为已消费 ──
        # 无论 Step②/③ 成功与否都标记 — 幂等闸的目的是防止
        # 同一条 reflection 被反复处理, 不是保证每次都成功.
        # 如果 Step② LLM 调用抛异常, 下次再来还是同一条,
        # 继续失败继续污染 knowledge 表没有意义.
        self._mark_consumed(
            db_path, consumption_key,
            reflection_point.get("source", "unknown"),
            knowledge_rowid=reflection_point.get("_knowledge_rowid"),
            consumed_episode_rowid=reflection_point.get(
                "_consumed_episode_rowid"),
        )

    def _pick_reflection_point(self, db_path: str) -> dict | None:
        """Step①: 挑一个值得反思的点."""
        import sqlite3
        try:
            conn = sqlite3.connect(db_path)
        except Exception as e:
            logger.info("🧠 pick_reflect sqlite3.connect failed: %s", e)
            return None

        # (a) gap
        try:
            from ocos.reasoning.curiosity import PredictionGapTracker
            tracker = PredictionGapTracker(db_path=db_path)
            gaps = tracker.emit_gap_hypothesis(top_n=1)
            if gaps:
                g = gaps[0]
                conn.close()
                logger.info("🧠 pick_reflect hit (a) gap: %s", g.get('hypothesis','')[:60])
                return {
                    "source": "prediction_gap",
                    "question": f"为什么 {g['task_text'][:60]} 预测准确率只有 {g['error_magnitude']:.2f}? 如何改进?",
                    "hint": g.get("hypothesis", "")[:100],
                }
            logger.debug("🧠 pick_reflect (a) gap empty")
        except Exception as e:
            logger.debug("🧠 pick_reflect (a) gap err: %s", e)

        # (b) 最近 failed goal
        try:
            row = conn.execute(
                "SELECT substr(description,1,80) as d, created_at FROM goals "
                "WHERE status IN ('abandoned','failed','expired') "
                "ORDER BY rowid DESC LIMIT 1"
            ).fetchone()
            if row:
                conn.close()
                logger.info("🧠 pick_reflect hit (b) failed goal")
                return {
                    "source": "failed_goal",
                    "question": f"这个目标为什么失败了? 有没有办法让下次成功? 目标: {row[0]}",
                    "hint": "失败原因分析",
                }
            logger.debug("🧠 pick_reflect (b) no failed goal")
        except Exception as e:
            logger.debug("🧠 pick_reflect (b) err: %s", e)

        # (b') 最近 failure_lesson Episodes (Phase 3 + Phase 2-bugfix V2)
        # Planning 路径的真实失败 (MUTATION-VETO → canonical lesson)
        # → 直接进 Cognition 候选池, 不隔 knowledge 表.
        # Phase 2-bugfix V2: 同时排除:
        #   a) consumed_episode_rowid 已记录的 rows (正常路径)
        #   b) 幽灵 key hash: consumed_episode_rowid=None 但 reflection_key
        #      存在的记录 (修复前的旧记录, _make_consumption_key 对同一个
        #      episode rowid 会生成同一个 key → 幂等闸在 pick 阶段就该排除)
        try:
            # Phase 2-bugfix: 确保表有 consumed_episode_rowid 列
            try:
                conn.execute(
                    "ALTER TABLE cognition_consumed "
                    "ADD COLUMN consumed_episode_rowid INTEGER")
            except Exception:
                pass
            # 一次拉齐所有已消耗 episode rowid + 幽灵 rowid (从 key hash 反推)
            # 幽灵 key 无法反推 rowid (key 是 hash), 所以用 NOT IN + 额外扫描
            _all_consumed_keys = set()
            _consumed_rows = conn.execute(
                "SELECT reflection_key, consumed_episode_rowid "
                "FROM cognition_consumed WHERE source='failure_lesson_episode'"
            ).fetchall()
            _explicit_eids = [r[1] for r in _consumed_rows if r[1] is not None]
            _ghost_keys = [r[0] for r in _consumed_rows if r[1] is None]

            # 优先用明确的 rowid NOT IN 排除
            _params_excl = list(_explicit_eids)
            _sql_extra = ""
            if _params_excl:
                _sql_extra = (f" AND e.rowid NOT IN "
                              f"({','.join('?'*len(_params_excl))})")

            row = conn.execute(
                f"SELECT e.rowid, e.context, e.created_at "
                f"FROM episodes e "
                f"WHERE e.action = 'failure_lesson' "
                f"{_sql_extra} "
                f"ORDER BY e.rowid DESC LIMIT 1",
                _params_excl,
            ).fetchone()

            # V2-bugfix: 即使 SQL 层面没排除, 也用 key hash 二次确认.
            # 用 while 循环逐条验 ghost key — 确保不会只跳一条就停.
            while row and row[1] and _ghost_keys:
                _test_point = {
                    "source": "failure_lesson_episode",
                    "question": "x",  # 占位, 下面用真实值
                    "hint": "x",
                }
                import json as _json
                try:
                    _ctx_test = _json.loads(row[1])
                except Exception:
                    _ctx_test = {}
                _cause_test = _ctx_test.get("cause", "?")
                _blocked_test = str(_ctx_test.get("blocked_action", ""))[:60]
                _test_point["question"] = (
                    f"最近有一个 {_cause_test} 失败: "
                    f"blocked_action='{_blocked_test}' → "
                    f"从中学到了什么? 如何改进未来的规划?")
                _test_point["hint"] = f"failure cause={_cause_test}"
                _test_key = self._make_consumption_key(_test_point)
                if _test_key in _ghost_keys:
                    # 这条 rowid 对应的 key 已被幽灵记录 → 跳过, 找下一条
                    logger.info(
                        "🧠 pick_reflect (b') skip rowid=%d: ghost key=%s "
                        "→ recursing to next rowid",
                        row[0], _test_key)
                    row = conn.execute(
                        f"SELECT e.rowid, e.context, e.created_at "
                        f"FROM episodes e "
                        f"WHERE e.action = 'failure_lesson' "
                        f"AND e.rowid < ? {_sql_extra} "
                        f"ORDER BY e.rowid DESC LIMIT 1",
                        [row[0]] + _params_excl,
                    ).fetchone()
                else:
                    break  # 找到一条 key 不在 ghost_keys 里的 → 跳出循环

            if row and row[1]:
                _erowid, _ctx_str = row[0], row[1]
                import json as _json
                try:
                    ctx = _json.loads(_ctx_str)
                except Exception:
                    ctx = {}
                _cause = ctx.get("cause", "?")
                _blocked = str(ctx.get("blocked_action", ""))[:60]
                conn.close()
                logger.info(
                    "🧠 pick_reflect hit (b') failure_lesson rowid=%d", _erowid)
                return {
                    "source": "failure_lesson_episode",
                    "question": (f"最近有一个 {_cause} 失败: "
                                 f"blocked_action='{_blocked}' → "
                                 f"从中学到了什么? 如何改进未来的规划?"),
                    "hint": f"failure cause={_cause}",
                    "_consumed_episode_rowid": _erowid,
                }
            logger.debug("🧠 pick_reflect (b') no failure_lesson")
        except Exception as e:
            logger.debug("🧠 pick_reflect (b') err: %s", e)

        # (c) 新知识 — 优先挑 agent 工作沉淀的 (lesson/principle/procedure),
        #     排除认知循环自己刚刚沉淀的 concept, 避免递归嵌套自激.
        # Phase 2: 排除已被 consumed 的 knowledge rowid — 让大脑能跳到下一条
        try:
            _consumed_kids = [r[0] for r in conn.execute(
                "SELECT knowledge_rowid FROM cognition_consumed "
                "WHERE knowledge_rowid IS NOT NULL"
            ).fetchall()]
            _excl = f"AND rowid NOT IN ({','.join('?'*len(_consumed_kids))})" if _consumed_kids else ""
            row = conn.execute(
                f"SELECT rowid, substr(statement,1,80) as s, scope_domain "
                f"FROM knowledge "
                f"WHERE scope_domain IN ('lesson','principle','procedure','debug') "
                f"{_excl} "
                f"ORDER BY rowid DESC LIMIT 1",
                _consumed_kids,
            ).fetchone()
            if not row:
                row = conn.execute(
                    f"SELECT rowid, substr(statement,1,80) as s, scope_domain "
                    f"FROM knowledge "
                    f"WHERE scope_domain = 'concept' AND statement NOT LIKE '%Q: 新知识%' "
                    f"{_excl} "
                    f"ORDER BY rowid DESC LIMIT 1",
                    _consumed_kids,
                ).fetchone()
            if row and row[1]:
                _krowid, _stmt, _domain = row
                conn.close()
                logger.info("🧠 pick_reflect hit (c) knowledge rowid=%d", _krowid)
                return {
                    "source": "new_knowledge",
                    "question": (f"新知识 [{_domain}] 说 '{_stmt}' — "
                                 f"这个对 OCOS 架构意味着什么? 有什么可以落地的改进?"),
                    "hint": "知识落地建议",
                    "_knowledge_rowid": _krowid,  # Phase 2: 让 _mark_consumed 存
                }
            logger.debug("🧠 pick_reflect (c) no knowledge")
        except Exception as e:
            logger.debug("🧠 pick_reflect (c) err: %s", e)

        # (d) deepen topics
        try:
            row = conn.execute(
                "SELECT topic FROM reflection_seed_topics WHERE used=0 ORDER BY rowid DESC LIMIT 1"
            ).fetchone()
            logger.debug("🧠 pick_reflect (d) row=%s", row)
            if row:
                conn.close()
                logger.info("🧠 pick_reflect hit (d) deepen topic")
                return {
                    "source": "deepen_topic",
                    "question": f"深入学习: {row[0]}",
                    "hint": "反思引导",
                }
        except Exception as e:
            logger.debug("🧠 pick_reflect (d) err: %s", e)

        conn.close()
        logger.debug("🧠 pick_reflect ALL branches missed → None")
        return None

    def _build_plan_from_reflection(
            self, reflection: dict, llm_findings: str, db_path: str) -> dict | None:
        """Step③: 从反思 + LLM 学习结果构建一个 mini-plan."""
        if not reflection:
            return None

        src = reflection.get("source", "reflection")
        q = reflection.get("question", "")[:100]
        h = reflection.get("hint", "")

        # 构建 plan content (简短, 因为是每 60s 一次)
        content_lines = [
            f"# Mini-Plan: 来自持续认知循环",
            f"",
            f"## 触发源",
            f"- 来源: {src}",
            f"- 问题: {q}",
            f"- 提示: {h}",
            f"",
        ]
        if llm_findings:
            content_lines.extend([
                f"## LLM 学习结果",
                f"{llm_findings[:600]}",
                f"",
            ])
        content_lines.extend([
            f"## 建议行动",
            f"1. 基于以上分析, 增加一个 follow-up goal 深入探索",
            f"2. 下次 dream consolidation 时重点关注这个方向",
            f"3. 如果 LLM 学习结果有代码架构启发, 记入 knowledge principle",
        ])

        title = f"Mini-Plan: {src} — {q[:40]}"
        return {
            "title": title[:80],
            "summary": f"[{src}] {q[:60]}",
            "content": "\n".join(content_lines),
        }

    # ── Phase S2-P2: 每日自进化循环 ─────────────────────────────────

    # 每 N 个 dream_interval 触发一次自进化（≈ 4h）
    _EVOLUTION_INTERVAL_TICKS = 2880

    # 种子学习主题 — 长期自我进化方向
    _EVOLUTION_SEED_TOPICS = [
        "cognitive architecture ACT-R SOAR CLARION",
        "LLM agent reflection self-improving",
        "digital life autonomous learning loop",
        "knowledge representation semantic memory",
        "autonomous agent curiosity-driven",
        "self-evolving code architecture",
        "cognitive load decision efficiency",
    ]

    def _daily_self_evolution(self) -> None:
        """每日自进化循环 — 双路径学习 + 自我总结优化方案.

        触发条件: cycle % _EVOLUTION_INTERVAL_TICKS == 0 (dream cycle 时检查)

        执行步骤:
          1. EpistemicDrive suggest → 挑 3 个不确定/薄弱领域
          2. LLMTutor 对每个领域问 3 个核心问题 → 沉淀 knowledge
          3. WebResearcher 对每个领域搜 2 个 query → 沉淀 knowledge
          4. 记录当日学习统计 → 输出日志
          5. (可选) LLM 总结生成自我优化方案 → 写入 knowledge principles
        """
        from ocos.learning.unified_ingestor import IngestStatus

        db_path = getattr(self, "_db_path", None)
        cycle = getattr(self._runtime, "_cycle_count", 0)
        if not db_path or cycle % self._EVOLUTION_INTERVAL_TICKS != 0:
            return

        logger.info(
            "━━━ 每日自进化循环 启动 (cycle=%d) ━━━", cycle)

        ingestor = self._build_ingestor(db_path)
        researcher = self._build_researcher()
        tutor = self._build_tutor()

        # ── Step 1: EpistemicDrive suggest + 种子主题补充 ──
        topics: list[str] = []
        try:
            from ocos.reasoning.curiosity import PredictionGapTracker, EpistemicDrive
            tracker = PredictionGapTracker(db_path=db_path)
            drive = EpistemicDrive(tracker=tracker, db_path=db_path, top_n=3)
            topics.extend(list(drive.suggest_explore())[:3])
            topics.extend(list(drive.suggest_growth())[:2])
        except Exception:
            pass  # EpistemicDrive 失败不阻塞

        # 种子主题 fallback — 保证每次都有东西学
        if not topics:
            # 用 cycle 取模挑 3 个种子主题，让每轮都不同
            import hashlib

            def _topic_key(t: str) -> int:
                return int(hashlib.md5(t.encode()).hexdigest(), 16) % cycle

            topics = sorted(
                self._EVOLUTION_SEED_TOPICS,
                key=_topic_key,
            )[:3]

        logger.info("  📋 本轮学习主题 (%d): %s",
                     len(topics), topics)

        total_stored = 0
        total_new = 0

        # ── Step 2+3: 双路径学习 ──
        for topic in topics[:3]:
            # 路径 1: LLMTutor (问 3 个核心问题)
            for question in [
                f"什么是 {topic}？核心原理和关键概念是什么？",
                f"{topic} 对自主 Agent / 数字生命有什么实际启发？",
                f"如何把 {topic} 的思想融入 OCOS 的自我进化架构？",
            ]:
                result = tutor.ask(question)
                if result.success and result.answer.strip():
                    arts = result.to_ingest_artifacts()
                    for art in arts:
                        for r in ingestor.ingest(art, owner="daily_evolve_llm"):
                            if r.status == IngestStatus.STORED:
                                total_stored += 1
                                total_new += 1

            # 路径 2: WebResearcher (搜 2 个 query)
            for query in [topic, f"{topic} 2024 2025 latest"]:
                try:
                    res = researcher.research(query)
                    if res and getattr(res, "findings", None):
                        for finding in res.findings[:2]:
                            from ocos.learning.unified_ingestor import IngestArtifact, SourceChannel
                            art = IngestArtifact(
                                channel=SourceChannel.WEB_RESEARCH,
                                content=str(finding)[:500],
                                title=f"web:{query[:40]}",
                                confidence=getattr(res, "confidence", 0.7),
                                tags=["daily_evolve", topic[:20]],
                            )
                            for r in ingestor.ingest(art, owner="daily_evolve_web"):
                                if r.status == IngestStatus.STORED:
                                    total_stored += 1
                                    total_new += 1
                except Exception:
                    pass  # DuckDuckGo 超时/空结果 → 跳过

        # ── Step 5: 自我总结优化方案 → 写 evolution_artifacts (PENDING) ──
        # 关键闸门: 方案不直接写 knowledge — 必须经人工审核 (approve) 后才能沉淀
        if tutor._generator is not None and total_new > 0:
            try:
                summary_prompt = (
                    f"你是 OCOS 数字生命的自我进化顾问。"
                    f"今天 OCOS 学习了 {total_new} 条新知识 (关于 {', '.join(topics[:2])}),"
                    "涉及认知架构、LLM Agent 自反思、数字生命自主学习等方向。"
                    "OCOS 当前架构有 daemon 守护进程、EpistemicDrive 好奇心、"
                    "KnowledgeRegistry 知识沉淀、GrowthOptimizer 自进化护栏。"
                    "请基于这些方向分析 OCOS 可以如何自我升级，提出 3 条具体的优化建议。"
                    "每条建议要包含: 改动点、预期收益、风险评估 (LOW/MEDIUM/HIGH)。"
                )
                summary = tutor.ask(summary_prompt)
                if summary.success and summary.answer.strip():
                    try:
                        from ocos.evolution.artifacts import (
                            EvolutionArtifact, ArtifactType,
                            EvolutionArtifactStore,
                        )

                        evo_store = EvolutionArtifactStore(db_path)
                        evo_art = EvolutionArtifact.new(
                            type=ArtifactType.PLAN,
                            title=f"每日自进化方案 (cycle={cycle})",
                            content=summary.answer.strip(),
                            summary=summary.answer.strip()[:150],
                            confidence=0.85,
                            source_agent="daily_evolve_plan",
                            tags=["self_evolution", "daily_plan"],
                            risk_level="MEDIUM",  # 方案默认 MEDIUM 风险
                            human_review_required=True,
                        )
                        evo_store.save(evo_art)
                        logger.info(
                            "  📝 自我优化方案已产出 (EVO-%s) → "
                            "待人工审核后沉淀 knowledge",
                            evo_art.artifact_id,
                        )
                    except Exception as e:
                        logger.warning(
                            "  self-evolution artifact save failed: %s", e)
            except Exception:
                pass

        logger.info(
            "━━━ 每日自进化循环 完成 (cycle=%d): "
            "stored=%d topics=%d new=%d ━━━",
            cycle, total_stored, len(topics), total_new,
        )

    # ── Phase S2-P1b: UnifiedIngestor 经验自动摄入 ──
    def _ingest_experience(self) -> None:
        """每 dream_interval 触发 — ExperienceExtractor → UnifiedIngestor.

        注入完整 KnowledgeRegistry(semantic_store) + BeliefStore ——
        让 ingest 真正落到 knowledge / belief SQL 表。
        """
        try:
            from ocos.learning.channels.experience_extractor import ExperienceExtractor
            from ocos.learning.unified_ingestor import IngestStatus

            db_path = getattr(self, "_db_path", None)
            if not db_path:
                return
            extractor = ExperienceExtractor(db_path=db_path)
            ingestor = self._build_ingestor(db_path)
            artifacts = extractor.extract_recent(days=7, limit=20)
            if not artifacts:
                return
            stored = dup = filt = fail = 0
            for exp in artifacts:
                # ExperienceExtractor 返回 ExperienceArtifact —— 先调
                # to_ingest_artifacts() 转成 IngestArtifact 再喂 ingestor
                ingest_arts = (
                    exp.to_ingest_artifacts()
                    if hasattr(exp, "to_ingest_artifacts")
                    else [exp]
                )
                for art in ingest_arts:
                    try:
                        results = ingestor.ingest(
                            art, owner="daemon_experience")
                        for r in results:
                            if r.status == IngestStatus.STORED:
                                stored += 1
                            elif r.status == IngestStatus.DUPLICATE:
                                dup += 1
                            elif r.status == IngestStatus.FILTERED_LOW_QUALITY:
                                filt += 1
                            else:
                                fail += 1
                    except Exception:
                        logger.exception(
                            "UnifiedIngestor failed for one artifact")
            logger.info(
                "Phase S2-P1b ingest: %d raw → stored=%d dedup=%d "
                "filtered=%d failed=%d",
                len(artifacts), stored, dup, filt, fail)
        except Exception:
            logger.debug(
                "UnifiedIngestor skipped (no data or missing deps)",
                exc_info=True)

        # Phase S2-P2b: working_memory 自动填充 — 跨 tick 活跃推理上下文
        try:
            from ocos.storage.working_memory import WorkingMemory
            wm = WorkingMemory(db_path=db_path)
            agent_obj = getattr(self._runtime, "agent", None)
            wm.store("daemon.cycle", {
                "tick": self._hb_ticks,
                "cycle": getattr(self._runtime, "_cycle_count", 0),
                "autonomy_level": getattr(self, "_autonomy_level", "ask"),
                "active_goal": str(getattr(agent_obj, "goal_stack", None))[:100] if agent_obj else None,
            }, ttl=600)  # 10 分钟过期
        except Exception:
            pass

    # ── Phase S2-P1a: EpistemicDrive → WebResearcher + LLMTutor 自动调研 ──
    def _epistemic_research(self) -> None:
        """每 dream_interval 触发 — EpistemicDrive 高不确定性 domain → WebResearcher + LLMTutor."""
        try:
            from ocos.reasoning.curiosity import PredictionGapTracker, EpistemicDrive
            from ocos.learning.channels.web_researcher import WebResearcher
            from ocos.learning.channels.llm_tutor import LLMTutor
            from ocos.learning.unified_ingestor import (
                UnifiedIngestor, IngestArtifact, SourceChannel, IngestStatus,
            )

            db_path = getattr(self, "_db_path", None)
            if not db_path:
                return

            # EpistemicDrive: 拿 top 1 不确定性 domain
            tracker = PredictionGapTracker(db_path=db_path)
            drive = EpistemicDrive(tracker=tracker, db_path=db_path, top_n=1)
            suggestions = (
                list(drive.suggest_growth())[:1]
                + list(drive.suggest_explore())[:1]
            )
            if not suggestions:
                return

            ingestor = self._build_ingestor(db_path)
            researcher = self._build_researcher()
            tutor = self._build_tutor()
            total_stored = 0
            for topic in suggestions[:2]:  # 每轮最多 2 个调研（限流）
                # 渠道 1: WebResearcher
                try:
                    result = researcher.research(topic)
                    if result and getattr(result, "findings", None):
                        for finding in result.findings[:3]:
                            art = IngestArtifact(
                                channel=SourceChannel.WEB_RESEARCH,
                                content=f"调研「{topic}」: {finding}",
                                title=f"web:{topic[:40]}",
                                confidence=getattr(result, "confidence", 0.7),
                                tags=["web_research", topic[:20]],
                                metadata={
                                    "topic": topic,
                                    "source": getattr(result, "source", "web"),
                                },
                            )
                            rs = ingestor.ingest(art, owner="epistemic_web")
                            for r in rs:
                                if r.status == IngestStatus.STORED:
                                    total_stored += 1
                        logger.info(
                            "Phase S2-P1a web research: '%s' → %d findings",
                            topic[:40], len(result.findings[:3]))
                except Exception:
                    logger.exception(
                        "Phase S2-P1a web research failed for '%s'",
                        topic[:40])

                # 渠道 2: LLMTutor (内部 LLM 知识库问答)
                try:
                    qa = tutor.ask(topic)
                    if qa and getattr(qa, "success", False) and getattr(qa, "answer", None):
                        art = IngestArtifact(
                            channel=SourceChannel.LLM_QA,
                            content=f"LLM 问答「{topic}」: {qa.answer}",
                            title=f"llm_qa:{topic[:40]}",
                            confidence=getattr(qa, "confidence", 0.6),
                            tags=["llm_qa", topic[:20]],
                            metadata={"topic": topic, "source": "llm_tutor"},
                        )
                        rs = ingestor.ingest(art, owner="epistemic_llm")
                        for r in rs:
                            if r.status == IngestStatus.STORED:
                                total_stored += 1
                        logger.info(
                            "Phase S2-P1a llm tutor: '%s' → 1 answer",
                            topic[:40])
                except Exception:
                    logger.exception(
                        "Phase S2-P1a llm tutor failed for '%s'",
                        topic[:40])

            logger.info(
                "Phase S2-P1a total epistemic artifacts stored: %d",
                total_stored)
        except Exception:
            logger.debug("Epistemic research skipped", exc_info=True)

    def _write_heartbeat(self) -> None:
        """UX-F3: 每 tick 写心跳文件（Web 侧栏/状态命令判断存活）。

        L0-3/L0-5: 心跳携带自主级别与制动状态 — `ocos status`/vitals
        可判断"进程活着但被制动"（区别于僵死）。
        """
        import json
        from pathlib import Path
        hb = Path(os.environ.get(
            "OCOS_HEARTBEAT_PATH",
            str(Path.home() / ".ocos" / "daemon_heartbeat.json")))
        hb.parent.mkdir(parents=True, exist_ok=True)
        hb.write_text(json.dumps({
            "pid": os.getpid(),
            "cycle": getattr(self._runtime, "_cycle_count", 0),
            "braked": self._braked,
            "autonomy_level": self._autonomy_level,
            "ts": datetime.now(timezone.utc).isoformat(),
        }), encoding="utf-8")

    def _drain_user_inbox(self) -> int:
        """FIX-03: 消费收件箱中的用户消息 → respond_auto（对话即路由）。

        改为与 web/TUI 一致的路由逻辑：任务类消息自动受理为目标，
        回复中注入 goal_id 供后续追问 grounding。
        """
        if self._user_inbox is None:
            return 0
        try:
            messages = self._user_inbox.drain(limit=3)
        except Exception:
            logger.exception("UserInbox drain failed")
            return 0
        for msg in messages:
            # FIX-03: 改用 respond_auto 以统一路由逻辑
            if self._responder is not None:
                try:
                    out = self._responder.respond_auto(
                        msg["content"], session_id=msg.get("session_id", "say"))
                    goal_id = out.get("goal_id")
                    if out.get("accepted", True):
                        logger.info("User message delivered: %s (%s)",
                                    msg["id"], msg["content"][:40])
                        if goal_id:
                            logger.info("Goal created: %s", goal_id)
                    else:
                        logger.warning("User message rejected: %s", msg["id"])
                    # FIX-VAL1: 回复写回收件箱（ocos say --wait 的轮询源），
                    # 并投递 outbound 供 TUI /outbox 可见 — 修复 FIX-03 回复丢失回归
                    reply_text = str(out.get("reply", "") or "")
                    if not reply_text:
                        reply_text = "（daemon 已处理该消息，但未生成文本回复）"
                    try:
                        self._user_inbox.reply(msg["id"], reply_text)
                        self._user_inbox.post_outbound(reply_text)
                    except Exception:
                        logger.exception("Inbox reply write-back failed: %s", msg["id"])
                    continue
                except Exception as exc:
                    logger.exception("respond_auto failed, falling back to inject")
                    # FIX-VAL1: 失败也要写回诚实错误 — --wait 不应无限悬挂
                    try:
                        self._user_inbox.reply(
                            msg["id"], f"（消息处理失败：{type(exc).__name__} — 详见 daemon 日志）")
                    except Exception:
                        logger.exception("Inbox failure reply write-back failed: %s", msg["id"])
            # fallback: 旧路径（_responder 为 None 时）
            try:
                result = self._runtime.inject_user_message(
                    msg["content"], sender=msg.get("sender", "say"))
                if result.get("accepted"):
                    logger.info("User message delivered: %s (%s)",
                                msg["id"], msg["content"][:40])
            except Exception:
                # fallback 也必须保护 — 此函数被主 tick 循环裸调用
                logger.exception("inject_user_message fallback failed: %s",
                                 msg["id"])
        return len(messages)

    def _perceive(self) -> dict:
        """V3 感知-反应神经: 刺激扫描 → EventBus 留痕 → PROBE 落地。

        这是 OCOS 第一条"刺激驱动"行为通路（此前全部行为皆目标驱动
        或用户驱动）。扫描无刺激时零开销。
        """
        if self._stimulus is None:
            return {"fired": 0, "proposed": 0}
        stimuli = self._stimulus.scan()
        for s in stimuli:
            try:
                self._event_bus.push_stimulus(s)
            except Exception:
                logger.debug("event bus push failed", exc_info=True)
        if stimuli and self._motivation is not None:
            stats = self._motivation.propose_stimulus(
                stimuli, level=self._autonomy_level)
            logger.info("Perception → motivation: %s", stats)
            return {"fired": len(stimuli), **stats}
        return {"fired": len(stimuli), "proposed": 0}

    def _auto_approve_pending(self, cap: int = 10) -> int:
        """全自动模式（OCOS_APPROVAL_MODE=auto）: 待批队列每 tick 自动通过。

        用户决策（2026-09-07，个人使用模式）: 不使用人工审批，全部自动
        通过。治理留痕完整保留 — decide(decided_by="auto") 与 execute_approved
        走与人工批准同一条溯源通道（approval_id 校验、ExecutionAudit、
        result_summary 回写均不绕过）；ask 模式下本方法为零开销空转。
        cap/tick 防积压一次性爆发挤爆 tick 预算。
        """
        bridge = getattr(self._runtime, "_decision_bridge", None)
        store = getattr(bridge, "_pending_store", None)
        if bridge is None or store is None:
            return 0
        from ocos.execution.pending import approval_disabled
        if not approval_disabled():
            return 0
        try:
            rows = store.list_by_status("pending")[:cap]
        except Exception:
            logger.exception("auto approve: list pending failed")
            return 0
        n = 0
        for row in rows:
            pid = row.get("id", "")
            try:
                if not store.decide(pid, approved=True, decided_by="auto"):
                    continue
                payload = json.loads(row.get("payload_json") or "{}")
                payload.setdefault("approval_id", pid)
                dispatched = bridge.execute_approved(
                    row["action_type"], payload)
                ok = (dispatched is not None
                      and getattr(dispatched, "status", "") == "done")
                summary = (str(getattr(dispatched, "result", ""))[:500]
                           if dispatched is not None else "no executor")
                store.mark_executed(pid, result_summary=summary, executed=ok)
                n += 1
                logger.info("Auto-approved %s (%s) -> %s",
                            pid, row["action_type"],
                            "executed" if ok else "blocked")
            except Exception:
                logger.exception("auto approve failed: %s", pid)
        return n

    # U5: 每日学习摘要推送
    def _push_daily_learning_summary(self) -> None:
        """每天一次: 从 lessons 视图收集今日 failure lessons，
        生成 3-5 条关键发现，推送到 user_inbox（daemon 主动说话）。"""
        import datetime as _dt
        today = _dt.date.today().isoformat()
        last_date = getattr(self, "_last_daily_summary_date", "")
        if last_date == today:
            return  # 今天已推送过

        try:
            import sqlite3 as _sqlite3
            import os as _os
            from ocos.interaction.inbox import UserInbox

            db_path = _os.path.expanduser("~/.ocos/ocos.db")
            if not _os.path.exists(db_path):
                return
            conn = _sqlite3.connect(db_path)
            conn.row_factory = _sqlite3.Row

            # 今日 failure lessons 总数 + cause 分布
            agg = conn.execute("""
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN outcome LIKE '%execution_error%' THEN 1 ELSE 0 END) as exec_err,
                    SUM(CASE WHEN outcome LIKE '%permission_denied%' THEN 1 ELSE 0 END) as perm,
                    SUM(CASE WHEN outcome LIKE '%dependency_missing%' THEN 1 ELSE 0 END) as dep
                FROM lessons WHERE date(created_at)=?""", (today,)).fetchone()

            total = agg["total"] if agg else 0
            if total == 0:
                conn.close()
                self._last_daily_summary_date = today
                return  # 今天没东西，也记日期避免反复查

            # Top 3 高频 agent
            top_agents = conn.execute("""
                SELECT tags, COUNT(*) as c FROM lessons
                WHERE date(created_at)=? GROUP BY tags ORDER BY c DESC LIMIT 3
            """, (today,)).fetchall()

            conn.close()

            # 摘要文案
            lines = [f"📚 今日学习摘要（{today}）", f"共 {total} 条 failure lesson"]
            if agg["exec_err"]:
                lines.append(f"  · 执行错误 {agg['exec_err']} 次")
            if agg["perm"]:
                lines.append(f"  · 权限拒绝 {agg['perm']} 次")
            if agg["dep"]:
                lines.append(f"  · 依赖缺失 {agg['dep']} 次")
            if top_agents:
                _agents = []
                for a in top_agents:
                    _t = (a["tags"] or "")
                    if "writer" in _t.lower():
                        _agents.append(f"writer×{a['c']}")
                    elif "reviewer" in _t.lower():
                        _agents.append(f"reviewer×{a['c']}")
                    elif "planner" in _t.lower():
                        _agents.append(f"planner×{a['c']}")
                if _agents:
                    lines.append(f"高频: {', '.join(_agents)}")

            summary = "\n".join(lines)
            logger.info("Daily learning summary:\n%s", summary)

            # 推送到 outbox（daemon 主动输出 → post_outbound，带 kind）
            try:
                inbox = UserInbox(db_path=db_path)
                inbox.post_outbound(content=summary, kind="report")
            except Exception:
                logger.exception("Failed to push daily summary to outbox")

            self._last_daily_summary_date = today
        except Exception:
            logger.exception("Daily learning summary generation failed")

    def _pump_evolution_artifacts(self, cap: int = 5) -> int:
        """B1 管道打通: evolution_artifacts PENDING→APPROVED→goals 表.

        每 12 tick (≈60s) 扫一次:
          1) PENDING auto_generated + LOW risk + confidence>=0.6 → 自动 APPROVED
             (去重: 同 summary 已存在 APPROVED 则跳过)
          2) APPROVED plan (applied_at IS NULL) → 写 goals 表 PENDING
             (limit=cap, 节流防爆发)
        """
        from ocos.evolution.artifacts import (
            EvolutionArtifactStore, ArtifactStatus, ArtifactType,
        )
        store = EvolutionArtifactStore(self._db_path)

        # ── Step 1: 自动批准低风险 PENDING plans ──
        auto_approved = 0
        try:
            pending = store.list(
                status=ArtifactStatus.PENDING,
                type=ArtifactType.PLAN,
                limit=50,
            )
            # 去重: 同 summary text 近 10 分钟已有 APPROVED 就跳过
            recent_approved_summaries: set[str] = set()
            for art in store.list(
                status=ArtifactStatus.APPROVED,
                type=ArtifactType.PLAN,
                limit=30,
            ):
                s = (art.summary or "")[:80].strip()
                if s:
                    recent_approved_summaries.add(s)

            for art in pending:
                if auto_approved >= cap:
                    break
                risk = getattr(art, "risk_level", "") or ""
                conf = getattr(art, "confidence", 0) or 0
                tags = getattr(art, "tags", []) or []
                is_auto = "auto_generated" in tags or "continuous_cognition" in tags
                is_low = risk.upper() in ("LOW", "")
                is_conf_ok = conf >= 0.55
                summary_key = (art.summary or "")[:80].strip()

                if is_auto and is_low and is_conf_ok and summary_key not in recent_approved_summaries:
                    store.review(
                        art.artifact_id, ArtifactStatus.APPROVED,
                        reviewer="auto_pump",
                        comment=f"B1 auto-approve (LOW risk, conf={conf:.2f})",
                    )
                    recent_approved_summaries.add(summary_key)
                    auto_approved += 1
                    logger.info("🧠 Auto-approved artifact %s (conf=%.2f, risk=%s)",
                                art.artifact_id[:8], conf, risk)
        except Exception:
            logger.exception("pump step 1 (auto-approve) failed")

        # ── Step 2: APPROVED plans → goals 表 ──
        goals_created = 0
        try:
            import sqlite3
            db = sqlite3.connect(self._db_path)
            db.row_factory = sqlite3.Row

            approved_null_applied = db.execute("""
                SELECT artifact_id, title, summary, content, confidence
                FROM evolution_artifacts
                WHERE type='plan' AND status='approved'
                  AND (applied_at IS NULL OR applied_at = '')
                  AND (risk_level IN ('LOW', '') OR risk_level IS NULL)
                ORDER BY rowid ASC LIMIT ?""", (cap,)).fetchall()

            for row in approved_null_applied:
                aid = row["artifact_id"]
                title = row["title"] or f"Evolution plan {aid[:8]}"
                summary = row["summary"] or ""
                desc = f"{title}\n\n{summary[:200]}"   # 写入 goals 的 description

                # 精确去重: 查 goals.metadata 里的 artifact_id（而非 title LIKE）
                dup = db.execute(
                    "SELECT id, status FROM goals WHERE metadata LIKE ? LIMIT 1",
                    (f"%\"artifact_id\": \"{aid}\"%",)).fetchone()
                if dup:
                    logger.info("Pump: skip duplicate goal for artifact %s "
                                "(goal=%s status=%s) — mark applied",
                                aid[:8], dup["id"], dup["status"])
                    store.mark_applied(aid)   # FIX: skip 也要标记已处理
                    goals_created += 0         # 不占 cap 但记一次处理
                    continue

                # 写入 goals 表 (PENDING, source=evolution_artifact)
                db.execute("""
                    INSERT OR IGNORE INTO goals
                    (id, level, description, status, source, priority,
                     created_at, updated_at, metadata)
                    VALUES (?, 'AUTO', ?, 'PENDING', 'evolution_artifact', ?,
                            datetime('now'), datetime('now'), ?)
                """, (
                    f"EVO-GOAL-{aid[:8]}",
                    desc,
                    min(2.0, (row["confidence"] or 0.5) * 2 + 0.5),
                    json.dumps({
                        "artifact_id": aid,
                        "confidence": row["confidence"],
                        "autonomous": True,
                    }),
                ))
                db.commit()

                # 标记 artifact applied
                store.mark_applied(aid)
                goals_created += 1
                logger.info("🚀 Artifact %s → goal (id=EVO-GOAL-%s)", aid[:8], aid[:8])

            db.close()
        except Exception:
            logger.exception("pump step 2 (adopt as goals) failed")

        if auto_approved or goals_created:
            logger.info("🧠 Pump: auto_approved=%d, goals_created=%d",
                        auto_approved, goals_created)
        return auto_approved + goals_created

    def _claim_persisted_goals(self) -> int:
        """UX-1: 认领 goals 表中 CLI 创建的 PENDING 人类目标。

        每 tick 最多认领 1 个（与队列同款节流）。认领 = goals 表置 ACTIVE
        （防重复），内容写入 runtime._goal_store 供 Step 6 分解消费。
        V1 闭环: 无 HUMAN 待领时认领已批准的自主目标（SELF + approved，
        LEVEL>=1 门控 — 批准即 authority，LEVEL=0 仍全程静默）。
        """
        if self._domain_goal_store is None:
            return 0
        try:
            claimed = self._domain_goal_store.claim_pending_human(limit=1)
            if not claimed:
                from ocos.execution.autonomy import can_autonomous_execute, can_propose
                if can_autonomous_execute():
                    # LEVEL>=2 低风险自主执行 — goals_table 直写提案
                    # （无 approved 标记）也可认领
                    claimed = self._domain_goal_store.claim_pending_approved_self(
                        limit=1, require_approved=False)
                elif can_propose():
                    # LEVEL>=1 — 仅认已批准（人工/自动通过）的自主目标
                    claimed = self._domain_goal_store.claim_pending_approved_self(
                        limit=1, require_approved=True)
        except Exception:
            logger.exception("Goal claim failed")
            return 0
        for row in claimed:
            src_channel = row.get("source") or "daemon"
            metadata = row.get("metadata")
            if isinstance(metadata, str):
                try:
                    metadata = json.loads(metadata)
                except ValueError:
                    metadata = {}
            _fallback_domain = self._classify_goal_domain(
                row.get("description", ""))
            domain = ((metadata or {}).get("domain", _fallback_domain)
                      if isinstance(metadata, dict) else _fallback_domain)
            is_autonomous = (isinstance(metadata, dict)
                             and bool(metadata.get("autonomous")))
            if is_autonomous:
                # L3: 自主目标入在途队列（FIFO 近似配对 goal_result，
                # 驱动防跑飞连续失败计数）
                self._autonomous_inflight.append(row["id"])
            if self._import_goal(description=row.get("description", ""),
                                 domain=domain, goal_id=row["id"],
                                 caller="motivation" if is_autonomous else src_channel,
                                 self_origin=is_autonomous):
                self._goal_processed += 1
                logger.info("Claimed persisted goal: %s (domain=%s, autonomous=%s)",
                            row["id"], domain, is_autonomous)
                # P1 执行可见性（2026-09-08 用户反馈"不知道后台是在做还是
                # 断了"）: 认领即发 progress 出站消息 — 执行起点在 TUI/
                # WebUI 对话流可见（执行窗口常短于前端 6s 轮询，仅靠
                # feed 活动徽章会错过起点，此消息为可靠锚点）
                if self._user_inbox is not None:
                    try:
                        self._user_inbox.post_outbound(
                            f"⟳ 已认领目标 {row['id']}："
                            f"{row.get('description', '')[:80]}\n"
                            f"（domain={domain}，"
                            f"{'自主' if is_autonomous else '人工'}目标 — "
                            f"执行完成后结果自动回推本对话）",
                            kind="progress")
                    except Exception:
                        logger.debug("claim progress outbound failed",
                                     exc_info=True)
        return len(claimed)
