# DECISION THEORY v1.0 (Frozen)

**状态**: ❄️ 冻结
**日期**: 2026-07-22
**所属架构层**: 概念层
**前置冻结**: Information Theory ✅, Process Theory ✅, Goal Theory ✅
**后续依赖**: Execution Theory（Phase 16 下一阶段）
**上游约束**: Goal Invariant 2（Goal 生命周期长于任何 Decision）、Goal Invariant 3（Goal ↔ Decision 一对多）

---

## 1. 本体定义

### 一句话定义

> **Decision 是 Agent 在多个可行方案之间作出的、对后续 Action 具有约束力的选择承诺（Commitment）。**

### 核心否定（已冻结）

| 命题 | 结论 |
|------|------|
| Decision 是 Goal？ | **否**。Goal 是"想达到什么状态"（规范性承诺），Decision 是"在当前状态下选择哪个方案"（选择承诺）。Goal 先于 Decision。 |
| Decision 是 Process？ | **否**。Decision 是**选择承诺本身**，不是做出承诺的过程。（做出承诺的过程是 Decision Making — 见 §3） |
| Decision 是 Action？ | **否**。Decision 是 Action 的授权承诺，但 Decision 本身不执行。 |
| Decision 是 Plan？ | **否**。Plan 是 Decision 的输出（多个被选方案的执行路径），Plan 不是 Decision。 |
| Decision 是世界事实？ | **否**。Decision 不是观察结果（Observation），不是推理结论（Conclusion）。Decision 是一种**承诺**（Commitment），承诺未来按选定的方案行动。 |

### 语义分离（核心冻结）

**Decision（承诺/结果）** 与 **Decision Making（做决定的过程）** 是两回事：

```
Decision Making     →     Decision           →     Action
（过程）                    （承诺）                   （执行）
  │                         │
ProcessType.DECISION        不是 Process，不是 Information
process_type=DECISION       是独立的 Commitment 对象
```

这一分离永久解决了"Decision 是 Process 还是 Information"的 A/B 辩论：

- **Decision Making（过程）** → 属于 Process Foundation（ProcessType.DECISION），使用 TransformProcess 数据模型，触发 INFORMATION_TRANSFORMATION 事件，通过 record_process_trace 记录
- **Decision（承诺/结果）** → Decision Making 过程的输出，是一个独立的 Commitment 对象（当前 abi.py 中的 Decision 类），不是 Information，不是 Process

---

## 2. 三个不变量

> 以下三条不变量是架构宪法级约束。

### Invariant 1 — Decision 必须引用 Goal

没有 Goal，就不存在合法的 Decision。

```
Decision.goal_id ≠ ""     （永远引用一个 Goal）
Goal ↔ Decision = 1:多    （Invariant 3 from Goal Theory）
```

**推论**:
- Decision 从 Goal 获得授权范围
- Decision 不会自我授权
- Decision 的输入边界由 Goal 定义（Goal 是规范性约束）

### Invariant 2 — 一个 Decision 只能承诺一个选择

多个候选方案属于 Decision Making 过程（推理/评估阶段），而不是一个 Decision 同时承诺多个结果。

```
Decision Making 过程中：考虑 N 个方案 ✓
Decision（结果）：选择一个方案 ✓
Decision（结果）：同时承诺 N 个方案 ✗
```

**推论**:
- 如果后续需要对备选方案回退，需要创建新的 Decision（替换旧的）
- Decision 的"选择承诺"是原子性的

### Invariant 3 — Decision 是 Action 的唯一授权来源

保持与宪法 Rule 1（`DECISION_IS_ONLY_ACTION_SOURCE`）一致。

```
没有 Decision → 没有合法的 Action
Action.params.decision_id ≠ ""
```

**推论**:
- PolicyEngine 的 `decision-required` 规则是正确的架构约束
- 任何执行路径必须有一个起源 Decision
- 但不要求每个 Action 对应一个独立的 Decision（一个 Decision 可以授权多个 Action）

---

## 3. Decision 与 Process 的关系

### 双层语义

| 层面 | 名称 | 性质 | 数据模型 | 事件 | Trace |
|------|------|------|---------|------|-------|
| 过程层 | Decision Making | Process | TransformProcess(process_type=DECISION) | INFORMATION_TRANSFORMATION_* | record_process_trace |
| 结果层 | Decision | Commitment | Decision 类（独立对象） | DECISION_FORMED / DECISION_VALIDATED | 作为 Trace 中的引用 |

### 流程映射

```
Decision Making (Process)
    │
    ├── input_addresses: [addr_goal, addr_conclusion, addr_context, addr_policy]
    ├── steps: [evaluate_candidates, assess_risk, select_best]
    │
    └── output_addresses: [addr_decision]
                                │
                                ▼
                         Decision（Commitment 对象）
                            │
                            ├── decision_id
                            ├── goal_id（引用 Goal）
                            ├── selected_option
                            ├── confidence
                            └── status: proposed → committed → executed
```

### 已冻结

