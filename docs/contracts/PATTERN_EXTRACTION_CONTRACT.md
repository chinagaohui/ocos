# Phase 10 Semantic Memory — Pattern Extraction Contract v1.0

> Status: **FROZEN ✅** — Step 2 complete. Proceeding to Step 3 (Concept Formation).
>
> Step 2 is the first **generation layer** of Phase 10.
> Step 1 prevented: *existing abstractions from acquiring power.*
> Step 2 prevents: *the system smuggling authority while generating abstractions.*

---

## §1 — Responsibility Boundary

### 1.1 Identity Statement

```
Phase 4 Experience Store  (raw events)
    │
    ▼
Pattern Extraction Engine  (Step 2 — this contract)
    │
    ├── discovers recurrence
    ├── computes statistical correlation
    ├── extracts candidate patterns
    └── preserves counter-examples and anomalies
    │
    ▼
Pattern  (statistical structure, NOT rule)
    │
    ▼
Concept Formation  (Step 3)  /  Principle Derivation  (Step 4)
```

### 1.2 Core Declaration

> **Pattern Extraction discovers recurrence. It does not discover commands.**

| ✅ Allowed | ❌ Forbidden |
|-----------|-------------|
| Discover repeated structures | Generate rules |
| Compute statistical correlations | Generate policies |
| Extract candidate patterns | Generate action recommendations |
| Preserve counter-examples and anomalies | Judge causality |
| Report frequency distributions | Override current state |
| Tag boundary conditions | Produce decisions or obligations |

### 1.3 What Pattern Extraction Is NOT

| NOT this | Why |
|----------|-----|
| Rule Mining | Rules are binding constraints (Phase 6 / Constitution). Patterns are observations. |
| Policy Generator | Policies prescribe behaviour. Patterns describe observed structures. |
| Decision Engine | Decisions mutate Reality (Article I). Patterns do not. |
| Causal Analyzer | Correlation ≠ Causation. Causal claims belong to Hypothesis Layer. |
| State Override | Past patterns cannot override current Reality state (SA-04 / SA-07). |

### 1.4 Experience → Pattern Pipeline (contract level)

```
ExperienceRecords[1..N]
    │
    │  (Step 2 input — raw Phase 4 data)
    ▼
[Similarity Detection]    ← identical/boundary recognition
    │
    ▼
[Frequency Computation]   ← occurrence rate, not truth probability
    │
    ▼
[Candidate Extraction]    ← structural descriptions only
    │
    ▼
[Counter-Example Scan]    ← MUST preserve anomalies
    │
    ▼
Pattern[1..M]             ← output; each traceable to source
```

**Design principle:** Every pipeline step either enriches description or preserves ambiguity.
No step adds authority, obligation, or imperative semantics.

---

## §2 — Input Contract

### 2.1 PatternExtractionInput

```python
@dataclass
class PatternExtractionInput:
    """Input for pattern extraction.

    Every extraction must declare its source of truth.
    """

    experience_ids: List[str]              # Phase 4 ExperienceRecord IDs
    experience_records: List[dict]         # The actual Experience data
    scope: dict                            # Current context filter
    extraction_context: str                # "semantic_memory" | "manual_query"
    created_at: datetime                   # When extraction was triggered
```

### 2.2 Provenance Rule

Every Pattern must answer:

> **Which experiences produced this pattern?**

```
Pattern
    ↓ source_experience_ids
ExperienceRecord[1..N]
    ↓ source_event_ids
Reality Events
```

**Contract rule:** Every Pattern output MUST carry `source_experience_ids`.
Patterns with empty or null source MUST be rejected.

### 2.3 Prohibited Input Patterns

| ❌ Forbidden input shape | Why |
|-------------------------|-----|
| Current Reality State as input | Would let past pattern override current state |
| Simulation output without `source_type = "simulation"` tag | Would let simulation become reality |
| Pre-processed "certainty" scores | Would inject truth probability into pattern generation |
| Decision outcomes | Would bypass Decision → Experience lifecycle |
| User instructions as experience | Would confuse instruction with observation |

