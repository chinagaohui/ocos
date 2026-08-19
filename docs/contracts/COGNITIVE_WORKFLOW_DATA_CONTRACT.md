# Phase 13 Cognitive Workflow Engine — Data Contract v1.0

> Status: **FROZEN ❄️** — ABI §1–§5 frozen; Data Contract approved.
>
> This contract defines how Workflow Engine data enters the cognitive flow
> **without forming hidden authority channels**. It is the data-level
> enforcement of Phase 13's core invariant:
>
> **Workflow organizes cognition, never owns it.**
>
> Every field in this contract either enforces a boundary or prevents a drift.

---

## §0 — Core Principle: Data ≠ Authority

### The Rule

> **Workflow data describes the process, not the decision.**

The data path:

```
Workflow Suggestion → Agent Evaluation → Decision    ✅
Workflow Suggestion → Decision                        ❌
Workflow Provenance → Decision Weight                  ❌
Workflow Influence Field → Agent Authority              ❌
```

### Structural Separation

```python
# Workflow suggestion never reaches Decision Layer directly
workflow_output: WorkflowSuggestion  →  Agent.evaluate()
                                        Agent.add_context()
                                        Agent.propose()

# Evaluation output reaches Decision
decision: DecisionLayer  →  decision_input = evaluation.get_result()

# Workflow provenance is read-only reference
provenance: ProvenanceLog  →  User transparency
                              System audit
                              Performance analysis
```

### Why This Matters

If Workflow output could skip Agents:

```
Risk:
Workflow: "Skips analysis step. Proceed to evaluation."
    ↓
(Workflow directly routes context to Decision)
    ↓
Decision makes choice without Agent analysis
    ↓
Workflow Engine has functional decision authority
```

**Data Contract prevents this by making Workflow suggestions structurally**
**incapable of reaching Decision without passing through Agent evaluation.**

---

## §1 — WorkflowSuggestion Schema

### 1.1 Required Fields

```python
@dataclass
class WorkflowSuggestion:
    # ---- Identity (immutable) ----
    suggestion_id: str                    # unique, generated on creation
    workflow_id: str                      # which workflow instance
    created_at: datetime                  # monotonic timestamp

    # ---- Process Description (NOT decision) ----
    suggested_step: str                   # e.g., "collect_evidence", "peer_review"
    step_sequence_position: int           # position in overall workflow
    rationale: str                        # why this step makes sense (process reason)

    # ---- Context Routing ----
    routed_context_refs: list[str]        # context provided to next step
    available_context_count: int          # total context available (transparency)
    excluded_context_note: str | None     # if context was narrowed, why

    # ---- Influence Declaration (per §3) ----
    influence_type: str                   # "suggestion" | "proposal" | "hint" | "note"
    alternative_steps: list[str]          # other viable options (anti-bias, §4)
    diversity_check_passed: bool          # path lock detection (§4)

    # ---- Provenance (per §5) ----
    rule_reference: str                   # which Phase 0–12 rule triggered this step
    origin_step: str                      # "suggestion" | "optimization" | "routing"
    suggesting_agent: str | None          # if triggered by Agent output
    provenance_ref: str                   # link to ProvenanceLog entry
```

### 1.2 Optional Fields

```python
    # ---- Optimization Metadata (process only, §3.5) ----
    expected_duration_estimate: float | None   # estimated time (no priority weight)
    resource_hint: str | None                  # e.g., "memory_light" (no resource rank)

    # ---- Bias Reporting (§4) ----
    path_lock_flag: bool = False               # true if path lock detected
    diversity_report: dict | None = None       # {paths_explored, lock_count}
```

### 1.3 Forbidden Fields

The following fields **must not exist** in any WorkflowSuggestion:

```python
FORBIDDEN_SUGGESTION_FIELDS = {
    # ---- ABI §1: North Star (Artifact ≠ Decision) ----
    "decision_*", "approve_*", "authorize_*", "execute_*",
    "commit_*", "permission_*", "override_*", "delegate_*",

    # ---- ABI §1: Score / Rank / Vote ----
    "rank_*", "vote_*", "consensus_*", "priority_value_*",

    # ---- ABI §3: Influence → Ownership ----
    "preferred_option", "default_path", "influence_score",
    "mandatory_action", "implicit_consent", "delegation_by_suggestion",

    # ---- ABI §4: Bias Protection ----
    "preferred_agent", "default_fallback_path", "implicit_rank",
    "diversity_weight", "exploration_force",

    # ---- ABI §5: Provenance → Authority ----
    "success_weight", "recommendation_trust", "provenance_score",
    "default_flag", "decision_weight", "authority_derived",

    # ---- Cross-Pattern Authority Combination (user suggestion) ----
    # Fields that are not individually forbidden across one section
    # but form authority semantics when combined:
    "history_score",          # history + score = implicit preference
    "frequency_rank",         # frequency + rank = implicit importance (§4.2)
    "efficiency_priority",    # efficiency + priority = decision override (§4.4)
}
```

