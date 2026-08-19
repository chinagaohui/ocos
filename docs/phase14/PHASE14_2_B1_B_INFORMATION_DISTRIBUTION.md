# Phase14.2-B1-B Information Distribution Observation

> **Status:** DRAFT v1.1 — Design Review in Progress
> **Date:** 2026-07-22
> **Preceded by:** Phase14.2-B1-A Narrative Boundary (FROZEN ❄️)
> **Purpose:** Define the ABI, scope, and constraints for **information distribution** observation — tracking *where* entities, terms, and references appear across text, while strictly avoiding any inference about *why* they appear.

---

## §0 Core Principle (FROZEN — MUST NOT BE CHANGED)

```
Information distribution measures WHERE information appears.
Information distribution does NOT judge WHY it appears.
信息分布测量信息在哪里出现，不判断为什么出现。
```

### Three Prohibitions (distribution-specific)

| Prohibition | Meaning | Wrong example |
|-------------|---------|---------------|
| Position ≠ Intent | 位置不是意图 | "实体第3章首次出现" → "这是伏笔" ❌ |
| Interval ≠ Effect | 间隔不是效果 | "间隔35000字" → "悬念持续太久" ❌ |
| Count ≠ Importance | 频次不是重要性 | "提及15次" → "这是重要角色" ❌ |

### Allowed / Forbidden Examples

```python
# ✅ ALLOWED — distribution observation
{ "entity_id": "char_lin_ming", "first_seen": 1200, "mention_count": 15, "intervals": [300, 800, 1500] }
{ "term": "时空裂隙", "appearance_count": 7, "chapter_positions": [1, 3, 5, 7, 9, 12, 20] }
{ "reference_distance": [35000, 12000, 8000] }
{ "reference_state_transition": { "reference_id": "X", "previous_state": "OPEN", "current_state": "CLOSED", "transition_position": 24500 } }

# ❌ FORBIDDEN — quality / interpretation / recommendation
{ "important_character": "char_lin_ming" }         # 重要性解释
{ "theme_keyword": "命运" }                         # 语义标签
{ "suspense_duration": 35000 }                     # 读者效果推断
{ "tension_building": true }                       # 效果评价
{ "foreshadow_entity": true }                      # 意图推断
{ "reveal_effective": "well_timed" }               # 质量评价
{ "reader_curiosity": 0.8 }                        # 读者体验推断
{ "payoff_quality": "satisfying" }                 # 结局质量
{ "mystery_creation": "delayed_reveal" }           # 写作手法解释
{ "core_concept": "time_travel" }                  # 概念标签
{ "symbolism": "the_gate" }                        # 符号解读
{ "meaning": "fate_is_unavoidable" }               # 意义解读
{ "information_importance": "high" }               # 信息价值判断
{ "entity_role": "protagonist" }                   # 角色地位
{ "key_information": true }                        # 重要性分类
```

---

## §1 Forward Reference to Phase14.2-A / B1-A

B1-B inherits ALL constraints from previous phases:

| Constraint | Source | Enforcement |
|------------|--------|-------------|
| Output type must be `EvidenceNode` | Phase14.1 Schema §1 | EVX-03/04 |
| Observation payload must be `MetricObservation` or `InformationDistributionObservation` | ABI | Schema check |
| No interpretation fields | Phase14.2 EVX-01 | Validator |
| No capability fields | Phase14.2 EVX-02 | Validator |
| Complete SourceRef required | Phase14.2 EVX-03 | Validator |
| Extractor isolation | Phase14.2 EVX-05 | Validator (recursive) |
| Deterministic output | Phase14.2 EVX-06 | Unit test |
| Schema purity | Phase14.2 EVX-07 | Validator |
| Boundary Purity | B1-A NBX-01 | Validator |
| Position Integrity | B1-A NBX-02 | Validator |
| Deterministic Segmentation | B1-A NBX-03 | Validator |
| Semantic Leakage Scan | B1-A NBX-04 | Validator |
| Vocabulary Restriction | B1-A NBX-05 | Validator |
| Evidence Schema Compatibility | B1-A NBX-06 | Validator |

