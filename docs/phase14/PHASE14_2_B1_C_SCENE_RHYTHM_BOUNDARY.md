# Phase14.2-B1-C — Scene Time-Structure Evidence

> **Status:** PRE-DESIGN — Boundary definition only. No ABI, no implementation.
>
> **Date:** 2026-07-22
>
> **Inherits:** Phase14.2-A ❄️ → Phase14.2-B1-A ❄️ → Phase14.2-B1-B ❄️
>
> **Next step after approval:** Proceed to Full Design (§4 ABI + §5 Extractor + §6 RBX + §7 Tests)

---

## §0 Pipeline Positioning

### Phase14 的真正目标

Phase14 的最终目的不是建立一个文学分析系统，也不是评价小说质量的工具。

**真实链路：**

```
作品输入 → 观察 → 证据 → 模式 → 能力 → Edit Agent → OpenTale能力增强
```

**实际的分层：**

```
Layer 0  Deep Text Perception         ← Phase14.2-A
Layer 1  Evidence Graph               ← Phase14.2-B (B1-A, B1-B, B1-C, B1-D)
Layer 2  Knowledge Dynamics           ← Phase14.3
Layer 3  Meta Principle               ← Phase14.4
Layer 4  Capability Package           ← Phase14.5
Layer 5  Edit Agent                   ← Phase14.8
           ↓
         OpenTale
```

### B1-C 在此管道中的位置

B1-C 不是独立的"节奏分析模块"。它在管道中的角色：

```
作品 → B1-A Boundary (场景分割)
         ↓
       B1-B Info Distribution (实体位置)
         ↓
       B1-C Scene Time-Structure ← 当前位置
         ↓
       证据 (EvidenceNode)
         ↓
       Style Knowledge Graph (Phase14.3) ← 首次使用此证据
         ↓
       Capability Package (Phase14.5)
         ↓
       Edit Agent (Phase14.8) → OpenTale 生成调整
```

B1-C 的产出是**时间结构证据**——不是分析结论。

### Identity Statement

```
B1-C observes:
  → Scene length (character/paragraph/sentence counts)
  → Per-segment text composition (dialogue/description/action ratios)
  → Transition intervals between text-mode changes
  → Punctuation and break density

B1-C provides evidence for:
  → Style Knowledge Graph (Phase14.3): author-specific text-organization patterns
  → Capability Package (Phase14.5): for Edit Agent to adjust OpenTale generation

B1-C does NOT:
  → Judge whether rhythm is fast or slow
  → Measure reader experience or emotional impact
  → Produce style analysis or genre assessment
  → Generate recommendations for writing
```

### Drift Warning

> ⚠️ B1-C is the most dangerous Observation module.
>
> The term "节奏" (rhythm) carries interpretative connotation in human language.
> The pipeline positioning means B1-C data will eventually feed into capability packages.
>
> **If B1-C is designed as "rhythm analysis" instead of "time-structure evidence collection", the downstream Style Knowledge Graph will be built on interpretive data — not observation data.**
>
> **Correct design:**
> B1-C outputs are:
> - Computable by a high school student with a ruler on a printed page
> - Verifiable by a second reader independently counting the same units
> - Meaningless without an interpretive layer (Phase14.3+) above them

---

## §0.5 Core Principle

> **B1-C measures the temporal distribution of observable textual units within scenes.**
> **It provides evidence for Style Knowledge Graph. It does not interpret rhythm.**
>
> **B1-C 测量文本单元的时序分布，为风格知识图谱提供证据。它不解释节奏。**

### Precedent

Phase14.2-B1-B established the pattern:

| B1-B (Information Distribution) | B1-C (Scene Time-Structure) |
|--------------------------------|-----------------------------|
| Where does entity appear? | Where do textual units cluster? |
| How far between references? | How far between transitions? |
| OPEN or CLOSED state? | How long in each state? |
| **Observes information geometry** | **Observes temporal/density geometry** |

B1-C extends B1-B's spatial measurement into temporal measurement — still geometric, still deterministic, still Evidence-only.

---

## §1 Inherited Constraints

B1-C inherits all constraints from the Phase14 evidence chain:

### Layer 1 — Evidence Schema (Phase14.1)

