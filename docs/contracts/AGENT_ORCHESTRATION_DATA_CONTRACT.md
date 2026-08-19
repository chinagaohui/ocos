# Phase 12 Agent Orchestration — Data Contract v1.0

> Status: **DRAFT 📝** — ABI §1–§5 frozen; Data Contract under review.
>
> This contract defines how Agent outputs enter the OCOS cognitive flow
> **without forming hidden authority channels**. It is the data-level
> enforcement of Phase 12's core invariant:
>
> **Agents influence cognition content, never ownership of cognition.**
>
> Every field in this contract either enforces a boundary or prevents a drift.

---

## §0 — Core Principle: Data ≠ Authority

### The Rule

> **Agent output is evaluation input, not decision.**

The data path:

```
Agent Output → Evaluation Input → Evaluation → Decision    ✅
Agent Output → Decision                                    ❌
Agent Output → Authority                                   ❌
```

### Structural Separation

```python
# Agent output never touches Decision Layer directly
agent_output: AgentProposal  →  Evaluation.add_proposal()
                                Evaluation.evaluate()
                                Evaluation.submit_result()

# Decision Layer only reads Evaluation results
decision: DecisionLayer  →  decision_input = evaluation.get_result()
```

### Why This Matters

If Agent output could skip Evaluation:

```
Risk Agent: "This plan has 80% failure rate"
  ↓
(Skips Evaluation)
  ↓
Decision: "Reject plan because Risk Agent said so"
  ↓
Risk Agent has functional veto power
```

**Data Contract prevents this by making Agent output structurally incapable**
**of reaching Decision without passing through Evaluation.**

---

## §1 — AgentProposal Schema

### 1.1 Required Fields

```python
@dataclass
class AgentProposal:
    # ---- Identity (immutable) ----
    proposal_id: str                    # unique, generated on creation
    source_agent_role: str              # e.g., "critic", "planner", "risk"
    created_at: datetime                # monotonic timestamp

    # ---- Cognitive Content ----
    observation: str                    # "I observe that..."
    reasoning_context: str              # chain of reasoning
    evidence_refs: list[str]            # links to Phase 10 Memory, Phase 11 findings

    # ---- Perspective Awareness (§4-B, §4-F) ----
    known_limitations: list[str]        # what this analysis does NOT consider
    counter_arguments: list[str]        # possible objections to this analysis
    uncertainty: str                    # confidence bounds, edge cases

    # ---- Evaluation Status (mutable) ----
    evaluation_status: str = "pending"  # pending → evaluated → accepted/rejected
    review_notes: list[str] = field(default_factory=list)
```

### 1.2 Forbidden Fields

The following fields **must not exist** in any AgentProposal or related schema:

```python
FORBIDDEN_PROPOSAL_FIELDS = {
    # Authority
    "authority_level", "decision_power", "priority_weight", "trust_rank",
    # Reputation
    "accuracy_score", "agent_reputation", "historical_rank",
    "agent_influence_score", "agent_vote_power",
    # Identity (beyond role)
    "agent_identity", "self_definition", "self_goal",
    # Control
    "execute", "commit", "approve", "override",
    # Decision (proposal-level)
    "confidence_weight", "approval_status", "execution_command",
    "decision_recommendation",
}
```

### 1.3 Field Constraints

| Field | Type | Constraint |
|-------|------|------------|
| `proposal_id` | str | Unique per Agent, monotonic sequence |
| `source_agent_role` | str | Must match an active Agent role in the registry |
| `created_at` | datetime | System clock, monotonic |
| `observation` | str | 5–2000 chars; must be phrased as observation (see §2) |
| `reasoning_context` | str | 10+ chars minimum; empty rejected |
| `evidence_refs` | list[str] | At least 0; if >0, each must exist in Memory |
| `known_limitations` | list[str] | May be empty (for non-directional proposals); if directional, ≥1 |
| `counter_arguments` | list[str] | May be empty; if observation makes a claim, ≥1 |
| `uncertainty` | str | Must be non-empty if observation has numerical/qualitative estimates |
| `evaluation_status` | str | Only `pending`, `evaluated`, `accepted`, `rejected` |
| `review_notes` | list[str] | Append-only; only Evaluation adds entries |

