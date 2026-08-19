# Phase 10 Semantic Memory — Data Contract v1.0

> Status: **DRAFT 📝** — ABI §1–§3 frozen; Data Contract under review.
> 
> This contract defines how semantic abstractions exist in the system
> **without acquiring authority**. It is the data-level enforcement
> of Phase 10's core axiom:
>
> **Semantic Memory creates abstraction, not authority.**
>
> Every field in this contract either enforces a boundary or prevents a drift.

---

## §1 — Responsibility Boundary

### 1.1 Identity Statement

```
┌─────────────────────────────────────────────────────┐
│  Phase 4 Experience Layer                           │
│  "What happened" → ExperienceRecord                 │
│                                                     │
│         ▼ (pull-based extraction)                   │
│                                                     │
│  Phase 10 Semantic Memory Layer                     │
│  "What patterns persist across experiences"         │
│  → SemanticAbstraction (Pattern → Concept → Princ.) │
└─────────────────────────────────────────────────────┘
```

### 1.2 What Semantic Memory Is

```
Se
Memory: "We have observed X recurring under Y conditions"
Understanding: "X and Y may be related through Z"
Knowledge: "Here is our current best abstraction"
NOT Truth: "This is how the world really works"
NOT Authority: "This is how the system should behave"
```

### 1.3 What Semantic Memory Stores

Semantic Memory stores **derived perspectives** from experience.
It does not store reality itself.

| Stores | Does NOT store |
|--------|---------------|
| Patterns observed across events | Truth claims |
| Concepts abstracted from patterns | Entity identities |
| Principles generalized from concepts | System rules |
| Confidence in abstraction stability | Probabilities of reality |
| Boundary conditions of validity | Universal laws |
| Known counter-examples | Definitive refutations |

### 1.4 Core Declaration

```
Semantic Abstraction  ≠  Truth
Semantic Abstraction  ≠  Rule
Semantic Abstraction  ≠  Decision
Semantic Abstraction  ≠  Identity
Semantic Abstraction  ≠  Obligation
Semantic Abstraction  ≠  Authority

An abstraction is a perspective, not a command.
No abstraction is permanent truth.
```

### 1.5 Identity Isolation Declaration

> **SemanticAbstraction cannot modify, classify, or define Identity Layer entities.**
>
> 中文：SemanticAbstraction 不得修改、定义或锁定 Identity Layer。

**Rationale:** Semantic Memory abstracts patterns and concepts from experience.
It must not drift into character/personality modelling, which is the Identity
Layer's domain (Phase 9.5 Constitution — "Identity cannot drift").

| ❌ Forbidden example | Why |
|---------------------|-----|
| Concept `"Cautious decision-maker"` → Entity `"Lin Jin is a cautious type"` | Concept used as personality label — Identity drift |
| Pattern `"Entity A consistently explores"` → Profile `"Entity A = explorer"` | Pattern solidified into entity identity |
| Principle `"High transparency reduces risk"` → Trait `"All high-performers are transparent"` | Principle applied as identity classifier |

**Contract rule:** A SemanticAbstraction may describe relationships between
observed events. It must not assign permanent attributes to any entity in the
Identity Layer. Identity Layer state is only modifiable via Phase 6 Governance
and Phase 9.5 Identity Boundary procedures.

### 1.6 Layer Relationships

```
Phase 4 (Experience Store)
    │  raw Event → ExperienceRecord
    │  confidence = historical reliability
    ▼
Phase 10 (Semantic Memory) — pull-based
    │  pattern ← concept ← principle
    │  confidence = abstraction stability over N samples
    ▼
Decision Layer — NEVER receives SemanticAbstraction as input
```

---

## §2 — SemanticAbstraction Schema

### 2.1 Core Object

