# Phase14.4.5 — Principle Registry Contract

**Status**: ❄️ FROZEN (2026-07-22)
**Phase**: Phase14.4 Meta Principle Formation
**Domain**: Cognitive — Knowledge Base
**Previous**: §14.4.4 Principle Validation ✅
**Next**: §14.4.6 Freeze Audit

---

## §5.0 Positioning

### 5.0.1 What this is

Principle Registry is a **Knowledge Base** — not a Capability Library.

It stores verified abstract mechanisms (Principles) as knowledge facts.
It does NOT organize, rank, recommend, or package these facts.

### 5.0.2 Single Source of Truth

Registry is the **single source of truth** for Principles.

```
Inference → Validation → Registry ← 唯一正式来源 ← Phase14.5
```

Phase14.5 MUST read from Registry, NOT from Validation output directly.
This ensures versioning, invalidation, and archiving are consistently visible.

### 5.0.3 Core discipline (frozen in ABI)

> **Registry 不负责知识组织。 Registry 只保存知识事实。**
>
> Knowledge Organization 属于 Phase14.5 Capability Package。

This boundary prevents Registry from evolving into:
- Classification system
- Recommendation engine
- Similarity matcher
- Best-practice database
- "Universal knowledge center"

### 5.0.4 Position in OCOS pipeline

```
Reality
  ↓
Evidence
  ↓
Relation
  ↓
Pattern
  ↓
Pattern Registry (Observation KB — Phase14.3)
  ↓
Principle
  ↓
Principle Registry (Cognitive KB — Phase14.4.5) ← HERE
  ↓
Capability Package (Knowledge Organization — Phase14.5)
  ↓
Control Plane (Safe Invocation — Phase15)
```

### 5.0.5 Input/Output/Forbidden

| Channel | What |
|---|---|
| Input | ValidatedPrinciple (§14.4.4) |
| Output | PrincipleRecord (via Query) |
| Forbidden | Capability, Prompt Template, Agent Strategy, Writing Rule |

---

## §5.1 PrincipleRecord ABI

### 5.1.1 PrincipleRecord

```python
@dataclass
class PrincipleRecord:
    principle_id: str                       # pr-*
    derived_from_candidate: str            # pc-*
    abstraction_level: AbstractionLevel
    description: str                       # structural description only, no value judgment

    # Trace chain (consolidated root reference — trace API entry point)
    trace_root: TraceRoot

    # Validation provenance
    validation_record_ids: List[str]       # vr-*, from §14.4.4
    source_inference_records: List[str]    # ir-*, from §14.4.3

    # Knowledge graph edges
    dependency_refs: List[PrincipleDependency]

    # Versioning
    version: str                           # semantic version, e.g. "1.0.0"
    registry_revision: int                 # Registry's own modification counter
    status: LifecycleStatus
    created_at: datetime
    superseded_by: Optional[str]           # pr-* when status=superseded
    history_summary: Optional[List[VersionEntry]]
```

### 5.1.2 TraceRoot

```python
@dataclass
class TraceRoot:
    """Consolidated root references for full Reality traceability."""
    pattern_ids: List[str]       # pat-* from Phase14.3
    evidence_ids: List[str]      # ev-* or e-* from Phase14.3
    relation_ids: List[str]      # rel-* from Phase14.3
```

No separate join across 3 objects needed — trace API entry point is self-contained.

### 5.1.3 PrincipleDependency

```python
@dataclass
class PrincipleDependency:
    target_principle_id: str    # pr-*, MUST reference existing PrincipleRecord
    relation: str               # one of: generalizes | supports | contradicts | refines | depends_on | derives_from
    description: str            # structural description only, no value judgment
```

#### Allowed relations (6)

| Relation | Semantics | Example |
|---|---|---|
| `generalizes` | This Principle is a broader abstraction of target | P17 generalizes P09 |
| `supports` | This Principle's evidence reinforces target | P03 supports P22 |
| `contradicts` | Evidence points opposite direction from target | P22 contradicts P09 |
| `refines` | This Principle narrows/applies target in specific context | P11 refines P07 |
| `depends_on` | This Principle requires target as premise | P15 depends_on P04 |
| `derives_from` | This Principle evolved from target | P08 derives_from P12 |

#### Forbidden in dependency_refs

- `is_better_than` — comparison/value judgment
- `is_more_effective` — effectiveness evaluation (Phase15 domain)
- `is_recommended_over` — recommendation (Phase14.5 domain)
- `outperforms` — performance comparison
- `supersedes` — this is a lifecycle action, NOT a knowledge relation

#### Constraint: references only, no reasoning

