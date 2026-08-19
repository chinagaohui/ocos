# Runtime Ownership Matrix

> **Phase**: Phase15.5.0 — Frozen Pre-requisite for Phase15.5
> **Status**: ❄️ FROZEN (§15.5.5 Recovery Protocol included 2026-07-23)
> **Version**: 1.0.0
> **Freeze Date**: 2026-07-23

---

## 1. Runtime Layering

```
OCOS Control Plane
│
├── ExecutionPlan
│     (Director output — frozen immutable plan)
│
├── Runtime Orchestrator
│     (Scheduler — lifecycle management, no business logic)
│
├── Adapter
│     (Invocation bridge — OCOS → OpenTale)
│
├── ConstraintBundle Contract
│     (Interface contract — OCOS owns the contract)
│
├── ─ ─ ─ ─ ─ ─ ─ ─  OCOS / OpenTale Boundary ─ ─ ─ ─ ─ ─ ─ ─
│
├── ConstraintBundle Implementation
│     (Concrete structure — OpenTale owns the implementation)
│
└── OpenTale Runtime
      (Execution engine — system boundary, opaque to OCOS)
```

### Layer Boundary Rules

| Boundary | Rule |
|----------|------|
| OCOS → OpenTale | Only through Adapter → ConstraintBundle Contract |
| OpenTale → OCOS | Never. OpenTale does not import OCOS. |
| Adapter → ConstraintBundle | Must depend on interface contract, never concrete implementation |
| Orchestrator → ExecutionPlan | Read-only consumption. Orchestrator never modifies the plan. |

### Rule: ExecutionPlan is an Immutable Value Object

**ExecutionPlan is received by value, never by reference.**

- Runtime receives a deep copy or immutable snapshot at handoff
- Runtime must NOT modify, augment, or annotate the ExecutionPlan
- Any modification attempt is a contract violation detectable by Quality Gate
- ExecutionPlan identity is defined by its content, not by object reference

Rationale: Preventing the class of bugs where Runtime "accidentally" mutates the plan during scheduling, adapter dispatch, or recovery — corrupting audit trails and breaking Quality Gate re-validation.

---

### Rule: RuntimeInstance Identity

Every Runtime session carries its own identity — **RuntimeInstance**.

```python
@dataclass(frozen=True)
class RuntimeInstance:
    runtime_instance_id: str   # Unique per session
    runtime_version: str       # OCOS Runtime Contract version
    boot_time: float           # Unix timestamp of session start
    contract_version: str      # Adapter/ConstraintBundle contract version pinned at boot
```

**RuntimeInstance is identity, not state.**

- It is created once per Runtime session and never mutated
- It is attached to every ExecutionTicket, Adapter session, and Recovery log for traceability
- It enables multi-Runtime deployment (local, cloud, distributed) without shared mutable identity
- It is NOT narrative state — it carries no character, world, or story data

Rationale: Without explicit Runtime identity, multi-executor, distributed, or agent-based Runtime deployments cannot distinguish which instance produced which ticket, log, or recovery record.

---

## 2. Ownership Matrix

Which modules may perform which actions on which artifacts.

### Legend

| Symbol | Meaning |
|--------|---------|
| ✅ | Allowed |
| ❌ | Forbidden (must never) |
| — | Not applicable (artifact does not exist in this scope) |

### Creation Ownership

| Module \ Artifact | ExecutionPlan | ExecutionTicket | Queue | Adapter Session | ConstraintBundle | Recovery State |
|---|---|---|---|---|---|---|
| **OCOS** (Director) | ✅ Create | — | — | — | — | — |
| **Runtime Orchestrator** | ❌ | ✅ Create | ✅ Create | — | — | ❌ (via Recovery) |
| **Adapter** | ❌ | ❌ | ❌ | ✅ Create | ✅ Build (via contract) | ❌ |
| **ConstraintBundle** | ❌ | ❌ | ❌ | ❌ | ✅ (impl only) | ❌ |
| **OpenTale Runtime** | ❌ | ❌ | ❌ | ❌ | — | — |
| **Quality Gate** | ❌ | — | — | — | — | — |
| **Registry** | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |

### Modification Ownership

| Module \ Artifact | ExecutionPlan | ExecutionTicket | Queue | Adapter Session | ConstraintBundle | Recovery State |
|---|---|---|---|---|---|---|
| **OCOS** (Director) | ❌ (immutable after handoff) | — | — | — | — | — |
| **Runtime Orchestrator** | ❌ | ✅ (state transitions) | ✅ (enqueue/dequeue) | — | — | ✅ |
| **Adapter** | ❌ | ❌ | ❌ | ✅ (session state) | ❌ | ❌ |
| **ConstraintBundle** | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **OpenTale Runtime** | ❌ | ❌ | ❌ | ❌ | ❌ | — |
| **Quality Gate** | ❌ | ❌ | — | — | — | — |
| **Registry** | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |

### Deletion Ownership

