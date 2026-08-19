# DECISION_OWNERSHIP_MAP.md

> V2 架构审计的最终产出。
> 
> 定义整条 Pipeline 中每层的**决策边界**：
> 什么可以决定，什么必须留给下一层。
>
> **状态：FROZEN**
> **版本：v1.1（Architecture Constitution v1.0）**
> **冻结于 2026-07-17 16:34（老高审计通过）**
> **取代：所有之前的隐式决策模型**

---

## 第一原则

> **Every layer creates constraints, states and uncertainty for the next layer.**

每一层只能向下一层交付：
- **Constraints**（约束——不能做什么、必须面对什么）
- **States**（状态——世界状态、角色认知状态）
- **Uncertainty**（不确定空间——角色不知道什么、还可以怎么理解）

不可以交付：
- **行为指令**（角色应该做什么）
- **剧情选择**（故事应该怎样发展）
- **具体内容**（角色应该说什么）

---

## 决策授权表

| Layer | 可以决定（CAN）| 不可以决定（CANNOT）| 必须留给下一层 |
|:------|:--------------|:-------------------|:---------------|
| **Theory** | 世界规律、主题方向、核心问题 | 具体事件、角色行为、章节结构 | 叙事约束和意图 |
| **Narrative Gravity** | 主题约束（什么不属于这个故事） | 任何故事内容 | 每卷的叙事目标 |
| **Volume Blueprint** | 叙事压力、状态变化目标、读者问题、约束 | 角色行为序列、具体事件、对话 | 可执行的角色约束 |
| **Intent Layer / Constraint Bridge (CB)** | 候选空间（角色在面临X压力时可选的N个选项）、角色状态变化目标 / 候选影响路径 | 直接确定实际状态变化；唯一剧情线；唯一选择 | 场景可能性空间 |
| **Director** | 选择评价标准、约束冲突消解策略 | 写具体角色动作、写对话、写场景；**生成新的剧情候选；定义新的角色目标** | 场景功能需求和空间 |
| **Writer**（Narrative Realization Strategy）| 场景距离与信息释放策略、情感基调（压迫感/温情）、语言风格、节奏、氛围 | 改变故事方向、违背约束、替角色做选择；决定场景的具体内容 | 表达策略 |
| **LLM Execution**（Surface Realization）| 措辞、句型、描写细节 | 违背叙事约束、引入未授权的剧情；改变 Writer 决定的策略方向 | 最终正文 |
| **Quality Gate** | 检测 Decision Leakage、验证约束遵守、标识偏差 | 自行修改内容、替上游做决策 | 修复请求（反馈给对应层） |

---

## 决策不能反转的边界

以下决策在冻结后不可由下游层推翻：

| 决策类型 | 冻结层 | 示例 |
|:---------|:-------|:-----|
| 世界规律 | Theory | "光速不可超越" |
| 主题方向 | Theory | "毁灭来自确定性而非未知" |
| 叙事约束 | Volume Blueprint | C-01：不提前解释 |
| 角色状态 Delta | Volume Blueprint | "林烬权威信任从70→50" |
| 读者问题 | Volume Blueprint | "未来新闻是否可信？" |
| 角色基本身份 | Character Model（Ontology）| "林烬的 Primary Identity = builder" |
| 角色信念体系 | Character Model（Ontology）| "林烬 believe: 技术解决一切" |

---

## 范式对比

### 当前（Blueprint Execution Model）

```
Theory
  │  效果：无（信号未进入 Pipeline）
  ▼
Blueprint（Script）
  │  决定：角色做什么、剧情怎么走
  ▼
Director（执行指令生成器）
  │  决定：补充行为指令、控制叙事节奏
  ▼
CB（不存在 / CharBrain 情绪跟踪）
  │  效果：无
  ▼
Writer（扩写器）
  │  效果：忠实执行上游行为指令
  ▼
LLM → 正文
```

### 目标（Narrative Intent Translation Model）

```
Theory
  │  交付：世界规律、主题方向、核心问题
  ▼
Narrative Gravity
  │  交付：主题约束（什么不能做）
  ▼
Volume Blueprint
  │  交付：叙事压力、状态 Delta、读者问题
  ▼
Intent Layer（Constraint Bridge / CB）
  │  交付：候选空间（N个选项）、决策帧、信念偏移
  ▼
Director
  │  交付：选择标准、冲突消解
  ▼
Writer
  │  交付：正文（根据"角色面对什么 + 他选了"推导细节）
```

---

## 泄漏检测标准

对 Pipeline 中任何一段数据流，可以问以下问题来判断是否发生 Decision Leakage：

| 检查 | 问题 |
|:-----|:-----|
| **Agency Test** | 删除数据流中的角色姓名后，是否仍能表达完整的叙事压力？ |
| **Replacement Test** | 如果换成另一个角色，这个数据流是否仍然成立？（成立=泄漏） |
| **Why Test** | 上游能否回答"角色为什么做这个选择"？（能回答=泄漏） |
| **Scale Test** | 数据流中角色行为描述的占比是否超过 Narrative Pressure 的占比？ |
| **Counterfactual Test** | 如果角色做出完全不同的选择，这个数据是否仍然成立？（成立=Intent；不成立=Script） |

### 标准

- L0（Clean）：行为描述 0%，纯压力/约束
- L1（Acceptable）：行为描述 <10%
- L2（Degraded）：行为描述 10-30%
- L3（Contaminated）：行为描述 >30%
- **L4（Collapsed）**：行为描述 >70%，该层已退化为剧情执行器

当前全 Pipeline 状态：**L4（Collapsed）**（Writer Prompt ≈95%）。

---

## 附录：V2 审计映射

本图的每一项指标，均有 V2 审计文档中的对应 Finding 证明。

| 层 | 当前状态 | 目标状态 | V2 证据 |
|:---|:---------|:---------|:--------|
| Theory → Pipeline | 信号 0% | 100% 信号注入 | V2-005 |
| Blueprint | Script（97% DL）| Pressure Record（<10% DL）| V2-002 |
| Director | 执行指令生成器（70% DL）| 选择策略输出器（<10% DL）| V2-001 |
| CB / Intent | 不存在 | Constraint Bridge | V2-003 |
| Pipeline 整体 | Story Blueprint（97% Cascade）| Intent Translation（<10%） | V2-004 |
| Writer Prompt | 行为指令 ≈95% | 压力/决策 ≈100% | V2-005 |

---

*本文件由 V2 审计产出，作为架构迭代的可执行契约。*

*第一次迭代目标：将全 Pipeline Decision Leakage 从 L3（>30%）降至 L1（<10%）。*

*标志性节点：CB（Intent Interpretation Layer）上线 / Blueprint 格式切换至 Pressure-first / Writer Prompt 不再包含角色行为描述。*
