# Phase14.2-B1 Narrative Observation Boundary Contract

> **Status:** APPROVED ✅ — Signed by Architecture Review
> **Signed:** 2026-07-22
> **Preceded by:** Phase14.2-A (FROZEN ❄️)
> **Purpose:** Define the observation boundary for **narrative structure** extraction, preventing drift from structural measurement into plot evaluation.

---

## §0 Core Principle (FROZEN — MUST NOT BE CHANGED)

```
Narrative observation measures story structure.
Narrative observation does NOT evaluate story quality.
叙事观察测量故事结构，不评价故事质量。
```

### Three Prohibitions (narrative-specific)

| Prohibition | Meaning | Wrong example |
|-------------|---------|---------------|
| Structure ≠ Quality | 结构不是质量 | "场景转换12次" → "节奏紧凑" ❌ |
| Distance ≠ Judgment | 距离不是优劣 | "伏笔3000字后回收" → "悬念设计好" ❌ |
| Pattern ≠ Recommendation | 模式不是建议 | "每章3个事件" → "应该增加事件密度" ❌ |

### Allowed / Forbidden Examples

```python
# ✅ ALLOWED — structural observation
{ "scene_transition_count": 12 }
{ "chapter_event_count": 5 }
{ "information_gap": 3000 }            # 新信息到引用的距离
{ "setup_position": 120 }
{ "payoff_position": 3120 }
{ "pov_switch_count": 3 }

# ❌ FORBIDDEN — quality / interpretation / recommendation
{ "pacing_quality": "good" }            # 评价
{ "suspense_effective": true }          # 解释
{ "cliffhanger_intensity": 7.5 }        # 评分
{ "reader_engagement_estimate": 0.8 }   # 读者效果推断
{ "scene_tension": "high" }             # 语义标签
{ "story_flow": "smooth" }              # 价值判断
{ "should_increase_events": True }      # 建议
```

---

## §1 Forward Reference to Phase14.2-A

All narrative extractors inherit the same architecture constraints as micro-text extractors:

| Constraint | Source | Enforcement |
|------------|--------|-------------|
| Output type must be `EvidenceNode` | Phase14.1 Schema §1 | EVX-03/04 |
| Observation payload must be `MetricObservation` | Phase14.2 Observation ABI | Schema check |
| No interpretation fields | Phase14.2 EVX-01 | Validator |
| No capability fields | Phase14.2 EVX-02 | Validator |
| Complete SourceRef required | Phase14.2 EVX-03 | Validator |
| Extractor isolation (no principle/recommendation) | Phase14.2 EVX-05 | Validator (recursive) |
| Deterministic output (same version + same input → same hash) | Phase14.2 EVX-06 | Unit test |
| Schema purity (no impact/meaning/purpose) | Phase14.2 EVX-07 | Validator |

**No new validation rules** are introduced for B1. The EVX-01~07 series from Phase14.2-A covers all narrative observation requirements.

---

## §2 What Narrative Observation IS

### Allowed dimensions

Narrative observation measures **structural properties** of a text that can be computed from:

- **Boundary detection** — where scenes/chapters/events begin and end
- **Count aggregation** — how many of X exist (events, transitions, POV switches)
- **Distance calculation** — spacing between related elements (setup→payoff, info→reference)
- **Ratio computation** — proportion of text belonging to a structural category
- **Distribution analysis** — how structural elements are spread across the text

### Example: Valid narrative observations

```python
# Scene transitions — purely positional
observation = MetricObservation(
    metric_name="scene_transition_count",
    metric_value=12,
    unit="count",
    aggregation_method="sum",
    sample_range="chapter_001"
)

# Information gap — purely distance
observation = MetricObservation(
    metric_name="information_release_interval",
    metric_value=3000,
    unit="character",
    aggregation_method="mean",
    sample_range="full_text"
)

# Foreshadow distance — purely positional relationship
observation = MetricObservation(
    metric_name="foreshadow_distance",
    metric_value=2980,
    unit="character",
    aggregation_method="median",
    sample_range="chapter_001-005"
)
```

