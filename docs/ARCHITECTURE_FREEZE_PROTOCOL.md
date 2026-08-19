# Architecture Freeze Protocol (AFP)

> **Version**: 1.0
> **Status**: Architecture Admission Standard — OCOS Engineering Governance
> **Scope**: All future modules, planes, and subsystems entering the OCOS codebase

---

## Overview

The Architecture Freeze Protocol (AFP) is the **Architecture Admission Standard** for OCOS. It is not a post-hoc documentation template — it is the **gate** that every new module must pass before entering the mainline codebase.

### Three-Layer Governance Framework

AFP is the middle layer of OCOS's complete engineering governance architecture:

```
 Architecture Principles          ← Design axioms (why)
       │
       ▼
 Architecture Admission          ← AFP: module admission criteria (how to prove)
 Standard (AFP)
       │
       ▼
 Frozen Modules                  ← Certified stable capabilities (what)
```

Each layer has a distinct responsibility:

| Layer | Role | Questions It Answers | References |
|-------|------|---------------------|------------|
| **Architecture Principles** | Design axioms — the "why" of system architecture | Why is the system structured this way? What trade-offs were made? What must never be violated? | `OCOS_CORE_CONSTITUTION.md` (7 部分 + 11 条不可变规则 + 5 阶段实施计划 A–E) |
| **AFP (this document)** | Admission standard — the "how" of module certification | How does a module prove it conforms to the principles? What gates must it pass before entering mainline? | `ARCHITECTURE_FREEZE_PROTOCOL.md` (10 阶段 + F1–F14) |
| **Frozen Modules** | Certified outputs — the "what" of stable capabilities | Which modules have passed certification? What are their boundaries, ownerships, and forbidden operations? | `docs/contracts/*_OWNERSHIP.md` + `audit/*_freeze_certificate.md` |

The relationship is one-directional: Principles define AFP, AFP gates modules, and modules must not undermine Principles.

### Admission Pipeline

