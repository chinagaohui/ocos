# GOAL THEORY v1.0 (Frozen)

**状态**: ❄️ 冻结
**日期**: 2026-07-22
**所属架构层**: 概念层（非架构层，因此使用 THEORY 命名合法）
**前置冻结**: Information Theory ✅, Process Theory ✅, Memory Audit ✅
**后续依赖**: DECISION_THEORY（Phase 16 下一阶段）
**不依赖**: Planning Theory, Execution Theory（Goal Theory 的链条到此为止）

---

## 1. 本体定义

### 一句话定义

> **Goal 是 Agent 对未来期望状态的规范性承诺（Normative Commitment），用于约束后续 Decision，而不是对世界事实的描述。**

### 核心结论（已冻结）

| 命题 | 结论 |
|------|------|
| Goal 是 Information？ | **否**。Goal 是**规范性对象**（Desired Future），Information 是**描述性对象**（Observed/Derived State）。两者属于不同范畴。 |
| Goal 是 Process？ | **否**。`ProcessType` 中不需要 `GOAL`。Goal 作为 Process 的输入，而非 Process 本身。四个"不堆叠"原则已涵盖此约束。 |
| Goal 是 Decision？ | **否**。Goal 约束 Decision，但不等于 Decision。 |
| Goal 生命周期？ | **独立存在**。与 Information Lifecycle、Process Lifecycle 独立。 |
| Goal 描述实现方式？ | **永不**。Goal 只回答"想达到什么状态"，不回答"怎么做到"。 |

---

## 2. 三个不变量

> 以下三条不变量是架构宪法级约束。任何实现违反其一，即视为架构违规。

### Invariant 1 — Goal 只回答 What，不回答 How

Goal 只描述：

```
想达到什么状态（What should be true）
```

Goal 永远不描述：

```
怎么做到（How）
```

**正确示例**: `Goal: 获得完整地图`
**错误示例**: `Goal: 去调用 execute_engine`

"如何实现"属于 Decision 和 Planning 的职责。

### Invariant 2 — Goal 生命周期长于任何 Decision

一次 Decision 的失败**不终止**其来源 Goal。

```
Goal
    ├── Decision A → failed → retry
    ├── Decision B → failed → retry
    └── Decision C → succeeded
```

**推论**:
- Goal 从创建到结束可能经历多次 Decision 迭代
- Decision 的失败不是 Goal 的失败（除非 Goal 自身判定为不可达）
- Goal 的状态独立于 Decision 的状态

### Invariant 3 — Goal 可以产生多个 Decision（一对多）

Goal ↔ Decision 是 **一对多** 关系。系统不支持"一个 Goal 只能创建一次 Decision"的语义。

```
Goal 可以：
    ├── 产生多个 Decision（串行或并行）
    ├── 失败的 Decision 不终止 Goal
    └── 被新的 Decision 取代（旧的 Decision 标记为 superseded）
```

**架构含义**:
- Agent 的重规划、自修复、多轮尝试、策略切换能力依赖此不变量
- 如果 Goal ↔ Decision 是一对一，Agent 无法重试或切换策略
- `Decision.goal_id` 引用 Goal，但 Goal 不持有 Decision 列表（防止状态膨胀）

---

## 3. Goal 的边界

Goal Theory 的链条**停止于 Decision**。不讨论其下游。

```
Goal Theory 的边界
────────────────
Goal
    ↓
Decision      # Goal 驱动 Decision，但不规定如何实现
```

**不讨论**:
- **Plan**: 属于 Planning Theory
- **Task**: 属于 Execution / Planning Theory
- **Action**: 属于 Execution Theory
- **Execution**: 属于 Execution Theory

**允许提及但不冻结**（仅在边界章节说明关系）：

```
Goal → Decision → (Plan → Task → Action)
                  ↑_____________________|
                  属于 Planning / Execution Theory
```

---

## 4. 生命周期（仅语义，不冻结实现）

Goal 可以处于以下规范状态。此处只冻结"Goal 有哪些合法状态"，不冻结 ContextManager 的实现方式。

```
Created
    ↓
Active ←────────┐
    ↓            │
    ├── Paused ──┘  （可恢复）
    │
    ├── Completed    （达成 → 产生 Memory）
    ├── Failed       （不可达）
    ├── Cancelled    （被创建者撤销）
    ├── Superseded   （被新 Goal 替代 → 旧的自动失效）
    └── Expired      （超时或失去时效）
```

**状态转换规则**（仅语义约束）:
- **Created → Active**: 唯一合法入口
- **Active ↔ Paused**: 可双向切换（唯一可逆转换）
- **Active → {Completed, Failed, Cancelled, Superseded, Expired}**: 不可逆终止
- **Paused → {Cancelled, Superseded}**: 非活跃状态下允许部分终止

**不冻结**:
- ContextManager 如何存储 Goal
- `dataclasses.replace` 还是可变对象
- 谁负责状态转换（Agent / User / Policy）

---

## 5. Goal 与其他对象的关系

只定义关系语义，不定义实现。

```
Goal
    │
    ├── constrains → Decision(s)
    │       Goal 约束 Decision 的输入边界和授权范围。
    │       Decision.goal_id 引用 Goal，但 Goal 不持有 Decision 列表。
    │       Goal ↔ Decision 是一对多（Invariant 3）。
    │
    ├── owned by → Agent / User / System
    │       Goal 的 owner 决定谁有权限修改或删除它。
    │       Goal.source 记录来源（user / agent_generated / decomposition / external_event / system）。
    │
    ├── referenced by → Process
    │       Goal 可以作为 Process（尤其是 Reasoning Process）的输入。
    │       Goal 本身不是 Process，也不拥有 Process。
    │
    ├── produced by → Goal 设定
    │       Goal 可以被创建（用户指定、Agent 自主生成、上级分解、事件触发）。
    │       不允许 Goal 自我创建 — Goal 的创建者必须外在于 Goal 自身。
    │
    └── terminated → Memory / Knowledge
            Goal 完成时产生 Memory 和/或 Knowledge。
            Goal 的完成结果是 Information（描述性），但 Goal 自身不是 Information。
```

---

## 6. 成功标准（Success Criterion）

Goal 只定义"什么叫成功"，不负责"判断是否成功"。

```
Goal.SuccessCriterion
    ↓（由 Evaluation / Verification Process 判断）
是否达到目标
```

**已冻结**:
- Goal 可以携带成功标准的声明式描述（如"地图覆盖率 > 90%"）
- Goal 不执行成功判断（那属于 Evaluation / Verification）
- 判断成功的 Process 独立于 Goal 自身

**未冻结**:
- 成功标准的数据格式（属于 DECISION_THEORY 或 EVALUATION_THEORY）
- 谁来执行判断（Agent / 外部系统）

---

## 7. 与宪法关系

Goal Theory 冻结后，宪法 `KERNEL_NEVER_KNOWS_BUSINESS` 的适用范围：

- `Goal` 类定义在 ABI（契约层），视为通信契约而非业务实现
- v1.x 不迁移 Goal 出 ABI
- v2.0 视架构重构决定是否迁移到 `models/`

---

## 8. 变更记录

| 版本 | 日期 | 变更 |
|------|------|------|
| v1.0 | 2026-07-22 | ❄️ 冻结。本体定义 + 三不变量 + 边界 + 生命周期语义 + 关系图 + 成功标准 |
