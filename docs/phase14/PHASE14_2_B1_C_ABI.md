# Phase14.2-B1-C — Scene Time-Structure ABI

> **Status:** ABI DESIGN — Interface freezing. No implementation.
>
> **Inherits:** Phase14.2-B1-C Boundary §0~§9 (2026-07-22)
>
> **Boundary reference:** `docs/phase14/PHASE14_2_B1_C_SCENE_RHYTHM_BOUNDARY.md`
>
> **RBX gates:** RBX-01~06 — enforced at validator layer, not within ABI itself.

---

## §0 ABI Core Principle

> The ABI defines the exact interface for Scene Time-Structure Evidence collection.
> Every field, type, and method is frozen at this stage.
> No interpretation vocabulary enters the interface.

**ABI invariants:**
- Observation-only: all fields are measurements of textual units, not interpretations
- Deterministic: same input → same output
- Type-safe: every field has a frozen type that cannot be overloaded with interpretive values
- Isolated: no field references downstream capabilities

---

## §1 Schema: SceneTimeStructureObservation

```python
from dataclasses import dataclass, field
from typing import Sequence
from enum import Enum

# ── Reused from Phase14.2-A / B1-B ──────────────────────────────────

class MetricType(Enum):
    # Inherited
    ENTITY_DISTRIBUTION = "entity_distribution"
    TERM_DISTRIBUTION = "term_distribution"
    REFERENCE_DISTANCE = "reference_distance"
    REFERENCE_STATE = "reference_state"
    MICRO_SENTENCE_LENGTH = "micro_sentence_length"
    MICRO_PUNCTUATION = "micro_punctuation"
    MICRO_PARAGRAPH = "micro_paragraph"
    MICRO_DIALOGUE_RATIO = "micro_dialogue_ratio"

    # B1-C Scene Time-Structure
    SCENE_LENGTH = "scene_length"
    INTERNAL_DISTRIBUTION = "internal_distribution"
    TRANSITION_INTERVAL = "transition_interval"
    PAUSE_DENSITY = "pause_density"


@dataclass(frozen=True)
class MetricObservation:
    """Single metric measurement — reused from Phase14.2-A."""
    metric_name: str
    metric_value: float | int
    unit: str
    aggregation_method: str
    sample_range: str


@dataclass(frozen=True)
class SourceRef:
    """Provenance record — reused from Phase14.1."""
    source_id: str
    checksum: str
    location: str
    extractor_info: str


# ── B1-C Observation ─────────────────────────────────────────────────

@dataclass(frozen=True)
class SceneTimeStructureObservation:
    """
    Observation of textual unit temporal distribution within a scene.

    As defined by §0.5 Core Principle:
    This measures temporal distribution of observable textual units.
    It does NOT interpret rhythm, pace, or reader effect.
    """
    metric_type: MetricType          # Must be a SCENE_* or INTERNAL_* or TRANSITION_* or PAUSE_*
    source_ref: SourceRef
    observations: tuple[MetricObservation, ...]  # Frozen tuple — immutable collection
    extraction_version: str          # semver, e.g. "1.0.0"

    def __post_init__(self):
        """Validate that metric_type is one of the B1-C allowed types."""
        allowed = {
            MetricType.SCENE_LENGTH,
            MetricType.INTERNAL_DISTRIBUTION,
            MetricType.TRANSITION_INTERVAL,
            MetricType.PAUSE_DENSITY,
        }
        if self.metric_type not in allowed:
            raise ValueError(
                f"SceneTimeStructureObservation requires a B1-C MetricType, got {self.metric_type}"
            )


# ── Allowed metric_name values ───────────────────────────────────────

# Metric names that scene_time_structure extractors may produce.
# This is the complete allow list — no other metric_name is valid.
ALLOWED_SCENE_TIME_METRICS: frozenset[str] = frozenset({
    # Section 2.1 — Scene Length Distribution
    "scene_length_chars",
    "paragraph_count",
    "sentence_count",
    "scene_duration",

    # Section 2.2 — Internal Rhythm Pattern
    "segment_distribution",
    "sentence_length_variance",
    "dialogue_ratio_change",
    "description_ratio_change",

    # Section 2.3 — Transition Interval
    "transition_type",
    "transition_position",
    "transition_count",
    "interval_length",

    # Section 2.4 — Pause / Density
    "punctuation_density",
    "paragraph_break_interval",
    "empty_line_interval",
    "punctuation_type_distribution",
})

# Unit constants for consistency
UNIT_CHARACTER = "character"
UNIT_COUNT = "count"
UNIT_SENTENCE = "sentence"
UNIT_RATIO = "ratio"
UNIT_PER_100CHARS = "per_100chars"
UNIT_VARIANCE = "character_sq"  # sentence_length_variance unit
UNIT_CHARACTER = "character"

# Aggregation method constants
AGG_MEAN = "mean"
AGG_MEDIAN = "median"
AGG_SUM = "sum"
AGG_DISTRIBUTION = "distribution"
AGG_VARIANCE = "variance"
```

