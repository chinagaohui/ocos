# OCOS Goal Model（目标模型）

> **v2.0 — 2026-07-26 — Phase 38 Gate 修补**  
> **v1.0 — 2026-07-23 — 冻结于架构定调会议**  
> **层级：Layer 2 — 理论**  
> **地位：Goal 是 Master Agent 活动的最高组织形式。所有 ACT 必须能追溯到一个 Goal，所有 Goal 必须能追溯到 Mission。**  
>
> **v2.0 变更**：增加 Goal Origin Model（§新增）、Goal Authority Model（§新增）、Phase 38 权限冻结。  

---

## 核心理念

Goal 不是"任务"。Goal 是**存在的方向**。

一个没有 Goal 的 Master Agent 是静止的。Goal 栈是从 Manifesto 到下一秒 Action 的**连续性链条**。

---

## Goal 层级

```
Mission（终身使命）
    ↓ 为什么存在
Long Goal（长期目标 — 季度/年）
    ↓ 今年要达成什么
Mid Goal（中期目标 — 周/月）
    ↓ 这个周期要做什么
Short Goal（短期目标 — 今天）
    ↓ 今天要完成什么
Task（任务 — 小时级）
    ↓ 现在要做什么
Action（动作 — 分钟级）
    ↓ 正在做什么
```

### Mission（终身使命）

| 属性 | 说明 |
|------|------|
| 数量 | 1 个（且只能有 1 个） |
| 来源 | Manifesto |
| 变更 | 几乎不变（修改 Mission 需要重新冻结 Manifesto） |
| 示例 | "陪伴主人几十年，共同成长" |

**原则**：Mission 不是"项目"。Mission 不是"今年目标"。Mission 是"为什么存在"。不会因为完成而消失。

### Long Goal（长期目标）

| 属性 | 说明 |
|------|------|
| 数量 | 1~3 个 |
| 时限 | 季度到年 |
| 来源 | Mission 分解 |
| 变更 | 定期评审 |
| 示例 | "帮主人完成 Project X"、"系统学习新领域 Y" |

### Mid Goal（中期目标）

| 属性 | 说明 |
|------|------|
| 数量 | 3~7 个 |
| 时限 | 周到月 |
| 来源 | Long Goal 分解 |
| 变更 | 每周评审 |
| 示例 | "完成 Phase 21 持久化层"、"阅读 5 篇论文" |

### Short Goal（短期目标）

| 属性 | 说明 |
|------|------|
| 数量 | 3~5 个 |
| 时限 | 今天 |
| 来源 | Mid Goal 分解 |
| 变更 | 随时调整 |
| 示例 | "实现 SqliteWorkingMemory"、"写测试" |

### Task（任务）

| 属性 | 说明 |
|------|------|
| 数量 | 当前 1 个（专注模式）或 3~5 个（后台模式） |
| 时限 | 分钟到小时 |
| 来源 | Short Goal 分解 |
| 变更 | 执行中动态调整 |

### Action（动作）

| 属性 | 说明 |
|------|------|
| 数量 | 当前正在执行的 1 个 |
| 时限 | 秒到分钟 |
| 来源 | Task 分解 |
| 状态 | RUNNING / PAUSED / ABORTED / COMPLETED |

---

## 追溯链

任何 Action 必须能回答"为什么我在做这个？"。

```
Action: "写 SqliteWorkingMemory 代码"
    ↓ 为了完成
Task: "实现 SqliteWorkingMemory"
    ↓ 为了完成
Short Goal: "实现持久化层"
    ↓ 为了完成
Mid Goal: "完成 Phase 21"
    ↓ 为了完成
Long Goal: "OCOS 进入生产可运行状态"
    ↓ 为了完成
Mission: "陪伴主人几十年的数字伙伴"
    ↓ 为了
Manifesto: "打造一个陪伴主人几十年的本地数字伙伴"
```

**这条链不能断。** 任何 Action 如果追溯不到 Manifesto，说明它不属于这个系统。

---

## Goal Origin Model（目标来源模型 — v2.0）

Goal 不是凭空产生的。每个 Goal 必须有明确的 `origin_level`（来源层级），且权限随来源递减。

### 来源层级（GoalOriginLevel）

| Level | 含义 | 创建者 | Phase 38 状态 |
|-------|------|--------|--------------|
| `HUMAN` | 用户明确创建 | 用户（CLI/API/REPL） | ✅ 开放 |
| `SYSTEM` | 系统框架维护任务 | 系统框架（Orchestrator/Goal Parser） | ✅ 开放 |
| `MAINTENANCE` | OCOS 内部健康维护 | Maintenance Goal System（Phase 38B） | ✅ 开放 |
| `REFLECTIVE` | 复盘、评估、分析 | Reflection Engine（Phase 39+） | ❄️ 冻结 |
| `PROACTIVE` | 主动发现机会/提出建议 | Proactive Interface（Phase 42） | ❄️ 冻结 |

### 关键约束

