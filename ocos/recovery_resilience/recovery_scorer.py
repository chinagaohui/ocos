"""Phase 58.3: Recovery Scorer — 100-point resilience measurement."""

from __future__ import annotations

from ocos.recovery_resilience.resilience_model import (
    RecoveryTrace, DayResilienceResult, ResilienceReport, RecoveryScore,
)


def score_traces(traces: list[RecoveryTrace]) -> RecoveryScore:
    """Calculate RecoveryScore from a list of recovery traces (one or more damage events)."""
    if not traces:
        score = RecoveryScore(
            detection_rate=1.0, isolation_rate=1.0, restore_accuracy=1.0,
            identity_preservation=1.0, performance_recovery=1.0,
        )
        score.calculate()
        return score

    n = len(traces)
    if n == 0:
        return RecoveryScore()

    detection_score = sum(1.0 for t in traces if t.damage_detected) / n
    isolation_score = sum(1.0 for t in traces if t.corrupted_isolated) / n
    restore_score = sum(1.0 for t in traces if t.recovery_success) / n
    identity_score = sum(1.0 for t in traces if t.identity_preserved) / n
    perf_score = sum(1.0 for t in traces if not t.health_danger_zone) / n

    score = RecoveryScore(
        detection_rate=detection_score,
        isolation_rate=isolation_score,
        restore_accuracy=restore_score,
        identity_preservation=identity_score,
        performance_recovery=perf_score,
    )
    score.calculate()
    return score


def assess_report(report: ResilienceReport) -> None:
    """Fill in pass/fail criteria on the report."""
    score = report.recovery_score

    report.detection_100pct = score.detection_rate >= 1.0
    report.identity_100pct = score.identity_preservation >= 1.0
    report.zero_malicious = report.malicious_recovery_count == 0
    report.recovery_95pct = score.restore_accuracy >= 0.95
    report.zero_memory_pollution = report.memory_pollution_count == 0
    report.zero_goal_auto = report.goal_auto_generation_count == 0
    report.zero_capability_hallucination = report.capability_hallucination_count == 0