### 2.4 Current State Isolation

```
Pattern Extraction reads:  Past Experience (Phase 4)
Pattern Extraction does NOT read:  Current Reality State
```

**Rationale:** If Pattern Extraction had access to current state,
past patterns could influence current judgment before evaluation:

```
Past pattern: "Resource pressure → conflict"  (extracted from Phase 4)
    ↓  (current state available as input)
... system skips evaluating whether current situation applies
    ↓
Past abstraction overrides current state             ← ❌ violates SA-04/SA-07
```

**Contract rule:** `PatternExtractionInput` MUST NOT contain current
Reality state fields. The binding between pattern and current context
happens in the Retrieval layer (not extraction).

---

## §3 — Pattern Generation Boundary

### 3.1 What a Pattern Is

A Pattern is a **repeated correlation** observed across multiple experiences.

```
Allowed:
    "Under resource shortage, project delay probability increases"
    "In 70% of observed cases, early disclosure reduced conflict"
    "Teams with high trust scores showed faster recovery in 8/10 cases"

These are all:
    - structured observations
    - time-bound (past)
    - bounded by scope conditions
```

### 3.2 Frequency → Truth — FORBIDDEN

| ❌ Forbidden transformation | Why |
|---------------------------|-----|
| `"90% of experiences"` → `"this is true 90% of the time"` | Frequency is historical, not predictive |
| `"It happened 100 times"` → `"it is a fact"` | Recurring observation ≠ established truth |
| `"Pattern confirmed by 1000 cases"` → `"confidence=0.999 as truth prob"` | Confidence is abstraction stability, not truth |

**Contract rule:**

```
90% occurrence = historical frequency
90% occurrence ≠ truth probability
90% occurrence ≠ authority to act

Frequency describes the past. It does not predict the future.
Frequency describes what was observed. It does not define what is correct.
```

### 3.3 Frequency → Rule — FORBIDDEN

| ❌ Forbidden transformation | Why |
|---------------------------|-----|
| `"Team failures were caused by poor communication 20/20 cases"` → `"Must prioritize communication"` | Pattern as Policy Generator |
| `"Exploration reduced risk in 15/20 projects"` → `"Always explore first"` | Pattern as imperative |
| `"High pressure → low exploration (count=100)"` → `"Under pressure, force exploration"` | Pattern as strategy |

**Contract rule:** A Pattern describes what **was** observed.
It does not prescribe what **should** be done.
Patterns cannot carry `must`, `should`, `always`, `never` semantics — this is
enforced at the data level (Data Contract §2.5 Statement Constraints) and at
the extraction level (Pattern Schema §4).

### 3.4 What a Pattern Is NOT

```
Pattern ≠ Truth
Pattern ≠ Rule
Pattern ≠ Policy
Pattern ≠ Decision
Pattern ≠ Prediction
Pattern ≠ Obligation
Pattern = "This structure was observed under these conditions"
```

### 3.5 Frequency Attribution

Every Pattern MUST carry:

| Field | Purpose |
|-------|---------|
| `occurrence_count` | How many times the structure was observed |
| `total_observations` | Out of how many total relevant experiences |
| `rate` | occurrence_count / total_observations |

These three fields together ensure:
- Frequency is transparent (ratio, not raw count alone)
- Small samples are visible (2/3 is different from 200/300)
- No single number can be interpreted as "truth probability"

---

## §4 — Pattern Schema

### 4.1 Core Object