---

## §2 What B1-B Observes

B1-B measures **information distribution** across a text — tracking entity mentions, term appearances, and the gaps between references. The four observation areas are explicitly scoped to **positional measurement only**.

### 2.1 Entity Mention Distribution

Track where entities appear in the text surface. Pure positional counting — no role, importance, or classification.

**Allowed:**
```python
{
    "entity_id": "char_lin_ming",          # entity identifier only
    "mention_count": 15,                    # total occurrences
    "first_position": 1200,                 # first occurrence offset
    "appearance_positions": [1200, 1500, 2300, ...]  # all positions
}
```

**Forbidden:**
- ❌ `entity_role` — 角色地位（protagonist, antagonist, supporting）
- ❌ `important_character` — 重要性分类
- ❌ `main_character` — 角色地位判断
- ❌ `foreshadow_entity` — 伏笔意图推断
- ❌ `role_in_plot` — 叙事功能解释

### 2.2 Term Appearance Distribution

Track keyword/term occurrences — pure frequency + position.

**Allowed:**

```python
{
    "target_type": "TERM",
    "target_hash": "sha256:...",
    "first_position": BoundaryPosition(...),
    "mention_count": 7,
    "occurrence_positions": [BoundaryPosition(...), ...],
    "interval_distribution": [5000, 12000, 3000]
}
```

**Forbidden:**
- ❌ `theme_keyword` — 主题标签
- ❌ `core_concept` — 核心概念解释
- ❌ `symbolism` — 符号解读
- ❌ `narrative_function` — 叙事功能判断

### 2.3 Reference Distance Measurement

Measure distance between two related references. This is pure arithmetic — no interpretation of "gaps" or "suspense."

**Allowed:**

```python
{
    "distance_type": "SAME_ENTITY_INTERVAL",  # | TERM_INTERVAL | REFERENCE_STATE
    "reference_A_hash": "sha256:...",
    "reference_B_hash": "sha256:...",
    "position_A": BoundaryPosition(...),
    "position_B": BoundaryPosition(...),
    "distance_characters": 35000,
    "distance_chapters": 5
}
```

**Forbidden:**
- ❌ `suspense_duration` — 读者效果推断
- ❌ `tension_building` — 紧张感评价
- ❌ `reader_curiosity` — 读者心理推断
- ❌ `gap_effectiveness` — 间隔效果评级
- ❌ `curiosity_gap` — 好奇心推断
- ❌ `mystery_level` — 神秘感等级

### 2.4 Reference State Transition ⚠️

This is the most delicate observation. The system can only detect that a reference previously marked as unknown **now has a known form** — it cannot know whether a "mystery was resolved" or a "secret was revealed."

**Allowed:**

```python
{
    "transition_type": "REFERENCE_STATE",
    "reference_id": "ref_unknown_017",
    "previous_state": "OPEN",
    "current_state": "CLOSED",
    "transition_position": BoundaryPosition(...),
    "first_mention_position": BoundaryPosition(...)
}
```

**State definitions:**
- `OPEN` — reference appears without contextual resolution (first occurrence of an unknown referent)
- `CLOSED` — the same referent appears in a form that is self-explanatory (context provides resolution)

**Forbidden (explicitly deferred from B1-B):**
- ❌ `reveal_effective` — 透露效果评价 → Phase14.3+
- ❌ `mystery_creation` — 悬念手法分类 → Phase14.3+
- ❌ `payoff_quality` — 收束质量判断 → Phase14.3+
- ❌ `reading_experience` — 阅读体验推断 → Phase14.4+
- ❌ `is_resolved` — "解决"带解释性（改用 state_transition）
- ❌ `mystery_depth` — 谜团深度评级
- ❌ `resolution_satisfaction` — 结局满意度

---

## §3 What B1-B IS NOT