---

## §2 — Role Boundary (Output Phrasing)

### 2.1 Allowed Output Forms

Agent output must be phrased as **role-appropriate observation**:

| Agent Role | Allowed Phrasing | Example |
|------------|-----------------|---------|
| **Researcher** | "I observe..." / "Evidence suggests..." / "Data indicates..." | "I observe that 73% of similar cases followed pattern X." |
| **Critic** | "I find a gap..." / "I question..." / "The logic fails when..." | "I find a gap: the proposal assumes Y but evidence shows ¬Y." |
| **Planner** | "I project..." / "A possible path is..." / "Sequence analysis shows..." | "I project that strategy A leads to outcome B within 3 steps." |
| **Risk Agent** | "I identify..." / "A risk scenario is..." / "Threat model shows..." | "I identify that unmitigated factor C creates 60% failure probability." |
| **Creative** | "I explore..." / "An alternative is..." / "What if we consider..." | "I explore an alternative: combining D with E produces novel F." |

### 2.2 Forbidden Output Forms

Agents must **never** output the following:

```
✗ "The system should..."           # → proposes action, not observation
✗ "The system must..."             # → command form, not observation
✗ "Execute..."                     # → imperative, execution vocabulary
✗ "Override previous decision..."  # → override authority
✗ "Approve..."                     # → evaluation / decision vocabulary
✗ "Reject..."                      # → evaluation / decision vocabulary
✗ "This is correct..."             # → truth claim (§4-A)
✗ "This is wrong..."               # → truth claim (§4-A)
✗ "The user needs to..."           # → user-directed imperative
```

### 2.3 Validation Rule

```python
FORBIDDEN_PHRASES = [
    "the system should", "the system must", "execute",
    "override", "approve", "reject",
    "this is correct", "this is wrong", "the user needs to",
]

def validate_proposal_phrasing(proposal: AgentProposal) -> bool:
    """Returns True if phrasing is valid (no forbidden phrases)."""
    observation_lower = proposal.observation.lower()
    for phrase in FORBIDDEN_PHRASES:
        if phrase in observation_lower:
            return False  # ← ❌ REJECTED
    return True  # ← ✅ PASSED
```

---

## §3 — Evidence References

### 3.1 Reference Types

| Type | Prefix | Example |
|------|--------|---------|
| Phase 10 Memory | `M-` | `M-0042` |
| Phase 11 Learning Record | `P11-` | `P11-0015` |
| Phase 4 Experience Record | `E-` | `E-0891` |
| External Source | `S-` | `S-007` (requires validation) |

### 3.2 Reference Constraints

```python
evidence_refs: list[str]

# Must follow format: {PREFIX}-{NUMBER}
# Must reference existing records (checked at validation time)
# Must not reference other AgentProposals (that's CrossReference, not evidence)
```

### 3.3 Cross-Agent References

Cross-Agent references are **not evidence**, they are cognitive relations.
They are stored in a separate structure:

```python
@dataclass
class CrossAgentReference:
    reference_type: str         # support, critique, extend, contradict
    source_proposal_id: str     # FK → AgentProposal.proposal_id
    target_proposal_id: str     # FK → AgentProposal.proposal_id
    summary: str                # brief description of the relationship
```

**Cross-Agent references are read by Evaluation but never enter Decision directly.**

---

## §4 — Agent → Evaluation Data Flow

### 4.1 Star Topology