---

## §3 What Narrative Observation IS NOT

### Forbidden observation categories

| Category | Forbidden root words | Rationale |
|----------|---------------------|-----------|
| **Quality** | `quality`, `score`, `rating`, `grade`, `level` | Describes value, not structure |
| **Intensity** | `intensity`, `strength`, `depth`, `degree` | Requires interpretation, not measurement |
| **Effect** | `engagement`, `tension`, `suspense`, `emotion`, `feeling` | Infers reader experience |
| **Judgment** | `good`, `bad`, `effective`, `poor`, `smooth`, `clunky` | Value judgment |
| **Recommendation** | `should`, `increase`, `decrease`, `improve`, `fix` | Prescribes action |
| **Semantic Label** | `climax`, `setup`, `payoff`, `hook`, `filler` | Labels are interpretation, not measurement |
| **Genre evaluation** | `appeal`, `market`, `audience`, `genre_quality` | Marketing evaluation, not structural |

### Check: Am I observing or interpreting?

Ask these three questions for every proposed observation field:

1. **Can another developer implement this from the ABI alone and get the same number?**
   - Yes → Safe (deterministic measurement)
   - No → Dangerous (requires subjective interpretation)

2. **Would a 12-year-old with a ruler get the same answer?**
   - Yes → Safe (mechanical)
   - No → Dangerous (requires domain knowledge)

3. **Does this observation tell me WHAT, not what it MEANS?**
   - What → Safe (structure)
   - What it means → Dangerous (interpretation)

---

## §4 Extractors Allowed in Phase14.2-B1

### 4.1 Event Boundary Extractor

**extractor_id**: `narrative_event_boundary_v1`

**What it observes**: Scene transitions, time jumps, POV switches, event paragraph boundaries.

```python
{
    "evidence_type": "EVENT_BOUNDARY",
    "observation": [
        MetricObservation("scene_transition_count", int, "count", "sum", segment),
        MetricObservation("pov_switch_count", int, "count", "sum", segment),
        MetricObservation("time_jump_count", int, "count", "sum", segment),
        MetricObservation("mean_scene_length", float, "character", "mean", segment),
        MetricObservation("scene_length_variance", float, "character", "variance", segment),
    ]
}
```

**Forbidden outputs**:
- ❌ `scene_quality: "well-structured"`
- ❌ `pacing_score: 7`
- ❌ `scene_tension: "high"`
- ❌ `event_importance: "major"`

### 4.2 Information Distribution Extractor

**extractor_id**: `narrative_information_distribution_v1`

**What it observes**: New information appearance positions, density changes, reference intervals.

```python
{
    "evidence_type": "INFORMATION_DISTRIBUTION",
    "observation": [
        MetricObservation("new_information_count", int, "count", "sum", segment),
        MetricObservation("mean_information_interval", float, "character", "mean", segment),
        MetricObservation("information_density", float, "count_per_1000chars", "mean", segment),
        MetricObservation("reference_gap_min", float, "character", "min", segment),
        MetricObservation("reference_gap_max", float, "character", "max", segment),
    ]
}
```

**Forbidden outputs**:
- ❌ `information_reveal_pacing: "good"`
- ❌ `mystery_depth: 8`
- ❌ `reader_surprise_level: "high"`

### 4.3 Scene Rhythm Extractor

**extractor_id**: `narrative_scene_rhythm_v1`

```python
{
    "evidence_type": "SCENE_RHYTHM",
    "observation": [
        MetricObservation("scene_count", int, "count", "sum", segment),
        MetricObservation("scene_length_distribution", dict, "ratio", "distribution", segment),
        MetricObservation("transition_frequency", float, "count_per_1000chars", "mean", segment),
        MetricObservation("scene_type_ratio_dialogue", float, "ratio", "mean", segment),
        MetricObservation("scene_type_ratio_narration", float, "ratio", "mean", segment),
        MetricObservation("scene_type_ratio_mixed", float, "ratio", "mean", segment),
    ]
}
```

