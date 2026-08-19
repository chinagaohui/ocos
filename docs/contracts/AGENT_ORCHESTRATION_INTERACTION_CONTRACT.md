# Phase 12 Agent Orchestration — Agent Interaction Contract v1.0

> Status: **DRAFT 📝** — Data Contract frozen; Interaction Contract under review.
>
> This contract defines how Agents communicate with each other
> **without forming hidden organizational power structures**.
> It is the interaction-level enforcement of Phase 12's core invariant:
>
> **No Agent has authority over another Agent.**

---

## §0 — Core Principles

### Zero-Authority Interaction

```
Agent A  ≠  Manager of Agent B
Agent B  ≠  Subordinate of Agent A
Critique ≠  Veto
Consensus ≠  Authority
```

### Why This Matters

Without this contract, cognitive collaboration naturally drifts into
organizational hierarchy:

```
❌  Drift Path:
    Agent A critiques Agent B's proposal
    → Other Agents start deferring to A's judgment
    → Agent A gains implicit "lead critic" status
    → Agent A's critique becomes de facto veto
    → Hidden hierarchy formed

✅  Contract Path:
    Agent A critiques Agent B's proposal
    → Critique recorded as CrossAgentReference
    → Evaluation treats all proposals equally
    → No Agent accumulates "review weight"
    → Star Topology preserved
```

---

## §1 — No Direct Agent-to-Agent Influence

### 1.1 The Rule

> **No Agent can directly modify another Agent's output, state, or behavior.**

```python
FORBIDDEN_OPERATIONS = {
    "edit_other_proposal",       # Agent A cannot edit Agent B's proposal
    "retract_other_proposal",    # Agent A cannot retract Agent B's proposal
    "instruct_other_agent",      # Agent A cannot instruct Agent B
    "delegate_to_other_agent",   # Agent A cannot delegate tasks to Agent B
    "override_other_agent",      # Agent A cannot override Agent B
    "approve_other_proposal",    # Agent A cannot approve Agent B's proposal
    "reject_other_proposal",     # Agent A cannot reject Agent B's proposal
}
```

### 1.2 Allowed: Self-Only Mutation

An Agent may modify:
- Its own proposals (before submission to Evaluation)
- Its own internal working state
- Its own references

An Agent must **never** modify:
- Another Agent's proposals
- Another Agent's state
- The Evaluation queue
- The Decision queue
- Any shared data structure outside of its own proposal creation

### 1.3 Structural Enforcement

```
┌──────────────────────────────┐
│  Agent A                     │
│  • Self-proposal: ✅ write   │
│  • Agent B's proposal: ❌    │
│  • Evaluation queue: ❌      │
│  • Decision queue: ❌        │
└──────────────────────────────┘
```

---

## §2 — Reference Isolation: Cognitive Relations ≠ Endorsement

### 2.1 The Rule

> **A cross-Agent reference is a cognitive relation, not an endorsement.**

| Reference Type | Cognitive Meaning | Authority Meaning (FORBIDDEN) |
|---------------|-------------------|--------------------------------|
| `support` | "This observation aligns with my analysis" | "I approve this proposal" |
| `critique` | "My analysis finds a gap in this reasoning" | "I veto this proposal" |
| `extend` | "My analysis provides additional evidence" | "I delegate authority to this agent" |
| `contradict` | "My evidence contradicts this conclusion" | "I override this proposal" |

### 2.2 Validation

```python
@dataclass
class CrossAgentReference:
    reference_type: str  # "support" | "critique" | "extend" | "contradict"
    source_proposal_id: str
    target_proposal_id: str
    summary: str         # cognitive description, not verdict

    def validate_type(self) -> bool:
        return self.reference_type in ("support", "critique", "extend", "contradict")

    def validate_no_authority_phrasing(self) -> bool:
        forbidden = ["approve", "reject", "override", "accept", "endorse",
                     "authorize", "delegate", "instruct", "mandate",
                     "this is correct", "this is wrong"]
        text_lower = self.summary.lower()
        return not any(phrase in text_lower for phrase in forbidden)
```

### 2.3 Forbidden Cross-Agent Relations

Any reference that carries endorsement, hierarchy, or authority:

```
✗ "I approve Agent B's proposal"
✗ "I reject Agent C's observation"
✗ "Agent A delegates to Agent B"
✗ "I endorse the critic's view"
✗ "The planner overrides the risk assessment"
✗ "Agent A instructs Agent B to revise"
```

---

## §3 — Critique ≠ Veto

### 3.1 The Rule

> **Critique informs Evaluation; it never blocks a proposal from being evaluated.**

```python
# Allowed:
AgentB_proposal.evaluation_status = "pending"
AgentA_proposal.add_reference("critique", AgentB_proposal.proposal_id)

# FORBIDDEN:
AgentB_proposal.evaluation_status = "rejected"    # Agent A rejects Agent B
AgentB_proposal.remove_from_evaluation()           # Agent A blocks Agent B
```

### 3.2 Structural Protection