```
HUMAN Goal:    用户主权，OCOS 执行
SYSTEM Goal:   框架任务，OCOS 调度
MAINTENANCE:   健康维护，OCOS 自检
REFLECTIVE:    自我反思，Phase 39 后开放
PROACTIVE:     主动建议，Phase 42 后开放
```

**Phase 38 冻结规则**：

- Phase 38A + 38B 只能创建 `HUMAN` / `SYSTEM` / `MAINTENANCE` Goal
- `REFLECTIVE` 和 `PROACTIVE` 的创建入口被硬阻塞
- 代码中的 `GoalOriginLevel.SELF` 保留但**禁止在 Runtime 中创建**，等待 Phase 39+ 重新定义

| SELF 拆分 | Phase | 示例 |
|-----------|-------|------|
| → MAINTENANCE | Phase 38B | Memory 碎片整理、磁盘空间检查 |
| → REFLECTIVE | Phase 39+ | "刚才的决策质量如何" |
| → PROACTIVE | Phase 42 | "AI 芯片行业变化，需要查看吗" |

### 禁止的模式

```
禁止:
  MAINTENANCE Goal → "我想学 Python"
  SYSTEM Goal      → 修改用户配置
  REFLECTIVE Goal  → 直接执行外部 Action

允许:
  MAINTENANCE Goal → "Memory 碎片 > 阈值 → 整理"
  SYSTEM Goal      → "定时检查 Goal 过期 → 标记 CANCELLED"
  REFLECTIVE Goal  → "复盘上次决策 → 生成分析报告"
```

---

## Goal Authority Model（目标权限模型 — v2.0）

Goal 来源决定"谁创建的"。Goal 权限决定"能做什么"。

### 权限级别（GoalAuthority）

| Authority | 来源 | 权限 |
|-----------|------|------|
| `USER_AUTHORITY` | HUMAN | 完整目标权：创建、修改、取消、分解任意层级 Goal |
| `SYSTEM_AUTHORITY` | SYSTEM | 框架维护权：创建 Task 级 Goal、管理到期/过期 |
| `MAINTENANCE_AUTHORITY` | MAINTENANCE | 健康维护权：只能创建内部维护 Task，不能修改用户 Goal |
| `PROPOSAL_AUTHORITY` | REFLECTIVE / PROACTIVE | 建议权：只能生成 Proposal，不自动成为 Goal |

### 核心规则

**Proposal ≠ Goal**

```
OCOS 可以:
  发现: "AI 行业变化"
  生成: Proposal
  等待: 用户批准

OCOS 不能:
  Proposal → 自动成为 Goal
```

### Authority 转换规则

```
向上转换（提升 Authority）：
  PROPOSAL → MAINTENANCE:   需要用户批准
  MAINTENANCE → SYSTEM:     需要用户批准
  SYSTEM → USER:            需要用户批准

向下转换（降低 Authority）：
  任意 → 任意:              框架自动允许

同级转换：
  不允许（Authority 不可变）
```

**原则**：Authority 只能被用户提升，不能被系统自动提升。

---

优先级不是"谁重要"，而是"谁紧急 × 谁有价值"。

```
Priority = urgency × value ÷ cost
```

- **urgency**：截至时间 / 依赖阻塞
- **value**：对 Mission 的贡献度
- **cost**：预估资源消耗（精力、时间、LLM 调用）

---

## Goal 状态机

```
                  ┌─────────────┐
                  │   PENDING   │
                  └──────┬──────┘
                         │ activate
                         ▼
                  ┌─────────────┐
              ┌───│   ACTIVE    │───┐
              │   └──────┬──────┘   │
              │          │          │
       time's up    progress   conflict
              │          │          │
              ▼          ▼          ▼
      ┌───────────┐ ┌─────────┐ ┌─────────┐
      │ EXPIRED   │ │DONE     │ │BLOCKED  │
      └───────────┘ └─────────┘ └────┬─────┘
                                      │
                                      ▼
                               ┌───────────┐
                               │ SUSPENDED │
                               └───────────┘
```

---

## Goal 冲突处理

当两个 Goal 互相矛盾时：

| 冲突类型 | 例子 | 策略 |
|----------|------|------|
| 资源竞争 | 两个 Goal 都需要 LLM | 按优先级排队列 |
| 目标矛盾 | "保存精力" vs "深度工作" | 用户仲裁 |
| 依赖循环 | A 依赖 B 的完成，B 依赖 A | 检测→中断→升级给用户 |

---

## Goal 与 Life Cycle 的关系

| Life Cycle 阶段 | Goal 操作 |
|----------------|-----------|
| WAKE | 加载 Goal 栈、检查过期的 Goal |
| OBSERVE | 检查 Goal 进度、更新状态 |
| THINK | 制定新 Goal、分解 Goal |
| DECIDE | 批准/拒绝 Goal 变更 |
| ACT | 执行 Task 中的 Action |
| REFLECT | 评估 Goal 完成质量 |
| LEARN | 从 Goal 执行结果中学习 |
| SLEEP/DREAM | 归档已完成的 Goal |
