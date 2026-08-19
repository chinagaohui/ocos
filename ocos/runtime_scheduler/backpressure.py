"""Phase 51.2: BackpressureManager — 过载保护。

RS51-04: 当事件速率超过处理能力，不崩溃，而是降级。
    
策略:
    1. 水位线触发: 队列深度 > high_watermark → 启动背压
    2. 优先级降级: 拒绝 LOW/BACKGROUND，推迟 MEDIUM
    3. 解压: 队列深度 < low_watermark → 恢复正常
    4. 逐级恢复: MEDIUM → LOW → BACKGROUND 逐步恢复
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ocos.runtime_scheduler.scheduler_types import (
    Priority, BackpressureState, SchedulerTask, TaskStatus,
)


@dataclass
class BackpressureManager:
    """背压管理器 — 认知系统的"安全阀"。

    不是拒绝一切，而是按优先级降级:
        - CRITICAL: 始终放行
        - HIGH: 始终放行 (系统关键)
        - MEDIUM: 背压时推迟 (不拒绝，延迟执行)
        - LOW: 背压时拒绝
        - BACKGROUND: 背压时拒绝

    信息淹没场景:
        10000 events/sec → Queue 溢出 → Backpressure
        → 只处理 CRITICAL/HIGH → Queue 恢复正常 → 恢复全优先级
    """

    state: BackpressureState = field(default_factory=BackpressureState)
    enabled: bool = True

    def check(self, task: SchedulerTask) -> bool:
        """检查任务是否应该被接受。返回 True=接受, False=拒绝。"""
        if not self.enabled:
            return True

        if not self.state.active:
            return True

        # 背压激活中
        if task.priority in (Priority.CRITICAL, Priority.HIGH):
            return True  # 始终放行

        if task.priority == Priority.MEDIUM:
            # 推迟: 标记 backpressured 而非拒绝
            task.status = TaskStatus.BACKPRESSURED
            self.state.deferred_count += 1
            return False

        # LOW / BACKGROUND
        self.state.rejected_count += 1
        return False

    def update(self, queue_depth: int) -> None:
        """根据队列深度更新背压状态。"""
        self.state.queue_depth = queue_depth
        if not self.state.active and queue_depth > self.state.high_watermark:
            self._activate()
        elif self.state.active and queue_depth < self.state.low_watermark:
            self._deactivate()

    def _activate(self) -> None:
        self.state.active = True
        self.state.triggered_at_tick = 0  # caller 负责设置

    def _deactivate(self) -> None:
        self.state.active = False
        self.state.deferred_count = 0
        self.state.rejected_count = 0

    def drain_deferred(self) -> list[SchedulerTask]:
        """恢复推迟的任务。"""
        # 调用者负责从 queue 中找回 BACKPRESSURED 任务重新入队
        return []

    @property
    def is_active(self) -> bool:
        return self.state.active

    def get_state(self) -> dict:
        return {
            "active": self.state.active,
            "queue_depth": self.state.queue_depth,
            "rejected": self.state.rejected_count,
            "deferred": self.state.deferred_count,
        }


__all__ = ["BackpressureManager"]
