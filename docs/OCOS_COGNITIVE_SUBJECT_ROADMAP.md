# OCOS 认知主体路线图（P0-P5 总路线 / 七层优先级）

> **状态：路线图锚点 / NOT-AUTHORIZED（2026-09-14，Human Gate 确认）**
> 本文件 = 从"带记忆的反射系统"走向"具有连续自身经验、理解、判断和学习能力的
> 数字认知主体"的总路线落盘。**仅作为后续 Scope Amendment 的锚点，不授予任何
> 实施权限。**
>
> 承接：P1-1D 正式收档（`OCOS_P1-1D_DECISION_HOST_SEMANTIC_BOUNDARY_AUDIT.md` §9）。
> 任何里程碑启动都必须走：
>
> ```text
> Scope Amendment → Semantic Boundary Design → Attribution Infrastructure Freeze
> → Human Gate GO → Implementation
> ```

---

## 0. 定位与纪律

- **这是路线图，不是实施方案**：只记录方向、优先级与边界，不包含实现细节。
- **不授权任何生产代码修改**：当前 OCOS 处于 G3/G4/P1-1D 全冻结状态。
- 与旧版 `ROADMAP.md`（Era I/II，Phase 0-28）**互相独立**：旧版覆盖架构建设与生命体
  组织成型；本文件覆盖认知主体链（Cognitive Subject Chain）的建设顺序。

---

## 1. 当前冻结状态（P1-1D 收档锚点）

```text
G3 Worldview Formation                 PASS / FROZEN
G4 Worldview → Thinking                PASS / FROZEN
P1-1D Scope Assessment                 PASS / FROZEN
Decision Host / Semantic Boundary      PASS / FROZEN
P1-1D-B                                NOT AUTHORIZED
```

已钉死的架构边界（收档 §9）：

| 概念 | 状态 |
| --- | --- |
| Cognitive Decision Host | **不存在** |
| Production Planning Host | 存在（AgentRuntime step6） |
| TaskDAG | Action Carrier |
| DecisionBridge | Mutation Authorization / Execution Gate |
| Thinking → Decision Semantic Boundary | **不存在** |
| ChatResponder → DecisionBridge | **REJECTED** |
| 旧 `decision/` / `cognitive_loop/` 等 | 不得作为现成 Cognitive Decision Host 重新启用 |
| Trace enhancement | **未授权** |
| 生产代码 | **零改动** |

**核心架构结论**：OCOS 已存在认知链（Worldview → Thinking）与行动链
（Goal → Planning → TaskDAG → DecisionBridge → Authorization → Execution），
但中间存在 `Thinking ─── X ─── Decision`：**认知结果 → 主体 Decision 的正式语义层
尚未定义**。这个 `X` 不是 bug，也不是 wiring gap，而是**尚未定义的认知语义边界**。

---

## 2. 总路线图

```text
                    ┌──────────────────────┐
                    │   External World     │
                    │ LLM / Internet / DB  │
                    │ Tools / OpenClaw     │
                    └──────────┬───────────┘
                               │
                         Knowledge Interface
                               │
                               ▼
Reality
  ↓
Observation
  ↓
Experience
  ↓
Recognition
  ↓
┌─────────────────────────────────────────────┐
│                 OCOS SELF                   │
│                                             │
│ Identity                                    │
│ Situation                                   │
│ Experience                                  │
│ Memory                                      │
│ Knowledge                                   │
│ Worldview                                   │
│ Cognition                                   │
│ Capability                                  │
│                                             │
└──────────────────────┬──────────────────────┘
                       ↓
                    Thinking
                       ↓
              ┌────── Decision ──────┐
              │                       │
              ↓                       ↓
           Planning               Reflection
              ↓                       │
            TaskDAG                  Learning
              ↓                       │
       Governance / Authority         │
              ↓                       │
          Execution                   │
              ↓                       │
            Reality                   │
              ↓                       │
         Observation ────────────────┘
```

成熟标志：**不是"模型越来越强"，而是 OCOS 自己越来越知道**——我经历过什么、
我记住了什么、我学会了什么、我相信什么、我怎么看世界、我是谁、我现在在想什么、
我为什么这么想、我准备做什么、过去的经历为什么让我这一次选择不同。

