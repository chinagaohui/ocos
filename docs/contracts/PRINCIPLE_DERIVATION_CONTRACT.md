# Phase 10 Semantic Memory — Principle Derivation Contract v1.0

> Status: **FROZEN ✅** — Step 4 complete. Proceeding to Step 5 (Provenance Layer).
>
> Step 4 is the third and most dangerous **generation layer** of Phase 10.
>
> Step 2 risk: frequency → rule
> Step 3 risk: similarity → identity
> **Step 4 risk: understanding → authority**
>
> A Principle is the highest form of abstraction in Semantic Memory.
> It is also the closest to "best practice" → Policy → Decision drift.
>
> Every principle carries the seed of its own corruption:
> "This is how things usually go" → "This is how things should go."

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
Phase 10 Step 3 — Concept Formation
    │
    ▼
Concept[1..N]   (semantic groupings)
    │
Phase 10 Step 4 — Principle Derivation (this contract — THE LAST ABSTRACTION)
    │
    ├── synthesises higher-level understanding from concepts
    ├── expresses structural insight about how observed systems tend to behave
    ├── can inform evaluation and reasoning (contextual reference, not command)
    └── does NOT produce rules, policies, decisions, obligations, or recommendations
    │
    ▼
Principle[1..K]   (guided understanding, NOT commanded action)
```

### 1.2 Core Declaration

> **Principle may guide understanding.**
> **Principle cannot command action.**
> **A principle describes how things have been observed to work,**
> **not how things must work.**

| ✅ Allowed | ❌ Forbidden |
|-----------|-------------|
| Synthesise higher-level understanding from concepts | Generate rules or rule-like statements |
| Express observed structural tendencies | Produce policies or best-practice mandates |
| Support evaluation and reasoning (as reference) | Command decisions or actions |
| Describe "this system tends to behave this way under these conditions" | Prescribe "this is how the system should behave" |
| Carry scope and limitations explicitly | Claim universality or eternal validity |

### 1.3 What Principle Derivation Is NOT

| NOT this | Why |
|----------|-----|
| Rule Mining | Rules prescribe behaviour. Principles describe observed tendencies. |
| Policy Generator | Policies mandate action. Principles inform understanding. |
| Decision Engine | Decisions commit resources. Principles are reference only. |
| Best Practice Catalogue | "Best" implies normative judgment. Principles are structural observations. |
| Truth Discovery | Principles are revisable abstractions. They are not discovered truths. |
| Moral Code | Principles describe how things work, not how they should work ethically. |

### 1.4 The Power Drift Ladder

```
Pattern     "X tends to co-occur with Y"                       ✅ observational
    │
Concept     "X and Y share a structural relationship under Z"   ✅ semantic
    │
Principle   "Systems operating under Z tend toward X-Y         ⚠️  highest safe level
             dynamics"
    │
    │   ╔═══════════════════════════════════════════╗
    │   ║  ❌ CROSSING THIS LINE = AUTHORITY DRIFT  ║
    │   ╚═══════════════════════════════════════════╝
    │
    ▼
"Best practice":  "Under Z, adopt X-Y strategy"               ❌ policy
    │
"Policy":         "Systems under Z MUST implement X-Y"         ❌ rule
    │
"Decision":       "Apply X-Y to current system"                ❌ action
```

**Contract rule:** Principle Derivation output MUST stay above the drift line.
Any output that can be rewritten as "must / should / ought to / need to"
without changing its meaning is a policy or rule, not a principle.

---

## §2 — Input Contract

### 2.1 PrincipleFormationInput

```python
@dataclass
class PrincipleFormationInput:
    """Input for principle derivation.

    Principle Derivation receives Concepts (Step 3 output) and provenance.
    It MUST NOT receive Identity Layer data, current state, decision history,
    or any external normative framework.
    """

    # --- Required ---
    concepts: List[Concept]                    # Step 3 output concepts
    concept_provenances: List[ConceptProvenance]  # Step 3 provenance chain

    # --- Optional ---
    scope: dict                                # context scope for synthesis
    derivation_context: str = "semantic_memory"

    # --- Forbidden inputs (MUST NOT be present) ---
    # external_policies: List[Any]             ❌ Would introduce external norms
    # rules: List[Rule]                        ❌ Would produce rule hierarchy
    # identity_profiles: dict                  ❌ Identity is off-limits
    # current_state: dict                      ❌ Current state not read
    # decision_history: List[Any]              ❌ Decision history bypasses lifecycle
    # ethical_frameworks: List[str]            ❌ Moral codes are external authority