```python
# ❌ FORBIDDEN — no reasoning payload in dependency_refs
dependency_refs[0].reasoning = "Because this principle demonstrates..."
dependency_refs[0].proof = "..."
dependency_refs[0].analysis = "..."
dependency_refs[0].llm_explanation = "..."

# ✅ ALLOWED — reference only
dependency_refs[0] = PrincipleDependency(
    target_principle_id="pr-017",
    relation="generalizes",
    description="P22 captures the same mechanism at L3 abstraction"
)
```

Reasoning belongs to **Inference → Validation** phases, NOT Registry.

#### Constraint: target must reference existing PrincipleRecord

```
target_principle_id MUST resolve to a registered PrincipleRecord.
PrincipleCandidate  ✗  →  ValidatedPrinciple  ✗  →  PrincipleRecord  ✓
```

### 5.1.4 LifecycleStatus

```python
class LifecycleStatus(str, Enum):
    REGISTERED = "registered"
    SUPERSEDED = "superseded"
    ARCHIVED = "archived"
    INVALIDATED = "invalidated"
```

### 5.1.5 VersionEntry

```python
@dataclass
class VersionEntry:
    version: str
    status: str
    timestamp: datetime
    reason: str              # structural description of what changed
```

### 5.1.6 Forbidden fields in PrincipleRecord

Same discipline as Phase14.3 Registry:

| Field | Reason |
|---|---|
| quality_score | Quality evaluation is not a knowledge fact |
| effectiveness | Effectiveness belongs to Control Domain |
| success_rate | Success rate belongs to Phase15 |
| recommendation | Recommendation belongs to Phase14.5 |
| priority | Priority ranking is not storage layer |
| ranking | Ranking is not storage layer |
| confidence | Confidence (non-statistical) belongs to Inference phase |
| usefulness | Usefulness judgment is not Registry concern |
| best_for | Applicability recommendation is Phase14.5 |
| should_apply | Application decision is Phase15 |
| popularity | Popularity is ReaderOS domain |
| reader_approval | Reader opinion is not Cognitive KB fact |

---

## §5.2 Lifecycle

### 5.2.1 State machine

```
                  ┌─────────────────┐
                  │   REGISTERED    │
                  └────────┬────────┘
                           │
                  ┌────────┴────────┐
                  │                 │
           new version        contradictory
          provides better       evidence
          abstraction          invalidates
                  │                 │
                  ▼                 ▼
          ┌─────────────┐  ┌──────────────┐
          │ SUPERSEDED  │  │ INVALIDATED  │
          └─────────────┘  └──────────────┘
                  │
            knowledge no
            longer active
                  │
                  ▼
          ┌─────────────┐
          │  ARCHIVED   │
          └─────────────┘
```

### 5.2.2 Allowed transitions

| From | To | Condition |
|---|---|---|
| REGISTERED | SUPERSEDED | New version published; superseded_by populated |
| REGISTERED | INVALIDATED | Irresolvable contradictory evidence confirmed |
| REGISTERED | ARCHIVED | Principle no longer relevant (non-invalid) |
| SUPERSEDED | ARCHIVED | Superseded version retired from active history |
| INVALIDATED | ARCHIVED | Invalidated entry moved to cold storage |

### 5.2.3 Forbidden transitions

| From | To | Reason |
|---|---|---|
| SUPERSEDED | INVALIDATED | Historical version keeps its record; invalidate the CURRENT version instead |
| ARCHIVED | REGISTERED | Archived is terminal — create new version if revived |
| INVALIDATED | REGISTERED | Invalidated is terminal — create new version with corrected evidence |
| ARCHIVED | SUPERSEDED | Archived is terminal |

### 5.2.4 Transition constraints

- `SUPERSEDED → INVALIDATED` is FORBIDDEN — the current version carries the fault, not the history
- When REGISTERED → SUPERSEDED, `superseded_by` MUST be populated with the new `pr-*` ID
- Each transition records a `VersionEntry` in `history_summary`

---

## §5.3 Query Contract

### 5.3.1 Returns Reference, not Record

Query MUST return **PrincipleReference**, not full PrincipleRecord.

```python
@dataclass
class PrincipleReference:
    principle_id: str
    version: str
    status: LifecycleStatus
    abstraction_level: AbstractionLevel
    trace_root_summary: Dict       # compact: count of patterns/evidences/relations
    dependency_summary: List[str]  # target principle_ids only (no full dependency objects)
```

**Phase14.5 access pattern**:
```
Reference → Resolver → Principle (full Record)
```

This enables:
- Caching (Reference is lightweight)
- Lazy resolution (only resolve when needed)
- Version pinning (Reference pins a specific version)
- Permission checks (resolve gated by authorization)

### 5.3.2 Query dimensions