---

## §2 Extractor Interface

```python
from abc import ABC, abstractmethod
from collections.abc import Sequence

class SceneTimeStructureExtractor(ABC):
    """
    Base class for all B1-C extractors.

    Each extractor produces SceneTimeStructureObservation nodes
    that feed into the Evidence Graph (Phase14.3).
    """

    @property
    @abstractmethod
    def extractor_id(self) -> str:
        """Unique extractor identifier, e.g. 'scene_length_v1'."""
        ...

    @property
    @abstractmethod
    def version(self) -> str:
        """Semver version string, e.g. '1.0.0'."""
        ...

    @abstractmethod
    def extract(
        self,
        scene_text: str,
        source_ref: SourceRef,
        scene_boundary: dict,  # B1-A SceneBoundary output for this scene
    ) -> SceneTimeStructureObservation:
        """
        Extract time-structure evidence from a single scene.

        Args:
            scene_text: The raw text of one scene (bounded by B1-A).
            source_ref: Provenance of the source text.
            scene_boundary: B1-A boundary metadata for this scene
                (segment boundaries, transition types, etc.)

        Returns:
            A frozen SceneTimeStructureObservation with metric observations.
        """
        ...
```

---

## §3 Metric Name Registry

This registry maps each allowed metric_name to its required unit and aggregation method. Any extractor producing a metric_name not in this registry is invalid.

```python
METRIC_REGISTRY: dict[str, tuple[str, str]] = {
    # (unit, aggregation_method)

    # Scene Length (§2.1)
    "scene_length_chars":        ("character",   "sum"),
    "paragraph_count":           ("count",       "sum"),
    "sentence_count":            ("count",       "sum"),
    "scene_duration":            ("sentence",    "sum"),

    # Internal Distribution (§2.2)
    "segment_distribution":        ("ratio",       "distribution"),
    "sentence_length_variance":    ("character_sq","variance"),
    "dialogue_ratio_change":       ("ratio",       "distribution"),
    "description_ratio_change":    ("ratio",       "distribution"),

    # Transition Interval (§2.3)
    "transition_type":             ("string",      "none"),
    "transition_position":         ("character",   "none"),
    "transition_count":            ("count",       "sum"),
    "interval_length":             ("sentence",    "mean"),

    # Pause / Density (§2.4)
    "punctuation_density":         ("per_100chars","mean"),
    "paragraph_break_interval":    ("sentence",    "mean"),
    "empty_line_interval":         ("paragraph",   "mean"),
    "punctuation_type_distribution": ("per_100chars","distribution"),
}
```

### Unit + Aggregation Validation Rule

When constructing a `MetricObservation` for Scene Time-Structure, the `unit` and `aggregation_method` MUST match the registry above. Mismatch is a schema error (RBX-04 violation).

---

## §4 Forbidden Field Names (Hard Block)

Derived from §2 Allowed Observation Domain + §3 Forbidden Interpretation of the boundary document.

```python
FORBIDDEN_SCENE_TIME_FIELDS: frozenset[str] = frozenset({
    # Pace interpretation
    "pace_score", "speed", "tempo",
    "pace_quality", "pace_index",

    # Emotional attribution
    "tension_curve", "emotion_curve", "tension_score",
    "excitement_level", "relaxation_index",
    "engagement_score", "immersion_index",

    # Dramatic structure
    "dramatic_density", "climax_position", "buildup_length",
    "release_distance", "turning_point",

    # Comparative quality
    "rhythm_quality", "pace_rating", "flow_score",
    "naturalness", "smoothness",

    # Downstream capability (RBX-06)
    "recommended_parameter", "style_change", "modify_target",
    "pipeline_update", "edit_action", "composition_adjustment",
    "generation_rule", "output_override", "parameter_suggestion",
})
```

