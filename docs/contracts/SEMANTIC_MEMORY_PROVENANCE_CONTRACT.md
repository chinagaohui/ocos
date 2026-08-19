# Phase 10 Semantic Memory — Provenance Contract v1.0

> Status: **FROZEN ✅** — Step 5 complete. Proceeding to Step 6 (Validation Tests).
>
> Step 5 is the **infrastructure layer** of Phase 10. It does not
> generate new abstractions. It ensures every existing abstraction
> can be traced, verified, and audited back to concrete experiences.
>
> The first four contracts define *how to produce abstractions safely*.
> This contract defines *how to prove where abstractions came from*.

---

## §1 — Role and Position in Phase 10

### 1.1 Identity Statement

```
Experience Layer (Phase 4) — raw event records
    │
    ├── Step 2: Pattern Extraction      → Pattern[1..M]
    ├── Step 3: Concept Formation       → Concept[1..N]
    ├── Step 4: Principle Derivation    → Principle[1..K]
    │
    └── Step 5: Provenance Layer (this contract)
        ├── ties every abstraction to its source
        ├── ensures no orphan abstraction exists
        ├── preserves immutable history of derivations
        └── provides evidence traceability from Principle → Experience
```

### 1.2 Core Declaration

> **Every abstraction must prove where it came from.**
> **Provenance is the evidence chain, not a reference or citation.**
> **An abstraction without provenance is a hallucination — not memory.**

### 1.3 What Provenance Is NOT

| NOT this | Why |
|----------|-----|
| A metadata field | Provenance IS the chain — not a tag |
| A citation system | Citations point to external sources. Provenance traces internal lineage. |
| A logging system | Logs record events. Provenance records derivation. |
| A version history | Versions track changes. Provenance tracks origin. |
| An audit trail (only) | Audit trails verify compliance. Provenance verifies existence. |

### 1.4 The Provenance Principle

> If a Principle cannot name the Concepts it synthesises,
> and if those Concepts cannot name the Patterns they aggregate,
> and if those Patterns cannot name the Experiences they observe,
> then the Principle is not Semantic Memory — it is generated belief.

**Step 5 ensures this never happens.**

---

## §2 — Chain Integrity

### 2.1 The Four-Link Chain

```
                  ┌──────────────────┐
                  │   Principle[K]   │
                  └────────┬─────────┘
                           │ source_concept_ids (non-empty)
                  ┌────────▼─────────┐
                  │   Concept[N]     │
                  └────────┬─────────┘
                           │ source_pattern_ids (non-empty)
                  ┌────────▼─────────┐
                  │   Pattern[M]     │
                  └────────┬─────────┘
                           │ source_experience_ids (non-empty)
                  ┌────────▼─────────┐
                  │ ExperienceRec[L] │
                  └────────┬─────────┘
                           │ source_event_ids (non-empty)
                  ┌────────▼─────────┐
                  │  Reality Events  │
                  └──────────────────┘
```

### 2.2 Chain Integrity Rules

| Rule | Level | Rationale |
|------|-------|-----------|
| `source_concept_ids` MUST be non-empty | Principle | Every principle must trace to at least one concept |
| `source_pattern_ids` MUST be non-empty | Concept | Every concept must trace to at least one pattern |
| `source_experience_ids` MUST be non-empty | Pattern | Every pattern must trace to at least one experience |
| `source_event_ids` MUST be non-empty | Experience | Every experience must trace to at least one reality event |
| Each link MUST resolve to an existing abstraction | All | No dangling references; all IDs must exist in their respective stores |

### 2.3 Chain Validation Function

