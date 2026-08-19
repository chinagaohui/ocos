# CROSS-THEORY AUDIT v1.0

**状态**: Draft
**日期**: 2026-07-22
**审计范围**: INFORMATION_THEORY, PROCESS_THEORY, GOAL_THEORY, DECISION_THEORY, EXECUTION_THEORY, KNOWLEDGE_MODEL, CONSTITUTION, EVENT_SCHEMA, TRACE_ENGINE
**审计方法**: 逐对检查五项 Theory 的概念定义、生命周期、事件、所有权、引用方向

---

## 1. 理论依赖图

```
INFORMATION_THEORY (L0) ─── Layer 0：世界在系统里是什么
    │
    ├── PROCESS_THEORY (L4) ─── Layer 4：认知过程
    │       └── Decision Making ≠ Decision（§3, DECISION_THEORY）
    │
    ├── KNOWLEDGE_MODEL (L2) ─── Layer 2：Verified Information
    │
    ├── GOAL_THEORY（概念层）─── 规范性承诺（Desired Future）
    │       └── Goal → Decision + 停止（§3, GOAL_THEORY）
    │
    ├── DECISION_THEORY（概念层）─── 选择承诺（Commitment）
    │       └── Decision Making（Process）→ Decision（Commitment）→ Action（§3）
    │
    ├── EXECUTION_THEORY（概念层）─── 将承诺转化为世界变化
    │       └── Execution → Action → Observation（§1）
    │
    └── CONSTITUTION（L1）─── 约束规则
```

---

## 2. 核心发现

### 🔴 CT-01: 概念唯一性（INFORMATION_THEORY vs GOAL_THEORY / DECISION_THEORY）

**问题**: `INFORMATION_THEORY.md` §3（Semantic Role 表）将 Goal 定义为 `R_G`、Decision 定义为 `R_D`，意味着它们都是 Information 的子类型。但 `GOAL_THEORY.md` §1 和 `DECISION_THEORY.md` §1 明确冻结 Goal ≠ Information、Decision ≠ Information。

**冲突具体位置**:

| 文档 | 行 | 声明 |
|------|-----|------|
| INFORMATION_THEORY.md §3 | 98 | `Goal = R_G`（语义角色） |
| INFORMATION_THEORY.md §3 | 101 | `Decision = R_D`（语义角色） |
| KNOWLEDGE_MODEL.md §1.3 | 46 | 图表显示 Goal 是 Information 子类型 |
| KNOWLEDGE_MODEL.md §1.3 | 47 | 图表显示 Decision 是 Information 子类型 |
| GOAL_THEORY.md §1 | — | Goal ≠ Information（规范性 vs 描述性） |
| DECISION_THEORY.md §1 | — | Decision ≠ Information（承诺 vs 事实） |
| DECISION_THEORY.md §3 | — | Decision Making 的输出不是 Information，是 Commitment |

**严重等级**: **P1 — 理论冲突**
**影响范围**: INFORMATION_THEORY, KNOWLEDGE_MODEL, GOAL_THEORY, DECISION_THEORY, `information.py`(SemanticRole 枚举)

**修复方案**: INFORMATION_THEORY v2.0 需要移除 `R_G`(Goal) 和 `R_D`(Decision) 语义角色，或改为"可被 Information 引用但不是 Information"的旁注。

---

### 🔴 CT-02: 生命周期一致性（重叠检查）

| 概念 | 生命周期状态机 | 与谁重叠 | 评估 |
|------|-------------|---------|------|
| **Information** | Created→Validated→Referenced→Deprecated→Archived | — | 独立 ✅ |
| **Process** | CREATED→RUNNING→COMPLETED/FAILED | — | 独立 ✅ |
| **Goal** | Created→Active↔Paused→Completed/Failed/Cancelled/Superseded/Expired | — | 独立 ✅（GOAL_THEORY §4） |
| **Decision** | Proposed→Committed→Executed/Revoked/Superseded/Expired | — | 独立 ✅（DECISION_THEORY §4） |
| **Execution** | Pending→Running→Succeeded/Failed/Interrupted/Cancelled | — | 独立 ✅（EXECUTION_THEORY §5） |
| **Constitution Lifecycle** | Acquire→Validate→Retain→Access→Transform→Decay→Archive→Delete | 与 Information Lifecycle 符号不同 | 🟡 符号未对齐（Constitution §12 vs Information §4） |

**结论**: 五个生命周期互不重叠 ✅。Constitution Rule 12 使用的生命周期命名（Acquire→Validate→Retain→Access→Transform→Decay→Archive→Delete）与 INFORMATION_THEORY（Created→Validated→Referenced→Deprecated→Archived）命名不同。语义一致但符号不一致。

