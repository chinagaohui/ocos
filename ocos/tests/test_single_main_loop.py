"""P1-C 循环收敛验收测试（2026-08-29）。

背景: OCOS 存在 5 个循环实体（AgentRuntime / RuntimeKernel / LoopOrchestrator /
AutonomousLoop / TaskScheduler），生产唯一主动循环 = ResidentRuntime._tick_loop。
P1-C 收敛目标: 认知循环唯一宿主 = RuntimeKernel.tick_loop，AgentRuntime.tick
经 driver 注入（注入式，不违反 R39-203 Governance 隔离），LoopOrchestrator /
TaskScheduler 保持组件地位、不进入生产路径。

验收项:
  T1 kernel attach driver → tick_loop(3) 驱动 3 次 + last_agent_result 可查
  T2 未 attach driver → pipeline 8 stage trace 完整（空系统心跳语义不变）
  T3 ResidentRuntime 集成 → daemon 启动后 runtime cycle 与 kernel tick 同步增长
  T4 循环宿主唯一性 → daemon/factory/run.py 不引用 LoopOrchestrator/TaskScheduler
  T5 Governance 隔离 → runtime_kernel.py / pipeline.py 不 import ocos.agent
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

OCOS_ROOT = Path(__file__).resolve().parents[2]


# ── T1: kernel 经 driver 驱动 Agent ──────────────────────────────────────


def test_t1_kernel_drives_agent_via_driver():
    from ocos.runtime.runtime_kernel import RuntimeKernel

    calls: list[int] = []

    def driver(tick_id: int) -> dict:
        calls.append(tick_id)
        return {"cycle": len(calls), "tick_id": tick_id}

    kernel = RuntimeKernel()
    kernel.attach_agent_driver(driver)
    kernel.start()
    try:
        kernel.tick_loop(max_ticks=3)
    finally:
        kernel.shutdown(checkpoint=False)

    assert len(calls) == 3, f"driver 应被驱动 3 次，实际 {len(calls)}"
    assert kernel.tick_count == 3
    assert kernel.last_agent_result == {"cycle": 3, "tick_id": calls[-1]}


def test_t1_driver_result_updates_per_tick():
    from ocos.runtime.runtime_kernel import RuntimeKernel

    seen: list[int] = []
    kernel = RuntimeKernel()
    kernel.attach_agent_driver(lambda tick_id: seen.append(tick_id) or {"n": tick_id})
    kernel.start()
    try:
        kernel.tick_loop(max_ticks=2)
    finally:
        kernel.shutdown(checkpoint=False)

    # last_agent_result 反映最近一次 driver 执行
    assert len(seen) == 2
    assert kernel.last_agent_result == {"n": seen[-1]}


# ── T2: 未 attach driver 时空系统心跳语义不变 ─────────────────────────────


def test_t2_pipeline_empty_heartbeat_unchanged():
    from ocos.runtime.pipeline import TickPipeline
    from ocos.runtime.pipeline_protocol import PipelineStage

    pipe = TickPipeline()
    ctx = pipe.execute_tick(tick_id=7, runtime_state="RUNNING")

    assert pipe.last_agent_result is None
    # 8 阶段 trace + COMPLETE
    trace = [t for t in ctx.stage_traces]
    assert trace[-1] == "COMPLETE"
    assert len([t for t in trace if t != "COMPLETE"]) == len(PipelineStage)


# ── T3: ResidentRuntime 集成 — daemon 经 kernel 驱动 ──────────────────────


def _make_agent():
    from unittest.mock import MagicMock

    agent = MagicMock()
    agent.boot = MagicMock()
    # agent_id 保持 MagicMock：boot 时跳过持久化（同 test_phase33）
    # 镜像 test_phase33._make_agent：身份/注意力/目标栈桩
    agent.state.status.name = "IDLE"
    agent.attention = MagicMock()
    agent.attention.update = MagicMock()
    agent.attention.current_focus = "none"
    agent.goal_stack = MagicMock()
    agent.goal_stack.get_active_count.return_value = 0
    return agent


def test_t3_daemon_ticks_through_kernel():
    from ocos.daemon import ResidentRuntime

    rt = ResidentRuntime(_make_agent(), tick_interval=0.05, max_cycles=100)
    rt.start()
    try:
        import time

        time.sleep(0.35)
        # runtime cycle 与 kernel tick 同步增长（每轮 daemon → kernel.tick_loop(1) → agent driver）
        assert rt.cycle_count >= 3, f"runtime cycles={rt.cycle_count}"
        assert rt._kernel.tick_count == rt.cycle_count, (
            f"kernel tick({rt._kernel.tick_count}) 应等于 runtime cycle({rt.cycle_count})"
        )
        # driver 已把 AgentRuntime.tick 注入 kernel（最近一次 agent 执行结果可查）
        assert rt._kernel.last_agent_result is not None
    finally:
        rt.stop(timeout=2.0)


# ── T4: 循环宿主唯一性 — C/D 不进入生产路径 ────────────────────────────────


@pytest.mark.parametrize(
    "production_file",
    [
        "ocos/daemon/__init__.py",
        "ocos/daemon/factory.py",
        "ocos/interaction/cli/commands/run.py",
    ],
)
def test_t4_production_path_has_no_loop_orchestrator(production_file):
    src = (OCOS_ROOT / production_file).read_text(encoding="utf-8")
    assert "LoopOrchestrator" not in src, f"{production_file} 不应引用 LoopOrchestrator"
    assert "TaskScheduler" not in src, f"{production_file} 不应引用 TaskScheduler"
    assert "AutonomousLoop" not in src, f"{production_file} 不应引用 AutonomousLoop"


# ── T5: Governance 隔离 — kernel/pipeline 不 import ocos.agent ────────────


@pytest.mark.parametrize(
    "runtime_file",
    [
        "ocos/runtime/runtime_kernel.py",
        "ocos/runtime/pipeline.py",
        "ocos/runtime/stages/event_ingestion.py",
        "ocos/runtime/stages/learning_trigger.py",
    ],
)
def test_t5_no_agent_import_in_runtime_kernel(runtime_file):
    src = (OCOS_ROOT / runtime_file).read_text(encoding="utf-8")
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert not alias.name.startswith("ocos.agent"), (
                    f"{runtime_file} 违反 R39-203: import {alias.name}"
                )
        elif isinstance(node, ast.ImportFrom):
            assert not (node.module or "").startswith("ocos.agent"), (
                f"{runtime_file} 违反 R39-203: from {node.module} import ..."
            )