| Rule | Source | Applies to B1-C |
|------|--------|-----------------|
| EVX-01 | No interpretation fields | ✅ |
| EVX-02 | No capability fields | ✅ |
| EVX-03 | Complete SourceRef required | ✅ |
| EVX-04 | Observation-only, no self-interpreting | ✅ |
| EVX-05 | Recursive field/value scan for forbidden vocabulary | ✅ |
| EVX-06 | Source Determinism (SHA-256) | ✅ |

### Layer 2 — Narrative Boundary (Phase14.2-B1-A)

| Rule | Source | Applies to B1-C |
|------|--------|-----------------|
| NBX-01 | Scene boundary is paragraph/section based, not concept based | ✅ |
| NBX-02 | No emotional scene labels | ✅ |
| NBX-03 | Transition types are textual, not dramatic | ✅ |
| NBX-04 | Boundary detection must be deterministic | ✅ |
| NBX-05 | No scene hierarchy (major/minor) | ✅ |
| NBX-06 | Sequential only — no flashback/overlap tracking | ✅ |

### Layer 3 — Information Distribution (Phase14.2-B1-B)

| Rule | Source | Applies to B1-C |
|------|--------|-----------------|
| IBX-01 | Observation Purity | ✅ |
| IBX-02 | Schema Integrity | ✅ |
| IBX-03 | Position Integrity | ✅ |
| IBX-04 | Semantic Leakage | ✅ |
| IBX-05 | Vocabulary Restriction | ✅ |
| IBX-06 | Deterministic Extraction | ✅ |
| IBX-07 | Cross-layer Isolation | ✅ |
| IBX-08 | Evidence Compatibility | ✅ |

### Forbidden Fields (inherited)

```python
FORBIDDEN_INFORMATION_FIELDS = {
    "importance", "value", "weight", "critical", "major", "minor",
    "key_information", "essential", "core_information",
    "_uncertainty", "_score", "_confidence", "_probability",
    "_likelihood", "_reliability", "_certainty", "_significance",
    "_priority", "_severity", "_impact", "_relevance"
}

FORBIDDEN_CROSS_LAYER_VOCABULARY = {
    "foreshadow", "payoff", "setup", "reveal", "mystery",
    "suspense", "meaning", "symbolism", "theme", "climax",
    "hook", "filler", "tension", "arc", "beat", "turning_point",
    "red_herring", "chekhovs_gun", "plot_device", "deus_ex_machina",
    "narrative_weight"
}
```

### B1-C Additional Forbidden Vocabulary

In addition to the inherited forbidden sets, B1-C adds:

```python
FORBIDDEN_RHYTHM_VOCABULARY = FORBIDDEN_CROSS_LAYER_VOCABULARY | {
    # Pacing interpretation
    "fast", "slow", "brisk", "leisurely", "hurried", "stately",
    "pacing_quality", "pace_score", "speed",
    # Emotional affect
    "tension", "relaxed", "intense", "calm", "dramatic", "quiet",
    "exciting", "boring", "thrilling", "dull",
    # Reader effect
    "climax", "anti_climax", "release", "buildup", "lull",
    "highlight", "low_point", "breath",
    # Qualitative judgment
    "effective", "ineffective", "good_rhythm", "bad_rhythm",
    "natural", "forced", "smooth", "abrupt",
    # Author intent
    "intended_pace", "designed_rhythm", "planned",
    # Beat terminology (carries dramatic connotation)
    "emotional_beat", "story_beat",
}
```

---

## §2 Allowed Observation Domain

B1-C observes four aspects of scene rhythm, each strictly computational.

### 2.1 Scene Length Distribution

**What:** The dimensional dimensions of a scene in observable textual units.

**Allowed:**
| Field | Type | Unit | Description |
|-------|------|------|-------------|
| `scene_length_chars` | int | character | Total characters in the scene |
| `paragraph_count` | int | count | Number of paragraphs |
| `sentence_count` | int | count | Number of sentences |
| `scene_duration` | float | sentence | Duration implied by scene length (placeholder — may map to sentence count or word count as proxy) |

**Forbidden:** `scene_importance`, `scene_value`, `major_scene`, `minor_scene`, `scene_weight`, `scene_significance`

