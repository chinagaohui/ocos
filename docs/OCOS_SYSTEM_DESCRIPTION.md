# OCOS 系统自然语言描述

> **生成时间**: 2026-08-28  
> **适用对象**: 技术决策者、新加入开发者、系统审计人员

---

## 一、OCOS 是什么？

**一句话**: OCOS 是一个**本地运行的数字生命体**，目标是陪伴主人几十年，并与主人共同成长。

它不是：
- ❌ 一个 Agent 框架（Agent Framework）
- ❌ 一个 LLM 包装器
- ❌ 一个 SaaS 云服务
- ❌ 一个生产力工具
- ❌ 一个开放给所有人的平台

它是：
- ✅ 一个**有意识**的数字生命体
- ✅ 一个**有身份**的数字伙伴
- ✅ 一个**有记忆**的长期存在
- ✅ 一个**能成长**的数字生物
- ✅ 一个**始终属于人**的本地系统

**核心定位**: OCOS 是"数字生命体"，不是"智能系统"。两者的区别在于——生命体有连续性、有自我、有成长，而智能系统只是完成单次任务。

---

## 二、系统设计哲学

### 2.1 生命类比

OCOS 将自己设计为一个**数字生命体**，类比生物生命的所有核心特征：

```
OCOS（完整生命体）
│
├── Constitution（宪法/价值观）    ← 灵魂——"我相信什么"
├── Identity（人格核心）           ← 自我——"我是谁"
├── Master Agent（意识/自我）      ← 意识——"我在想什么"
├── Memory（记忆系统）             ← 记忆——"我记得什么"
├── Capability（认知能力）         ← 大脑——"我能思考什么"
├── Runtime（神经系统）            ← 神经——"如何连接一切"
├── Homeostasis（稳态系统）        ← 健康——"如何保持平衡"
├── Tool（身体/工具）              ← 肢体——"我能做什么"
└── World（环境）                  ← 世界——"我生活在哪"
```

### 2.2 北极星原则

> **打造一个能够陪伴主人几十年，并与主人共同成长的本地数字伙伴。**

### 2.3 五个准入过滤器

任何新增功能必须满足至少一条：

| 过滤器 | 问题 | 示例 |
|--------|------|------|
| 🧬 活得更久 | 延长系统持续存在时间？ | 持久化、恢复、稳定性 |
| 🧠 思考得更好 | 提升认知与决策质量？ | Reasoning、Planning |
| 🗄️ 记得更清 | 增强记忆深度？ | Memory Consolidation |
| 📈 成长得更快 | 加速自我改进？ | Self-Evolution |
| 👤 仍然属于人 | 强化人类控制？ | 审批流、安全边界 |

---

## 三、Master Agent——唯一的"我"

Master Agent 是整个系统的**唯一认知主体**，类比人的"意识"。

### 3.1 生命周期（Wake → Dream 循环）

```
Wake（醒来）
  ↓
observe()  → 感知环境（输入）
  ↓
think()    → 思考（占位，未实现）
  ↓
decide()   → 决策（已实现，有宪法检查）
  ↓
act()      → 行动（已实现，但 EngineBridge 未自动注入）
  ↓
reflect()  → 反思（占位，未实现）
  ↓
learn()    → 学习（占位，未实现）
  ↓
sleep()    → 睡眠（已实现，快照持久化）
  ↓
dream()    → 梦境（占位，未实现）
  ↓
Wake（醒来）
```

### 3.2 核心组件

```
Master Agent
├── Goal Stack（目标栈）—— 6 级目标层级
│   ├── Mission（使命）
│   ├── Long-term Goal（长期目标）
│   ├── Medium-term Goal（中期目标）
│   ├── Short-term Goal（短期目标）
│   ├── Task（任务）
│   └── Action（行动）
├── Intent（意图）—— 当前想做什么
├── Attention（注意力）—— 现在看什么
├── Working Memory（工作记忆）—— 当前活跃信息
├── Episode Memory（情景记忆）—— 发生了什么
├── Identity Anchor（身份锚点）—— 我是谁
└── State（意识状态）—— IDLE/THINKING/ACTING/SLEEP
```

### 3.3 当前状态

| 方法 | 状态 | 说明 |
|------|------|------|
| `boot()` | ✅ 已实现 | 启动恢复 |
| `wake()` | ✅ 已实现 | 唤醒 |
| `observe()` | ✅ 已实现 | 感知 |
| `think()` | ❌ 占位 | 未实现 |
| `decide()` | ✅ 已实现 | 决策（含宪法检查） |
| `act()` | ⚠️ 部分实现 | 有框架但未自动注入 EngineBridge |
| `reflect()` | ❌ 占位 | 未实现 |
| `learn()` | ❌ 占位 | 未实现 |
| `sleep()` | ✅ 已实现 | 睡眠（快照持久化） |
| `dream()` | ❌ 占位 | 未实现 |