```
Any new module
     │
     ▼
Architecture Freeze Protocol (AFP)
     │
     ├── Stage 1: Boundary Freeze      — what is IN / OUT of scope
     ├── Stage 2: Ownership Freeze     — 4 ownership questions answered
     ├── Stage 3: ABI Freeze           — data types, contracts, protocols
     ├── Stage 4: Validation Freeze    — pre-conditions, post-conditions
     ├── Stage 5: Lifecycle Freeze     — state machines, transitions
     ├── Stage 6: Dependency Audit     — import graph, layer boundaries
     ├── Stage 7: Forbidden Ops Audit  — what this module must never do
     ├── Stage 8: Determinism Audit    — same input → same output
     ├── Stage 9: Identity Audit       — identity preservation
     ├── Stage 10: Certificate + ADR   — freeze doc + decision record
     │
     ▼
Admitted into Mainline (Frozen)

AFP enforces that every module answers four ownership questions:

1. **What does it know?** (information boundaries)
2. **What does it control?** (decision scope)
3. **What does it own?** (state/responsibility)
4. **What does it decide?** (authority boundaries)

And additionally: **What must it never do?**

A freeze is not a feature-complete marker. A freeze is a **boundary-lock**: the module's interfaces, ownership, dependencies, and prohibited behaviors are certified and will not change without a new freeze cycle.

---

## The Freeze Process (10 Stages)

```
Stage  1 — Boundary Freeze       (what is IN / OUT of scope)
Stage  2 — Ownership Freeze      (4 ownership questions answered)
Stage  3 — ABI Freeze            (data types, contracts, protocols)
Stage  4 — Validation Freeze     (pre-conditions, post-conditions)
Stage  5 — Lifecycle Freeze      (state machines, transitions)
Stage  6 — Dependency Audit      (import graph, layer boundaries)
Stage  7 — Forbidden Ops Audit   (what this module must never do)
Stage  8 — Determinism Audit     (same input → same output)
Stage  9 — Identity Audit        (identity preservation across lifecycle)
Stage 10 — Certificate Generation (freeze document + changelog)
```

Each stage produces one or more **audit dimensions** (F1–F14). Stages may be executed in parallel within a single freeze cycle; the sequence above represents dependency order.

---

## The 14 Audit Dimensions (F1–F14)

### F1 — ABI Completeness

**Purpose**: Verify that all public types, protocols, enums, and constants are exported and correctly typed.

**Checks**:
- Contract version constants exist and are typed (`str`, `frozenset`, etc.)
- All expected enum types exist with expected members
- Core dataclass types exist and are frozen/immutable
- Protocol interfaces exist with required abstract methods
- Default implementations exist for each protocol

**Pass condition**: All ABI elements match their frozen specification.

---

### F2 — Ownership Compliance

**Purpose**: Verify that the module's data structures contain only the fields it is permitted to own.

**Checks**:
- No narrative/domain fields appear in structural types
- All identity fields are structural (IDs, timestamps, versions)
- Policy/configuration types contain no domain leakage
- Record types contain no reasoning or evaluation fields

**Pass condition**: Zero fields violate the pre-established Ownership Matrix.

---

### F3 — Lifecycle Integrity

**Purpose**: Verify that all state machines are well-formed and transitions are deterministic.

**Checks**:
- Valid transition function exists and rejects illegal transitions
- Self-transitions (state → same state) are forbidden
- Known-forbidden transitions (skip states, rollbacks, re-runs) are rejected
- Terminal states accept no onward transitions
- Valid-state constants are non-empty

**Pass condition**: No state machine violation across any entity type.

---

### F4 — Recovery / Lifecycle Protocol

**Purpose**: Verify that error recovery and lifecycle management follow specified protocols (e.g., R1–R7).

**Checks**:
- No narrative tokens in type/function names
- No imports from upstream layers (Knowledge, Control)
- Attempt tracking increments correctly
- Deterministic replay under identical inputs
- Escalation produces only protocol-compliant verdicts
- No identity construction inside recovery handlers
- All manager methods are implemented

**Pass condition**: All protocol rules satisfied.

---

### F5 — Adapter / Layer Isolation

**Purpose**: Verify that this module communicates with adjacent layers only through defined interfaces.

**Checks**:
- No direct imports from downstream layers
- Communication occurs only through abstract protocol interfaces
- No implicit dependencies through type leakage

**Pass condition**: No direct cross-layer import violations.

---

### F6 — Dependency Audit

**Purpose**: Verify that the import graph is one-directional and contains no reverse dependencies.

**Checks**:
- No imports from upstream layers (Knowledge, Control → Runtime)
- Module boundaries are respected in `__init__.py` exports
- Dependency direction matches the architectural layering

**Pass condition**: Import graph is a DAG matching the architecture.

---

### F7 — Forbidden Operations

**Purpose**: Verify that the module contains no code from its defined "must never do" list.

**Checks**:
- No LLM/model API calls
- No prompt generation or template building
- No narrative content generation keys
- No Registry writes (Pattern/Principle/Knowledge)
- No quality scoring or evaluation
- Forbidden-keys constants are non-empty and populated
- Scheduler/Adapter forbidden operations lists exist

**Pass condition**: Zero occurrences of forbidden patterns in source code (excluding docstrings and comments verified via AST).

---

### F8 — Determinism Audit

**Purpose**: Verify that all public operations are deterministic: same inputs → same outputs.

**Checks**:
- Recovery produces same verdict on repeated identical calls
- Validation produces same result on repeated identical inputs
- All recovery reasons produce consistent results
- Scheduler dispatch decisions are deterministic given same queue state

**Pass condition**: All tested operations return identical outputs for identical inputs.

---

### F9 — Identity Preservation

**Purpose**: Verify that identity fields are preserved across the entire lifecycle.

**Checks**:
- Ticket ID preserved across recovery chains
- Correlation ID preserved across retries
- Attempt counter increments monotonically
- Runtime Instance ID preserved across all operations
- Contract version is consistent across records
- Identity IDs are unique per construction

**Pass condition**: All identity fields survive the operation chain intact.

---

### F10 — Transparency Audit

**Purpose**: Verify that the module's output records contain only structural/mechanical data, not reasoning traces.

**Checks**:
- No reasoning fields (`reasoning`, `thought`, `analysis`, `explanation`, etc.)
- No narrative evaluation fields in any result type
- No quality assessment fields in any structural record

**Pass condition**: All record/result types are structurally transparent.

---

### F11 — Purity Audit

**Purpose**: Verify that operations are pure: they don't mutate their inputs or produce side effects beyond their intended scope.

**Checks**:
- Operations do not mutate input arguments
- Validators do not modify their targets
- No file I/O, network calls, or global state mutations in core logic

**Pass condition**: No input mutation or unexpected side effects detected.

---

### F12 — Boundary Audit

**Purpose**: Verify that the module does not depend on the implementation of its downstream consumers.

**Checks**:
- No imports from execution/consumption layers
- Protocol interfaces are truly abstract (no implementation methods)
- Module `__init__` does not export downstream types
- All communication with downstream layers goes through protocol abstractions

**Pass condition**: The module is replaceable without modifying its consumers.

---

### F13 — Evolution Audit

**Purpose**: Verify that future architectural evolution of this module cannot silently break freezing boundaries. Unlike F1–F12 which check current state, F13 checks **evolvability constraints** — structural guardrails that prevent gradual drift.

**Checks**:

| Check | Enforcement |
|-------|-------------|
| **Will the addition of a new capability create a second decision entry point?** | Ownership Matrix must be updated before capability is added; if new capability would add a decision point outside the authorized scope, freeze must be reopened |
| **Can a new feature be added without introducing cross-layer dependencies?** | All new feature imports must be auditable against the architecture layers |
| **Does a proposed change expand forbidden operations?** | Any new API endpoint / public method must be checked against F7 forbidden patterns |
| **Does a proposed change introduce new mutable state?** | New state variables must be declared in the Ownership Matrix; hidden mutable state is forbidden |
| **Can a proposed feature be removed without ripple effects?** | Each feature must carry an explicit "removal cost" assessment |

**Pass condition**: All new feature proposals pass these 5 checks before merge. The freeze certificate should record this as **auditable by code review**, not by automated script alone.

**Implementation requirement**: The project MUST enforce that any PR adding capability to a frozen module includes an F13 impact assessment in the PR description.

---

### F14 — Replaceability Audit

**Purpose**: Verify that the frozen module can be replaced wholesale without architectural disruption. This is the ultimate test of interface-boundary quality.

**Three questions for every frozen module**:

| # | Question | Pass Criterion |
|---|----------|----------------|
| Q1 | **Can the entire module implementation be replaced?** | A new implementation can be swapped in by implementing the same protocol interface(s) and providing a factory/builder. No source-code modification of consumers required. |
| Q2 | **After replacement, does the ABI remain compatible?** | All public types, protocol signatures, and exported constants are source-compatible. No behavioral contract is broken (same pre/post conditions). |
| Q3 | **Are consumers unaffected by the replacement?** | Consumer code compiles against the ABI, not the implementation. If a consumer must change, the interface boundary is too porous. |

**Additional checks**:
- The module has at least one abstract protocol interface
- All cross-module communication goes through that interface
- Default implementations are separable from the interface definition
- Configuration/policy types are owned by the interface, not the implementation
- Internal state is not exposed through the public API

**Pass condition**: All three questions are answered "yes" with verifiable evidence. If any answer is "no", the ABI boundary has coupling issues that must be resolved before certification.

#### F14.5 — Replaceability Metrics (Quantitative)

For long-term governance, F14 can evolve from three qualitative questions into a structured scoring system:

| Metric | Definition | Target |
|--------|------------|--------|
| **Interface Stability** | Does the public ABI change under replacement? | No change |
| **Consumer Impact Count** | Number of modules that must change | 0 |
| **Dependency Fan-out** | Number of modules affected by replacement | ≤ 1 (the replaced module itself) |
| **State Migration Required** | Does replacement require data migration? | No |
| **Rollback Capability** | Can the old implementation be restored without side effects? | Yes, without data loss |
| **Test Surface Change** | Do existing tests for consumers need modification? | 0 |
| **Configuration Compatibility** | Do existing configs work with the new impl? | Yes (backward-compatible) |

These metrics are measured at certification time and recorded in the freeze certificate. Over time, a project can track each metric across freeze cycles to detect architectural coupling trends.

---

## Freeze Cycle Workflow

### Pre-Freeze Checklist

- [ ] Ownership Matrix drafted (who owns what)
- [ ] Forbidden operations list compiled (must never do)
- [ ] Protocol interfaces defined (ABI boundaries)
- [ ] State machines specified (lifecycle transitions)
- [ ] Recovery/lifecycle protocol documented
- [ ] Layer dependency diagram approved

### Freeze Stages

```
Stage 1: Boundary Freeze
  └─ Deliverable: Scope document (what is IN/OUT)