**Rationale:** Scene length is simply a count of characters/paragraphs/sentences within a bounded segment (boundary from B1-A). No interpretation of whether the length is appropriate.

### 2.2 Internal Rhythm Pattern

**What:** How textual composition changes across segments within a scene.

**Allowed:**
| Field | Type | Unit | Description |
|-------|------|------|-------------|
| `segment_distribution` | dict | proportion | Per-segment ratio of scene total (e.g., segment_1: 0.3, segment_2: 0.5) |
| `sentence_length_variance` | float | character² | Variance of sentence lengths within the scene |
| `dialogue_ratio_change` | dict | ratio | Dialogue proportion per segment (e.g., segment_1: 0.2, segment_2: 0.6) |
| `description_ratio_change` | dict | ratio | Description/narrative proportion per segment |

**Segment definition:** A contiguous block of paragraphs within the scene. Segment boundaries determined by:
- Paragraph shift (topic change)
- Section break (empty line)
- Scene-internal boundary signals (from B1-A)

**Forbidden:** `fast_pace`, `slow_pace`, `exciting`, `boring`, `rhythm_quality`, `pace_quality`

**Rationale:** Distribution is a pure computation: for each segment, count sentences of different lengths, count dialogue lines vs description lines. The ratio itself is raw data. Whether the ratio signifies "fast pace" is not observed here.

### 2.3 Transition Interval

**What:** The distance between different observable textual states within the scene.

**Allowed:**
| Field | Type | Unit | Description |
|-------|------|------|-------------|
| `transition_type` | str | — | Type of transition (from B1-A: dialogue_to_description, action_to_dialogue, etc.) |
| `transition_position` | int | character | Absolute position of transition point |
| `transition_count` | int | count | Number of transitions in the scene |
| `interval_length` | float | sentence | Sentences between this transition and the previous one |

**Forbidden:** `smooth_transition`, `effective_transition`, `dramatic_transition`, `natural_flow`, `forced_transition`, `transition_quality`

**Rationale:** A transition is just a detected change in textual mode (B1-A boundary). The interval is a distance measurement — identical in nature to B1-B's reference distance. Nothing interpretive.

### Pause Definition (Boundary)

> **Pause means textual segmentation marker only.**
>
> "Pause" in B1-C is strictly defined as:
> - A punctuation mark that indicates a syntactic break (period, comma, semicolon, dash, ellipsis, exclamation, question)
> - A blank line between paragraphs (section break)
> - A paragraph break
>
> "Pause" is NOT:
> - An emotional pause
> - A dramatic pause
> - A reader pause
> - A suspense break
> - A breathing point
>
> The term "pause" is inherited from natural language (写作停顿), but in B1-C it means only:
> **measurable distance between observable textual segmentation markers.**
>
> Allowed field names containing "pause":
> - `punctuation_density` ✅ (counts of punctuation marks)
> - `paragraph_break_interval` ✅ (distance between paragraph breaks)
> - `empty_line_interval` ✅ (distance between section breaks)
>
> Forbidden field names containing "pause":
> - `emotional_pause` ❌
> - `dramatic_pause` ❌
> - `suspense_pause` ❌
> - `reader_pause` ❌

**What:** Where textual "pauses" occur — measured as density of structural markers.

**Allowed:**
| Field | Type | Unit | Description |
|-------|------|------|-------------|
| `punctuation_density` | float | per_100chars | Punctuation marks per 100 characters |
| `paragraph_break_interval` | float | sentence | Average sentences between paragraph breaks |
| `empty_line_interval` | float | paragraph | Average paragraphs between empty lines (section breaks) |
| `punctuation_type_distribution` | dict[str, float] | per_100chars | Distribution by punctuation type (period, comma, dash, etc.) |

**Forbidden:** `emotional_pause`, `suspense_pause`, `dramatic_pause`, `breathing_room`, `tension_buildup`, `reader_rest`

**Rationale:** Punctuation density is a purely mechanical measurement. An empty line between two paragraphs indicates a structural break — not "suspense." A long paragraph without punctuation breaks indicates high density — not "tension."

---

## §3 Forbidden Interpretation