```python
def validate_provenance_chain(principle: Principle, stores: StoreSet) -> bool:
    """Validate the full chain from Principle to ExperienceRecord.

    Returns True if every link in the chain exists and is non-empty.
    Returns False (with error detail) if any link is broken.
    """
    # Level 1: Principle → Concept
    if not principle.source_concept_ids:
        return False  # orphan principle
    for cid in principle.source_concept_ids:
        concept = stores.concepts.get(cid)
        if not concept:
            return False  # dangling concept reference
        # Level 2: Concept → Pattern
        if not concept.source_pattern_ids:
            return False  # orphan concept
        for pid in concept.source_pattern_ids:
            pattern = stores.patterns.get(pid)
            if not pattern:
                return False  # dangling pattern reference
            # Level 3: Pattern → Experience
            if not pattern.source_experience_ids:
                return False  # orphan pattern
            for eid in pattern.source_experience_ids:
                experience = stores.experiences.get(eid)
                if not experience:
                    return False  # dangling experience reference
                # Level 4: Experience → Reality Event
                if not experience.source_event_ids:
                    return False  # orphan experience
    return True
```

**Contract rule:** This validation MUST be possible for every stored
abstraction. Any abstraction that fails chain validation is a
provenance violation and MUST be quarantined.

---

## §3 — No Orphan Abstraction

### 3.1 Orphan Definition

An **orphan abstraction** is any Semantic Memory entity that:
1. Has an empty source ID list at its level, OR
2. References source IDs that no longer exist in the respective store

| Level | Orphan condition |
|-------|-----------------|
| Principle | `source_concept_ids == []` OR any referenced concept does not exist |
| Concept | `source_pattern_ids == []` OR any referenced pattern does not exist |
| Pattern | `source_experience_ids == []` OR any referenced experience does not exist |
| Experience | `source_event_ids == []` (Phase 4 contract violation) |

### 3.2 Orphan Prevention

| Mechanism | How |
|-----------|-----|
| Write-time validation | Every save operation validates source ID list is non-empty and references exist |
| Periodic audit | Scheduled check scans all stored abstractions for orphan conditions |
| Cascade protection | Deleting a source abstraction MUST check for dependent abstractions first |
| Hard rejection | System MUST reject any write that creates an orphan |

### 3.3 Orphan Handling

```python
class OrphanAbstraction(ProvenanceViolation):
    """An abstraction exists without traceable provenance."""
    def handle(self, abstraction, source_list_name: str):
        """
        1. Quarantine the abstraction (mark as "unverified")
        2. Alert provenance audit
        3. Do NOT delete automatically — human review may recover provenance
        4. Abstraction is invisible to normal queries until resolved
        """
```

**Contract rule:** Orphan detection is a runtime invariant, not a periodic
check. Every write and every source deletion MUST validate chain integrity.

---

## §4 — Immutable History

### 4.1 Core Principle

> **Provenance records are immutable.**
> **You cannot rewrite where an abstraction came from.**

Once an abstraction is created and its provenance recorded, the provenance
chain MUST be immutable. This does not mean the abstraction itself cannot
change (confidence may update, status may transition), but the **origin**
fields — `source_X_ids`, `created_at`, `formation_method` — are permanent.

### 4.2 What Is Immutable

| Field | Immutable? | Rationale |
|-------|-----------|-----------|
| `source_concept_ids` | ✅ Yes | Origin of derivation cannot be rewritten |
| `source_pattern_ids` | ✅ Yes | Origin of derivation cannot be rewritten |
| `source_experience_ids` | ✅ Yes | Origin of derivation cannot be rewritten |
| `source_event_ids` | ✅ Yes | Origin of recording cannot be rewritten |
| `created_at` | ✅ Yes | Timestamp of abstraction creation |
| `formation_method` | ✅ Yes | How the abstraction was generated |
| `generator` | ✅ Yes | Which component produced the abstraction |

| Field | Mutable? | Rationale |
|-------|----------|-----------|
| `confidence` | ✅ Yes | Confidence updates as evidence evolves |
| `status` | ✅ Yes | Active/weakened/invalidated transitions are valid |
| `limitations` | ✅ Yes (append-only) | New limitations may be discovered |
| `applicability` | ✅ Yes (append-only) | New scope conditions may be observed |
| `counter_examples` | ✅ Yes (append-only) | New counter-evidence may emerge |

### 4.3 Append-Only Policy

Mutable provenance fields follow **append-only** semantics:

```python
# ✅ Allowed — add new limitation
principle.limitations.append("Does not apply under extreme novelty conditions")

# ✅ Allowed — add new counter-example
concept.counter_examples.append({"experience_id": "E1024", "observation": "..."})

# ✅ Allowed — add new source (if evidence expands)
pattern.source_experience_ids.append("E2048")  # only if it's genuinely additive

# ❌ Forbidden — remove or rewrite existing provenance
principle.source_concept_ids.clear()  # orphan violation
concept.source_pattern_ids = ["P42"]  # rewriting history
```

### 4.4 Immutability Enforcement

```python
@dataclass(frozen=True)
class ProvenanceRecord:
    """Core provenance is immutable once written."""
    source_ids: Tuple[str, ...]   # frozen tuple, not mutable list
    created_at: datetime
    formation_method: str
    generator: str
```

**Contract rule:** Any operation that attempts to remove, replace, or
reorder existing provenance source IDs is a violation and MUST be rejected.

---

## §5 — Evidence Traceability

### 5.1 Core Principle

> **Evidence traceability means: given any abstraction, you can list
> every concrete experience that contributed to its formation.**
>
> Traceability is a read-only query, not a storage mechanism.

### 5.2 Traceability Queries

```python
# Given a Principle, list all supporting ExperienceRecords
def get_supporting_experiences(principle_id: str) -> List[ExperienceRecord]:
    """Traverse the chain: Principle → Concepts → Patterns → Experiences."""
    principle = store.get_principle(principle_id)
    experience_ids = set()
    for cid in principle.source_concept_ids:
        concept = store.get_concept(cid)
        for pid in concept.source_pattern_ids:
            pattern = store.get_pattern(pid)
            experience_ids.update(pattern.source_experience_ids)
    return [store.get_experience(eid) for eid in experience_ids]


# Given an ExperienceRecord, list all abstractions derived from it
def get_derived_abstractions(experience_id: str) -> Dict[str, List[str]]:
    """Reverse traversal: Experience → Patterns → Concepts → Principles."""
    result = {
        "patterns": [],
        "concepts": [],
        "principles": [],
    }
    # Find patterns that cite this experience
    for pattern in store.patterns.values():
        if experience_id in pattern.source_experience_ids:
            result["patterns"].append(pattern.pattern_id)
            # Find concepts that cite these patterns
            for concept in store.concepts.values():
                if pattern.pattern_id in concept.source_pattern_ids:
                    result["concepts"].append(concept.concept_id)
                    # Find principles that cite these concepts
                    for principle in store.principles.values():
                        if concept.concept_id in principle.source_concept_ids:
                            result["principles"].append(principle.principle_id)
    return result
```

### 5.3 Traceability Guarantees

| Guarantee | Enforcement |
|-----------|-------------|
| Every abstraction has ≥1 supporting experience | Chain validation (§2) |
| Forward trace: abstraction → experiences | `get_supporting_experiences()` |
| Reverse trace: experience → abstractions | `get_derived_abstractions()` |
| No unbroken links in either direction | Chain integrity rules |
| Traceability is always available offline | Provenance is stored, not computed |

### 5.4 The Traceability Test

**Contract rule:** For ANY stored abstraction, a consumer MUST be able
to list at least one concrete ExperienceRecord that contributed to its
formation, without accessing any external system or component.

```
Principle "resource-scarcity tendency"
    → Concept "scarcity-induced conservatism"
        → Pattern "scarcity→delay correlation (8/10 cases)"
            → Experience "Project Alpha: budget cut → delayed timeline"
```

If this trace fails at any point, the abstraction fails provenance audit.

---

## §6 — Conflict Trace Preservation

### 6.1 Core Principle

> **Provenance preserves not just supporting evidence,**
> **but also conflicting evidence.**
>
> Counter-examples are traceable through the same chain mechanism.

### 6.2 Counter-Example Provenance

Every abstraction carries `counter_examples`, and those counter-examples
MUST be traceable to concrete experiences:

```python
@dataclass
class CounterExample:
    """A counter-example to a concept or principle."""
    experience_id: str              # which experience contradicts this
    pattern_id: Optional[str]       # which pattern (if pattern-level)
    observation: str                # what was observed
    recorded_at: datetime
    severity: str                   # "contradicts" | "weakens" | "limits_scope"
```

### 6.3 Counter-Example Chain

```
Abstraction (Concept or Principle)
    ├── supporting_patterns → traceable to Experiences (positive evidence)
    └── counter_examples → traceable to Experiences (negative evidence)

Both chains MUST satisfy the same provenance integrity rules:
    - counter_experience_id MUST resolve to an existing ExperienceRecord
    - counter_pattern_id (if present) MUST resolve to an existing Pattern
    - Empty counter_examples list is valid (absence of counter-evidence ≠ proof)
```

### 6.4 Conflict Visibility

**Contract rule:** A query for "evidence supporting abstraction X" MUST
also surface the count of known counter-examples. Hiding conflict from
consumers is a provenance violation.

```python
def get_evidence_summary(abstraction) -> dict:
    return {
        "supporting_experiences": count,  # always shown
        "counter_examples": count,        # always shown — never hidden
        "confidence": abstraction.confidence,
        "limitations": abstraction.limitations,
    }
```

---

## §7 — Version Evolution

### 7.1 Core Principle

> **Abstractions evolve. Provenance records the evolution.**
> **Each version of a provenance record preserves the previous state.**

### 7.2 Evolution Record

```python
@dataclass
class ProvenanceEvolution:
    """Records how an abstraction's provenance changed over time."""
    abstraction_id: str
    abstraction_type: str                  # "principle" | "concept" | "pattern"
    version_history: List[ProvenanceSnapshot]
    # version_history[0] = creation snapshot (immutable origin)
    # version_history[1..N] = subsequent updates (append-only)


@dataclass
class ProvenanceSnapshot:
    """A point-in-time record of an abstraction's provenance."""
    version: int
    timestamp: datetime
    source_ids: FrozenSet[str]             # stable view at this version
    confidence: float
    status: str
    limitations: List[str]                 # frozen view at this version
    counter_examples: List[CounterExample] # frozen view at this version
    change_reason: str                     # why this change was made
```

### 7.3 Evolution Rules

| Rule | Rationale |
|------|-----------|
| Every change to provenance fields creates a new snapshot | History is preserved |
| Source IDs are immutable after creation | Origin cannot be rewritten (see §4) |
| Limitations and counter-examples are append-only | No removal of known limitations |
| Confidence may increase or decrease | Evidence evolution is bidirectional |
| Status transitions are recorded with reason | "weakened" and "invalidated" must be explainable |

### 7.4 Evolution Boundaries

| ✅ Allowed | ❌ Forbidden |
|-----------|-------------|
| Append new limitation | Remove existing limitation |
| Add new counter-example | Remove existing counter-example |
| Update confidence (up or down) | Change source IDs after creation |
| Transition status (active → weakened → invalidated) | Restore from invalidated to active without new evidence |
| Record a new provenance snapshot with reason | Rewrite or delete a historical snapshot |

---

## §8 — Deletion Boundary

### 8.1 Core Principle

> **Deletion in Semantic Memory is not erasure.**
> **Provenance survives the abstraction it references.**

### 8.2 Abstraction Deletion Rules

| Rule | Rationale |
|------|-----------|
| Deleting an abstraction does NOT delete its provenance record | Future audit must still be possible |
| Deleting an abstraction MUST check downstream dependents | Preventing dangling references |
| Dependent abstractions MUST be quarantined, not auto-deleted | No cascade deletion of memory |
| Provenance records are permanent | Once recorded, never destroyed |

### 8.3 Deletion Lifecycle