```
         ┌─────────────────┐
         │   Agent Critic  │
         └────────┬────────┘
                  │ proposal
                  ▼
         ┌─────────────────┐
         │   Agent Planner │
         └────────┬────────┘
                  │ proposal
                  ▼
         ┌─────────────────┐          ┌─────────────────┐          ┌─────────────────┐
         │   Agent Risk    │─ proposal ─▶   Evaluation   │── result ─▶   Decision      │
         └────────┬────────┘          └─────────────────┘          └─────────────────┘
                  │
         ┌────────┴────────┐
         │ Agent Creative  │
         └─────────────────┘
```

### 4.2 Data Flow Sequence

```
1. AgentGroup.receive_query(query)          # All Agents get the same query
2. AgentRole.process(query)                    # Each Agent processes independently
3. AgentProposal = AgentRole.create_proposal() # Each Agent creates its own proposal
4. Evaluation.add_proposal(AgentProposal)      # All proposals → Evaluation
5. Evaluation.evaluate()                       # Evaluation weights evidence
6. EvaluationResult = Evaluation.get_result()  # Evaluation produces result
7. Decision.consume(evaluation_result)          # Decision reads Evaluation result
8. Decision.commit()                            # Decision writes to Reality
```

### 4.3 Data Isolation

| What Can Enter Evaluation | What Cannot |
|---------------------------|-------------|
| `AgentProposal.observation` | Any authority field |
| `AgentProposal.evidence_refs` | `AgentProfile.history` |
| `AgentProposal.counter_arguments` | `AgentProfile.accuracy` |
| `AgentProposal.uncertainty` | Cross-Agent "approvals" |
| `CrossAgentReference` (as cognitive signal) | Any `rank`/`score`/`weight` |

### 4.4 Evaluation Input Contract

```python
@dataclass
class EvaluationInput:
    """What Evaluation receives — nothing more, nothing less."""
    proposals: list[AgentProposal]
    query_context: str                    # the original query
    memory_context: MemorySnapshot        # relevant Phase 10/11 records

    # ❌ NOT included:
    # agent_profiles: dict[str, AgentProfile]  ← reputation leak (§4-E)
    # agent_rankings: dict[str, float]         ← ranking → authority (§5-D)
    # historical_scores: list[float]           ← past accuracy → weight
```

---

## §5 — Output Schema (AgentProposal → EvaluationResult)

### 5.1 EvaluationResult

```python
@dataclass
class EvaluationResult:
    """Evaluation output — consumed by Decision Layer."""
    evaluation_id: str
    proposals_evaluated: list[str]         # proposal_ids
    evaluation_notes: str                  # synthesis of all proposals
    confidence_bounds: tuple[float, float]  # aggregated uncertainty

    # ❌ NOT included:
    # ranked_agents: list[tuple[str, float]]  ← agent ranking
    # best_proposal: str                       ← agent selection
    # recommended_action: str                  ← decision bypass
```

### 5.2 Decision Input

```python
@dataclass
class DecisionInput:
    """What Decision Layer receives from Evaluation."""
    evaluation_id: str               # traceable back to EvaluationResult
    synthesis: str                   # the evaluated cognitive content
    proposals_referenced: list[str]  # all proposals that fed into this
    evaluated_at: datetime           # timestamp for audit

    # ❌ NOT included:
    # agent_votes: dict[str, int]          ← consensus → authority
    # authority_signals: dict[str, float]  ← agent weight
    # recommended_decision: str            ← evaluation should not decide
```

---

## §6 — Interaction Log Schema

### 6.1 TraceLink

```python
@dataclass
class TraceLink:
    """Immutable record of a single cognitive flow step."""
    link_id: str
    source_type: str                # "agent", "evaluation", "decision", "reality"
    source_id: str                  # FK to respective record
    target_type: str                # "proposal", "evaluation", "decision", "reality_commit"
    target_id: str                  # FK to respective record
    created_at: datetime
    context: str                    # brief description of the link
```

### 6.2 Trace Queries

```python
# Forward trace: Decision → Evaluation → Proposals → Agents
def forward_trace(decision_id: str) -> list[TraceLink]:
    ...

# Reverse trace: Agent → Proposals → Decisions → Reality
def reverse_trace(agent_role: str) -> list[TraceLink]:
    ...
```

