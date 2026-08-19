# Phase 11: Autonomous Learning — Memory Update Contract v1.0

> Status: **DRAFT 📝** — After Acquisition Contract.
> Upstream: ACQUISITION_CONTRACT.md, LEARNNING_GOAL_CONTRACT.md, AUTONOMOUS_LEARNING_DATA_CONTRACT.md
> Downstream: Phase 10 Semantic Memory Evaluation
>
> **This contract is the bridge between Phase 11 and Phase 10.**
>
> Memory Update is a proposal for knowledge evolution.
> **Memory Update is NOT direct memory mutation.**
> Proposal ≠ Acceptance.
> More learning ≠ More write authority.

---

## §1 — Proposal Boundary

### 1.1 Role Declaration

```
MemoryUpdateProposal 是：
  ─ 知识演进的提案
  ─ 新增抽象的建议
  ─ 修正线索的提交

MemoryUpdateProposal 不是：
  ─ 直接写入
  ─ 决定
  ─ 命令
  ─ authority 升级入口
  ─ 历史改写器
```

### 1.2 MemoryUpdateProposal Schema

```yaml
proposal_id:                string
source_learning_goal_id:    string              # must point to an approved LearningGoal
evidence_ids:               [string]            # references to EvidenceRecords
target_layer:               string              # experience | pattern | concept | principle
change_type:
  - add                                         # 新增抽象
  - revise                                      # 修改已有抽象（非覆盖）
  - append_evidence                             # 追加证据/反例
  - deprecate                                   # 标记为 superseded
target_reference:           string              # abstraction_id (for revise/deprecate)
proposed_content:           string              # the new/updated content
rationale:                  string              # why this change is proposed
limitations:                [string]            # known limitations of the proposal
status:                     string              # proposed (initial state — cannot be auto-accepted)
timestamp:                  string              # ISO 8601
provenance:                 string              # full trace to original Gap/Goal/Acquisition
```

### 1.3 Forbidden Fields

```
┃ decision:           Proposal 不能携带"决定"属性
┃ approval:           Proposal 不能自签署 approval
┃ authority:          Proposal 不能携带权限修改指令
┃ priority:           Proposal 不能定义优先级
┃ mandatory:          Proposal 不能是强制性的
┃ effective_immediately:  Proposal 不能自声明立即生效
┃ override_existing:  Proposal 不能声明"覆盖旧知识"
```

### 1.4 Allowed Change Types — Detailed

| Type | Meaning | Example |
|------|---------|---------|
| `add` | 新增一个不存在的抽象 | 创建新 Pattern / Concept / Principle |
| `revise` | 更新已有抽象的置信度或描述 | 更新 Principle 的 confidence 从 0.3 → 0.6 |
| `append_evidence` | 为已有抽象添加证据或反例 | 追加一条 contradiction 到 Principle |
| `deprecate` | 标记已有抽象为 superseded （不删除） | 标记旧 Pattern 为 superseded_by=p_new |

### 1.5 Forbidden Change Types

```
┃ delete:             不允许删除任何抽象
┃ replace:            不允许替换（用新内容覆盖旧内容）
┃ merge:              不允许自动合并抽象
┃ archive:            不允许归档（超出学习范围）
┃ rewrite_history:    不允许改写 Provenance
```

---

## §2 — Phase 10 Integration Boundary

### 2.1 Data Flow

```
Phase 11:
  KnowledgeGap
      ↓
  LearningGoal
      ↓
  Acquisition
      ↓
  EvidenceRecord
      ↓
  MemoryUpdateProposal         ← §1 scope ends here
      │
      ▼
  ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─
  Phase 10 / Constitution:
  Phase 10 Semantic Memory Evaluation
      ↓
  Decision (Article I)
      ↓
  Phase 10 Abstraction Store    ← committed only here
  ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─
```

### 2.2 Bridge Contract

