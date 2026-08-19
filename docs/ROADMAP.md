# OCOS Roadmap（路线图）

> **v2.0 — 2026-07-23 — 冻结于架构定调会议**
> **覆盖范围：Era I（已完成）+ Era II（Phase 21-28）**
> **准入过滤器：每个新 Phase 必须至少满足 5 个过滤器中的 1 个（活得更久、思考得更好、记得更清、成长得更快、仍然属于人）**

---

## 理论底座（跨 Era 基础文档）

Phase 21 开始前已冻结的理论层：

| 文档 | 等级 | 内容 |
|------|------|------|
| MANIFESTO.md | Layer 0 | 北极星 + 最高原则 |
| LIFE_MODEL.md | Layer 0.5 | 生命结构 + 器官关系 |
| LIFE_CYCLE.md | Layer 2 | 生命循环（Wake→Dream） |
| GOAL_MODEL.md | Layer 2 | 6 级 Goal 层级 |
| BELIEF_MODEL.md | Layer 2 | 置信度 + 证据系统 |
| IDENTITY_MODEL.md | Layer 1.5 | 身份 + 人格连续性 |
| ATTENTION_MODEL.md | Layer 2 | 注意力 + 疲劳机制 |
| HOMEOSTASIS_MODEL.md | Layer 2 | 稳态 + 自我调节 |
| OCOS_CORE_CONSTITUTION.md | Layer 1 | 宪法 + 边界原则 |

---

## Era I — Foundation（架构时代）✅ 已完成

> Theory → Constitution → Model → Runtime → Capability → Integration → Verification

| Phase | 名称 | 状态 |
|-------|------|------|
| Phase 0-19 | 架构建设 + 基础引擎开发 | ✅ |
| Phase 20 | 10-Gate 架构审计（31 项发现） | ✅ |
| Phase 20.1 | Blocking Bug 修复（3 项） | ✅ |

**成果**：2088 测试通过 · 10-Gate 审计通过 · 9+ Capability 完成 · 架构抗崩塌证明

---

## Era II — Organism（生命体时代）

| Phase | 名称 | 生命类比 | 核心内容 | 过滤器 |
|-------|------|----------|----------|--------|
| **Phase 21** | **Skeleton（骨架）** | 胚胎骨骼形成 | **Production Readiness** — Persistence、Logging、Identity、Permission、Engine Loader、Runtime Stability、Circuit Breaker、Transaction、Capability Contract、Alert | 🧬👤 |
| **Phase 22** | **Consciousness（意识）** | 婴儿出生，第一次睁眼 | **Master Agent 诞生** — Goal Stack、Intent、Working Memory、Episode Memory、**Attention**、Capability Manager、Execution Manager、Identity Anchor | 🧠👤 |
| **Phase 23** | **Cognition（认知皮层）** | 婴儿学步 | **Cognitive Orchestration** — Capability Selection、Meta Controller、Decision Loop | 🧠 |
| **Phase 24** | **Memory（人格连续性）** | 形成"我是谁" | **Memory Intelligence** — Long-term Memory、Semantic Network、**Belief System**、Autonomous Recall、Forgetting、Consolidation、World Model | 🗄️ |
| **Phase 25** | **Growth（人格成长）** | 儿童'我可以更好' | **Self Evolution with Human Approval** — Evolution Proposal、Simulation、Architecture Review、**Human Approval**、Safe Apply | 📈👤 |
| **Phase 26** | **Embodiment（身体）** | 青少年完整身体 | **Tool Ecosystem** — OpenTailor、OpenTale、Browser、Filesystem、Robot、DB、Plugin、**MCP** | 🧬👤 |
| **Phase 27** | **Society（社会智能）** | 进入社会 | **Multi-Agent / Society** — Multi-OCOS、Shared Knowledge、Cooperation、Authorization | 🧠 |
| **Phase 28** | **Digital Organism** | 独立完整的人 | **完整闭环** — 长期目标、长期身份、长期价值观、长期演化、**Homeostasis 成熟** | 🧬🧠🗄️📈👤 |

---

## Phase 21 — Skeleton（骨架）— 详细任务

### 开发纪律