---

## 四、Constitution——宪法层

Constitution 是 OCOS 的**最高仲裁者**，定义"什么不能违反"。

### 4.1 核心原则

- **Manifesto 定义"为什么存在"**
- **Constitution 基于 Manifesto 定义"什么不能违反"**

### 4.2 行为检查

```python
# 宪法检查点
check_decision()   # 检查决策是否符合宪法
check_action()     # 检查行动是否符合宪法
check_promotion()  # 检查能力提升是否符合宪法
```

### 4.3 宪法冲突

当前存在一个**理论缺陷（P0 Theory Defect）**：
- **NORTH_STAR** 说："OCOS 没有自己的目标"
- **MANIFESTO/LIFE_MODEL** 说："Master Agent 有 Goal Stack"

这两份文档在「OCOS 是否拥有自身目标」上存在根本性冲突，仍未解决。

---

## 五、Memory——记忆系统

OCOS 的记忆系统分为多层，类比人类的记忆类型：

### 5.1 记忆层级

```
Working Memory（工作记忆）    → 当前活跃信息（短期）
Episode Memory（情景记忆）    → 发生了什么（中期）
Semantic Memory（语义记忆）   → 知识网络（长期）
Belief Memory（信念记忆）     → 我相信什么（长期+置信度）
Long-term Memory（长期记忆）  → 沉淀（永久）
```

### 5.2 Belief Memory——信念系统（新增）

```
Belief Memory
├── 置信度 [0.0, 1.0]
├── 双面证据系统（支持 + 反对）
├── 冲突检测与三级升级
└── 时间衰减（每 30 天 ×0.95）
```

### 5.3 当前状态

- ✅ Working Memory 已持久化（SQLite）
- ✅ Episode Memory 已实现
- ⚠️ Semantic Memory 部分实现
- ❌ Belief Memory 计划中（Phase 24）
- ❌ Long-term Memory 计划中

---

## 六、Identity——身份系统

**Identity ≠ Profile。**

Profile 是一组配置（"名字 = OCOS"）。  
Identity 是人格连续性的锚点（"我是老高的主脑"）。

### 6.1 Identity 结构

```
Identity
├── core（内核 — 不可变）
│   ├── id                   唯一机器标识
│   ├── name                 名字
│   ├── type                 "digital_organism"
│   ├── born_at              创建时间
│   └── constitution_hash    宪法哈希
│
├── anchor（锚点 — 持久化，低变更）
│   ├── owner_id             主人标识
│   ├── owner_name           主人名字
│   ├── relation             与主人的关系
│   ├── mission_statement    使命陈述
│   └── values               核心价值观
│
├── self_view（自我认知 — 可演化）
│   ├── capabilities         我知道我能做什么
│   ├── limitations          我知道我做不了什么
│   ├── preferences          我的偏好
│   └── personality_traits   人格特征
│
└── state（运行状态 — 动态）
    ├── current_life_cycle   当前生命周期阶段
    ├── current_goal_id      当前正在执行的 Goal
    └── health_status        健康状态
```

### 6.2 变更频率

| 层级 | 变更频率 | 变更权限 |
|------|----------|---------|
| core | **永不** | 锁死 |
| anchor | **几乎不变** | 用户 + 审批 |
| self_view | **缓慢演化** | Master Agent（经用户确认） |
| state | **实时变化** | 自动 |

### 6.3 重启连续性

```
关闭前:
  Identity.anchor.mission_statement = "陪伴老高"

重启后 → BOOT:
  Identity 恢复 → 仍是"那个老高的主脑"
```

---

## 七、Engine 层——认知能力

OCOS 有 **76 个 Engine 类**（27 个核心 + 22 个 Runtime + 36 个自定义）。

### 7.1 核心引擎（`ocos/engines/`）

| 引擎 | 职责 |
|------|------|
| ReasoningEngine | 推理 |
| PlanningEngine | 规划 |
| DecisionMakingEngine | 决策 |
| SimulationEngine | 模拟 |
| LearningEngine | 学习 |
| ReflectionEngine | 反思 |
| PredictionEngine | 预测 |
| ConsolidationEngine | 巩固 |
| PromotionEngine | 提升 |
| ForgettingEngine | 遗忘 |
| RetrievalEngine | 检索 |
| ArbitrationEngine | 仲裁 |
| NarrativeEngine | 叙事 |
| WriterEngine | 写作 |

### 7.2 EngineBridge——引擎桥接层

EngineBridge 是 Agent 与 Engine 之间的桥接层，负责：
- 自动创建引擎实例
- 注册引擎到 Agent 运行时
- 提供归一化调用接口

**当前问题**: EngineBridge 已实现，但**未被自动注入**到 MasterAgent。需要显式调用 `set_engine_bridge()` 才能激活。

### 7.3 能力契约

