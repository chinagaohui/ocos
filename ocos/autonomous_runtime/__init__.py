"""Phase 60: Autonomous Runtime — OCOS自我运行的认知引擎。

Builds on Phase 46's cognitive_loop.LoopOrchestrator to add:
  - Self-running cognitive loop (autonomous tick)
  - Sleep/wake rhythms
  - Action dispatch to OpenTale / web search / internal ops
  - Safety supervision (anti-runaway, identity protection)

Architecture:
    AutonomousLoop
    ├── wraps LoopOrchestrator (Phase 46)
    ├── RuntimeConfig (timing/thresholds/rhythms)
    ├── ActionDispatcher (routes to OpenTale / web / internal)
    └── LoopSupervisor (safety boundaries)

Usage:
    from ocos.autonomous_runtime import AutonomousLoop, RuntimeConfig

    loop = AutonomousLoop()
    # Hermes feeds input
    loop.tick("reader feedback: character arc feels rushed")
    # OCOS thinks, produces decision, dispatches action
    # Loop runs autonomously, sleeps when idle, wakes on triggers
"""

from ocos.autonomous_runtime.runtime_config import (
    LoopMode, WakeTrigger, RuntimeConfig, LoopStats,
)
from ocos.autonomous_runtime.autonomous_loop import AutonomousLoop
from ocos.autonomous_runtime.action_dispatcher import (
    ActionType, DispatchedAction, ActionDispatcher,
)
from ocos.autonomous_runtime.loop_supervisor import (
    SupervisorAlert, SupervisorState, LoopSupervisor,
)


def quick_runtime_test() -> dict:
    """Quick verification of the autonomous runtime."""
    from ocos.autonomous_runtime.autonomous_loop import AutonomousLoop
    from ocos.autonomous_runtime.runtime_config import RuntimeConfig

    config = RuntimeConfig(tick_interval_ms=100, max_ticks_per_session=50)
    loop = AutonomousLoop(config=config)

    # Feed some inputs
    loop.tick("Novel project: romance, chapter 5")
    loop.tick("Reader feedback: pacing is good but emotional depth lacking")

    # Autonomous ticks (self-reflection)
    for _ in range(3):
        loop.tick()

    return loop.summary()