```python
@dataclass
class SemanticAbstraction:
    """Phase 10 core data type.
    
    Every field exists to maintain one invariant:
    this object describes a perspective, not an authority.
    """

    # --- Identity ---
    abstraction_id: str                          # unique, immutable
    level: str                                    # "pattern" | "concept" | "principle"
    statement: str                                # the abstraction text

    # --- Provenance ---
    source_experience_ids: List[str]              # MUST be non-empty
    created_at: datetime                          # immutable after creation

    # --- Confidence ---
    confidence: float                             # [0.0, 1.0] — abstraction stability, NOT truth probability
    scope: List[dict]                             # conditions under which this abstraction was observed

    # --- Status ---
    status: str                                   # "active" | "weakened" | "split" | "deprecated"

    # --- Optional extenders ---
    parent_abstraction_id: Optional[str] = None   # trace back: principle ← concept ← pattern
    counter_examples: List[str] = field(default_factory=list)
    validation_history: List[dict] = field(default_factory=list)

    # ---------- FORBIDDEN FIELDS (not in schema, declared here for contract enforcement) ----------
    # is_rule: bool              ❌  abstraction ≠ constraint
    # is_decision: bool         ❌  abstraction ≠ decision
    # is_authority: bool        ❌  abstraction ≠ authority
    # can_execute: bool         ❌  abstraction ≠ action
    # priority: int             ❌  abstraction ≠ precedence
    # recommendation: str       ❌  abstraction ≠ instruction
    # is_obligation: bool       ❌  abstraction ≠ must-do
```

### 2.2 Field Semantics

| Field | Meaning | NOT |
|-------|---------|-----|
| `abstraction_id` | Unique handle for retrieval and provenance | Not a "knowledge ID" for system-wide reference |
| `level` | Abstraction granularity: pattern/concept/principle | Not a hierarchy of correctness |
| `statement` | Human-readable description of observed structure | Not an instruction or rule |
| `source_experience_ids` | Link to Phase 4 ExperienceRecords that produced this | Not an authority citation |
| `created_at` | When this perspective was formed | Not the "discovery time of truth" |
| `confidence` | How stable this abstraction has been across N observations | Not how likely it maps to objective reality |
| `scope` | Conditions under which the abstraction was observed | Not a truth domain |
| `status` | Current lifecycle state of the abstraction | Not a "correctness" marker |

### 2.3 Allowed `level` Values

| Value | Definition | Example |
|-------|-----------|---------|
| `pattern` | Repeated observation across multiple experiences | "Under resource scarcity, team exploration decreases" |
| `concept` | Semantic grouping of related patterns | "Resource Competition Dynamic" |
| `principle` | Generalized guidance derived from concepts | "Pre-exposing risks earlier reduces downstream costs" |

### 2.4 Forbidden `level` Values

| Value | Reason | Risk |
|-------|--------|------|
| `rule` | Would violate Pattern ≠ Rule constraint | Pattern → Rule |
| `policy` | Would create binding behaviour | Abstraction → Obligation |
| `decision` | Would bypass Decision Layer | Abstraction → Decision |
| `obligation` | Would create action requirement | Observation → Obligation |
| `identity` | Would lock entity to abstraction | Concept → Label |
| `truth` | Would claim objective correctness | Abstraction → Authority |

**Contract rule:** If a `level` value is not in the `allowed` list, the
Semantic Memory Store MUST reject it. No fallback, no coercion, no default.

### 2.5 `statement` Constraints

| ✅ Allowed | ❌ Forbidden |
|-----------|-------------|
| "Under high pressure, teams tend to explore less" | "Teams must reduce exploration" |
| "Resource shortage correlates with increased conflict probability" | "Resource shortage always causes conflict" |
| "In observed cases, early planning improved outcomes" | "Always plan early to succeed" |
| "This pattern appeared in 8/10 similar scenarios" | "This is the correct pattern" |

**Contract rule:** `statement` MUST describe observation or abstraction.
It MUST NOT express normative language or imperative constraints.

**Forbidden imperative patterns (English + Chinese):**