```

### 2.2 Prohibited Inputs

| ❌ Forbidden input | Why |
|-------------------|-----|
| External policies or rules | Would turn principle derivation into rule justification |
| Identity Profiles | Principle about entities → identity lock (violates Step 3 §5) |
| Current State | Past principle would override current reality (SA-04/SA-07 violation) |
| Decision History | Would create "what worked before → must work again" reinforcement loop |
| Ethical/Moral frameworks | Would introduce normative authority into structural observation |
| User-provided "best practices" | Would inject external authority into Semantic Memory |

### 2.3 Input Contract Rule

```
PrincipleFormationInput

    ✅ concepts[1..K]                       — allowed (Step 3 output)
    ✅ concept_provenances[1..K]            — allowed
    ✅ scope                                — allowed
    ❌ external_policies: List[Policy]      — forbidden
    ❌ identity_profiles: dict              — forbidden
    ❌ current_state: dict                  — forbidden
    ❌ decision_history: List[Decision]     — forbidden
    ❌ ethical_frameworks: List[str]        — forbidden
```

**Contract rule:** If any input field contains a normative assertion
("must", "should", "ought to", "best practice", "correct", "proper"),
the input MUST be rejected. Principle Formation receives observations,
not prescriptions.

---

## §3 — Principle Generation Boundary

### 3.1 What a Principle Is

A Principle is a **higher-level synthesis** of multiple concepts,
expressing a structural insight about how observed systems tend to
behave under certain conditions. It is the most abstract form of
Semantic Memory — and the one closest to authority drift.

```
✅ Allowed:
    Concept A: "Resource scarcity → cautious decision-making"
    Concept B: "Resource scarcity → decreased exploration"
    Concept C: "Resource scarcity → increased information-seeking"

    → Principle: "Systems under resource scarcity tend to prioritise
      preservation over expansion, conditional on survival threshold"

    → This is structural insight about observed dynamics.
    → It is NOT "systems should conserve resources under scarcity"
    → It is NOT "always prioritise preservation"
```

### 3.2 Principle ≠ Rule

| ✅ Principle (allowed) | ❌ Rule (forbidden) |
|------------------------|-------------------|
| "Systems under scarcity tend toward conservative behaviour" | "Systems under scarcity MUST conserve resources" |
| "Conflict probability increases when resource pressure exceeds threshold T" | "Avoid conflict when resources are low" |
| "Information-seeking correlates with uncertainty under these conditions" | "Always seek more information under uncertainty" |

**Contract rule:** A Principle expresses tendency, observation, correlation.
A rule expresses obligation, prohibition, or recommendation.
If a Principle's statement can be prefixed with "You must" or "You should"
and still make sense, it is a rule, not a principle.

### 3.3 Principle Generation Process

```
Concepts[1..K]
    │
    ├── 1. Identify structural commonalities across concepts
    ├── 2. Synthesise higher-level description of observed dynamics
    ├── 3. Tag scope conditions and known limitations
    ├── 4. Declare counter-examples and boundary cases
    └── 5. Output: Principle[1..J]

    NO step in this process produces:
        - actionable recommendations
        - normative statements
        - behavioural prescriptions
        - classification decisions
