"""Phase M: RuntimeLoop — OCOS 运行时主循环抽象层。

RuntimeLoop 是 OCOS 的"心脏起搏器"，将生命周期管理、tick 驱动、
事件循环统一封装为可独立测试的模块。

设计原则:
  - 不替代 ResidentRuntime（daemon 包装层），而是提供底层循环引擎
  - 支持同步/异步双模式
  - 心跳、检查点、恢复逻辑内聚
  - 外部注入 hook（per-tick callback）保持 Kernel 纯净

用法:
  # 同步模式
  loop = RuntimeLoop(runtime, interval=5.0)
  loop.start()
  loop.run_for(1000)  # 跑 1000 tick
  loop.stop()

  # 异步模式
  async with RuntimeLoop(runtime, interval=5.0) as loop:
      await loop.run_forever()
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from contextlib import asynccontextmanager, contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum, auto
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class LoopState(Enum):
    """运行时循环状态。"""
    STOPPED = auto()
    STARTING = auto()
    RUNNING = auto()
    PAUSING = auto()
    PAUSED = auto()
    STOPPING = auto()


@dataclass
class LoopMetrics:
    """循环运行指标。"""
    started_at: Optional[float] = None
    stopped_at: Optional[float] = None
    total_ticks: int = 0
    failed_ticks: int = 0
    last_tick_id: int = 0
    last_tick_timestamp: Optional[datetime] = None
    avg_tick_duration_ms: float = 0.0
    _tick_durations: list[float] = field(default_factory=list)

    @property
    def uptime_seconds(self) -> float:
        if self.started_at is None:
            return 0.0
        end = self.stopped_at or time.time()
        return end - self.started_at

    @property
    def ticks_per_second(self) -> float:
        uptime = self.uptime_seconds
        if uptime <= 0:
            return 0.0
        return self.total_ticks / uptime

    def record_tick(self, duration_ms: float, tick_id: int, timestamp: datetime):
        self.total_ticks += 1
        self.last_tick_id = tick_id
        self.last_tick_timestamp = timestamp
        self._tick_durations.append(duration_ms)
        # 保留最近 100 次用于滑动平均
        if len(self._tick_durations) > 100:
            self._tick_durations = self._tick_durations[-100:]
        if self._tick_durations:
            self.avg_tick_duration_ms = sum(self._tick_durations) / len(self._tick_durations)


class RuntimeLoop:
    """OCOS 运行时主循环引擎。

    负责:
    - 启动/停止循环线程
    - 每 tick 调用 runtime.tick()
    - 周期性指标记录
    - 外部 hook 注入（per-tick / on-start / on-stop）
    """

    def __init__(
        self,
        runtime: Any,
        interval: float = 1.0,
        max_ticks: int = 0,  # 0 = 无限
        name: str = "ocos-runtime-loop",
    ) -> None:
        self._runtime = runtime
        self._interval = interval
        self._max_ticks = max_ticks
        self._name = name

        self._state = LoopState.STOPPED
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._pause_event = threading.Event()
        self._pause_event.set()  # 默认未暂停
        self._lock = threading.RLock()

        # Hooks
        self._on_start: Optional[Callable[["RuntimeLoop"], None]] = None
        self._on_stop: Optional[Callable[["RuntimeLoop"], None]] = None
        self._on_tick: Optional[Callable[[int, dict[str, Any]], None]] = None
        self._on_error: Optional[Callable[[int, Exception], None]] = None

        # Metrics
        self._metrics = LoopMetrics()
        self._tick_counter = 0

    # ── Public API ────────────────────────────────────────────────────────

    @property
    def state(self) -> LoopState:
        return self._state

    @property
    def metrics(self) -> LoopMetrics:
        return self._metrics

    @property
    def name(self) -> str:
        return self._name

    def start(self) -> "RuntimeLoop":
        """启动循环（线程模式）。"""
        with self._lock:
            if self._state == LoopState.RUNNING:
                logger.warning("Loop %s already running", self._name)
                return self
            if self._state == LoopState.STARTING:
                return self
            self._state = LoopState.STARTING
            self._stop_event.clear()
            self._pause_event.set()

        # 启动线程
        self._thread = threading.Thread(
            target=self._run_sync_loop,
            name=f"{self._name}-thread",
            daemon=True,
        )
        self._thread.start()

        with self._lock:
            self._state = LoopState.RUNNING
            self._metrics.started_at = time.time()
            if self._on_start:
                try:
                    self._on_start(self)
                except Exception as e:
                    logger.warning("on_start hook failed: %s", e)
            logger.info("Loop %s started (interval=%.2fs, max_ticks=%d)",
                       self._name, self._interval, self._max_ticks)
        return self

    def stop(self, timeout: float = 30.0) -> bool:
        """停止循环。返回 True 若成功停止。"""
        with self._lock:
            if self._state not in (LoopState.RUNNING, LoopState.PAUSED):
                logger.debug("Loop %s not running (state=%s)", self._name, self._state.name)
                return True
            self._state = LoopState.STOPPING

        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=timeout)

        stopped = not self._thread or not self._thread.is_alive()
        with self._lock:
            if stopped:
                self._state = LoopState.STOPPED
                self._metrics.stopped_at = time.time()
                if self._on_stop:
                    try:
                        self._on_stop(self)
                    except Exception as e:
                        logger.warning("on_stop hook failed: %s", e)
                logger.info("Loop %s stopped. ticks=%d failed=%d uptime=%.1fs",
                           self._name, self._metrics.total_ticks,
                           self._metrics.failed_ticks, self._metrics.uptime_seconds)
            else:
                logger.error("Loop %s did not stop within %.1fs", self._name, timeout)
        return stopped

    def run_for(self, ticks: int, timeout: float = 0.0) -> LoopMetrics:
        """同步运行指定 tick 数（阻塞调用）。"""
        if ticks <= 0:
            return self._metrics

        # 临时设置 max_ticks 并同步执行
        original_max = self._max_ticks
        self._max_ticks = ticks

        with self._lock:
            if self._state != LoopState.STOPPED:
                raise RuntimeError(f"Cannot run_for while loop is {self._state.name}")
            self._state = LoopState.STARTING
            self._stop_event.clear()
            self._pause_event.set()
            self._metrics.started_at = time.time()
            if self._on_start:
                try:
                    self._on_start(self)
                except Exception as e:
                    logger.warning("on_start hook failed: %s", e)

        try:
            self._run_sync_loop()
        finally:
            self._max_ticks = original_max
            with self._lock:
                self._state = LoopState.STOPPED
                self._metrics.stopped_at = time.time()
                if self._on_stop:
                    try:
                        self._on_stop(self)
                    except Exception as e:
                        logger.warning("on_stop hook failed: %s", e)
        return self._metrics

    def pause(self) -> None:
        """暂停循环（不终止线程）。"""
        with self._lock:
            if self._state == LoopState.RUNNING:
                self._state = LoopState.PAUSING
        self._pause_event.clear()
        with self._lock:
            self._state = LoopState.PAUSED
            logger.info("Loop %s paused", self._name)

    def resume(self) -> None:
        """恢复循环。"""
        with self._lock:
            if self._state == LoopState.PAUSED:
                self._state = LoopState.PAUSING
        self._pause_event.set()
        with self._lock:
            self._state = LoopState.RUNNING
            logger.info("Loop %s resumed", self._name)

    # ── Async API ─────────────────────────────────────────────────────────

    @contextmanager
    def sync_context(self):
        """同步上下文管理器。"""
        self.start()
        try:
            yield self
        finally:
            self.stop()

    @asynccontextmanager
    async def async_context(self):
        """异步上下文管理器。"""
        await self.async_start()
        try:
            yield self
        finally:
            await self.async_stop()

    async def async_start(self) -> "RuntimeLoop":
        """异步启动（使用 asyncio 事件循环）。"""
        if self._state == LoopState.RUNNING:
            return self
        self._state = LoopState.STARTING
        self._metrics.started_at = time.time()
        if self._on_start:
            try:
                self._on_start(self)
            except Exception as e:
                logger.warning("on_start hook failed: %s", e)
        logger.info("Async loop %s started", self._name)
        self._state = LoopState.RUNNING
        return self

    async def async_stop(self) -> bool:
        """异步停止。"""
        self._stop_event.set()
        if self._state == LoopState.RUNNING:
            self._state = LoopState.STOPPING
            self._metrics.stopped_at = time.time()
            if self._on_stop:
                try:
                    self._on_stop(self)
                except Exception as e:
                    logger.warning("on_stop hook failed: %s", e)
            self._state = LoopState.STOPPED
            logger.info("Async loop %s stopped", self._name)
        return True

    async def async_run(self, max_ticks: int | None = None,
                        interval: float | None = None) -> LoopMetrics:
        """异步运行循环。"""
        await self.async_start()
        try:
            limit = max_ticks or self._max_ticks
            count = 0
            while self._state == LoopState.RUNNING:
                if limit is not None and count >= limit:
                    break
                await self._async_tick()
                count += 1
                if interval and interval > 0:
                    await asyncio.sleep(interval)
        finally:
            await self.async_stop()
        return self._metrics

    # ── Hook registration ─────────────────────────────────────────────────

    def on_start(self, fn: Callable[["RuntimeLoop"], None]) -> "RuntimeLoop":
        """注册启动回调。"""
        self._on_start = fn
        return self

    def on_stop(self, fn: Callable[["RuntimeLoop"], None]) -> "RuntimeLoop":
        """注册停止回调。"""
        self._on_stop = fn
        return self

    def on_tick(self, fn: Callable[[int, dict[str, Any]], None]) -> "RuntimeLoop":
        """注册每 tick 回调 (tick_id, result)。"""
        self._on_tick = fn
        return self

    def on_error(self, fn: Callable[[int, Exception], None]) -> "RuntimeLoop":
        """注册错误回调 (tick_id, exception)。"""
        self._on_error = fn
        return self

    # ── Internal ──────────────────────────────────────────────────────────

    def _run_sync_loop(self) -> None:
        """同步主循环实现。"""
        while not self._stop_event.is_set():
            # 检查暂停
            if not self._pause_event.wait(timeout=self._interval):
                continue

            tick_start = time.perf_counter()
            try:
                result = self._runtime.tick()
                tick_duration = (time.perf_counter() - tick_start) * 1000  # ms
                self._tick_counter += 1
                self._metrics.record_tick(
                    tick_duration, self._tick_counter,
                    datetime.now(timezone.utc),
                )
                if self._on_tick:
                    try:
                        self._on_tick(self._tick_counter, result or {})
                    except Exception as e:
                        logger.warning("on_tick hook failed: %s", e)
            except Exception as e:
                self._metrics.failed_ticks += 1
                logger.error("Tick %d failed: %s", self._tick_counter, e, exc_info=True)
                if self._on_error:
                    try:
                        self._on_error(self._tick_counter, e)
                    except Exception:
                        pass
                # 失败后短暂等待再重试
                time.sleep(max(0.1, self._interval * 0.1))
                continue

            # 检查 max_ticks
            if self._max_ticks > 0 and self._tick_counter >= self._max_ticks:
                break

            # 休眠
            if self._interval > 0 and not self._stop_event.wait(timeout=self._interval):
                continue

    async def _async_tick(self) -> None:
        """异步单次 tick。"""
        tick_start = time.perf_counter()
        try:
            result = self._runtime.tick()
            tick_duration = (time.perf_counter() - tick_start) * 1000
            self._tick_counter += 1
            self._metrics.record_tick(tick_duration, self._tick_counter,
                                      datetime.now(timezone.utc))
            if self._on_tick:
                try:
                    self._on_tick(self._tick_counter, result or {})
                except Exception as e:
                    logger.warning("on_tick hook failed: %s", e)
        except Exception as e:
            self._metrics.failed_ticks += 1
            logger.error("Async tick %d failed: %s", self._tick_counter, e, exc_info=True)
            if self._on_error:
                try:
                    self._on_error(self._tick_counter, e)
                except Exception:
                    pass


# ── Factory ─────────────────────────────────────────────────────────────

def create_runtime_loop(
    runtime: Any,
    interval: float = 1.0,
    max_ticks: int = 0,
    name: str = "ocos-loop",
) -> RuntimeLoop:
    """工厂函数：创建 RuntimeLoop 实例。"""
    return RuntimeLoop(
        runtime=runtime,
        interval=interval,
        max_ticks=max_ticks,
        name=name,
    )