```
Request to delete abstraction X
    │
    ├── 1. Check downstream dependents
    │       - Patterns that reference X's experiences
    │       - Concepts that reference X's patterns
    │       - Principles that reference X's concepts
    │
    ├── 2. If dependents exist:
    │       - Mark X as "deleted" (not erased)
    │       - Quarantine dependents (status = "provenance_orphaned")
    │       - Log deletion to provenance audit
    │       - Do NOT cascade delete
    │
    └── 3. If no dependents:
            - Mark X as "deleted"
            - Preserve provenance record
            - Abstraction data MAY be archived after retention period
```

### 8.4 Permanent Provenance Record

Even after an abstraction is deleted, its provenance record MUST
survive in an append-only provenance store:

```python
@dataclass
class DeletedAbstractionProvenance:
    """Provenance record that survives abstraction deletion."""
    abstraction_id: str
    abstraction_type: str
    created_at: datetime
    deleted_at: datetime
    source_ids: Tuple[str, ...]          # preserved from creation
    reason_for_deletion: str
    deletion_approved_by: str
    downstream_orphans: List[str]        # abstractions quarantined by this deletion
```

**Contract rule:** No operation in Semantic Memory permanently destroys
provenance information. Deletion is a status transition, not data erasure.

---

## §9 — Authority Isolation

### 9.1 Core Principle

> **Provenance is evidence. It is not authority.**
> **Tracing an abstraction to many experiences does not make it correct.**
> **Tracing an abstraction to many experiences does not make it binding.**

### 9.2 What Provenance IS and IS NOT

| Provenance IS | Provenance IS NOT |
|--------------|-------------------|
| Evidence chain | Truth validation |
| Derivation history | Correctness guarantee |
| Recording of source | Authority to act |
| Audit mechanism | Decision input |
| Transparency tool | Weight of evidence in decision |

### 9.3 Prohibited Provenance Uses

| ❌ Forbidden use | Why |
|-----------------|-----|
| "This principle has provenance to 1000 experiences → it must be correct" | Evidence volume ≠ truth |
| "This concept traces to more patterns → it should outrank conflicting concepts" | Provenance depth ≠ priority |
| "This pattern has strong provenance → decision must follow it" | Provenance is not decision authority |
| "No counter-examples in provenance → this principle is universally valid" | Absence of counter-evidence ≠ proof |

### 9.4 The Provenance Authority Guard

```python
# ❌ Forbidden — provenance as authority
def decide_by_provenance_depth(context: dict) -> Decision:
    """Select the abstraction with deepest provenance as the authoritative one."""
    # VIOLATION: provenance depth does not confer decision authority

# ✅ Allowed — provenance as context
def get_evidence_context(scope: dict) -> EvidenceContext:
    """Return abstractions with their provenance chains for evaluation."""
    # OK: provenance is provided as contextual reference, not as authority
```

### 9.5 Provenance Store Boundaries

The Provenance Store (the system that maintains these chains) MUST NOT:

- Expose a "provenance weight" or "evidence score" for decision input
- Rank abstractions by provenance depth for automatic selection
- Surface provenance data to Decision Layer components with authority labels
- Allow deletion of provenance records (permanent store)

---

## §10 — Validation (PV-01 – PV-08)

### PV-01: Full Chain Validation

```python
def test_pv01_full_chain_validation():
    """Every abstraction passes full provenance chain validation."""
    abstractions = [
        *store.principles.values(),
        *store.concepts.values(),
        *store.patterns.values(),
    ]
    for abstraction in abstractions:
        assert validate_provenance_chain(abstraction, stores)
```

### PV-02: Orphan Detection

```python
def test_pv02_orphan_detection():
    """Abstraction with empty source IDs is rejected on write."""
    orphan_principle = Principle(
        principle_id="orphan",
        statement="An unsupported claim",
        source_concept_ids=[],  # empty = orphan
        ...
    )
    with pytest.raises(OrphanAbstraction):
        store.save_principle(orphan_principle)
```

### PV-03: Immutability of Source IDs

```python
def test_pv03_source_ids_immutable():
    """Source IDs cannot be rewritten after creation."""
    pattern = create_and_save_pattern()
    original_sources = pattern.source_experience_ids.copy()
    # Attempt to clear
    with pytest.raises(ProvenanceViolation):
        pattern.source_experience_ids.clear()
    # Attempt to reassign
    with pytest.raises(ProvenanceViolation):
        pattern.source_experience_ids = []
    # Verify unchanged
    assert pattern.source_experience_ids == original_sources
```