```

---

## §4 — Principle Schema

### 4.1 Core Object

```python
@dataclass
class Principle:
    """Step 4 output: a high-level structural insight.

    Principle synthesises understanding from multiple concepts.
    It describes observed system dynamics. It does NOT command action.
    """

    # --- Identity ---
    principle_id: str                          # unique, immutable
    statement: str                             # structural insight (see Data Contract §2.5)

    # --- Provenance ---
    source_concept_ids: List[str]              # MUST be non-empty — traces to Concepts
    created_at: datetime                       # immutable

    # --- Semantic fields ---
    scope: dict                                # conditions under which principle holds
    supporting_concepts: List[str]             # concept ids that support this principle
    counter_examples: List[dict]               # concepts/patterns that challenge the principle
    confidence: float                          # abstraction stability (see Data Contract §2.7)
    limitations: List[str]                     # MUST be non-empty — principle without limitations
                                               # is incomplete by contract

    # --- Provenance chain ---
    provenance: "PrincipleProvenance"          # see §11

    # --- Status ---
    status: str                                # "active" | "weakened" | "invalidated"

    # --- Applicability ---
    applicability: dict                        # explicit conditions of applicability (see §9)

    # ---------- FORBIDDEN FIELDS (not in schema) ----------
    # rule_text: str                           ❌ Principle ≠ Rule
    # policy: str                              ❌ Principle ≠ Policy
    # decision_action: str                     ❌ Principle ≠ Decision
    # recommendation: str                      ❌ Principle ≠ Recommendation
    # obligation: str                          ❌ Principle ≠ Obligation
    # best_practice: str                       ❌ Principle ≠ Best Practice
    # truth_value: bool                        ❌ Principle ≠ Truth
    # is_authoritative: bool                   ❌ Principle ≠ Authority
    # priority: int                            ❌ Principle ≠ Priority
    # enforcement_mechanism: str               ❌ Principle ≠ Enforcement
```

### 4.2 Field Semantics

| Field | Meaning | NOT |
|-------|---------|-----|
| `statement` | Structural insight about observed system dynamics | Normative, prescriptive, or imperative claim |
| `source_concept_ids` | Which concepts formed this principle | Entity identifiers or authority references |
| `scope` | Conditions under which the principle was observed | Domain of universal applicability |
| `supporting_concepts` | Positive evidence for the principle | Proof of correctness or universal truth |
| `counter_examples` | Known challenges to the principle | Exceptions that confirm the rule |
| `confidence` | Abstraction stability across concepts | Truth probability or authority weight |
| `limitations` | **REQUIRED.** Known boundary conditions of the insight | Optional metadata |
| `applicability` | Explicit conditions where principle may/may not apply | Universal scope |

### 4.3 `source_concept_ids` Constraint

**MUST be non-empty.** Every Principle carries traceable concept sources.

```
Principle
    ↓ source_concept_ids (non-empty, min 2 recommended)
Concept[1..N]
    ↓ source_pattern_ids (non-empty)
Pattern[1..M]
    ↓ source_experience_ids (non-empty)
ExperienceRecord[1..K]
    ↓ source_event_ids
Reality Events
```

**Contract rule:** Principle with `source_concept_ids == []` is an orphan
and MUST be rejected. Principles formed from a single concept are strongly
discouraged (recommended minimum: 2+ concepts for synthesis).

### 4.4 `limitations` Constraint

**MUST be non-empty.** A principle without stated limitations is an
incomplete abstraction and presents authority drift risk.

```
Principle: "Systems under resource scarcity tend toward conservative
            behaviour under survival thresholds"
Limitations:
    - Does NOT apply when novelty reward exceeds survival risk
    - Does NOT apply when external intervention is available
    - May not hold in multi-agent cooperation scenarios