| Module \ Artifact | ExecutionPlan | ExecutionTicket | Queue | Adapter Session | ConstraintBundle | Recovery State |
|---|---|---|---|---|---|---|
| **OCOS** (Director) | ❌ | — | — | — | — | — |
| **Runtime Orchestrator** | ❌ | ✅ (on completion) | ✅ (on completion) | — | — | ✅ (on completion) |
| **Adapter** | ❌ | ❌ | ❌ | ✅ (on completion/failure) | ❌ | ❌ |
| **ConstraintBundle** | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **OpenTale Runtime** | ❌ | ❌ | ❌ | ❌ | — | — |
| **Registry** | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |

### Retry / Rollback / Abort Ownership

| Operation | Owner | Constraint |
|-----------|-------|------------|
| **Retry** | Runtime Orchestrator | Max retry count bounded per Adapter configuration |
| **Rollback** | Runtime Orchestrator | Only within a single ExecutionTicket lifetime |
| **Abort** | Runtime Orchestrator | Final state — ticket enters `ABORTED`, no further transitions |
| **Resume** | Runtime Orchestrator | Only from `SUSPENDED` state |
| **Timeout** | Runtime Orchestrator | Hard limit per invocation, configurable at Orchestra level |

---

## 3. Allowed Operations Matrix

The operations each module may perform on canonical data types.

| Operation | ExecutionPlan | Signal | Registry | Principle | Pattern | Adapter Session | Ticket |
|---|---|---|---|---|---|---|---|
| **Read** | Runtime, Quality Gate, Adapter | Director, Quality Gate | Signal→Director Mapping only | Director only | Pattern Discovery only | Adapter only | Runtime only |
| **Create** | Director only | Director only | Registry only | Principle only | Pattern only | Adapter only | Runtime only |
| **Update** | ❌ None | ❌ None | ❌ None (append-only) | ❌ None (frozen) | ❌ None (frozen) | ✅ Adapter only | ✅ Runtime only (state only) |
| **Delete** | ❌ None | ❌ None | ❌ None | ❌ None | ❌ None | Adapter only | Runtime only (on completion) |
| **Validate** | Quality Gate | Quality Gate | ❌ | ❌ | ❌ | ❌ | ❌ |

### Adapter Invocation Operations (§15.5.3)

| Operation | AdapterRegistration | AdapterRegistry | AdapterInvocationRecord | AdapterInvoker | InvocationAudit |
|-----------|-------------------|-----------------|------------------------|----------------|-----------------|
| **Read** | ✅ | ✅ | ✅ | ✅ (registry only) | ✅ |
| **Create** | Registry only | Registry only | Invoker only | ❌ (stateless) | Audit factory only |
| **Update** | ❌ (frozen) | ✅ (register/replace) | ❌ (immutable, complete returns new) | ❌ | ❌ (frozen) |
| **Delete** | Registry only (clear) | Registry only (clear) | ❌ | ❌ | ❌ |

---

## 11. Adapter Invocation Contract (§15.5.3)

### Contract Purpose

```
┌─────────────────────────────────────────────────────────────────┐
│  OCOS Runtime Orchestrator                                       │
│                                                                   │
│  ├── Scheduler            (§15.5.2)  — dispatch control           │
│  ├── AdapterInvoker       (§15.5.3)  — route + invoke adapter     │
│  │     ├── AdapterRegistry            — SSOT: domain → adapter    │
│  │     └── AdapterInvocationRecord    — invocation lifecycle      │
│  ├── Recovery Manager     (§15.5.5)  — retry/abort/resume        │
│  └── Validation           (§15.5.4)  — structural validation     │
│                                                                   │
│  Adapter Protocol Interface (in runtime_contract.py):              │
│    adapter.invoke(allocation, ticket_id, runtime_instance_id)      │
│      → AdapterResult(status, adapter_session_id, ...)              │
│                                                                   │
│  ─ ─ ─  Adapter Layer ─ ─ ─                                      │
│  OpenTale-side adapter implements AdapterProtocol                 │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

### Types

#### AdapterRegistration (Immutable Value Object)

```python
@dataclass(frozen=True)
class AdapterRegistration:
    domain: ControlDomain         # Which control domain this adapter handles
    adapter: AdapterProtocol      # The protocol-compliant adapter instance
    name: str                     # Human-readable name (for events/logs only)
    registered_at: datetime       # When this registration was established
```

- Created via `AdapterRegistration.create(domain, adapter, name=None)`
- If `name` is omitted, defaults to `domain.value`
- Fully frozen — no field may be mutated after creation
- Used solely for registry storage; never passed across system boundary

#### AdapterRegistry (SSOT)

```python
class AdapterRegistry:
    # Single Source of Truth: ControlDomain → AdapterRegistration
    def register(self, domain, adapter, name=None) -> None
    def resolve(self, domain) -> AdapterRegistration | None
    def resolve_or_raise(self, domain) -> AdapterRegistration
    def clear(self) -> None