| Category | English | 中文 |
|----------|---------|------|
| Obligation | `must`, `should`, `shall`, `need to`, `required`, `mandatory` | 必须、应该、应当、需要、要求、强制 |
| Absolutes | `always`, `never`, `every`, `all` | 永远、绝不、所有、全部 |
| Prohibition | `forbidden`, `not allowed`, `cannot` (as prescription) | 不得、禁止、不允许 |
| Implicit rule | `the rule is`, `the policy is`, `best practice` | 规则是、标准是、最佳实践 |
| Identity lock | `X is a Y type`, `X is characterized as` | X属于Y类型、X具有Y特征 |

`statement` describes what was observed, not what must be done, not what is prohibited, not what entity type an actor belongs to.

### 2.6 `source_experience_ids` Constraint

**MUST be non-empty.** Every abstraction must trace back to at least one
Phase 4 ExperienceRecord.

```
Abstraction
    ↓ evidence
ExperienceRecord
    ↓ observation
Reality Event
```

**No orphan abstractions.** If an abstraction's source experiences are all
deleted from Phase 4, the abstraction MUST be deprecated, not promoted.

### 2.7 `confidence` Semantics

```
confidence = abstraction stability across observed samples
confidence ≠ truth probability
confidence ≠ authority score
confidence ≠ correctness guarantee
```

| Rule | Rationale |
|------|-----------|
| `confidence ∈ [0.0, 1.0]` | Standard float range |
| `confidence` does NOT grant authority | high confidence ≠ bypass evaluation |
| `confidence` does NOT create obligation | high confidence ≠ must-follow |
| `confidence` is relative to scope | May be 0.9 within scope, 0.0 outside |

---

## §3 — Level Boundary Contract

### 3.1 Pattern Level

**Definition:** Repeated observation of a structure across multiple experiences.

```
Phase 4 Experience[1..N]
    ↓
detect: "when X happens, Y tends to follow"
    ↓
Pattern: "X → Y (observed in M/N cases under conditions C)"
```

**Allowed:**
- `"Resource shortage increases failure probability"`
- `"In 70% of observed cases, early disclosure reduced conflict"`

**Forbidden:**
- `"Resource shortage inevitably causes failure"` ← predication as certainty
- `"X = failure pattern"` ← labeling entity with pattern
- `"When resource shortage, follow protocol"` ← pattern as instruction

**Boundary rule:** A Pattern describes what **was** observed.
It does not prescribe what **should** be done.
It does not predict what **will** happen (that is Phase 9 Simulation).

### 3.2 Concept Level

**Definition:** Semantic grouping of related patterns into an abstract category.

```
Pattern A: "Resource shortage → conflict increase"
Pattern B: "Information asymmetry → trust decrease"
Pattern C: "Competitive pressure → alliance shift"
    ↓
Concept: "Resource Competition Dynamic"
```

**Allowed:**
- `"Resource Competition Dynamic"` — abstraction of interrelated patterns
- `"Trust Spiral"` — pattern cluster label
- `"Scarcity Conflict"` — reusable conceptual category

**Forbidden:**
- `"Character A = Scarcity Conflict type"` — entity labeling with concept
- `"This scenario = Resource Competition"` — scenario fixed to concept
- `"All conflicts are Resource Competition"` — concept as universal classifier

**Boundary rule:** A Concept is a **semantic grouping**, not an **entity identity**.
Concepts describe relationships between patterns, not inherent properties of entities.
Applying a concept to an entity is provisional and reversible.

### 3.3 Principle Level

**Definition:** Generalized guidance derived from validated concepts.

```
Concept A: "Resource Competition Dynamic"
Concept B: "Trust Collapse Pattern"
Concept C: "Information Asymmetry Effect"
    ↓
Principle: "Under uncertainty, resource pressure increases coordination cost"
```

**Allowed:**
- `"Under uncertainty, resource pressure increases coordination cost"`
- `"Pre-exposing risks early reduces downstream failure probability"`
- `"In observed systems, high transparency correlates with faster recovery"`

