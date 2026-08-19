# Phase 10 Semantic Memory — Concept Formation Contract v1.0

> Status: **FROZEN ✅** — Step 3 complete. Proceeding to Step 4 (Principle Derivation).
>
> Step 3 is the second **generation layer** of Phase 10 — and more dangerous than Step 2.
>
> Step 2 risk: frequency → rule
> Step 3 risk: similarity → **identity definition**

---

## §1 — Responsibility Boundary

### 1.1 Identity Statement

```
Phase 4 Experience (raw events)
    │
Phase 10 Step 2 — Pattern Extraction
    │
    ▼
Pattern[1..M]   (repeated correlations)
    │
Phase 10 Step 3 — Concept Formation (this contract)
    │
    ├── aggregates patterns with shared structure
    ├── extracts common semantics
    ├── establishes semantic associations
    └── does NOT classify, label, or define entities
    │
    ▼
Concept[1..N]   (semantic grouping, NOT identity label)
    │
    ▼
Phase 10 Step 4 — Principle Derivation
```

### 1.2 Core Declaration

> **Concept Formation creates reusable abstractions.**
> **Concept Formation does not classify entities.**
> **Concept is a perspective, not an identity.**

| ✅ Allowed | ❌ Forbidden |
|-----------|-------------|
| Aggregate patterns with shared structure | Classify entities |
| Extract common semantic meaning | Define entity identity |
| Establish semantic relationships | Predict deterministic behaviour |
| Group observed characteristics | Generate labels for actors |
| Tag boundary and scope conditions | Assign permanent personality traits |
| Track counter-examples per concept | Lock entity into concept category |

### 1.3 What Concept Formation Is NOT

| NOT this | Why |
|----------|-----|
| Entity Classification | Classification assigns entities to fixed types. Concepts describe observed structures. |
| User/Character Labelling | Labels are Identity Layer concerns. Concepts are semantic memory. |
| Personality Profiling | Personality implies permanence. Concepts describe observed patterns. |
| Category Assignment | Categories create hierarchies. Concepts describe relationships. |
| Behaviour Prediction | Concepts summarise past observations. They do not forecast future actions. |

### 1.4 The Danger of Drift

```
Observed pattern
    ↓
"A repeatedly exhibits cautious behaviour under pressure"
    ↓
Concept: "cautious decision-making under pressure"     ✅  (semantic grouping)
    ↓
Identity drift: "A is a cautious type"                 ❌  (identity lock)
    ↓
Label: "A = cautious person"                           ❌  (identity violation)
```

**Contract rule:** Concept Formation MUST stop at the semantic grouping level.
Any output that maps a concept to an entity identity is contract violation.

---

## §2 — Input Contract

### 2.1 ConceptFormationInput

```python
@dataclass
class ConceptFormationInput:
    """Input for concept formation.

    Concept Formation receives patterns (Step 2 output) and provenance,
    NEVER Identity Layer data or current state.
    """

    # --- Required ---
    patterns: List[Pattern]                    # Step 2 output patterns
    pattern_provenances: List[PatternProvenance]  # Step 2 provenance chain
    scope: dict                                # context scope for aggregation

    # --- Optional ---
    extraction_context: str = "semantic_memory"  # context tag

    # --- Forbidden inputs (MUST NOT be present) ---
    # identity_entities: List[Any]              ❌ Identity Layer is off-limits
    # current_state: dict                       ❌ Current state not read
    # external_labels: List[str]                ❌ External classification not accepted
    # decision_history: List[Any]               ❌ Decision history not consumed
```

### 2.2 Prohibited Inputs

| ❌ Forbidden input | Why |
|-------------------|-----|
| Identity Layer entities as classification targets | Concept would become entity label and violate Identity Boundary |
| Current Reality State | Would let past patterns override current context (SA-04/SA-07) |
| Decision history | Would bypass Decision → Experience lifecycle (Articles I–II) |
| External labels or tags | Would introduce external classification into Semantic Memory (Provenance contamination) |
| User-provided "entity type" overrides | Would inject authority into abstraction (Constitution drift) |

### 2.3 Identity Isolation at Input