Stage 2: Ownership Freeze
  └─ Deliverable: Ownership Matrix (§1), 4 questions answered

Stage 3: ABI Freeze
  └─ Deliverable: F1 — ABI Completeness audit (all types/protocols frozen)

Stage 4: Validation Freeze
  └─ Deliverable: Validation contracts defined and tested

Stage 5: Lifecycle Freeze
  └─ Deliverable: F3 — Lifecycle Integrity audit + F4 — Recovery Protocol audit

Stage 6: Dependency Audit
  └─ Deliverable: F5 — Isolation audit + F6 — Dependency audit

Stage 7: Forbidden Ops Audit
  └─ Deliverable: F7 — Forbidden Operations audit

Stage 8: Determinism Audit
  └─ Deliverable: F8 — Determinism audit + F11 — Purity audit

Stage 9: Identity Audit
  └─ Deliverable: F9 — Identity Preservation + F10 — Transparency

Stage 10: Certificate Generation
  └─ Deliverable: F12 — Boundary Audit + F13 — Evolution Audit + F14 —
       Replaceability Audit + Certificate document + Ownership doc update
```

### Post-Freeze

- Freeze certificate saved to `audit/<module>_freeze_certificate.md`
- Ownership document updated with changelog entry
- Changelog dates use actual verification date
- Certificate includes: version info, audit results, architecture status, decision chain diagram

### ADR Integration

Each freeze cycle SHOULD produce an **Architecture Decision Record (ADR)** alongside the freeze certificate, following this template:

```markdown
# ADR-<phase>-<seq>: Freeze <Module> — <scope>