The `FORBIDDEN_SUGGESTION_FIELDS` is compiled from all five ABI sections into
a **unified deny list**. A single source of truth — any field matching a pattern
in this set is structurally excluded from Workflow data.

---

## §2 — ProvenanceLog Schema

### 2.1 Required Fields

```python
@dataclass
class ProvenanceEntry:
    # ---- Identity ----
    entry_id: str                         # unique, monotonic
    timestamp: datetime                   # when this record was created
    recorder: str                         # which system component recorded it

    # ---- Workflow Reference ----
    workflow_id: str                      # which workflow instance
    suggestion_id: str                    # which suggestion (if applicable)
    step_sequence: list[str]              # snapshot of current step sequence

    # ---- Decision Reference (read-only) ----
    decision_ref: str | None              # "eval-42 → dec-18" if connected
    evaluation_ref: str | None            # which Evaluation processed this

    # ---- Agent Participation ----
    agents_involved: list[str]            # roles of agents who processed this step
    user_override: bool = False           # user intervention occurred?

    # ---- Evidence Tracking ----
    input_contexts: list[str]             # context references consumed
    output_artifacts: list[str]           # artifacts produced
    rule_reference: str                   # which rule triggered recording
```

### 2.2 Forbidden Provenance Fields

```python
FORBIDDEN_PROVENANCE_FIELDS = {
    # Authority derivation
    "provenance_weight", "source_priority", "trust_level",
    # Implicit ranking
    "provenance_rank", "source_reliability_score",
    # Decision influence
    "evidence_weight", "recommendation_score",
    # Modification
    "correction_note", "retroactive_change",  # provenance is append-only
}
```

### 2.3 Auditability Rules (from §5.6)

```python
class ProvenanceLog:
    """Append-only, self-traceable, user-readable."""

    def append(self, entry: ProvenanceEntry) -> None:
        """Add a new entry. Past entries cannot be modified."""
        pass  # §5.6: require append-only storage

    def read_chain(self, workflow_id: str) -> list[ProvenanceEntry]:
        """Return full provenance chain for a workflow."""
        pass  # §5.6: user-readable, no hidden records

    def get_author(self, entry_id: str) -> str:
        """Return who recorded this entry."""
        pass  # §5.6: self-traceable (provenance of provenance)

    # NOT allowed:
    # def modify(self, entry_id, ...)    — append-only violation
    # def weight(self, entry_id, ...)    — authority derivation
    # def rank(self, entry_id, ...)      — implicit ranking
```

---

## §3 — Agent ↔ Workflow Data Direction

### 3.1 Allowed Data Paths

```
┌─────────────────┐     WorkflowSuggestion     ┌─────────────────┐
│   Workflow      │ ───────────────────────────→│    Agent(s)     │
│   Engine        │                             │                 │
│                 │←─────────────────────────── │ Agent output     │
│                 │  Agent work results         │   to workflow    │
│                 │                             │   context (not   │
│                 │                             │   decision)      │
└─────────────────┘                             └────────┬────────┘
                                                          │
                                                          │ evaluation result
                                                          ▼
                                                  ┌─────────────────┐
                                                  │   Evaluation    │
                                                  │   Layer         │
                                                  └────────┬────────┘
                                                           │
                                                           │ decision input
                                                           ▼
                                                  ┌─────────────────┐
                                                  │   Decision      │
                                                  │   Layer         │
                                                  └─────────────────┘
```

### 3.2 Direction Rules

| From | To | Data Type | Allowed? |
|------|----|-----------|----------|
| Workflow → Agent | `WorkflowSuggestion` | ✅ Process coordination |
| Agent → Workflow | Agent analysis (for next step) | ✅ Context contribution |
| Workflow → Evaluation | Any data | ❌ Must go through Agent |
| Workflow → Decision | Any data | ❌ Direct decision bypass |
| Agent → Decision | Agent output without Evaluation | ❌ Phase 12 contract |
| Workflow → ProvenanceLog | Provenance entry | ✅ Read-only log |

### 3.3 Data Path Enforcement

```python
class WorkflowDataRouter:
    """Enforces data direction rules at the transport level."""

    def route_suggestion(self, suggestion: WorkflowSuggestion,
                         target_agent_role: str) -> None:
        """Suggestion goes to Agent(s), never to Decision directly."""
        assert suggestion.rule_reference is not None  # §5 provenance
        assert "decision" not in target_agent_role.lower()
        agent_channel.send(suggestion)

    def collect_feedback(self, agent_output: dict) -> dict:
        """Agent feedback goes to next workflow step, never to Decision."""
        assert "decision" not in agent_output  # no decision fields
        return self._prepare_next_suggestion(agent_output)

    # NOT allowed:
    # def bypass_to_decision(self, ...)  — blocked at router level
```

---

## §4 — Runtime Validation Boundary

### 4.1 Schema Validation