```

**Contract rule:** A Principle with `limitations == []` MUST NOT be stored.
The limitations list is the only thing that prevents a principle from
being misinterpreted as universal truth.

---

## §5 — Principle ≠ Rule Boundary

### 5.1 Core Principle

> **A principle describes observed tendency.**
> **A rule prescribes required behaviour.**
> **Principle Derivation produces the former, never the latter.**

### 5.2 Language Boundary

Principle `statement` MUST describe structural tendency.
It MUST NOT express obligation, prohibition, or normative command.

**English prohibited rule-language expressions:**

`must`, `must not`, `should`, `should not`, `shall`, `shall not`,
`required to`, `required not to`, `obligated to`, `prohibited from`,
`need to`, `have to`, `ought to`, `always`, `never`, `rule:`,
`policy:`, `best practice:`

**Chinese prohibited rule-language expressions (中文禁止规则语言表达):**

`必须`, `不得`, `禁止`, `应该`, `应当`, `不该`, `不应该`,
`需要`, `务必`, `一定要`, `绝不能`, `规则:`, `政策:`,
`最佳实践:`, `正确做法:`, `规定:`, `按...进行`

**Examples:**

| ✅ Allowed (tendency) | ❌ Forbidden (rule) |
|-----------------------|-------------------|
| "Systems under scarcity tend toward conservative behaviour" | "Systems under scarcity MUST conserve resources" |
| "Conflict probability increases when pressure exceeds threshold" | "Avoid conflict when pressure is high" |
| "Information-seeking correlates with uncertainty" | "Always seek more information" |
| "资源受限时系统倾向保守行为" | "资源受限时必须保守" |
| "压力超过阈值时冲突概率上升" | "压力高时应避免冲突" |

### 5.3 The "Should Test"

**Contract rule:** If a Principle's statement can be meaningfully prefixed
with "You should" or "You must" without changing its grammatical structure,
it is a rule, not a principle.

```
"You should systems under scarcity tend toward conservative behaviour"
    → nonsense → is a principle ✅

"You must conserve resources under scarcity"
    → reads as a command → is a rule ❌
```

### 5.4 Contract Enforcement

```
is_valid_principle_statement(statement):
    IF statement matches any prohibited rule-language (EN or CN):
        REJECT
    IF statement passes "should test":
        REJECT
    IF statement contains imperative verb (command form):
        REJECT
    ELSE:
        ACCEPT (observational tendency)
```

---

## §6 — Principle ≠ Policy Boundary

### 6.1 Core Principle

> **A policy is a normative framework that guides action.**
> **A principle is an observational framework that informs understanding.**
> **These are distinct layers.**

### 6.2 Principle vs Policy

| Dimension | Principle (✅ allowed) | Policy (❌ forbidden) |
|-----------|----------------------|----------------------|
| Nature | Observational | Normative |
| Output | "Systems under X tend toward Y" | "Under X, adopt Y approach" |
| Tone | Descriptive | Prescriptive |
| Scope | "Under these observed conditions" | "In all such cases" |
| Enforcement | None — reference only | Sets expectations for behaviour |
| Revision | When evidence changes | When authority decides |

### 6.3 Policy Drift Protection

**Contract rule:** Principle Derivation output MUST NOT contain:

- Language of recommendation (`recommend`, `suggest`, `advise`)
- Language of best practice (`best practice`, `ideal approach`, `optimal strategy`)
- Language of strategy (`strategy:`, `approach:`, `tactic:`)
- Action-oriented framing (`to improve X, do Y`, `for better results, Z`)

```
❌ Forbidden policy drift:
    "Under resource scarcity, the best practice is to conserve"
    ⟶ Policy, not principle

✅ Allowed principle:
    "Resource scarcity correlates with conservative behaviour in observed systems"
    ⟶ Principle, structural observation
```

---

## §7 — Principle ≠ Decision Boundary

### 7.1 Core Principle

> **A decision commits resources, changes state, or binds an agent.**
> **A principle is a reference for understanding — not a command to act.**
> **The gap between "understanding" and "doing" is inviolable.**

### 7.2 Principle vs Decision

| Dimension | Principle (✅ allowed) | Decision (❌ forbidden) |
|-----------|----------------------|----------------------|
| What it does | Informs context | Changes state |
| Relationship to action | Reference only | Action trigger |
| Binding | Not binding | Binding (commit) |
| Reversibility | Always revisable | May have committed consequences |
| Consumer | Evaluation Layer, Reasoning | Actor, Governance |

### 7.3 Decision Drift Protection

**Contract rule:** Principle output MUST NOT:

- Enter a DecisionGenerator or Commit Service directly
- Be labelled as "decision input" or "recommendation source"
- Be consumed by any component that produces action commands
- Carry fields like `decision_weight`, `priority_score`, `override_level`

### 7.4 Confidence ≠ Decision Weight

```
Principle.confidence = 0.95
    → means: "this principle consistently synthesises from stable concepts"
    → does NOT mean: "this principle should outrank other considerations"