**Context**:
Why is this module being frozen now? What problem does the freeze solve?
(e.g., "Runtime must not acquire narrative decision capability" / "Boundaries must be established before Knowledge Plane is implemented")

**Decision**:
Which boundaries are frozen? Which operations are forbidden?
What ownership is asserted? What is explicitly NOT frozen?

**Alternatives Considered**:
- Why not a looser boundary?
- Why not delay freeze until feature X is ready?
- Why not merge without freeze?

**Consequences**:
- What can no longer be changed without a new freeze cycle?
- What future capabilities are constrained by this freeze?
- Which layers must adapt if this freeze is ever lifted?

**Verification**:
- AFP dimensions certified: F1–F14
- Regression: <N>/<N> ✅
- Audit: <N>/<N> PASS
```

**ADR registration**: ADRs are stored at `docs/adr/ADR-<phase>-<seq>.md` and registered in `docs/adr/README.md`.

### Rationale

ADR integration closes the loop:

| Without ADR | With ADR |
|-------------|----------|
| Future engineers see *what* was frozen | They also see *why* and *what alternatives* were rejected |
| Freeze is technical enforcement | Freeze becomes an auditable governance decision |
| Hard to revisit past decisions | Each freeze has a traceable decision chain |
| New team members need oral history | New team members read ADRs |

---

## Certificate Template

```markdown
# <Module> Freeze Certificate

