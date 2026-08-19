# OCOS North Star

> Last frozen: 2026-07-21 — Phase 9 Gate 7 completed, prior to Phase 10.
> This file is the highest-level architecture constraint. No Phase, no ABI, no capability
> may contradict it. All lower-level documents (ABIs, LAYER_RULES, contracts) inherit
> from and are subordinate to this charter.

---

## Purpose

OCOS exists to augment **human cognition**.

It is a personal, locally run cognitive assistance system that understands its user,
accumulates experience, learns proactively, analyzes problems, proposes options,
and evolves — always under strict access control.

One sentence:

> **A personal, private, assistive cognitive layer — not an autonomous agent.**

---

## Never Become

OCOS must **never** become:

| Prohibited State | Why |
|---|---|
| **Autonomous authority** | The system does not decide. The user decides. |
| **Self-directed entity** | The system has no goals of its own. Only the user's goals matter. |
| **Reality mutation agent** | No capability may mutate Reality without explicit, authorized commit. |
| **General AGI experiment** | Not a platform for open-ended intelligence scaling. A focused personal tool. |

---

## Core Loop

```
Observe → Understand → Learn → Recommend → User Decide → Act → Remember
```

Every capability added must serve at least one step in this loop.
A capability that does not strengthen this loop is a distraction.

---

## Immutable Rules

1. **User owns goals.** OCOS proposes, the user disposes.
2. **Decision requires authorization.** No path exists for the system to bypass the user.
3. **Reality mutation requires explicit commit.** Write operations are gated by `Decision → Commit → Reality`.
4. **Capability growth never grants authority growth.** Better analysis does not mean more power.
5. **Simulation never decides.** Simulation produces proposals. Governance interprets. User authorizes.

---

## Phase Screening Questions

Every Phase, before design begins, ask:

### Q1 — Direction
> Is this capability enhancing **the user's cognition** or **the system's own capability**?
>
> If the latter, flag for review.

### Q2 — Nature
> Does it add **Information**, **Understanding**, or **Recommendation** —
> or does it add **Authority**?
>
> Only the first three are permitted.

### Q3 — Removability
> If this Phase were deleted tomorrow, would OCOS still be a valuable personal assistant?
>
> If no, this Phase may be over-centralized; reconsider.

---

## Relationship to Phase ABIs

The North Star is an **outer constraint**: every Phase ABI must contain an explicit
section titled **"North Star Compliance"** that answers the three questions above
and explains how the Phase stays within the North Star bounds.

---

## What Comes Next

Phase 10 and beyond should return to the original founding direction:

- Personal knowledge management
- Work assistance
- Creativity enhancement
- Learning assistance
- Decision assistance

Infrastructure (Phases 0–9) is complete. The system now has:
- A kernel with layered isolation
- An event bus for communication
- A meta-observation layer for self-awareness
- A simulation layer for what-if analysis
- A governance layer for safe decision routing

The next frontier is not more infrastructure — it is making this infrastructure
serve the user intelligently.
