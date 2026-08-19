# Architecture Constitution Pattern — v1.0

> A governance pattern for any long-lived, self-evolving system.
> Not a template — do not copy OCOS rules. Copy the governance structure.
>
> Origin: OCOS project, Phase 9.5 Architecture Freeze (2026-07-21)

---

## Purpose

Systems that acquire capabilities over time face a common failure mode:

> Each new capability makes the system more powerful, but also makes it harder to
> remember what the system was originally for.

This pattern provides a minimal governance model to ensure **identity continuity**
across evolution. It answers four questions:

| Question | Response |
|----------|----------|
| Why does this system exist? | North Star |
| What must never change? | Constitution |
| How do new capabilities enter? | Phase Entry Review |
| How is compliance verified? | Implementation + Tests |

The pattern is complete when adding more governance layers would produce more
risk than benefit ("governance bloat").

---

## Pipeline

### Step 1 — North Star Definition

Define the system's purpose as a single, testable statement.

Structure:
- **Purpose** — one sentence: what the system is for
- **Never Become** — 3–5 explicit prohibitions (what the system must never turn into)
- **Core Loop** — the fundamental user → system interaction cycle in N steps

Output: a single-page North Star document.

**Rule:** Every feature proposal passes through the North Star. If the answer to
"does this make the system stronger?" outweighs "does this make the system more
useful to its user?", the proposal is rejected.

### Step 2 — Constitution Creation

Identify N immutable rules (typically 5) that define the system's identity.

Each rule:
- Is a single unambiguous constraint
- Has a clear violation test
- Maps to at least one architecture test

Two-tier mutability:
- **Permanent** (Articles I–III): never change, defines the system's fundamental
  authority and boundary model
- **Conditional** (Articles IV–V): can be revised with written justification and
  explicit user approval

**Warning:** A Constitution with >10 articles is probably governance bloat.

### Step 3 — Immutable Core Identification

Not every rule is equally deep. Identify the 1–3 rules that, if broken, would
fundamentally change the system's nature. These form the **immutable core**.

Examples from OCOS:
- Decision is the only mutation authority
- Capability growth never grants authority
- Observation never becomes obligation

These are permanent — they cannot be amended even with justification.

### Step 4 — Phase Entry Review (4 Gates)

Every new capability phase must pass four gates before design begins:

| Gate | Question | Failure condition |
|------|----------|-------------------|
| A — Direction | Does this serve the user or the system itself? | If "system stronger" > "user better" |
| B — Authority | Does this change who proposes, who decides, who executes? | If authority flow changes without Constitution redesign |
| C — Boundary | Does this touch the system's mutation path? | If yes, must pass through the designated Decision layer |
| D — Identity | After this phase, is the system more like a cognitive tool or an autonomous optimizer? | If trending toward autonomous |

### Step 5 — ABI Contract Definition

Each phase produces an Architecture Boundary Interface (ABI) document containing:

1. **North Star Compliance** — answers to Gates A–D
2. **Constitution Compliance** — proof that no immutable rule is violated
3. **Phase-Specific Contracts** — allow/deny lists for the new capability
4. **Verification Tests** — automated tests that enforce the ABI

### Step 6 — Implementation + Tests

Architecture tests as code. Each Constitution rule and ABI contract must have at
least one automated test that fails if the rule is violated.

Test categories:
- **Restriction tests** — prove a forbidden pattern is rejected
- **Permission tests** — prove an allowed pattern works
- **Boundary tests** — prove edge cases are handled (e.g. removable capability)

---

## Key Principle: Structural Transfer, Not Rule Copying

This pattern transfers **governance structure**, not specific rules.

A different system using this pattern would produce different rules:

```
OCOS:                              Another system:
  Decision = mutation authority      Approval gate = deployment authority
  Capability ≠ authority             Feature flag ≠ production access
  Observation ≠ obligation           Monitoring ≠ auto-remediation
  Simulation ≠ reality               Staging ≠ production
```

The structure (North Star → Constitution → Gates → ABI → Tests) stays the same.
The content is system-specific.

---

## Anti-Patterns

### Governance Bloat

Adding gates beyond the minimum sufficient set (North Star + 4 Entry Gates + ABI).
Symptoms: recursive review layers, governance council, meta-approval requirements.

**Correction:** If a new gate catches a risk that the existing 4 gates already cover,
it is bloat. Stop.

### Rule Copying

Copying OCOS rules verbatim into another system.
Symptoms: "Decision Authority" in a system without decisions.

**Correction:** Ask "what is the immutable core of THIS system?" instead of
"what are the 5 rules from OCOS?"

### Constitution as Process Manual

Using the Constitution to describe workflows, data formats, or CI/CD pipelines.
Symptoms: 50-page Constitution, articles about deployment procedures.

**Correction:** Constitution is about identity. Workflows go in operational docs.

---

## When This Pattern Is Complete

The pattern is complete when:
1. North Star captures why the system exists
2. Constitution captures what must never change
3. Phase Entry Review gates prevent drift
4. ABI contracts define evolution boundaries
5. Tests enforce all of the above
6. Adding more governance layers would create "governance of governance"

At this point, stop. Return to capability work.
