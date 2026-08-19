# OpenTale 架构原则

> 冻结于 P4 阶段开始前。此文件定义的所有原则在未经过架构委员会审批前不可修改。

---

## P-001: Observation Requires Consumption (ORC)

**状态：** ✅ 冻结

**一句话定义：**

> 任何长期存在于 OpenTale Core 的观测信号，都必须有明确的消费路径（Consumption Path）；否则，它只是诊断数据，而不是系统能力。

**完整生命周期：**

```
Observation
    ↓
Validation（P4：该信号是否具有预测能力？）
    ↓
Registry（信号被正式记录，含 validation_source、predictive_power）
    ↓
Consumption（至少一个下游模块因该信号做出不同决策）
    ↓
Outcome（该决策改变了什么可测量的结果？）
```

**准入规则：**

一个信号要进入 OpenTale Core，必须回答四个问题：

| # | 问题 | 含义 |
|:-:|:-----|:------|
| 1 | 它观测什么？ | Observation |
| 2 | 如何证明这个观测有预测价值？ | Validation |
| 3 | 哪个模块会因为它改变决策？ | Consumer |
| 4 | 这个决策改变了什么结果？ | Outcome |

如果问题 3 或 4 没有答案，该信号不得进入 Core，应保留在 Experimental 或 Diagnostics 域。

**适用范围：**

此原则适用于 OpenTale 中所有长期保留的观测层资产，包括但不限于：

- Belief Engine 的输出
- CanonLedger 的快照
- ReaderOS 的 Finding
- Director 的 Deviation
- Experience Learner 的学习结果
- 任何未来新增的 Observer/Detector

**当前违反情况（待修复）：**

| 模块 | 观测内容 | 消费方 | 状态 |
|:-----|:---------|:-------|:-----|
| Belief Engine | Character Trust/Fear | — | ⚠️ 有人观测，无人消费 |
| ReaderOS | Finding 数组 | RepairPolicy | ✅ 已消费 |
| Director | DeviationFinding | PolicyCandidate | ✅ 部分消费 |
| CanonLedger | 状态快照 | — | ⚠️ 有人观测，无人消费 |
| Experience Learner | 经验记录 | — | ⚠️ 有人观测，无人消费 |

**违反处理：**

- 已存在的违反（Belief、CanonLedger、Experience）不追溯修复，但新增模块/信号必须遵守。
- 长期违反的模块应标记为 Experimental 或 Diagnostics，不得被任何正式 Pipeline 步骤依赖。

---

## P-002: Evidence is Immutable

**状态：** ✅ 冻结（自 2026-07-09）

事实不可篡改。只记录可观测事件，不记录推断状态。

详见 P4_COMPLETION.md 与 EFFECTIVE_EVIDENCE_CONTRACT.md。

---

## P-003: All Latent States are Inferred

**状态：** ✅ 冻结（自 2026-07-09）

Trust、Fear、Interest 等潜变量不可直接写入，只能由可观测证据推断。

---

## P-004: Planning Targets Evidence, Not Hidden States

**状态：** ✅ 冻结（自 2026-07-09）

Planner 规划的是将产生哪些可观测证据，而不是直接操纵隐藏状态。

---

## P-005: Every Model is Replaceable Because the Protocol is Stable

**状态：** ✅ 冻结（自 2026-07-09）

稳定的是协议，不是实现。任何模型（Belief Engine、Planner、Writer）都可替换。

---

## P-006: Replication Before Intervention

**状态：** ✅ 冻结（自 2026-07-13，原 FP-8）

> Observation → Finding → Replication → Policy → Intervention

适用于 Narrative Budget、RepairPolicy、Belief Calibration、Character Runtime 等所有演化场景。

---

## P-007: Protocol Over Template

**状态：** ✅ 冻结（自 2026-07-09）

系统优先定义稳定的信息契约（Protocol），而非为每个题材编写模板分支。题材差异通过 Protocol 的参数化表达，不通过代码分支表达。

---

## P-008: Validation Backend Must Be Replaceable (VBR)

**状态：** ✅ 冻结（2026-07-14）

**一句话定义：**

> P4 的验证后端是可替换的。P4 协议层只依赖 ValidationBackend Protocol，不依赖任何具体实现。

**理由：**

P4a 阶段使用 RRG 作为验证后端，但 P4b 阶段一定会引入真实读者数据。如果协议层依赖 RRG 的具体接口，替换后端时 Registry 的历史数据将无法与新建数据隔离和校准。

**约束：**

```python
# P4 协议层唯一依赖的抽象
class ValidationBackend(Protocol):
    def evaluate(
        self,
        chapter_id: str,
        findings: list[Finding],
    ) -> ValidationOutcome:
        ...
```