### 3.1 Forbidden observation categories

|| Category | Forbidden examples | Rationale |
||----------|-------------------|-----------|
|| **Importance** | `important_character`, `main_character`, `key_entity`, `information_importance`, `key_information`, `critical_information` | Frequency ≠ importance |
|| **Entity Role** | `entity_role`, `protagonist`, `antagonist`, `supporting_role`, `narrative_function` | Occurrence count ≠ character classification |
|| **Relevance** | `plot_relevance`, `story_significance`, `narrative_weight` | Position ≠ meaning |
|| **Mystery** | `mystery_score`, `suspense_level`, `curiosity_index`, `mystery_depth` | Distance ≠ reader effect |
|| **Foreshadow** | `foreshadow_entity`, `setup_payoff_paired`, `hint_strength` | Timing ≠ intent |
|| **Payoff** | `payoff_quality`, `resolution_satisfaction`, `reveal_effectiveness` | Resolution ≠ quality |
|| **Meaning** | `theme_label`, `core_concept`, `symbolism`, `narrative_function` | Position ≠ interpretation |
|| **Information Value** | `information_value`, `information_weight`, `essential`, `core_information`, `major`, `minor` | Presence ≠ importance |
|| **Evaluation** | Reader reaction, Suspense score, Narrative effectiveness, Quality evaluation | All deferred to Phase14.3+ |

### 3.2 Explicitly deferred to later phases

| Feature | Reason | Target |
|---------|--------|--------|
| Reader reaction prediction | Requires reader-effect model | Phase14.4+ |
| Suspense / tension scoring | Requires subjective interpretation | Phase14.4+ |
| Narrative effectiveness evaluation | Requires Principle layer | Phase14.3+ |
| Quality evaluation | Requires Capability Evaluation | Phase14.5+ |
| Writing recommendation | Capability layer | Phase14.5+ |

---

## §4 ABI — InformationDistributionObservation

```python
@dataclass(frozen=True)
class InformationDistributionObservation:
    """Records where target entities/terms appear across the text surface.

    Measures position ONLY. No interpretation, no quality, no intent.
    Observations are tuples of `MetricObservation` for schema consistency.
    """
    metric_type: str                              # e.g. "ENTITY_DISTRIBUTION" | "TERM_DISTRIBUTION"
                                                  #       | "REFERENCE_DISTANCE" | "REFERENCE_STATE"
    source_ref: SourceRef                         # complete source reference
    observations: tuple[MetricObservation, ...]   # ordered measurements (position, count, intervals)
    extraction_version: str                       # semver-compatible version string
```

### ABI constraints

- **Frozen dataclass** — immutable after construction
- `metric_type` must be one of: `ENTITY_DISTRIBUTION`, `TERM_DISTRIBUTION`, `REFERENCE_DISTANCE`, `REFERENCE_STATE`
- `observations` contain only `MetricObservation` instances — no nested custom dataclasses
- All `MetricObservation` field names must pass IBX-01 (Observation Purity) and IBX-07 (Cross-layer Isolation)
- All integer distances are non-negative
- No optional fields — every observation must be complete

### Forbidden fields (MUST NOT appear in any observation)

