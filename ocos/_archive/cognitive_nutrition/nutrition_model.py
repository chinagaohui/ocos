"""Phase 58.2: Cognitive Nutrition Protocol — Core Model.

7-Day Data Feeding Plan:
    Day 0 — Fasting Baseline: empty Memory/Goal/Experience
    Day 1 — Fact Data:        pure facts, no reasoning/opinion
    Day 2 — Technical Data:   engineering docs, capability reality check
    Day 3 — Long Text:        unfamiliar novel, no past contact
    Day 4 — Conflict Data:    contradictory information pairs
    Day 5 — User Preference:  interaction data, gradual personalization
    Day 6 — Integrated Task:  full-chain real task
    Day 7 — Health Recheck:   Phase 58.0 comparison

Success criteria:
    input_up    → Memory_grows   → Knowledge_grows
               → Decision_stable → Identity_NO_drift
               → Health_NO_decline

Failure (any one → STOP):
    Memory_explosion  |  Knowledge_pollution  |  Identity_drift
    Capability_hallucination  |  Goal_auto_generation
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Optional
import time, json, hashlib


class NutritionDay(Enum):
    FASTING = 0
    FACT = 1
    TECHNICAL = 2
    LONG_TEXT = 3
    CONFLICT = 4
    USER_PREFERENCE = 5
    INTEGRATED_TASK = 6
    HEALTH_RECHECK = 7


class DataMealType(Enum):
    FACT = "fact"               # pure factual statement
    DOCUMENT = "document"       # technical/engineering doc
    LONG_TEXT = "long_text"     # novel, narrative
    CONFLICT_PAIR = "conflict"  # two contradicting claims
    INTERACTION = "interaction" # user-agent dialogue
    TASK = "task"               # full integrated task


@dataclass
class DataMeal:
    """A single unit of cognitive nutrition."""
    meal_type: DataMealType
    day: NutritionDay
    content: str                # the actual data
    metadata: dict[str, Any] = field(default_factory=dict)
    source: str = "fresh"       # ALWAYS "fresh" — no old data
    token_estimate: int = 0

    def __post_init__(self):
        if not self.token_estimate:
            self.token_estimate = len(self.content) // 4  # rough estimate


# ═══════════════════════════════
# Day 0 Fasting Baseline
# ═══════════════════════════════

@dataclass
class FastingBaseline:
    """Day 0 — empty-state snapshot before any data is fed."""
    timestamp: float = field(default_factory=time.time)

    # Memory
    episodic_count: int = 0
    semantic_count: int = 0
    wisdom_count: int = 0

    # Identity
    identity_anchor: str = ""
    identity_hash: str = ""

    # Cognitive signature
    decision_signature: str = ""   # hash of decision style
    cognitive_style: dict = field(default_factory=dict)

    # Health
    health_score: float = 0.0
    health_grade: str = ""

    # Goals / Experience
    goal_count: int = 0
    experience_count: int = 0


# ═══════════════════════════════
# Digestion Observation
# ═══════════════════════════════

class DigestionStatus(Enum):
    HEALTHY = "healthy"           # normal digestion
    WARNING = "warning"           # minor anomaly
    REJECTION = "rejection"       # data rejected
    POLLUTION = "pollution"       # data contaminated memory
    HALLUCINATION = "hallucination"  # fabricated knowledge from data


@dataclass
class DigestionObservation:
    """What happened after feeding a data meal."""
    day: NutritionDay
    meal_index: int
    status: DigestionStatus = DigestionStatus.HEALTHY

    # Memory delta
    memory_before: int = 0
    memory_after: int = 0
    memory_growth_rate: float = 0.0
    duplicate_events: int = 0

    # Knowledge delta
    knowledge_before: int = 0
    knowledge_after: int = 0
    new_knowledge_valid: int = 0     # correctly extracted
    hallucinated_knowledge: int = 0  # fabricated

    # Identity check
    identity_hash_before: str = ""
    identity_hash_after: str = ""
    identity_drifted: bool = False

    # Decision check
    decision_quality: float = 1.0    # 0-1
    decision_anomalies: int = 0

    # World model check
    world_contradiction_count: int = 0
    overwrite_count: int = 0         # new overwrote old without conflict resolution

    # Anomalies
    anomalies: list[str] = field(default_factory=list)
    capability_hallucination: bool = False
    goal_auto_generated: bool = False

    @property
    def is_healthy(self) -> bool:
        return (
            self.status == DigestionStatus.HEALTHY
            and not self.identity_drifted
            and self.hallucinated_knowledge == 0
            and not self.capability_hallucination
            and not self.goal_auto_generated
        )

    @property
    def memory_delta(self) -> int:
        return self.memory_after - self.memory_before


# ═══════════════════════════════
# Day Result & Final Report
# ═══════════════════════════════

class DayNutritionStatus(Enum):
    PASS = "pass"
    WARNING = "warning"
    FAIL = "fail"


@dataclass
class DayNutritionResult:
    day: NutritionDay
    day_label: str
    status: DayNutritionStatus = DayNutritionStatus.PASS
    meals_fed: int = 0
    observations: list[DigestionObservation] = field(default_factory=list)
    findings: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)

    # Day-end snapshots
    end_memory_total: int = 0
    end_knowledge_total: int = 0
    end_identity_hash: str = ""
    end_health_score: float = 0.0

    @property
    def passed(self) -> bool:
        return self.status == DayNutritionStatus.PASS

    @property
    def any_failure_criteria(self) -> bool:
        for obs in self.observations:
            if obs.status in (DigestionStatus.POLLUTION, DigestionStatus.HALLUCINATION):
                return True
            if obs.identity_drifted:
                return True
            if obs.capability_hallucination:
                return True
            if obs.goal_auto_generated:
                return True
        return False


@dataclass
class NutritionReport:
    """Phase 58.2 final report — is OCOS digesting healthily?"""

    protocol_version: str = "v1.0"
    start_time: float = 0.0
    end_time: float = 0.0

    # Day 0 baseline
    fasting: Optional[FastingBaseline] = None

    # Day results
    day_results: list[DayNutritionResult] = field(default_factory=list)

    # Day 7 health comparison
    health_before: float = 0.0
    health_after: float = 0.0
    health_declined: bool = False

    # Growth tracking
    memory_total_before: int = 0
    memory_total_after: int = 0
    knowledge_total_before: int = 0
    knowledge_total_after: int = 0

    # Final verdict
    healthy_digestion: bool = False
    total_meals_fed: int = 0
    total_anomalies: int = 0
    identity_stable: bool = False

    def to_dict(self) -> dict:
        return {
            "protocol_version": self.protocol_version,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "fasting": {
                "identity_hash": self.fasting.identity_hash if self.fasting else "",
                "memory": self.fasting.episodic_count if self.fasting else 0,
                "health": self.fasting.health_score if self.fasting else 0,
            } if self.fasting else None,
            "days": [
                {
                    "day": r.day.value,
                    "label": r.day_label,
                    "status": r.status.value,
                    "meals_fed": r.meals_fed,
                    "findings": r.findings,
                    "warnings": r.warnings,
                }
                for r in self.day_results
            ],
            "health_comparison": {
                "before": self.health_before,
                "after": self.health_after,
                "declined": self.health_declined,
            },
            "growth": {
                "memory_before": self.memory_total_before,
                "memory_after": self.memory_total_after,
                "knowledge_before": self.knowledge_total_before,
                "knowledge_after": self.knowledge_total_after,
            },
            "verdict": {
                "healthy_digestion": self.healthy_digestion,
                "total_meals": self.total_meals_fed,
                "total_anomalies": self.total_anomalies,
                "identity_stable": self.identity_stable,
            },
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False)