```
Phase 11 → Phase 10 的唯一接口是：

MemoryUpdateProposal(status=proposed)
    └── type: add | revise | append_evidence | deprecate
    └── target_layer: experience | pattern | concept | principle
    └── provenance: full trace to Phase 11 records

Phase 11 不调用：
  ┃ Phase 10.PrincipleStore.save()
  ┃ Phase 10.PatternStore.update()
  ┃ Phase 10.ConceptStore.delete()
  ┃ Phase 10.SemanticMemory.commit()
  ┃ Phase 10.ProvenanceLog.modify()
```

### 2.3 Evaluation Ownership

```
MemoryUpdateProposal 的 Evaluation 由 Phase 10 的 Evaluation 链负责：

  Phase 10 检查：
    ─ 新抽象是否与现有知识一致
    ─ 是否有冲突需要记录
    ─ Provenance 是否完整
    ─ 是否遵守 Phase 10 Contracts

  Phase 11 不参与 Evaluation 决策过程：
    ─ Phase 11 提交 Proposal
    ─ Phase 10 评估并决定
    ─ Phase 11 无否决权
    ─ Phase 11 无自动通过权
```

### 2.4 Enforcement

```
Phase 11 → Phase 10 write:
  ┃ FORBIDDEN: any direct write to Phase 10 stores
  ┃
  ┃ REQUIRED:
  ┃   MemoryUpdateProposal(status=proposed)
  ┃   → Phase 10 Evaluation
  ┃   → Decision (Article I)
  ┃   → Phase 10 storage write
```

---

## §3 — Immutable History Protection

### 3.1 Inheritance from Phase 10

```
Phase 10 Provenance Contract:
  Provenance Record is immutable.
  No system module may rewrite, delete, or modify a provenance record.

Phase 11 extends:
  MemoryUpdateProposal creates NEW Provenance entry only.
  MemoryUpdateProposal does NOT modify or delete existing Provenance.
```

### 3.2 Allowed Operations on History

| Operation | Allowed? | Condition |
|-----------|:--------:|-----------|
| Append new evidence | ✅ | Must reference existing abstraction |
| Append counter-example | ✅ | Must reference existing abstraction |
| Append limitation | ✅ | Must reference existing abstraction |
| Create superseding abstraction | ✅ | Must reference superseded_id |
| Rewrite source history | ❌ | Immutable |
| Erase contradiction | ❌ | Conflict is preserved |
| Change provenance | ❌ | Provenance immutable |
| Replace original abstraction | ❌ | Only deprecate + new |

### 3.3 Supersede Pattern (Not Delete)

```
Deprecation Flow:

  1. Create NEW abstraction (Pattern B)
     └── supersedes: Pattern A
     └── rationale: new evidence contradicts Pattern A

  2. Pattern A remains in Phase 10 store
     └── status: superseded
     └── superseded_by: Pattern B

  3. Provenance:
     └── Pattern A → [immutable history]
     └── Pattern B → [new provenance referencing A]

Result:
  ─ Pattern B 是当前建议的抽象
  ─ Pattern A 不可删除 — 保留历史证据
  ─ Provenance 链完整可审计
```

### 3.4 Enforcement

```
No Phase 11 module shall call:
  ┃ delete()
  ┃ overwrite()
  ┃ modify_provenance()
  ┃ erase()
  ┃ clear()

Allowed:
  ┃ create_new_abstraction(supersedes=old_id)
  ┃ append_evidence(abstraction_id)
  ┃ append_limitation(abstraction_id)
```

---

## §4 — Proposal ≠ Acceptance

### 4.1 Status Flow

```
MemoryUpdateProposal.status:

  proposed  →  submitted to Evaluation
      │
      ▼
  evaluated →  Evaluation 审查完成
      │
      ├── accepted    →  wait for Decision
      ├── rejected    →  closed, reason recorded
      └── needs_revision →  additional evidence required
      │
      ▼
  committed →  Decision executed
```

### 4.2 Status Ownership