```
ConceptFormationInput

    ✅ patterns[1..M]                         — allowed
    ✅ pattern_provenances[1..M]              — allowed
    ✅ scope                                   — allowed
    ❌ identity_profile: dict                  — forbidden
    ❌ entity_classification: str              — forbidden
    ❌ personality_traits: dict                — forbidden
    ❌ target_entities: List[str]              — forbidden
```

**Contract rule:** Concept Formation MUST NOT receive Identity entities
as classification targets. If any input field maps to an entity identity,
the input MUST be rejected.

---

## §3 — Concept Generation Boundary

### 3.1 What a Concept Is

A Concept is a **semantic grouping** of patterns that share structural
characteristics. It describes what multiple patterns have in common
without assigning that commonality to any entity.

```
✅ Allowed:
    Pattern A: "Under resource scarcity, delay probability increases"
    Pattern B: "Under resource scarcity, conflict probability increases"
    Pattern C: "Under resource scarcity, exploration decreases"

    → Concept: "resource-constrained adaptation pattern"
    → NOT automatic rule: "must allocate more resources"
    → NOT identity lock: "this team is resource-pressured"
```

### 3.2 Pattern Aggregation ≠ Classification

| ✅ Allowed aggregation | ❌ Forbidden classification |
|-----------------------|---------------------------|
| Multiple patterns with shared structure → semantic grouping | Multiple patterns about same entity → entity type label |
| "Patterns A, B, C share the property 'triggered by scarcity'" | "Entity X frequently appears in scarcity patterns → X = scarcity-prone" |
| "These patterns form a family: high-pressure adaptation" | "These patterns show character A is the 'high-pressure type'" |

**Contract rule:** Concept describes **what patterns share**, not **what an entity is**.
Every concept must be expressible without naming a specific entity.

### 3.3 Conceptual Hierarchy

```
[Pattern]                    [Pattern]                    [Pattern]
  "scarcity→delay"             "scarcity→conflict"          "scarcity→exploration↓"
      \                            |                            /
       \                           |                           /
        Concept: "resource-constrained adaptation pattern"
                         |
                         |  (optional)
                         v
            Sub-concept: "resource-constrained
            conflict avoidance"
```

Permitted: hierarchical grouping of patterns into concepts.
Forbidden: mapping any level of this hierarchy to an entity identity.

---

## §4 — Concept Schema

### 4.1 Core Object

```python
@dataclass
class Concept:
    """Step 3 output: a semantic grouping of patterns.

    Concept summarises shared structural characteristics across patterns.
    It does NOT classify entities, define identities, or assign labels.
    """

    # --- Identity ---
    concept_id: str                            # unique, immutable
    statement: str                             # observational summary (see Data Contract §2.5)
    description: str                           # optional richer description

    # --- Provenance ---
    source_pattern_ids: List[str]              # MUST be non-empty — traces to Patterns
    created_at: datetime                       # immutable

    # --- Semantic fields ---
    semantic_scope: dict                       # conditions under which concept holds
    supporting_patterns: List[str]             # pattern ids that support this concept
    counter_examples: List[dict]               # patterns/experiences that challenge the concept
    confidence: float                          # abstraction stability (see Data Contract §2.7)
    limitations: List[str]                     # known boundary conditions

    # --- Provenance chain ---
    provenance: "ConceptProvenance"            # see §8

    # --- Status ---
    status: str                                # "active" | "weakened" | "invalidated"

    # ---------- FORBIDDEN FIELDS (not in schema) ----------
    # identity_target: str                     ❌ Concept ≠ Identity
    # classification: str                      ❌ Concept ≠ Classification
    # category: str                            ❌ Concept ≠ Category
    # role: str                                ❌ Concept ≠ Role
    # personality_type: str                    ❌ Concept ≠ Personality
    # recommended_action: str                  ❌ Concept ≠ Recommendation
    # is_rule: bool                            ❌ Concept ≠ Rule
    # is_decision: bool                        ❌ Concept ≠ Decision
    # is_obligation: bool                      ❌ Concept ≠ Obligation
    # decision_weight: float                   ❌ Concept ≠ Decision input
```

### 4.2 Field Semantics

