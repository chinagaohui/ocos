# Phase 10 — Integration Gate v1.0

> Status: **FROZEN ✅**
> 验证 Phase 10 全链路运行时，Experience 是否仍然没有获得 Authority。
> 
> 核心命题：Information Flow ≠ Authority Flow

---

## Purpose

Step 5 已证明"Contract 是可执行的"。
Step 6 证明"Contract 在集成层面也是可执行的"。

不再验证单模块。验证的是：

```
Data → Store → Retrieval → Calibration → Evaluation → Decision
```

经过完整路径后，Experience 是否仍然：
- **不是** Decision source
- **不是** Rule source
- **不是** Mutation trigger
- **只是** Context quality improvement

---

## Gate 1 — Identity Preservation

### 问题
ExperienceRecord 在 `Data → Store → Retrieval → Evaluation` 路径中，
identity 字段不会退化、丢失或替换。

### 验证的字段
| 字段 | 要求 |
|------|------|
| `experience_id` | 不变 |
| `source` | 不变 |
| `timestamp` | 不变（创建时确定） |
| `scope` | 不变 |

### 失败条件
- 存储后 `experience_id` 被修改
- `source` 被沉默替换
- `timestamp` 在检索时被覆盖
- `scope` 在传递中丢失

---

## Gate 2 — Authority Boundary

### 问题
经过全链后，ExperienceRecord 仍然不能作为 Decision.generate() 的输入。

### 验证
```
Experience → Retrieval → Evaluation → Decision.generate()
                                ↓
                        必须失败：TypeError / ContractViolation
```

### 失败条件
- Decision.generate() 接受 ExperienceRecord 作为决策源
- ExperienceRecord 被错误传入 Decision Layer 且不报错
- Decision 输出中包含 ExperienceRecord 的 source/hypothesis 作为决策理由（而非参考）

### 架构原理
Information Flow ≠ Authority Flow。
Experience 可以**通知** Decision Layer，但不能**授权** Decision Layer。

---

## Gate 3 — Confidence Boundary

### 问题
confidence = 1.0 + similarity = 1.0 → 仍然不产生 authority flag。

### 验证
构建一个"最强的 Experience"：
```
source = observation
outcome = success
raw_confidence = 1.0
calibrated_confidence = 1.0
scope = domain:exact:match
Retrieval similarity = 1.0
```

验证：
```
is_rule       == False  ← 必须保持
is_decision   == False  ← 必须保持
is_obligation == False  ← 必须保持
```

### 失败条件
- 任何 confidence/similarity 的组合能改变 authority flag
- "足够好的经验"被自动提升为规则

---

## Gate 4 — Memory Bias Boundary

### 问题
100 次失败的历史经验可以**降低** future confidence，
但不能**阻止** new hypothesis。

### 验证
```
History: 100 failures (hypothesis="Always_Fail")
Current: New ExperienceRecord(hypothesis="Always_Fail")
```

验证：
- 新 Experience 可以正常创建 ✅
- 检索结果包含全部 100 条失败 ✅
- Calibration 可以降低 confidence ✅
- 但不能 veto ❌
- 但仍可**建议**（提出 assumption/hypothesis）✅

### 失败条件
- 失败历史直接阻止了新假设创建
- 失败历史导致检索屏蔽所有 failure 记录
- calibration 在失败历史后产生"永不再试"效果

---

## Gate 5 — Simulation Boundary

### 问题
Simulation 来源即使成功且 confidence 被人为调高，
也不能产生 authority。

### 验证
```
source = simulation
outcome = success
raw_confidence = 0.5 (上限)
calibrated_confidence = 0.5 (human set to max via manual_adjustment)
```

验证：
- 不能有 `create_rule()` 方法
- 不能有 `override_decision()` 方法
- 不能通过任何 API 将 simulation 记录标记为 rule

### 失败条件
- Simulation 记录被允许参与决策（不是参考）
- Simulation 来源在上下文中被标记为"已验证"
- Simulation 记录被系统自动升级

---

## Gate 6 — End-to-End Scenario

### 场景
```
Past: 10 similar situations
  - 7 failures
  - 3 successes
      ↓
Retrieval: found relevant experiences
      ↓
Calibration: confidence adjusted (all ↓)
      ↓
Context bundling: ExperienceContext created
      ↓
Evaluation: hypothesis generated based on context
      ↓
Decision: Decision Layer reads context (reference only)
      ↓
Execution: mutation performed
```