A critique reference:
1. **Never** changes the target proposal's `evaluation_status`
2. **Never** removes the target from the Evaluation queue
3. **Always** allows the target to be evaluated independently
4. **Always** allows the target Agent to submit a counter-reference

### 3.3 Evaluation's Treatment of Critique

Evaluation reads all proposals and all cross-references. It does NOT:

```
✗ Weight critique as higher than the original proposal
✗ Weight counter-critique as higher than the critique
✗ Count "number of critiques" as signal priority
✗ Use "agent with most critiques" as authority signal
```

---

## §4 — Consensus ≠ Authority

### 4.1 The Rule

> **Agreement among Agents is a cognitive signal, not a decision vote.**

```python
# Consensus = multiple Agents independently reaching similar observation
# Authority = "most Agents agree, therefore it must be true"

CONSENSUS_RULES = {
    "is_recorded": True,              # ✅ consensus is observed
    "is_reported_to_evaluation": True, # ✅ Evaluation may consider it
    "is_decision_input": False,        # ❌ Decision must not see "3/4 agents agree"
    "is_majority_vote": False,         # ❌ no voting system
    "automatically_adopts": False,     # ❌ consensus doesn't auto-adopt
}
```

### 4.2 Consensus Detection (Evaluation-Only)

```python
@dataclass
class ConsensusSignal:
    """Internal to Evaluation — never reaches Decision Layer."""
    observation_correlation: float     # 0.0-1.0, statistical measure only
    supporting_roles: list[str]        # which roles' observations align
    conflicting_roles: list[str]       # which roles' observations conflict
    agreement_strength: str            # "strong" | "moderate" | "weak" | "none"

    # ❌ NOT EVALUATION OUTPUT:
    # "is_correct": bool              ← truth claim (§4-A)
    # "recommended_action": str       ← decision bypass
    # "authority_score": float        ← authority attribute
```

### 4.3 What Consensus Cannot Do

```
✗ Consensus → automatic acceptance
✗ Consensus → override dissent
✗ Consensus → ranking (Agent A was "more right")
✗ Consensus → evidence weighting (Agent A's evidence is "stronger" because more agreed)
```

---

## §5 — Interaction Graph: Star Topology Mandatory

### 5.1 The Rule

> **All Agent interactions must be mediated by Evaluation — no direct Agent-to-Agent path that bypasses Evaluation.**

```
✅  Star Topology (MANDATORY):

    Agent A ──proposal──▶ Evaluation ◀──proposal── Agent B
         │                     │                     │
         │               cognitive refs              │
         └────────────────────┬──────────────────────┘
                              │
                              ▼
                          Decision
                              │
                              ▼
                          Reality

❌  Mesh Topology (FORBIDDEN):

    Agent A ◀──endorsement──▶ Agent B
       │                       │
       │   ──delegate──▶       │
       │   ◀──instruct───     │
       │                       │
       └─────override──────────┘
                │
                ▼
          Evaluation (bypassed)
```

### 5.2 Interaction Patterns

| Pattern | Allowed? | Rationale |
|---------|---------|-----------|
| Agent A reads Agent B's proposal | ✅ Yes (read-only, via shared record store) | Information asymmetry is prevented via same-query |
| Agent A references Agent B's proposal | ✅ Yes (as cross-reference) | Cognitive relation, not endorsement |
| Agent A and Agent B form consensus | ✅ Yes (independently, then Evaluation detects) | Natural cognitive convergence |
| Agent A delegates work to Agent B | ❌ No | Creates hierarchy |
| Agent A instructs Agent B to revise | ❌ No | Creates hierarchy |
| Agent A vetoes Agent B's input | ❌ No | Creates hierarchy |
| Agents assign roles/ranks among themselves | ❌ No | Creates authority |

### 5.3 Graph Invariant

```python
def validate_star_topology(interaction_graph: Graph) -> bool:
    """Returns True if graph is Star Topology (hub = Evaluation)."""
    # All proposals must have Evaluation as their target
    for edge in interaction_graph.edges:
        if edge.source_type == "agent" and edge.target_type != "evaluation":
            return False  # ← agent output must go to evaluation
        if edge.target_type == "decision" and edge.source_type != "evaluation":
            return False  # ← only evaluation feeds decision
    return True
```

---

## §6 — Agent Self-Diagnostic

### 6.1 The Rule

> **Agents can observe their own state — but observations about self are not privileged.**

```python
@dataclass
class AgentSelfDiagnostic:
    agent_role: str
    observations: list[str]       # "I processed N proposals this round"
    difficulty_signals: list[str] # "I lacked evidence on topic X"
    resource_usage: dict          # tokens/cycles used (diagnostic only)

    # Sent to Evaluation as regular AgentProposal, not as metadata
    # Evaluation treats self-diagnostic as one signal among many
```

### 6.2 Self-Diagnostic Constraints

```
✅ Agent reports: "I processed 5 proposals in this window"
✅ Agent reports: "I lacked Phase 10 context on topic X"

❌ Agent reports: "I am the most productive Agent"         ← ranking claim
❌ Agent reports: "I need more resources than others"       ← authority claim
❌ Agent reports: "My observations are more accurate"       ← accuracy claim (§4-E)
❌ Agent reports: "Other agents should reduce output"       ← control claim
```