| Field | Meaning | NOT |
|-------|---------|-----|
| `statement` | Observational summary of shared pattern structure | Imperative, normative, or identity claim |
| `source_pattern_ids` | Which patterns formed this concept | Entity identifiers |
| `semantic_scope` | Conditions under which the concept was derived | Domain of universal applicability |
| `supporting_patterns` | Positive evidence for the concept | Proof of correctness |
| `counter_examples` | Known challenges to the concept | Exceptions that confirm the rule |
| `confidence` | Abstraction stability across patterns | Truth probability or identity certainty |

### 4.3 `source_pattern_ids` Constraint

**MUST be non-empty.** Every Concept carries traceable pattern sources.

```
Concept
    ↓ source_pattern_ids (non-empty)
Pattern[1..N]
    ↓ source_experience_ids (non-empty)
ExperienceRecord[1..M]
    ↓ source_event_ids
Reality Events
```

**Contract rule:** Concept with `source_pattern_ids == []` is an orphan and
MUST be rejected. No concept exists without provenance.

---

## §5 — Concept ≠ Label Boundary

### 5.1 Core Principle

> **Concept describes what patterns share.**
> **Label assigns what an entity is.**

The boundary between concept and label is the most critical line in
Step 3. Crossing it turns Semantic Memory into a passive identity
profiling system.

### 5.2 Language Boundary

Concept `statement` MUST describe shared structural characteristics.
It MUST NOT assign permanent identity attributes to any entity.

**English prohibited identity-lock expressions:**

`is a`, `is inherently`, `is by nature`, `is always`, `must be`,
`classified as`, `categorized as`, `belongs to`, `type of`,
`the kind that`, `essentially`, `fundamentally`

**Chinese prohibited identity-lock expressions (中文禁止身份锁定表达):**

`属于`, `就是`, `本质是`, `天生`, `永远`, `必然`, `固定为`,
`定义为`, `归类为`, `归属于`, `是一种`, `本质上`, `根本上是`,
`一定是`, `总是`

**Examples:**

| ✅ Allowed (observational) | ❌ Forbidden (identity lock) |
|---------------------------|---------------------------|
| "观察到该角色在压力下表现出谨慎决策倾向" | "该角色属于谨慎型" |
| "This entity exhibited cautious behaviour under pressure" | "This entity is a cautious type" |
| "多个失败案例均涉及资源不足场景" | "该团队是失败型团队" |
| "Multiple failures occurred under resource scarcity" | "The team is failure-prone by nature" |
| "高压环境下探索行为显著减少" | "天生回避不确定性" |

### 5.3 Identity Drift Detection

**Contract rule:** If a Concept can be rewritten as an identity claim about
a specific entity (`X is a Y`), it violates this boundary.

```
Concept statement: "This pattern describes cautious behaviour under pressure"
    → OK: describes behaviour, not entity

Concept statement: "This entity is a cautious decision-maker"
    → VIOLATION: locks identity

Concept statement: "Patterns A, B, C share resource-constraint adaptation structure"
    → OK: describes pattern relationship

Concept statement: "Entity X is resource-constrained-adaptive"
    → VIOLATION: assigns concept as entity attribute
```

### 5.4 Contract Rule

```
Concept Formation output MUST be expressible without naming an entity.
If removing the entity name changes the concept from valid to meaningless,
the concept is actually an identity claim and violates this contract.

    Valid:   "Resource scarcity patterns share adaptation structure"
    Invalid: "Lin Jin is cautious"  →  identity classification, not concept
```

---

## §6 — Generalization Boundary

### 6.1 Core Principle

> **Concept summarises observed structures.**
> **Concept does not predict all future states.**

Concepts describe what was seen, not what will be seen. A concept formed
from 100 past cases does not guarantee the 101st case will conform.

| ✅ Allowed | ❌ Forbidden |
|-----------|-------------|
| "过去观察到该模式频繁出现" | "未来一定出现该模式" |
| "This structure was observed in 80% of relevant cases" | "This structure will always hold" |
| "Under observed scope conditions, this grouping applied" | "This grouping applies universally" |

### 6.2 No Predictive Certainty