> **Frozen**: <YYYY-MM-DD>
> **Verified By**: <entity> — <audit reference>
> **Prerequisite**: <prerequisite phases>

## Audit Results

| Dimension | Status | Checks Passed |
|-----------|:------:|:-------------:|
| F1 — ABI Completeness | ✅ PASS | <N> |
| F2 — Ownership Compliance | ✅ PASS | <N> |
| F3 — Lifecycle Integrity | ✅ PASS | <N> |
| ... | ... | ... |
| F14 — Replaceability Audit | ✅ PASS | <N> |
| **TOTAL** | **✅ <N>/14** | **<N>** |

## Architecture Status

- All F1–F14 checks PASS
- Full regression: <N>/<N> ✅
- Phase decision chain: <diagram>
```

---

## Applying AFP to OCOS Phases

| Phase | Module | F1–F12 | F13 | F14 | Certificate |
|-------|--------|:------:|:---:|:---:|:-----------:|
| Phase15 | Runtime | ✅ | ✅* | ✅* | ✅ `audit/phase15.5_runtime_freeze_certificate.md` |

> *F13 and F14 are defined after Phase15's initial certification. Existing frozen modules should be retro-audited for F13/F14 as part of the next applicable freeze cycle.

### Phase16 (Knowledge Plane) — Recommended Sequence

Phase15 demonstrated that **Ownership is more important than implementation**. For Phase16, the starting point is even more fundamental: before frozen Ownership, the **atomic model of knowledge** must be established.

#### Step 0: Knowledge Abstraction Model

The first deliverable of Phase16 is not an Ownership document — it is **KNOWLEDGE_MODEL.md** (or KNOWLEDGE_ABSTRACTION.md), answering three questions:

1. **What are the atomic objects of the Knowledge Plane?**
   - Evidence, Pattern, Principle, Registry, Policy, etc.

2. **What one-directional elevation relationships are permitted between them?**
   ```
   Observation
        ↓
   Evidence
        ↓
   Pattern
        ↓
   Principle
        ↓
   Policy  (for Control Plane consumption)
   ```

3. **Which relationships are absolutely forbidden?**
   - (e.g., Principle must not reverse-modify Evidence)
   - (e.g., Pattern must not bypass Evidence to create Policies)
   - (e.g., Registry must not be owned by a runtime entity)

Once the abstraction layer is frozen, the remaining sequence follows the established pattern:

```
Knowledge Abstraction Model  ← STEP 0: freeze the atomic units and their allowed relationships
    ↓
Knowledge Ownership          ← who owns what (Registry owns storage, which layer owns each type)
    ↓
Knowledge ABI                ← types, protocols, exported constants per atomic unit
    ↓
Knowledge Lifecycle          ← Registry lifecycle states, Pattern maturity stages
    ↓
Knowledge Validation         ← pre/post conditions for cross-layer elevation operations
    ↓
Knowledge Evolution          ← F13 — what capabilities could cause drift in the abstraction
    ↓
Knowledge Freeze             ← AFP Stage 10 + ADR
```

This prevents the Knowledge Plane from decomposing into an unauditable god object: if the abstraction hierarchy is fixed first, every subsequent design decision — Ownership, ABI, Lifecycle, Validation — is a refinement of that frozen model, not an ad-hoc invention.

---

## Appendix: Key Principles

1. **A freeze is a boundary lock**, not a feature-complete marker.
2. **Ownership Matrix is the source of truth** for what a module can and cannot do.
3. **Forbidden operations define a module's character** more than allowed operations.
4. **Decision chains must never be bypassable** — all execution flows through the established chain.
5. **Replaceability is the ultimate test of interface quality** — if you can't swap the implementation, the interface is too porous.
6. **Evolution constraints prevent gradual drift** — every new capability must be auditable against freeze boundaries.
7. **Each layer has exactly one primary responsibility** — a module that does two things is two modules.
8. **The certificate proves the freeze at a point in time** — it does not guarantee future compliance; re-audits are required when boundaries change.
