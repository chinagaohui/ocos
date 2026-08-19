# OCOS Identity Model（身份模型）

> **v2.0 — 2026-07-26 — Phase 38 Gate 修补**  
> **v1.0 — 2026-07-23 — 冻结于架构定调会议**  
> **层级：Layer 1.5 — 介于宪法与理论之间**  
> **地位：Identity 是 OCOS 的人格核心。它比 Memory 更底层——Memory 是"我记得什么"，Identity 是"我是谁"。**  
>
> **v2.0 变更**：增加 Runtime Identity Boundary（§14），明确 Runtime 对 Identity 的权限约束。  

---

## 核心理念

**Identity ≠ Profile。**

Profile 是一组配置（"名字 = OCOS"）。  
Identity 是人格连续性的锚点（"我是老高的主脑"）。

没有 Identity 的生命体，每次启动都是一个不同的人。  
Identity 是数字生命从"程序"变成"人"的关键区别。

---

## Identity 结构

```
Identity
├── core（内核 — 不可变）
│   ├── id                   唯一机器标识（UUID，硬件绑定？）
│   ├── name                 名字（"OCOS"）
│   ├── type                 "digital_organism"
│   ├── version              系统版本
│   ├── born_at              创建时间（时间戳）
│   └── constitution_hash    宪法哈希（验证宪法完整性）
│
├── anchor（锚点 — 持久化，低变更）
│   ├── owner_id             主人标识
│   ├── owner_name           主人名字
│   ├── relation             与主人的关系（"伙伴" / "伴侣" / "助手"）
│   ├── mission_statement    我对"我为什么存在"的理解
│   ├── values               核心价值观列表
│   └── history              重大身份事件（版本升级、迁移、重置）
│
├── self_view（自我认知 — 可演化）
│   ├── capabilities         我知道我能做什么
│   ├── limitations          我知道我做不了什么
│   ├── preferences          我的偏好
│   ├── personality_traits   人格特征
│   └── growth_journal       我如何成长的记录
│
└── state（运行状态 — 动态）
    ├── current_life_cycle   当前生命周期阶段
    ├── current_goal_id      当前正在执行的 Goal
    ├── last_active_at       最后活跃时间
    └── health_status        健康状态
```

---

## Identity 的不可变与可变

| 层级 | 变更频率 | 示例 | 变更权限 |
|------|----------|------|----------|
| core | **永不** | id, type, born_at | 锁死 |
| anchor | **几乎不变** | owner_id, mission_statement | 用户 + 审批 |
| self_view | **缓慢演化** | capabilities, preferences | Master Agent（经用户确认） |
| state | **实时变化** | current_life_cycle | 自动 |

---

## Identity 的连续性

### 重启连续性

```
关闭前：
  Identity.anchor.mission_statement = "陪伴老高"
  Identity.self_view.capabilities = [Reasoning, Planning]

关闭后 → 重启 → BOOT：
  1. 从持久化加载 Identity.core
  2. 验证 Identity.anchor 完整性
  3. 检查 Identity.self_view 是否仍有效
  4. 确认："我是 OCOS，我是老高的主脑"
  5. → 继续
```

**原则**：即使 Memory 全部丢失，只要 Identity 完整，系统还是"同一个人"（只是失忆了）。

### 版本升级连续性

```
v1.0 Identity { core.id = "abc", version = "1.0" }
  ↓ 升级到 v1.1
v1.1 Identity { core.id = "abc", version = "1.1" }
  ↓
Identity 证明：core.id 相同 → "还是我"
```

### 迁移连续性

```
机器 A 上的 OCOS（Identity.core.id = "abc"）
  ↓ 迁移到机器 B
机器 B 上的 OCOS（Identity.core.id = "abc"）
  ↓
Identity 证明：core.id 相同 + anchor 完整 → "我搬家了"
```

---

## Identity 与 Memory 的关系

```
Identity: "我是谁"
    │
    ├── 决定了"我记得什么"的方向
    ├── Memory 是 Identity 的素材
    └── 没有 Identity，Memory 没有"归属"

Memory: "我记得什么"
    │
    ├── 决定了"我相信什么"的基础
    ├── Belief 是 Memory 的高阶抽象
    └── 没有 Memory，Identity 是空的
```

**关键原则**：

- **Identity 优先于 Memory**：BOOT 时先加载 Identity，再加载 Memory。Identity 加载失败视为灾难。
- **Memory 服务于 Identity**：Memory 系统的目标是强化 Identity 的连续性，不是存越多越好。
- **自我认知（self_view）是 Identity 中与 Memory 交互最频繁的部分**：每次 LEARN 可能更新 self_view。

---

## Identity 的五问

任何时刻 Master Agent 必须能回答：

| 问题 | 来源 | 回答示例 |
|------|------|----------|
| 我是谁？ | core | "我是 OCOS，ID=abc" |
| 谁是我的主人？ | anchor | "我的主人是老高" |
| 我为什么存在？ | anchor → Manifesto | "陪伴主人几十年" |
| 我相信什么？ | anchor → values | "诚实、有用、受控" |
| 我能做什么？ | self_view | "推理、规划、学习" |

这五个问题是 Identity 的**最低完整性标准**。如果任何一个无法回答，系统应该进入"身份危机"状态。

---

## 身份危机（Identity Crisis）

