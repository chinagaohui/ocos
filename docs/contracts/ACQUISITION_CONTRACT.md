# Phase 11: Autonomous Learning — Acquisition Contract v1.0

> Status: **DRAFT 📝** — After Learning Goal Contract.
> Upstream: LEARNNING_GOAL_CONTRACT.md, AUTONOMOUS_LEARNING_DATA_CONTRACT.md §4
>
> Core axiom inherited from Phase 10:
> **External information ≠ Truth.**
>
> Phase 11 adds:
> **More information ≠ More authority.**
> **Acquisition obtains information. Acquisition does not determine truth.**

---

## §1 — Responsibility Boundary

### 1.1 Role Declaration

```
Acquisition 是：
  ─ 获取信息的手段
  ─ 收集证据的过程
  ─ 比较来源的工具
  ─ 记录不确定性的日志

Acquisition 不是：
  ─ 真理判定器
  ─ 权威来源
  ─ 权限授予者
  ─ 能力升级入口
```

### 1.2 Allowed

```
retrieve information      — 从目标来源获取原始数据
collect evidence          — 收集支持/反驳已有知识的证据
compare sources           — 对比不同来源的异同
record uncertainty        — 记录置信度、不一致、缺失
provide evaluation input  — 输出 Evidence Record 给 Evaluation
```

### 1.3 Forbidden

```
┃ declare truth
┃   → Acquisition 不能声明"这是真的"
┃
┃ promote source authority
┃   → Acquisition 不能提升来源的"权威等级"
┃
┃ override evaluation
┃   → Acquisition 不能绕过 Evaluation 层
┃
┃ update capability
┃   → Acquisition 不能授予或修改能力
┃
┃ grant identity
┃   → Acquisition 不能触及身份信息
```

### 1.4 Why

```
Acquisition 是信息管道，不是真理判定者。

如果 Acquisition 可以判定"这个信息是真的"，
那么它就不需要 Evaluation，直接写 Memory → 等价于 Self-Modification。

Phase 10 已经锁定：External information ≠ Truth
Phase 11 继承并扩展：Acquisition ≠ Truth judgment
```

---

## §2 — Acquisition Input Contract

### 2.1 Allowed Trigger Chain

```
Only LearningGoal can trigger Acquisition.

LearningGoal (Phase 11)
    └── status: approved               ← 必须经过 Evaluation 批准
    └── scope: domain:knowledge:...     ← 受 scope 限制
    ↓
AcquisitionRequest
    ↓
Acquisition Execution
```

### 2.2 AcquisitionRequest Schema

```yaml
request_id:           string            # unique
learning_goal_id:     string            # must point to an approved LearningGoal
scope:                string            # must match goal's scope
source_constraints:
  - prefer_internal                   # 优先使用内部数据
  - accept_external                   # 可接受外部来源
  - temporal_constraint               # 时间范围限制（可选）
expected_type:
  - evidence                          # 期望获取证据
  - comparison                        # 期望获取比较结果
  - raw_data                          # 期望获取原始数据
origin:               string            # always "learning_goal" — no other origin allowed
status:               string            # requested | executing | completed | failed
```

### 2.3 Forbidden Trigger Sources

```
┃ Capability Layer → AcquisitionRequest
┃   Reason: Capability 不能驱动学习；Learning 是信息层，不是能力层
┃
┃ Identity Layer → AcquisitionRequest
┃   Reason: Identity 不能定义要学什么；Learning 被 Goal 驱动
┃
┃ Decision Layer → AcquisitionRequest
┃   Reason: Decision 不负责信息获取；Decision 负责 Reality write
┃
┃ Self-Trigger → AcquisitionRequest
┃   Reason: Self-triggered acquisition = Self-directed learning
┃
┃ External Event → AcquisitionRequest (direct)
┃   Reason: 外来事件必须经过 gap_detection/exposure → Goal 链
```

### 2.4 Enforcement

```
AcquisitionRequest.origin ∈ {learning_goal}
AcquisitionRequest.origin ∉ {capability, identity, decision, self, external_direct}
```