- P4 Registry 不得直接引用 RRG 类型
- Experience Learner 不得区分 Outcome 来源
- 所有验证数据必须携带 `backend_name` 元数据，但消费方不得据此分支决策

**当前实现：**

| Backend | 类型 | 状态 |
|:--------|:-----|:-----|
| RRGBackend | Proxy (P4a) | ✅ 已实现 |
| HumanBackend | External (P4b) | 🔮 未来 |

---

## P-009: Representation Conversion, No Semantic Leakage

**状态：** ✅ 冻结（2026-07-18, BC-003 封顶时确立）

**一句话定义：**

> 每一层只负责一种表示（Representation）到另一种表示（Representation）的转换，不创造属于下一层的语义对象。

**七层链中每一层的一句话职责**

| 层 | 唯一职责 | 输入 | 输出 |
|:---|:---------|:-----|:-----|
| World State | 提供客观事实 | — | 事实序列 |
| POV Compiler | 投影角色可见世界 | World + POV | POV Package |
| Belief Graph Builder | 构建当前信念图 | POV + History + Registry | Belief Graph |
| Belief Compiler | 比较两张信念图并输出 Delta | Graph(t-1) + Graph(t) | Primary Delta |
| Reader Compiler | 将 Delta 映射为体验需求 | Primary Delta | Experience Template |
| ESL Builder | 将体验需求组织为体验序列 | Template + Intent | Experience Sequence |
| Writer | 将体验序列渲染为文本 | Experience Sequence | Draft Text |

**约束含义：**

1. **不创造属于下一层的语义对象：** POV Compiler 不创造 Belief；Builder 不创造 Delta；Reader Compiler 不创造叙事策略。

2. **每层可替换：** 只要输入/输出协议稳定，任何层的实现（Rule / LLM / Neural / Symbolic）都可以独立替换。

3. **接口耦合降低：** 每层只依赖上游的协议，不依赖上游的实现细节。Belief Compiler 不需要知道 Belief 是怎么被提取的。

**适用范围：**

OpenTale 所有新增的编译层必须遵守此原则。任何试图让一层同时完成两种表示转换的设计应被拆分为两层。

---

## P-010: Representation First

**状态：** ✅ 冻结（2026-07-18）

**一句话定义：**

> 系统中的任何新能力，必须首先表现为一种新的 Representation，或者一种已有 Representation 之间的转换；否则，不允许进入生产架构。

**准入门：**

当有人提议新增模块时，必须先回答两个问题：

1. 它对应哪一种 Representation？
2. 它是在进行哪一种 Representation → Representation 的转换？

如果回答不了，那么它应该属于：

- Writer Prompt
- ESL Pattern
- Rule
- Evaluator
- Tooling

而不是新的架构层。

**例：**

| 提议 | P-010 检查 | 判定 |
|:-----|:-----------|:-----|
| 加一个悬念模块 | 悬念是什么 Representation？ | ❌ → Writer Prompt 或 ESL Pattern |
| 加一个节奏控制器 | 节奏是什么 Representation？ | ❌ → ESL Builder 内部优化 |
| 加一个情绪 Agent | 情绪输出是什么 Representation？ | ❌ → Evaluator（Observer） |
| 加一种新的 Reader Memory 类型 | 已有 Reader Memory 表示的子类 | ✅ → 表示扩展 |
| 加一个 Belief Graph 的增量更新协议 | Belief Graph 已有，增量是表示转换 | ✅ → 编译链扩展 |

**三种对象类型的显式区分：**

| 类型 | 是否属于编译链 | 可否创造新 Representation | 示例 |
|:-----|:--------------|:------------------------|:-----|
| **Representation** | ✅ 是 | —（被转换）| Belief Graph / Experience Template |
| **Compiler** | ✅ 是 | ❌ 只转换 | POV Compiler / Belief Compiler |
| **Observer / Evaluator** | ❌ 否 | ❌ 永远不 | ReaderOS / Quality Gate / POV Evaluator |

Observer 和 Evaluator 不创造 Representation。它们只观察已存在的信号。
ReaderOS 永远不是 Compiler。Quality Gate 永远不是 Compiler。

这与系统中已有的「Observer 不阻断生产」原则一脉相承——Observer 可以观察，但不会干预编译链。

---

## 原则变更流程

1. 提出变更 → 2. 架构委员会讨论 → 3. 投票 → 4. 更新此文件并更新版本号

---

当前版本：v1.0（2026-07-18）

---

_此文件与 SOUL.md 同级别，属 OpenTale 架构级约束。_
