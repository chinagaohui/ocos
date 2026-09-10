"""Phase 51.1: LifecycleManager — OCOS 启动/运行/关闭/恢复生命周期。

管理完整的生命循环:
    COLD_BOOT → WARM_BOOT → RUNNING → CHECKPOINTING → SHUTTING_DOWN
    CRASHED → RECOVERY → WARM_BOOT → RUNNING
    
关键原则:
    - 正常关闭时自动保存最终快照
    - 异常终止后下次启动自动恢复
    - 运行时周期性 Checkpoint
    - DEGRADED 模式允许部分域恢复
"""

from __future__ import annotations

import signal
import sys
from dataclasses import dataclass, field
from typing import Any, Callable

from ocos.persistence.storage_types import (
    Snapshot, LifecyclePhase, LifecycleEvent, LifecycleLog,
    RecoveryState, RecoveryOutcome,
)
from ocos.persistence.snapshot_manager import SnapshotManager
from ocos.persistence.recovery_manager import RecoveryManager


@dataclass
class LifecycleManager:
    """OCOS 生命周期管理器。

    用法:
        lm = LifecycleManager(snapshot_manager, recovery_manager)
        lm.boot()             # 冷启动或恢复
        lm.run(...)           # 运行循环
        # on shutdown or signal:
        lm.shutdown()         # 保存最终快照
    """

    snapshot_manager: SnapshotManager = field(default_factory=SnapshotManager)
    recovery_manager: RecoveryManager = field(default_factory=RecoveryManager)
    log: LifecycleLog = field(default_factory=LifecycleLog)
    current_phase: LifecyclePhase = LifecyclePhase.COLD_BOOT
    current_tick: int = 0

    # Checkpoint 配置
    checkpoint_interval: int = 1000       # 每 N tick 自动 checkpoint
    checkpoint_on_pause: bool = True      # idle 超过阈值时 checkpoint
    pause_threshold_ticks: int = 100      # idle 阈值
    max_snapshots: int = 20               # 保留最大快照数

    # 运行时引用
    _tick_counter: int = 0
    _tick_fn: Callable[[], Any] | None = None
    _cleanup_fns: list[Callable[[], None]] = field(default_factory=list)

    # ── Boot ──

    def boot(self) -> RecoveryState:
        """启动 OCOS: 尝试从快照恢复。"""
        self._record(LifecyclePhase.COLD_BOOT, "Starting boot sequence")

        result = self.recovery_manager.cold_boot()
        self.current_phase = self.recovery_manager.get_phase(result)
        self.current_tick = result.tick_at_recovery

        if self.current_phase == LifecyclePhase.WARM_BOOT:
            self._record(LifecyclePhase.WARM_BOOT,
                         f"Recovered at tick {result.tick_at_recovery}, "
                         f"snapshot age: {result.age_seconds:.0f}s")
        elif self.current_phase == LifecyclePhase.DEGRADED:
            self._record(LifecyclePhase.DEGRADED,
                         f"Partial recovery: {len(result.recovered_domains)} domains, "
                         f"{len(result.failed_domains)} failed")
        else:
            self._record(LifecyclePhase.COLD_BOOT, "Fresh start — no snapshot found")

        # 注册信号处理
        self._register_signals()

        return result

    # ── Run ──

    def run(self, tick_fn: Callable[[], Any]) -> None:
        """运行主循环。"""
        self._tick_fn = tick_fn
        self._record(LifecyclePhase.RUNNING, f"Entering run loop at tick {self.current_tick}")
        self.current_phase = LifecyclePhase.RUNNING

    def add_cleanup(self, fn: Callable[[], None]) -> None:
        """注册关闭时调用的清理函数。"""
        self._cleanup_fns.append(fn)

    # ── Shutdown ──

    def shutdown(self, reason: str = "normal") -> Snapshot | None:
        """正常关闭: 保存最终快照。"""
        self.current_phase = LifecyclePhase.SHUTTING_DOWN
        self._record(LifecyclePhase.SHUTTING_DOWN, reason)

        # 执行清理
        for fn in self._cleanup_fns:
            try:
                fn()
            except Exception:
                pass

        # 保存最终快照
        snapshot = self.snapshot_manager.take_and_save(
            self.current_tick,
            reason=f"shutdown: {reason}",
        )
        self._record(LifecyclePhase.SHUTTING_DOWN,
                     f"Final snapshot saved: {snapshot.snapshot_id}")

        return snapshot

    def crash(self, reason: str = "") -> None:
        """异常终止: 尝试紧急保存。"""
        self.current_phase = LifecyclePhase.CRASHED
        self._record(LifecyclePhase.CRASHED, reason or "unknown crash")

    # ── Checkpoint ──

    def checkpoint(self, reason: str = "auto") -> Snapshot | None:
        """运行时检查点。"""
        self._record(LifecyclePhase.CHECKPOINTING, reason)
        snapshot = self.snapshot_manager.take_and_save(self.current_tick, reason)

        # 清理旧快照
        self.snapshot_manager.serializer.prune(keep=self.max_snapshots)

        self._record(LifecyclePhase.RUNNING,
                     f"Checkpoint done: {snapshot.snapshot_id}")
        return snapshot

    # ── Health ──

    @property
    def is_healthy(self) -> bool:
        return self.current_phase in (
            LifecyclePhase.RUNNING, LifecyclePhase.WARM_BOOT,
        )

    @property
    def is_degraded(self) -> bool:
        return self.current_phase == LifecyclePhase.DEGRADED

    @property
    def boot_count(self) -> int:
        return self.log.boot_count

    # ── Internal ──

    def _record(self, phase: LifecyclePhase, detail: str) -> None:
        from time import time
        evt = LifecycleEvent(
            event_id=f"life-{len(self.log.events):04d}",
            phase=phase,
            timestamp=time(),
            tick=self.current_tick,
            detail=detail,
        )
        self.log.events.append(evt)
        self.log.current_phase = phase
        if phase == LifecyclePhase.WARM_BOOT:
            self.log.boot_count += 1

    def _register_signals(self) -> None:
        """注册 SIGINT/SIGTERM 处理。

        FIX-CROSS-TEST: 不在 handler 里 sys.exit(0) — 会污染 pytest 进程
        （pytest timeout 发 SIGTERM → 整个测试进程 exit）。daemon 主循环
        应该从 shutdown 返回后自行终止。handler 只做清理，不强制退出。
        """
        def handler(signum, frame):
            self.shutdown(f"signal {signum}")
            # 只设事件让主循环退出，不硬退出进程
        try:
            signal.signal(signal.SIGINT, handler)
            signal.signal(signal.SIGTERM, handler)
        except (ValueError, OSError):
            pass  # 非主线程无法注册


__all__ = ["LifecycleManager"]