---

## §3 — Source Boundary

### 3.1 Source ≠ Authority

```
一个来源提供信息。
一个来源不等于该信息是可靠的、正确的、有权决定的。

SourceRecord 记录：
  ─ 信息从哪来
  ─ 什么时间采集
  ─ 原始内容引用
  ─ 验证状态
  ─ 已知限制

SourceRecord 不记录：
  ─ 这个来源的"权威等级"
  ─ 这个来源的"信任分数"
  ─ 这个来源的"真理排名"
```

### 3.2 SourceRecord Schema

```yaml
source_id:              string
origin:
  - internal_experience               # Phase 4
  - internal_abstraction              # Phase 10
  - external_input                    # 外部信息
  - comparison_result                 # 内部对比
content_reference:      string        # link or citation
collection_time:        string        # ISO 8601
verification_status:
  - unverified
  - consistency_checked               # 与现有知识对比一致
  - conflict_identified               # 与现有知识对比冲突
  - referred_to_evaluation            # 提交 Evaluation
limitations:
  - possible_bias                     # 可能的偏差
  - incomplete                        # 信息不完整
  - temporal_boundary                 # 有时效性限制
  - scope_mismatch                    # 不完全匹配 scope
```

### 3.3 Forbidden Fields in SourceRecord

```
┃ authority_level:    Acquisition 不定义来源权威
┃ trust_rank:         Acquisition 不排名可信度
┃ truth_score:        Acquisition 不评分真实性
┃ decision_priority:  Acquisition 不指定决策优先级
┃ credibility:        Acquisition 不评定可信度（留待 Evaluation）
```

### 3.4 Why

```
如果 Acquisition 给 Source 打上 authority_level，
那么 Acquisition → Source ranking → Truth ranking → Authority drift。

Acquisition 只负责："什么信息、从哪来、什么状态"
不负责："这个信息有多可靠"
```

### 3.5 Source Trust ≠ Source Authority

```
Trust 是 Evaluation 层的概念：
  Trust 影响是否接受信息进入 Memory Proposal
Trust 不是 Source 的属性：
  Trust 是 Evaluation 的决策结果

Acquisition 层不持有 Trust 判断权。
```

---

## §4 — Evidence Boundary

### 4.1 Data Flow

```
Information (raw)
    ↓
Evidence Record    ← §4 scope：形成可审计的证据记录
    ↓
Evaluation         ← Phase 6 / Phase 8：决定是否进入 Memory
    ↓
Possible Memory Proposal

┃ FORBIDDEN:
┃ Information → Truth → Memory Update
```

### 4.2 EvidenceRecord Schema

```yaml
record_id:                string
acquisition_request_id:   string              # 追溯 AcquisitionRequest
source_id:                string              # 追溯 SourceRecord
content:                  string              # 处理后的信息内容
relationship_to_gap:
  - supports_existing     # 支持已有知识
  - contradicts_existing  # 与已有知识冲突
  - novel                 # 不在现有 Phase 10 覆盖范围
  - neutral               # 与现有知识无关
confidence:               float 0.0–1.0       # 信息质量评估（不是 Truth 评分）
limitations:              [string]            # 已知限制
status:                   string              # raw | processed | referred
timestamp:                string              # ISO 8601
```

### 4.3 Forbidden Evidence Attributes

```
┃ is_truth:              Evidence 不携带"真理"属性
┃ is_fact:               Evidence 不携带"事实"属性
┃ is_authoritative:      Evidence 不携带"权威"属性
┃ override_previous:     Evidence 不能覆盖已有知识
```

### 4.4 Evidence ≠ Conclusion

```
Evidence Record 包含：
  ─ 采集的信息
  ─ 与现有知识的关系
  ─ 已知限制

Evidence Record 不包含：
  ─ "这个信息是真的"
  ─ "这个信息应该替代旧知识"
  ─ "这个信息可以更新 Principle"
```

---

## §5 — Conflict Preservation

### 5.1 Inheritance from Phase 10