---

## 3. 七层优先级

### 第一优先级：补上真正的 Decision（当前最大结构性缺口）

已证明真实的两条链：

```text
Experience → Recognition → Worldview → Thinking        （认知链，真实）
Goal → Planning → TaskDAG → DecisionBridge → Authorization → Execution   （行动链，真实）
```

但 `Thinking ─── X ─── Decision` 仍为空。未来第一个大工程不是"接更多模型"，
而是 **Cognitive Decision Capability**。必须首先回答：

1. **Decision 到底是什么？** 不能再使用 `decision = LLM reply`，而应定义成 OCOS
   自己的语义对象，例如：

```text
Decision
├── decision_id
├── thinking_trace_id
├── situation
├── objective
├── considered_options
├── selected_option
├── rationale
├── consumed_worldview
├── consumed_experience
├── consumed_memory
├── uncertainty
├── confidence
└── intended_action
```

2. **Decision ≠ Action**：Decision 是"我认为现在应该选择什么，以及为什么"；
   Action 才是"具体执行什么"。

目标链：

```text
Self → Situation → Experience/Memory/Worldview/Cognition → Thinking
  → Decision → Planning → TaskDAG → Authorization → Execution
```

> **本层现在必须保持冻结。** 未来走 Scope Amendment → Semantic Boundary Design →
> Attribution Infrastructure Freeze → Human Gate → Implementation，不能直接改。

### 第二优先级：完成"过去改变现在"的真正证明

OCOS 最核心的实验。已证明 `X → Recognition → Worldview W1 → Thinking 输入变化`，
但最终目标仍是：

```text
X → D → W1 → Thinking1 → Decision1 → Y1
```

且证明 `W1≠W0 ∧ Thinking1≠Thinking0 ∧ Decision1≠Decision0 ∧ Y1≠Y0`，
并存在 `Z` = 如果没有 X，本来会发生什么。

最终回答：**如果这段经历从来没有发生过，OCOS 会不会做出不同的判断？**
若答案"会"且证据链完整（X → Recognition → Self/Worldview Delta → Thinking Delta
→ Decision Delta → Behavior Delta），才真正完成：
*因为过去发生过什么，所以现在的 OCOS 会想得不一样。*
这是 OCOS 从"有记忆"进入"有认知连续性"的关键证明。

### 第三优先级：让 Experience / Memory 真正统一

问题不是"没有记忆"，而是**记忆很多但尚未形成一个统一的主体经验体系**。目标：

```text
Reality → Observation → Experience
   ├── What happened / Evidence / Outcome / Context / Self involvement / Consequence
   ↓
Recognition → Learning
   ↓
Memory / Wisdom / Skill / Worldview / Self
```

各结构语义区分：

| 结构 | 记录什么 |
| --- | --- |
| Experience | 我经历了什么？ |
| Memory | 我决定长期保留什么？ |
| Knowledge | 我知道什么？ |
| Wisdom | 我从过去经历中形成了什么可复用理解？ |
| Skill | 我现在能稳定做什么？ |
| Worldview | 我因此形成了什么关于世界的判断框架？ |
| Self | 这件事情改变了"我"什么？ |

这些结构已分别存在，但尚未收敛成统一的主体生命周期（P1 后半段重要工作）。

### 第四优先级：让 World Model 从"临时状态"变成真正的世界理解

现状问题：WorldStore 能表示世界，但不能真正长期记住世界（更接近
`Observation → WorldStore → 当前 Context`）。

目标：

```text
Observation → World Model → Persistent World State → Change
  → Prediction → Prediction Error → Recognition → Learning
```

**关键边界（永远保持）：World Model ≠ Worldview。**

```text
World Model:  "这个环境中 category-detect 不存在。"   ← 世界的模型
Worldview:    "面对不确定环境，我应该先验证，而不是假设环境可靠。"  ← 主体性解释
```

两者应互相影响，但不能互相冒充。