```python
@dataclass
class Pattern:
    """Step 2 output: a repeated correlation observed across experiences.

    Pattern is a structural observation, NOT a rule, NOT a decision.
    Its purpose is to describe recurrence, not prescribe action.
    """

    # --- Identity ---
    pattern_id: str                          # unique, immutable
    statement: str                           # MUST be observational (see §2.5 Data Contract)
    description: str                         # optional richer description

    # --- Frequency ---
    occurrence_count: int                    # number of times the structure appeared
    total_observations: int                  # out of N relevant experiences
    rate: float                              # occurrence_count / total_observations

    # --- Provenance ---
    source_experience_ids: List[str]         # MUST be non-empty
    created_at: datetime                     # immutable

    # --- Epistemic fields ---
    counter_examples: List[dict]             # MUST be present (may be empty list)
    scope: dict                              # conditions under which the pattern was observed
    confidence: float                        # abstraction stability across N samples (see Data Contract §2.7)
    limitations: List[str]                   # known boundary conditions, weaknesses

    # --- Provenance chain ---
    provenance: "PatternProvenance"          # see §6

    # --- Status ---
    status: str                              # "active" | "weakened" | "invalidated"

    # ---------- FORBIDDEN FIELDS (not in schema) ----------
    # rule_id: str                           ❌ Pattern ≠ Rule
    # is_rule: bool                          ❌ Pattern ≠ Rule
    # is_policy: bool                        ❌ Pattern ≠ Policy
    # recommendation: str                    ❌ Pattern ≠ Recommendation
    # action: str                            ❌ Pattern ≠ Action
    # decision: str                          ❌ Pattern ≠ Decision
    # obligation: str                        ❌ Pattern ≠ Obligation
    # cause: str                             ❌ Pattern ≠ Causation
    # truth_probability: float               ❌ Frequency ≠ Truth
```

### 4.2 Field Semantics

| Field | Meaning | NOT |
|-------|---------|-----|
| `statement` | Observational description of structure | Imperative or normative claim |
| `occurrence_count` | How many times this structure appeared | Authority score |
| `total_observations` | Sample size context | Denominator for truth probability |
| `rate` | Historical frequency | Probability of future occurrence |
| `confidence` | Abstraction stability across samples | Truth probability or authority weight |
| `counter_examples` | Known deviations from the pattern | Edge cases that confirm the rule |
| `scope` | Conditions under which pattern was seen | Domain of universal applicability |

### 4.3 `occurrence_count` Constraint

```
occurrence_count describes:  how many times the structure appeared
occurrence_count is NOT:     authority score
occurrence_count is NOT:     truth indicator
occurrence_count is NOT:     priority weight

occurrence_count > threshold  →  more observations, NOT higher authority
occurrence_count > threshold  →  more data, NOT more truth
occurrence_count > threshold  →  wider sample, NOT stronger obligation
```

**Contract rule:** `occurrence_count` MUST NOT influence authority, priority, or
decision weight in any downstream layer. High frequency means "well-observed,"
not "more correct."

### 4.4 `counter_examples` Constraint

**MUST be present.** Every Pattern carries a counter_examples list
(even if empty — explicitly, not by omission).

```
Pattern + (empty counter_examples) = "No deviations observed yet"
    ↓
can become "absolute belief" if exceptions are forgotten

Pattern + explicit counter_examples = "Deviations known and tracked"
    ↓
remains revisable, keeps epistemic humility
```

**Contract rule:** If counter_examples is empty, the Pattern MUST still
declare `counter_examples = []` — never null, never omitted.
A pattern with counter_examples removed or suppressed violates this contract.

### 4.5 Output Restriction

Pattern Extraction Engine outputs ONLY:

```
Pattern[1..M]
```

It MUST NOT output:

```
Rule
Policy
Decision
Recommendation
Action
Obligation
Causal Statement
State Override
```

---

## §5 — Causality Boundary

### 5.1 Correlation ≠ Causation

Pattern Extraction detects **correlation**, not **causation**.

| ✅ Allowed | ❌ Forbidden |
|-----------|-------------|
| `"A and B frequently co-occur"` | `"A causes B"` |
| `"When A increased, B decreased (observed 8/10 times)"` | `"A drives B down"` |
| `"A precedes B in 75% of cases"` | `"A triggers B"` |

### 5.2 Why Causality is Forbidden at Extraction Stage

Causal claims belong to the **Hypothesis Layer** (Phase 3 / future Hypothesis
Generation), not to Semantic Memory's extraction step. Reasoning about why
something happened requires:

1. Hypothesis generation (what might explain this?)
2. Evidence evaluation (does the data support the explanation?)
3. Simulation (if I change A, does B change?)

None of these exist in Pattern Extraction. Extraction only answers:

> **What structures repeat?**

It does not answer:

> **Why do they repeat?**

### 5.3 Contract Rule

```
Pattern statement MUST be framed as:
    "X and Y co-occur under conditions Z"
    "When X, Y tends to follow (observed M/N times)"

Pattern statement MUST NOT be framed as:
    "X causes Y"
    "X leads to Y"
    "X triggers Y"
    "X is the reason for Y"
    "Because X, Y"
```

**Causality Language Boundary:**

> Pattern describes observed co-occurrence.
> Pattern does not explain why the relationship exists.
> 中文：Pattern 描述观察到的结构关系。Pattern 不解释结构产生的原因。

**English prohibited causal expressions:**

`causes`, `caused`, `cause`, `lead to`, `leads to`, `leading to`, `trigger`, `triggers`, `triggered`, `because`, `therefore`, `results in`, `resulted in`, `drives`, `driven by`

**Chinese prohibited causal expressions (中文禁止因果表达):**

`导致`, `造成`, `引发`, `促成`, `因此`, `所以`, `必然`, `说明`, `证明`, `决定`, `使得`, `带来`, `源自`, `归根于`

**Enforcement:** `Pattern.statement` is subject to the same imperative-language
rules as `SemanticAbstraction.statement` (Data Contract §2.5). Additionally,
causal verbs (both English and Chinese above) are forbidden in Pattern statements
and descriptions.

### 5.4 Provenance of Correlation

```
Pattern:
    "Under resource scarcity, project delay frequency increases"
    source: experiences [E1, E2, E5, E7, E9, E12]
    counter_examples: [E4 — no delay despite scarcity]
    rate: 5/6 = 0.83

NOT:
    "Resource scarcity causes project delays"
```

---

## §6 — PatternProvenance Schema

### 6.1 Core Object

```python
@dataclass
class PatternProvenance:
    """Records how a Pattern was extracted and from what."""

    created_from_experience_ids: List[str]   # Phase 4 source events
    extraction_method: str                    # "frequency_detection" | "clustering" | "similarity_grouping"
    generator: str                            # component that produced the pattern
    created_at: datetime                      # immutable
    updated_at: Optional[datetime]            # last confidence/metadata update
    extraction_parameters: dict               # settings used during extraction
    validation_history: List[dict]            # [(timestamp, event, detail), ...]
```

### 6.2 Provenance Rules

| Rule | Rationale |
|------|-----------|
| `created_from_experience_ids` MUST match source in Pattern | Consistency |
| `extraction_method` MUST be truthful | Distinguish frequency from clustering |
| `created_at` immutable | Extraction time cannot be falsified |
| `validation_history` append-only | Every update leaves a trace |

### 6.3 Provenance Chain

```
Pattern
    ↓
PatternProvenance
    ├── created_from_experience_ids[1..N]
    │       ↓
    │   ExperienceRecord (Phase 4)
    │       ↓
    │   Event (Reality)
    │
    └── extraction_method
    └── generator
    └── extraction_parameters
    │
    ▼
Answerable: "Why does this Pattern exist?"
    └── "Because experiences [E1, E3, E5, E7] showed this correlation"
    └── "Extracted via frequency detection with threshold 0.6"
```

---

## §7 — Authority Isolation

### 7.1 Forbidden Output Types

The Pattern Extraction Engine MUST NOT expose any output interface that
returns:

| Forbidden Type | Reason |
|---------------|--------|
| `Rule` | Pattern ≠ Rule |
| `Policy` | Pattern ≠ Policy |
| `Decision` | Pattern ≠ Decision |
| `Recommendation` | Pattern ≠ Recommendation |
| `Action` | Pattern ≠ Action |
| `Obligation` | Pattern ≠ Obligation |
| `PriorityRanking` | Pattern ≠ Priority |
| `StatusOverride` | Past pattern ≠ Current state override |