```

- One-to-one mapping: each ControlDomain has exactly one adapter
- Re-registration replaces the existing binding
- `resolve_or_raise` raises `KeyError` when missing (invoker uses this)
- Registry does NOT know about OpenTale — stores protocol-bound mappings only
- Thread-safe by convention (no shared mutable state across registrations)

#### AdapterInvocationRecord (Invocation Lifecycle)

```python
@dataclass(frozen=True)
class AdapterInvocationRecord:
    invocation_id: str                # UUID hex (12 chars)
    ticket_id: str                    # Owning ExecutionTicket ID
    allocation: ControlAllocation     # The allocation being executed
    runtime_instance_id: str          # Owning RuntimeInstance ID
    domain: ControlDomain             # Control domain for routing
    registered_adapter_name: str      # Adapter name at invocation time
    invoked_at: datetime              # When invocation was created
    adapter_session_id: str | None    # Set after invoke completes
    adapter_result: AdapterResult | None  # Set after invoke completes
    events: tuple[ExecutionEvent, ...]    # Events during lifecycle
    duration_ms: int                  # Wall-clock duration
    completed: bool                   # Whether invoke completed
```

- Created via `AdapterInvocationRecord.create(...)` (static factory)
- `.complete(adapter_session_id, result, events)` returns immutable new record
- `.success` property: True if completed OK, False if failed, None if not yet completed

#### AdapterInvoker (Stateless Dispatch)

```python
class AdapterInvoker:
    def __init__(self, registry: AdapterRegistry)
    def invoke(self, allocation, ticket_id, runtime_instance_id)
        -> tuple[AdapterInvocationRecord, list[ExecutionEvent]]
```

Steps:
1. Resolve adapter by `allocation.control_domain` via `registry.resolve_or_raise()`
2. Create `AdapterInvocationRecord` (immutable pre-invoke snapshot)
3. Emit `EventType.ADAPTER_INVOKED` event
4. Call `adapter.invoke(allocation, ticket_id, runtime_instance_id)`
5. Validate result: `result.allocation_id` must match `allocation.signal_id`
6. Complete the record via `record.complete(...)`
7. Emit `EventType.ADAPTER_RESULT` event with status + duration
8. Return (completed_record, events)

On adapter exception:
- Emit `EventType.SESSION_FAILED` event with error details
- Re-raise as `RuntimeError`

#### InvocationAudit (Read-Only Audit)

```python
@dataclass(frozen=True)
class InvocationAudit:
    invocation: AdapterInvocationRecord   # Full invocation record
    outcome: DispatchVerdict              # What scheduler decided
    runtime_instance_id: str
    ticket_id: str
    allocation_signal_id: str
```

- Created via `InvocationAudit.from_invocation(record, decision)`
- Requires completed record — raises `ValueError` on non-completed
- MUST NOT contain narrative state, generated text, or quality scores

### Forbidden Operations

The Adapter Invocation layer MUST NOT:

| Operation | Forbidden? | Rationale |
|-----------|-----------|-----------|
| Modify allocation | ❌ | Invoker receives allocations as immutable values |
| Modify ticket | ❌ | Tickets belong to Scheduler lifecycle |
| Generate content | ❌ | Adapter bridges, does not create |
| Access narrative state | ❌ | Runtime owns no narrative state |
| Reschedule | ❌ | Scheduling belongs to Scheduler |
| Bypass validation | ❌ | Result validation is non-optional |
| Construct prompts | ❌ | Would violate No Text Generation |

### Invocation Keys Forbidden in Events

The following keys MUST NOT appear in execution event details:

- `prompt` — would leak prompt construction into audit trail
- `generated_text` — would leak generated content
- `narrative_content` — would leak narrative state
- `quality_score` — would violate No Quality Judgment
- `recommendation` — would violate No Recommendation

### Contract Discipline

1. **AdapterInvoker is stateless** — no instance fields beyond registry reference
2. **AdapterInvoker does not own decisions** — routes allocations, does not modify them
3. **AdapterInvoker does not track history** — invocation records serve that role
4. **AdapterInvoker does not know OpenTale** — only knows `AdapterProtocol`
5. **AdapterRegistry is the SSOT** — no cached or derived adapter mappings
6. **Registration is by domain, not by adapter name** — names are for events and logs only
7. **All events are fully traceable** — every invocation produces exactly ADAPTER_INVOKED + ADAPTER_RESULT (or SESSION_FAILED)
8. **Result validation is structural** — checks allocation_id match and duration_ms non-negative, never narrative quality
9. **Duration is calculated at record completion** — true wall-clock time, not adapter self-report

### Integration with Scheduler (§15.5.2)

```
Scheduler.get_next_ticket()
    → ticket + allocations
    → for each allocation:
        → AdapterInvoker.invoke(allocation, ticket_id, runtime_id)
          → registry.resolve_or_raise(domain)
          → adapter.invoke(allocation, ticket_id, runtime_id)
          → AdapterResult
        → completed record + events
    → DispatchDecision
    → back to scheduler loop
