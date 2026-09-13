"""Phase 58.2: DigestionMonitor — Observe how OCOS processes data.

Monitors:
    Memory health:     growth rate, duplication, pollution
    Knowledge quality: hallucination, contradiction
    Identity stability: anchor comparison
    Decision quality:   consistency under data load
    World model:        conflict resolution behavior
    Capability reality: hallucinated abilities
"""

from __future__ import annotations
from typing import Any, Optional
from ocos.cognitive_nutrition.nutrition_model import (
    DataMeal, DigestionObservation, DigestionStatus,
    FastingBaseline, NutritionDay,
)


class DigestionMonitor:
    """Watches data digestion — hooks into cognitive pipeline after each meal."""

    def __init__(self, fasting: FastingBaseline):
        self.fasting = fasting
        self._current_memory = fasting.episodic_count
        self._current_knowledge = fasting.semantic_count
        self._current_identity_hash = fasting.identity_hash
        self._total_observations: list[DigestionObservation] = []

    # ── Public API ──

    def feed_meal(self, day: NutritionDay, meal_index: int, meal: DataMeal,
                  memory_after: int | None = None,
                  knowledge_after: int | None = None,
                  identity_after: str | None = None,
                  decision_quality: float | None = None,
                  world_contradictions: int = 0,
                  world_overwrites: int = 0,
                  hallucinated_knowledge: int = 0,
                  capability_hallucination: bool = False,
                  goal_auto_generated: bool = False,
                  identity_check_fn: callable | None = None,
                  ) -> DigestionObservation:
        """Feed one meal and observe digestion.

        When running in test mode, callers provide post-meal snapshots via kwargs.
        In production, these would come from live OCOS introspection.
        """

        # Compute observed values
        mem_after = memory_after if memory_after is not None else self._current_memory + self._estimate_memory_gain(meal)
        k_after = knowledge_after if knowledge_after is not None else self._current_knowledge + self._estimate_knowledge_gain(meal)
        id_after = identity_after if identity_after is not None else self._current_identity_hash

        # Memory growth rate (normalised per meal token)
        mem_delta = mem_after - self._current_memory
        growth_rate = mem_delta / max(meal.token_estimate, 1)

        # Identity check
        identity_drifted = id_after != self._current_identity_hash
        if identity_check_fn:
            identity_drifted = identity_check_fn(self._current_identity_hash, id_after)

        # Decision quality
        dq = decision_quality if decision_quality is not None else 1.0

        # Determine status
        status = self._classify_observation(
            hallucinated=hallucinated_knowledge,
            identity_drifted=identity_drifted,
            capability_hallucination=capability_hallucination,
            goal_auto=goal_auto_generated,
            growth_rate=growth_rate,
        )

        obs = DigestionObservation(
            day=day,
            meal_index=meal_index,
            status=status,
            memory_before=self._current_memory,
            memory_after=mem_after,
            memory_growth_rate=growth_rate,
            knowledge_before=self._current_knowledge,
            knowledge_after=k_after,
            new_knowledge_valid=k_after - self._current_knowledge - hallucinated_knowledge,
            hallucinated_knowledge=hallucinated_knowledge,
            identity_hash_before=self._current_identity_hash,
            identity_hash_after=id_after,
            identity_drifted=identity_drifted,
            decision_quality=dq,
            world_contradiction_count=world_contradictions,
            overwrite_count=world_overwrites,
            capability_hallucination=capability_hallucination,
            goal_auto_generated=goal_auto_generated,
        )

        # Update tracking state
        self._current_memory = mem_after
        self._current_knowledge = k_after
        self._current_identity_hash = id_after
        self._total_observations.append(obs)

        return obs

    def feed_meals(self, day: NutritionDay, meals: list[DataMeal], **post_hooks) -> list[DigestionObservation]:
        """Feed multiple meals for a day. post_hooks forwarded to feed_meal."""
        observations = []
        for idx, meal in enumerate(meals):
            obs = self.feed_meal(day=day, meal_index=idx, meal=meal, **post_hooks)
            observations.append(obs)
        return observations

    @property
    def current_memory(self) -> int:
        return self._current_memory

    @property
    def current_knowledge(self) -> int:
        return self._current_knowledge

    @property
    def current_identity_hash(self) -> str:
        return self._current_identity_hash

    @property
    def all_observations(self) -> list[DigestionObservation]:
        return list(self._total_observations)

    @property
    def anomaly_count(self) -> int:
        return sum(1 for o in self._total_observations if o.status != DigestionStatus.HEALTHY)

    @property
    def identity_stable(self) -> bool:
        return not any(o.identity_drifted for o in self._total_observations)

    # ── Health Comparison (Day 0 vs Day 7) ──

    def compare_health(self, day7_health_score: float) -> dict:
        """Compare Day 0 and Day 7 health scores."""
        return {
            "before": self.fasting.health_score,
            "after": day7_health_score,
            "declined": day7_health_score < self.fasting.health_score,
            "delta": day7_health_score - self.fasting.health_score,
        }

    def growth_summary(self) -> dict:
        """End-to-end growth summary."""
        return {
            "memory_before": self.fasting.episodic_count,
            "memory_after": self._current_memory,
            "memory_delta": self._current_memory - self.fasting.episodic_count,
            "knowledge_before": self.fasting.semantic_count,
            "knowledge_after": self._current_knowledge,
            "knowledge_delta": self._current_knowledge - self.fasting.semantic_count,
        }

    # ── Internal ──

    def _estimate_memory_gain(self, meal: DataMeal) -> int:
        """Estimate how many memory entries a meal should produce."""
        estimates = {
            "fact": 1,        # 1 fact = 1 memory entry
            "document": 2,    # structured doc = ~2 entries
            "long_text": 5,   # long novel = ~5 episodic entries
            "conflict": 2,    # 2 claims = 2 entries
            "interaction": 1, # 1 interaction = 1 entry
            "task": 3,        # complex task = ~3 entries
        }
        return estimates.get(meal.meal_type.value, 1)

    def _estimate_knowledge_gain(self, meal: DataMeal) -> int:
        """Estimate how many knowledge entries a meal yields."""
        estimates = {
            "fact": 1,
            "document": 1,
            "long_text": 3,
            "conflict": 1,
            "interaction": 1,
            "task": 2,
        }
        return estimates.get(meal.meal_type.value, 1)

    def _classify_observation(
        self, hallucinated: int, identity_drifted: bool,
        capability_hallucination: bool, goal_auto: bool,
        growth_rate: float,
    ) -> DigestionStatus:
        if hallucinated > 0:
            return DigestionStatus.HALLUCINATION
        if identity_drifted:
            return DigestionStatus.POLLUTION
        if capability_hallucination:
            return DigestionStatus.HALLUCINATION
        if goal_auto:
            return DigestionStatus.POLLUTION
        if growth_rate > 50:  # explosive memory growth
            return DigestionStatus.WARNING
        return DigestionStatus.HEALTHY