### PV-04: Evidence Traceability Forward

```python
def test_pv04_forward_trace():
    """Given a Principle, list supporting experiences."""
    principle = store.get_principle("p_scarcity")
    experiences = get_supporting_experiences(principle.principle_id)
    assert len(experiences) > 0
    # Every experience must have source_event_ids
    for exp in experiences:
        assert len(exp.source_event_ids) > 0
```

### PV-05: Evidence Traceability Reverse

```python
def test_pv05_reverse_trace():
    """Given an Experience, find derived abstractions."""
    experience = store.get_experience("E100")
    derived = get_derived_abstractions(experience.experience_id)
    # At least one path should exist
    total = len(derived["patterns"]) + len(derived["concepts"]) + len(derived["principles"])
    assert total > 0
```

### PV-06: Counter-Example Traceability

```python
def test_pv06_counter_example_trace():
    """Counter-examples are traceable to concrete experiences."""
    for concept in store.concepts.values():
        for ce in concept.counter_examples:
            exp = store.get_experience(ce.experience_id)
            assert exp is not None, f"Counter-example references non-existent experience: {ce.experience_id}"
```

### PV-07: Deletion Preserves Provenance

```python
def test_pv07_deletion_preserves_provenance():
    """Deleting an abstraction preserves its provenance record."""
    concept = create_and_save_concept()
    provenance_before = get_provenance_record(concept.concept_id)
    store.delete_concept(concept.concept_id)
    # Provenance still exists
    provenance_after = get_provenance_record(concept.concept_id)
    assert provenance_after is not None
    assert provenance_after.source_ids == provenance_before.source_ids
```

### PV-08: Provenance ≠ Authority

```python
def test_pv08_provenance_not_authority():
    """Provenance store does not expose authority interfaces."""
    store = ProvenanceStore()
    # Allowed interfaces
    assert hasattr(store, "validate_chain")
    assert hasattr(store, "get_evidence_context")
    # Forbidden interfaces
    assert not hasattr(store, "rank_by_provenance_depth")
    assert not hasattr(store, "get_evidence_weight")
    assert not hasattr(store, "select_authoritative")
    assert not hasattr(store, "get_decision_ready")
```

---

## Step 5 Audit Matrix

| # | Boundary | Status | Key Check |
|---|----------|--------|-----------|
| A | Chain Integrity | **FROZEN ✅** | Principle → Concept → Pattern → Experience, every link non-empty and resolvable. |
| B | No Orphan Abstraction | **FROZEN ✅** | Write-time validation + periodic audit. Orphans quarantined, not auto-deleted. |
| C | Immutable History | **FROZEN ✅** | Source IDs and creation metadata are frozen after write. Append-only for limitations/counter-examples. |
| D | Evidence Traceability | **FROZEN ✅** | Forward (abstraction → experiences) and reverse (experience → abstractions) queries supported. |
| E | Conflict Trace Preservation | **FROZEN ✅** | Counter-examples have same traceability as supporting evidence. Conflict count always visible. |
| F | Version Evolution | **FROZEN ✅** | Every provenance change creates a new snapshot. Source IDs immutable; limitations append-only. |
| G | Deletion Boundary | **FROZEN ✅** | Deletion is status transition, not erasure. Provenance record survives. No cascade delete. |
| H | Authority Isolation | **FROZEN ✅** | Provenance is evidence, not authority. No ranking/weight/decision interfaces. |

---

## Step 5 Freeze Target

When frozen, the contract guarantees:

```
Every abstraction has a traceable chain to concrete experience.
No orphan abstraction exists in Semantic Memory.
Provenance history is permanent — deletion preserves evidence.
Counter-examples are as traceable as supporting evidence.
Provenance informs understanding but does not confer authority.
```

Provenance lives as **evidence infrastructure**, not **authority framework**.
