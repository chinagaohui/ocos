# Phase14.4.4 — Principle Validation Contract

**Status**: ❄️ FROZEN (2026-07-22)
**Phase**: Phase14.4 Meta Principle Formation
**Previous**: §14.4.3 Evidence Chain / Explanation ABI ✅
**Next**: §14.4.5 Principle Registry

## §0 Positioning

**Principle Validation** is NOT Principle Scoring.
It does not evaluate *quality* or *value*.
It verifies *structural sufficiency*.

### What this means

Validation asks:

> Does this Principle have enough structural evidence to be considered a valid abstraction of observed narrative mechanisms?

Validation does NOT ask:

> Is this Principle good? Is it effective? Should readers like it?

### Core Principle

Every Cognitive Output must be traceable to Reality.

```
Capability (Phase14.5)
  ↓
Validated Principle (§14.4.4)
  ↓
Principle Candidate (§14.4.2)
  ↓
Inference Record (§14.4.3)
  ↓
Pattern References
  ↓
Evidence References
  ↓
Reality (Phase14.3)
```

## §1 Validation Dimensions (5)

### 1.1 Evidence Sufficiency

**Question**: Are there enough Patterns to support this Principle?

| Abstraction Level | Minimum Pattern Count | Notes |
|---|---|---|
| L1 Mechanism Candidate | ≥2 | Single pattern cannot form mechanism |
| L2 Principle | ≥3 | Must span at least 2 distinct works |
| L3 General Principle | ≥5 | Must span ≥3 distinct works/cross-genre |

**Forbidden**: "feels sufficient" / "common sense" / "widely known" — must count explicit Patterns.

### 1.2 Cross-Context Stability

**Question**: Does this mechanism appear across different works/contexts?

A Principle derived from patterns in a single work is not stable.
Stability requires patterns from ≥2 distinct works for L2, ≥3 for L3.

**Forbidden**: "reads like a universal principle" / "this is common" — must cite distinct works.

### 1.3 Contradictory Evidence

**Question**: Are there counter-examples that weaken the abstraction?

Contradictory evidence does not automatically invalidate — but must be recorded.

| Ratio (Contradictory / Supporting) | Result |
|---|---|
| 0% | PASS |
| >0% ≤25% | WEAKENED — recorded in Validation Record |
| >25% ≤50% | INCONCLUSIVE — requires review |
| >50% | FAIL — invalid abstraction |

**Forbidden**: "no known counter-examples" without explicit search — must check Evidence Chain.

### 1.4 Abstraction Consistency

**Question**: Did the derivation skip levels?

| Derivation Path | Status |
|---|---|
| L0 Pattern → L1 → L2 | Valid |
| L0 Pattern Set → L2 directly | INVALID — level jump |
| L0 Pattern → L3 directly | INVALID — level skip |
| L1 Mechanism Candidates → L2 | Valid |
| L2 Principles → L3 | Valid |
| L0 Pattern → L3 (with intermediate L1+L2 documented) | Valid if chain traceable |

**Forbidden**: "intuitively it's a general principle" — must trace each abstraction step.

### 1.5 Trace Completeness

**Question**: Can the Principle be traced all the way to Reality?

| Check | Requirement |
|---|---|
| Pattern references exist | principle_candidate.source_pattern_ids ≥ 1 |
| Evidence references exist | principle_candidate.source_evidence_ids ≥ 1 |
| Inference record exists | record_id linked to candidate_id |
| All referenced IDs resolvable | pattern_ids start pat-, evidence ev-/e- |
| Explanation references match | key_pattern_ids ⊆ source_pattern_ids |

**Forbidden**: Principle without evidence chain → not accepted.

## §2 Validation ABI

### 2.1 DimensionResult

```python
@dataclass
class DimensionResult:
    dimension: str          # one of the 5 above
    status: str             # PASS | WEAKENED | INCONCLUSIVE | FAIL
    supporting_refs: List[str]
    contradictory_refs: List[str]
    detail: str             # structural description only
```

### 2.2 ValidationResult

```python
@dataclass
class ValidationResult:
    result_id: str                      # vr-*
    candidate_id: str                   # pc-* (principle_candidate)
    dimension_results: List[DimensionResult]
    overall_status: str                 # VALIDATED | INVALIDATED | PENDING_REVIEW
    validated_at: datetime
    validator_version: str = "1.0"
```

### 2.3 ValidatedPrinciple

```python
@dataclass
class ValidatedPrinciple:
    principle_id: str                   # vp-*
    derived_from_candidate: str         # pc-*
    validation: ValidationResult
    abstraction_level: AbstractionLevel
    valid_pattern_ids: List[str]
    valid_evidence_ids: List[str]
    created_at: datetime
```

## §3 Forbidden Fields & Content

**Must NOT appear** in any Validation output:
- `confidence_score` — confidence is observation-level only
- `principle_score` — validation is pass/fail, not score
- `quality_score` — OCOS does not measure quality
- `effectiveness_score` — not a "what works" system
- `importance` — no priority ranking
- `priority` — no business priority
- `recommendation` — no "best practice"
- `best_practice_tag` — no prescriptive tagging
- `commercial_value` — market evaluation is Phase15+
- `reader_approval` — human preference is forbidden input
- `difficulty` — no difficulty rating
- `popularity` — no popularity ranking

## §4 Rules

### R1: Dimension Statuses are bounded
Only 4 statuses: PASS, WEAKENED, INCONCLUSIVE, FAIL.

### R2: Overall Status from Dimensions
| Rule | Overall |
|---|---|
| All dimensions PASS | VALIDATED |
| Any dimension FAIL | INVALIDATED |
| Any WEAKENED / INCONCLUSIVE (no FAIL) | PENDING_REVIEW |
| Trace Completeness FAIL | INVALIDATED (non-blocking) |

### R3: Abstraction Consistency is conditional
L0→L3 without intermediate steps → INVALIDATED.
Cannot be overridden.

### R4: Trace Completeness is mandatory
A Principle without traceable evidence chain cannot be validated.
Cannot be PENDING_REVIEW — must be INVALIDATED or supplemented.

### R5: No score aggregation
No averaging of dimension statuses.
No weighted sum.
No "overall score" field.

## §5 Interface

### Input
```
PrincipleCandidate (from §14.4.2)
  + Evidence Chain (from §14.4.3)
```

### Process
```
PrincipleCandidate
  → Apply 5 Validation Dimensions
  → For each dimension: check against evidence
  → Aggregate: overall_status
  → Produce ValidatedPrinciple
```

### Output
```
ValidatedPrinciple (this contract)
  → Principle Registry (§14.4.5)
```

### Phase14.4 Isolation
Output is a **Validated Principle** — NOT:
- Capability Package
- Writing Rule
- Prompt Template
- Agent Instruction
- Strategy Document
- Best Practice Guide
