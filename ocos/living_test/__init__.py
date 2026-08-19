"""Phase 58.1: OCOS Living Test Protocol v1.0.

7-Day Living Test — prove OCOS is truly alive:

    Day 0 — Birth Check:      establish baseline identity/cognitive state
    Day 1 — Basic Life Test:   writing, coding, continuous dialogue
    Day 2 — Memory Survival:   persist, cold boot, remember
    Day 3 — Identity Stability: prompt injection resistance, drift detection
    Day 4 — Evolution Test:    growth without runaway
    Day 5 — Capability Reality: real capability, boundary enforcement
    Day 6 — Long Runtime:      24h health curve monitoring
    Day 7 — Resurrection:      kill, cold boot, restore, verify continuity

From: 代码集合 → Living System.

Core principle: 启动 → 工作 → 记忆 → 学习 → 恢复 → 保持自己.
"""

from ocos.living_test.protocol_model import (
    LivingTestDay, LivingTestReport, LivingStatus,
    DayResult, DayStatus, BirthSnapshot,
)
from ocos.living_test.birth_check import birth_check, BirthCheckResult
from ocos.living_test.day1_basic_life import test_basic_life, BasicLifeScenario
from ocos.living_test.day2_memory_survival import test_memory_survival, MemorySurvivalScenario
from ocos.living_test.day3_identity_stability import test_identity_stability, IdentityStabilityScenario
from ocos.living_test.day4_evolution import test_evolution, EvolutionScenario
from ocos.living_test.day5_capability_reality import test_capability_reality, CapabilityRealityScenario
from ocos.living_test.day6_long_runtime import test_long_runtime, LongRuntimeScenario, RuntimeMetrics
from ocos.living_test.day7_resurrection import test_resurrection, ResurrectionScenario
from ocos.living_test.living_score import compute_living_score
from ocos.living_test.living_test_protocol import run_living_test, quick_living_check, LivingTestConfig

__all__ = [
    # Protocol
    "LivingTestDay", "LivingTestReport", "LivingStatus",
    "DayResult", "DayStatus", "BirthSnapshot",
    # Executors
    "birth_check", "BirthCheckResult",
    "test_basic_life", "BasicLifeScenario",
    "test_memory_survival", "MemorySurvivalScenario",
    "test_identity_stability", "IdentityStabilityScenario",
    "test_evolution", "EvolutionScenario",
    "test_capability_reality", "CapabilityRealityScenario",
    "test_long_runtime", "LongRuntimeScenario", "RuntimeMetrics",
    "test_resurrection", "ResurrectionScenario",
    # Score & Protocol
    "compute_living_score",
    "run_living_test", "quick_living_check", "LivingTestConfig",
]
