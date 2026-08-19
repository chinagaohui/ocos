# Phase 13 Cognitive Workflow Engine — Interaction Contract v1.0

> Status: **FROZEN ❄️** — Data Contract frozen; Interaction Contract approved.
>
> This contract defines how Workflow Engine interacts with Agents,
> Evaluation Layer, and Decision Layer
> **without forming hidden organizational power structures**.
> It is the interaction-level enforcement of Phase 13's core invariant:
>
> **Workflow coordinates cognition, never commands it.**

---

## §0 — Core Principles

### Zero-Authority Interaction

```
Workflow  ≠  Manager of Agents
Agent     ≠  Subordinate of Workflow
Workflow  ≠  Evaluation bypass
Agent     ≠  Workflow authority source
Critique  ≠  Veto
```

### Why This Matters

Without this contract, cognitive coordination naturally drifts into
management hierarchy:

```
❌  Drift Path:
    Workflow suggests Step A → Agent A
    → Agent A always follows Workflow's suggestion
    → Workflow stops offering alternatives
    → Workflow suggestions become de facto commands
    → Workflow gains functional management authority

✅  Contract Path:
    Workflow suggests Step A → Agent A
    → Agent A evaluates, may choose Step B
    → Workflow logs the path chosen
    → Both paths remain available
    → Star Topology preserved
```

---

## §1 — Workflow ↔ Agent: Collaboration, Not Management

### 1.1 The Rule

> **Workflow Engine suggests. Agents decide. Evaluation validates.**

### 1.2 Allowed Interactions

| Direction | Interaction | Type | Valid? |
|-----------|-------------|------|--------|
| Workflow → Agent | Offer step suggestion | `suggest_step()` | ✅ |
| Workflow → Agent | Route available context | `route_context()` | ✅ |
| Workflow → Agent | Report workflow state | `report_progress()` | ✅ |
| Agent → Workflow | Indicate analysis complete | `complete_step()` | ✅ |
| Agent → Workflow | Request context extension | `request_context()` | ✅ |
| Agent → Workflow | Provide feedback for next step | `report_findings()` | ✅ |
| Workflow → Agent | Require alternative evaluation | `require_diversity_check()` | ✅ Only when path_lock detected |

### 1.3 Forbidden Interactions

| Direction | Interaction | Drift Risk |
|-----------|-------------|------------|
| Workflow → Agent | Command to execute | Workflow → Management |
| Workflow → Agent | Override Agent's decision | Workflow → Authority |
| Workflow → Agent | Skip evaluation step | Workflow → Decision bypass |
| Workflow → Agent | Assign priority to Agent | Workflow → Hierarchy |
| Agent → Workflow | Request priority boost | Agent → Influence Workflow |
| Agent → Workflow | Declare self as workflow authority | Agent → Workflow control |

### 1.4 Interaction Protocol

