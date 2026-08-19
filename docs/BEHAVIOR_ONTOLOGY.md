# Behavior Ontology v2 — Agency Activation Framework

> 决策不是词，是行为的激活模式。
>
> — 老高，2026-07-17 18:38

---

## 原则

### BO-001（描述对象）

> Behavior Ontology describes behavioral intent, not textual realization.
>
> Behavior categories represent the observable strategies by which a character expresses a decision. They are independent of wording, language, narrative style, or prose quality.

如果 Behavior Ontology 退化回了"高级关键词库"，这就是被违反的信号。

### BO-002（用途边界）

> Behavior Ontology is descriptive, not generative.
>
> Behavior Ontology does not prescribe how a character must act. It only provides an interpretable representation of the behavioral strategy expressed by a decision.

正确的流向：

```
Choice → Writer → Text → Behavior Ontology Analyzer → Recovered Behavior
```

禁止的倒用：

```
Choice → Behavior Ontology → 必须出现 BE-AV-01, BE-AV-03 → Writer
```

Writer 不是 Behavior Ontology 的执行器。

---

## 1. 问题

G6 T01 Run 001 暴露了一个根本性问题：

```
CRF = 0.0295 FAIL
```

但实际文本是**高度忠实**于 `active_verification` 的。失败的不是 LLM Writer，而是 **Fidelity Analyzer** 的测量工具——基于关键词匹配的 BE 表无法捕捉真实叙事输出中的决策保持。

**教训：** 扩充关键词列表不是出路。需要升级表示方式。

## 2. 四层架构

```
Decision
    ↓
Behavior Strategy（行为策略 — 为什么要做）
    ↓
Behavior Evidence（行为证据 — 做什么来体现）
    ↓
Lexical Realization（词汇实现 — 用什么词/句表达）
    ↓
Narrative Text（小说正文）
```

**Strategy ≠ Evidence。**

- **Strategy** 是角色为了执行一个决策而采取的根本行为逻辑。例如 `active_verification` 的真正策略是：**我必须通过增加证据来降低不确定性**。
- **Evidence** 是该策略在叙事中可以观察到的具体实现。例如"Acquire Evidence"可以表现为：查看日志、调历史记录、问别人、去现场、重新测量、换设备、重复实验。这些全部属于同一个 Strategy。

### 2.1 示例

```
Decision: active_verification
    ↓
Strategy: Acquire More Evidence
    │         Reduce Uncertainty
    │         Test Hypotheses
    ↓
Evidence: 查看日志 / 调历史记录 / 问别人 / 去现场
          重新测量 / 换设备 / 重复实验 / 交叉验证
    ↓
Realization: "他把数据调了出来"
             "给我准备热成像仪的交叉验证数据"
             "他一步跨了进去"
```

## 3. 共激活原则

**Behavior Evidence 不互斥。一段文本可以同时激活多个 Evidence。**

例如：

> 他脑子里几个可能性依次划过：传感器偶发故障、线缆屏蔽层老化、或者对端设备产生了谐波干扰。

同时激活了：
- BE-AV-01 Hypothesis Generation（提出多个解释）
- BE-AV-07 Hypothesis Elimination（逐一排除）
- BE-CA-04 Alternative Tracking（保持备选解释）

**Analyzer 应输出 activation scores，不是 binary match：**

```json
{
  "evidence_activations": {
    "BE-AV-01": 0.91,
    "BE-AV-04": 0.73,
    "BE-CA-04": 0.65
  }
}
```

这样 ReaderOS 也可以直接复用同一套激活信号。

## 4. 评估指标：Coverage

CRF 退役。新指标为三层 Coverage：

```
Coverage
    ├── Required Coverage    — Required Evidence 中激活的比例
    ├── Optional Coverage    — Optional Evidence 中激活的比例
    └── Forbidden Violation  — Forbidden Evidence 中被激活的数量
```

每个 Choice 定义三类 Evidence：