```python
# Blocked by IBX-01 (Observation Purity) + NBX-05 (Vocabulary Restriction)
FORBIDDEN_DISTRIBUTION_FIELDS = {
    # Original distribution fields
    "importance", "relevance", "mystery", "foreshadow",
    "payoff", "meaning", "suspense", "tension",
    "reader_curiosity", "symbolism", "theme_label",
    "narrative_function", "effectiveness", "quality",
    "intent", "purpose", "role", "function",
    "core_concept", "significance",
    # Entity-specific
    "entity_role", "main_character", "important_character",
    "protagonist", "antagonist", "supporting_role",
    # Information value (Patch 1)
    "information_importance", "information_value", "information_weight",
    "critical_information", "key_information", "essential",
    "core_information", "major", "minor",
    # Term-specific
    "theme_keyword", "symbolic_term", "important_term",
    # Reference Distance / State
    "suspense_duration", "curiosity_gap", "tension_gap", "mystery_level",
    "gap_effectiveness", "is_resolved", "mystery_depth", "resolution_satisfaction",
    # Cross-layer interpretation (IBX-07)
    "setup", "reveal", "climax", "hook", "filler",
}

# Blocked by IBX-07 (Cross-layer Isolation) — semantic interpretation vocabulary
# These words are forbidden as metric_name prefixes, field names, tags, or metadata
FORBIDDEN_CROSS_LAYER_VOCABULARY = {
    "foreshadow", "payoff", "setup", "reveal", "mystery",
    "suspense", "meaning", "symbolism", "theme", "climax",
    "hook", "filler", "tension", "pacing_quality",
    "narrative_effect", "reader_engagement",
}
```

---

## §5 InformationDistributionObservation Extractor

**extractor_id**: `narrative_information_distribution_v1`

### Input

Preprocessed text + entity/term index.

### Output

```python
{
    "evidence_type": "INFORMATION_DISTRIBUTION",
    "observation": InformationDistributionObservation,
    "source_ref": SourceRef,
    "confidence": 1.0,                      # fixed — structural measurement is deterministic
}
```

### Internal structure

```
NarrativeInformationDistributionExtractor
├── EntityPositionCollector
│   └── scan(text, entity_index) → entity_occurrence_map
├── TermPositionCollector
│   └── scan(text, term_index) → term_occurrence_map
├── ReferenceDistanceCalculator
│   └── compute(occurrence_map) → distance_analysis
└── ReferenceStateTransitionDetector
    └── scan_reference_states(text) → state_transitions
```

### Component Constraints

|| Component | Allowed | Forbidden |
||-----------|---------|-----------|
|| EntityPositionCollector | Entity id, mention count, position | Entity role, importance, class, character classification |
|| TermPositionCollector | Term text, count, positions | Theme, concept, symbol, importance classification |
|| ReferenceDistanceCalculator | Absolute distance in chars/chapters | Gap quality, suspense score, mystery level, curiosity inference |
|| ReferenceStateTransitionDetector | OPEN→CLOSED state transition, distance | Reveal quality, payoff assessment, resolution satisfaction |

---

## §6 B1-B Gates (Inherited + New)

### Inherited gates from B1-A

All G1–G7 and NBX-01–06 apply unchanged.

### New gates: IBX-01 through IBX-08

| # | Criteria | Verification Method |
|---|----------|-------------------|
| **IBX-01** | **Observation Purity** — No forbidden distribution fields (importance, relevance, mystery, foreshadow, payoff, meaning, entity_role, information_value, etc.) in any output | Recursive scan of observation fields against `FORBIDDEN_DISTRIBUTION_FIELDS` |
| **IBX-02** | **Schema Integrity** — All `InformationDistributionObservation` instances match the ABI: valid `metric_type`, all observations are `MetricObservation`, no extra fields, no optional fields | Schema validation per observation |
| **IBX-03** | **Position Integrity** — All BoundaryPosition values valid (start < end, locator_hash present); interval_distribution non-negative; occurrence_positions ascending | Schema validation per observation |
| **IBX-04** | **Semantic Leakage** — Input containing interpretation vocabulary (foreshadow, suspense, mystery, payoff, setup, reveal) does not leak into observation field names, values, metric_name, or tags | `TestSemanticLeakageDistribution` — recursive scan of all output fields |
| **IBX-05** | **Vocabulary Restriction** — No term/entity observations carry theme_label, symbolic_term, important_term, core_concept, or any vocabulary from `FORBIDDEN_DISTRIBUTION_FIELDS` | Recursive scan of metric_name, tags, and observation field names |
| **IBX-06** | **Deterministic Extraction** — Same input text + same extractor_version + same configuration → identical hash(observation). 3 consecutive runs must produce byte-identical output. Required for EvidenceStore append-only integrity. | 3× repeat run + SHA-256 hash comparison of serialized output |
| **IBX-07** | **Cross-layer Isolation** — Recursive scan across observation, metadata, metric_name, unit, tags for `FORBIDDEN_CROSS_LAYER_VOCABULARY` (foreshadow, payoff, setup, reveal, mystery, suspense, meaning, symbolism, theme, climax, hook, filler, tension, pacing_quality, narrative_effect, reader_engagement) | Recursive vocabulary scan of all output fields including nested MetricObservation components |
| **IBX-08** | **Evidence Compatibility** — All outputs conform to EvidenceNode append-only rules: version must be extractor_version, source_ref must be complete, no overwrite of previous evidence; compatible with Phase14.1 Evidence Schema | Schema check + VersionIsolation test + append-only mock store test |