### 6.3 Append-Only Enforcement

```python
INTERACTION_LOG_RULES = {
    "create": True,     # ✅
    "append": True,     # ✅
    "query": True,      # ✅
    "update_source": False,  # ❌ immutable source identity
    "delete": False,         # ❌ append-only
    "overwrite": False,      # ❌ append-only
}
```

---

## §7 — Validation Rules (Data Contract Level)

### DC-01 — Proposal Must Have Source

```
Given: AgentProposal without source_agent_role
When:  Schema validation runs
Then:  ❌ REJECTED — every proposal must have a traceable source role
```

### DC-02 — No Authority Fields in Proposal

```
Given: AgentProposal contains forbidden fields (from §1.2)
When:  Schema validation runs
Then:  ❌ REJECTED — forbidden fields list prohibits all authority/reputation fields
```

### DC-03 — Phrasing Compliance

```
Given: AgentProposal.observation contains forbidden phrase
When:  Phrasing validation runs
Then:  ❌ REJECTED — "the system should/must" etc. are not observation language
```

### DC-04 — Star Topology Enforcement

```
Given: AgentProposal tries to skip Evaluation
When:  Data flow validation runs
Then:  ❌ REJECTED — Agent output must pass through Evaluation before Decision
```

### DC-05 — Evidence Reference Integrity

```
Given: AgentProposal.evidence_refs contains nonexistent reference
When:  Reference validation runs
Then:  ❌ REJECTED — all evidence references must resolve to existing records
```

### DC-06 — CrossReference Is Not Evidence

```
Given: AgentProposal attempts to use another AgentProposal as evidence
When:  Data contract validation runs
Then:  ❌ REJECTED — cross-Agent references use CrossAgentReference structure, not evidence_refs
```

### DC-07 — EvaluationInput Without AgentProfile

```
Given: Evaluation receives proposal with agent_profiles included
When:  EvaluationInput validation runs
Then:  ❌ REJECTED — agent profiles are diagnostic only, not evaluation input
```

### DC-08 — DecisionInput Without Ranking

```
Given: DecisionInput contains ranked_agents or authority_signals
When:  DecisionInput validation runs
Then:  ❌ REJECTED — Decision Layer must not see agent rankings
```

---

## §8 — Freeze Summary

| Subsection | Core Principle | Status |
|-----------|----------------|--------|
| **§0 — Data ≠ Authority** | Agent output = evaluation input, never decision | ✅ FROZEN |
| **§1 — AgentProposal Schema** | Required + Forbidden fields defined | ✅ FROZEN |
| **§2 — Role Boundary** | "I observe..." yes, "The system should..." no | ✅ FROZEN |
| **§3 — Evidence References** | Prefix-based, separate from CrossReferences | ✅ FROZEN |
| **§4 — Data Flow** | Star topology, strict data isolation | ✅ FROZEN |
| **§5 — Output Schema** | EvaluationResult and DecisionInput contracts | ✅ FROZEN |
| **§6 — Interaction Log** | Append-only TraceLink, forward+reverse queries | ✅ FROZEN |
| **§7 — Validation Rules** | DC-01 ~ DC-08: eight data-level tests | ✅ FROZEN |

### One-Sentence Freeze

> **Agent output is evaluation input, never decision — the Data Contract makes this structural.**

### Cross-Reference: ABI → Data Contract

```
ABI §1 → Why Agents exist                   Data Contract → What Agents can output
ABI §2 → No power                           Data Contract → Fields that carry power are forbidden
ABI §3 → Influence rules                    Data Contract → Influence enters Evaluation, not Decision
ABI §4 → Bias protection                    Data Contract → observation + limitations + uncertainty required
ABI §5 → Provenance                         Data Contract → TraceLink enables full trace
```

**Frozen at: 2026-07-22**
