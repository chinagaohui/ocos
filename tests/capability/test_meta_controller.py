"""Phase 23 — Gate 23-04: Meta Controller 测试。

验证:
  23-012: 死循环检测
  23-013: 停滞检测
  23-014: 超时检测
  23-015: 干预执行
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT))

from ocos.capability.models import (
    ProcessGraph,
    SkillExecutionRecord,
    SkillStatus,
)
from ocos.capability.meta_controller import (
    MetaController,
    MetaControllerConfig,
    Intervention,
)


# ── Helpers ──────────────────────────────────────────────────────────────────


def make_record(
    skill_id: str,
    skill_name: str = "",
    status: SkillStatus = SkillStatus.COMPLETED,
) -> SkillExecutionRecord:
    return SkillExecutionRecord(
        skill_id=skill_id,
        skill_name=skill_name or skill_id,
        status=status,
    )


def make_process(
    *records: SkillExecutionRecord,
    start_time: datetime | None = None,
    total_duration: float = 0.0,
) -> ProcessGraph:
    process = ProcessGraph(
        id="test-process",
        skill_graph_id="test-graph",
        session_id="test-session",
        start_time=start_time or datetime.now(timezone.utc),
        total_duration=total_duration,
    )
    for r in records:
        process.add_record(r)
    return process


# ── 23-012: 死循环检测 ────────────────────────────────────────────────────


def test_meta_deadlock_detection():
    """同一 Skill 重复 N 次 → 死循环。"""
    config = MetaControllerConfig(deadlock_threshold=5)
    controller = MetaController(config)

    records = [make_record("s1", "Stuck Skill", SkillStatus.COMPLETED)] * 5
    process = make_process(*records)

    intervention = controller.monitor(process)

    assert intervention.decision == "abort"
    assert any("DEADLOCK" in t for t, _ in intervention.interventions)


def test_meta_deadlock_not_yet():
    """少于阈值 → 无死循环。"""
    config = MetaControllerConfig(deadlock_threshold=5)
    controller = MetaController(config)

    records = [make_record("s1", "Stuck")] * 4
    process = make_process(*records)

    intervention = controller.monitor(process)

    assert intervention.decision == "continue"


def test_meta_deadlock_mixed_skills():
    """不同 Skill 交替执行 → 不死循环。"""
    config = MetaControllerConfig(deadlock_threshold=5)
    controller = MetaController(config)

    records = [
        make_record("s1", "A"), make_record("s2", "B"),
        make_record("s1", "A"), make_record("s2", "B"),
        make_record("s1", "A"),
    ]
    process = make_process(*records)

    intervention = controller.monitor(process)

    assert intervention.decision == "continue"


# ── 23-013: 停滞检测 ──────────────────────────────────────────────────────


def test_meta_stall_detection():
    """连续 3 次失败 → 停滞。"""
    controller = MetaController()

    records = [
        make_record("s1", "A", SkillStatus.FAILED),
        make_record("s2", "B", SkillStatus.FAILED),
        make_record("s3", "C", SkillStatus.FAILED),
    ]
    process = make_process(*records)

    intervention = controller.monitor(process)

    assert intervention.decision == "retry"
    assert any("STALLED" in t for t, _ in intervention.interventions)


def test_meta_stall_not_yet():
    """少于 3 次失败 → 无停滞。"""
    controller = MetaController()

    records = [
        make_record("s1", "A", SkillStatus.FAILED),
        make_record("s2", "B", SkillStatus.FAILED),
    ]
    process = make_process(*records)

    intervention = controller.monitor(process)

    assert intervention.decision == "continue"


def test_meta_stall_with_success_in_between():
    """失败间插入了成功 → 停滞计数重置。"""
    controller = MetaController()

    records = [
        make_record("s1", "A", SkillStatus.FAILED),
        make_record("s2", "B", SkillStatus.FAILED),
        make_record("s3", "C", SkillStatus.COMPLETED),
        make_record("s4", "D", SkillStatus.FAILED),
    ]
    process = make_process(*records)

    intervention = controller.monitor(process)

    assert intervention.decision == "continue"


# ── 23-014: 超时检测 ──────────────────────────────────────────────────────


def test_meta_timeout_detection():
    """超出 max_process_duration → 超时。"""
    config = MetaControllerConfig(max_process_duration_seconds=10.0)
    controller = MetaController(config)

    start = datetime.now(timezone.utc) - timedelta(seconds=30)
    process = make_process(
        make_record("s1", "A"),
        start_time=start,
        total_duration=30.0,
    )

    intervention = controller.monitor(process)

    assert intervention.decision == "abort"
    assert any("TIMEOUT" in t for t, _ in intervention.interventions)


def test_meta_timeout_not_yet():
    """未超出时间 → 无超时。"""
    config = MetaControllerConfig(max_process_duration_seconds=10.0)
    controller = MetaController(config)

    process = make_process(
        make_record("s1", "A"),
        start_time=datetime.now(timezone.utc),
        total_duration=5.0,
    )

    intervention = controller.monitor(process)

    assert intervention.decision == "continue"


# ── 23-015: 干预执行 ──────────────────────────────────────────────────────


def test_meta_intervention_abort():
    """abort 干预应发送停止信号。"""
    controller = MetaController()

    # 模拟 executor
    class MockExecutor:
        def __init__(self):
            self.stopped = []

        def stop(self, process_id: str):
            self.stopped.append(process_id)

    executor = MockExecutor()
    controller.intervene(executor, "p1", "abort")

    assert "p1" in executor.stopped
    assert len(controller.intervention_history) == 1
    assert controller.intervention_history[0]["action"] == "abort"


def test_meta_intervention_no_abort_on_non_abort():
    """non-abort 干预不应调用 stop。"""
    controller = MetaController()

    class MockExecutor:
        def __init__(self):
            self.stopped = []

        def stop(self, process_id: str):
            self.stopped.append(process_id)

    executor = MockExecutor()
    controller.intervene(executor, "p1", "retry")

    assert len(executor.stopped) == 0


def test_meta_path_too_long():
    """路径过长应警告。"""
    config = MetaControllerConfig(max_skills_per_process=5)
    controller = MetaController(config)

    records = [make_record(f"s{i}", f"Skill {i}") for i in range(10)]
    process = make_process(*records)

    intervention = controller.monitor(process)

    assert any("PATH_TOO_LONG" in t for t, _ in intervention.interventions)


def test_meta_clear_history():
    """清除历史应清空。"""
    controller = MetaController()
    controller.intervene(None, "p1", "abort")

    assert len(controller.intervention_history) == 1
    controller.clear_history()
    assert len(controller.intervention_history) == 0
