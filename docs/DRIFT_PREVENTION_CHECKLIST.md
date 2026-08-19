# Drift Prevention Checklist

> This checklist is the operational form of the **Constitution Phase Entry Review**
> (see `ARCHITECTURE_CONSTITUTION.md` — Phase Entry Review section).
> Every Phase proposal must pass both the Constitution gates (A–D) and this
> expanded checklist before design begins.

---

## Section A — North Star Screening (Constitution Gate A)

### Q1 — Direction

> Is this capability enhancing **the user's cognition** or **the system's own capability**?

| Answer | Action |
|--------|--------|
| User's cognition | ✅ OK |
| System's capability | ⚠️ Must explain why this is necessary to serve the user |

### Q2 — Nature

> Does this Phase add **Information**, **Understanding**, or **Recommendation** —
> or does it add **Authority**?

| Answer | Action |
|--------|--------|
| Information / Understanding / Recommendation | ✅ OK |
| Authority | ❌ Blocked. Cannot proceed. |

### Q3 — Removability

> If this Phase were deleted tomorrow, would OCOS still be a valuable personal assistant?

| Answer | Action |
|--------|--------|
| Yes (valuable without it) | ✅ OK |
| No (system collapses) | ⚠️ Must justify why this Phase must be core |

---

## Section B — Constitution Compliance (Gates B–C)

### Article I — Decision is the only mutation authority

Does this Phase create a new Reality write path outside Decision?

- [ ] No — it uses existing Decision → Commit path
- [ ] Yes — ❌ Blocked unless Constitution is amended

### Article II — Capability growth never grants authority

Does this Phase give more authority to a module that already has power?

- [ ] No — new capability has no new authority
- [ ] Yes — ❌ Auto-reject. Describe what was attempted.

### Article III — Observation never becomes obligation

Does this Phase observe anything?

- [ ] No observation
- [ ] Observation only, no reaction obligation
- [ ] Observation triggers action — ⚠️ Must route through Governance

### Article IV — Prediction never becomes truth

Does this Phase produce predictions, probabilities, or simulations?

- [ ] No
- [ ] Yes — outputs are explicitly marked as evidence, not fact
- [ ] Yes — outputs are treated as ground truth — ❌ Blocked

### Article V — Simulation never becomes Reality

Does this Phase depend on Simulation?

- [ ] No
- [ ] Yes — and the Phase has a documented deletion boundary
- [ ] Yes — but removing Simulation breaks the Phase — ⚠️ Acceptable if Phase is simulation itself (Phase 9). For Phase 10+, justify.

---

## Section C — Boundary Test

### Authority perimeter

Draw the authority boundary. What is the most powerful thing this Phase can do?
Is that acceptable per the North Star?

- Most powerful action:
- Acceptable? Yes / No
- If no, what constraint reduces authority to acceptable level?

### Deletion test

Draw a box around this Phase's code. What depends on it? Can it be removed
without cascading changes?

- Code boundary:
- Dependents:
- Removable without kernel damage? Yes / No

---

## Section D — Past Drift Markers

Check for warning signs:

- [ ] This Phase makes a previous Phase "mandatory" (reclassifying a removable layer as core)
- [ ] This Phase creates a code path where the system acts without the user
- [ ] This Phase introduces a "self-improvement" loop that is not supervised
- [ ] This Phase assumes the user's goals without confirmation
- [ ] This Phase's value proposition cannot be explained without saying "AI should..."

If any marker is checked, the Phase must be redesigned or rejected.
