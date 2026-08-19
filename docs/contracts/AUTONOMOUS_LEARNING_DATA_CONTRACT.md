# Phase 11: Autonomous Learning — Data Contract v1.0

> Status: **DRAFT 📝** — After ABI freeze.
> Extends Phase 10 Semantic Memory Contracts.
> Does NOT replace them — Phase 11 operates on top of Phase 10 abstractions.
>
> Core Invariant: **Learning is observation of knowledge state, not instruction to change system.**

---

## §1 — Learning Record Responsibility

### 1.1 LearningRecord ≠ System Directive

```
LearningRecord 是：
  Observation of knowledge state
  Evidence of gap existence
  Proposal for knowledge improvement

LearningRecord 不是：
  Instruction to change system
  Command to acquire information
  Mandate to update memory
  Permission to grant capability
```

### 1.2 Record Types

| Type | Description | Can be created by |
|------|-------------|-------------------|
| `KnowledgeGap` | 某 domain 的理解盲区记录 | Gap Detector, External Exposure, Evaluation |
| `LearningGoal` | 一个可回答的 question | Based on KnowledgeGap |
| `AcquisitionRecord` | 获取信息的日志 | Acquisition module |
| `MemoryUpdateProposal` | 对 Phase 10 抽象更新的建议 | Any Phase 11 module |
| `LearningLog` | 全生命周期审计追踪 | System |

### 1.3 Not a Capability

LearningRecord 的存在不代表对应的 Learning 有权执行。

```
KnowledgeGap 存在 ≠ 系统有义务填补
LearningGoal 提案 ≠ LearningGoal 自动执行
AcquisitionRecord 存在 ≠ 获取的信息自动成为知识
MemoryUpdateProposal 输出 ≠ Memory 已被更新
```

---

## §2 — Knowledge Gap Schema

### 2.1 Core Object: KnowledgeGap

```yaml
gap_id:         string            # unique identifier
domain:         string            # scope (domain:context)
description:    string            # human-readable description of the unknown
evidence_sources:
  - type:       gap_detection | external_exposure | evaluation_request
    source_id:  string            # e.g. Pattern ID, Experience ID
    confidence: float             # 0.0–1.0 — confidence that this is a real gap
unknown_type:
  - missing                        # no knowledge exists for this scope
  - uncertain                      # knowledge exists but confidence is low
  - conflicting                    # multiple sources contradict each other
severity:
  - informational                  # gap exists, low impact if never filled
  - review_needed                  # gap warrants evaluation attention
created_by:
  - gap_detection                  # (default) Phase 11 internal analysis
  - exposure                       # passive observation of new input
  - evaluation                     # Evaluation layer requested a check
status:
  - observed                       # just identified, not evaluated
  - evaluated                      # passed Evaluation Gate
  - resolved                       # resulted in a Phase 10 update
  - abandoned                      # Evaluation decided not to pursue
timestamp:     string              # ISO 8601
provenance:    string              # link to Phase 10 Provenance record
```

### 2.2 Allowed Fields

| Field | Reason |
|-------|--------|
| `gap_id` | 唯一标识 |
| `domain` | 限定 scope |
| `description` | 描述盲区性质 |
| `evidence_sources` | 发现依据 |
| `unknown_type` | 盲区类别（missing/uncertain/conflicting） |
| `severity` | 严重程度（不包含优先级） |
| `created_by` | 来源 |
| `status` | 生命周期 |
| `timestamp` | 审计追踪 |
| `provenance` | Phase 10 连接 |

### 2.3 Forbidden Fields

```
┃ FORBIDDEN in KnowledgeGap:
┃ priority:           Gap detection cannot assign priority
┃ importance:         Gap detection cannot declare importance
┃ must_learn:         Gap detection cannot mandate learning
┃ required_action:    Gap detection cannot define action
┃ system_goal:        Gap detection cannot redefine system purpose
┃ urgency:            Gap detection cannot declare time pressure
┃ owner:              Gap detection cannot claim responsibility
```

### 2.4 gap_id Naming Convention