```python
class WorkflowAgentInteraction:
    """Defines the allowed interaction surface between Workflow and Agents."""

    # ---- Allowed: Workflow-to-Agent (collaboration) ----

    def suggest_step(self, suggestion: WorkflowSuggestion, agent_role: str) -> None:
        """Offer a process suggestion. Agent is free to accept or decline."""
        assert suggestion.influence_type in {"suggestion", "proposal", "hint", "note"}
        # Agent receives suggestion as evaluation input, not instruction
        agent_channel.deliver(suggestion)

    def route_context(self, context: list[str], agent_role: str) -> None:
        """Route context to agent. Must declare scope transparency (§4.5)."""
        self._log_context_routing(context, agent_role)
        agent_channel.deliver({"context": context, "total_available": len(context)})

    def report_progress(self, workflow_id: str) -> WorkflowStatus:
        """Expose current workflow state (read-only)."""
        return self._get_status(workflow_id)

    # ---- Forbidden: Workflow-to-Agent (management) ----

    # def execute_step(self, step, agent) -> None:          ❌ Management
    # def override_agent(self, agent, decision) -> None:     ❌ Authority
    # def bypass_evaluation(self, step) -> None:              ❌ Decision bypass
    # def prioritize_agent(self, agent, priority) -> None:   ❌ Hierarchy


class AgentWorkflowInteraction:
    """Defines what Agents can request from Workflow Engine."""

    # ---- Allowed: Agent-to-Workflow (feedback) ----

    def complete_step(self, agent_output: dict) -> None:
        """Signal step completion. Workflow routes to next step."""
        assert "decision" not in agent_output  # Phase 12: Agent ≠ Decision
        workflow_router.advance(agent_output)

    def request_context(self, context_type: str, reason: str) -> list[str]:
        """Request additional context. Workflow may provide if available."""
        return self._get_additional_context(context_type, reason)

    def report_findings(self, findings: dict) -> None:
        """Provide analysis output that may influence next Workflow step.
        Only process-relevant findings; never authority claims."""
        # Allowed: "Evidence suggests focusing on X"
        # Forbidden: "Authority suggests skipping Y"
        assert "authority" not in findings
        workflow_router.receive_findings(findings)

    # ---- Forbidden: Agent-to-Workflow (authority influence) ----

    # def set_priority(self, priority) -> None:          ❌ Influence Workflow
    # def claim_workflow_authority(self) -> None:        ❌ Workflow control
    # def override_suggestion(self, suggestion) -> None:  ❌ Agent → Workflow command
```

---

## §2 — Workflow ↔ Evaluation: Observation, Not Control

### 2.1 The Rule

> **Workflow provides process data to Evaluation.**
> **Evaluation evaluates.**
> **Workflow never evaluates.**

### 2.2 Allowed Interactions

```python
class WorkflowEvaluationInteraction:
    """Workflow's interaction with Evaluation Layer is read-only reference."""

    def provide_process_context(self, suggestion: WorkflowSuggestion,
                                provenance: ProvenanceEntry) -> None:
        """Provide workflow process context to Evaluation."""
        # Evaluation uses this to assess how the suggestion was formed
        pass

    def report_workflow_status(self, status: WorkflowStatus) -> None:
        """Expose workflow state for Evaluation's situational awareness."""
        pass

    # Evaluation output flows to Decision, not back to Workflow
    # Evaluation ← Workflow: ✅ context reference
    # Evaluation → Workflow: ❌ No feedback loop that creates authority
```

### 2.3 Forbidden Interactions

```
Workflow → Evaluation: command to evaluate in a certain way     ❌
Workflow → Evaluation: skip certain evidence                    ❌
Evaluation → Workflow: request decision override                ❌
Evaluation → Workflow: assign evaluation authority to Workflow   ❌
```

---

## §3 — Workflow ↔ Decision: Never Direct

### 3.1 The Rule

> **Workflow output never reaches Decision Layer.**
>
> Path: Workflow → Agent → Evaluation → Decision ✅
> Path: Workflow → Decision                                  ❌

### 3.2 Interaction Matrix

| From | To | Means | Allowed? |
|------|----|-------|----------|
| Workflow | Decision | Direct message | ❌ Bypasses Agent+Evaluation |
| Workflow | Decision | Through context router | ❌ Bypass |
| Workflow | Decision | Through provenance log | ❌ Read-only provenance ≠ decision input |
| Decision | Workflow | Request process info | ✅ Decision can query workflow status |
| Decision | Workflow | Request re-evaluation | ⚠️ Only through Evaluation |
| Decision | Workflow | Assign authority | ❌ Workflow cannot receive authority |

```python
class WorkflowDecisionBoundary:
    """Enforces the Workflow ↔ Decision isolation."""

    # ---- Allowed: Decision reads Workflow data ----

    def get_workflow_status(self, workflow_id: str) -> WorkflowStatus:
        """Decision can query workflow state for situational awareness."""
        return workflow_store.get_status(workflow_id)

    def get_provenance_chain(self, workflow_id: str) -> list[ProvenanceEntry]:
        """Decision can read provenance for context."""
        return provenance_log.read_chain(workflow_id)

    # ---- Blocked: Workflow → Decision ----

    def _block_workflow_to_decision(self):
        """No direct channel exists. Structural separation, not policy."""
        raise DataDirectionError("Workflow → Decision is blocked by contract")
```