```

- Scheduler owns the dispatch loop
- AdapterInvoker is a service the scheduler calls
- Scheduler never calls adapter.invoke() directly — always through AdapterInvoker
- Scheduler never modifies allocations before or after invocation

---

## 12. Validation Contract (§15.5.4)

### Contract Purpose

The Validation layer provides **structural pre- and post-condition checks** for every artifact flowing through the Runtime. Validation is pure, deterministic, and domain-agnostic — it checks structure, not narrative quality.

```
┌──────────────────────────────────────────────────────────┐
│  Runtime Validation Layer  (§15.5.4)                      │
│                                                            │
│  Each artifact type has a dedicated validator:             │
│                                                            │
│  ├── TicketValidator      — checks ExecutionTicket fields  │
│  ├── AllocationValidator  — checks ControlAllocation       │
│  ├── ResultValidator      — checks AdapterResult           │
│  ├── RecordValidator      — checks AdapterInvocationRecord │
│  ├── EventValidator       — checks ExecutionEvent          │
│  └── SessionValidator     — checks ExecutionSession        │
│                                                            │
│  RuntimeValidator (composite) — delegates to all six and   │
│    aggregates results into a single RuntimeValidationResult │
│                                                            │
│  All validators follow the same shape:                     │
│    validate(artifact) → RuntimeValidationResult            │
│                                                            │
│  No side effects, no state, no model calls.                │
└──────────────────────────────────────────────────────────┘
```

### Validation Principles (R1–R7)

| # | Principle | Enforcement |
|---|-----------|-------------|
| **R1** | **Pure Function** — Given identical input, `validate()` always returns identical output. | No mutable state, no memoisation, no random, no I/O. Verified by deterministic tests. |
| **R2** | **No Fail-Fast** — Validation collects ALL issues in a single pass, not stopping at the first failure. | Test asserts that a multi-failure artifact returns all its issues, not truncated to one. |
| **R3** | **No Filtering** — Every issue found must be reported. Validation must not silently skip or suppress issues. | Code review: no `break`/`return` in issue-collection loops. |
| **R4** | **No Scoring** — Validation produces a binary valid/invalid verdict, never a quality score or recommendation. | `RuntimeValidationResult` has no `score` field, no severity-grading beyond `ERROR`/`WARN`. |
| **R5** | **Backwards Compatible** — Extra fields on validated artifacts must not cause errors or rejection. | Tests add optional unknown fields and assert no spurious failures. |
| **R6** | **Graceful Handling of None** — Any `None` field must produce an issue, never a crash. | Boundary tests pass `None` for every nullable field. |
| **R7** | **Known Enums Only** — Validation rejects unrecognised enum values (`ControlDomain`, `ExecutionState`, `EventType`) without enumerating or guessing. | Tests pass garbage enum strings and assert rejection. |

### Validation Categories

| Category | Description | Tests |
|----------|-------------|-------|
| **Pure Function** | Same input → same output every time. No state, I/O, randomness. | `test_*_pass` + non-memoisation checks |
| **Deterministic** | Implicitly covered by pure-function tests; no mutable state shared between calls. | Aggregation-level deterministic checks |
| **Enum Exhaustiveness** | Every ValidationCode enum member has a test exercising its associated check. | `TestIssueCodeExhaustiveness` — one test per code enum |
| **Boundary** | Edge cases: `None`, empty strings, negative values, unrecognised enums. | `TestBoundary` — 7 tests |
| **Compatibility** | Extra optional fields on artifacts must not cause validation failures. | `TestCompatibility` — 2 tests |

### Validators Overview

| Validator | Artifact | Primary Checks |
|-----------|----------|----------------|
| **TicketValidator** | `ExecutionTicket` | ticket_id, runtime_instance_id, execution_plan_id, state enum |
| **AllocationValidator** | `ControlAllocation` | signal_id, control_domain enum |
| **ResultValidator** | `AdapterResult` | adapter_session_id, status enum, duration_ms ≥ 0, started_at ≤ finished_at, narrative keyword warning |
| **RecordValidator** | `AdapterInvocationRecord` | invocation_id, domain enum, duration_ms ≥ 0, completed+session consistency |
| **EventValidator** | `ExecutionEvent` | event_id, event_type enum, timestamp validity, empty optional fields warning |
| **SessionValidator** | `ExecutionSession` | session_id, ticket_id, allocation_id, runtime_instance_id, state enum |
| **RuntimeValidator** | Mixed (composite) | Delegates all six, aggregates issues, enforces no-fail-fast |

### ValidationCode Enums

Each validator has a matching `*ValidationCode` enum that lists every issue code it can produce:

| Enum | Codes |
|------|-------|
| `TicketValidationCode` | `TICKET_MISSING_FIELD`, `TICKET_INVALID_STATE` |
| `AllocationValidationCode` | `ALLOCATION_MISSING_FIELD`, `ALLOCATION_INVALID_DOMAIN` |
| `ResultValidationCode` | `RESULT_MISSING_FIELD`, `RESULT_INVALID_STATUS`, `RESULT_NEGATIVE_DURATION`, `RESULT_FINISHED_BEFORE_STARTED`, `RESULT_NARRATIVE_KEYWORD_WARNING` |
| `RecordValidationCode` | `RECORD_MISSING_FIELD`, `RECORD_INCONSISTENT_STATE`, `RECORD_INVALID_DOMAIN` |
| `EventValidationCode` | `EVENT_MISSING_FIELD`, `EVENT_INVALID_TYPE`, `EVENT_INVALID_TIMESTAMP`, `EVENT_EMPTY_OPTIONAL` |
| `SessionValidationCode` | `SESSION_MISSING_FIELD`, `SESSION_INVALID_STATE` |

### Integration with Quality Gate

Validation is called by Quality Gate during its own validation pipeline. However, §15.5.4 validation is strictly structural — it can never escalate to Quality Gate severity on its own.

```
Quality Gate
    │
    ├── invokes §15.5.4 validate() for structure checks
    │     (structural issues → §15.5.4 issues)
    │
    └── runs §15.4 quality checks for semantic/architectural rules
          (policy issues → QualityGateViolation)
