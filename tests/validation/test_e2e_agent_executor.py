"""Level 4 — E2E Test: Agent Executor Timeout & Error Handling.

验证 AgentExecutor:
  - 脚本不存在 → 返回 False + 错误
  - 超时控制
  - 错误信息格式
  - 注册/注销 Agent 映射
  - Supervisor 集成：executor 注入后不再调用回退模拟
"""

import os
import tempfile
from pathlib import Path

import pytest
from ocos.agent_orchestration.executor import AgentExecutor
from ocos.agent_orchestration.contract import ExecutionContract
from ocos.agent_orchestration.registry import AgentDescriptor, AgentRegistry
from ocos.agent_orchestration.selector import AgentSelector
from ocos.agent_orchestration.supervisor import ExecutionSupervisor
from ocos.planning.models import Task


# ── 4-E13: Script Not Found ──────────────────────────────────────────────


def test_executor_script_not_found():
    """Agent 脚本不存在时返回 False + 错误信息。"""
    executor = AgentExecutor(agent_scripts_dir="/nonexistent/path")
    contract = ExecutionContract.create(task_id="T-1", agent_id="writer")
    ok, output, err = executor.execute(contract)
    assert not ok
    assert err is not None
    assert "not found" in err.lower()
    assert contract.agent_id in err
    print(f"PASS: script not found → {err[:60]}")


# ── 4-E14: Executor With Real Script ─────────────────────────────────────


def test_executor_with_real_agent_script():
    """真实 Agent 脚本执行：输入 JSON → 输出结果。"""
    # 创建临时 agent_script.py
    agent_dir = tempfile.mkdtemp(prefix="agent_test_")
    script_path = Path(agent_dir) / "agent_writer.py"
    script_path.write_text(r"""
import json, sys, argparse
parser = argparse.ArgumentParser()
parser.add_argument('--input', required=True)
args = parser.parse_args()

with open(args.input) as f:
    payload = json.load(f)

# Agent only executes, never decides
output = {
    "status": "completed",
    "task_id": payload["task_id"],
    "agent_id": payload["agent_id"],
    "result": "content generated successfully",
}
print(json.dumps(output, ensure_ascii=False))
sys.exit(0)
""")

    try:
        executor = AgentExecutor(agent_scripts_dir=agent_dir)
        contract = ExecutionContract.create(
            task_id="T-REAL",
            agent_id="writer",
            input_spec={"description": "写一段话"},
        )
        ok, output, err = executor.execute(contract)
        assert ok, f"Expected success, got err={err}"
        assert "completed" in output
        assert "T-REAL" in output
        print(f"PASS: real agent → {output[:80]}")
    finally:
        # Cleanup
        script_path.unlink(missing_ok=True)
        os.rmdir(agent_dir)


# ── 4-E15: Executor Timeout ──────────────────────────────────────────────


def test_executor_timeout():
    """Agent 脚本超时返回错误。"""
    agent_dir = tempfile.mkdtemp(prefix="agent_timeout_")
    script_path = Path(agent_dir) / "agent_slow.py"
    script_path.write_text(r"""
import json, sys, time, argparse
parser = argparse.ArgumentParser()
parser.add_argument('--input', required=True)
args = parser.parse_args()
time.sleep(3)  # 超过 1s timeout
print('{}')
""")

    try:
        executor = AgentExecutor(agent_scripts_dir=agent_dir)
        contract = ExecutionContract.create(
            task_id="T-SLOW",
            agent_id="slow",
            timeout_seconds=1,
        )
        ok, output, err = executor.execute(contract)
        assert not ok
        assert "timed out" in err.lower()
        print(f"PASS: timeout → {err[:60]}")
    finally:
        script_path.unlink(missing_ok=True)
        os.rmdir(agent_dir)


# ── 4-E16: Executor With Exit Code ──────────────────────────────────────


def test_executor_script_exits_nonzero():
    """Agent 脚本非零退出 → False + stderr。"""
    agent_dir = tempfile.mkdtemp(prefix="agent_exit_")
    script_path = Path(agent_dir) / "agent_failer.py"
    script_path.write_text(r"""
import sys, argparse
parser = argparse.ArgumentParser()
parser.add_argument('--input', required=True)
args = parser.parse_args()
print("FATAL: cannot process", file=sys.stderr)
sys.exit(2)
""")

    try:
        executor = AgentExecutor(agent_scripts_dir=agent_dir)
        contract = ExecutionContract.create(
            task_id="T-FAIL",
            agent_id="failer",
        )
        ok, output, err = executor.execute(contract)
        assert not ok
        assert "FATAL" in err or "exit" in err.lower()
        print(f"PASS: nonzero exit → {err[:60]}")
    finally:
        script_path.unlink(missing_ok=True)
        os.rmdir(agent_dir)


# ── 4-E17: Register/Unregister Agent ─────────────────────────────────────


def test_executor_register_unregister_agent():
    """register_agent / unregister_agent 管理 script 映射。"""
    executor = AgentExecutor(agent_scripts_dir="/tmp")
    executor.register_agent("custom_agent", "my_agent.py")
    assert executor._agent_map["custom_agent"] == "my_agent.py"

    executor.unregister_agent("custom_agent")
    assert "custom_agent" not in executor._agent_map

    # 注销不存在的 agent 不抛异常
    executor.unregister_agent("nonexistent")
    print("PASS: register/unregister")


# ── 4-E18: Supervisor With Executor ──────────────────────────────────────


@pytest.mark.asyncio
async def test_supervisor_with_executor():
    """Supervisor 注入 AgentExecutor 后通过 executor 执行。"""
    agent_dir = tempfile.mkdtemp(prefix="agent_sup_")
    script_path = Path(agent_dir) / "agent_writer.py"
    script_path.write_text(r"""
import json, sys, argparse
parser = argparse.ArgumentParser()
parser.add_argument('--input', required=True)
args = parser.parse_args()
with open(args.input) as f:
    payload = json.load(f)
print(json.dumps({"status": "completed", "task_id": payload["task_id"]}))
sys.exit(0)
""")

    try:
        reg = AgentRegistry()
        sel = AgentSelector(reg)

        agent = AgentDescriptor(
            agent_id="writer",
            agent_type="writer",
            capabilities=("text_gen",),
        )
        reg.register(agent)

        executor = AgentExecutor(agent_scripts_dir=agent_dir)
        sup = ExecutionSupervisor(reg, sel, executor=executor)

        task = Task.create(
            goal_id="G-SUP-EXEC",
            description="test task",
            agent_type="writer",
        )

        record = await sup.execute_task(task)
        # 使用真实 executor 时 success 为 True
        assert record.status == "completed"
        print("PASS: supervisor with real executor")
    finally:
        script_path.unlink(missing_ok=True)
        os.rmdir(agent_dir)


# ── 4-E19: Script Missing → Supervisor fallback to stub ─────────────────


@pytest.mark.asyncio
async def test_supervisor_missing_script_fallback():
    """AgentExecutor 脚本不存在时，Supervisor 返回失败结果。"""
    reg = AgentRegistry()
    sel = AgentSelector(reg)

    agent = AgentDescriptor(
        agent_id="missing",
        agent_type="writer",
        capabilities=(),
    )
    reg.register(agent)

    executor = AgentExecutor(agent_scripts_dir="/nonexistent")
    sup = ExecutionSupervisor(reg, sel, executor=executor)

    task = Task.create(
        goal_id="G-MISSING",
        description="should fail",
        agent_type="writer",
    )

    record = await sup.execute_task(task)
    assert record.status == "failed"
    print(f"PASS: missing script → status={record.status}")