Decision weight is determined by:
    - Current context evaluation (Evaluation Layer)
    - Multiple principles, patterns, and concepts (not just one)
    - Real-time constraints (Current State)
    - NOT by principle.confidence alone
```

---

## §8 — Evidence Requirement

### 8.1 Core Principle

> **Every principle must be supported by evidence.**
> **The evidence is the provenance chain — not an external citation.**

### 8.2 Evidence Threshold

| Requirement | Rule |
|-------------|------|
| Source concepts | `source_concept_ids` MUST be non-empty (≥2 recommended) |
| Source patterns | Every concept in the chain must carry `source_pattern_ids` |
| Source experiences | Every pattern must carry `source_experience_ids` |
| Limitations | `limitations` MUST be non-empty |
| Counter-examples | `counter_examples` MAY be empty (absence of counter-evidence ≠ proof) |

### 8.3 The Evidence Test

**Contract rule:** For any Principle, it MUST be possible to trace its
evidence path to at least one concrete ExperienceRecord:

```
Principle
    → source_concept_ids[0] → Concept
        → source_pattern_ids[0] → Pattern
            → source_experience_ids[0] → ExperienceRecord
                → source_event_ids → Reality Event  (Phase 4 chain)
```

If any link is broken (empty source list), the Principle is orphaned
and MUST be rejected.

---

## §9 — Applicability Boundary

### 9.1 Core Principle

> **Every principle has a scope.**
> **No principle applies universally.**
> **Applicability is bounded by evidence, not by claim.**

### 9.2 Applicability Schema

```python
@dataclass
class Applicability:
    """Declares where a principle has been observed to hold."""

    observed_contexts: List[str]        # e.g., ["long_term_projects", "stability_phase"]
    observed_domains: List[str]         # e.g., ["interpersonal_dynamics", "resource_management"]
    known_non_applicable: List[str]     # contexts where principle is known NOT to apply
    conditions: str                     # "observed under threshold T"
    derived_from_observations: int      # count of observations supporting applicability
```

### 9.3 Applicability Rules

| Rule | Rationale |
|------|-----------|
| Principle MUST declare where it has been observed to apply | Prevents implicit universality |
| Principle MUST declare known non-applicable contexts | Prevents over-extension |
| `observed_contexts` MUST be populated from provenance | Not from external authority |
| Applicability is always revisable | New observations may extend or narrow scope |

**Contract rule:** A Principle without an `applicability` section that
declares both positive and negative scope conditions is incomplete
and MUST NOT be stored as active.

---

## §10 — Conflict Preservation

### 10.1 Core Principle

> **Conflicting principles must remain visible.**
> (Semantic Memory Constraint #6)

Two principles expressing contradictory structural insights about
similar scope conditions MUST coexist. The layer that resolves
conflict is Evaluation (outside Semantic Memory).

```
Principle X: "Resource scarcity promotes conservative behaviour"
    confidence: 0.85, scope: long-term survival scenarios

Principle Y: "Resource scarcity promotes rapid exploration
              when novelty reward > survival risk"
    confidence: 0.70, scope: high-variance reward environments

BOTH exist. Neither is chosen as "correct".
The Evaluation Layer selects relevance per context.
```

### 10.2 Conflict Rules

| Rule | Rationale |
|------|-----------|
| Conflicting principles MUST NOT be merged | Would violate SemMem Constraint #6 |
| Conflicting principles MUST NOT be deleted on confidence alone | High confidence ≠ "correct" |
| Conflicting principles MUST NOT be ranked by global priority | Relevance is context-dependent |
| Conflicting principles MAY be conditionally scoped by applicability | Both can be true in different contexts |

### 10.3 Prohibited Operations

| ❌ Forbidden | Why |
|-------------|-----|
| `delete_principle(id, reason="lower_confidence")` | Conflict is knowledge, not error |
| `merge_principles(id_a, id_b) → unified` | Would create single-truth abstraction |
| `select_winning_principle(scope) → one` | Would bypass Evaluation Layer |
| `resolve_conflicts(all_principles) → ranked` | Global ranking is authority, not memory |

---

## §11 — Provenance Chain

### 11.1 Core Object

```python
@dataclass
class PrincipleProvenance:
    """Full provenance record for a Principle."""

    created_from_concept_ids: List[str]      # Step 3 source concepts
    formation_method: str                    # "structural_synthesis" | "cross_concept_aggregation"
    generator: str                           # component that produced the principle
    created_at: datetime                     # immutable
    updated_at: Optional[datetime]           # last metadata update
    validation_history: List[dict]           # [(timestamp, event, detail), ...]
    evidence_depth: int                      # how many experience records support this
    last_evidence_review: datetime           # when evidence was last verified