### Absolute Prohibitions

The following are **never** valid as B1-C observations:

1. **Pace judgment:** Any assertion about whether rhythm is fast, slow, appropriate, effective
2. **Emotional attribution:** Any claim about reader feelings (tension, relaxation, excitement)
3. **Dramatic structure:** Any reference to climax, buildup, release, turning point
4. **Comparative quality:** Any statement about one rhythm being better or worse than another
5. **Author intent:** Any inference about what the author intended rhythmically
6. **Genre normalization:** Any comparison against genre expectations (e.g., "this scene has lower dialogue ratio than expected for romance")

### Boundary Test

Before adding ANY field to B1-C, ask:

```
Q: Can this value be computed directly from text using paragraph/sentence/punctuation counts?
   NO  → PROHIBITED. This is interpretive.

Q: Does this field name imply an evaluation?
   YES → PROHIBITED. Names must be neutral descriptors.

Q: Could this field be used as a rule by a downstream capability?
   YES → Check: is the value directional? (e.g., "high dialogue ratio" alone is neutral.
        "optimal dialogue ratio" is directional → PROHIBITED.)

Q: Would a music theory toolkit output this field?
   NO  → PROHIBITED. Rhythm vocabulary from music (tempo, interval, duration, density) is safe.
        Narrative vocabulary (climax, tension, release) is explicitly forbidden.
```

### Drift Chain Protection

```
B1-C Scene Time-Structure Evidence
  ↓
  ↓  Only textual distribution and transition data
  ↓
Observation Layer (Phase14.2)
  ↓
  ↓  NEVER crosses into interpretation
  ↓
Style Knowledge Graph (Phase14.3) ← ACTUAL interpretation happens HERE
                                    ← With capability-level constraints
                                    ← Using B1-C data as raw material, not as conclusion
```

B1-C must produce OUTPUTS that are:
- Computable by a high school student with a ruler on a printed page
- Verifiable by a second reader independently counting the same units
- Meaningless without an interpretive layer (Phase14.3+) above them
- Unable to drive any action without downstream capability processing

---

## §4 ABI (Boundary)

> **Note:** This is a boundary sketch only. Full ABI with frozen dataclasses belongs in the Implementation Design document.

### Observation Interface

B1-C observations use the same MetricObservation interface as B1-B:

```python
@dataclass(frozen=True)
class MetricObservation:
    metric_name: str              # e.g., "scene_length_chars", "punctuation_density"
    metric_value: float | int     # numeric value only
    unit: str                     # "character", "count", "per_100chars", "sentence", "ratio"
    aggregation_method: str       # "mean", "median", "sum", "distribution", "variance"
    sample_range: str             # "scene_001", "scene_001-010", "chapter_001"
```

### Extractor Interface

```python
@dataclass(frozen=True)
class SceneRhythmObservation:
    metric_type: MetricType       # SCENE_RHYTHM
    source_ref: SourceRef
    observations: list[MetricObservation]
    extraction_version: str       # semver
```

### MetricType Enum (Proposed Addition)

```python
class MetricType(Enum):
    # Existing (inherited)
    ENTITY_DISTRIBUTION = "entity_distribution"
    TERM_DISTRIBUTION = "term_distribution"
    REFERENCE_DISTANCE = "reference_distance"
    REFERENCE_STATE = "reference_state"
    
    # New for B1-C
    SCENE_LENGTH = "scene_length"
    INTERNAL_DISTRIBUTION = "internal_distribution"
    TRANSITION_INTERVAL = "transition_interval"
    PAUSE_DENSITY = "pause_density"
```

---

## §5 Extractor Design (Boundary Sketch)

> **Note:** Full design — including component classes, preprocessor integration, validator layer — belongs in the Implementation Design after this Boundary is frozen.

### Proposed Components

| Component | Responsibility | Inherits from |
|-----------|---------------|---------------|
| `SceneLengthExtractor` | Measure character/paragraph/sentence counts per scene | B1-A SceneBoundary |
| `InternalDistributionExtractor` | Measure per-segment composition ratios | B1-A SegmentBoundary |
| `TransitionIntervalExtractor` | Measure transition points and intervals | B1-A TransitionType |
| `PauseDensityExtractor` | Measure punctuation/break density | Phase14.2-A Preprocessor |