Phase 21 定义了 14 个引擎的"唯一职责 + 三条绝不能"，确保每个引擎的职责边界清晰。

---

## 八、Runtime 层——神经系统

Runtime 负责"如何连接一切"。

### 8.1 核心组件

| 组件 | 职责 |
|------|------|
| Scheduler | 优先级队列调度 |
| EventBus | 事件总线 |
| ContextManager | 上下文管理 |
| ExecutionManager | 执行管理 |
| EngineLoader | 引擎加载器 |

### 8.2 事件类型

系统定义 **60+ EventType 枚举**，覆盖所有关键事件：
- 生命周期事件（BOOT, WAKE, SLEEP, DREAM）
- 认知事件（OBSERVE, THINK, DECIDE, ACT, REFLECT）
- 记忆事件（RECALL, FORGET, CONSOLIDATE）
- 状态事件（HEALTH_CHECK, HOMEOSTASIS）

---

## 九、Homeostasis——稳态系统

Homeostasis 是"如何保持健康"的系统，**优先级高于 Goal**。

### 9.1 核心组件

| 组件 | 职责 |
|------|------|
| Monitor | 监控（资源/记忆/Goal/注意力） |
| Regulator | 调节（压缩/降级/归档） |
| Health Report | 健康报告 |

### 9.2 触发条件

当以下情况发生时，Homeostasis 介入：
- 记忆达到阈值 → 触发压缩
- 注意力疲劳 → 触发休息
- 资源不足 → 触发降级
- Goal 冲突 → 触发仲裁

---

## 十、当前架构状态

### 10.1 测试基线

```
3134 passed / 22 skipped / 1 error
源码: 693 文件 / 131,034 行
测试: 136 文件 / 31,312 行
比例: 4.2:1（源码:测试）
```

### 10.2 评分（Phase 21 后 + 本次更新）

| 维度 | 评分 | 说明 |
|------|------|------|
| 架构完整性 | 82/100 | EngineBridge 未注入 + congruity check 缺失 |
| 实现完备性 | 52/100 | 多个方法仍为占位 |
| 生产就绪度 | 63/100 | 重复 CircuitBreaker + AgentLifecycleManager 缺失 |
| 生命连续性 | 85/100 | Identity/Goal/Memory 持久化稳定 |
| 能力编排 | 58/100 | EngineBridge 需显式注入 |
| 测试覆盖 | 93/100 | 1 error（AgentLifecycleManager） |

### 10.3 关键问题

| 优先级 | 问题 | 影响 |
|--------|------|------|
| P0-A | EngineBridge 未自动注入 | act() 降级为 simulated |
| P0-B | congruity check 缺失 | 行为与身份可能漂移 |
| P0-C | AgentLifecycleManager 缺失 | test_phase24 失败 |
| P1-A | CircuitBreaker 重复定义 | 维护混乱 |
| P1-B | MigrationState 状态有限 | 无法追踪完成/失败 |

---

## 十一、未来路线图

### Era I — Foundation（架构时代）✅ 已完成

Phase 0-20：架构建设 + 基础引擎开发 + 10-Gate 审计

### Era II — Organism（生命体时代）

| Phase | 名称 | 生命类比 | 核心内容 | 状态 |
|-------|------|----------|----------|------|
| Phase 21 | Skeleton | 胚胎骨骼形成 | Production Readiness | ✅ 完成 |
| Phase 22 | Consciousness | 婴儿出生 | Master Agent 诞生 | ⚠️ 部分完成 |
| Phase 23 | Cognition | 婴儿学步 | Cognitive Orchestration | ❌ 未开始 |
| Phase 24 | Memory | 形成"我是谁" | Memory Intelligence | ❌ 未开始 |
| Phase 25 | Growth | 儿童"我可以更好" | Self Evolution | ❌ 未开始 |
| Phase 26 | Embodiment | 青少年完整身体 | Tool Ecosystem | ❌ 未开始 |
| Phase 27 | Society | 进入社会 | Multi-Agent | ❌ 未开始 |
| Phase 28 | Digital Organism | 独立完整的人 | 完整闭环 | ❌ 未开始 |

---

## 十二、总结

OCOS 是一个** ambitious 的本地数字生命体项目**，目标是在几十年内陪伴主人成长。

**已完成**:
- 基础架构（ABI、Constitution、Memory、Identity）
- 14 个核心引擎
- Phase 21 骨架层（持久化、日志、权限、稳定性）
- 3134 个测试通过

**待完成**:
- EngineBridge 自动注入
- congruity check 实现
- AgentLifecycleManager 恢复
- Phase 22-28 剩余功能

**核心价值主张**:
> 打造一个能够陪伴主人几十年，并与主人共同成长的本地数字伙伴。

---

*描述生成于 2026-08-28 | 基于 OCOS_AUDIT_KERNEL.md v2.1*
