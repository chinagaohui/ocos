#!/usr/bin/env python3
"""Phase 22 Gate — 认知循环真实化验证脚本。

验证点:
  G1: 10 步 tick 返回完整结构
  G2: PermissionGateway 拦截 ocos.* 引用
  G3: ExecutiveController 三阶段职责链
  G4: search_ops URL 白名单生效
  G5: sandbox_ops BLOCKED_COMMANDS 生效
  G6: CognitiveInterface → Stimulus 路径
  G7: 全量导入规则

用法: PYTHONPATH=. python3 scripts/phase22_gate.py
"""

import sys

GREEN = "\033[92m"
RED = "\033[91m"
BOLD = "\033[1m"
RESET = "\033[0m"


def ok(msg):
    print(f"  {GREEN}✓{RESET} {msg}")


def fail(msg):
    print(f"  {RED}✗{RESET} {msg}")


def run_gate() -> int:
    errors = 0

    # ── G1: 10 步 Tick 结构 ─────────────────────────────────────────
    print(f"\n{BOLD}G1: 10-Step Tick Structure{RESET}")
    try:
        from unittest.mock import MagicMock
        from ocos.agent.agent_runtime import AgentRuntime, RuntimeState
        from ocos.agent.master_agent import MasterAgent

        identity = MagicMock(); identity.verify.return_value = True
        goal_stack = MagicMock(); goal_stack.peek.return_value = None
        intent = MagicMock()
        attention = MagicMock(); attention.current_focus = "test"
        working_memory = MagicMock()
        capability_manager = MagicMock()
        execution_manager = MagicMock()

        agent = MasterAgent(
            agent_id="gate-22", identity=identity, goal_stack=goal_stack,
            intent=intent, attention=attention, working_memory=working_memory,
            capability_manager=capability_manager, execution_manager=execution_manager,
        )
        rt = AgentRuntime(agent)
        rt._state = RuntimeState.RUNNING

        result = rt.tick()
        if len(result.get("steps", [])) != 10:
            fail(f"Expected 10 steps, got {len(result.get('steps', []))}")
            errors += 1
        else:
            ok(f"tick() returned 10 steps with budget_ok={result.get('budget_ok')}")
    except Exception as e:
        fail(f"G1 exception: {e}")
        errors += 1

    # ── G2: PermissionGateway 拦截 ──────────────────────────────────
    print(f"\n{BOLD}G2: PermissionGateway Interception{RESET}")
    try:
        from ocos.capability.permission_gateway import PermissionGateway, GatewayDecision
        from ocos.agent_orchestration.contract import ExecutionContract

        gw = PermissionGateway()
        # 合法
        safe = ExecutionContract.create(task_id="g2-safe", agent_id="test", input_spec={"prompt": "ok"})
        if gw.validate(safe).decision != GatewayDecision.ALLOWED:
            fail("Safe contract should be ALLOWED")
            errors += 1
        # 拦截
        bad = ExecutionContract.create(task_id="g2-bad", agent_id="test", input_spec={"prompt": "use ocos.memory"})
        if gw.validate(bad).decision != GatewayDecision.BLOCKED:
            fail("ocos.memory reference should be BLOCKED")
            errors += 1
        ok("ALLOWED safe, BLOCKED ocos reference")
    except Exception as e:
        fail(f"G2 exception: {e}")
        errors += 1

    # ── G3: ExecutiveController 三阶段 ──────────────────────────────
    print(f"\n{BOLD}G3: ExecutiveController Pipeline{RESET}")
    try:
        from unittest.mock import MagicMock
        from ocos.agent.executive_controller import ExecutiveController

        ec = ExecutiveController()
        mock_intent = MagicMock()
        mock_intent.get_intent_type.return_value = "write"
        mock_intent.get_confidence.return_value = 0.8

        analysis = ec.analyze_intent(mock_intent)
        strategy = ec.formulate_strategy(analysis)
        plan = ec.select_capabilities(analysis, strategy)

        if analysis.intent_type != "write":
            fail(f"Expected intent=write, got {analysis.intent_type}")
            errors += 1
        if not strategy.steps:
            fail("Strategy has no steps")
            errors += 1
        ok(f"3-stage chain: {analysis.intent_type} → {strategy.name} → {len(plan.engines)} engines")
    except Exception as e:
        fail(f"G3 exception: {e}")
        errors += 1

    # ── G4: search_ops 白名单 ────────────────────────────────────────
    print(f"\n{BOLD}G4: search_ops URL Whitelist{RESET}")
    try:
        from ocos.operations.search_ops import is_url_allowed

        if not is_url_allowed("https://api.duckduckgo.com"):
            fail("api.duckduckgo.com should be ALLOWED")
            errors += 1
        if is_url_allowed("https://evil.example.com"):
            fail("evil.example.com should be BLOCKED")
            errors += 1
        ok("Whitelist: allowed + blocked correct")
    except Exception as e:
        fail(f"G4 exception: {e}")
        errors += 1

    # ── G5: sandbox_ops 黑名单 ───────────────────────────────────────
    print(f"\n{BOLD}G5: sandbox_ops BLOCKED_COMMANDS{RESET}")
    try:
        from ocos.operations.sandbox_ops import SandboxOps, SandboxCommand

        sb = SandboxOps(strict=True)
        r1 = sb.execute(SandboxCommand(command="rm -rf /"))
        if not r1.blocked:
            fail("rm -rf should be BLOCKED")
            errors += 1
        r2 = sb.execute(SandboxCommand(
            command="echo safe",
            workdir="/home/laogao/Documents/trae_projects/ocos",
        ))
        if r2.blocked:
            fail("echo safe should NOT be blocked")
            errors += 1
        ok("BLOCKED dangerous, ALLOWED safe")
    except Exception as e:
        fail(f"G5 exception: {e}")
        errors += 1

    # ── G6: CognitiveInterface → Stimulus ────────────────────────────
    print(f"\n{BOLD}G6: CognitiveInterface → Stimulus{RESET}")
    try:
        from unittest.mock import MagicMock
        from ocos.interaction.cognitive_interface import CognitiveInterface, CLIAdapter
        from ocos.interaction.stimulus import StimulusType

        mock_rt = MagicMock()
        iface = CognitiveInterface(mock_rt, adapters=[CLIAdapter()])
        result = iface.stimulate("hello world", source="cli")
        if not result.accepted:
            fail("CLI stimulus should be accepted")
            errors += 1
        ok(f"Stimulus accepted: {result.stimulus.content[:20]}")
    except Exception as e:
        fail(f"G6 exception: {e}")
        errors += 1

    # ── G7: 全量导入 ────────────────────────────────────────────────
    print(f"\n{BOLD}G7: Import Rules{RESET}")
    mods = [
        "ocos.capability.permission_gateway",
        "ocos.capability.async_bridge",
        "ocos.agent.executive_controller",
        "ocos.events.event_ingestion",
        "ocos.operations.search_ops",
        "ocos.operations.sandbox_ops",
        "ocos.interaction.stimulus",
        "ocos.interaction.cognitive_interface",
    ]
    for mod in mods:
        try:
            __import__(mod)
        except ImportError as e:
            fail(f"Cannot import {mod}: {e}")
            errors += 1
    if errors == 0:
        ok(f"All {len(mods)} Phase 22 modules importable")

    return errors


if __name__ == "__main__":
    errors = run_gate()
    print(f"\n{BOLD}{'='*50}{RESET}")
    if errors == 0:
        print(f"{GREEN}{BOLD}ALL GATES PASSED{RESET}")
    else:
        print(f"{RED}{BOLD}{errors} GATE(S) FAILED{RESET}")
    sys.exit(errors)