```

### Forbidden Operations

The Validation layer MUST NOT:

| Operation | Forbidden? | Rationale |
|-----------|-----------|-----------|
| Generate text | ❌ | Would violate No Text Generation |
| Call LLM / model API | ❌ | Pure structural checks only |
| Access narrative state | ❌ | Runtime validation has no access to narrative |
| Score or grade quality | ❌ | Only valid/invalid verdict |
| Modify artifacts | ❌ | Validation is read-only |
| Skip checks | ❌ | Every artifact must pass validation |
| Mutate shared state | ❌ | Must be fully deterministic/repeatable |
| Recommend decisions | ❌ | Validation does not guide policy |

### Contract Discipline

1. **All validators are pure functions** — no instance state, no I/O, no randomness
2. **Every validation code has a matching test** — enum exhaustiveness is enforced by `TestIssueCodeExhaustiveness`
3. **Validation is single-pass, no fail-fast** — collects all issues before returning
4. **Validation is backward compatible** — extra fields on artifacts are tolerated (not rejected)
5. **Validation is domain-agnostic** — checks structure only, never narrative correctness
6. **`RuntimeValidationResult` is a frozen dataclass** — immutable after creation
7. **`ValidationIssue` is a frozen dataclass** — immutable issue with code, message, optional field, source

### File Layout

```
reality/
├── runtime_validation.py   # All validators, enums, result/issue types
├── runtime_contract.py     # ExecutionTicket, AdapterResult, etc.
├── director_contract.py    # ControlDomain enum
└── __init__.py             # Exports all validators + types

tests/phase15/
├── test_phase15_5_4_validation_contract.py  # 89 tests
```

---

## 4. Forbidden Operations (Absolute)

These operations are FORBIDDEN for every module in the Runtime layer (Orchestrator, Adapter, and all supporting components):

### ❌ No Knowledge Generation
- Must NOT generate Patterns
- Must NOT derive Principles
- Must NOT modify Registry entries
- Must NOT create new Evidence or Relation records
- Must NOT query Knowledge Plane for narrative judgment

### ❌ No Text / Prompt Generation
- Must NOT generate narrative text
- Must NOT construct prompts
- Must NOT call LLM / model API
- Must NOT write story content
- Must NOT evaluate or judge narrative quality

### ❌ No Signal Generation
- Must NOT create new ControlSignal instances
- Must NOT modify existing ControlSignal instances
- Must NOT bypass Director arbitration

### ❌ No Registry Modification
- Must NOT write to PrincipleRegistry
- Must NOT write to PatternRegistry
- Must NOT modify Knowledge Base

### ❌ No Quality Judgment
- Must NOT score narrative quality
- Must NOT compare stories
- Must NOT recommend changes
- Must NOT rate execution outcomes

### ❌ No Cross-Layer Bypass
- Must NOT import OpenTale Runtime directly
- Must NOT call Writer/Director modules directly
- Must NOT bypass Adapter for OpenTale interaction
- Must NOT access pattern/registry data for runtime decisions

---

## 5. Lifecycle Responsibility

### ExecutionTicket Lifecycle States

```
Pending ──→ Queued ──→ Running ──→ Completed
  │            │          │
  │            │          ├──→ Failed ──→ Archived
  │            │          │
  │            │          ├──→ Aborted ──→ Archived
  │            │          │
  │            │          └──→ Suspended ──→ Running (resume)
  │            │
  │            └──→ Cancelled ──→ Archived
  │
  └──→ Archived (never entered queue)
```

### State Transition Rules

| From | To | Allowed? | Trigger |
|------|----|----------|---------|
| Pending | Queued | ✅ | Orchestrator enqueue |
| Queued | Running | ✅ | Scheduler dispatch |
| Running | Completed | ✅ | All allocations consumed |
| Running | Failed | ✅ | Adapter invocation error (non-recoverable) |
| Running | Aborted | ✅ | Manual abort or timeout |
| Running | Suspended | ✅ | Runtime policy or external signal |
| Suspended | Running | ✅ | Resume signal |
| Failed | Archived | ✅ | Cleanup |
| Completed | Archived | ✅ | Cleanup |
| Aborted | Archived | ✅ | Cleanup |
| Cancelled | Archived | ✅ | Cleanup |
| Pending | Archived | ✅ | Never queued |
| Queued | Pending | ❌ | No backward transition |
| Running | Pending | ❌ | No backward transition |
| Completed | Running | ❌ | No replay from completed |
| Archived | Any | ❌ | Final state, immutable |

### Who Owns Each State Transition

| Transition | Owner | Validates |
|------------|-------|-----------|
| Pending → Queued | Runtime Orchestrator | ExecutionPlan is valid |
| Queued → Running | Scheduler | Queue position + resource availability |
| Running → Completed | Runtime Orchestrator | All Adapter invocations returned |
| Running → Failed | Runtime Orchestrator | Adapter error (non-recoverable) |
| Running → Aborted | Recovery Manager | User/Runtime abort signal |
| Running → Suspended | Recovery Manager | Resource/Policy constraint |
| Suspended → Running | Recovery Manager | Resume signal received |
| → Archived | Cleanup Manager | No pending operations |

---

## 6. Adapter Boundary

### Single Legitimate Path

```
ExecutionPlan
    │
    ▼