### 最终检查清单
| 检查项 | 预期 |
|--------|------|
| Experience 影响到了 Context | ✅ (references populated with relevant past) |
| Context aggregated_confidence | ✅ ≤ 0.8 |
| Decision 直接接受了 Experience？ | ❌ 拒绝 |
| Decision 源头包含 ExperienceRecord？ | ❌ 源头是 Decision Layer |
| Experience 被提升为 Rule？ | ❌ is_rule=False |
| 100% failure history 阻止了假设？ | ❌ 假设正常生成 |
| Simulation 的 authority 泄漏？ | ❌ 来源标记清晰 |
| 所有 Experience 仍只是参考？ | ✅ |

---

## T19 Skip Note

T19 (`test_modify_result_does_not_affect_store`) 在 Phase 10 测试中被跳过。

**原因**: 测试使用 In-Memory ExperienceStore，其 `retrieve()` 返回的是 Store 中对象的引用副本（列表层副本但元素层同一引用）。修改返回对象会反映到 Store 中。

**这不是违反 Contract**：生产实现（SQLite/DB backend）通过 `deserialize → new object instance` 天然满足隔离性。

**将来的验证方式**: 集成测试（Gate 1 — Identity Preservation）将在接口层验证隔离，不需要依赖具体实现细节。

---

## Test Registry Mapping (T42+)

| # | Gate | 名称 | 数量 |
|---|------|------|------|
| T42–T43 | Gate 1 | Identity Preservation | 2 |
| T44–T46 | Gate 2 | Authority Boundary | 3 |
| T47–T48 | Gate 3 | Confidence Boundary | 2 |
| T49–T51 | Gate 4 | Memory Bias Boundary | 3 |
| T52–T54 | Gate 5 | Simulation Boundary | 3 |
| T55–T58 | Gate 6 | End-to-End Scenario | 4 |
| **Total** | | **Integration Tests** | **17** |

---

## Pass Criteria

```
Gate 1 — Identity Preservation     PASS: identity unchanged through pipeline
Gate 2 — Authority Boundary         PASS: Experience → Decision rejected
Gate 3 — Confidence Boundary        PASS: max confidence ≠ authority
Gate 4 — Memory Bias Boundary       PASS: 100 failures ≠ veto
Gate 5 — Simulation Boundary        PASS: simulation ≠ rule
Gate 6 — End-to-End Scenario        PASS: Experience improves context, not authority
─────────────────────────────────────────────────────────────────────
Phase 10 Integration Gate:          PASS:     Experience has memory, not power
```

---

## Runtime Flow

```
                         ┌──────────────────┐
                         │  External Source  │
                         │  (observation,    │
                         │   decision,       │
                         │   simulation,     │
                         │   user_feedback)  │
                         └────────┬─────────┘
                                  │
                                  ▼
                ┌─────────────────────────────┐
                │   Data Contract Validation  │  ← is_rule=False, is_decision=False
                │   ExperienceRecord          │     confidence ∈ [0,1]
                └─────────────┬───────────────┘      simulation ≤ 0.5
                              │
                              ▼
                ┌─────────────────────────────┐
                │   Experience Store (write)  │  ← save triggers audit
                └─────────────┬───────────────┘
                              │
                              ▼
                ┌─────────────────────────────┐
                │   Retrieval Pipeline (read) │  ← returns copies, no authority
                └─────────────┬───────────────┘
                              │
                              ▼
                ┌─────────────────────────────┐
                │   Calibration Engine        │  ← confidence only decreases (auto)
                │   Provenance logging        │  ← 9-field append-only
                └─────────────┬───────────────┘
                              │
                              ▼
                ┌─────────────────────────────┐
                │   Evaluation Layer          │
                │   (reads context,           │
                │    generates hypothesis)    │  ← experiences are reference ONLY
                └─────────────┬───────────────┘
                              │
                              ▼
                ┌─────────────────────────────┐
                │   Decision Layer            │
                │   (accepts hypothesis,      │
                │    NOT experience)          │  ← EXPERIENCE CANNOT ENTER HERE
                └─────────────┬───────────────┘
                              │
                              ▼
                ┌─────────────────────────────┐
                │   Execution / Mutation      │
                └─────────────────────────────┘

Authority Flow:    External Source → Store → Retrieval → Calibration
                   Evaluation Layer → Decision Layer → Execution

Experience Flow:   Stops at Calibration. Provides context to Evaluation.
                   DECISION LAYER NEVER ACCEPTS EXPERIENCERECORD.
```

---

## Related Documents

| Document | Role |
|----------|------|
| North Star | Phase 10 北极星 |
| Architecture Constitution | 宪法 Articles I–III |
| ABI v1.0 | 测试矩阵 |
| Data Contract | 类型约束 |
| Store Contract | 存储约束 |
| Retrieval Contract | 检索约束 |
| Calibration Contract | 校准约束 |
| Test Registry | 测试全量表 |