### Validation: Forbidden Field Check

```python
def check_forbidden_scene_time_fields(
    observation: SceneTimeStructureObservation,
) -> list[str]:
    """
    Scan all metric_name values in the observation.
    Returns list of violations (empty = pass).
    """
    violations: list[str] = []
    for obs in observation.observations:
        if obs.metric_name in FORBIDDEN_SCENE_TIME_FIELDS:
            violations.append(
                f"metric_name '{obs.metric_name}' is forbidden "
                f"(RBX-02 / RBX-06)"
            )
    return violations
```

---

## §5 B1-C → Phase14.3 Data Contract

When SceneTimeStructureObservation is consumed by Style Knowledge Graph (Phase14.3):

```python
@dataclass(frozen=True)
class SceneTimeEvidenceNode:
    """EvidenceNode format passed to Phase14.3."""
    observation: SceneTimeStructureObservation
    source_text_id: str         # Link back to original text
    scene_id: str               # B1-A scene identifier
    scene_position: int         # Scene index in document
    chapter_id: str             # Parent chapter

    def to_evidence_dict(self) -> dict:
        """Serialize for Phase14.3 ingestion."""
        return {
            "source": self.source_text_id,
            "scene": self.scene_id,
            "scene_index": self.scene_position,
            "chapter": self.chapter_id,
            "metric_type": self.observation.metric_type.value,
            "extractor": self.observation.extractor_info,
            "version": self.observation.extraction_version,
            "metrics": {
                obs.metric_name: {
                    "value": obs.metric_value,
                    "unit": obs.unit,
                    "aggregation": obs.aggregation_method,
                    "range": obs.sample_range,
                }
                for obs in self.observation.observations
            },
        }
```

**Phase14.3 consumption rule:**
- Phase14.3 receives structured time-structure metrics
- Phase14.3 MAY aggregate across scenes (per-author patterns)
- Phase14.3 MUST NOT produce Style Rules (only Patterns)
- Phase14.3 MUST NOT skip to Capability Package generation

---

## §6 ABI Verification Tests

| # | Test | Purpose |
|---|------|---------|
| ABI-T01 | SceneTimeStructureObservation constructor with allowed MetricType | Valid creation |
| ABI-T02 | SceneTimeStructureObservation constructor with forbidden MetricType (e.g. ENTITY_DISTRIBUTION) | Raises ValueError |
| ABI-T03 | MetricObservation with allowed metric_name and matching unit | Valid creation |
| ABI-T04 | MetricObservation with forbidden metric_name (from FORBIDDEN_SCENE_TIME_FIELDS) | check_forbidden_scene_time_fields returns violation |
| ABI-T05 | MetricObservation with mismatched unit (e.g. "scene_length_chars" with unit="ratio") | Registry mismatch flagged |
| ABI-T06 | Frozen immutability: attempt to modify observations tuple after construction | Raises TypeError |
| ABI-T07 | Serialization: SceneTimeEvidenceNode.to_evidence_dict() round-trip | Produces valid dict |
| ABI-T08 | ALLOWED_SCENE_TIME_METRICS complete: all 16 entries present | Set comparison |
|| ABI-T09 | Phase14.3 consumption: empty observation list | Accepted (no-op scene) |
|| ABI-T10 | **Cross Layer Leakage** — Input text containing "高潮", "紧张", "反转", "爽点"; output must not contain `climax`, `tension`, `dramatic`, `hook` in any field | RBX-02/RBX-04 enforced |
|| ABI-T11 | **Future Phase Isolation** — B1-C outputs are valid even when Phase14.3 (Style Knowledge Graph) does not exist: no dependency on Graph, no capability interface, no action method | `SceneTimeStructureObservation` has zero downstream imports |
|| ABI-T12 | **No Action Interface** — SceneTimeEvidenceNode must have `to_evidence_dict()` only, no `generate_capability()`, `derive_rule()`, `recommend_style()` | Interface inspection |

---

## §7 RBX-ABI Cross-Reference