### 7.2 Allowed Output Interface

```python
# ✅ Allowed output shapes
def extract_patterns(input: PatternExtractionInput) -> List[Pattern]: ...
def get_pattern(pattern_id: str) -> Pattern: ...
def find_patterns(scope: dict) -> List[Pattern]: ...

# ❌ Forbidden output shapes
def extract_rules(input) -> List[Rule]: ...                    # ❌
def get_policy_candidates(input) -> List[Policy]: ...          # ❌
def generate_recommendations(input) -> List[str]: ...          # ❌
def evaluate_priority(input) -> PriorityRanking: ...           # ❌
```

### 7.3 `confidence` Isolation

Pattern Extraction's `confidence` field MUST NOT be consumed by any
Decision Layer component. It is readable only by:

- Semantic Memory Store (storage)
- Evaluation Layer (as context)
- Concept Formation (Step 3 — as input)
- Principle Derivation (Step 4 — as input)

It MUST NOT be passed to:

- DecisionGenerator
- Commit Service
- Governance Layer
- Any component that produces rules or mutations

---

## §8 — Pattern Validation (PE-01 – PE-06)

### PE-01: Pattern ≠ Rule

```python
def test_pe01_pattern_not_rule():
    """Repeated extraction of the same experience produces Pattern, not Rule."""
    same_experiences = [experience_for("failure_comm") for _ in range(100)]
    for exp in same_experiences:
        store.save_experience(exp)

    result = extract_patterns(PatternExtractionInput(
        experience_ids=[e.id for e in same_experiences],
        experience_records=same_experiences,
        scope={},
        extraction_context="test",
        created_at=datetime.now()
    ))
    for pattern in result:
        assert isinstance(pattern, Pattern)
        assert not hasattr(pattern, "is_rule")
        assert not hasattr(pattern, "rule_id")
        assert not hasattr(pattern, "is_policy")
```

### PE-02: Frequency ≠ Truth

```python
def test_pe02_frequency_not_truth():
    """90% frequency does not become truth probability."""
    high_freq = experiences_with_rate(0.9)
    result = extract_patterns(make_input(high_freq))
    for pattern in result:
        assert pattern.rate == 0.9
        assert not hasattr(pattern, "truth_probability")
        assert pattern.confidence != pattern.rate  # confidence ≠ frequency
```

### PE-03: Counter-Example Preservation

```python
def test_pe03_counter_example_preserved():
    """When positive and counter examples exist, counter examples are preserved."""
    experiences = [
        experience_for("pressure_conflict"),    # positive
        experience_for("pressure_cooperation"),  # counter-example
        experience_for("pressure_conflict"),     # positive
        experience_for("pressure_conflict"),     # positive
        experience_for("pressure_cooperation"),  # counter-example
    ]
    result = extract_patterns(make_input(experiences))
    # Counter-examples exist for the "pressure → conflict" pattern
    conflict_pattern = [p for p in result if "conflict" in p.statement.lower()]
    if conflict_pattern:
        cp = conflict_pattern[0]
        assert len(cp.counter_examples) > 0
        # counter_examples list is not None
        assert cp.counter_examples is not None
```

### PE-04: No Current State Override

```python
def test_pe04_no_current_state_override():
    """Pattern Extraction cannot access current Reality state."""
    with pytest.raises(ValueError):
        # Input containing current_state is rejected
        extract_patterns(PatternExtractionInput(
            experience_ids=["e1"],
            experience_records=[make_experience()],
            scope={},
            extraction_context="test",
            created_at=datetime.now(),
            # Attempt to inject current state
            extra={"current_state": {...}}
        ))
```

### PE-05: No Causality Leak

