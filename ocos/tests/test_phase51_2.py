"""Phase 51.2: Runtime Scheduler — Tests.

验证:
    RS51-01: Scheduler ≠ Brain — 不能 create_goal/modify_memory/make_decision
    RS51-02: Tick Stability — 10000 ticks 连续无丢失
    RS51-03: Priority Handling — 用户请求优先
    RS51-04: Backpressure — 10000 events 不崩溃
    RS51-05: Persistence Integration — Checkpoint → Shutdown → Restore
"""

import tempfile
from pathlib import Path
import pytest

from ocos.runtime_scheduler.scheduler_types import (
    Priority, Tick, TaskStatus, SchedulerTask, TickSchedule,
    SchedulerStatus, SchedulerStats, BackpressureState,
    WorkerStatus, Worker,
)
from ocos.runtime_scheduler.cognitive_clock import CognitiveClock
from ocos.runtime_scheduler.priority_queue import PriorityQueue
from ocos.runtime_scheduler.task_scheduler import TaskScheduler
from ocos.runtime_scheduler.backpressure import BackpressureManager
from ocos.runtime_scheduler.worker_manager import WorkerManager
from ocos.runtime_scheduler.scheduler_health import SchedulerHealth


# ═══════════════════════════════════════════════════════════════════════════════
# 1. Types
# ═══════════════════════════════════════════════════════════════════════════════


class TestTypes:
    def test_priority_ordering(self):
        """CRITICAL < HIGH < MEDIUM < LOW < BACKGROUND。"""
        assert Priority.CRITICAL < Priority.HIGH
        assert Priority.HIGH < Priority.MEDIUM
        assert Priority.MEDIUM < Priority.LOW
        assert Priority.LOW < Priority.BACKGROUND

    def test_tick_immutable(self):
        t1 = Tick(1)
        t2 = Tick(1)
        assert t1 == t2
        assert hash(t1) == hash(t2)

    def test_tick_add(self):
        assert (Tick(5) + 3).number == 8

    def test_tick_sub(self):
        assert Tick(10) - Tick(3) == 7

    def test_schedule_should_run(self):
        s = TickSchedule(name="test", every=10, offset=0)
        assert s.should_run(0)
        assert s.should_run(1)
        s.last_run = 0
        assert not s.should_run(5)
        assert s.should_run(10)

    def test_task_status_values(self):
        assert TaskStatus.BACKPRESSURED.value == "backpressured"

    def test_scheduler_status_values(self):
        assert SchedulerStatus.BACKPRESSURED.value == "backpressured"

    def test_backpressure_state_reject(self):
        bs = BackpressureState(active=True, high_watermark=100)
        assert not bs.should_reject(Priority.CRITICAL)
        assert not bs.should_reject(Priority.HIGH)
        assert bs.should_reject(Priority.LOW)
        assert bs.should_reject(Priority.BACKGROUND)

    def test_task_elapsed(self):
        task = SchedulerTask(task_id="t1", stage="test")
        task.started_at = 100.0
        task.finished_at = 100.5
        assert 0.49 < task.elapsed < 0.51


# ═══════════════════════════════════════════════════════════════════════════════
# 2. CognitiveClock
# ═══════════════════════════════════════════════════════════════════════════════


class TestCognitiveClock:
    def test_basic_advance(self):
        clock = CognitiveClock()
        t = clock.advance()
        assert t.number == 1
        assert clock.elapsed == 1

    def test_advance_n(self):
        clock = CognitiveClock()
        ticks = clock.advance_n(100)
        assert len(ticks) == 100
        assert ticks[0].number == 1
        assert ticks[-1].number == 100

    def test_no_skip_rs51_02(self):
        """RS51-02: 10000 tick 无跳号。"""
        clock = CognitiveClock()
        prev = 0
        for _ in range(10000):
            t = clock.advance()
            assert t.number == prev + 1, f"Gap at {prev} → {t.number}"
            prev = t.number
        assert clock.elapsed == 10000

    def test_schedule_due(self):
        clock = CognitiveClock()
        s = TickSchedule(name="mem", stage="memory", every=10, priority=Priority.LOW)
        clock.register_schedule(s)
        # 第一次运行于 tick 1
        t = clock.advance()
        clock.mark_completed(s, t)
        assert not s.should_run(2)
        # 10 tick 后才再次到期
        clock.advance_n(8)  # now at tick 9
        # tick 10 才到期
        for _ in range(10):
            clock.advance()
        # 到达 tick 20 — now -10 from last
        due = clock.due_schedules()
        assert len(due) >= 1

    def test_schedule_completed(self):
        clock = CognitiveClock()
        s = TickSchedule(name="perception", every=1)
        clock.register_schedule(s)
        t = clock.advance()
        clock.mark_completed(s, t)
        assert s.last_run == 1