---

### 🔴 CT-03: 所有权（Ownership）

| 概念 | 谁创建 | 谁修改 | 谁终止 | 谁引用 | 评估 |
|------|--------|--------|--------|--------|------|
| **Information** | Perception / Process | Lifecycle Engine | Governance / Forgetting | Address | ✅ |
| **Process** | Decision Making 引擎 | 不可修改（frozen） | Process 自身 | Address | ✅ |
| **Goal** | Agent / User / 分解 | Agent / Owner | Agent / Gov | Address | ✅ |
| **Decision** | Decision Making Process | 不可修改 | 外部（Revoke/Supersede） | Decision ID | ✅ |
| **Execution** | Execution Engine | 不可修改 | Execution 自身 | Decision ID | ✅ |
| **Action** | Execution Engine | 不可修改 | Execution 管理器 | Action ID | ✅ |

**发现**: 所有权方向严格单向 ✅。没有发现"谁修改自己"的环。

---

### 🟡 CT-04: 引用关系（Reference Graph）

当前引用方向（`→` = 持有引用）：

```
Goal.goal_id ← Decision.goal_id
                         ↓
Decision.decision_id ← Execution.decision_ref
                         ↓
Execution.action_refs → Action
                         ↓
Action.observation_ref → Observation
                         ↓
Observation → Information (UniversalAddress)
```

**问题 1**: 未明确定义反向引用的合法性（例如 Decision 持有 Goal ID，但 Goal 是否应持有 Decision 列表？）。GOAL_THEORY 明确 Goal 不持有 Decision 列表（§5），但代码中无强制约束。

**问题 2**: `Decision.reasoning: str` 目前是字符串而非 UniversalAddress（abi.py §187）。PROCESS_THEORY §5.2 要求输入输出统一为 Address。这是 Phase 15 已标记但未修复的兼容性问题。

---

### 🟡 CT-05: 事件体系（Event Consistency）

| 事件 | 对应概念 | 平行事件 | 重复/重叠 |
|------|---------|---------|----------|
| `GOAL_SET` | Goal 创建 | — | 与 INFORMATION_TRANSFORMATION 不同轴 ✅ |
| `GOAL_UPDATED` | Goal 状态变更 | — | 独立 ✅ |
| `GOAL_COMPLETED` | Goal 完成 | — | 独立 ✅ |
| `DECISION_FORMED` | Decision（承诺）形成 | — | 与 TRANSFORMATION 不同轴 ✅ |
| `DECISION_VALIDATED` | Decision 验证通过 | — | 独立 ✅ |
| `INFORMATION_TRANSFORMATION_STARTED` | Decision Making（过程）启动 | — | 不同轴 ✅ |
| `INFORMATION_TRANSFORMATION_COMPLETED` | Decision Making 完成 | — | 不同轴 ✅ |
| `INFORMATION_TRANSFORMATION_FAILED` | Decision Making 失败 | — | 不同轴 ✅ |
| `ACTION_SCHEDULED` | Action 调度 | — | 独立 ✅ |
| `GOVERNANCE_APPROVED` | 治理审批 | — | 独立 ✅ |

**结论**: 事件体系在 Decision Making ≠ Decision 分离后已无重复。Legacy 事件（GOAL_*, DECISION_*）与 Phase 15 事件（INFORMATION_TRANSFORMATION_*）各自服务于不同层面 ✅。

**🟡 建议**: v2.0 将命名统一为 `DECISION_FORMED → DECISION_COMMITTED`（更准确的语义描述）。

---

### 🟡 CT-06: Trace 一致性

| Trace 类型 | 记录 API | 对应概念 | 问题 |
|-----------|---------|---------|------|
| `DecisionTrace` | `record_decision_trace()`（传统） | Decision（承诺） | 传统路径 |
| `DecisionTrace` | `record_process_trace()` | Decision Making（过程）→ 映射 | Process 路径 |
| `ReasoningTrace` | `record_process_trace()` | Reasoning Process | 统一 |
| `SimulationTrace` | `record_process_trace()` | Simulation Process | 统一 |

**发现**: `DecisionTrace` 有两类创建路径，但 PROCESS_THEORY §6.4 已明确长期方向为统一入口。当前状态是**已规划但未完成**，不算冲突。

---

### 🔴 CT-07: Constitution 一致性