- Decision Making 使用 TransformProcess（复用 Process Foundation）
- Decision（结果）是 Process 的输出（不是 Process 本身）
- Decision Making 的输出不是 Information，而是 Commitment 对象（因为 Decision 不是世界事实）
- Process Foundation 的 `INFORMATION_TRANSFORMATION` 事件命名在此场景下实际描述的是"承诺的形成"（v1.x 保留命名）

### 未冻结（留待 Execution Theory）

- Decision → Action 的分解细节
- Decision Making 的具体算法（候选评估、风险分析）

---

## 4. 生命周期（仅语义）

只定义 Decision（承诺）的规范状态。Decision Making（过程）的生命周期复用 ProcessState。

```
Proposed
    ↓
Committed       （已授权 Action 执行）
    ↓
Executed        （承诺兑现，Action 已完成）

终止态（不经过 Executed）:
    Revoked       （被创建者撤销）
    Superseded    （被新 Decision 取代）
    Expired       （超时或失去时效）
```

**状态转换规则**：
- **Proposed → Committed**: 唯一合法执行入口
- **Committed → Executed**: 承诺兑现
- **{Proposed, Committed} → {Revoked, Superseded, Expired}**: 终止态
- **终止态不可逆**

**不冻结**:
- 状态机的实现细节
- 谁负责状态转换
- Governance Validation 的具体流程（属于 Constitution 层）

---

## 5. 与其他概念的关系

只定义关系语义，不定义实现。

```
Goal (Desired Future)
    │
    ├── constrains → Decision Making (Process)
    │                    │
    │                    └── produces → Decision (Commitment)
    │                                    │
    │                                    ├── references → Goal（Invariant 1）
    │                                    ├── authorizes → Action(s)（Invariant 3）
    │                                    ├── may be superseded by → Decision（新）
    │                                    └── contributes to → Trace / Audit
    │
    ▼
Action (Execution)
```

### 关键关系

| 关系 | 说明 |
|------|------|
| Goal → Decision Making | Goal 是 Decision Making Process 的输入（Address 引用） |
| Decision Making → Decision | Process 的输出（不是 Information，是 Commitment） |
| Decision → Goal | Invariant 1：Decision 必须引用 Goal |
| Decision → Action | Invariant 3：Decision 是 Action 的唯一授权来源 |
| Decision → Decision | 一个 Decision 可以被另一个 Decision 取代（Superseded） |
| Decision → Trace | Decision 作为 Trace 的引用目标 |
| Decision Making ↔ Process | Process Foundation 已覆盖 |

---

## 6. Success/Failure

Decision 自己不判断执行是否成功。Decision 只承诺"选择了什么"。

```
Decision.SuccessCriterion
    ── 表达了"选择了哪个方案"（Committed）
    ── 不表达"执行是否成功"（属于 Execution / Evaluation）
```

**已冻结**:
- Decision 的"成功" = 完成从 Proposed 到 Committed 的转换
- Decision 的"失败" = 进入 Revoked / Superseded / Expired 终止态
- Decision 不判断"被选方案的执行结果"（执行失败不意味 Decision 失败 — 这是 Goal Invariant 2 的推论）

**执行失败时的归属**:
```
Goal（不变）
    ├── Decision A → committed → Action failed
    ├── Decision A → revoked（因为发现不可行）
    ├── Decision B → committed → Action succeeded
    └── Goal → completed
```

Decision 的"执行失败"实际上是一个新的 Observation → Reasoning → Decision 迭代，而不是 Decision 自身状态变化。

---

## 7. Impact：审计发现的分辨

Decision Making ≠ Decision 的分离直接解决了此前 Decision Audit v1.0 的困惑：

| 审计发现 | 原困惑 | 本理论中的答案 |
|---------|--------|---------------|
| F1: Rule 10 宪法冲突 | Decision 在 Kernel ABI 是否违规？ | Decision（承诺/结果）在 ABI 是契约（不被视为业务实现）。Decision Making 使用 Process Foundation。两者都不违反。 |
| F2: 身份不明 | Decision 是 Information 还是 Process？ | 都不是。Decision（结果）是 Commitment。 |
| F3: 生命周期错位 | Decision.status vs ProcessState | Decision.status 是承诺状态，ProcessState 是过程状态。两者不同轴。 |
| F4: Trace 双轨 | record_decision_trace vs record_process_trace | record_process_trace 记录 Decision Making 过程。record_decision_trace 记录 Decision（结果）承诺。两条 Trace 通过 decision_id 关联。 |
| F5: Event 双轨 | DECISION_FORMED vs TRANSFORMATION | DECISION_FORMED 对应 Decision（承诺结果）的创建。TRANSFORMATION 对应 Decision Making（过程）的执行。两个不同层面。 |

---

## 8. 变更记录

| 版本 | 日期 | 变更 |
|------|------|------|
| v1.0 | 2026-07-22 | ❄️ 冻结。本体定义 + Decision Making ≠ Decision + 三不变量 + 生命周期语义 + 关系图 + Success/Failure 边界 |