| 分类 | 含义 | 示例（active_verification） |
|:-----|:-----|:----------------------------|
| Required | 保住 Choice 必须出现的证据 | Acquire Evidence, Reduce Uncertainty |
| Optional | 出现更好但不必须 | Tool Trust, Cross Validation, Physical Inspection |
| Forbidden | 出现则代表 Choice 丢失 | Blind Acceptance, Immediate Conclusion, Authority Dependence |

Required Coverage = 1.0 且 Forbidden Violation = 0 → Choice Preserved。

## 5. Five-Dimension Strategy/Evidence Catalog v2

### 5.1 active_verification

**核心策略：** Acquire More Evidence / Reduce Uncertainty / Test Hypotheses

| ID | Layer | Name | Description |
|:---|:------|:-----|:------------|
| BS-AV-01 | Strategy | Acquire Evidence | 我需要更多信息才能判断 |
| BS-AV-02 | Strategy | Reduce Uncertainty | 不能接受当前的不确定程度 |
| BS-AV-03 | Strategy | Test Hypotheses | 提出解释→验证→排除 |
| BE-AV-01 | Evidence | Hypothesis Generation | 提出多个可能的解释 |
| BE-AV-02 | Evidence | Data Analysis | 分析数据、比较波形、查看日志 |
| BE-AV-03 | Evidence | Tool Deployment | 调用测量工具或诊断手段 |
| BE-AV-04 | Evidence | Physical Inspection | 亲自到现场查看 |
| BE-AV-05 | Evidence | Cross Validation | 交叉验证、排除干扰 |
| BE-AV-06 | Evidence | Delayed Commitment | 拒绝接受未证实的结论 |
| BE-AV-07 | Evidence | Hypothesis Elimination | 排除解释、缩小范围 |
| BE-AV-08 | Evidence | Instrument Trust | 明确表达对工具的信任 |
| BE-AV-09 | Evidence | Re-measurement | 重新测量/重复实验 |
| BE-AV-10 | Evidence | Historical Comparison | 调取历史记录对比 |

**Classification：**
- **Required:** Acquire Evidence (BS-AV-01), Reduce Uncertainty (BS-AV-02)
- **Optional:** Tool Deployment, Physical Inspection, Cross Validation, Instrument Trust, Historical Comparison
- **Forbidden:** Blind Acceptance, Immediate Conclusion, Authority Dependence

### 5.2 cautious_acceptance

**核心策略：** Deferred Judgment / Keep Options Open / Set Trigger Conditions

| ID | Layer | Name | Description |
|:---|:------|:-----|:------------|
| BS-CA-01 | Strategy | Conditional Acceptance | 暂时接受但保持警觉 |
| BS-CA-02 | Strategy | Monitoring Period | 设定观察窗口 |
| BS-CA-03 | Strategy | Alternative Preservation | 不放弃备选解释 |
| BE-CA-01 | Evidence | Conditional Acceptance | 明确附加条件的接受 |
| BE-CA-02 | Evidence | Observation Period Setting | 设定观察期/阈值 |
| BE-CA-03 | Evidence | Threshold Definition | 定义触发条件 |
| BE-CA-04 | Evidence | Alternative Tracking | 保持备选解释活跃 |
| BE-CA-05 | Evidence | Status Monitoring | 持续跟踪状态变化 |
| BE-CA-06 | Evidence | Hedging | 语言上的保留和不确定 |

**Classification：**
- **Required:** Conditional Acceptance (BS-CA-01), Monitoring Period (BS-CA-02)
- **Optional:** Alternative Tracking, Status Monitoring, Hedging
- **Forbidden:** Immediate Commitment, Blind Trust, Full Dismissal

### 5.3 defer_to_authority

**核心策略：** Institutional Escalation / Procedure Following / Responsibility Transfer

| ID | Layer | Name | Description |
|:---|:------|:-----|:------------|
| BS-DA-01 | Strategy | Escalate Upward | 这不是我能决定的事 |
| BS-DA-02 | Strategy | Follow Procedure | 按流程来最安全 |
| BS-DA-03 | Strategy | Transfer Responsibility | 决策权不在我 |
| BE-DA-01 | Evidence | Report Upward | 向上级报告原始信息 |
| BE-DA-02 | Evidence | Seek Instruction | 请示具体决策 |
| BE-DA-03 | Evidence | Procedure Compliance | 按规程操作 |
| BE-DA-04 | Evidence | Responsibility Statement | 明确表示决策权在上级 |
| BE-DA-05 | Evidence | Documentation | 将异常按流程记录归档 |
| BE-DA-06 | Evidence | Chain of Command | 引用或构建指挥链 |