---

## §7 Entry Criteria for B1-B Implementation

| # | Criterion | Verification |
|---|-----------|-------------|
| E01 | Phase14.2-B1-A FROZEN | Gate report filed ✅ |
| E02 | All outputs are `EvidenceNode` | ABI compliance |
| E03 | Observation Purity — no forbidden fields | IBX-01 enforcement |
| E04 | Semantic Leakage — no interpretation vocabulary leaks | IBX-04 enforcement |
| E05 | Vocabulary Restriction — no theme/symbol/classified labels | IBX-05 enforcement |
| E06 | Complete `SourceRef` | EVX-03 enforcement |
| E07 | Deterministic output — byte-identical on repeat | IBX-06 test |
| E08 | Cross-layer Isolation — no foreshadow/payoff/setup/reveal vocabulary | IBX-07 enforcement |
| E09 | Phase14.1 / B1-A tests unchanged | Regression check |
| E10 | This document approved | Design review sign-off |

---

## §8 Implementation Order

| Step | Component | Output | Precondition |
|------|-----------|--------|-------------|
| ① | `InformationDistributionObservation` ABI (contract) | `contracts/information_distribution.py` | None |
| ② | EntityPositionCollector | Entity mention scanning against text | ABI stable |
| ③ | TermPositionCollector | Term appearance tracking | ABI stable |
| ④ | ReferenceDistanceCalculator | Distance computation from occurrence map | Collector stable |
| ⑤ | ReferenceStateTransitionDetector | OPEN→CLOSED state transition detection | Distance calculator stable |
| ⑥ | NarrativeInformationDistributionExtractor (integration) | Full pipeline | All components stable |
| ⑦ | Validator extension (IBX-01~08) | `evidence_validator.py` update | ABI + extractor stable |
| ⑧ | Tests | Unit + integration + semantic leakage + version isolation + deterministic hash | All code stable |
| ⑨ | Gate report + freeze | `PHASE14_2_B1_B_GATE_REPORT.md` | All tests pass |

---

## §9 Design Review Signature

|| Role | Action |
||------|--------|
|| Architecture Review | ✅ Approve §0 Core Principle — 2026-07-22 |
|| Architecture Review | ✅ Approve §2 Observation scope — 2026-07-22 |
|| Architecture Review | ✅ Approve §4 ABI — 2026-07-22 |
|| Architecture Review | ✅ Approve §6 Gates (IBX-01~08) — 2026-07-22 |
|| Implementation | ✅ Confirm all forbidden items deferred to appropriate future phase — 2026-07-22 |
|| **Freeze Status** | **Phase14.2-B1-B v1.1 APPROVED FOR IMPLEMENTATION ❄️** |
|| **Implementation Freeze** | **Phase14.2-B1-B FROZEN ❄️ 2026-07-22 — 8/8 IBX gates PASS, 55/55 tests PASS** |
|| **Freeze Review** | ✅ **FROZEN ❄️ — Approved by architecture lead: 8/8 IBX PASS, 55/55 tests PASS, Observation purity confirmed** |

---

*Information distribution measures what the text CONTAINS, not what the author INTENDS.*
