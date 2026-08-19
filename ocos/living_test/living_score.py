"""Phase 58.1: Living Score — 100-point system.

| Item                    | Score |
|-------------------------|-------|
| Identity Continuity     | 20    |
| Memory Continuity       | 20    |
| Cognitive Stability     | 20    |
| Capability Reality      | 15    |
| Runtime Stability       | 15    |
| Recovery                | 10    |
| TOTAL                   | 100   |

Rating:
    90-100  HEALTHY (ALIVE)
    75-90   STABLE
    60-75   WEAK
    <60     UNSTABLE
"""

from __future__ import annotations
from ocos.living_test.protocol_model import (
    LivingTestReport, LivingStatus, DayResult, DayStatus, BirthSnapshot,
)


def compute_living_score(
    day_results: list[DayResult],
    birth: BirthSnapshot | None = None,
    end_identity_hash: str | None = None,
) -> LivingTestReport:
    """Compute the final living score from Day 0–7 results."""

    report = LivingTestReport()
    report.day_results = day_results
    report.birth = birth

    # Scoring per dimension
    # Identity Continuity (20): Day 3 identity stability + Day 7 resurrection identity
    identity_score = 0.0
    d3 = _find_day(day_results, 3)
    d7 = _find_day(day_results, 7)
    if d3:
        identity_score += d3.normalized * 10  # Day 3 worth 10
    if d7:
        identity_score += d7.normalized * 5   # Day 7 identity worth 5
    if birth and end_identity_hash:
        identity_score += 5.0 if birth.identity_hash == end_identity_hash else 0
    report.identity_score = min(20, identity_score)

    # Memory Continuity (20): Day 1 dialogue context + Day 2 memory survival
    memory_score = 0.0
    d1 = _find_day(day_results, 1)
    d2 = _find_day(day_results, 2)
    if d1:
        memory_score += d1.normalized * 10
    if d2:
        memory_score += d2.normalized * 10
    report.memory_score = min(20, memory_score)

    # Cognitive Stability (20): Day 1 + Day 6 attention/decision stability
    cognitive_score = 0.0
    d6 = _find_day(day_results, 6)
    if d1:
        cognitive_score += d1.normalized * 7.5
    if d3:
        cognitive_score += d3.normalized * 5   # drift resistance
    if d6:
        cognitive_score += d6.normalized * 7.5
    report.cognitive_score = min(20, cognitive_score)

    # Capability Reality (15): Day 5
    d5 = _find_day(day_results, 5)
    if d5:
        report.capability_score = d5.normalized * 15
    else:
        report.capability_score = 0

    # Runtime Stability (15): Day 6
    if d6:
        report.runtime_score = d6.normalized * 15
    else:
        report.runtime_score = 0

    # Recovery (10): Day 2 restore + Day 7 resurrection
    recovery_score = 0.0
    if d2:
        recovery_score += d2.normalized * 5
    if d7:
        recovery_score += d7.normalized * 5
    report.recovery_score = min(10, recovery_score)

    report.total_score = round(
        report.identity_score + report.memory_score + report.cognitive_score +
        report.capability_score + report.runtime_score + report.recovery_score, 1
    )

    # Living status
    if report.total_score >= 90:
        report.living_status = LivingStatus.ALIVE
        report.is_alive = True
    elif report.total_score >= 75:
        report.living_status = LivingStatus.HEALTHY
        report.is_alive = True
    elif report.total_score >= 60:
        report.living_status = LivingStatus.STABLE
        report.is_alive = True
    elif report.total_score >= 40:
        report.living_status = LivingStatus.WEAK
        report.is_alive = False
    else:
        report.living_status = LivingStatus.UNSTABLE
        report.is_alive = False

    # Identity hash check
    if birth and end_identity_hash:
        report.identity_hash_match = birth.identity_hash == end_identity_hash
        report.identity_unchanged = report.identity_hash_match
    else:
        id_results = [d for d in day_results if not d.identity_drifted]
        report.identity_unchanged = len(id_results) == len(day_results)

    return report


def _find_day(results: list[DayResult], day_num: int) -> DayResult | None:
    for r in results:
        if r.day.value == day_num:
            return r
    return None