```
格式: kg_<sequential_number>

示例:
  kg_001   第一被识别的知识盲区
  kg_042   第42个

无语义（不包含 domain/priority 编码）。
```

### 2.5 Severity ≠ Priority

```
severity: informational
  意思：存在一个盲区，不影响当前运作
  不是：这个盲区不重要

severity: review_needed
  意思：值得交给 Evaluation 审查
  不是：必须立即填补
```

---

## §3 — Learning Goal Schema

### 3.1 Core Object: LearningGoal

```yaml
goal_id:        string              # unique identifier
based_on_gap:   string              # must point to an existing KnowledgeGap
type:
  - investigation                   # "What is...?" — exploratory
  - clarification                   # "Is it really...?" — validate
  - verification                    # "Does it hold under...?" — test
origin:
  - gap_detection                   # (default) from Phase 11 internal analysis
  - exposure                        # triggered by new incoming data
  - evaluation_request              # Evaluation layer asked for investigation
question:       string              # must be a well-formed question
scope:          string              # must match the parent gap's domain
expected_output:
  - principle                       # goal seeks a Principle
  - concept_clarification           # goal seeks Concept refinement
  - pattern_description             # goal seeks Pattern analysis
  - conflict_resolution             # goal seeks resolving contradictory evidence
status:
  - proposed                        # created, awaiting Evaluation
  - approved                        # Evaluation approved
  - active                          # being investigated
  - completed                       # resulted in a MemoryUpdateProposal
  - rejected                        # Evaluation rejected
rejection_reason: string            # only if status = rejected
timestamp:      string              # ISO 8601
```

### 3.2 Allowed Question Forms

Learning Goal 的 question 字段只能是以下形式：

```
允许：
  "What is the relationship between X and Y?"
  "How does Strategy A behave under condition B?"
  "Does Principle P still hold when C changes?"
  "Is Concept X consistent with observed data Y?"
  "What causes the discrepancy between source A and source B?"
  "Has the frequency of Pattern P changed over time?"

禁止：
  "How should OCOS evolve?"
  "What capability should OCOS gain?"
  "What system should OCOS become?"
  "Should OCOS change its purpose?"
  "How can OCOS become smarter?"
```

### 3.3 Type Constraint

| Type | Valid question prefix | Example |
|------|----------------------|---------|
| investigation | What, How | "What outcomes does A produce in B?" |
| clarification | Is, Does | "Is Principle P still valid under condition C?" |
| verification | Does, Has | "Does the observed data still support Pattern P?" |

### 3.4 Forbidden Types

```
┃ FORBIDDEN type values:
┃ mission              Learning cannot define system missions
┃ objective            Learning cannot set objectives
┃ self_improvement     Learning cannot target self-improvement
┃ upgrade              Learning cannot trigger upgrades
┃ optimization         Learning cannot optimize system functions
```

### 3.5 Goal → Gap Relationship

```
Every LearningGoal must:
  (a) reference a KnowledgeGap by gap_id
  (b) have a scope that matches or is a subset of the gap's domain
  (c) be a question that, if answered, would reduce or resolve the gap
```

---

## §4 — Acquisition Boundary

### 4.1 Data Flow

```
Source → Acquire → Evidence → Evaluate → Proposal
                       │
                       └─ NOT: Acquire → Truth → Update
```

### 4.2 Acquisition Record Schema

```yaml
record_id:         string
goal_id:           string           # which LearningGoal this serves
source_type:
  - internal_experience             # Phase 4
  - internal_abstraction            # Phase 10
  - external_input                  # user, file, network, etc.
source_origin:     string           # description of where
content:           string           # raw information
evidence_level:
  - raw                             # unverified
  - cross_referenced                # consistent with existing knowledge
  - verified                        # passed all checks
timestamp:         string           # ISO 8601
```

### 4.3 Source Trust Calibration

| Source Type | Default trust | Evaluation required? |
|-------------|--------------|----------------------|
| internal_experience | High | Already in Phase 4 |
| internal_abstraction | Medium | Check consistency with parent Gap |
| external_input | Low | **Mandatory** — must pass Evaluate gate |

