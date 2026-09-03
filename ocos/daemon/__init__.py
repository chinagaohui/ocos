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
import threading
import time
from datetime import datetime, timezone
from collections import deque
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Optional

logger = logging.getLogger(__name__)


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
        # Phase B: 生命周期编排器伴生层 — 负责疲劳检测、SLEEP转换、主动输出
        self._orchestrator: Any = None
        try:
            from ocos.agent.life_cycle_orchestrator import LifeCycleOrchestrator
            self._orchestrator = LifeCycleOrchestrator(agent)
        except Exception as e:
            logger.warning("LifeCycleOrchestrator unavailable: %s", e)
        # Phase E: 自我演化监控 — 定期检查 SelfModel 是否需要演化
        self._self_monitor: Any = None
        self._self_monitor_eligible: bool = False
        try:
            from ocos.self.monitor import SelfMonitor
            from ocos.self.builder import SelfModelBuilder
            from ocos.self.governor import SelfGovernor
            from ocos.self.identity_boundary import IdentityBoundary
            belief_store = self.memory_hub.belief() if self.memory_hub else None
            if belief_store is not None:
                boundary = IdentityBoundary.create_default()
                builder = SelfModelBuilder(belief_store, boundary)
                governor = SelfGovernor(boundary)
                self._self_monitor = SelfMonitor(builder, governor, belief_store)
                self._self_monitor_eligible = True
                logger.info("SelfMonitor initialized — evolution checks enabled")
        except Exception as e:
            logger.debug("SelfMonitor unavailable (evolution passive): %s", e)
        # P1-C 循环收敛: 认知循环宿主 = RuntimeKernel（默认自建）。
        # kernel 不 import ocos.agent — AgentRuntime.tick 经 driver 注入。
        if kernel is None:
            from ocos.runtime.runtime_kernel import RuntimeKernel
            kernel = RuntimeKernel()
        self._kernel: Any = kernel
        self._health_loop: Optional[Any] = health_loop  # GAP-P1-2
        self._perception_pipeline: Optional[Any] = perception_pipeline  # AUD-F1
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
        if db_path and db_path != ":memory:":
            try:
                from ocos.interaction.inbox import UserInbox
                self._user_inbox = UserInbox(db_path=db_path)
            except Exception as e:
                logger.warning("UserInbox unavailable, say channel disabled: %s", e)
            try:
                from ocos.interaction.converse import ChatResponder
                self._responder = ChatResponder(db_path=db_path)
            except Exception as e:
                logger.warning("ChatResponder unavailable: %s", e)
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
        """
        self._perception_pipeline = pipeline
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
            # P1-C: kernel boot + agent driver 注入（每 tick 驱动 AgentRuntime.tick）。
            # restart 场景下 kernel 保持 RUNNING，start() 幂等跳过。
            if self._kernel.state.name != "RUNNING":
                self._kernel.start()
            self._kernel.attach_agent_driver(lambda tick_id: self._runtime.tick())
            self._tick_thread = threading.Thread(
                target=self._tick_loop, name="ocos-daemon", daemon=True,
            )
            self._tick_thread.start()
            self._state = DaemonState.RUNNING
            logger.info("ResidentRuntime daemon started (interval=%.1fs)", self._tick_interval)

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
            # Phase B: orchestrator 安全关闭
            try:
                if self._orchestrator is not None:
                    self._orchestrator.shutdown()
            except Exception:
                pass
            self._state = DaemonState.STOPPED
            logger.info("ResidentRuntime daemon stopped. %d goals processed.", self._goal_processed)

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
                "memory": getattr(self._runtime, "memory", None),
                "beliefs": getattr(self._runtime, "beliefs", None),
            }

    # ── Internal ──────────────────────────────────────────────────────────────

    def _tick_loop(self) -> None:
        """主循环 — 经 RuntimeKernel 定时 tick（认知循环单一宿主），消费目标队列。

        Phase B: 伴生 LifeCycleOrchestrator 负责疲劳检测 + 主动输出触发，
        不替换主认知路径（kernel.tick_loop）以避免双重重跑认知循环。
        """
        while not self._stop_event.is_set():
            # UX-F3: 心跳落盘（每 5 tick 一次, 降低写盘对 tick 时序的影响）
            self._hb_ticks += 1
            if self._hb_ticks % 5 == 0:
                try:
                    self._write_heartbeat()
                except Exception:
                    pass
            # UX-J: 目标完成 → 自动回推结果到对话流
            if self._hb_ticks % 5 == 0:
                try:
                    self._push_goal_results()
                except Exception:
                    logger.exception("goal result push failed")

            # P1-1: 周期性 dream 巩固（Episode → Belief/Pattern/Wisdom）
            if self._hb_ticks % max(1, self.dream_interval_ticks) == 0:
                try:
                    self._run_dream_cycle()
                except Exception:
                    logger.exception("Dream consolidation failed")
            # Phase 33: 将队列中的目标导入 runtime 的 goal_store
            self._drain_goal_queue()
            # UX-1: 认领 CLI 创建的持久化目标（每 tick 最多 1 个）
            self._claim_persisted_goals()
            # UX-P2: 消费用户消息（ocos say）
            self._drain_user_inbox()

            # P1-C: 一次认知 tick = kernel.tick_loop(1)（8 空壳 stage + agent driver）
            try:
                self._kernel.tick_loop(max_ticks=1)
                self._idle_ticks = 0
            except Exception:
                logger.exception("Tick failed (cycle=%d)", self._runtime._cycle_count)

            # Phase B: 伴生 orchestrator 疲劳检测 + 主动输出 — 不重跑认知循环，只做状态检查
            if self._orchestrator is not None:
                try:
                    agent_obj = getattr(self._runtime, "agent", None)
                    attention = getattr(agent_obj, "attention", None) if agent_obj is not None else None
                    if attention is not None and hasattr(attention, "needs_sleep"):
                        if attention.needs_sleep():
                            logger.info("Fatigue detected at tick %d — triggering sleep/dream", self._hb_ticks)
                            try:
                                self._run_dream_cycle()
                            except Exception:
                                logger.exception("Fatigue dream failed")
                    # 定期主动输出（每 60 tick ≈ 5min @ 5s/tick）
                    if self._hb_ticks % 60 == 0:
                        if agent_obj is not None and hasattr(agent_obj, "maybe_proactive_output"):
                            agent_obj.maybe_proactive_output()
                except Exception:
                    pass

            # Phase E: 自我演化监控 — 每 120 tick（≈10min）检查一次 SelfModel 是否需要演化
            if self._self_monitor_eligible and self._self_monitor is not None:
                try:
                    if self._hb_ticks % 120 == 0:
                        result = self._self_monitor.run_once()
                        logger.info("Self evolution check: action=%s message=%s",
                                   result.action.value, result.message)
                except Exception:
                    logger.debug("SelfMonitor tick failed", exc_info=True)

            # GAP-P1-2: 周期健康体检（HealthLoop 内部按 interval_ticks 节流）
            if self._health_loop is not None:
                try:
                    self._health_loop.tick()
                except Exception:
                    logger.exception("Health loop tick failed")

            # AUD-F1: 感知周期（无传感器时零开销零写入）
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
                     goal_id: str | None, caller: str = "daemon") -> bool:
        """构造 agent 层 Goal 并写入 runtime._goal_store（Step 6 可消费）。

        UX-1 修复: 此前构造 UserGoal 传入期望 Goal 对象的 save()
        （属性名不匹配 → AttributeError 被吞），队列目标静默丢失。
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
                origin_level=GoalOriginLevel.HUMAN,   # UX-F4: 用户目标是人类来源
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

    def _push_goal_results(self) -> None:
        """UX-J: 新 goal_result episode → 出站消息（UI 自动弹出结果）。"""
        if self._user_inbox is None:
            return
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
                "SELECT rowid, substr(decision,1,600), created_at FROM episodes "
                "WHERE tags LIKE '%goal_result%' AND rowid > ? "
                "ORDER BY rowid LIMIT 5",
                (self._last_result_rowid,)).fetchall()
        finally:
            conn.close()
        for rid, decision, created in rows:
            self._user_inbox.post_outbound(
                f"目标执行完成（{created[11:19]}）：\n{decision}")
            self._last_result_rowid = rid

    def _run_dream_cycle(self) -> None:
        """P1-1: 完整睡眠巩固序列 — 修复生命周期相位后 sleep→dream。

        此前直接调 dream() 会因 lifecycle 处于 BOOTING 而抛
        "Cannot transition BOOTING to DREAMING"（合法路径要求
        BOOTING→ACTIVE→SLEEPING→DREAMING），巩固管线从未运转。
        """
        agent_obj = getattr(self._runtime, "agent", None)
        if agent_obj is None or not hasattr(agent_obj, "dream"):
            return
        from ocos.agent.lifecycle import LifecyclePhase
        cl = getattr(agent_obj, "_control_loop", None)
        if cl is not None:
            lc = getattr(cl, "_lifecycle", None)
            phase = getattr(lc, "phase", None)
            if phase == LifecyclePhase.BOOTING:
                # BOOTING → ACTIVE（合法迁移，tick 一直在跑本就处于活跃态）
                lc.transition_to_phase(LifecyclePhase.ACTIVE)
        agent_obj.sleep()    # ACTIVE → SLEEPING（WM 巩固 + 持久化）
        out = agent_obj.dream()   # SLEEPING → DREAMING → 巩固 → wake
        logger.info("Dream consolidation: wisdom_total=%s consolidation=%s",
                    (out.get("wisdom_stats") or {}).get("wisdom_total", "?"),
                    out.get("consolidation_stats", {}))

    def _write_heartbeat(self) -> None:
        """UX-F3: 每 tick 写心跳文件（Web 侧栏/状态命令判断存活）。"""
        import json
        from pathlib import Path
        hb = Path.home() / ".ocos" / "daemon_heartbeat.json"
        hb.parent.mkdir(parents=True, exist_ok=True)
        hb.write_text(json.dumps({
            "pid": os.getpid(),
            "cycle": getattr(self._runtime, "_cycle_count", 0),
            "ts": datetime.now(timezone.utc).isoformat(),
        }), encoding="utf-8")

    def _drain_user_inbox(self) -> int:
        """UX-P2: 消费收件箱中的用户消息 → 感知事件（Step 1 下一 tick 摄入）。"""
        if self._user_inbox is None:
            return 0
        try:
            messages = self._user_inbox.drain(limit=3)
        except Exception:
            logger.exception("UserInbox drain failed")
            return 0
        for msg in messages:
            result = self._runtime.inject_user_message(
                msg["content"], sender=msg["sender"])
            if result.get("accepted"):
                logger.info("User message delivered: %s (%s)",
                            msg["id"], msg["content"][:40])
            else:
                logger.warning("User message inject failed: %s — %s",
                               msg["id"], result.get("error"))
            # R1: 生成并回写自然语言回复（say --wait 的取回点）
            if self._responder is not None:
                try:
                    out = self._responder.respond(msg["content"])
                    self._user_inbox.reply(msg["id"], out["reply"])
                    logger.info("Reply written: %s (provider=%s)",
                                msg["id"], out["provider"])
                except Exception:
                    logger.exception("Reply generation failed for %s", msg["id"])
        return len(messages)

    def _claim_persisted_goals(self) -> int:
        """UX-1: 认领 goals 表中 CLI 创建的 PENDING 人类目标。

        每 tick 最多认领 1 个（与队列同款节流）。认领 = goals 表置 ACTIVE
        （防重复），内容写入 runtime._goal_store 供 Step 6 分解消费。
        """
        if self._domain_goal_store is None:
            return 0
        try:
            claimed = self._domain_goal_store.claim_pending_human(limit=1)
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
            domain = (metadata or {}).get("domain", "writing") if isinstance(metadata, dict) else "writing"
            if self._import_goal(description=row.get("description", ""),
                                 domain=domain, goal_id=row["id"],
                                 caller=src_channel):
                self._goal_processed += 1
                logger.info("Claimed persisted goal: %s (domain=%s)",
                            row["id"], domain)
        return len(claimed)