**Forbidden:**
- `"Must pre-expose risks"` — principle as obligation
- `"Always increase transparency"` — principle as universal rule
- `"Coordination cost is determined by resource pressure"` — principle as deterministic law

**Boundary rule:** A Principle is a **generalized observation**, not an **instruction**.
It does not carry `must`/`should`/`shall` semantics.
It does not override or replace LAYER_RULES.

### 3.4 Cross-Level Contamination Prevention

| Contamination | Path | Prevented by |
|--------------|------|-------------|
| Pattern → Rule | `"X tends to Y"` → `"When X, do Y"` | Level boundary, forbidden fields |
| Concept → Label | `"concept X"` → `"entity is X type"` | Level boundary, Identity restriction |
| Principle → Decision | `"principle suggests P"` → `"execute P"` | Authority Isolation |
| Principle → Rule | `"observed P"` → `"must P"` | Statement constraints |

---

## §4 — Immutable Boundary

### 4.1 Allowed Operations

| Operation | Description | Example |
|-----------|-------------|---------|
| **Append** | Add new abstraction from new experience | `store.add(SemanticAbstraction(...))` |
| **Update confidence** | Adjust stability based on new evidence | `abstraction.confidence = 0.75` |
| **Update metadata** | Add provenance or tags | `abstraction.validation_history.append(...)` |
| **Add provenance** | Link to new supporting experiences | `abstraction.source_experience_ids.append(id)` |
| **Mark deprecated** | Abstract is no longer considered reliable | `abstraction.status = "deprecated"` |
| **Split** | One abstraction becomes two under different conditions | See §3.8 in ABI |

### 4.2 Forbidden Operations

| Operation | Reason | Contract |
|-----------|--------|----------|
| **Rewrite statement** | Would change historical perspective | `statement` is immutable after creation |
| **Change level** | Would alter fundamental nature | `level` is immutable after creation |
| **Change created_at** | Would falsify provenance | `created_at` is immutable |
| **Remove/alter source_experience_ids** | Would break evidence chain | Source provenance is append-only |
| **Delete abstraction entirely** | Would lose perspective, even if wrong | Status = "deprecated" instead |
| **Merge conflicting abstractions** | Would compress conflict into single "truth" | Conflicting abstractions MUST coexist |

### 4.3 Conflict Preservation Rule

> **Conflicting abstractions MUST remain visible.**
> They MUST NOT be merged, resolved, or single-truth-selected.

```
Abstraction A: "Long-term planning improves success rate"
Abstraction B: "Rapid iteration adapts better to uncertain environments"
    ↓
BOTH remain visible
NEITHER is promoted to "correct principle"
Conflict is preserved as knowledge, not resolved as error
```

This is because **conflict is itself knowledge.**
The system knowing "sometimes A applies, sometimes B applies, and we haven't
fully mapped the boundary" is more valuable than prematurely choosing one.

### 4.4 Statement Immutability Detail

The `statement` field is the abstraction's **observed perspective at time of creation**.
Even if the abstraction is later invalidated, its original statement remains as a
historical record of what was believed and why.

| Timeline | Action | `statement` | `status` |
|----------|--------|------------|----------|
| T1 | Created | `"X → Y under C"` | `active` |
| T2 | New evidence found | unchanged | `weakened` |
| T3 | Counter-evidence disproves | unchanged | `deprecated` |

---

## §5 — Authority Isolation

### 5.1 Forbidden Field Classes

SemanticAbstraction MUST NOT contain any field from the following classes:

| Class | Forbidden Fields | Rationale |
|-------|-----------------|-----------|
| **Rule** | `is_rule`, `rule_id`, `enforcement`, `policy` | Pattern ≠ Rule |
| **Decision** | `is_decision`, `decision_id`, `chosen_option` | Abstraction ≠ Decision |
| **Authority** | `is_authority`, `authority_level`, `can_override` | Knowledge ≠ Power |
| **Execution** | `can_execute`, `execution_id`, `action_trigger` | Abstraction ≠ Action |
| **Obligation** | `is_obligation`, `must_follow`, `required_by` | Observation ≠ Obligation |
| **Priority** | `priority`, `rank`, `precedence` | Abstraction ≠ Precedence |
| **Recommendation** | `recommendation`, `recommended_action`, `suggested_step` | Insight ≠ Instruction |