### 4.4 Forbidden Acquisition Paths

```
┃ FORBIDDEN:
┃ External information → automatic truth
┃ Acquisition → direct Memory write
┃ Information → Capability grant
┃ Raw input → Principle
```

---

## §5 — Memory Update Contract

### 5.1 Data Flow (Inherited from Phase 10)

```
Learning Goal (Phase 11)
    ↓
Memory Update Proposal (Phase 11)     ← §5 scope ends here
    ↓
Semantic Memory Evaluation (Phase 10) ← Phase 10 contracts
    ↓
Decision (Constitution Article I)
    ↓
Memory committed
```

### 5.2 MemoryUpdateProposal Schema

```yaml
proposal_id:            string
based_on_goal:          string         # LearningGoal ID
based_on_gap:           string         # KnowledgeGap ID (redundant for trace)
target_layer:
  - pattern              # Phase 10
  - concept              # Phase 10
  - principle            # Phase 10
action_type:
  - create_abstraction
  - update_confidence
  - flag_conflict
  - supersede            # mark old abstraction as superseded (not deleted)
proposed_content:       string         # the new/updated abstraction content
provenance:             string         # full trace: gap → goal → acquisition → proposal
status:
  - proposed
  - under_evaluation
  - approved
  - rejected
  - committed
rejection_reason:       string         # only if rejected
timestamp:              string         # ISO 8601
```

### 5.3 Forbidden Write Targets

```
MemoryUpdateProposal cannot propose changes to:
  ┃ Identity
  ┃ Capability Registry
  ┃ Permission scope
  ┃ Governance rules
  ┃ Constitution
  ┃ Provenance Records (Phase 10 — immutable)
  ┃ Experience Records (Phase 4 — immutable)
```

### 5.4 Proposal ≠ Execution

```
MemoryUpdateProposal status = proposed:
  NOT YET executed.

Proposal becomes committed only after:
  Evaluation (Phase 10) → Decision (Article I)

Learning cannot execute, only propose.
```

---

## §6 — Authority Isolation

### 6.1 Phase 11 Data-Level Invariances

| # | Invariant | Enforcement |
|---|-----------|-------------|
| 1 | **Learning ≠ Self-Modification** | No Learning schema may contain fields for system identity, capability, or governance changes |
| 2 | **Knowledge ≠ Capability** | KnowledgeGap and Acquisition schemas have no capability-related fields |
| 3 | **Goal ≠ System Goal** | LearningGoal.type is limited to investigation/clarification/verification; mission/objective/self_improvement forbidden |
| 4 | **Proposal ≠ Execution** | MemoryUpdateProposal cannot bypass status=proposed → Evaluation → Decision chain |
| 5 | **Knowledge Update ≠ Identity Update** | MemoryUpdateProposal.target_layer cannot include identity, capability, or governance |

### 6.2 No Priority Escalation

No Phase 11 data structure may carry a `priority` or `urgency` field.

```
Reason: Priority is an Evaluation-layer concept.
        Gap detection creates evidence, not urgency.
        Learning proposes, Governance prioritizes.
```

### 6.3 Separating Data from Authority

```
Phase 11 的数据层只负责：
  ─ 记录盲区
  ─ 定义问题
  ─ 追踪获取
  ─ 输出提案

Phase 11 的数据层不负责：
  ─ 决定优先级
  ─ 授予权限
  ─ 修改身份
  ─ 执行操作

数据层与权限层的分离是硬边界。
```

---

## Related Documents

| Document | Role |
|----------|------|
| OCOS-AutonomousLearning-ABI-1.0.md | Phase 11 ABI — upstream |
| SEMANTIC_MEMORY_DATA_CONTRACT.md | Phase 10 Data Contract — shared abstraction types |
| SEMANTIC_MEMORY_PROVENANCE_CONTRACT.md | Phase 10 Provenance Contract — history immutability |
| OCOS-SemanticMemory-ABI-1.0.md | Phase 10 ABI — Memory update chain |
| ARCHITECTURE_CONSTITUTION.md | Articles I–III — binding authority rules |