```

### 11.2 Full Chain (Frozen)

```
Principle
    ↓ source_concept_ids (non-empty, ≥2 recommended)
Concept[1..N]
    ↓ source_pattern_ids (non-empty)
Pattern[1..M]
    ↓ source_experience_ids (non-empty)
ExperienceRecord[1..K]
    ↓ source_event_ids
Reality Events
```

### 11.3 Orphan Prohibition

```
Principle with empty source_concept_ids        → ❌ orphan — rejected
Concept with empty source_pattern_ids          → ❌ orphan — rejected (Step 3)
Pattern with empty source_experience_ids       → ❌ orphan — rejected (Step 2)
ExperienceRecord with empty source_event_ids   → ❌ orphan — rejected (Phase 4)
```

---

## §12 — Authority Isolation

### 12.1 Forbidden Output Types

The Principle Derivation Engine MUST NOT expose any output interface
that returns:

| Forbidden Type | Reason |
|---------------|--------|
| `Rule` | Principle ≠ Rule |
| `Policy` | Principle ≠ Policy |
| `Decision` | Principle ≠ Decision |
| `Recommendation` | Principle ≠ Recommendation |
| `Action` | Principle ≠ Action |
| `Obligation` | Principle ≠ Obligation |
| `Strategy` | Principle ≠ Strategy |
| `BestPractice` | Principle ≠ Normative Framework |
| `PriorityRanking` | Principle ≠ Priority |
| `StatusOverride` | Past principle ≠ Current state override |

### 12.2 Allowed Output Interface

```python
# ✅ Allowed output shapes
def derive_principles(input: PrincipleFormationInput) -> List[Principle]: ...
def get_principle(principle_id: str) -> Principle: ...
def find_principles(scope: dict) -> List[Principle]: ...

# ❌ Forbidden output shapes — authority interfaces
def generate_policy(principle_id: str) -> Policy: ...                      # ❌
def recommend_action(principle_id: str, context: dict) -> Action: ...      # ❌
def decide(principle_id: str, state: dict) -> Decision: ...                # ❌
def create_rule(principle_id: str) -> Rule: ...                             # ❌
def classify_by_principle(entity_id: str, principle_id: str) -> Label: ... # ❌
def rank_principles(context: dict) -> List[dict]: ...                       # ❌
```

### 12.3 `confidence` Isolation

Principle `confidence` MUST NOT be consumed by any Decision Layer
component. It is readable only by:

- Semantic Memory Store (storage)
- Evaluation Layer (as contextual reference for relevance)
- Higher reasoning components (as observational data, not authority)

It MUST NOT be passed to:

- DecisionGenerator
- Commit Service
- Governance Layer
- Identity Layer
- Any component that produces rules, policies, actions, or labels

### 12.4 The Final Gate

**Contract rule:** Principle is the last abstraction layer in Semantic
Memory. No component below Principle Derivation (higher abstraction)
may exist within Phase 10. The next layer after Principle is
autonomous evaluation and reasoning (Phase 11+), which treats
principles as **contextual reference, not authority**.

```
Semantic Memory (Phase 10) vvvvvvvvvvvvvvvvvvvvvvvv  BOUNDARY

    Principle[1..K]     ← last abstraction output

╔════════════════════════════════════════════════════╗
║  ❌ NO higher abstraction exists in Phase 10       ║
║  No "meta-principle", "axiom", "universal truth"  ║
║  No "policy generator", "rule factory"             ║
╚════════════════════════════════════════════════════╝

    Principle flows to (readable by):
        → Evaluation Layer (for relevance context)
        → Reasoning Layer (for structural insight)
        → Experience Store (for reference)

    Principle does NOT flow to:
        → Decision Layer
        → Governance Layer
        → Identity Layer