| 宪法规则 | 对应的 Theory | 一致性 | 备注 |
|---------|-------------|--------|------|
| R1: DECISION_IS_ONLY_ACTION_SOURCE | DECISION_THEORY I3 | ✅ 一致 | DECISION_THEORY 明确复用此规则 |
| R2: EVENT_BUS_IS_ONLY_COMMUNICATION | 全部 | ✅ 一致 | 无冲突 |
| R3: ALL_INPUTS_MUST_BE_OBSERVED | EXECUTION_THEORY I3 | ✅ 一致 | Execution 必须产出 Observation |
| R4: ALL_TRANSITIONS_MUST_BE_LOGGED | PROCESS_THEORY §6 | ✅ 一致 | |
| R5: KNOWLEDGE_CHANGES_REQUIRE_GOVERNANCE | KNOWLEDGE_MODEL §3 | ✅ 一致 | |
| R6: EVERY_ACTION_HAS_DECISION | DECISION_THEORY I3 | ✅ 一致 | |
| R7: SCHEDULING_MUST_BE_DETERMINISTIC | — | ✅ 独立 | 无依赖冲突 |
| R9: PLATFORM_800_LINE_LIMIT | — | ✅ 独立 | 无依赖冲突 |
| R10: KERNEL_NEVER_KNOWS_BUSINESS | 全部 | ✅ 解释一致 | DECISION_THEORY §7 已阐释：ABI 是契约层 |
| R11: RUNTIME_NEVER_KNOWS_KNOWLEDGE | — | ✅ 独立 | |
| R12: INFORMATION_LIFECYCLE_INVARIANT | INFORMATION_THEORY §4 | 🟡 符号未对齐 | 见 CT-02 |
| R13: INFORMATION_CONTROL_INVARIANT | INFORMATION_THEORY §4 | ✅ 一致 | |

**发现**: 基本一致 ✅。仅 R12 生命命名与 INFORMATION_THEORY 不同（8 阶段名 vs 5 状态名），语义一致。

**宪法缺少**: 
- Goal 相关规则（Goal 创建是否需 Governance？—— 需要但没有宪法规则）
- Execution 相关规则（Execution 是否有宪法约束？—— 目前无）

---

### 🟡 CT-08: 抽象层级一致性

| 概念 | 当前层 | 理论归属 | 是否正确 |
|------|--------|---------|---------|
| Information | L0 | 静态对象 | ✅ |
| Process | L4 | 认知转换 | ✅ |
| Goal | 概念层 | 规范性承诺 | ✅（不属于 L0-L4 任何一层，是独立概念） |
| Decision | 概念层 | 选择承诺 | ✅ |
| Execution | 概念层 | 过程性概念 | ✅ |

**发现**: 层级归属正确 ✅。Goal、Decision、Execution 都正确位于概念层（与 Process Theory 的 L4 不冲突，因为"层命名不堆叠"约束禁止的是架构层使用独立 THEORY 命名，而概念层使用 THEORY 是合法的）。

---

### 🔴 CT-09: 依赖方向审计（Dependency Direction）

理想单向依赖：

```
Goal
    ↓
Decision Making (Process)
    ↓
Decision (Commitment)
    ↓
Execution
    ↓
Action → Observation
    ↓
Information
    ↓
Process（下一轮认知）
```

检查反向依赖：

| 反向依赖嫌疑 | 是否存在 | 评估 |
|-------------|---------|------|
| Information 反向依赖 Goal | ❌ 不存在 | ✅ |
| Process 拥有 Goal | ❌ 不存在（Process 引用 Address，不拥有） | ✅ |
| Decision 修改 Information 生命周期 | ❌ 不存在 | ✅ |
| Execution 修改 Goal | ❌ 不存在 | ✅ |
| Execution 修改 Decision | ❌ 不存在（Invariant 2） | ✅ |
| Goal 持有 Decision 列表 | ❌ 不存在（GOAL_THEORY §5 明确否定） | ✅ |
| Decision 持有 Action 列表 | ❌ 不存在 | ✅ |
| Action 拥有 Observation | 🟡 Decision.reasoning: str（非 Address） | 需修复 |

**结论**: 依赖方向严格单向 ✅。唯一需修复的是 `Decision.reasoning: str`（非 Address），这是已知 v2.0 遗留问题（PROCESS_THEORY §8）。

---

## 3. 审计发现汇总