### 第五优先级：建立 OCOS 自己的 Skill / Competence（降低 LLM 依赖）

现状：`LLM → Reasoning → Action` 占比过高。成熟方向：

```text
Known Domain → OCOS Memory → OCOS Knowledge → OCOS Skill → OCOS Cognition → Decision
```

仅当遇到 `Unknown / Novel / High Uncertainty / High Complexity / Insufficient Evidence`
才走：

```text
OCOS → External Knowledge / LLM → Verification → Recognition → Learning
  → Knowledge / Memory / Skill / Worldview
```

外部模型的作用从"替我思考"变成"帮助我解决我暂时不会的问题"。

### 第六优先级：建立真正的 Meta-Cognition

已有：confidence / error recognition / self capability statistics / failure modes /
partial self-correction / prediction gaps。

距"我知道自己为什么这么想，并能检查自己的思考是否可靠"仍有距离。未来至少应回答：

```text
我现在在想什么？→ 我为什么这么想？→ 我用了哪些经验？→ 我用了哪些 Worldview？
→ 我有哪些假设？→ 哪些是假设，哪些是事实？→ 我哪里可能错？
→ 过去有没有类似情况？→ 过去的结果如何？→ 这次是否应该改变策略？
```

目标链：

```text
Thinking → Meta-Cognition → Thinking Quality Assessment → Revision → Decision
```

### 第七优先级：建立"外部世界接口"，但不要让它侵蚀主体

需要干净的 **Knowledge / Capability Interface**。外部（Internet / Databases /
Scientific APIs / Professional Knowledge Bases / Local Models / Frontier LLM /
OpenClaw / Browser / Research Agents）都只是 **External Capability**，统一进入：

```text
Knowledge Interface → Evidence → Recognition → Cognition → Governance
```

**禁止**：

```text
LLM → Self
Internet → Memory
External Agent → Decision
```

否则 OCOS 会重新退化成"一个 LLM Agent + 一堆数据库"。

---

## 4. 五大里程碑（P0-P5）

| 里程碑 | 名称 | 内容 |
| --- | --- | --- |
| **P0** | Decision | 建立真正的 Cognitive Decision，而不是把 LLM Reply 冒充 Decision |
| **P1** | Cognitive Continuity | Experience → Learning → Memory/Wisdom/Self/Worldview → Thinking → Decision 真正贯通 |
| **P2** | World Understanding | World Model 持久化、预测、误差、世界状态变化真正形成闭环 |
| **P3** | Self-Reliance | Skill + Knowledge + Experience 逐渐替代对 LLM 的重复依赖 |
| **P4** | Meta-Cognition | OCOS 能审视自己的认知过程、假设、错误和策略 |
| **P5** | External Cognitive Ecosystem | LLM、互联网、专业模型、OpenClaw 等全部成为 OCOS 的外部能力器官，而不是主体 |

**顺序纪律**：P0 排在最前，因为它正是 P1-1D 收档留下的 `X`（Decision 语义层本身
尚未定义）。在 P0 之前，P1-P5 的贯通都只是把 LLM 输出换个名字。

---

## 5. 重开纪律与唯一合法入口

- **现在不要急着进入 P0。**
- P1-1D 已证明：OCOS 缺的不是"再接一个模块"，而是 Decision 这个语义层本身还没被定义。
- 因此重开后**第一份交付物** = **Cognitive Decision 的纯只读 Semantic Architecture
  Design**（零生产代码改动），回答：Decision 是什么？语义载体是什么？Thinking 产物在
  什么条件下被正式解释为 Decision？Decision ≠ Action 的边界如何冻结？
- 唯一合法推进路径（任何里程碑都不得跳过）：

```text
Human Gate
   ↓
Scope Amendment
   ↓
Semantic Boundary Design
   ↓
Attribution Infrastructure Freeze
   ↓
Implementation Authorization
   ↓
Implementation
```

---

*本文件为路线图锚点文档（NOT-AUTHORIZED）。未修改任何生产代码。*
*任何里程碑实施需 Human Gate 明确授权，且必须先完成 Semantic Boundary Design + Attribution Infrastructure Freeze。*