| Dimension | Type | Semantics |
|---|---|---|
| principle_id | str | Exact ID match |
| validated_pattern_ids | List[str] | Trace to source patterns |
| abstraction_level | AbstractionLevel | L1/L2/L3 filter |
| version_constraint | str | Exact, range, or "latest" |
| status_filter | List[LifecycleStatus] | One or more statuses |
| validation_record_ids | List[str] | Trace to validation records |
| dependency_target | str | Find everything that depends on / is depended by pr-* |
| trace_root.pattern_ids | List[str] | Find principles derived from specific patterns |
| created_after | datetime | Temporal filter |
| tags | List[str] | Extended tags (structural only, no semantics) |

Multifilter uses AND semantics.

### 5.3.3 Pagination

```python
@dataclass
class QueryPage:
    offset: int = 0
    limit: int = 50              # max 100
    return_total: bool = False
```

### 5.3.4 Forbidden query operations

| Operation | Reason |
|---|---|
| sort_by_quality | Quality is not a Registry dimension |
| rank_principles | Ranking exceeds Knowledge Base |
| select_optimal | "Optimal" selection is Control Domain |
| recommend_top | Recommendation is Phase14.5 |
| find_similar | Similarity matching involves Cognitive judgment |
| cluster_principles | Clustering is Knowledge Organization (Phase14.5) |
| summarize_principles | Summarization exceeds storage layer |
| explain_principle | Explanation belongs to Inference phase |
| predict_applicability | Applicability prediction is Phase15 |
| suggest_combination | Combination suggestion is Capability Package |

### 5.3.5 Determinism

```
∀ query, registry_snapshot:
    run(query, registry_snapshot, tc1) = run(query, registry_snapshot, tc2)
```

Same Registry snapshot + same query = same result.

### 5.3.6 Error handling

| Scenario | Behavior |
|---|---|
| Invalid principle_id | Empty result, not error |
| Invalid status_filter | Ignore filter, continue |
| Pagination exceeded | Cap to max (100) |
| Empty Registry | Empty list |
| Timeout | Partial result + truncation marker |

---

## §5.4 Freeze Audit

### 5.4.1 Audit Check 1 — Domain Isolation

**Check**: PrincipleRecord has no Capability-level fields.

**Pass condition**: No field named:
- `capability_package`, `writing_rule`, `prompt_template`, `agent_instruction`
- `strategy_document`, `best_practice_guide`, `usage_advice`
- `effectiveness_score`, `quality_score`, `success_rate`
- `recommendation`, `priority`, `ranking`, `popularity`

### 5.4.2 Audit Check 2 — Trace Chain

**Check**: Every PrincipleRecord can trace 100% to Evidence.

**Trace path**: `principle_id → trace_root.pattern_ids → evidence_ids`

**Pass condition**: All IDs in trace_root MUST resolve.
No link in the chain is empty.

### 5.4.3 Audit Check 3 — Phase14→14.5 Isolation

**Check**: Registry output is PrincipleReference, not Capability Package.

**Pass condition**: Query returns PrincipleReference.
PrincipleRecord is never exposed directly to Phase14.5.
Phase14.5 reads from Registry, not from Validation.

### 5.4.4 Audit Check 4 — Knowledge Graph Integrity

**Check 4a — No circular dependencies**
```
For any pr-X: trace dependency graph → no path from pr-X back to pr-X.
```

**Check 4b — No orphaned Principles**
```
Every PrincipleRecord has at least one pattern in trace_root.
No PrincipleRecord exists without traceable evidence.
```

**Check 4c — No dead references**
```
Every dependency_refs.target_principle_id resolves to an existing PrincipleRecord.
```

**Check 4d — Dangling Reference** (new)
```
For every dependency_refs.target_principle_id:
    registry.lookup(target_principle_id) MUST return a non-empty result.
    If target does not exist → AUDIT FAILURE.
```

**Check 4e — Cross-version reference integrity**
```
If pr-X v1.0.0 depends_on pr-Y v2.0.0:
    pr-Y v2.0.0 MUST exist and be REGISTERED at the time of reference.
    If pr-Y was INVALIDATED or ARCHIVED → AUDIT WARNING.
```

---

## §6 Phase14.5 Interface Contract

### 6.1 Input to Phase14.5

Phase14.5 receives:
```
PrincipleReference[]
  ↓
Resolver
  ↓
PrincipleRecord[]
  ↓
Capability Package Construction
```

### 6.2 Isolation rules

- Phase14.5 MUST import from Registry (SSOT)
- Phase14.5 MUST NOT import from Validation output
- Phase14.5 NEVER receives `PrincipleCandidate`, `ValidatedPrinciple`, `DimensionResult`
- Registry NEVER outputs `CapabilityPackage`, `WritingRule`, `AgentStrategy`

### 6.3 Phase14.5 does NOT write to Registry

Registry is read-only from Phase14.5's perspective.
Capability Package is a NEW layer built on top.