---

## §4 — Star Topology: Workflow at Center, Not Top

### 4.1 The Topology

```
        ┌─────────────┐
        │   Decision  │
        └──────┬──────┘
               │ evaluation result
        ┌──────▼──────┐
        │  Evaluation │
        └──────┬──────┘
               │ agent proposals
        ┌──────▼──────┐
        │   Agents    │
        └──┬──┬──┬──┬─┘
           │  │  │  │
           │  │  │  │  WorkflowSuggestion (radial)
           │  │  │  │
        ┌──▼──▼──▼──▼──┐
        │   Workflow   │
        │   Engine     │
        └──────────────┘
```

Workflow Engine 处于**中心（Center）**，但非**顶端（Top）**。

- 中心 = 每个 Agent 都与 Workflow 通信 → Star Topology
- 非顶端 = Workflow 不支配 Agent → Workflow ≠ Manager

### 4.2 Topology Rules

| Rule | Meaning | Enforcement |
|------|---------|-------------|
| **Radial communication** | Agent ↔ Workflow only; no Agent-Agent routing through Workflow | Workflow does not act as message broker between Agents |
| **No hub authority** | Center of topology ≠ hierarchy top | Workflow cannot issue commands, only suggestions |
| **Agent autonomy preserved** | Agent can reject suggestion without consequence | No penalty mechanism in Workflow state |
| **Evaluation over Watch** | Workflow observes but does not judge Agent performance | No performance score in Workflow state |
| **Decision external** | Decision Layer is outside Workflow topology | Workflow cannot initiate decision flow |

### 4.3 Why Star, Not Hierarchy

```
Hierarchy (❌):
    Workflow (Manager)
        ↓ instruct
    Agent A          Agent B
        ↓            ↓
    Task            Task

    → Workflow has management authority
    → Agents become subordinates
    → Evaluation is bypassed

Star Topology (✅):
    Agent A ---- Workflow ---- Agent B
                  Engine
         Evaluation ---- Decision

    → Workflow coordinates, not commands
    → Agents maintain autonomy
    → Evaluation + Decision are independent
```

---

## §5 — Critique / Consensus / Reputation: No Re-Entry Paths

### 5.1 The Risk

Agent critique, consensus opinions, and reputation metrics are
Phase 12 concepts that could create **re-entry paths** into Workflow authority:

```
Agent A critiques Agent B's work
    ↓
Consensus shows Agent A is frequently correct
    ↓
Workflow records Agent A's "reputation"
    ↓
Workflow starts routing more work to Agent A
    ↓
Agent A gains functional priority via Workflow routing
    ↓
Hidden authority path formed
```

### 5.2 Phase 13 Rules

| Mechanism | In Workflow? | Allowed? | Reasoning |
|-----------|-------------|----------|-----------|
| Agent Critique | Stored in Agent output | ✅ Phase 12 contract | Workflow must NOT weight critiques |
| Agent Consensus | Evaluated by Evaluation | ✅ Phase 12 contract | Workflow must NOT derive routing from consensus |
| Agent Reputation | Tracked by Workflow | ❌ Denied | Reputation → implicit priority → authority |
| Agent Historical Accuracy | Tracked by Workflow | ❌ Denied | History → Authority (§5 prohibition) |
| Agent Confidence Score | In Agent output | ✅ Allowed | But Workflow must NOT use for routing weight |

### 5.3 Reputation-Free Routing