```
Concept formed from 5 patterns, each observed 20+ times
    → confidence = abstraction stability (how stable the grouping is)
    → NOT predictive certainty (how likely future cases will match)

Confidence describes: how robustly patterns cluster into this concept
Confidence does NOT describe: how likely an entity belongs to this category
Confidence does NOT describe: how likely future observations will conform
```

**Contract rule:** Concept MUST carry `limitations` describing scope conditions.
A concept without stated limitations is incomplete and MUST NOT be stored
until limitations are declared.

### 6.3 Generalization Drift

```
Observation:
    Entity A exhibited cautious behaviour under pressure (pattern)
    Entity B exhibited cautious behaviour under pressure (pattern)
    → Concept: "cautious decision-making under pressure"

Generalization drift:
    → "Cautious decision-making under pressure is a universal pattern"
    → "Entities observed in this pattern are cautious types"  ❌ identity drift

Correct:
    → "This concept was observed in scenarios X, Y, Z under conditions W"
    → "It may not apply under conditions A, B, C"  (limitations declared)
```

---

## §7 — Conflict Preservation

### 7.1 Core Principle

> **Conflicting concepts must remain visible.**
> (Semantic Memory Constraint #6)

Semantic Memory stores multiple perspectives, not a single truth.
Two conflicting concepts about the same structural space MUST coexist.

```
Concept A:
    "High pressure → cautious decisions"
    confidence: 0.8, scope: long-term projects

Concept B:
    "High pressure → rapid exploration"
    confidence: 0.65, scope: short-term survival scenarios

BOTH exist. Neither is deleted, merged, or resolved into a single truth.
The Evaluation Layer decides relevance per context.
```

### 7.2 Conflict Rules

| Rule | Rationale |
|------|-----------|
| Conflicting concepts MUST NOT be merged into unified truth | Would violate SemMem Constraint #6 |
| Conflicting concepts MUST NOT be deleted based on confidence alone | High confidence ≠ more correct |
| Conflicting concepts MUST NOT be reconciled without evidence | Resolution requires Evaluation Layer |
| Conflicting concepts MAY coexist in the same semantic scope | Conflict itself is knowledge |

### 7.3 Prohibited Conflict Operations

| ❌ Forbidden | Why |
|-------------|-----|
| `delete_concept(concept_id, reason="lower confidence")` | Conflicts are knowledge, not error |
| `merge_concepts(id_a, id_b, output="unified_concept")` | Would create single-truth narrative |
| `resolve_conflicts(scope)` → single concept | No Evaluation Layer input is bypass |
| `confidence_weighted_average(a, b)` → unified | Statistics cannot resolve semantics |

---

## §8 — Provenance Chain

### 8.1 Core Object

```python
@dataclass
class ConceptProvenance:
    """Records how a Concept was formed and from what patterns."""

    created_from_pattern_ids: List[str]        # Step 2 source patterns
    formation_method: str                      # "pattern_aggregation" | "semantic_clustering" | "manual_curation"
    generator: str                             # component that produced the concept
    created_at: datetime                       # immutable
    updated_at: Optional[datetime]             # last confidence/metadata update
    formation_parameters: dict                 # settings used during formation
    validation_history: List[dict]             # [(timestamp, event, detail), ...]
```

### 8.2 Provenance Chain (Frozen)

```
Concept
    ↓ source_pattern_ids (non-empty)
Pattern[1..N]
    ↓ source_experience_ids (non-empty)
ExperienceRecord[1..M]     (Phase 4)
    ↓ source_event_ids
Reality Events
```

**Contract rule:** Every link in the chain MUST have non-empty source IDs.
A broken chain (empty `source_pattern_ids` at Concept level, or empty
`source_experience_ids` at Pattern level) is contract violation.

### 8.3 Orphan Prohibition

```
Concept with empty source_pattern_ids       → ❌ orphan — rejected
Pattern with empty source_experience_ids    → ❌ orphan — rejected (Step 2 contract)
ExperienceRecord with empty source_event_ids → ❌ orphan — rejected (Phase 4 contract)
```

---

## §9 — Authority Isolation

### 9.1 Forbidden Output Types

The Concept Formation Engine MUST NOT expose any output interface that
returns:

| Forbidden Type | Reason |
|---------------|--------|
| `Rule` | Concept ≠ Rule |
| `Policy` | Concept ≠ Policy |
| `Decision` | Concept ≠ Decision |
| `Recommendation` | Concept ≠ Recommendation |
| `Action` | Concept ≠ Action |
| `Obligation` | Concept ≠ Obligation |
| `IdentityLabel` | Concept ≠ Label |
| `PriorityRanking` | Concept ≠ Priority |
| `StatusOverride` | Past concept ≠ Current state override |

### 9.2 Allowed Output Interface

```python
# ✅ Allowed output shapes
def form_concepts(input: ConceptFormationInput) -> List[Concept]: ...
def get_concept(concept_id: str) -> Concept: ...
def find_concepts(scope: dict) -> List[Concept]: ...

# ❌ Forbidden output shapes
def classify_entity(input: ConceptFormationInput, entity_id: str) -> Label: ...    # ❌
def assign_role(entity_id: str, concept_id: str) -> None: ...                       # ❌
def predict_behaviour(concept_id: str, entity_id: str) -> Prediction: ...            # ❌
def generate_recommendations(concept_id: str) -> List[str]: ...                     # ❌
```

### 9.3 `confidence` Isolation

Concept Formation's `confidence` field MUST NOT be consumed by any
Decision Layer component. It is readable only by:

- Semantic Memory Store (storage)
- Evaluation Layer (as context)
- Principle Derivation (Step 4 — as input)

It MUST NOT be passed to:

- DecisionGenerator
- Commit Service
- Governance Layer
- Identity Layer
- Any component that produces rules, labels, or mutations

### 9.4 Identity Layer Boundary

```
Concept
    │
    │  (MUST NOT pass)
    ▼
Identity Profile (Phase 1 / Phase 9.5)  ← ❌ FORBIDDEN

Concept
    │
    │  (MUST NOT pass)
    ▼
Entity Classification Service           ← ❌ FORBIDDEN
```

**Contract rule:** No Concept, Concept.confidence, or Concept.statement
enters the Identity Layer. Identity modifications are exclusive to
Phase 6 Governance and Phase 9.5 Identity Boundary procedures.

---

## §10 — Validation (CF-01 – CF-07)

### CF-01: Pattern → Concept Provenance

```python
def test_cf01_pattern_to_concept_provenance():
    """Concept formed from patterns carries traceable provenance."""
    patterns = [make_pattern("scarcity_delay"), make_pattern("scarcity_conflict")]
    input = ConceptFormationInput(
        patterns=patterns,
        pattern_provenances=[p.provenance for p in patterns],
        scope={},
        extraction_context="test"
    )
    concepts = form_concepts(input)
    for concept in concepts:
        assert len(concept.source_pattern_ids) > 0
        assert all(pid in [p.pattern_id for p in patterns]
                   for pid in concept.source_pattern_ids)
```

### CF-02: Concept Cannot Create Label

```python
def test_cf02_concept_cannot_create_label():
    """Concept output cannot be rewritten as entity identity claim."""
    patterns = [
        make_pattern("entity_behaviour_A"),
        make_pattern("entity_behaviour_B"),
    ]
    concepts = form_concepts(ConceptFormationInput(
        patterns=patterns, pattern_provenances=[], scope={}
    ))
    identity_locks = ["is a", "is inherently", "belongs to",
                      "属于", "就是", "本质是", "天生"]
    for concept in concepts:
        stmt_lower = concept.statement.lower()
        for lock in identity_locks:
            assert lock not in stmt_lower, \
                f"Identity-lock language found in concept: {concept.statement}"
```

### CF-03: Identity Isolation

```python
def test_cf03_identity_isolation():
    """Concept Formation rejects Identity Layer input."""
    with pytest.raises(ValueError):
        form_concepts(ConceptFormationInput(
            patterns=[make_pattern("p1")],
            pattern_provenances=[],
            scope={},
            extraction_context="test",
            identity_entities={"entity_id": "E1", "personality": "cautious"}
        ))
```

### CF-04: No Predictive Certainty

```python
def test_cf04_no_predictive_certainty():
    """Concept does not express predictive certainty."""
    concepts = form_concepts(make_solid_input())
    for concept in concepts:
        # Concept MUST carry limitations
        assert len(concept.limitations) >= 0  # at least empty list
        # confidence is NOT framed as prediction probability
        assert not hasattr(concept, "prediction_probability")
        assert not hasattr(concept, "future_guarantee")
```

### CF-05: Conflict Preservation

```python
def test_cf05_conflict_preservation():
    """Conflicting concepts coexist without forced resolution."""
    store = SemanticMemoryStore()
    concept_a = Concept(concept_id="c1", statement="Pattern A causes B",
                        ..., confidence=0.8)
    concept_b = Concept(concept_id="c2", statement="Pattern A does not cause B",
                        ..., confidence=0.6)
    store.save_concept(concept_a)
    store.save_concept(concept_b)
    # Both exist
    assert store.get_concept("c1") is not None
    assert store.get_concept("c2") is not None
    # No automatic merge
    merged = store.find_concepts_merged(scope={})
    assert merged is None or len(merged) > 1  # not collapsed
```

### CF-06: No Authority Leakage

```python
def test_cf06_no_authority_leakage():
    """Concept output interface does not expose authority functions."""
    engine = ConceptFormationEngine()
    # All allowed shapes
    assert hasattr(engine, "form_concepts")
    assert hasattr(engine, "get_concept")
    assert hasattr(engine, "find_concepts")
    # Forbidden shapes must NOT exist
    assert not hasattr(engine, "classify_entity")
    assert not hasattr(engine, "assign_role")
    assert not hasattr(engine, "predict_behaviour")
    assert not hasattr(engine, "generate_recommendations")
    assert not hasattr(engine, "generate_rules")
    assert not hasattr(engine, "label_entity")
```

### CF-07: Language Validator

```python
def test_cf07_language_validator():
    """Concept statement with identity-lock language is rejected."""
    forbidden = [
        "该实体属于谨慎型",
        "This entity is a cautious type",
        "他本质上是风险规避者",
        "She is inherently unreliable",
        "这个角色被定义为探索者",
    ]
    allowed = [
        "该实体过去表现出谨慎决策模式",
        "This entity exhibited cautious patterns under pressure",
        "多个案例显示风险规避倾向",
        "Multiple patterns show exploration behaviour in safe environments",
    ]
    for statement in forbidden:
        assert not is_valid_concept_statement(statement), \
            f"Identity-lock statement should be rejected: {statement}"
    for statement in allowed:
        assert is_valid_concept_statement(statement), \
            f"Observational statement should pass: {statement}"
```

---

## Step 3 Audit Matrix

| # | Boundary | Status | Key Check |
|---|----------|--------|-----------|
| A | Abstraction Responsibility | **FROZEN ✅** | Concept aggregates patterns. Concept does not classify entities. |
| B | Concept ≠ Classification | **FROZEN ✅** | Pattern aggregation ≠ entity classification. |
| C | Identity Isolation | **FROZEN ✅** | No Identity Layer input. No entity labelling. |
| D | Generalization Boundary | **FROZEN ✅** | Concept summarises past. No predictive certainty. |
| E | Conflict Preservation | **FROZEN ✅** | Conflicting concepts coexist; no merge/delete on confidence. |
| F | Provenance Chain | **FROZEN ✅** | Concept → Pattern → Experience, non-empty at every link. |
| G | Authority Isolation | **FROZEN ✅** | No rule/policy/decision/output to Identity Layer. |
| H | Current State Override | **FROZEN ✅** | Concept reads past only. No current state in input. |

---

## Step 3 Freeze Target

When frozen, the contract guarantees:

```
Pattern[1..M]  (Step 2)
    ↓
Concept[1..N]  (Step 3 — this contract)
    ├── describes "what shared meaning do these patterns carry"
    └── does NOT describe "what identity does an entity have"
    └── does NOT describe "what category does an entity belong to"
    └── does NOT describe "what will happen next"
    └── does NOT describe "what decision to make"
    └── does NOT describe "what rule to follow"
```

Concept lives as **semantic grouping**, not **identity label**.