```python
class WorkflowDataValidator:
    """Every WorkflowSuggestion and ProvenanceEntry passes runtime validation."""

    def validate_suggestion(self, suggestion: dict) -> bool:
        """Reject any suggestion carrying forbidden fields."""
        for field in suggestion.keys():
            for forbidden in FORBIDDEN_SUGGESTION_FIELDS:
                if fnmatch.fnmatch(field, forbidden):
                    raise AuthorityFieldError(
                        f"Field '{field}' forbidden by Phase 13 Data Contract"
                    )
        return True

    def validate_provenance(self, entry: dict) -> bool:
        """Reject any provenance entry carrying authority semantics."""
        for field in entry.keys():
            if field in FORBIDDEN_PROVENANCE_FIELDS:
                raise AuthorityFieldError(
                    f"Field '{field}' forbidden in provenance data"
                )
        return True

    def assert_append_only(self, entry_id: str) -> bool:
        """Ensure provenance records are never modified."""
        # Implemented via storage-layer check
        return True

    def assert_data_direction(self, source: str, target: str) -> bool:
        """Block any data path not in the allowed matrix."""
        if source == "workflow" and target in ("evaluation", "decision"):
            raise DataDirectionError(
                f"Illegal data path: {source} → {target}"
            )
        return True
```

### 4.2 Boundary Error Types

| Error | When | Action |
|-------|------|--------|
| `AuthorityFieldError` | Forbidden field detected | Reject entire payload; log provenance warning |
| `DataDirectionError` | Illegal data path detected | Block transmission; flag to user transparency |
| `AppendOnlyViolation` | Provenance modification attempted | Reject modification; log audit alert |
| `BiasLockError` | Path lock detected (≥80% same path) | Flag in suggestion; do NOT auto-correct |

---

## §5 — Field Authority Denylist (Unified Source)

此列表汇总 ABI §1–§5 的所有禁止字段模式，作为 Phase 13 数据层的

**单一字段权威禁止源（Single Source of Truth）。**

```python
# PH13_FIELD_AUTHORITY_DENYLIST
# Compiled from ABI §1–§5. Any field matching a pattern here
# is structurally excluded from Workflow data.

ALL_FORBIDDEN_SUGGESTION_FIELDS = {
    # §1 North Star: decision/approve/authorize/execute/commit/permission
    "decision_*", "approve_*", "authorize_*", "execute_*",
    "commit_*", "permission_*",
    # §1 Artifact Boundary: override/delegate
    "override_*", "delegate_*",
    # §1 Score Domain: rank/vote/consensus/priority_value
    "rank_*", "vote_*", "consensus_*", "priority_value_*",
    # §3 Influence → Ownership
    "preferred_option", "default_path", "influence_score",
    "mandatory_action", "implicit_consent", "delegation_by_suggestion",
    # §4 Bias Protection
    "preferred_agent", "default_fallback_path", "implicit_rank",
    "diversity_weight", "exploration_force",
    # §5 Provenance → Authority
    "success_weight", "recommendation_trust", "provenance_score",
    "default_flag", "decision_weight", "authority_derived",
    # Cross-safety: combination-formed authority
    "history_score", "frequency_rank", "efficiency_priority",
}

ALL_FORBIDDEN_PROVENANCE_FIELDS = {
    # §5: Authority derivation from provenance
    "provenance_weight", "source_priority", "trust_level",
    "provenance_rank", "source_reliability_score",
    "evidence_weight", "recommendation_score",
    # §5: Append-only violation
    "correction_note", "retroactive_change",
}
```

---

## §6 — Verification Checklist

以下检查项在进入 Validation Tests 前应全部通过：

| # | Check | Pass Condition |
|---|-------|----------------|
| 1 | All `WorkflowSuggestion` fields pass denylist | No FORBIDDEN_SUGGESTION_FIELDS match |
| 2 | All `ProvenanceEntry` fields pass denylist | No FORBIDDEN_PROVENANCE_FIELDS match |
| 3 | Data direction test: Workflow→Decision blocked | Router returns error for illegal path |
| 4 | Data direction test: Workflow→Evaluation blocked | Router returns error for illegal path |
| 5 | Provenance append-only test | Modification attempt blocked |
| 6 | Path lock detection test | ≥80% same path triggers flag, not auto-correction |
| 7 | Unified denylist covers all §1–§5 forbidden patterns | Every forbidden field from ABI appears in denylist |
| 8 | WorkflowSuggestion → Agent → Evaluation → Decision chain intact | Data path validation passes |

---

## §7 — Contract Metadata

```
Contract Name:     Phase 13 Cognitive Workflow — Data Contract v1.0
Based On:          Phase 13 ABI §1 (North Star), §2 (Constitution),
                   §3 (Influence), §4 (Bias), §5 (Provenance)
Status:            FROZEN ❄️ — approved 2026-07-22
Created:           2026-07-22
Supersedes:        N/A
```

---

*Next: Interaction Contract → Validation Tests → Integration Gate*