### Preprocessor Dependencies

B1-C requires B1-A's scene boundary detection as input:

```
Raw Text
  → B1-A Preprocessor (scene segmentation)
    → Scene 1 boundary: [0..4500]
    → Scene 2 boundary: [4501..8900]
    → Transition types between scenes: [action_to_dialogue, ...]
      → B1-C Scene Rhythm Extractors
        → Scene length per scene
        → Internal distribution per scene
        → Transition intervals
        → Density measurements
```

### Deterministic Guarantee

All B1-C extractors must be:
- **Deterministic:** Same input → same output (verified by SHA-256)
- **Stateless:** No cross-scene state (each scene processed independently)
- **Non-learning:** No model inference, no pattern matching beyond direct counting

---

## §6 RBX Validation Rules (Rhythm Boundary eXamination)

New validation layer specific to B1-C, sitting alongside EVX/NBX/IBX.

| # | Rule | Enforcement | Severity |
|---|------|-------------|----------|
| RBX-01 | **Rhythm Purity** — No field measures "feel" or "experience" | Field name + value regex scan | BLOCK |
| RBX-02 | **No Pace Interpretation** — No value asserts speed or quality | String match against FORBIDDEN_RHYTHM_VOCABULARY | BLOCK |
| RBX-03 | **Transition Determinism** — All transition types are text-mode markers, not dramatic events | Cross-check against B1-A allowed transition set | BLOCK |
| RBX-04 | **Vocabulary Restriction** — No narrative-interpretive vocabulary in any field or value | Recursive string scan (same as EVX-05) | BLOCK |
|| RBX-05 | **Evidence Compatibility** — Observation output must successfully serialize through MetricObservation | Schema validation | BLOCK |
|| RBX-06 | **Downstream Dependency Isolation** — EvidenceNode must not contain capability-targeting fields | Recursive field scan (capability vocabulary) | BLOCK |

### RBX-01 Detail

```
RBX-01 enforces that NO field in the SceneRhythmObservation
contains a name suggesting emotional or reader-experience measurement.

Violations: {
    "tension_score", "excitement_level", "relaxation_index",
    "engagement", "immersion", "absorption"
}

Sanity check: If the field name contains "feeling", "sense",
"experience", "impact", "effect", or any synonym → REJECT.
```

### RBX-02 Detail

```
RBX-02 enforces that NO string value in any field
uses vocabulary from FORBIDDEN_RHYTHM_VOCABULARY.

This catches values like:
  metric_name="pace_quality", metric_value=2.5
  → REJECT: metric_name contains "pace" judgment

  segment_label="climax_segment"
  → REJECT: "climax" is narrative-interpretive
```

### RBX-03 Detail

```
RBX-03 ensures that transition types observed by B1-C
are the SAME as those allowed by B1-A.

Allowed (from B1-A):
  dialogue_to_description, description_to_dialogue,
  action_to_dialogue, dialogue_to_action,
  action_to_description, description_to_action,
  narrative_to_dialogue, dialogue_to_narrative

Forbidden (do not exist in B1-A, invented by B1-C):
  calm_to_intense, slow_to_fast, buildup_to_climax
```

### RBX-06 Detail

```
RBX-06 enforces that NO field in the SceneTimeStructureObservation
references or targets a downstream capability.

Violations: {
    "recommended_parameter", "style_change", "modify_target",
    "pipeline_update", "edit_action", "composition_adjustment",
    "generation_rule", "output_override", "parameter_suggestion"
}

Rationale: B1-C is Evidence Layer (Layer 1), not Capability Layer (Layer 4).
EvidenceNode must not short-circuit the pipeline:
  Evidence → Knowledge Graph → Capability → Evaluation → Edit Agent

RBX-06 prevents future scope creep where an evidence field
"conveniently" includes a capability recommendation.
This is the same isolation principle as IBX-07 (Cross-layer Isolation)
applied to the B1-C → Phase14.3 boundary.
```

---

## §7 Gate Criteria

B1-C uses four gates, inheriting the Phase14.2 gating structure:

| # | Gate | Criteria | Evidence Required |
|---|------|----------|-------------------|
|| G01 | **RBX Suite** | RBX-01~06 all PASS | RBX validation script output |
| G02 | **Deterministic Test** | 3× repeated SHA-256 identical | CI test output |
| G03 | **Forbidden Vocabulary** | Zero matches in any field/value across all test cases | Recursive scan output |
| G04 | **Regression** | All inherited tests (EVX/NBX/IBX) still pass | Full test suite output |

### Gate Blockers

The following block B1-C Freeze:

1. Any RBX gate fails
2. Any forbidden vocabulary discovered in test output fields
3. Any non-deterministic test (3× SHA-256 mismatch)
4. Any inherited test regression (EVX/NBX/IBX)

---

## §8 Implementation Order

Following Phase14.2 standard sequence:

```
Step 0:  BOUNDARY FREEZE ← YOU ARE HERE
Step 1:  ABI (MetricType addition + SceneRhythmObservation schema)
Step 2:  B1-C components (4 extractors)
Step 3:  RBX validator implementation
Step 4:  Integration with B1-A boundary output
Step 5:  Tests (unit + integration + RBX + deterministic)
Step 6:  Gate report + freeze
```

### Phase Relationship

```
Phase14.2-B1-A (Boundary)
  → Provides scene boundaries + segment boundaries + transition types
    
Phase14.2-B1-B (Information Distribution)
  → Provides entity positions, term positions, reference distances, state transitions
  → B1-C uses entity/term density per scene as optional input
    
Phase14.2-B1-C (Scene Time-Structure) ← CURRENT
  → Provides scene length, internal distribution, transition intervals, density
  → EvidenceNode correctly tagged for downstream processing

Phase14.3 (Style Knowledge Graph)
  → Receives all four observation types (B1-A, B1-B, B1-C, B1-D) as structured input
  → Applies interpretive layer with capability constraints
  → B1-C data contributes to: author-specific text-organization patterns
  → **Critical boundary: Phase14.3 produces Pattern, not Style Rule.**
    Example — ALLOWED:
      Pattern: "Author A: scene internal — first 30% environment description,
                middle section dialogue ratio increases, last 20% action units increase"
      Evidence count: 500 scenes
    Example — FORBIDDEN:
      "Author A likes to accelerate in the second half, so we should imitate that"
      (This crosses into Meta Principle / Capability territory)
      → Phase14.3 inherits the same Observation→Evidence→Pattern→Capability chain
        and must not skip to Capability directly from Pattern.
  → Phase14.3 design must include its own cross-layer isolation rules
    (inheriting IBX-07 and RBX-06 principles)
```

---

## §9 Design Review Signature

> This document defines the **Boundary** for Phase14.2-B1-C Scene Time-Structure Evidence.
>
> The Boundary establishes:
> - §0 Pipeline Positioning (B1-C in the full Phase14 → Edit Agent → OpenTale chain)
> - §0.5 Core Principle (temporal distribution → Style Knowledge Graph evidence)
> - §1 Inherited constraints from EVX/NBX/IBX
> - §2 Allowed Observation Domain (4 categories of textual-unit time-structure)
> - §3 Forbidden Interpretation (absolute prohibitions — must be meaningless without Phase14.3+)
> - §4~§5 ABI + Extractor sketches (non-binding — refined in full design)
> - §6 RBX validation rules
> - §7 Gate criteria
>
> **Before proceeding to full design (§4 ABI → §5 Implementation → §6 RBX → §7 Tests):**
>
> [ ] Pipeline positioning reviewed: B1-C serves Style Knowledge Graph, not standalone analysis
> [ ] Core Principle reviewed: temporal distribution measurement, not rhythm interpretation
> [ ] Allowed/Forbidden domain reviewed and accepted (specifically: no interpretive drift)
> [ ] RBX rules reviewed and accepted
> [ ] Gate criteria reviewed and accepted
> [ ] No interpretive drift in any listed field name
> [ ] Confirm: B1-C cannot drive any action without Phase14.3+ processing

---

*B1-C measures the temporal distribution of observable textual units within scenes. It provides evidence for Style Knowledge Graph. It does not interpret rhythm.*