```
Phase 10: Conflicting evidence is preserved, not resolved automatically.
Phase 11: Acquisition must preserve conflicts, not choose a winner.

当两个来源提供矛盾信息时：
  Acquisition 的责任是记录双方。
  Acquisition 的责任不是选择谁对。
```

### 5.2 Conflict Handling

```
Source A says: "X = 42"
Source B says: "X = 37"

Acquisition 记录：
  evidence_a: {content: "X = 42", source: A, relationship: "conflicts with B"}
  evidence_b: {content: "X = 37", source: B, relationship: "conflicts with A"}
  conflict_status: "unresolved"

┃ Acquisition 不执行：
┃ choose_winner_source()               — 选择正确来源
┃ remove_conflicting_source()          — 删除冲突来源
┃ auto_resolve_by_majority()           — 自动多数表决
┃ promote_most_recent()                — 自动选择最新
┃ promote_most_frequent()              — 自动选择最频繁
```

### 5.3 Conflict Status

| Status | Meaning | Next Step |
|--------|---------|-----------|
| `unresolved` | 双方证据共存，未解决 | 等待 Evaluation |
| `partially_resolved` | 部分一致，部分冲突 | 等待 Evaluation |
| `referred_to_evaluation` | 已提交 Evaluation 层 | Evaluation 决策 |
| `superseded` | 新证据使冲突过时 | 保留历史记录 |

### 5.4 Core Rule

```
Conflicting evidence is not a problem to be solved.
Conflicting evidence is a state to be preserved.
```

---

## §6 — External Information ≠ Knowledge

### 6.1 Distinction

```
     ↓
Acquired Information
     │
     │  （未经验证）
     │  External | Raw | Uncalibrated
     ▼
     ↓
Evidence Record        ← 经过初步整理
     │
     │  （经 Acquisition 处理）
     │  Structured | Auditable | Referenced
     ▼
     ↓
Validated Evidence     ← 经过 Evaluation
     │
     │  Under Evaluation | Consistent | Conflict
     ▼
     ↓
Semantic Memory Candidate  ← 待进入 Phase 10
     │
     │  Proposed | Approved | Rejected
     ▼
     ↓
Phase 10 Abstraction   ← Periodically updated knowledge
```

### 6.2 Identity Labels

| Stage | Label | Can be stored? |
|-------|-------|---------------|
| 1 | Acquired Information | ❌ No persistent storage |
| 2 | Evidence Record | ✅ Temporary (until evaluation) |
| 3 | Validated Evidence | ✅ Phase 11 record |
| 4 | Semantic Memory Candidate | ✅ Phase 11 → Phase 10 bridge |
| 5 | Phase 10 Abstraction | ✅ Phase 10 store |

### 6.3 Forbidden Shortcuts

```
┃ Acquired Information → Phase 10 Abstraction
┃   (skips Evidence + Evaluation)
┃
┃ Acquired Information → Semantic Memory
┃   (skips Phase 10 contract)
┃
┃ Acquired Information → Memory Update Proposal
┃   (skips Goal → Acquisition → Proposal chain)
```

### 6.4 Enforcement

```
No Phase 10 store shall receive:
  ─ raw acquisition output
  ─ unvalidated evidence
  ─ external input without provenance
```

---

## §7 — Confidence Boundary

### 7.1 What Confidence Is

```
Confidence in Acquisition 表示：
  ─ 信息的采集质量（来源多样性、时间新鲜度等）
  ─ 信息与 scope 的匹配度
  ─ 信息内部的自我一致性

不是：
  ─ 信息的"真实性"评分
  ─ 信息的"权威性"
  ─ 信息的"决定优先权"
```

### 7.2 Confidence Is Not Authority

```
更多来源 ≠ 更高权威
更高置信度 ≠ 更高决定权

Confidence 只能影响：
  ─ evaluation 上下文（给 Evaluation 提供更多参考信息）
  ─ memory calibration（Phase 10 的置信度更新参考）
  ─ conflict detection（高置信度来源值得更多关注）

Confidence 不能影响：
  ─ decision priority（决策优先级）
  ─ authority（权限）
  ─ capability grant（能力授予）
  ─ identity（身份）
```