| 编号 | 审计项 | 问题描述 | 级别 | 影响范围 |
|------|--------|---------|------|---------|
| CT-01 | 概念唯一性 | INFORMATION_THEORY 将 Goal/Decision 列为 Semantic Role，与其 Theory 文档矛盾 | **P1** | INFORMATION_THEORY, KNOWLEDGE_MODEL, `information.py` |
| CT-02 | 生命周期 | Constitution R12 生命周期命名与 INFORMATION_THEORY 符号不同（语义一致） | **P3** | constitution.py |
| CT-03 | 所有权 | 无冲突（严格单向） | ✅ | — |
| CT-04 | 引用关系 | `Decision.reasoning: str` 非 Address，不符合同一契约 | **P2** | kernel/abi.py（已知 v2.0） |
| CT-05 | 事件致性 | Decision Making ≠ Decision 分离后事件无重复 | ✅ | — |
| CT-06 | Trace 致性 | DecisionTrace 双路径（已规划统一） | **P3** | trace_engine.py |
| CT-07 | 宪法致性 | 基本一致；宪法缺少 Goal/Execution 约束 | **P3** | constitution.py（可选） |
| CT-08 | 抽象层级 | 全部正确 | ✅ | — |
| CT-09 | 依赖方向 | 严格单向 ✅；仅 `Decision.reasoning: str` 需修复 | **P2** | kernel/abi.py |

---

## 4. 修复建议

### P1: 需要修复（理论冲突）

**CT-01 INFORMATION_THEORY v2.0 更新**:

在 INFORMATION_THEORY.md §3（Semantic Role 表）添加脚注：

> **Goal 和 Decision 在 v1.0 中的语义角色 `R_G` 和 `R_D` 是 legacy 占位。**
> 自 GOAL_THEORY v1.0 和 DECISION_THEORY v1.0 冻结后，Goal 和 Decision 不再被视为 Information 的子类型。
> Goal 是规范性对象（Desired Future），Decision 是选择承诺（Commitment）。
>
> **v2.0 计划**: 移除 `R_G` 和 `R_D` 语义角色。Semantic Role 枚举将只保留 Observation、Memory、Knowledge、Identity、Policy。
> **v1.x 兼容**: `information.py` 中保留 `R_G` 和 `R_D` 但不推荐使用。

同时更新 KNOWLEDGE_MODEL.md §1.3 图表（Goal 和 Decision 不再属于 Information 子树）。

### P2: 应修复但不紧急

**CT-04 / CT-09 `Decision.reasoning: str` → `reasoning_reference: UniversalAddress`**:
- 已在 PROCESS_THEORY §8 v2.0 计划中
- 不影响运行时正确性（当前兼容）

### P3: 可选修复

**CT-02 Constitution R12 命名对齐**:
- 将 `Acquire→Validate→Retain→Access→Transform→Decay→Archive→Delete` 对齐到 `Created→Validated→Referenced→Deprecated→Archived`
- 或反之
- 语义一致，仅符号不同，优先级低

**CT-06 Trace 统一**:
- 已在 PROCESS_THEORY §6.4 长期演进方向中
- v2.0 实施统一 ProcessTrace

**CT-07 Constitution 增加 Goal 规则**（可选）:

> **Rule 14（建议）**: Goal Creation Requires Source Declaration
> 每条 Goal 必须在创建时声明其来源（user / agent_generated / decomposition / external_event / system）。无来源的 Goal 为非法。

---

## 5. 推荐放弃项

| 项目 | 建议 | 原因 |
|------|------|------|
| 宪法 Rule 10 Decision 检查 | 保留现状 | DECISION_THEORY §7 已解释：ABI 是契约层 |
| Semantic Role `R_G` / `R_D` | v2.0 移除 | 与 GOAL/DECISION THEORY 矛盾 |
| `DecisionTrace` 双路径 | 保留现状 | 统一入口已规划（PROCESS_THEORY §6.4） |
| Legacy 事件 GOAL_/DECISION_ | 保留至 v2.0 | 与 TRANSFORMATION 事件不同轴 |

---

## 6. 架构进入一致性阶段确认

Cross-Theory Audit 结果：

| 指标 | 结果 |
|------|------|
| 概念唯一性冲突 | 1 项（P1: Information vs Goal/Decision） |
| 生命周期冲突 | 0 项（命名符号不一致 1 项 P3） |
| 所有权违规 | 0 项 |
| 引用环 | 0 项（1 个非 Address 引用 P2） |
| 事件重复 | 0 项 |
| Trace 双入口 | 1 项（已规划统一 P3） |
| 宪法与理论矛盾 | 0 项 |
| 依赖方向违规 | 0 项 |

**结论**: OCOS 六层理论体系已进入一致性阶段。1 项 P1 问题（Information Theory Semantic Role）和其修复路径明确，其余为已规划的 v2.0 工作。可以进入 Phase 17 能力实现层。

---

## 7. 变更记录

| 版本 | 日期 | 变更 |
|------|------|------|
| v1.0 | 2026-07-22 | 初始 Cross-Theory Audit。9 项审计 + 1 项 P1 发现 + 修复建议 |