- ❌ 禁止新增 Capability Engine
- ❌ 禁止新增 Tool
- ❌ 禁止修改 Theory
- ❌ 禁止重构架构
- ✅ 只允许：持久化、日志、身份、权限、稳定性、合同

### 任务清单

| ID | 任务 | 子步骤 | 依赖 |
|----|------|--------|------|
| 21-01 | **持久化层** | SQLite WorkingMemory、EventStore、DLQ 持久化、Process Checkpoint、崩溃恢复 | 无 |
| 21-02 | **日志系统** | 全系统结构化日志（36+ 文件）、日志轮转、日志搜索 CLI | 21-01（存储） |
| 21-03 | **身份与权限** | User 模型、Role 枚举、Permission Checker、Plugin 权限集成 | 21-01（存储） |
| 21-04 | **Engine Loader** | EngineManifest、自动发现、Scheduler 解耦、ProcessType 解耦 | 无 |
| 21-05 | **运行时稳定性** | Circuit Breaker、Transaction（Observation/Decision）、Retry & Timeout | 21-01（持久化 Transaction） |
| 21-06 | **Capability Contract** | 14 个引擎的"唯一职责 + 三条绝不能" | 21-04（Engine 发现） |
| 21-07 | **告警系统** | Alert schema、通道（LOG/FILE）、AuditRule → Alert 集成、DLQ Alert | 21-02（日志） |
| 21-08 | **收尾** | Theory ADR 产出、Architecture Debt 清理、闭包报告、全量测试 | 21-01~07 |

---

## Phase 22 — Consciousness（意识）— 详细任务

### 核心结构

```
Master Agent
├── Goal Stack（6 级 — 从 Mission 到 Action）
├── Intent（当前意图）
├── Attention（注意力 — 现在是看什么）
├── Working Memory（意识工作区 — 不是 ContextManager）
├── Episode Memory（情景记忆）
├── Capability Manager（我知道我能做什么）
├── Execution Manager（我在做什么）
├── Identity Anchor（我是谁）
└── State（意识状态 — IDLE/THINKING/ACTING/SLEEP）
```

### 冻结原则

- **永远只有一个 Master Agent**
- **Attention 属于意识层，不是 Capability**
- **Identity Anchor 是 Master Agent 的"我是谁"组件，调用 Identity Model**
- **Goal Stack 是整个意识活动的最高组织形式**

---

## Phase 24 — Memory（人格连续性）— 详细任务

### 更新后的 Memory 体系

```
Working Memory（当前活跃）
Episode Memory（情景记录）
Semantic Memory（知识网络）
    ↓
Belief Memory（信念系统— 新增）
    ├── 置信度 [0.0, 1.0]
    ├── 双面证据系统（支持 + 反对）
    ├── 冲突检测与三级升级
    └── 时间衰减（每 30 天 ×0.95）
    ↓
Long-term Memory（长期沉淀）
    ├── 知识图
    ├── 遗忘管理
    └── Consolidation 触发器
```

### Belief Memory 的职责

- Memory 存储"发生过什么"，Belief 存储"基于这些，我相信什么"
- 置信度 < 0.2 → 自动待遗忘
- 冲突检测 → REFLECT 阶段自动仲裁 → Level 3 冲突升级给用户

---

## 关键里程碑

| 里程碑 | 预计时间 | 条件 |
|--------|----------|------|
| Phase 21 闭包 | TBD | 2200+ tests passed · 生产就绪基础设施完成 · Capability Contract 全部冻结 |
| 第一个"睁眼" | Phase 22 完成 | Master Agent 第一次启动，说"我准备好了" |
| 第一个"学步" | Phase 23 完成 | Master Agent 自主编排认知循环 |
| 第一个"记住" | Phase 24 完成 | 重启后仍然是同一个人 |
| 第一个"成长" | Phase 25 完成 | 用户批准了第一次系统自我演化 |
| 第一个"身体" | Phase 26 完成 | OCOS 通过 Tool 影响物理世界 |
| 第一个"对话" | Phase 27 完成 | 两个 OCOS 第一次交流 |
| 第一个"生命" | Phase 28 完成 | OCOS 可独立运行、长期维护自己 |