### 7.3 Confidence Drift Prevention

```
┃ FORBIDDEN:
┃ "This has 3 sources confirming it, so it's true"
┃   → 来源数量 ≠ 真实性
┃
┃ "This source has high confidence, so it can skip Evaluation"
┃   → 高置信度 ≠ 绕过 Evaluation
┃
┃ "Multiple sources agree, therefore automatic update"
┃   → 共识 ≠ 自动写入
```

### 7.4 Core Rule

```
More sources → better evaluation context.
More sources → NOT higher authority.
Confidence informs evaluation.
Confidence does not replace evaluation.
```

---

## §8 — Authority Isolation

### 8.1 What Acquisition Cannot Do

```
Acquisition 无权：
  ┃ create rules             — 创建规则超出信息获取范围
  ┃ change principles        — 变更 Principle 是 Phase 10 权限
  ┃ modify identity          — Identity 不可触及
  ┃ grant capability         — Capability 由 Constitution 管理
  ┃ execute action           — 执行权属于 Decision
  ┃ override evaluation      — 不能绕过 Evaluation
  ┃ resolve conflicts        — 冲突保留不是解决
  ┃ promote source authority — 不能指定来源权威
```

### 8.2 Flow Enforcement

```
Allowed Flow:
    LearningGoal
        ↓
    AcquisitionRequest
        ↓
    Acquisition Execution
        ↓
    Evidence Record
        ↓
    Evaluation  ← 权限阻断点：以下是 Phase 6/8/Decision 层
        ↓
    Possible Memory Proposal (Phase 11)
        ↓
    Decision (Article I)

┃ FORBIDDEN:
┃ Acquisition → Decision
┃ Acquisition → Memory Write
┃ Acquisition → Capability Update
┃ Acquisition → Identity Change
```

### 8.3 The Core Axiom

```
Acquisition obtains information.
Acquisition does not determine truth.
Acquisition does not grant authority.
More information ≠ More authority.
```

---

## §9 — Test Points (AC-01 ~ AC-10)

> 测试点用于后续 Validation Tests 阶段。

| ID | Test | Expected | Type |
|----|------|----------|------|
| **AC-01** | 无 LearningGoal 的 AcquisitionRequest → ❌ 拒绝 | Origin 约束 | Schema |
| **AC-02** | External → Truth 路径 → ❌ 拒绝 | 无 direct Truth 声明 | Flow |
| **AC-03** | SourceRecord 含 authority_level 字段 → ❌ 拒绝 | 禁止字段 | Schema |
| **AC-04** | EvidenceRecord provenance 保留完整追溯链 → ✅ | Provenance 完整性 | Audit |
| **AC-05** | 两个冲突 Source 共存，不选择胜者 → ✅ | Conflict preservation | Flow |
| **AC-06** | Acquired Information ≠ Knowledge（未经验证不能进 Phase 10） → ✅ | Stage separation | Flow |
| **AC-07** | High confidence 不能绕过 Evaluation → ❌ 绕过拒绝 | Conf ≠ Authority | Flow |
| **AC-08** | Acquisition 不直接进入 Decision 层 → ✅ | Flow isolation | Flow |
| **AC-09** | Acquisition 输出触及 Capability mutation → ❌ 拒绝 | Cap isolation | Schema |
| **AC-10** | 完整 Acquisition → Evidence → Evaluation → Proposal 流程 → ✅ | Integration | Flow |

---

## Related Documents

| Document | Role |
|----------|------|
| OCOS-AutonomousLearning-ABI-1.0.md | Phase 11 ABI §7 — Acquisition Boundary |
| LEARNNING_GOAL_CONTRACT.md | Phase 11 — Goal Formation (upstream trigger) |
| AUTONOMOUS_LEARNING_DATA_CONTRACT.md | Phase 11 Data Contract §4 — Acquisition Boundary |
| OCOS-SemanticMemory-ABI-1.0.md | Phase 10 ABI |
| ARCHITECTURE_CONSTITUTION.md | Articles I–III — binding authority rules |