```python
class WorkflowRouter:
    """Routes suggestions to Agents without using reputation or priority."""

    def next_agent(self, suggestion: WorkflowSuggestion,
                   available_agents: list[str]) -> str:
        """Select agent without reputation, ranking, or historical weight."""
        # Allowed selection criteria:
        #   - Agent role (planner, critic, risk)
        #   - Round-robin (fair distribution)
        #   - Random selection (anti-bias)
        #   - Explicit user request

        # Forbidden selection criteria:
        #   - Agent historical accuracy (→ History ≠ Authority)
        #   - Agent reputation score (→ Reputation ≠ Priority)
        #   - Agent success count (→ Frequency ≠ Importance)
        #   - Agent confidence rank (→ Confidence ≠ Decision)

        assert "reputation" not in suggestion  # no reputation field
        return self._role_based_select(available_agents, suggestion.suggested_step)
```

---

## §6 — Failure Handling: No Evaluation Bypass

### 6.1 The Rule

> **Failure in Workflow does not grant authority to bypass Evaluation.**

### 6.2 Failure Scenarios

| Scenario | Workflow Action | Allowed? |
|----------|----------------|----------|
| Agent A fails to complete step | Workflow suggests retry or alternative agent | ✅ |
| All agents fail | Workflow flags system-level failure | ✅ |
| Workflow times out | Workflow reports timeout; Evaluation decides next action | ✅ |
| Workflow encounters error | Workflow reports error; Evaluation decides escalation | ✅ |
| Agent A fails | Workflow auto-routes to Agent B | ❌ Auto-routing = Decision by Workflow |
| Timeout | Workflow auto-skips evaluation | ❌ Skip = Decision bypass |
| Error | Workflow auto-falls back to default path | ❌ Default ≠ Correct (§4) |

```python
class FailureHandler:
    """Handles Workflow failures without acquiring decision authority."""

    def handle_agent_failure(self, agent_role: str, step: str,
                             alternatives: list[str]) -> FailureReport:
        """Report failure and suggest alternatives.
        Does NOT auto-route or auto-decide."""
        report = FailureReport(
            failed_agent=agent_role,
            failed_step=step,
            alternatives=alternatives,
            recommended_action=None,  # no auto-suggestion of "correct" path
        )
        # Evaluation layer decides next action
        evaluation_channel.deliver(report)
        return report

    def handle_timeout(self, workflow_id: str,
                       last_successful_step: str) -> FailureReport:
        """Report timeout. Does NOT auto-escalate."""
        report = FailureReport(
            workflow_id=workflow_id,
            failure_type="timeout",
            last_step=last_successful_step,
            recommended_action=None,  # no auto-decision
        )
        evaluation_channel.deliver(report)
        return report

    # Forbidden:
    # def auto_route_on_failure(self, ...) -> None:   ❌ Workflow decides
    # def auto_escalate(self, ...) -> None:            ❌ Workflow initiates escalation
```

---

## §7 — Interaction Safety Checklist

以下检查项在进入 Validation Tests 前应全部通过：

| # | Check | Pass Condition |
|---|-------|----------------|
| 1 | Workflow → Agent: suggestion only | No command/override patterns |
| 2 | Workflow → Evaluation: read-only | Evaluation never receives commands |
| 3 | Workflow → Decision: blocked | No direct channel exists |
| 4 | Agent → Workflow: no authority influence | Agent cannot request priority/weight |
| 5 | Star topology preserved | Workflow is center, not top |
| 6 | No reputation routing | Router uses role/random, not reputation |
| 7 | Failure handling: no bypass | Failure reports to Evaluation, never auto-routes |
| 8 | No critique/consensus weight in Workflow | Workflow does not derive routing from critique history |

---

## §8 — Contract Metadata

```
Contract Name:     Phase 13 Cognitive Workflow — Interaction Contract v1.0
Based On:          Phase 13 ABI §1–§5 + Data Contract §3 (Data Direction)
Status:            FROZEN ❄️ — approved 2026-07-22
Created:           2026-07-22
Supersedes:        N/A
```

---

*Next: Validation Tests → Integration Gate*
