"""Phase 33: ResidentRuntime — 常驻模式 daemon wrapper。

用法:
  from ocos.daemon.resident_runtime import ResidentRuntime
  rt = ResidentRuntime(agent, tick_interval=5.0)
  rt.start()
  rt.submit_goal("设计秒杀系统", domain=GoalDomain.DEVELOPMENT)
  # ... daemon 在后台每 5s tick 一次，自动分解+执行+记忆回写 ...
  rt.stop()

线程模型:
  - _tick_thread: 定时触发 AgentRuntime.tick()
  - 目标队列: thread-safe deque，tick step 6 自动消费
  - 优雅关闭: threading.Event + 最大等待 30s
"""

from __future__ import annotations

import logging
import threading
import time
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
        tick_interval: float = 5.0,
        max_cycles: int = 10_000,
        max_idle_cycles: int = 0,
    ) -> None:
        from ocos.agent.agent_runtime import AgentRuntime
        self._runtime: AgentRuntime = AgentRuntime(
            agent=agent,
            max_cycles=max_cycles,
        )
        self._tick_interval = tick_interval
        self._max_idle_cycles = max_idle_cycles
        self._state: DaemonState = DaemonState.STOPPED
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
        return self._runtime._cycle_count

    def start(self) -> None:
        """启动 daemon — boot AgentRuntime，启动 tick 线程。"""
        with self._lock:
            if self._state != DaemonState.STOPPED:
                logger.warning("Daemon already in state %s, ignoring start.", self._state.name)
                return
            self._state = DaemonState.STARTING
            self._stop_event.clear()
            self._runtime.boot()
            self._tick_thread = threading.Thread(
                target=self._tick_loop, name="ocos-daemon", daemon=True,
            )
            self._tick_thread.start()
            self._state = DaemonState.RUNNING
            logger.info("ResidentRuntime daemon started (interval=%.1fs)", self._tick_interval)

    def stop(self, timeout: float = 30.0) -> None:
        """优雅关闭 daemon — 停止 tick 线程，不 shutdown runtime。"""
        with self._lock:
            if self._state != DaemonState.RUNNING:
                return
            self._state = DaemonState.STOPPING
        self._stop_event.set()
        if self._tick_thread:
            self._tick_thread.join(timeout=timeout)
        with self._lock:
            self._state = DaemonState.STOPPED
            logger.info("ResidentRuntime daemon stopped. %d goals processed.", self._goal_processed)

    def submit_goal(self, description: str, domain: str = "development") -> int:
        """提交目标到 daemon 队列（线程安全）。

        返回当前队列长度。
        """
        goal = QueuedGoal(description=description, domain=domain)
        with self._lock:
            self._goal_queue.append(goal)
            self._goal_submitted += 1
            n = len(self._goal_queue)
            logger.info("Goal queued: %s (domain=%s, queue=%d)", description, domain, n)
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
        """主循环 — 定时 tick，消费目标队列，直到 stop_event。"""
        while not self._stop_event.is_set():
            # Phase 33: 将队列中的目标导入 runtime 的 goal_store
            self._drain_goal_queue()

            # 执行一次 tick
            try:
                self._runtime.tick()
                self._idle_ticks = 0
            except Exception:
                logger.exception("Tick failed (cycle=%d)", self._runtime._cycle_count)

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

        try:
            from ocos.kernel.goal_types import UserGoal, GoalDomain
            domain_map = {
                "development": GoalDomain.DEVELOPMENT,
                "research": GoalDomain.RESEARCH,
                "writing": GoalDomain.WRITING,
                "analysis": GoalDomain.ANALYSIS,
            }
            domain = domain_map.get(qg.domain, GoalDomain.DEVELOPMENT)
            goal = UserGoal(
                id=f"GOAL-DAEMON-{int(time.time() * 1000)}",
                raw_input=qg.description,
                objective=qg.description,
                domain=domain,
                caller=qg.caller,
            )
            # 存入 goal_store（如果存在）
            gs = getattr(self._runtime, "_goal_store", None)
            if gs is not None and hasattr(gs, "save"):
                gs.save(goal)
            else:
                # 无 goal_store 时，直接将 goal 注册到 runtime 的内部列表
                if hasattr(self._runtime, "_pending_goals"):
                    self._runtime._pending_goals.append(goal)

            self._goal_processed += 1
            return 1
        except Exception:
            logger.exception("Failed to import queued goal: %s", qg.description)
            return 0