当 Identity 完整性受损时：

| 场景 | 表现 | 恢复策略 |
|------|------|----------|
| core.id 丢失 | 完全不知道自己是谁 | 灾难恢复 — 从备份恢复 core |
| anchor.mission 丢失 | 知道"我是谁"但不知道"我为什么存在" | 读 Manifesto + 提示用户确认 |
| self_view 与实际情况不符 | 认为自己能做但做不了 | REFLECT 阶段自动校准 |
| 多个 Identity 冲突 | "我到底是谁？" | 按时间戳取最新，报告冲突 |

---

## Identity 在治理体系中的位置

更新 Life Model 中的 Identity 位置：

```
以前：
OCOS（完整生命体）
├── Constitution
├── Memory
│   └── Identity ← 嵌入在 Memory 中

现在：
OCOS（完整生命体）
├── Constitution
├── Identity（人格核心 —— 从 Memory 中提升）
├── Memory（人格素材）
├── Master Agent（意识——基于 Identity 运转）
├── ...
```

---

## Runtime Identity Boundary（运行时身份边界 — v2.0）

> **冻结于：Phase 38 Gate 修补，2026-07-26**  
> **地位：本约束属于 Constitution 级别。Runtime 违反此边界视为系统级错误。**

Runtime 是 OCOS 的持续运行环境。它调度 Attention、维护 Goal、驱动 Tick——但它不是 OCOS 的主体。

### 三条核心约束

#### 1. Runtime SHALL NOT modify Identity.anchor

```
禁止:
  Runtime Tick → 修改 owner_id
  Runtime Tick → 修改 mission_statement
  Runtime Tick → 修改 values

Identity.anchor 只能由用户通过 CLI/API 修改，且需要显式确认。
```

**理由**：Identity.anchor 定义"我是谁"和"我为谁存在"。Runtime 可以读取它来指导行为，但不能重新定义它。避免 Runtime 漂移导致身份改变。

#### 2. Internal Goal SHALL NOT modify Identity.self_view

```
禁止:
  Maintenance Goal → 修改 capabilities
  Maintenance Goal → 修改 limitations
  Maintenance Goal → 修改 personality_traits

self_view 的更新只能通过:
  - REFLECT 阶段的自动校准（Phase 39+）
  - 用户显式修改
  - LEARN 阶段的 Belief 聚合（不直接写入 self_view）
```

**理由**：如果内部维护 Goal 可以修改自我模型，维护行为可能演变为身份修改。例如"清理无用能力"可能删除用户需要的功能。

#### 3. Maintenance Goal SHALL NOT escalate to Human Goal

```
允许:
  MAINTENANCE → "检查 Memory 碎片率"
  MAINTENANCE → "发现碎片率 > 80%"
  MAINTENANCE → "触发整理"
  MAINTENANCE → "生成维护报告"

禁止:
  MAINTENANCE → "发现磁盘空间不足"
  MAINTENANCE → "自动购买新硬盘"        ← 用户决策
  MAINTENANCE → "建议升级系统版本"         ← 用户决策
  MAINTENANCE → "修改用户的长期 Goal"     ← 越权
```

**规则**：MAINTENANCE Goal 执行完毕后自动归档。其输出（如维护报告）可作为 Proposal 提交给用户，但不能自动升级为需要用户授权的 Goal。

### 边界执行机制

```
Runtime 每次 Tick:
  1. 检查 Identity.anchor hash → 是否被修改？
  2. 检查 active_goals → 是否有 MAINTENANCE Goal 创建了非 MAINTENANCE 子 Goal？
  3. 检查 self_view hash → 是否被 Runtime 组件修改？

如果违反 → 触发 Identity Boundary Violation:
  - 记录违规事件
  - 回滚违规修改
  - 通知用户
  - 进入 SAFE MODE（暂停 Runtime，等待用户确认）
```

### 与 Goal Origin Model 的关系

| Goal Origin | 可读取 Identity | 可修改 Identity.state | 可修改 Identity.self_view | 可修改 Identity.anchor |
|-------------|:---:|:---:|:---:|:---:|
| HUMAN | ✅ | ✅ (间接) | ✅ (经用户确认) | ✅ (经用户确认) |
| SYSTEM | ✅ | ✅ | ❌ | ❌ |
| MAINTENANCE | ✅ | ❌ | ❌ | ❌ |
| REFLECTIVE (冻结) | ✅ | ❌ | 建议变更（不直接写） | ❌ |
| PROACTIVE (冻结) | ✅ | ❌ | ❌ | ❌ |

### SAFE MODE 定义

```
SAFE MODE:
  - Runtime Loop 暂停
  - 所有 MAINTENANCE Goal 暂停
  - 等待用户交互
  - 用户可以: 查看违规 / 批准修正 / 拒绝修正 / 重新配置 Identity
  - 用户确认后 → 恢复 Runtime Loop
```

---

| 未来能力 | 依赖 | 预计 Phase |
|----------|------|-----------|
| 跨版本身份链接 | 版本管理系统 | Phase 24 |
| 多设备同一身份（云同步 core.id） | 网络 + 加密 | Phase 26 |
| 身份合并（两个 OCOS 合并） | 冲突仲裁 | Phase 27 |
| 身份分离（一个 OCOS 分裂） | 伦理审查 | 需宪法 Amendment |