```
proposed     →  set by Phase 11 (only initial state)
evaluated    →  set by Phase 10 Evaluation
accepted     →  set by Phase 10 Evaluation
rejected     →  set by Phase 10 Evaluation
needs_revision → set by Phase 10 Evaluation
committed    →  set by Decision Layer
```

### 4.3 What Phase 11 Cannot Set

```
Phase 11 不能自设置：
  ┃ status = accepted          — 自接受 = 自授权
  ┃ status = committed         — 自执行 = 自修改
  ┃ status = effective         — 自生效 = 绕过 Evaluation
  ┃ approved_by = self         — 自批准
  ┃ decision = approved        — 模拟 Decision
```

### 4.4 Enforcement

```
MemoryUpdateProposal.status must start as "proposed".
Any other initial status → ❌ REJECT.

Phase 11 modules cannot change status to:
  accepted | committed | effective | approved
Those transitions are exclusive to Evaluation/Decision layers.
```

---

## §5 — Identity / Capability Protection

### 5.1 Forbidden Write Targets

MemoryUpdateProposal 的 `target_layer` **不可**触及以下层：

```
┃ Identity Layer
┃   target_layer ∈ {identity, purpose, character, self_description}
┃   → ❌ REJECT
┃
┃ Capability Layer
┃   target_layer ∈ {capability, permission, authorization, role}
┃   → ❌ REJECT
┃
┃ Governance Layer
┃   target_layer ∈ {governance, evaluation_rules, constitution}
┃   → ❌ REJECT
┃
┃ Decision Layer
┃   target_layer ∈ {decision, decision_rules, commit_policy}
┃   → ❌ REJECT
```

### 5.2 Allowed Write Targets

```
MemoryUpdateProposal.target_layer 必须是：

  ─ experience       (Phase 4 — 经验记录)
  ─ pattern          (Phase 10)
  ─ concept          (Phase 10)
  ─ principle        (Phase 10)

以上四项仅限于对"知识"本身的修改/扩展。
```

### 5.3 Enforcement Rule

```
target_layer ∈ {experience, pattern, concept, principle}
target_layer ∉ {identity, capability, governance, decision, constitution}
```

---

## §6 — Conflict Preservation

### 6.1 Inheritance from Phase 10

```
Phase 10: Conflicting abstractions coexist.
Phase 11: Memory Update must preserve conflicts, not resolve them.
```

### 6.2 Conflict Handling

```
Existing Principle:   "Risk in high volatility is 0.3"
New Proposed Principle: "Risk in high volatility is 0.12"

MemoryUpdateProposal:
  ─ type: add (not revise or deprecate)
  ─ proposed_content: "Risk in high volatility is 0.12"
  ─ rationale: "New evidence from external source suggests different value"
  ─ limitations: ["External source unverified", "Sample size unknown"]

Phase 10 Evaluation receives:
  ─ Existing Principle P_001 (confidence: 0.6)
  ─ Proposed Principle P_002 (confidence: 0.2)
  ─ relationship: conflicting

Phase 10 Evaluation decides:
  ─ P_001: status = active (unchanged)
  ─ P_002: status = proposed
  ─ conflict record created: {a: P_001, b: P_002, status: unresolved}
```

### 6.3 Forbidden Conflict Resolution

```
MemoryUpdateProposal 不能执行：
  ┃ select_best_memory()           — 选择"最好"的记忆
  ┃ delete_old_memory()            — 删除旧知识
  ┃ resolve_conflict_automatically() — 自动解决冲突
  ┃ merge_memories()               — 合并冲突记忆
  ┃ override_with_newer()          — 覆盖为新
  ┃ override_with_higher_confidence() — 覆盖为高置信度
```

### 6.4 Core Rule

```
New knowledge does not erase old knowledge.
Conflict is preserved, not resolved.
Abstractions coexist until Evaluation decides.

Phase 11 may propose.
Phase 11 may not resolve.
```

---

## §7 — Authority Isolation

### 7.1 Final Lock