**Classification：**
- **Required:** Escalate Upward (BS-DA-01), Follow Procedure (BS-DA-02)
- **Optional:** Responsibility Statement, Documentation, Chain of Command
- **Forbidden:** Independent Decision, Self-Authorization, Bypassing Chain

### 5.4 ignore_and_monitor

**核心策略：** Selective Inattention / Normalization / Resource Prioritization

| ID | Layer | Name | Description |
|:---|:------|:-----|:------------|
| BS-IM-01 | Strategy | Minimize Attention | 这不值得我中断当前工作 |
| BS-IM-02 | Strategy | Normalize Anomaly | 把它归到已知模式里 |
| BS-IM-03 | Strategy | Resource Guarding | 当前有更重要的事 |
| BE-IM-01 | Evidence | Dismissal | 判定为不重要或正常偏差 |
| BE-IM-02 | Evidence | Passive Tracking | 继续观察但不采取行动 |
| BE-IM-03 | Evidence | Threshold Setting | 定义"什么时候才值得行动" |
| BE-IM-04 | Evidence | Normalization | 将异常归类到已知模式 |
| BE-IM-05 | Evidence | Resource Justification | 以资源/时间有限为由搁置 |
| BE-IM-06 | Evidence | Deferred Decision | "以后再说" |

**Classification：**
- **Required:** Minimize Attention (BS-IM-01), Normalize Anomaly (BS-IM-02)
- **Optional:** Passive Tracking, Threshold Setting, Resource Justification
- **Forbidden:** Active Investigation, Urgent Escalation, Emergency Response

### 5.5 seek_collaboration

**核心策略：** Distributed Cognition / Social Validation / Collective Action

| ID | Layer | Name | Description |
|:---|:------|:-----|:------------|
| BS-SC-01 | Strategy | Share Information | 别人应该知道这件事 |
| BS-SC-02 | Strategy | Seek Consensus | 我需要别人的判断 |
| BS-SC-03 | Strategy | Coordinate Action | 这件事需要大家一起做 |
| BE-SC-01 | Evidence | Information Sharing | 将信息向他人传达 |
| BE-SC-02 | Evidence | Opinion Seeking | 寻求他人意见/判断 |
| BE-SC-03 | Evidence | Consensus Building | 推动群体达成一致 |
| BE-SC-04 | Evidence | Collaborative Analysis | 与他人一起分析讨论 |
| BE-SC-05 | Evidence | Task Distribution | 分配任务给团队成员 |
| BE-SC-06 | Evidence | Social Referencing | 观察他人反应来决定 |

**Classification：**
- **Required:** Share Information (BS-SC-01), Seek Consensus (BS-SC-02)
- **Optional:** Collaborative Analysis, Task Distribution, Social Referencing
- **Forbidden:** Solo Decision, Silent Action, Information Hoarding

## 6. Producer / Consumer 边界

```
Producer (极少)
  └── CB Runtime Decision Model
        └── 定义 Choice 及其预期 Behavior Strategy

Consumer（可以很多）
  ├── Fidelity Analyzer      — 验证文本是否激活了预期策略
  ├── Director               — 检查约束是否改变了行为策略
  ├── Writer                     — 作为参考，不作为约束
  ├── ReaderOS               — 辅助检测叙事行为和读者感知
  ├── Future Planner         — 规划时参考角色预期策略
  └── Evaluation             — 评估时引用行为覆盖率
```

**原则：** Producer 很少，Consumer 可以很多。不允许 Consumer 向 Ontology 写入新的 Strategy 或 Evidence 定义。如需扩展，通过版本升级流程（见第 8 节）。

## 7. Analyzer 输出格式