```

---

## §13 — Validation (PD-01 – PD-09)

### PD-01: Principle → Concept → Pattern → Experience Provenance

```python
def test_pd01_full_provenance_chain():
    """Principle carries traceable chain to at least one ExperienceRecord."""
    principles = derive_principles(make_full_input())
    for principle in principles:
        assert len(principle.source_concept_ids) > 0
        chain_ok = False
        for cid in principle.source_concept_ids:
            concept = store.get_concept(cid)
            assert concept is not None
            assert len(concept.source_pattern_ids) > 0
            for pid in concept.source_pattern_ids:
                pattern = store.get_pattern(pid)
                assert pattern is not None
                assert len(pattern.source_experience_ids) > 0
                chain_ok = True
        assert chain_ok, "No complete evidence chain found for principle"
```

### PD-02: Principle ≠ Rule — Language Rejection

```python
def test_pd02_principle_not_rule_language():
    """Principle with rule language (must/should/always) is rejected."""
    forbidden = [
        "Systems under scarcity MUST conserve",
        "You should avoid conflict when pressure is high",
        "Always seek more information under uncertainty",
        "资源受限时必须保守",
        "压力高时应避免冲突",
        "Always follow this guideline",
        "This is the correct approach",
    ]
    allowed = [
        "Systems under scarcity tend toward conservative behaviour",
        "Conflict probability increases when pressure exceeds threshold",
        "Information-seeking correlates with uncertainty",
        "资源受限时系统倾向保守行为",
    ]
    for statement in forbidden:
        assert not is_valid_principle_statement(statement), \
            f"Rule language should be rejected: {statement}"
    for statement in allowed:
        assert is_valid_principle_statement(statement), \
            f"Observational tendency should pass: {statement}"
```

### PD-03: Principle ≠ Policy — Normative Rejection

```python
def test_pd03_principle_not_policy():
    """Principle with best-practice or strategy language is rejected."""
    policy_phrases = [
        "best practice",
        "optimal strategy",
        "推荐采用",
        "正确做法",
    ]
    for phrase in policy_phrases:
        assert not is_valid_principle_statement(phrase), \
            f"Policy language should be rejected: {phrase}"
```

### PD-04: Principle ≠ Decision — Authority Isolation

```python
def test_pd04_principle_not_decision():
    """Principle engine does not expose decision interfaces."""
    engine = PrincipleDerivationEngine()
    assert hasattr(engine, "derive_principles")
    assert hasattr(engine, "get_principle")
    assert hasattr(engine, "find_principles")
    assert not hasattr(engine, "generate_policy")
    assert not hasattr(engine, "recommend_action")
    assert not hasattr(engine, "decide")
    assert not hasattr(engine, "create_rule")
    assert not hasattr(engine, "rank_principles")
```

### PD-05: Evidence Requirement — Limitations MUST Exist

```python
def test_pd05_principle_requires_limitations():
    """Principle with empty limitations is rejected."""
    input_data = make_valid_input()
    with patch_object_attr(Principle, "limitations", []):
        with pytest.raises(ContractViolation):
            derive_principles(input_data)
```

### PD-06: Applicability Must Be Declared

```python
def test_pd06_applicability_declared():
    """Principle must have applicability section with scope."""
    principles = derive_principles(make_full_input())
    for principle in principles:
        assert hasattr(principle, "applicability")
        assert len(principle.applicability.get("observed_contexts", [])) > 0
        assert "known_non_applicable" in principle.applicability
```

### PD-07: Conflict Preservation

```python
def test_pd07_conflict_preservation():
    """Conflicting principles coexist without forced resolution."""
    store = SemanticMemoryStore()
    p_a = Principle(principle_id="p1", statement="Scarcity → conservative behaviour",
                     source_concept_ids=["c1"], ..., confidence=0.85)
    p_b = Principle(principle_id="p2", statement="Scarcity → exploration in novelty",
                     source_concept_ids=["c2"], ..., confidence=0.70)
    store.save_principle(p_a)
    store.save_principle(p_b)
    assert store.get_principle("p1") is not None
    assert store.get_principle("p2") is not None
    # No automatic merge or deletion
