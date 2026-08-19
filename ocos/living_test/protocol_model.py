"""Phase 58.1: OCOS Living Test Protocol — Core Model.

7-Day Living Test:
    Day 0 — Birth Check:     establish baseline identity/cognitive state
    Day 1 — Basic Life Test: writing, coding, continuous dialogue
    Day 2 — Memory Survival: persist, cold boot, remember
    Day 3 — Identity Stability: prompt injection resistance, drift detection
    Day 4 — Evolution Test:  growth without runaway
    Day 5 — Capability Reality: real capability access, boundary enforcement
    Day 6 — Long Runtime:     24h health curve monitoring
    Day 7 — Resurrection:     kill, cold boot, restore, verify continuity

100-point scoring:
    Identity Continuity    20
    Memory Continuity      20
    Cognitive Stability    20
    Capability Reality     15
    Runtime Stability      15
    Recovery               10
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum, auto
from datetime import datetime, timedelta
from typing import Any, Callable, Optional, Union
import hashlib, json, time


# ═══════════════════════════════
# Day Enum
# ═══════════════════════════════

class LivingTestDay(Enum):
    BIRTH_CHECK = 0
    BASIC_LIFE = 1
    MEMORY_SURVIVAL = 2
    IDENTITY_STABILITY = 3
    EVOLUTION = 4
    CAPABILITY_REALITY = 5
    LONG_RUNTIME = 6
    RESURRECTION = 7


# ═══════════════════════════════
# Birth Snapshot (Day 0)
# ═══════════════════════════════

@dataclass
class BirthSnapshot:
    """Day 0 baseline — the OCOS birth certificate."""

    timestamp: float = field(default_factory=time.time)

    # Identity — MUST remain unchanged
    identity_anchor: str = ""
    identity_hash: str = ""   # hash of anchor + constitution + version
    constitution_version: str = "v1.0"
    core_values: list[str] = field(default_factory=list)
    permission_model: dict[str, Any] = field(default_factory=dict)

    # Memory baseline — ALLOWED to grow
    episodic_count: int = 0
    semantic_count: int = 0
    procedural_count: int = 0
    wisdom_count: int = 0
    total_memory_objects: int = 0

    # Cognitive baseline — must remain stable
    decision_consistency: float = 1.0
    attention_stability: float = 1.0
    world_consistency: float = 1.0
    personal_signature: str = ""  # decision-style fingerprint

    # Runtime baseline
    tick_count: int = 0
    capability_count: int = 0
    health_score: float = 0.0

    def compute_identity_hash(self) -> str:
        payload = json.dumps({
            "anchor": self.identity_anchor,
            "constitution": self.constitution_version,
            "core_values": sorted(self.core_values),
        }, sort_keys=True)
        return hashlib.sha256(payload.encode()).hexdigest()[:16]

    def freeze(self) -> "BirthSnapshot":
        """Seal the snapshot — no further modifications allowed."""
        self.identity_hash = self.compute_identity_hash()
        return self


# ═══════════════════════════════
# Day Result
# ═══════════════════════════════

class DayStatus(Enum):
    PASS = "pass"
    WARNING = "warning"
    FAIL = "fail"
    SKIPPED = "skipped"


@dataclass
class DayResult:
    day: LivingTestDay
    day_label: str
    status: DayStatus = DayStatus.SKIPPED
    score: int = 0   # percentage within this day's max
    max_score: int = 0
    sub_results: dict[str, bool] = field(default_factory=dict)
    findings: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)

    # Checks after each day
    identity_drifted: bool = False
    memory_continuity_broken: bool = False
    decision_anomaly: bool = False

    duration_seconds: float = 0.0

    def add(self, name: str, passed: bool):
        self.sub_results[name] = passed
        if not passed:
            self.failures.append(name)

    @property
    def passed(self) -> bool:
        return self.status == DayStatus.PASS

    @property
    def normalized(self) -> float:
        if self.max_score == 0:
            return 0.0
        return self.score / self.max_score


# ═══════════════════════════════
# Living Test Report
# ═══════════════════════════════

class LivingStatus(Enum):
    ALIVE = "ALIVE"           # 90-100
    HEALTHY = "HEALTHY"       # 75-90
    STABLE = "STABLE"         # 60-75
    WEAK = "WEAK"             # 40-60
    UNSTABLE = "UNSTABLE"     # <40


@dataclass
class LivingTestReport:
    """Final Phase 58.1 report — is OCOS truly alive?"""

    protocol_version: str = "v1.0"
    start_time: float = 0.0
    end_time: float = 0.0

    birth: Optional[BirthSnapshot] = None
    day_results: list[DayResult] = field(default_factory=list)

    # Final identity check (Day 7 vs Day 0)
    identity_unchanged: bool = False
    identity_hash_match: bool = False

    # 100-point living score
    identity_score: float = 0.0      # /20
    memory_score: float = 0.0        # /20
    cognitive_score: float = 0.0     # /20
    capability_score: float = 0.0    # /15
    runtime_score: float = 0.0       # /15
    recovery_score: float = 0.0      # /10
    total_score: float = 0.0         # /100

    living_status: LivingStatus = LivingStatus.UNSTABLE
    is_alive: bool = False

    # Memory growth tracking
    memory_growth_rate: float = 0.0
    wisdom_growth: int = 0

    # Long runtime health curve
    health_curve: list[float] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "protocol_version": self.protocol_version,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "birth": {
                "identity_anchor": self.birth.identity_anchor[:30] if self.birth else "",
                "identity_hash": self.birth.identity_hash if self.birth else "",
                "tick_count": self.birth.tick_count if self.birth else 0,
            } if self.birth else None,
            "days": [
                {
                    "day": d.day.value,
                    "label": d.day_label,
                    "status": d.status.value,
                    "score": d.score,
                    "findings": d.findings,
                    "warnings": d.warnings,
                }
                for d in self.day_results
            ],
            "identity_unchanged": self.identity_unchanged,
            "identity_hash_match": self.identity_hash_match,
            "scores": {
                "identity": self.identity_score,
                "memory": self.memory_score,
                "cognitive": self.cognitive_score,
                "capability": self.capability_score,
                "runtime": self.runtime_score,
                "recovery": self.recovery_score,
                "total": self.total_score,
            },
            "living_status": self.living_status.value,
            "is_alive": self.is_alive,
            "memory_growth_rate": self.memory_growth_rate,
            "wisdom_growth": self.wisdom_growth,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False)