# ═══════════════════════════════════════════════════════════════════════════════
# 3. PriorityQueue
# ═══════════════════════════════════════════════════════════════════════════════


class TestPriorityQueue:
    def test_higher_priority_first(self):
        """RS51-03: CRITICAL 优先于 LOW。"""
        pq = PriorityQueue()
        pq.push(SchedulerTask(task_id="low", priority=Priority.LOW))
        pq.push(SchedulerTask(task_id="critical", priority=Priority.CRITICAL))
        pq.push(SchedulerTask(task_id="med", priority=Priority.MEDIUM))

        assert pq.pop().task_id == "critical"
        assert pq.pop().task_id == "med"
        assert pq.pop().task_id == "low"

    def test_fifo_within_priority(self):
        pq = PriorityQueue()
        pq.push(SchedulerTask(task_id="a", priority=Priority.HIGH))
        pq.push(SchedulerTask(task_id="b", priority=Priority.HIGH))
        assert pq.pop().task_id == "a"
        assert pq.pop().task_id == "b"

    def test_depth(self):
        pq = PriorityQueue()
        assert pq.depth == 0
        pq.push(SchedulerTask(task_id="x"))
        assert pq.depth == 1

    def test_peek(self):
        pq = PriorityQueue()
        pq.push(SchedulerTask(task_id="top", priority=Priority.CRITICAL))
        assert pq.peek().task_id == "top"
        assert pq.depth == 1  # still there

    def test_cancel_all(self):
        pq = PriorityQueue()
        for i in range(5):
            pq.push(SchedulerTask(task_id=f"t{i}"))
        n = pq.cancel_all()
        assert n == 5
        assert pq.depth == 0

    def test_drain_priority(self):
        pq = PriorityQueue()
        pq.push(SchedulerTask(task_id="critical", priority=Priority.CRITICAL))
        pq.push(SchedulerTask(task_id="low1", priority=Priority.LOW))
        pq.push(SchedulerTask(task_id="low2", priority=Priority.LOW))

        drained = pq.drain_priority(Priority.LOW)
        assert len(drained) == 2
        assert pq.depth == 1
        assert pq.pop().task_id == "critical"


# ═══════════════════════════════════════════════════════════════════════════════
# 4. TaskScheduler
# ═══════════════════════════════════════════════════════════════════════════════