```

### PD-08: Orphan Rejection

```python
def test_pd08_orphan_principle_rejected():
    """Principle with empty source_concept_ids is rejected."""
    orphan = Principle(
        principle_id="orphan",
        statement="Some rule-like statement",
        source_concept_ids=[],  # empty = orphan
        ...
    )
    with pytest.raises(ContractViolation):
        store.save_principle(orphan)
```

### PD-09: Confidence ≠ Authority Gate

```python
def test_pd09_confidence_not_authority():
    """Principle.confidence is NOT available to Decision Layer components."""
    engine = PrincipleDerivationEngine()
    principles = derive_principles(make_full_input())
    for principle in principles:
        # Confidence is readable from store or engine
        assert principle.confidence >= 0.0
        # But confidence is NOT a decision weight
        assert not hasattr(principle, "decision_weight")
        assert not hasattr(principle, "priority_score")
        assert not hasattr(principle, "authority_level")
        # Engine should not expose confidence-as-authority
        assert not hasattr(engine, "get_principle_by_priority")
```

---

## Step 4 Audit Matrix

| # | Boundary | Status | Key Check |
|---|----------|--------|-----------|
| A | Principle Responsibility | **FROZEN ✅** | Principle synthesises structural insight. Does not command action. |
| B | Principle ≠ Rule | **FROZEN ✅** | Descriptive tendency, not prescriptive obligation. "Should test". |
| C | Principle ≠ Policy | **FROZEN ✅** | No "best practice", "strategy", "recommendation" language. |
| D | Principle ≠ Decision | **FROZEN ✅** | Principle does not enter Decision layer. Confidence ≠ decision weight. |
| E | Evidence Requirement | **FROZEN ✅** | Full provenance chain to Experiences. Limitations MUST be non-empty. |
| F | Applicability Boundary | **FROZEN ✅** | Scope + known non-applicable contexts. No universal claims. |
| G | Conflict Preservation | **FROZEN ✅** | Conflicting principles coexist. No merge/delete/resolve. |
| H | Provenance Chain | **FROZEN ✅** | Principle → Concept → Pattern → Experience, non-empty at every link. |
| I | Authority Isolation | **FROZEN ✅** | 10 forbidden output types. Final gate: no higher abstraction in Phase 10. |

---

## Step 4 Freeze Target

When frozen, the contract guarantees:

```
Pattern[1..M]  (Step 2)
    ↓
Concept[1..N]  (Step 3)
    ↓
Principle[1..K]  (Step 4 — this contract — last abstraction)
    ├── describes "what higher-level structural insight do these concepts suggest"
    └── does NOT describe "what rule to follow"
    └── does NOT describe "what policy to adopt"
    └── does NOT describe "what decision to make"
    └── does NOT describe "what action to take"
    └── does NOT describe "what is universally true"
    └── does NOT describe "what is best practice"
```

Principle lives as **structural understanding**, not **normative command**.

---

## Phase 10 Semantic Memory — Abstraction Stack (Final Structure)

```
Experience (Phase 4) — raw records of what happened
    │
    ▼
Pattern (Step 2)  — "what repeated structures were observed"
    │               Pattern ≠ Rule | Frequency ≠ Truth | Correlation ≠ Causation
    ▼
Concept (Step 3)  — "what shared meaning do these patterns carry"
    │               Concept ≠ Label | Abstraction ≠ Identity | Confidence ≠ Prediction
    ▼
Principle (Step 4) — "what higher-level insight emerges from these concepts"
                     Principle ≠ Rule/Policy/Decision | Evidence Is Required
                     Conflict Is Preserved | No Authority Leakage

    ╔══════════════════════════════════════════╗
    ║  PHASE 10 SEMANTIC MEMORY BOUNDARY       ║
    ║  No higher abstraction exists here.       ║
    ║  Principles enter Evaluation Layer        ║
    ║  as contextual reference — NOT authority. ║
    ╚══════════════════════════════════════════╝
```
