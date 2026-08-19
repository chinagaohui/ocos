"""Phase 23 — Gate 23-02: Fallback 策略测试（防 Workflow 退化的关键）

验证:
  23-004: retry — 失败后重试 max_retries 次
  23-005: skip — 失败后跳过，Process 继续
  23-006: fallback:<id> — 切换到备用 Skill
  23-007: abort — 失败后 Process 停止（默认）
  23-008: 单 Skill 失败 ≠ 整个 Process 失败（Skill Graph ≠ Workflow）
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

PROJECT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT))

from ocos.agent.cognitive_bridge import BridgeResult, CognitiveBridge
from ocos.capability.models import (
    ProcessGraph,
    Skill,
    SkillGraph,
    SkillExecutionRecord,
    SkillStatus,
)
from ocos.capability.skill_graph_executor import SkillGraphExecutor


# ── Helpers ──────────────────────────────────────────────────────────────────


def make_skill(
    id: str,
    name: str = "",
    capability: str = "reasoning",
    fallback: str = "abort",
    max_retries: int = 0,
    prerequisite: list[str] | None = None,
) -> Skill:
    return Skill(
        id=id,
        name=name or id,
        required_capability=capability,
        fallback_strategy=fallback,
        max_retries=max_retries,
        prerequisite=prerequisite or [],
        input_state={},
        output_state={},
    )


def make_success_result(message: str = "ok") -> BridgeResult:
    return BridgeResult(
        success=True,
        message=message,
        data={"result": message},
    )


def make_failure_result(error: str = "error") -> BridgeResult:
    return BridgeResult(
        success=False,
        message=error,
        errors=[error],
    )


def make_linear_graph(skills: list[Skill]) -> SkillGraph:
    """创建 A→B→C 线性图。"""
    for i in range(1, len(skills)):
        skills[i].prerequisite = [skills[i - 1].id]
    return SkillGraph(
        id="linear",
        name="Linear Graph",
        skills=skills,
    )


# ── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
def bridge_mock() -> MagicMock:
    """返回 mock 的 CognitiveBridge，所有方法返回成功。"""
    mock = MagicMock(spec=CognitiveBridge)
    mock.reason.return_value = make_success_result("reasoned")
    mock.plan.return_value = make_success_result("planned")
    mock.decide.return_value = make_success_result("decided")
    mock.reflect.return_value = make_success_result("reflected")
    mock.learn.return_value = make_success_result("learned")
    return mock


@pytest.fixture
def executor(bridge_mock: MagicMock) -> SkillGraphExecutor:
    return SkillGraphExecutor(bridge=bridge_mock)


# ── 23-004: retry ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_fallback_retry_success_after_retries(
    bridge_mock: MagicMock, executor: SkillGraphExecutor
) -> None:
    """retry 策略：第一次失败但重试后成功。"""
    skill = make_skill("retry_me", "Retry", fallback="retry", max_retries=3)

    # 前两次失败，第三次成功
    bridge_mock.reason.side_effect = [
        make_failure_result("fail 1"),
        make_failure_result("fail 2"),
        make_success_result("ok"),
    ]
    graph = SkillGraph(id="gr", name="Retry Graph", skills=[skill])

    process = await executor.start(graph, context={})

    assert process.status == SkillStatus.COMPLETED
    assert len(process.execution_history) == 1
    record = process.execution_history[0]
    assert record.status == SkillStatus.COMPLETED
    assert record.attempt == 3  # 第一次 + 两次重试 = 3 次尝试
    assert bridge_mock.reason.call_count == 3


@pytest.mark.asyncio
async def test_fallback_retry_all_fail(
    bridge_mock: MagicMock, executor: SkillGraphExecutor
) -> None:
    """retry 策略：所有重试都失败。"""
    skill = make_skill("retry_all", "Retry All", fallback="retry", max_retries=2)

    bridge_mock.reason.return_value = make_failure_result("fail")

    graph = SkillGraph(id="gr", name="Retry All", skills=[skill])
    process = await executor.start(graph, context={})

    assert process.status == SkillStatus.FAILED
    record = process.execution_history[0]
    assert record.status == SkillStatus.FAILED
    assert record.attempt == 3  # 第一次 + 2 次重试
    assert bridge_mock.reason.call_count == 3


@pytest.mark.asyncio
async def test_fallback_retry_with_exponential_backoff(
    bridge_mock: MagicMock, executor: SkillGraphExecutor
) -> None:
    """retry 应有指数退避延迟。"""
    skill = make_skill("sleepy", "Sleepy", fallback="retry", max_retries=2)
    bridge_mock.reason.return_value = make_failure_result("fail")
    bridge_mock.reason.side_effect = None  # 清除 side_effect

    graph = SkillGraph(id="gr", name="Sleepy", skills=[skill])

    import time
    t0 = time.monotonic()
    process = await executor.start(graph, context={})
    elapsed = time.monotonic() - t0

    # 第一次立即执行，两次重试：0.2s + 0.4s = 0.6s 退避
    assert elapsed >= 0.2, f"期望至少 0.2s 退避，实际 {elapsed:.2f}s"
    assert process.status == SkillStatus.FAILED


# ── 23-005: skip ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_fallback_skip_single_skill(
    bridge_mock: MagicMock, executor: SkillGraphExecutor
) -> None:
    """skip 策略：单 Skill 失败后跳过，Process 应完成。"""
    skill = make_skill("skip_me", "Skip Me", fallback="skip")
    bridge_mock.reason.return_value = make_failure_result("skip this")

    graph = SkillGraph(id="gr", name="Skip Graph", skills=[skill])
    process = await executor.start(graph, context={})

    assert process.status == SkillStatus.COMPLETED, (
        "skip 策略：即使 Skill 失败，Process 也应完成"
    )
    record = process.execution_history[0]
    assert record.status == SkillStatus.SKIPPED, (
        "记录应标记为 SKIPPED"
    )
    assert record.output.get("skipped") is True
    assert record.output.get("original_error") == "skip this"


@pytest.mark.asyncio
async def test_fallback_skip_in_middle_of_chain(
    bridge_mock: MagicMock, executor: SkillGraphExecutor
) -> None:
    """skip 策略：在链中间失败，前后 Skill 仍正常执行。

    技能链: A → B → C, B 使用 skip 策略
    A 成功, B 失败→跳过, C 成功, Process 完成
    """
    skill_a = make_skill("a", "A", fallback="abort")
    skill_b = make_skill("b", "B", fallback="skip")
    skill_c = make_skill("c", "C", fallback="abort")

    call_count = {"count": 0}

    def reason_side_effect(**kwargs):
        call_count["count"] += 1
        # B 在第二次调用时失败（A→B→C，B 是第二次）
        if call_count["count"] == 2:
            return make_failure_result("B failed")
        return make_success_result("ok")

    bridge_mock.reason.side_effect = reason_side_effect

    graph = make_linear_graph([skill_a, skill_b, skill_c])
    process = await executor.start(graph, context={})

    assert process.status == SkillStatus.COMPLETED, (
        "skip 策略：中间 Skill 失败不应导致整个链失败"
    )
    assert len(process.execution_history) == 3

    # A 成功
    assert process.execution_history[0].status == SkillStatus.COMPLETED
    # B 跳过
    assert process.execution_history[1].status == SkillStatus.SKIPPED
    # C 成功（因为 B 是 skip 不是 abort，执行继续）
    assert process.execution_history[2].status == SkillStatus.COMPLETED


# ── 23-006: fallback:<id> ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_fallback_fallback_skill(
    bridge_mock: MagicMock, executor: SkillGraphExecutor
) -> None:
    """fallback:<id> 策略：失败后切换到备用 Skill。"""
    primary = make_skill("primary", "Primary", fallback="fallback:backup")
    backup = make_skill("backup", "Backup", fallback="abort")

    # primary 失败 → 切换到 backup
    bridge_mock.reason.side_effect = [
        make_failure_result("primary failed"),
        make_success_result("backup worked"),
    ]

    graph = SkillGraph(id="gr", name="Fallback Graph", skills=[primary])
    context = {"_fallback_skills": [backup]}

    process = await executor.start(graph, context=context)

    assert process.status == SkillStatus.COMPLETED
    record = process.execution_history[0]
    assert record.status == SkillStatus.COMPLETED
    assert "backup" in record.skill_name.lower()


@pytest.mark.asyncio
async def test_fallback_fallback_skill_not_found(
    bridge_mock: MagicMock, executor: SkillGraphExecutor
) -> None:
    """fallback:<id> 策略：备用 Skill 不存在时应 abort。"""
    primary = make_skill("primary", "Primary", fallback="fallback:nonexistent")
    bridge_mock.reason.return_value = make_failure_result("failed")

    graph = SkillGraph(id="gr", name="No Fallback", skills=[primary])
    process = await executor.start(graph, context={})

    assert process.status == SkillStatus.FAILED
    assert process.execution_history[0].status == SkillStatus.FAILED


# ── 23-007: abort ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_fallback_abort_single_skill(
    bridge_mock: MagicMock, executor: SkillGraphExecutor
) -> None:
    """abort 策略：Skill 失败，Process 失败。"""
    skill = make_skill("fail", "Fail", fallback="abort")
    bridge_mock.reason.return_value = make_failure_result("abort this")

    graph = SkillGraph(id="gr", name="Abort Graph", skills=[skill])
    process = await executor.start(graph, context={})

    assert process.status == SkillStatus.FAILED
    record = process.execution_history[0]
    assert record.status == SkillStatus.FAILED


@pytest.mark.asyncio
async def test_fallback_abort_stops_chain(
    bridge_mock: MagicMock, executor: SkillGraphExecutor
) -> None:
    """abort 策略在链中：失败后的 Skill 不应执行。

    技能链: A → B → C, B 使用 abort
    A 成功, B 失败, C 不执行
    """
    skill_a = make_skill("a", "A")
    skill_b = make_skill("b", "B", fallback="abort")
    skill_c = make_skill("c", "C")

    call_count = {"count": 0}

    def reason_side_effect(**kwargs):
        call_count["count"] += 1
        if call_count["count"] == 2:  # B
            return make_failure_result("B failed")
        return make_success_result("ok")

    bridge_mock.reason.side_effect = reason_side_effect

    graph = make_linear_graph([skill_a, skill_b, skill_c])
    process = await executor.start(graph, context={})

    assert process.status == SkillStatus.FAILED
    assert len(process.execution_history) == 2  # C 未执行
    assert process.execution_history[0].status == SkillStatus.COMPLETED
    assert process.execution_history[1].status == SkillStatus.FAILED


# ── 23-008: Skill Graph ≠ Workflow ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_executor_no_workflow_degradation(
    bridge_mock: MagicMock, executor: SkillGraphExecutor
) -> None:
    """验证 Skill Graph ≠ Workflow。

    5 个 Skill 的链，其中一个使用 skip 策略失败，Process 应完成。
    这是 Skill Graph 与 Workflow 的关键区别：
      - Workflow: 一步失败 = 全线失败
      - Skill Graph: 单步失败可跳过/重试/切换
    """
    skills = [
        make_skill("s1", "Skill 1"),                          # abort（默认）
        make_skill("s2", "Skill 2"),                          # abort（默认）
        make_skill("s3", "Skill 3", fallback="skip"),         # skip — 关键
        make_skill("s4", "Skill 4", fallback="retry", max_retries=2),  # retry
        make_skill("s5", "Skill 5"),                          # abort（默认）
    ]

    call_count = {"count": 0}

    def reason_side_effect(**kwargs):
        call_count["count"] += 1
        # s3 失败（第 3 次调用），s4 失败一次然后成功
        if call_count["count"] == 3:  # s3
            return make_failure_result("S3 failed (will be skipped)")
        if call_count["count"] == 4:  # s4 first try
            return make_failure_result("S4 try 1")
        return make_success_result("ok")

    bridge_mock.reason.side_effect = reason_side_effect

    graph = make_linear_graph(skills)
    process = await executor.start(graph, context={})

    # 关键断言：Process 必须完成
    assert process.status == SkillStatus.COMPLETED, (
        f"Skill Graph ≠ Workflow: 即使有 Skill 失败 (skip/retry 后成功)，"
        f"Process 应完成，实际: {process.status.value}"
    )

    assert len(process.execution_history) == 5, (
        f"所有 5 个 Skill 都应执行（skip 不停止链），"
        f"实际: {len(process.execution_history)}"
    )

    # s1: completed, s2: completed, s3: skipped, s4: completed (after retry), s5: completed
    assert process.execution_history[0].status == SkillStatus.COMPLETED
    assert process.execution_history[1].status == SkillStatus.COMPLETED
    assert process.execution_history[2].status == SkillStatus.SKIPPED
    assert process.execution_history[3].status == SkillStatus.COMPLETED
    assert process.execution_history[4].status == SkillStatus.COMPLETED


# ── 辅助测试：停止信号 ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_stop_signal_cancels_process(
    bridge_mock: MagicMock, executor: SkillGraphExecutor
) -> None:
    """停止信号应取消 Process。

    使用 5 个 Skill 的链，在第一个 Skill 完成后发送停止信号。
    第二个 Skill 执行前检测到信号并取消。
    """
    skills = [make_skill(f"s{i}", f"Skill {i}") for i in range(5)]
    graph = make_linear_graph(skills)

    call_count = {"count": 0}

    def reason_side_effect(**kwargs):
        call_count["count"] += 1
        if call_count["count"] == 1:
            # 第一个 Skill 完成后立即停止
            for pid in list(executor._stop_events.keys()):
                executor.stop(pid)
                break
        return make_success_result("ok")

    bridge_mock.reason.side_effect = reason_side_effect

    process = await executor.start(graph, context={})

    assert process.status == SkillStatus.CANCELLED, (
        f"应被取消，实际: {process.status.value}"
    )


# ── 辅助测试：空 SkillGraph ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_empty_skill_graph_fails(
    executor: SkillGraphExecutor,
) -> None:
    """空 SkillGraph 应失败（validation 失败）。"""
    graph = SkillGraph(id="empty", name="Empty", skills=[])
    process = await executor.start(graph, context={})

    assert process.status == SkillStatus.FAILED
    assert len(process.error_log) > 0