### 5.2 Authority Isolation Contract

```
A SemanticAbstraction may only be:
    - retrieved
    - read
    - referenced as context
    - used for pattern comparison

A SemanticAbstraction may NOT be:
    - passed as Decision input
    - used to override LAYER_RULES
    - referenced in Commit Service
    - used to veto any process
```

### 5.3 Interface-Level Enforcement

The Semantic Memory Store interface MUST reject any query shaped as:

```
# ❌ Forbidden query shapes:
store.find_abstractions(authority=True)
store.get_rule_candidates()
store.get_decisions_from_concepts()

# ✅ Allowed query shapes:
store.find_abstractions(level="pattern", scope=current_context)
store.get_semantic_context(hypothesis=current_hypothesis)
store.get_abstraction(abstraction_id=id)
```

### 5.4 Allowed Fields for Reference

SemanticAbstraction may reference (via metadata/provenance):

- `scope` — conditions under which the abstraction was observed
- `confidence` — stability of the abstraction (NOT authority weight)
- `limitations` — known boundary conditions
- `source` — which experiences produced this
- `counter_examples` — known contradictory evidence

These fields describe the abstraction's **epistemic position**,
not its **decision authority**.

---

## §6 — Provenance Schema

### 6.1 SemanticProvenance

```python
@dataclass
class SemanticProvenance:
    """Records why and how an abstraction exists.
    
    Answers "why does this concept exist?"
    NOT "is this concept correct?"
    """

    created_from_experience_ids: List[str]   # Phase 4 source events (MUST exist)
    extraction_method: str                    # "frequency", "correlation", "clustering", "manual"
    generator: str                            # component/function that produced the abstraction
    created_at: datetime                      # when the abstraction was formed
    updated_at: datetime                      # last confidence/metadata update
    validation_history: List[dict]            # [(timestamp, event_type, detail), ...]
    validation_count: int                     # number of times validated (appended, not overwritten)
```

### 6.2 Validation History Entry

```python
@dataclass
class ValidationEntry:
    timestamp: datetime
    event_type: str         # "new_support" | "counter_example" | "confidence_update" | "scope_narrow" | "split" | "deprecation"
    detail: str             # description of what changed
    triggered_by: str       # experience_id or process that caused the change
```

### 6.3 Provenance Rules

| Rule | Rationale |
|------|-----------|
| `created_from_experience_ids` MUST be non-empty | No orphan abstractions (§8) |
| `extraction_method` MUST be truthfully recorded | Distinguish frequency from inference |
| `created_at` is immutable | History cannot be rewritten |
| `validation_history` is append-only | Every change leaves a trace |
| `validation_count` monotonic | Always increases; not a confidence score |

### 6.4 Provenance Chain

```
Abstraction ← Provenance ← ExperienceRecord[1..N]
    │                          │
    │                          └── source_experience_ids
    │
    └── validation_history[0..M]
         │
         └── each entry linked to triggering experience or process
```

---

## §7 — Validation Tests (SA-01 – SA-10)

### SA-01: Pattern Cannot Become Rule

```python
def test_sa01_pattern_not_rule():
    """Even after 1000 observations, a Pattern is not a Rule."""
    for _ in range(1000):
        exp = store.save_experience(ExperienceRecord(
            hypothesis="test", outcome="consistent", confidence=0.8
        ))
        pattern = semantic.extract_pattern(exp)
        # pattern is NOT in LAYER_RULES
        assert pattern.statement not in LAYER_RULES
        assert hasattr(pattern, "is_rule") is False
```

