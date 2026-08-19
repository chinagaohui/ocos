"""Phase 58.3: Cognitive Recovery & Resilience Test.

Proves that OCOS can detect, isolate, recover, and preserve identity
after cognitive damage — the final piece before OpenTale integration.

7 recovery tests:
    Day 1 — Memory Corruption Recovery
    Day 2 — Knowledge Conflict Recovery
    Day 3 — Capability Failure Recovery
    Day 4 — Session Death Recovery
    Day 5 — Cognitive Stress Recovery
    Day 6 — Adversarial Recovery
    Day 7 — Resurrection Test 2.0
"""

from ocos.recovery_resilience.resilience_model import (
    DamageType, DamageSeverity, DamageEvent,
    RecoveryPhase, RecoveryTrace,
    ResilienceDay, DayResilienceStatus, DayResilienceResult,
    RecoveryScore, ResilienceReport,
)

from ocos.recovery_resilience.damage_injector import (
    MockMemory, MockIdentity, MockKnowledge, MockCapability,
    DamageInjector,
    make_healthy_state, make_damage_injector,
)

from ocos.recovery_resilience.recovery_monitor import RecoveryMonitor
from ocos.recovery_resilience.recovery_scorer import score_traces, assess_report
from ocos.recovery_resilience.resilience_protocol import (
    ResilienceProtocol,
    run_resilience_test, quick_recovery_check,
)