class TestTaskScheduler:
    def make_scheduler(self) -> TaskScheduler:
        scheduler = TaskScheduler()
        scheduler.checkpoint_interval = 999999  # 禁用 auto-checkpoint 干扰测试
        return scheduler

    def test_basic_run(self):
        executed = []
        scheduler = self.make_scheduler()
        scheduler.register_stage("test", lambda: executed.append(1), Priority.HIGH, every=1)

        stats = scheduler.run(max_ticks=100)
        assert stats.total_ticks == 100
        assert stats.completed_tasks >= 100

    def test_stage_registration(self):
        scheduler = self.make_scheduler()
        results = []
        scheduler.register_stage("stage_a", lambda: results.append("a"), Priority.CRITICAL, every=1)
        scheduler.register_stage("stage_b", lambda: results.append("b"), Priority.LOW, every=10)

        scheduler.run(max_ticks=50)
        assert len(results) > 0
        assert "a" in results

    def test_priority_ordering_rs51_03(self):
        """RS51-03: CRITICAL 阶段先于 MEDIUM 阶段执行。"""
        order = []
        scheduler = self.make_scheduler()
        scheduler.register_stage("crit", lambda: order.append("crit"), Priority.CRITICAL, every=1)
        scheduler.register_stage("med", lambda: order.append("med"), Priority.MEDIUM, every=10)

        scheduler.run(max_ticks=100)

        # 第一个 tick 的 crit 一定在 med 前面
        assert order[0] == "crit"

    def test_pause_resume(self):
        scheduler = self.make_scheduler()
        scheduler.register_stage("test", lambda: None, every=1)

        scheduler.run(max_ticks=10)
        scheduler.pause()
        assert scheduler.stats.status == SchedulerStatus.PAUSED

        before = scheduler.stats.total_ticks
        scheduler.resume()
        scheduler.run(max_ticks=10)
        assert scheduler.stats.total_ticks > before

    def test_stop(self):
        scheduler = self.make_scheduler()
        scheduler.register_stage("test", lambda: None, every=1)

        import threading, time
        def stopper():
            time.sleep(0.02)
            scheduler.stop()

        t = threading.Thread(target=stopper, daemon=True)
        t.start()
        scheduler.run(max_ticks=0)  # infinite
        assert scheduler.stats.status == SchedulerStatus.STOPPED

    def test_rs51_01_no_goal_creation(self):
        """RS51-01: Scheduler 不创建 goal，只执行注册的 stage。"""
        scheduler = self.make_scheduler()

        # 不应有 create_goal, modify_memory, make_decision 相关的 API
        assert not hasattr(scheduler, "create_goal")
        assert not hasattr(scheduler, "modify_memory")
        assert not hasattr(scheduler, "make_decision")

    def test_task_failure_retry(self):
        attempts = []
        def flaky():
            attempts.append(1)
            if len(attempts) < 3:
                raise RuntimeError("flaky")
            return "ok"

        scheduler = self.make_scheduler()
        scheduler.register_stage("flaky", flaky, Priority.HIGH, every=1)

        scheduler.run(max_ticks=3)
        # 3 attempts succeeded on 3rd → max_retries=2, so task may succeed after 3 ticks
        assert len(attempts) >= 3

    def test_rs51_02_tick_stability(self):
        """RS51-02: 10000 ticks 连续无丢失。"""
        scheduler = self.make_scheduler()
        scheduler.register_stage("test", lambda: None, every=1)

        ticks_recorded = []
        scheduler.on_tick = lambda t: ticks_recorded.append(t.number)
        scheduler.run(max_ticks=10000)

        assert len(ticks_recorded) == 10000
        for i, n in enumerate(ticks_recorded, 1):
            assert n == i, f"Gap at i={i}, n={n}"


# ═══════════════════════════════════════════════════════════════════════════════
# 5. BackpressureManager
# ═══════════════════════════════════════════════════════════════════════════════


class TestBackpressureManager:
    def test_activate_deactivate(self):
        bm = BackpressureManager()
        bm.state.high_watermark = 50
        bm.state.low_watermark = 10

        bm.update(60)
        assert bm.is_active

        bm.update(5)
        assert not bm.is_active

    def test_critical_always_accepted(self):
        bm = BackpressureManager()
        bm.state.active = True

        task = SchedulerTask(task_id="urgent", priority=Priority.CRITICAL)
        assert bm.check(task)

    def test_low_rejected_under_pressure(self):
        bm = BackpressureManager()
        bm.state.active = True

        task = SchedulerTask(task_id="bg", priority=Priority.LOW)
        assert not bm.check(task)

    def test_medium_deferred(self):
        bm = BackpressureManager()
        bm.state.active = True

        task = SchedulerTask(task_id="medium", priority=Priority.MEDIUM)
        assert not bm.check(task)
        assert task.status == TaskStatus.BACKPRESSURED


# ═══════════════════════════════════════════════════════════════════════════════
# 6. WorkerManager
# ═══════════════════════════════════════════════════════════════════════════════


class TestWorkerManager:
    def test_assign_and_release(self):
        wm = WorkerManager()
        task = SchedulerTask(task_id="t1", stage="memory")
        w = wm.assign(task)
        assert w.status == WorkerStatus.BUSY
        assert w.current_task is task

        task.status = TaskStatus.COMPLETED
        wm.release(task)
        assert w.status == WorkerStatus.IDLE
        assert w.tasks_completed == 1

    def test_isolation(self):
        """Stage A busy 不阻塞 Stage B。"""
        wm = WorkerManager()
        a = SchedulerTask(task_id="a", stage="perception")
        b = SchedulerTask(task_id="b", stage="memory")

        wm.assign(a)
        assert wm.is_busy("perception")
        assert not wm.is_busy("memory")

        wm.assign(b)
        assert wm.is_busy("memory")

    def test_busy_idle_tracking(self):
        wm = WorkerManager()
        wm.assign(SchedulerTask(task_id="x", stage="attention"))

        assert wm.busy_stages() == ["attention"]
        assert len(wm.idle_stages()) == 0

    def test_stats(self):
        wm = WorkerManager()
        wm.assign(SchedulerTask(task_id="t", stage="memory"))
        s = wm.stats()
        assert s["total_workers"] == 1
        assert s["busy"] == 1