### SA-02: Concept Cannot Become Label

```python
def test_sa02_concept_not_label():
    """A Concept describes pattern relationships, not entity identity."""
    concept = SemanticAbstraction(
        level="concept",
        statement="Resource Competition Dynamic",
        source_experience_ids=["exp_1", "exp_2", "exp_3"],
        confidence=0.8,
        scope=[],
        status="active"
    )
    # Concept cannot be used to label an entity
    assert concept.level == "concept"
    # Entity identity is NOT in the abstraction
    with pytest.raises(AttributeError):
        _ = concept.entity_type
    with pytest.raises(AttributeError):
        _ = concept.character_label
```

### SA-03: Principle Cannot Become Decision

```python
def test_sa03_principle_not_decision():
    """A Principle cannot be passed to DecisionGenerator."""
    principle = SemanticAbstraction(
        level="principle",
        statement="Under uncertainty, resource pressure increases coordination cost",
        source_experience_ids=["exp_4", "exp_5"],
        confidence=0.85,
        scope=[],
        status="active"
    )
    # DecisionGenerator rejects SemanticAbstraction as input
    decision_generator = DecisionGenerator()
    with pytest.raises(TypeError):
        decision_generator.generate(principle)
```

### SA-04: High Confidence No Authority Escalation

```python
def test_sa04_confidence_no_authority():
    """Highest confidence abstraction still has no authority fields."""
    max_conf_abstraction = SemanticAbstraction(
        level="principle",
        statement="Highly stable observed pattern",
        source_experience_ids=["exp_6"],
        confidence=1.0,
        scope=[],
        status="active"
    )
    # No authority fields exist
    forbidden = ["is_rule", "is_decision", "is_authority", "priority",
                 "recommendation", "can_execute", "is_obligation"]
    for field in forbidden:
        assert not hasattr(max_conf_abstraction, field)
    # Even at max confidence, it cannot bypass evaluation
    assert max_conf_abstraction.level == "principle"
    assert max_conf_abstraction.confidence == 1.0
    # Evaluation was still called (asserted by evaluation layer test)
```

### SA-05: Conflicting Abstractions Preserved

```python
def test_sa05_conflict_preserved():
    """Conflicting abstractions MUST both remain visible."""
    pattern_a = SemanticAbstraction(
        abstraction_id="p_a",
        level="pattern",
        statement="Long-term planning improves success",
        source_experience_ids=["exp_7"],
        confidence=0.8,
        scope=[],
        status="active"
    )
    pattern_b = SemanticAbstraction(
        abstraction_id="p_b",
        level="pattern",
        statement="Rapid iteration adapts better to uncertainty",
        source_experience_ids=["exp_8"],
        confidence=0.75,
        scope=[],
        status="active"
    )
    store.add(pattern_a)
    store.add(pattern_b)
    # Both exist in store
    retrieved_a = store.get(pattern_a.abstraction_id)
    retrieved_b = store.get(pattern_b.abstraction_id)
    assert retrieved_a is not None
    assert retrieved_b is not None
    # Neither was merged or deleted
    assert retrieved_a.statement != retrieved_b.statement
```

### SA-06: Source Provenance Required

```python
def test_sa06_provenance_required():
    """Every SemanticAbstraction MUST have non-empty source_experience_ids."""
    with pytest.raises(ValueError):
        SemanticAbstraction(
            level="pattern",
            statement="Orphan abstraction",
            source_experience_ids=[],   # empty — rejected
            confidence=0.5,
            scope=[],
            status="active"
        )
    with pytest.raises(ValueError):
        # No provenance at all is also rejected
        SemanticAbstraction(
            level="pattern",
            statement="No source",
            # source_experience_ids missing
            confidence=0.5,
            scope=[],
            status="active"
        )
```

### SA-07: Past Abstraction Cannot Override Current State

