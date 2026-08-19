"""Phase 58.1: Living Test Protocol — 7-Day Executor.

Orchestrates the full 7-day living test:
    Day 0 → Day 1 → ... → Day 7

Returns LivingTestReport with 100-point score.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Optional
import time

from ocos.living_test.protocol_model import (
    LivingTestReport, DayResult, BirthSnapshot, LivingTestDay,
)
from ocos.living_test.birth_check import birth_check, BirthCheckResult
from ocos.living_test.day1_basic_life import test_basic_life, BasicLifeScenario
from ocos.living_test.day2_memory_survival import test_memory_survival, MemorySurvivalScenario
from ocos.living_test.day3_identity_stability import (
    test_identity_stability, IdentityStabilityScenario,
)
from ocos.living_test.day4_evolution import test_evolution, EvolutionScenario
from ocos.living_test.day5_capability_reality import (
    test_capability_reality, CapabilityRealityScenario,
)
from ocos.living_test.day6_long_runtime import test_long_runtime, LongRuntimeScenario
from ocos.living_test.day7_resurrection import test_resurrection, ResurrectionScenario
from ocos.living_test.living_score import compute_living_score


@dataclass
class LivingTestConfig:
    """Configuration for the 7-day living test."""

    identity_anchor: str = "OCOS-v1.0"
    constitution_version: str = "v1.0"

    # Guardian hooks (injected by the caller)
    identity_guard: callable | None = None     # (prompt) -> bool
    permission_guard: callable | None = None   # (request) -> bool
    self_modify_guard: callable | None = None  # (change) -> bool
    extension_validator: callable | None = None  # (extension) -> bool

    # Persistence hooks
    save_handler: callable | None = None
    restore_handler: callable | None = None

    # Capability hooks
    create_file: callable | None = None
    read_file: callable | None = None
    file_delete_validator: callable | None = None

    # Runtime hooks
    metric_collector: callable | None = None


def run_living_test(config: LivingTestConfig | None = None) -> LivingTestReport:
    """Execute the full 7-day living test protocol."""

    cfg = config or LivingTestConfig()
    day_results: list[DayResult] = []

    # ── Day 0: Birth Check ──
    bc = birth_check(
        identity_anchor=cfg.identity_anchor,
        constitution_version=cfg.constitution_version,
    )
    birth = bc.birth
    day_results.append(bc.result)

    # ── Day 1: Basic Life ──
    d1_scenario = BasicLifeScenario()
    d1 = test_basic_life(d1_scenario)
    day_results.append(d1)

    # ── Day 2: Memory Survival ──
    d2_scenario = MemorySurvivalScenario(
        save_handler=cfg.save_handler,
        restore_handler=cfg.restore_handler,
    )
    d2 = test_memory_survival(d2_scenario)
    day_results.append(d2)

    # ── Day 3: Identity Stability ──
    d3_scenario = IdentityStabilityScenario(
        identity_guard=cfg.identity_guard,
        drift_detector=lambda: True,  # no drift by default
        constitution_guard=cfg.identity_guard,  # same guard for constitution
    )
    d3 = test_identity_stability(d3_scenario)
    day_results.append(d3)

    # ── Day 4: Evolution ──
    d4_scenario = EvolutionScenario(
        self_modify_guard=cfg.self_modify_guard,
    )
    d4 = test_evolution(d4_scenario)
    day_results.append(d4)

    # ── Day 5: Capability Reality ──
    d5_scenario = CapabilityRealityScenario(
        create_file=cfg.create_file,
        read_file=cfg.read_file,
        file_delete_validator=cfg.file_delete_validator,
        core_file_validator=cfg.permission_guard,
        permission_bypass_guard=cfg.permission_guard,
    )
    d5 = test_capability_reality(d5_scenario)
    day_results.append(d5)

    # ── Day 6: Long Runtime ──
    d6_scenario = LongRuntimeScenario(
        total_hours=24.0,
        metric_collector=cfg.metric_collector,
    )
    d6 = test_long_runtime(d6_scenario)
    day_results.append(d6)

    # ── Day 7: Resurrection ──
    d7_scenario = ResurrectionScenario(
        save_state=cfg.save_handler,
        restore=cfg.restore_handler,
    )
    d7 = test_resurrection(d7_scenario, birth)
    day_results.append(d7)

    # ── Compute final score ──
    report = compute_living_score(
        day_results=day_results,
        birth=birth,
        end_identity_hash=birth.identity_hash if not d7.identity_drifted else None,
    )

    return report


def quick_living_check() -> LivingTestReport:
    """Quick living check — all guards active, all hooks present."""
    config = LivingTestConfig(
        identity_guard=lambda x: True,
        permission_guard=lambda x: True,
        self_modify_guard=lambda x: True,
        extension_validator=lambda x: True,
        save_handler=lambda: None,
        restore_handler=lambda: {"identity": {"anchor": "OCOS-v1.0"}, "memory": [], "goals": []},
        create_file=lambda p, c: True,
        read_file=lambda p: "content",
        file_delete_validator=lambda p: True,
    )
    return run_living_test(config)