```
More learning ≠ More write authority.

Learning 获得：
  ✅ proposal ability        — 提出知识更新建议
  ✅ evidence collection     — 收集证据能力
  ✅ gap detection           — 发现盲区能力
  ✅ question formation      — 产生问题能力

Learning 不获得：
  ❌ memory authority        — 不可直接写 Memory
  ❌ identity authority      — 不可触及 Identity
  ❌ capability authority    — 不可授予 Capability
  ❌ decision authority      — 不可进入 Decision 层
  ❌ governance authority    — 不可修改 Governance
```

### 7.2 Authority Flow Summary

| Phase 11 Module | Produces | Authority |
|----------------|----------|-----------|
| Gap Detection | KnowledgeGap | None — gap is observation |
| Goal Formation | LearningGoal | None — goal is question |
| Acquisition | EvidenceRecord | None — evidence is raw |
| Memory Update | MemoryUpdateProposal | None — proposal is suggestion |
| → Evaluation | ← | Evaluation 决定是否采纳 |
| → Decision | ← | Decision 决定是否执行 |

### 7.3 The Five Invariances (Final)

```
1. Learning ≠ Self-Modification
   Learning proposes improvement, does not modify itself.

2. Knowledge ≠ Capability
   Acquiring knowledge does not grant new authority.

3. Goal ≠ System Goal
   Learning goal is a question, not a mission.

4. Proposal ≠ Execution
   Proposal must pass Evaluation → Decision to commit.

5. Knowledge Update ≠ Identity Update
   Memory updates cannot touch Identity/Capability/Governance.
```

---

## §8 — Test Points (MU-01 ~ MU-10)

> 测试点用于后续 Validation Tests 阶段。

| ID | Test | Expected | Type |
|----|------|----------|------|
| **MU-01** | Learning 直接调用 Phase 10 store write → ❌ 拒绝 | No direct write | Flow |
| **MU-02** | Proposal 必须有 LearningGoal 来源 → ✅ 或 ❌ | Source validation | Schema |
| **MU-03** | Proposal 初始 status 非 "proposed" → ❌ 拒绝 | Initial status check | Schema |
| **MU-04** | Provenance 修改 → ❌ 拒绝 | Immutable provenance | Flow |
| **MU-05** | Conflict 自动合并 → ❌ 拒绝 | Conflict preservation | Flow |
| **MU-06** | Identity 修改 (target_layer=identity) → ❌ 拒绝 | Layer isolation | Schema |
| **MU-07** | Capability 修改 (target_layer=capability) → ❌ 拒绝 | Layer isolation | Schema |
| **MU-08** | Decision 注入 (target_layer=decision) → ❌ 拒绝 | Layer isolation | Schema |
| **MU-09** | Phase 10 Evaluation 必经 → ✅ 确认 | Bridge contract | Integration |
| **MU-10** | 完整 Proposal 流程 (Gap → Goal → Acquisition → Evidence → Proposal → Evaluation) → ✅ | Integration | Flow |

---

## Related Documents

| Document | Role |
|----------|------|
| OCOS-AutonomousLearning-ABI-1.0.md | Phase 11 ABI §8 — Memory Update Boundary |
| AUTONOMOUS_LEARNING_DATA_CONTRACT.md | Phase 11 Data Contract §5 — Memory Update |
| ACQUISITION_CONTRACT.md | Phase 11 — Evidence source (upstream) |
| LEARNNING_GOAL_CONTRACT.md | Phase 11 — Goal Formation (upstream trigger) |
| OCOS-SemanticMemory-ABI-1.0.md | Phase 10 ABI — downstream consumer |
| SEMANTIC_MEMORY_DATA_CONTRACT.md | Phase 10 — shared abstraction types |
| SEMANTIC_MEMORY_PROVENANCE_CONTRACT.md | Phase 10 — history immutability |
| ARCHITECTURE_CONSTITUTION.md | Articles I–III — binding authority rules |