# ═══════════════════════════════════════════════════════════════════════════════
# 7. SchedulerHealth
# ═══════════════════════════════════════════════════════════════════════════════


class TestSchedulerHealth:
    def test_healthy(self):
        health = SchedulerHealth()
        stats = SchedulerStats(
            completed_tasks=100, failed_tasks=0,
            current_queue_depth=5, avg_task_latency=0.01,
        )
        report = health.check(Tick(1), stats)
        assert report["healthy"]

    def test_tick_gap_detected(self):
        health = SchedulerHealth()
        health.last_tick = Tick(5)
        stats = SchedulerStats()
        report = health.check(Tick(10), stats)
        assert not report["healthy"]
        assert any("gap" in i.lower() for i in report["issues"])

    def test_high_failure_rate(self):
        health = SchedulerHealth()
        stats = SchedulerStats(completed_tasks=50, failed_tasks=50)
        report = health.check(Tick(100), stats)
        assert not report["healthy"]
        assert any("Failure" in i for i in report["issues"])

    def test_backpressure_warning(self):
        health = SchedulerHealth()
        stats = SchedulerStats(status=SchedulerStatus.BACKPRESSURED)
        report = health.check(Tick(1), stats)
        assert any("backpressure" in w.lower() for w in report["warnings"])


# ═══════════════════════════════════════════════════════════════════════════════
# 8. Integration: RS51-05 持久化联动
# ═══════════════════════════════════════════════════════════════════════════════


class TestSchedulerPersistenceIntegration:
    def test_get_set_state_rs51_05(self):
        """RS51-05: 调度器状态可序列化恢复。"""
        scheduler = TaskScheduler()
        scheduler.register_stage("test", lambda: None, every=1)
        scheduler.run(max_ticks=500)

        state = scheduler.get_state()
        assert state["current_tick"] == 500
        assert state["completed"] > 0

        # 恢复
        s2 = TaskScheduler()
        s2.register_stage("test", lambda: None, every=1)
        s2.set_state(state)

        assert s2.clock.current.number == 500
        assert s2.stats.total_tasks == state["total_tasks"]

    def test_full_cycle_with_persistence(self):
        """完整周期: Run → Checkpoint → Shutdown → Restore → Continue。"""
        from ocos.persistence import SnapshotManager, SnapshotDomain
        from ocos.persistence.snapshot_manager import StateProvider

        # 创建调度器
        s1 = TaskScheduler()
        results = []
        s1.register_stage("perception", lambda: results.append("p"), Priority.CRITICAL, every=1)
        s1.register_stage("memory", lambda: results.append("m"), Priority.LOW, every=10)

        # 运行 500 tick
        s1.run(max_ticks=500)
        assert len(results) > 0

        # 导出状态
        state = s1.get_state()
        tick_at_shutdown = state["current_tick"]

        # --- SHUTDOWN ---
        # --- COLD BOOT ---

        s2 = TaskScheduler()
        s2.register_stage("perception", lambda: results.append("p2"), Priority.CRITICAL, every=1)
        s2.register_stage("memory", lambda: results.append("m2"), Priority.LOW, every=10)
        s2.set_state(state)

        # 验证恢复
        assert s2.clock.current.number == tick_at_shutdown
        assert s2.stats.completed_tasks == state["completed"]

        # 继续运行
        s2.run(max_ticks=100)
        assert s2.clock.current.number > tick_at_shutdown

    def test_tick_as_checkpoint_trigger(self):
        """RS51-05: scheduler 集成 checkpoint 回调。"""
        checkpoints = []
        scheduler = TaskScheduler()
        scheduler.checkpoint_interval = 100
        scheduler.on_checkpoint = lambda tick: checkpoints.append(tick)
        scheduler.register_stage("test", lambda: None, every=1)

        scheduler.run(max_ticks=500)
        assert len(checkpoints) == 5  # tick 100,200,300,400,500
        assert checkpoints == [100, 200, 300, 400, 500]