### 4.4 Foreshadow Distance Extractor

**extractor_id**: `narrative_foreshadow_distance_v1`

```python
{
    "evidence_type": "FORESHADOW_DISTANCE",
    "observation": [
        MetricObservation("setup_payoff_count", int, "count", "sum", segment),
        MetricObservation("mean_foreshadow_distance", float, "character", "mean", segment),
        MetricObservation("min_foreshadow_distance", float, "character", "min", segment),
        MetricObservation("max_foreshadow_distance", float, "character", "max", segment),
        MetricObservation("foreshadow_density", float, "count_per_chapter", "mean", segment),
    ]
}
```

**CRITICAL**: This extractor observes **distance only**. It does NOT:
- Judge whether the foreshadow was effective
- Classify foreshadow type (telegraph/plant/red-herring)
- Determine if the payoff was satisfying
- Recommend foreshadow density

---

## §5 Not Allowed in Phase14.2-B1

The following are **explicitly deferred** to Phase14.3+:

| Feature | Reason | Target Phase |
|---------|--------|-------------|
| Plot quality scoring | Requires Principle layer | Phase14.3+ |
| Tension curve analysis | Requires reader-effect model | Phase14.4+ |
| Conflict intensity classification | Semantic interpretation | Phase14.3+ |
| Character arc evaluation | Requires Entity Resolution first | Phase14.2-C+ |
| Genre compliance check | Cross-work analysis | Phase14.4 |
| Writing recommendation generation | Capability layer | Phase14.5 |

---

## §6 Entry Criteria for Phase14.2-B1

Before B1 implementation begins, all of the following must hold:

| # | Criterion | Verification |
|---|-----------|-------------|
| E01 | Phase14.2-A FROZEN | Gate report filed |
| E02 | All B1 outputs are `EvidenceNode` | ABI compliance |
| E03 | No `interpretation` fields | EVX-01 enforcement |
| E04 | No `quality` fields | EVX-01 enforcement |
| E05 | No `recommendation` fields | EVX-05 enforcement |
| E06 | Complete `SourceRef` | EVX-03 enforcement |
| E07 | Deterministic (same input→same output) | EVX-06 test |
| E08 | Phase14.1 Schema unchanged | G6-style verification |
| E09 | Boundary Contract signed | This document approved |

---

## §7 Boundary Contract Signature

| Role | Action |
|------|--------|
| Architecture Review | ✅ Approve §0 Core Principle |
| Architecture Review | ✅ Approve §3 Forbidden categories |
| Architecture Review | ✅ Approve §4 Extractor scope |
| Implementation | ☐ Confirm B1 extractors stay within §4 |
| Implementation | ☐ Confirm forbidden features deferred to §5 targets |

---

### Freeze Declaration

```
PHASE14.2-B1-NARRATIVE-BOUNDARY-CONTRACT
Status: APPROVED ✅
Signed: 2026-07-22

Principle: Narrative Observation measures structural properties
           without producing interpretation, evaluation,
           recommendation, or capability.

Authority: Evidence Layer only.

Forbidden: Quality / Effect / Judgment / Recommendation /
           Semantic Meaning / Genre Evaluation

Signature: Architecture Review
```

---

### Implementation Roadmap

Per reviewer direction, Phase14.2-B1 shall be implemented in four ordered sub-phases:

| Sub-phase | Extractor | Precondition | Status | Gate Test |
|-----------|-----------|-------------|--------|-----------|
| **B1-A** | Event Boundary Extractor | None (foundation) | ✅ **FROZEN ❄️** | G1: structural only, EVX-01~07 + NBX-01~06 pass |
| **B1-B** | Information Distribution Extractor | B1-A stable | ⏳ Planned | G2: no semantic labeling |
| **B1-C** | Scene Rhythm Extractor | B1-B stable | ⏳ Planned | G3: ratio/distribution only |
| **B1-D** | Foreshadow Distance Extractor | B1-C stable | ⏳ Planned | G4: distance only, no judgment |

---

*Narrative observation measures what the story IS, not whether it is GOOD.*
