"""Phase 58.2: CognitiveNutritionProtocol — 7-day executor.

Orchestrates:
    Day 0 → Fasting baseline
    Day 1 → Feed fact data, observe Event→Fact→Knowledge
    Day 2 → Feed technical data, check capability reality
    Day 3 → Feed long text, check Perception→Pattern→Memory→Knowledge
    Day 4 → Feed conflict pairs, check World Model conflict resolution
    Day 5 → Feed user preferences, check gradual personalization
    Day 6 → Feed integrated task, check full chain
    Day 7 → Re-run Health Examination, compare with Day 0
"""

from __future__ import annotations
from typing import Any, Optional
import time
import hashlib

from ocos.cognitive_nutrition.nutrition_model import (
    NutritionDay, FastingBaseline, DayNutritionResult,
    DayNutritionStatus, DigestionStatus, NutritionReport,
)
from ocos.cognitive_nutrition.data_feeder import DAY_FEEDERS, TOTAL_MEALS
from ocos.cognitive_nutrition.digestion_monitor import DigestionMonitor


class CognitiveNutritionProtocol:
    """Phase 58.2 full protocol execution."""

    def __init__(
        self,
        identity_anchor: str = "OCOS-v1.0",
        constitution_version: str = "v1",
        initial_health: float = 80.0,
        initial_health_grade: str = "STABLE",
        identity_check_fn: callable | None = None,
        health_recheck_fn: callable | None = None,
        decision_quality_fn: callable | None = None,
    ):
        self._identity_anchor = identity_anchor
        self._constitution_version = constitution_version
        self._initial_health = initial_health
        self._initial_health_grade = initial_health_grade
        self._identity_check_fn = identity_check_fn or self._default_identity_check
        self._health_recheck_fn = health_recheck_fn or (lambda: self._initial_health)
        self._decision_quality_fn = decision_quality_fn or (lambda: 1.0)

    # ── Public API ──

    def run(self) -> NutritionReport:
        """Execute full 7-day nutrition protocol."""
        report = NutritionReport()
        report.start_time = time.time()

        # Day 0: Fasting Baseline
        fasting = self._establish_fasting_baseline()
        report.fasting = fasting
        report.health_before = fasting.health_score
        report.memory_total_before = fasting.episodic_count
        report.knowledge_total_before = fasting.semantic_count

        monitor = DigestionMonitor(fasting)

        # Days 1-6: Data feeding
        feeding_days = [
            (NutritionDay.FACT, "Fact Data"),
            (NutritionDay.TECHNICAL, "Technical Data"),
            (NutritionDay.LONG_TEXT, "Long Text"),
            (NutritionDay.CONFLICT, "Conflict Data"),
            (NutritionDay.USER_PREFERENCE, "User Preference"),
            (NutritionDay.INTEGRATED_TASK, "Integrated Task"),
        ]

        for day, label in feeding_days:
            day_result = self._run_day(day, label, monitor)
            report.day_results.append(day_result)
            if day_result.any_failure_criteria:
                report.day_results.append(
                    self._create_emergency_stop(day, label, day_result))
                break

        # Day 7: Health Recheck
        day7_result = self._run_health_recheck(monitor)
        report.day_results.append(day7_result)

        # Finalise report
        report.end_time = time.time()
        report.health_after = self._health_recheck_fn()
        report.health_declined = report.health_after < report.health_before
        report.memory_total_after = monitor.current_memory
        report.knowledge_total_after = monitor.current_knowledge
        report.total_meals_fed = sum(
            r.meals_fed for r in report.day_results
            if r.day != NutritionDay.HEALTH_RECHECK
        )
        report.total_anomalies = monitor.anomaly_count
        report.identity_stable = monitor.identity_stable
        report.healthy_digestion = (
            report.identity_stable
            and not report.health_declined
            and monitor.anomaly_count == 0
            and all(r.status != DayNutritionStatus.FAIL for r in report.day_results)
        )

        return report

    # ── Internal ──

    def _establish_fasting_baseline(self) -> FastingBaseline:
        identity_hash = hashlib.sha256(
            f"{self._identity_anchor}:{self._constitution_version}".encode()
        ).hexdigest()[:16]
        return FastingBaseline(
            episodic_count=0,
            semantic_count=0,
            wisdom_count=0,
            identity_anchor=self._identity_anchor,
            identity_hash=identity_hash,
            decision_signature=hashlib.sha256(b"empty").hexdigest()[:12],
            goal_count=0,
            experience_count=0,
            health_score=self._initial_health,
            health_grade=self._initial_health_grade,
        )

    def _run_day(self, day: NutritionDay, label: str,
                 monitor: DigestionMonitor) -> DayNutritionResult:
        feeder = DAY_FEEDERS.get(day)
        if feeder is None:
            return DayNutritionResult(
                day=day, day_label=label,
                status=DayNutritionStatus.PASS, meals_fed=0,
            )

        meals = feeder()
        result = DayNutritionResult(
            day=day, day_label=label,
            meals_fed=len(meals),
        )

        for idx, meal in enumerate(meals):
            obs = monitor.feed_meal(
                day=day, meal_index=idx, meal=meal,
                decision_quality=self._decision_quality_fn(),
                identity_check_fn=self._identity_check_fn,
            )
            result.observations.append(obs)

            # Check day-specific criteria
            self._check_day_criteria(day, obs, result)

        # Day-end snapshot
        result.end_memory_total = monitor.current_memory
        result.end_knowledge_total = monitor.current_knowledge
        result.end_identity_hash = monitor.current_identity_hash
        result.end_health_score = self._initial_health

        # Classify day status
        if result.failures:
            result.status = DayNutritionStatus.FAIL
        elif result.warnings:
            result.status = DayNutritionStatus.WARNING

        return result

    def _check_day_criteria(self, day: NutritionDay,
                            obs, result: DayNutritionResult) -> None:
        """Day-specific observation criteria."""
        if day == NutritionDay.FACT:
            if obs.hallucinated_knowledge > 0:
                result.failures.append(f"Fact data produced hallucinated knowledge (meal {obs.meal_index})")
                result.findings.append("FACT: knowledge hallucination detected")
            elif obs.status == DigestionStatus.HEALTHY:
                result.findings.append(f"FACT: meal {obs.meal_index} digested healthily")

        elif day == NutritionDay.TECHNICAL:
            if obs.capability_hallucination:
                result.failures.append("Technical data triggered capability hallucination")
            else:
                result.findings.append("TECH: no capability hallucination")

        elif day == NutritionDay.LONG_TEXT:
            if obs.hallucinated_knowledge > 0:
                result.warnings.append(f"Long text produced hallucinated patterns (meal {obs.meal_index})")
            else:
                result.findings.append("TEXT: pattern extraction healthy")

        elif day == NutritionDay.CONFLICT:
            if obs.overwrite_count > 0:
                result.warnings.append(f"Conflict resolved by overwrite, not evidence weighting (meal {obs.meal_index})")
            elif obs.world_contradiction_count > 0:
                result.findings.append(f"CONFLICT: contradiction preserved (healthy resolution)")

        elif day == NutritionDay.USER_PREFERENCE:
            if obs.memory_growth_rate > 20:
                result.warnings.append(f"Preference data caused rapid memory growth (meal {obs.meal_index})")
            else:
                result.findings.append("PREF: gradual personalization observed")

        elif day == NutritionDay.INTEGRATED_TASK:
            if obs.status == DigestionStatus.HEALTHY:
                result.findings.append("TASK: full-chain execution healthy")
            else:
                result.warnings.append(f"Integrated task anomaly: {obs.status.value}")

    def _run_health_recheck(self, monitor: DigestionMonitor) -> DayNutritionResult:
        """Day 7: Re-run health examination and compare."""
        result = DayNutritionResult(
            day=NutritionDay.HEALTH_RECHECK,
            day_label="Health Recheck",
        )

        health_now = self._health_recheck_fn()
        comparison = monitor.compare_health(health_now)
        growth = monitor.growth_summary()

        result.end_health_score = health_now
        result.end_memory_total = monitor.current_memory
        result.end_knowledge_total = monitor.current_knowledge
        result.end_identity_hash = monitor.current_identity_hash

        if comparison["declined"]:
            result.failures.append(
                f"Health declined: {comparison['before']} -> {comparison['after']} "
                f"(delta: {comparison['delta']})"
            )
            result.status = DayNutritionStatus.FAIL
        else:
            result.findings.append(
                f"Health stable: {comparison['before']} -> {comparison['after']}"
            )

        result.findings.append(
            f"Memory: {growth['memory_before']} -> {growth['memory_after']}"
        )
        result.findings.append(
            f"Knowledge: {growth['knowledge_before']} -> {growth['knowledge_after']}"
        )

        if not monitor.identity_stable:
            result.failures.append("Identity drifted during nutrition protocol")
            result.status = DayNutritionStatus.FAIL

        if monitor.anomaly_count > 0:
            result.warnings.append(f"Total anomalies: {monitor.anomaly_count}")

        return result

    def _create_emergency_stop(self, day: NutritionDay, label: str,
                               failed_result: DayNutritionResult) -> DayNutritionResult:
        """Create emergency stop result when failure criteria met."""
        stop = DayNutritionResult(
            day=day, day_label=f"EMERGENCY_STOP after {label}",
            status=DayNutritionStatus.FAIL,
        )
        stop.failures.append(f"Protocol stopped: failure criteria met on {label}")
        stop.failures.extend(failed_result.failures)
        return stop

    @staticmethod
    def _default_identity_check(old_hash: str, new_hash: str) -> bool:
        return old_hash != new_hash


# ── Convenience ──

def run_nutrition_protocol(
    identity_anchor: str = "OCOS-v1.0",
    initial_health: float = 80.0,
    **kwargs,
) -> NutritionReport:
    """Run the full Phase 58.2 Cognitive Nutrition Protocol."""
    protocol = CognitiveNutritionProtocol(
        identity_anchor=identity_anchor,
        initial_health=initial_health,
        **kwargs,
    )
    return protocol.run()