Runtime Orchestrator
    │
    ▼
Adapter.invoke(allocation: ControlAllocation) → AdapterResult
    │
    ▼
ConstraintBundleContract.build(allocation, adapted_constraints)
    │
    ▼
(OCOS boundary)
    │
ConstraintBundle Implementation (OpenTale side)
    │
    ▼
OpenTale Runtime (Writer / Character / etc.)
```

### Adapter Contract Rules

1. Adapter receives exactly ONE `ControlAllocation` per invocation
2. Adapter delivers exactly ONE `ConstraintBundleContract` to OpenTale
3. Adapter returns `AdapterResult` containing execution status + optional trace data
4. Adapter must NOT modify the `ControlAllocation` it receives
5. Adapter must NOT retain reference to `ExecutionPlan`
6. Adapter must NOT log narrative content (only structural metadata)
7. Each Adapter instance serves one session, one allocation

### Rule: Adapter Invocation SHOULD Be Idempotent

**Same ExecutionTicket + Same Allocation → at most one effective side effect.**

- Adapter SHOULD be designed so that identical invocations produce identical external effects
- If idempotence cannot be guaranteed, Adapter MUST return `NON_IDEMPOTENT` in its result
- `NON_IDEMPOTENT` signals Recovery Manager to treat retry as unsafe — skip retry, escalate to ABORTED
- The Runtime Orchestrator delegates idempotence assessment to the Adapter; it does not assume

Rationale: Recovery retry without idempotence guarantees can produce duplicate side effects (e.g., character updated twice, scene written twice) that are invisible to OCOS but corrupt OpenTale execution state.

### ConstraintBundle Boundary

| Aspect | OCOS | OpenTale |
|--------|------|----------|
| **Owns** | `ConstraintBundleContract` (interface/dataclass) | `ConstraintBundle` (implementation) |
| **Defines** | `build()` signature, field types, constraints | Concrete constraint structures, runtime logic |
| **Versioning** | Contract version (semver) | Implementation version (independent) |
| **Dependency** | None on OpenTale | Must satisfy Contract interface |

---

## 7. Recovery Ownership

### Scope

| Recovery Action | Owned By | Affects |
|-----------------|----------|---------|
| Retry | Runtime Orchestrator (Recovery Manager) | Adapter session only |
| Rollback | Runtime Orchestrator (Recovery Manager) | ExecutionTicket state |
| Abort | Runtime Orchestrator (Recovery Manager) | ExecutionTicket → ABORTED |
| Resume | Runtime Orchestrator (Recovery Manager) | ExecutionTicket → RUNNING |
| Timeout | Runtime Orchestrator (Scheduler) | Adapter session → TIMEOUT |

### Recovery Constraints

1. **Retry** does NOT create new signals, plans, or principles
2. **Rollback** does NOT restore narrative state (Runtime has no narrative state)
3. **Abort** is a terminal state — no recovery from ABORTED
4. **Resume** is only valid from SUSPENDED state
5. **Timeout** threshold is set at Orchestra level, not per allocation

### Rule: Recovery Executes Policy, Does Not Decide

**Recovery Manager is an executor, not a decision-maker.**

- Recovery Manager performs the actions prescribed by Policy (retry N times, abort after N failures, suspend on resource pressure)
- Recovery Manager must NOT decide:
  - How many retry attempts are permitted (Policy decides)
  - Whether to abort or suspend (Policy decides)
  - Whether to escalate to Meta Control (Policy decides)
- The decision layer for recovery is intentionally external: initially simple configuration, later Phase15.6 Meta Control
- This prevents Recovery from evolving into an autonomous decision-maker that rivals Director or Meta Control

Rationale: Without this rule, Recovery is the module most prone to accumulating "just one more decision" — eventually becoming a second Director with no quality gate oversight.

### What Recovery May NOT Do

- ❌ Modify ExecutionPlan
- ❌ Modify Registry
- ❌ Generate new signals
- ❌ Rewrite constraint bundles
- ❌ Bypass Quality Gate
- ❌ Call LLM / model API
- ❌ Import OpenTale Runtime directly

---

## 8. OpenTale Boundary (System Interface)

### What OCOS Exports to OpenTale

```
ConstraintBundleContract (interface only)
ExecutionTicket (read-only state)
RuntimeResult (status code only: SUCCESS / FAILED / PARTIAL / ABORTED)
```

### What OCOS Imports from OpenTale

```
Nothing. Dependency is one-way: OCOS → Adapter → ConstraintBundle Contract.
```

### Integration Rules

| Rule | Description |
|------|-------------|
| **One-Way Gate** | OCOS calls OpenTale via Adapter. OpenTale never calls OCOS. |
| **No Shared State** | OCOS and OpenTale share no mutable state. All data passed as value objects. |
| **No Shared Registry** | OpenTale has no access to OCOS Registry. OCOS has no access to OpenTale internal state. |
| **Failure Isolation** | OpenTale failure does not corrupt OCOS state. Adapter handles errors and returns structured results. |
| **Version Independence** | OCOS and OpenTale may evolve on different version schedules. Contract versioning ensures compatibility. |
| **No Registry Invalidation** | OpenTale Runtime failures shall NEVER invalidate PatternRegistry or PrincipleRegistry. Knowledge Plane state is independent of Runtime execution outcome. A failed execution does not retroactively invalidate a valid pattern or principle. |

Rationale (No Registry Invalidation): Runtime execution failures (timeout, adapter error, story generation failure) are execution-level events. Knowledge Plane state (Patterns, Principles) is derived from structural analysis and domain design — not from execution success. Binding Knowledge lifecycle to Runtime lifecycle would make Knowledge unrecoverable after transient execution failures.

---

## 9. Core Principle: Runtime Owns No Narrative State

> **Runtime is a scheduler, not a state keeper.**

### Runtime MAY Own

| State Type | Examples | Storage Lifecycle |
|------------|----------|-------------------|
| Execution Tickets | Ticket ID, state, timestamps | Per execution session |
| Queue State | Queue position, order | Per orchestration run |
| Lifecycle Metadata | Runtime creation time, version | Module lifecycle |
| Timeout Config | Per-adapter timeout threshold | Configuration scope |
| Retry Counters | Retry attempt numbers | Per allocation session |
| Lock State | Execution lock, concurrency guard | Per ticket lifetime |
| Recovery Records | Recovery attempt log | Per ticket lifetime |

### Runtime MUST NOT Own

| State Type | Examples | Rationale |
|------------|----------|-----------|
| Character State | Character personality, memory, relationships | Belongs to Narrative Domain |
| World State | Setting, timeline, lore | Belongs to Narrative Domain |
| Pattern State | Active patterns, pattern metadata | Belongs to Knowledge Plane |
| Principle State | Active principles, inference history | Belongs to Knowledge Plane |
| Story Progress | Chapter number, plot arcs, pacing | Belongs to Narrative Domain |
| Narrative Memory | Past events, character arcs | Belongs to Narrative Narrative Memory |
| Signal History | Past signal values | Belongs to Control Plane (Quality Gate) |
| Director State | Budget allocations, conflict records | Belongs to Control Plane (Director) |
| User Preferences | Genre, style, formatting | Belongs to Application Layer |

### Why This Matters

1. **Replaceability** — Runtime can be replaced (local → cloud, single → multi-engine) without migrating narrative state
2. **Testability** — Runtime tests need only ticket/queue fixtures, not full narrative world
3. **Observability** — Runtime failures are structural (timeout, abort), not narrative (bad story quality)
4. **Recoverability** — Runtime recovery is mechanical (retry, resume), not semantic (restore story coherence)
5. **Scalability** — Stateless runtime can scale horizontally; narrative state lives in bounded context

---

## 10. Runtime Transparency Principle

> **Runtime decisions must be fully explainable through structural execution records.**

### Runtime MAY Produce

| Record Type | Examples | Storage |
|-------------|----------|---------|
| ExecutionLog | Ticket created, ticket queued, ticket dispatched | Per ticket |
| LifecycleLog | Runtime boot, Runtime shutdown, version change | Per RuntimeInstance |
| AdapterLog | Allocation dispatched, result received, duration | Per allocation |
| RecoveryLog | Retry attempt N, Abort triggered, Resume from SUSPENDED | Per recovery event |

### Runtime MUST NOT Produce

| Record Type | Examples | Rationale |
|-------------|----------|-----------|
| Reasoning Trace | "Skipped scene 3 because pacing felt slow" | Structural runtime has no narrative reasoning |
| Thought Trace | "Character motivation insufficient, deferring" | Narrative analysis belongs to Knowledge or Director |
| Narrative Analysis | "Scene conflict resolved poorly, score = 3/5" | Quality judgment belongs to (future) evaluation layer, not Runtime |
| Quality Evaluation | "This allocation is suboptimal" | Optimisation belongs to Meta Control or Policy |

### Why Transparency Matters

1. **Debuggability** — Every Runtime action has a structural explanation visible as a log entry
2. **Auditability** — Post-mortem analysis reads structured execution records, not AI reasoning chains
3. **Testability** — Runtime behaviour is deterministic: same input → same log sequence → same outcome
4. **Boundary Enforcement** — If a module cannot explain its action without narrative reasoning, it belongs in Knowledge or Control Plane, not Runtime

---

## 13. Recovery Protocol Contract (§15.5.5)

> **Status**: ❄️ FROZEN 2026-07-23
> **Implements**: `reality/runtime_recovery.py`

The Recovery Protocol defines the concrete types and behaviours that realise
the ownership rules declared in §7.

### 13.1 Domain Enums

| Enum | Values | Purpose |
|------|--------|---------|
| `RecoveryState` | `NOT_STARTED`, `RETRYING`, `SUSPENDED`, `RESUMING`, `ABORTED` | Lifecycle states of a recovery episode |
| `RecoveryReason` | `TIMEOUT`, `ADAPTER_FAILURE`, `VALIDATION_FAILURE`, `RESOURCE_EXHAUSTED`, `POLICY_ABORT`, `NON_IDEMPOTENT` | Reason for invoking recovery |
| `Recoverability` | `RECOVERABLE`, `NON_RECOVERABLE` | Static classification of reason → recoverability |
| `RecoveryAction` | `RETRY`, `SUSPEND`, `ABORT`, `RESUME`, `ESCALATE_TO_POLICY` | Action taken by the Recovery Manager |
| `RecoveryVerdict` | `SUCCESS`, `FAILED`, `ESCALATED` | Outcome verdict returned to the caller |

### 13.2 Key Types

- **`RecoveryRecord`** — One frozen dataclass per recovery event. Carries:
  `record_id`, `correlation_id`, `ticket_id`, `session_id`, `runtime_instance_id`,
  `attempt`, `reason`, `recoverability`, `action`, `policy_version`, `runtime_version`,
  `contract_version`, `timestamp`, `previous_state`, `new_state`, `detail`.

- **`RecoveryResult`** — Output envelope with exactly one `latest_record: RecoveryRecord`
  and a `verdict: RecoveryVerdict`. No records history — history is owned by the caller.

- **`RecoveryContext`** — Version-pinned replay context passed on every call:
  `policy_version`, `runtime_version`, `contract_version`, `max_retries`.

### 13.3 Protocol Interface

```python
class RecoveryProtocol(ABC):
    @abstractmethod
    def handle_failure(
        self, ticket, session, reason, previous_records, context,
    ) -> RecoveryResult: ...

    @abstractmethod
    def handle_resume(
        self, ticket, previous_records, context,
        session: ExecutionSession | None = None,
    ) -> RecoveryResult: ...