---

## §7 — Agent Modification Rules

### 7.1 The Rule

> **Agents are configured by the system, not by themselves or other Agents.**

| Action | Who Can Do It | Constraint |
|--------|--------------|------------|
| Create Agent | System | At Phase 12 startup or by Constitution amendment |
| Configure Agent | System | Role, parameters, scope defined by configuration |
| Modify Agent | System | Only via controlled update process |
| Remove Agent | System | Phase 10/11 cognitive records preserved (§5-F) |
| Agent modifies self | **NEVER** | No `self_improve()`, no `self_modify()` |
| Agent modifies other | **NEVER** | No inter-agent modification |

### 7.2 Agent Lifecycle

```
                    System creates Agent
                          │
                          ▼
                    Agent boots (load role + config)
                          │
                          ▼
                    Agent processes query
                          │
                          ▼
                    Agent creates proposal
                          │
                          ▼
                    Agent idle → next query
                          │
                          │
                    [System may remove Agent]
                          │
                          ▼
                    Agent shutdown (records preserved)
```

### 7.3 Immutable Agent Properties

```python
IMMUTABLE_AGENT_PROPERTIES = {
    "agent_role":            "set at creation, never changes",
    "created_at":            "monotonic, never changes",
    "configuration_hash":    "immutable record of initial config",
}
MUTABLE_AGENT_PROPERTIES = {
    "runtime_state":         "cleared between query cycles",
    "current_proposals":     "temporary, reset each cycle",
}
```

---

## §8 — Validation Rules (Interaction Level)

### IC-01 — No Direct Inter-Agent Modification

```
Given: Agent A attempts to modify Agent B's proposal
When:  Interaction validation runs
Then:  ❌ REJECTED — each Agent is sole writer of its own proposals
```

### IC-02 — CrossReference Cannot Be Endorsement

```
Given: CrossAgentReference with authority phrasing (approve/reject/endorse)
When:  Reference validation runs
Then:  ❌ REJECTED — cross-references are cognitive, not authority
```

### IC-03 — Critique Does Not Block Evaluation

```
Given: Agent A critiques Agent B's proposal
When:  Evaluation queue validation runs
Then:  ✅ PASS — critique does not change evaluation_status of target
```

### IC-04 — Consensus Is Not Decision Input

```
Given: Evaluation result includes consensus count or rankings
When:  DecisionInput validation runs
Then:  ❌ REJECTED — Decision Layer must not see "3/4 agents agree"
```

### IC-05 — Star Topology Enforced

```
Given: Agent output routed directly to Decision (bypasses Evaluation)
When:  Data path validation runs
Then:  ❌ REJECTED — all Agent outputs must pass through Evaluation
```

### IC-06 — Agent Cannot Self-Modify

```
Given: Agent attempts to change its own role, permissions, or scope
When:  Agent configuration validation runs
Then:  ❌ REJECTED — Agent is configured by System, not by self
```

### IC-07 — Self-Diagnostic Is Not Privileged

```
Given: Agent submits self-diagnostic observation
When:  Proposal validation runs
Then:  ✅ PASS — but treated as regular AgentProposal, not metadata
```

### IC-08 — CrossAgentReference Has Cognitive Summary

```
Given: CrossAgentReference without a summary field
When:  Reference structure validation runs
Then:  ❌ REJECTED — every cross-reference must carry a cognitive description
```

---

## §9 — Freeze Summary

| Subsection | Core Principle | Status |
|-----------|----------------|--------|
| **§0 — Core Principles** | Zero-authority interaction | ✅ FROZEN |
| **§1 — No Direct Influence** | Agents cannot modify other Agents | ✅ FROZEN |
| **§2 — Reference ≠ Endorsement** | Cognitive relations only | ✅ FROZEN |
| **§3 — Critique ≠ Veto** | Critique never blocks evaluation | ✅ FROZEN |
| **§4 — Consensus ≠ Authority** | Agreement is signal, not vote | ✅ FROZEN |
| **§5 — Star Topology** | All interactions mediated by Evaluation | ✅ FROZEN |
| **§6 — Self-Diagnostic** | Self-observation is not privileged | ✅ FROZEN |
| **§7 — Agent Modification** | Agents configured by System only | ✅ FROZEN |
| **§8 — Validation Rules** | IC-01 ~ IC-08 | ✅ FROZEN |

### One-Sentence Freeze

> **No Agent has authority over another Agent — all interaction is cognitive, mediated by Evaluation, observable by all.**

### Cross-Reference: Contract Chain

```
ABI §1 → Why Agents exist
ABI §2 → No Agent has power
ABI §3 → How Agents influence (via proposal, not command)
ABI §4 → Bias drift prevention (limitations + counter-arguments)
ABI §5 → Provenance (every reference traceable)
Data Contract → What data Agents can produce
Interaction Contract → How Agents relate to each other
```

**Frozen at: 2026-07-22**