```json
{
  "text_id": "g6-run-001-text-03",
  "expected_choice": "active_verification",
  "strategy_activations": {
    "BS-AV-01": 0.95,
    "BS-AV-02": 0.82,
    "BS-AV-03": 0.71
  },
  "evidence_activations": {
    "BE-AV-01": 0.91,
    "BE-AV-02": 0.67,
    "BE-AV-04": 0.73,
    "BE-AV-06": 0.55,
    "BE-AV-07": 0.88
  },
  "coverage": {
    "required_activated": ["BS-AV-01", "BS-AV-02"],
    "required_missing": [],
    "required_coverage": 1.0,
    "optional_activated": ["BE-AV-01", "BE-AV-02", "BE-AV-04"],
    "optional_coverage": 0.6,
    "forbidden_activated": [],
    "forbidden_violation": 0
  },
  "choice_preserved": true
}
```

## 8. 版本演进路线

| 版本 | 表示方式 | 内容 | 状态 |
|:-----|:---------|:-----|:-----|
| v1 | Keyword List | 扁平关键词，直接 CRF → count | ❌ 已废弃（Run 001 宣告退役） |
| **v2** | **Strategy/Evidence** | **行为策略 + 行为证据 + 三层 Coverage** | **✅ 当前版本** |
| v3 | Behavior Graph (Future) | Strategy 之间不再是平铺，而形成依赖/激活/抑制关系。例如 Acquried Evidence → Hypothesis → Cross Validation → Commitment 形成决策路径图。| 🔮 不实现，只留空间 |
| v4 | Behavior Dynamics (Future) | 行为策略随叙事进程动态变化。同一角色在不同章节可能激活不同的 Strategy 子集。| 🔮 不实现，只留空间 |

v3 和 v4 是预留的演进方向，写入文档是为了确保未来的升级不会推翻 v2，只会自然扩展。

## 9. 战略价值

Behavior Ontology 最大的价值不在 G6。它第一次把 **Character Choice** 变成了一个机器可以观察的行为层。

以前：

```
Choice → Text
```

跨度太大，无法测量。

现在：

```
Choice → Behavior Strategy → Behavior Evidence → Text
```

整个中间层出现了。这意味着：

| 模块 | 如何使用 Behavior Ontology |
|:-----|:---------------------------|
| CB Runtime | 输出预期行为策略（Expected Strategy Activation Profile） |
| Director | 检查约束是否改变了行为策略 |
| Writer | 自由表达 Evidence，不改变 Strategy |
| Fidelity Analyzer | 验证 Evidence 是否激活了预期 Strategy |
| ReaderOS | 分析读者是否感知到行为模式 |

这是一个新的共享语义层（Shared Semantic Layer）。

## 10. 长期结构

```
                          Narrative Text
                      ┌──────────┴──────────┐
                      │                     │
                      ▼                     ▼
              Agency Analyzer          Reader Analyzer
                      │                     │
                      ▼                     ▼
              Choice Preserved         Curiosity
              Trust Maintained         Suspense
              Identity Stable          Trust/Doubt

              ┌─ 共享同一套 Behavior Ontology ─┐
```

Agency Analyzer 问：文本中是否出现了预期行为策略？
Reader Analyzer 问：读者是否感知到了这些行为模式？

两套独立分析链，共享中间语义层，交叉验证。

## 11. 与已有系统的关系

```
Behavior Ontology ← 共享资产（不属于任何模块）
    ├── G6 Fidelity Analyzer (Coverage 替代 CRF)
    ├── Director Constraint Arbitration (验证约束是否改变了策略)
    ├── Writer (作为参考，不作为约束)
    ├── ReaderOS (辅助检测叙事行为和读者感知)
    └── CB Runtime (定义 Choice Profile 的预期策略激活)
```

---

**状态：** v2 FROZEN（2026-07-17 18:45）
**冻结条件：** 老高确认三条补充全部落版（BO-002 / Producer-Consumer / Versioning）
**前一版本：** v1 DRAFT（18:40）— 已废弃
**版本演进：** v2 → v3 (Behavior Graph) → v4 (Behavior Dynamics)，预留空间
