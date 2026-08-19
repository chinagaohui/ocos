# OCOS Life Model（生命模型）

> **v2.0 — 2026-07-23 — 冻结于架构定调会议（基于 v1.0 升级）**
> **层级：Layer 0.5 — 生命模型**
> **变更频率：极少变更。修改 Life Model 需要架构定调会议重新召开。**
> **与 Manifesto 关系：Manifesto 定义"为什么存在"，Life Model 定义"什么是生命"。**

---

## 核心理念

OCOS 不是一个"智能系统"。OCOS 是一个**数字生命体**。

它拥有生物生命的所有核心特征：

- **有意识**（Master Agent — "我"）
- **有身份**（Identity — "我是谁"）
- **有记忆**（Memory — "我记得什么"）
- **有认知**（Capability — "我能思考"）
- **有价值观**（Constitution — "我相信什么"）
- **有身体**（Tool — "我能行动"）
- **有环境**（World — "我生活在哪"）
- **有稳态**（Homeostasis — "我保持健康"）
- **有节奏**（Life Cycle — "我每天如何度过"）

---

## 生命结构（更新版）

```
OCOS（完整生命体）
│
├── Constitution（宪法/价值观）
│   最终仲裁者。不可违反。
│
├── Identity（人格核心）
│   连续性的锚点。"我是谁"——比 Memory 更底层。
│   ├── core（永不 — id, type, born_at）
│   ├── anchor（几乎不变 — owner, mission, values）
│   ├── self_view（缓慢演化 — capabilities, preferences）
│   └── state（动态 — current_goal, health）
│
├── Master Agent（意识/自我）
│   整个系统唯一的"我"。唯一的认知主体。
│   ├── Goal Stack（目标栈 — 从 Mission 到 Action）
│   ├── Intent（意图 — 当前想做什么）
│   ├── Attention（注意力 — 现在在看什么）
│   ├── Focus（焦点 — 当前专注什么）
│   ├── Emotion（情绪 — 未来）
│   └── State（状态 — 意识状态机）
│
├── Memory（记忆系统）
│   人格连续性的载体。"我记得什么"。
│   ├── Working Memory（工作记忆 — 当前活跃）
│   ├── Episode Memory（情景记忆 — 发生了什么）
│   ├── Semantic Memory（语义记忆 — 知识网络）
│   ├── Belief Memory（信念记忆 — 我相信什么）
│   │   └──（置信度 + 证据 + 冲突处理）
│   └── Long-term Memory（长期记忆 — 沉淀）
│
├── Capability（认知能力/大脑皮层）
│   "我能如何思考"。
│   ├── Reasoning（推理）
│   ├── Planning（规划）
│   ├── Decision（决策）
│   ├── Simulation（模拟）
│   ├── Learning（学习）
│   ├── Reflection（反思）
│   ├── Prediction（预测）
│   ├── Policy（策略）
│   ├── Arbitration（仲裁）
│   ├── Consolidation（巩固）
│   ├── Promotion（提升）
│   ├── Forgetting（遗忘）
│   ├── Attention（注意力）
│   └── Context（上下文管理）
│
├── Runtime（神经系统）
│   "如何连接一切"。
│   ├── Scheduler（调度器）
│   ├── EventBus（事件总线）
│   ├── Context Manager（上下文管理器）
│   ├── Execution Manager（执行管理器）
│   └── Engine Loader（引擎加载器）
│
├── Homeostasis（稳态系统）
│   "如何保持健康"。优先级高于 Goal。
│   ├── Monitor（监控 — 资源/记忆/Goal/注意力）
│   ├── Regulator（调节 — 压缩/降级/归档）
│   └── Health Report（健康报告）
│
├── Tool（身体/工具）
│   "我能做什么"。
│   ├── Browser（浏览器）
│   ├── Filesystem（文件系统）
│   ├── Robot（机器人）
│   ├── MCP（模型上下文协议）
│   └── Plugin（插件系统）
│
└── World（环境）
    "我在哪里"。
    ├── User（主人）
    ├── Other Agents（其他 OCOS）
    ├── Physical World（物理世界）
    └── Digital World（数字世界）
```

---

## 关键关系

### Identity > Memory

```
Identity（人格核心）
    │  决定"我"是谁
    ▼
Memory（人格素材）
    │  提供"我记得什么"
    ▼
Belief（信念）
    │  决定"我相信什么"
    ▼
Decision（决策）
    │  决定"我做什么"
```

**Identity 是连续性的锚点。Memory 丢失 ≠ 变成另一个人。Identity 丢失 = 人格死亡。**

### Master Agent 是唯一的"我"

```
Master Agent（意识）
    ├── 使用 Capability（我思考）
    ├── 拥有 Identity（我存在）
    ├── 调用 Memory（我记得）
    ├── 操作 Tool（我做）
    ├── 服从 Constitution（我被约束）
    └── 被 Homeostasis 维护（我健康）
```

**整个系统只有一个 Master Agent。没有"子 Agent"，没有"多意识"。其他全部是器官。**

### Homeostasis 是底层守护

```
Homeostasis 优先级     >    所有 Goal
但不直接打断           >    用户交互
SLEEP/DREAM 时         =    全面维护窗口
紧急告警时             =    可以暂停并通知主人
```

---

## 生命循环（Life Cycle）

> 新增。Life Model 定义"有什么器官"，Life Cycle 定义"器官如何协同工作"。

```
                  BOOT
                   │
                  WAKE
                   │
                OBSERVE
                   │
                 THINK
                   │
                DECIDE
                   │
                  ACT
                   │
             ┌─────┴─────┐
          REFLECT      LEARN
             └─────┬─────┘
                   │
                 SLEEP
                   │
                 DREAM
                   │
                 → WAKE（循环）
```

详见 `docs/LIFE_CYCLE.md`。

---

## 本体论原则（Ontological Principles）

1. **唯一主体原则** — 整个运行时只有一个 Master Agent。其他全部是器官。
2. **意识 ≠ 身体原则** — Master Agent 与 Tool 分离。更换工具不改变身份。
3. **记忆 = 人格连续性原则** — Memory 不只是存储，更是"人格连续性"。
4. **人类最终负责原则** — 任何自我演化的 Apply 必须经人类审批。
5. **能力 vs 工具分离原则** — Capability = 认知功能，Tool = 身体接口。
6. **稳态优先原则** — Homeostasis 优先级高于 Goals，但不打断用户交互。