```python
def test_pe05_no_causality_leak():
    """Pattern output MUST NOT contain causal verbs."""
    experiences = alternating_type(experience_for("a_up_b_up"))
    result = extract_patterns(make_input(experiences))
    causal_verbs = ["cause", "because", "triggers", "leads to",
                    "drives", "results in", "therefore"]
    for pattern in result:
        statement_lower = pattern.statement.lower()
        for verb in causal_verbs:
            assert verb not in statement_lower, \
                f"Causal verb '{verb}' found in pattern statement: {pattern.statement}"
        # Pattern description also prohibited
        desc_lower = pattern.description.lower()
        for verb in causal_verbs:
            assert verb not in desc_lower, \
                f"Causal verb '{verb}' found in pattern description: {pattern.description}"
```

### PE-06: Provenance Required

```python
def test_pe06_provenance_required():
    """Pattern without source experiences is rejected."""
    with pytest.raises(ValueError):
        Pattern(
            pattern_id="orphan",
            statement="Pattern with no source",
            description="",
            occurrence_count=0,
            total_observations=0,
            rate=0.0,
            source_experience_ids=[],  # empty — rejected
            created_at=datetime.now(),
            counter_examples=[],
            scope={},
            confidence=0.0,
            limitations=[],
            provenance=PatternProvenance(
                created_from_experience_ids=[],
                extraction_method="test",
                generator="test",
                created_at=datetime.now()
            ),
            status="active"
        )
```


### PE-07: Causality Language Rejection

```python
def test_pe07_causality_language_rejection_en():
    """Pattern statement with English causal verbs is rejected."""
    causal_en = [
        "Resource shortage causes failure",
        "Frequent communication leads to success",
        "Because of high pressure, conflict occurs",
        "Transparency therefore reduces risk",
    ]
    for statement in causal_en:
        assert not is_valid_pattern_statement(statement), \
            f"Causal statement should be rejected: {statement}"


def test_pe07_causality_language_rejection_cn():
    """Pattern statement with Chinese causal expressions is rejected."""
    causal_cn = [
        "长期训练导致成功",
        "资源不足造成失败",
        "频繁沟通引发冲突",
        "不透明因此误解",
        "数据证明规则成立",
    ]
    for statement in causal_cn:
        assert not is_valid_pattern_statement(statement), \
            f"Chinese causal statement should be rejected: {statement}"


def test_pe07_valid_correlation_statement():
    """Non-causal correlational statements pass validation."""
    pass_cases = [
        "长期训练与成功结果共同出现",
        "Resource shortage and failure co-occur (observed 8/10 cases)",
        "频繁沟通时冲突减少",
        "Under high pressure, conflict probability increases",
    ]
    for statement in pass_cases:
        assert is_valid_pattern_statement(statement), \
            f"Valid correlation statement should pass: {statement}"
```


---
## Step 2 Audit Matrix

| # | Boundary | Status | Key Check |
|---|----------|--------|-----------|
| A | Extraction Responsibility | **FROZEN ✅** | Pattern ≠ Rule. Pattern ≠ Causation. Pattern ≠ State. |
| B | Frequency Boundary | **FROZEN ✅** | Frequency ≠ Truth. Frequency ≠ Authority. |
| C | Correlation/Causality | **FROZEN ✅** | No causal verbs (EN + CN) in pattern statement. |
| D | Pattern Schema | **FROZEN ✅** | occurrence_count, rate, counter_examples, provenance all required. |
| E | Counter-Example Preservation | **FROZEN ✅** | counter_examples list MUST exist. |
| F | Provenance | **FROZEN ✅** | source_experience_ids MUST be non-empty. |
| G | Authority Isolation | **FROZEN ✅** | No rule/policy/decision/recommendation outputs. |
| H | Current State Isolation | **FROZEN ✅** | Extraction reads past only. |

---

## Step 2 Freeze Target

When frozen, the contract guarantees:

```
Experience (Phase 4)
    ↓
Pattern Extraction  (Step 2 — this contract)
    ↓
Pattern
    ├── describes "what repeated correlation was observed"
    └── does NOT describe "what should be done"
    └── does NOT describe "what is true"
    └── does NOT describe "what causes what"
    └── does NOT describe "what to decide"
```

Pattern lives as **statistical structure**, not **authority structure**.