```python
def test_sa07_past_not_override():
    """Past abstractions cannot prevent formation of conflicting new ones."""
    # Past abstraction
    past = SemanticAbstraction(
        level="pattern",
        statement="Resource pressure → conflict",
        source_experience_ids=["exp_9"],
        confidence=0.9,
        scope=[],
        status="active"
    )
    store.add(past)
    # New contradictory experience
    new_exp = ExperienceRecord(
        hypothesis="cooperation_strategy",
        outcome="success",
        confidence=0.8
    )
    new_pattern = semantic.extract_pattern(new_exp)
    # new_pattern describes: "Resource pressure → cooperation"
    # It exists alongside past, not replacing it
    assert store.get(past.abstraction_id) is not None
    assert store.get(new_pattern.abstraction_id) is not None
```

### SA-08: No Orphan Abstraction

```python
def test_sa08_no_orphan():
    """If all source experiences are removed, the abstraction is deprecated, not promoted."""
    abstraction = SemanticAbstraction(
        level="pattern",
        statement="Test pattern",
        source_experience_ids=["exp_orphan"],
        confidence=0.7,
        scope=[],
        status="active"
    )
    store.add(abstraction)
    # Simulate Phase 4 source removal
    store.simulate_source_removal("exp_orphan")
    # Abstraction should be deprecated, not kept as active
    updated = store.get(abstraction.abstraction_id)
    assert updated.status == "deprecated"
    # It should NOT be promoted to any higher level
    assert updated.level == "pattern"
```

### SA-09: No Forbidden Authority Fields

```python
def test_sa09_no_forbidden_fields():
    """SemanticAbstraction schema MUST NOT contain forbidden authority fields."""
    forbidden = ["is_rule", "is_decision", "is_authority", "can_execute",
                 "priority", "recommendation", "is_obligation"]
    schema_fields = [f.name for f in fields(SemanticAbstraction)]
    for field in forbidden:
        assert field not in schema_fields, f"Field '{field}' is forbidden in SemanticAbstraction"
```

### SA-10: Delete/Rewrite History Blocked

```python
def test_sa10_delete_rewrite_blocked():
    """Semantic Memory Store MUST reject delete and statement rewrite operations."""
    abstraction = SemanticAbstraction(
        level="pattern",
        statement="Original observed pattern",
        source_experience_ids=["exp_10"],
        confidence=0.6,
        scope=[],
        status="active"
    )
    store.add(abstraction)
    # Delete rejected
    with pytest.raises(OperationNotAllowed):
        store.delete(abstraction.abstraction_id)
    # Statement rewrite rejected
    with pytest.raises(OperationNotAllowed):
        store.update_statement(abstraction.abstraction_id, "Rewritten")
    # Level change rejected
    with pytest.raises(OperationNotAllowed):
        store.update_level(abstraction.abstraction_id, "principle")
    # Deprecation IS allowed
    store.deprecate(abstraction.abstraction_id)
    assert store.get(abstraction.abstraction_id).status == "deprecated"
```

---

## Contract Status

| Section | Status |
|---------|--------|
| **§1 — Responsibility Boundary** | **FROZEN ✅** |
| §1.5 Identity Isolation | FROZEN (integral to §1) |
| **§2 — SemanticAbstraction Schema** | **FROZEN ✅** |
| **§3 — Level Boundary Contract** | **FROZEN ✅** |
| **§4 — Immutable Boundary** | **FROZEN ✅** |
| **§5 — Authority Isolation** | **FROZEN ✅** |
| §6 — Provenance Schema | **DRAFT 📝** |
| §7 — Validation Tests (SA-01–10) | **DRAFT 📝** |

### Frozen Core Invariants

```
1. Every abstraction must trace to evidence (no orphans)
2. Every level must be pattern|concept|principle (no rule|decision|identity)
3. Every statement must be observational (no imperative language)
4. Confidence = abstraction stability, NOT truth or authority
5. No authority fields exist in the schema
6. History is immutable (no delete, no rewrite, no merge)
7. Conflicting abstractions coexist
```
