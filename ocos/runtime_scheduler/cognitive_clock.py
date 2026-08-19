"""Phase 51.2: CognitiveClock — tick 编号、时间推进、周期任务。

RS51-02: 保证 tick 连续、无重复、无丢失。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from ocos.runtime_scheduler.scheduler_types import Tick, TickSchedule, Priority


@dataclass
class CognitiveClock:
    """认知时钟 — OCOS 的心跳。

    tick 是认知活动的基本时间单位:
        - 每次 tick 触发一次认知循环
        - tick 从 0 开始，单调递增
        - RS51-02: 连续、不可变、不可回退
    """

    current: Tick = field(default_factory=lambda: Tick(0))
    start_tick: Tick = field(default_factory=lambda: Tick(0))
    schedules: list[TickSchedule] = field(default_factory=list)
    on_tick: Callable[[Tick], None] | None = None  # tick 回调

    @property
    def elapsed(self) -> int:
        """从启动以来经过的 tick 数。"""
        return self.current - self.start_tick

    def advance(self) -> Tick:
        """前进一个 tick。RS51-02: 不会跳号。"""
        self.current = self.current + 1
        if self.on_tick:
            self.on_tick(self.current)
        return self.current

    def advance_n(self, n: int) -> list[Tick]:
        """前进 N 个 tick。返回所有跳过的 tick。"""
        ticks = []
        for _ in range(n):
            ticks.append(self.advance())
        return ticks

    # ── 周期任务 ──

    def register_schedule(self, schedule: TickSchedule) -> None:
        """注册周期性任务。"""
        self.schedules.append(schedule)

    def due_schedules(self, tick: Tick | None = None) -> list[TickSchedule]:
        """返回当前 tick 应执行的周期任务。"""
        t = tick or self.current
        due = []
        for s in self.schedules:
            if s.should_run(t.number):
                due.append(s)
        return due

    def mark_completed(self, schedule: TickSchedule, tick: Tick | None = None) -> None:
        """标记周期任务已在该 tick 执行。"""
        t = tick or self.current
        schedule.last_run = t.number

    # ── 状态 ──

    def reset(self) -> None:
        """重置时钟 (仅用于测试)。"""
        self.current = Tick(0)
        self.start_tick = Tick(0)
        for s in self.schedules:
            s.last_run = -1


__all__ = ["CognitiveClock"]