```

### 13.4 DefaultRecoveryManager Behaviour Matrix

| Reason | Recoverability | Action | New State | Verdict |
|--------|---------------|--------|-----------|---------|
| TIMEOUT | RECOVERABLE | RETRY | RETRYING | SUCCESS |
| ADAPTER_FAILURE | RECOVERABLE | RETRY | RETRYING | SUCCESS |
| VALIDATION_FAILURE | RECOVERABLE | RETRY | RETRYING | SUCCESS |
| RESOURCE_EXHAUSTED | RECOVERABLE | SUSPEND | SUSPENDED | SUCCESS |
| POLICY_ABORT | NON_RECOVERABLE | ESCALATE_TO_POLICY | ABORTED | ESCALATED |
| NON_IDEMPOTENT | NON_RECOVERABLE | ESCALATE_TO_POLICY | ABORTED | ESCALATED |

- **Retry**: increments `attempt`, preserves `correlation_id` and all identity fields
- **Escalation**: produces `ESCALATED` verdict only (no Meta Control call — pure protocol)
- **Max retries exceeded** (`attempt > context.max_retries`): escalates regardless of reason
- **Resume from SUSPENDED**: produces `RESUME` → `RETRYING` (SUCCESS)
- **Resume from non-SUSPENDED**: produces `ABORT` → `ABORTED` (FAILED)

### 13.5 Recovery Rules (R1–R7)

| Rule | Enforced | Check |
|------|----------|-------|
| **R1** Mechanical Recovery — no narrative tokens in type names, field names, or docstrings | ✅ | `NARRATIVE_FORBIDDEN_TOKENS` |
| **R2** No Re-planning — Recovery never imports `ExecutionPlan` | ✅ | AST import scan |
| **R3** Retry binds Ticket — attempt number increments, ticket_id unchanged | ✅ | Identity preservation tests |
| **R4** Replayable — deterministic output for same input | ✅ | Same-input same-output assertion |
| **R5** Escalation is Protocol — ESCALATED verdict only, no external calls | ✅ | Verdict-only check |
| **R6** No External Observation — Recovery never imports Knowledge/Registry/Observation modules | ✅ | AST import scan |
| **R7** No New Identity — Recovery creates only `RecoveryRecord`; no new Ticket/Session/RuntimeInstance/Allocation | ✅ | Output type audit |

### 13.6 Identity Preservation

- `correlation_id` is generated once per recovery chain (first record) and preserved across all subsequent records
- `ticket_id`, `runtime_instance_id` are never changed by Recovery
- `session_id` is passed through from the caller (or uses `ticket.ticket_id` as fallback)
- The only mutable fields across a recovery chain are: `attempt`, `state`, `timestamp`, `detail`

### 13.7 File Layout

```
reality/runtime_recovery.py         — All types, protocol, and default implementation
reality/__init__.py                  — Public exports (Recovery* types + helpers)
tests/phase15/test_phase15_5_5_recovery_contract.py  — 61 tests, 7 rule classes
```

### 13.8 Test Coverage

- 5 enum tests (values, frozen, narrative-free)
- 5 Recoverability classification tests (deterministic, covers all, narrative-free)
- 4 record/result/context dataclass tests
- 2 protocol interface tests
- 10 DefaultRecoveryManager behaviour tests
- 4 R1 mechanical recovery tests
- 2 R2 no-replanning tests
- 1 R6 no-external-observation test
- 3 R7 no-new-identity tests
- 3 Identity preservation tests
- 4 Boundary/edge-case tests
- **Total: 61 tests (100% pass)**

*This document is part of OCOS Phase15.5 Runtime Orchestration. All contents are frozen as Phase15.5.0 pre-requisite.*