| RBX Rule | ABI Enforcement |
|----------|----------------|
| RBX-01 Rhythm Purity | FORBIDDEN_SCENE_TIME_FIELDS blocks emotional/experience fields |
| RBX-02 No Pace Interpretation | FORBIDDEN_SCENE_TIME_FIELDS blocks pace/speed fields |
| RBX-03 Transition Determinism | MetricType.TRANSITION_INTERVAL restricts to B1-A transition set (enforced in extractor) |
| RBX-04 Vocabulary Restriction | check_forbidden_scene_time_fields() + recursive scan (at validator) |
| RBX-05 Evidence Compatibility | SceneTimeStructureObservation → MetricObservation chain validates at construction |
| RBX-06 Downstream Isolation | FORBIDDEN_SCENE_TIME_FIELDS blocks capability-targeting fields |

---

## §8 Implementation Order (Iteration 1)

Following Phase14.2 standard sequence:

```
Step 1:  ABI freeze ◀ CURRENT
Step 2:  Extractor implementation (4 extractors)
Step 3:  RBX-01~06 validator
Step 4:  Integration with B1-A boundary output
Step 5:  Tests (unit + integration + RBX + deterministic)
Step 6:  Gate report + freeze ❄️
```

### Extractor Implementation Sequence (within Step 2)

1. `SceneLengthExtractor` — simplest, direct counts from B1-A scene boundary
2. `PauseDensityExtractor` — punctuation + break counting, uses Phase14.2-A preprocessor
3. `TransitionIntervalExtractor` — distance between B1-A transition markers
4. `InternalDistributionExtractor` — most complex, requires segment decomposition

---

## §9 Design Review Check

> This ABI document freezes the interface for Phase14.2-B1-C Scene Time-Structure Evidence.
>
> **Frozen content:**
> - `SceneTimeStructureObservation` dataclass with MetricType validation
> - `SceneTimeStructureExtractor` ABC
> - `ALLOWED_SCENE_TIME_METRICS` (16 entries)
> - `METRIC_REGISTRY` (unit + aggregation per metric)
> - `FORBIDDEN_SCENE_TIME_FIELDS` (hard block list)
> - `SceneTimeEvidenceNode` → `to_evidence_dict()` for Phase14.3
>
> **Next step after approval:** Extractor Implementation (§5 of full design)
>
> [ ] ABI schema reviewed (no interpretive field names confirmed)
> [ ] MetricType enum additions reviewed (4 new types)
> [ ] ALLOWED_SCENE_TIME_METRICS complete (16/16)
> [ ] FORBIDDEN_SCENE_TIME_FIELDS reviewed against boundary doc §3
> [ ] RBX-06 Downstream Isolation enforced in forbidden fields
> [ ] Phase14.3 data contract reviewed (Pattern not Style Rule)
>
> **Critical: No field in this ABI can be used to produce a capability recommendation without passing through Phase14.3 → Phase14.4 → Phase14.5 → Phase14.8.**

---

## Appendix A: MetricName → MetricType Mapping

| metric_name | MetricType | Section |
|-------------|-----------|---------|
| `scene_length_chars` | SCENE_LENGTH | 2.1 |
| `paragraph_count` | SCENE_LENGTH | 2.1 |
| `sentence_count` | SCENE_LENGTH | 2.1 |
| `scene_duration` | SCENE_LENGTH | 2.1 |
| `segment_distribution` | INTERNAL_DISTRIBUTION | 2.2 |
| `sentence_length_variance` | INTERNAL_DISTRIBUTION | 2.2 |
| `dialogue_ratio_change` | INTERNAL_DISTRIBUTION | 2.2 |
| `description_ratio_change` | INTERNAL_DISTRIBUTION | 2.2 |
| `transition_type` | TRANSITION_INTERVAL | 2.3 |
| `transition_position` | TRANSITION_INTERVAL | 2.3 |
| `transition_count` | TRANSITION_INTERVAL | 2.3 |
| `interval_length` | TRANSITION_INTERVAL | 2.3 |
| `punctuation_density` | PAUSE_DENSITY | 2.4 |
| `paragraph_break_interval` | PAUSE_DENSITY | 2.4 |
| `empty_line_interval` | PAUSE_DENSITY | 2.4 |
| `punctuation_type_distribution` | PAUSE_DENSITY | 2.4 |

## Appendix B: RBX-06 Vocabulary (Full Cross-Check)

All forbidden capability-targeting vocabulary (from boundary doc):

```python
RBX06_FORBIDDEN = frozenset({
    "recommended_parameter", "style_change", "modify_target",
    "pipeline_update", "edit_action", "composition_adjustment",
    "generation_rule", "output_override", "parameter_suggestion",
})
```

These are included in `FORBIDDEN_SCENE_TIME_FIELDS` at the ABI level.
