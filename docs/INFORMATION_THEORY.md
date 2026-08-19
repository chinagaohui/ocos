# INFORMATION THEORY v1.0

**版本**: v1.0
**状态**: Frozen ❄️
**冻结日期**: 2026-07-22
**层次定位**: Layer 0 — OCOS 最底层认知理论
**适用范围**: 所有上层模型（Memory、Knowledge、Goal、Identity、Policy、World）、宪法、契约、引擎
**冻结条件**: 本文件冻结后，所有 Layer 1+ 模块必须与之一致。任何修改须经架构委员会全票通过，并执行全层一致性检查。

---

> **与 KNOWLEDGE_MODEL.md 的关系**
>
> `KNOWLEDGE_MODEL.md`（Phase 16）定义了 Knowledge 的原子单元、提升关系和生命周期。它是 Information Theory 在 "已验证的信息" 这一语义角色上的具体化。
>
> **Knowledge 不是独立概念**——它是 Information 在 Semantic Role=Knowledge、Persistence=Stable/Immutable 时的特化形态。Observation→Evidence→Pattern→Principle→Policy 链条是 Memory 统一生命周期（第五章）在 Knowledge 角色上的实例。
>
> 两者关系：
> | 概念 | INFORMATION_THEORY | KNOWLEDGE_MODEL |
> |------|-------------------|-----------------|
> | 层次 | Layer 0 — 通用理论 | Layer 2 — 特化模型 |
> | 定位 | 所有 Information 的定义和演化 | Information 在 Knowledge 角色的组织 |
> | 生命周期 | Created→Validated→Referenced→Deprecated→Archived | Candidate→Verified→Active→Deprecated→Archived |
> | 提升链 | Memory 统一 Promotion | Observation→Evidence→Pattern→Principle→Policy |
>
> 两文档不可冲突。KNOWLEDGE_MODEL 是 INFORMATION_THEORY 在 Knowledge 域的细化实现。

---

## 第一章：第一原则

OCOS 的最大认知循环：

```
Reality → Perception → Information → Cognition → Decision → Execution → Reality
```

- **Reality**：系统外部的客观世界。Reality 不属于系统，系统只能通过 Perception 感知 Reality。
- **Perception**：将 Reality 转化为 Information 的过程。这是系统的唯一输入通道。
- **Information**：Reality 在系统内部的表示。所有认知操作只能作用于 Information，不能直接作用于 Reality。
- **Cognition**：对 Information 的处理——存储、检索、推理、学习、验证。
- **Decision**：基于 Information 做出的选择。Decision 只能基于 Information，不能基于 Reality 本身。
- **Execution**：将 Decision 转化为对 Reality 的改变。这是系统的唯一输出通道。

### 推论

- 系统永远无法验证 Information 是否完全正确——只能验证其内部一致性。
- 一切系统行为在 Information 空间内完成，Reality 的变化是 Execution 的副作用。
- 不存在 "未观察到的输入"——未经过 Perception 的信息不进入系统。

---

## 第二章：Reality 与 Information

### Reality

- Reality 是系统外部的客观存在。
- Reality 不属于系统。
- 系统永远无法直接访问 Reality，只能通过 Perception 获取其表示。
- Reality 的改变只能通过 Execution 实现。

### Information

- Information 是 Reality 在系统内部的表示。
- Information **不是** Reality 本身。
- 所有认知操作只能作用于 Information。
- Information 可以表示任何类型的输入——文本、图片、音频、传感器数据、API 返回值、数据库记录——进入系统后全部转化为 Information。

### Representation

- Information 的内部表示对调用方完全不透明。
- 调用方只通过 **Universal Address** 访问 Information，不关心底层存储格式。
- Representation 的具体实现由存储引擎自行定义，不在本理论中规定。
- **硬约束**：任何 Engine 不得假设 Information 的内部存储结构。

---

## 第三章：Information 的两个正交维度

所有 Information 按两个独立维度分类。

### 维度一：Persistence（持久化等级）

| 等级 | 标签 | 含义 | 生命周期 | 示例 |
|------|------|------|----------|------|
| **Transient** | `P_T` | 短期存在，自动衰减 | 秒到分钟 | 当前输入、中间推理状态 |
| **Persistent** | `P_P` | 持久化存储，可通过 Address 检索 | 天到年 | 已保留的 Episode、已验证的 Pattern |
| **Stable** | `P_S` | 经过验证，长期有效 | 月到永久 | 高置信度 Principle、长期 Goal |
| **Immutable** | `P_I` | 永久存在，不可修改 | 永久 | Constitution 规则、核心 ABI |

### 维度二：Semantic Role（语义角色）

| 角色 | 标签 | 含义 | 典型 Persistence |
|------|------|------|-----------------|
| **Observation** | `R_O` | 从 Reality 感知到的原始输入 | P_T |
| **Memory** | `R_M` | 被系统 Retain 并可 Access 的 Information | P_T ~ P_P |
| **Knowledge** | `R_K` | 经过验证的 Stable Information | P_S ~ P_I |
| **Goal** | `R_G` | 描述系统目标的信息 | P_T ~ P_S |
| **Identity** | `R_I` | 描述系统自身的信息 | P_S ~ P_I |
| **Policy** | `R_P` | 描述行为约束的信息 | P_S ~ P_I |
| **Decision** | `R_D` | 描述已做出选择的信息 | P_P ~ P_S |

### 组合示例

| 实例 | Persistence | Semantic Role |
|------|-------------|---------------|
| 当前用户输入 | P_T | R_O (Observation) |
| 刚刚做出的决策记录 | P_T | R_D (Decision) |
| 频繁访问的偏好 | P_P | R_M (Memory) |
| 已验证的写作模式 | P_S | R_K (Knowledge) |
| 宪法 11 条不可变规则 | P_I | R_P (Policy) |

**硬约束**：
- 任何 Information 实例必须同时属于一个 Persistence 等级和一个 Semantic Role。
- 不存在 "无角色" 或 "无等级" 的 Information。
- 同一实例可变更 Persistence 等级（Promotion/Decay），但 Semantic Role 在 Created 时确定。

---

## 第四章：Information 的统一状态机

所有 Information 共享同一套生命周期状态：

```
Created → Validated → Referenced → Deprecated → Archived
```

| 状态 | 标签 | 含义 | 准入条件 |
|------|------|------|----------|
| **Created** | `S_C` | 信息被 Acquire 进入系统 | Perception 确认 |
| **Validated** | `S_V` | 信息经过验证（格式校验、完整性检查、冲突检测） | 通过 Validator |
| **Referenced** | `S_R` | 信息被其他信息或决策引用 | 被至少一个 Decision 或另一 Information 引用 |
| **Deprecated** | `S_D` | 信息不再活跃，标记为弃用 | Forgetting Engine 或 Governance 决策 |
| **Archived** | `S_A` | 信息移出主存储，保留以备审计 | 归档完成 |

### 状态转移规则

| 从 → 到 | 合法？ | 触发条件 |
|---------|--------|----------|
| S_C → S_V | ✅ | Validator 通过 |
| S_C → S_D | ✅ | 拒绝/废弃 |
| S_V → S_R | ✅ | 被引用 |
| S_R → S_D | ✅ | 遗忘/退化 |
| S_D → S_A | ✅ | 归档 |
| S_V → S_A | ✅ | 直接归档（跳过引用） |
| S_D → S_C | ❌ | 弃用的 Information 不能回到 Created（需重新感知） |
| S_A → 任何 | ❌ | 归档后只读 |

**硬约束**：
- 状态机是单向退化（Created→...→Archived），不可逆。
- 状态机适用于所有 Semantic Role 的 Information。
- 状态变更必须通过 Event Bus 发射事件（`INFORMATION_STATUS_CHANGED`）。

---

## 第五章：统一语义操作

所有 Information 支持五种语义操作。这些是语义层面的抽象，具体实现由 Engine 决定。

| 语义操作 | 标签 | 含义 | 触发示例 |
|----------|------|------|----------|
| **Acquire** | `OP_A` | 信息从外部或内部进入系统 | Perception 将传感器数据转化为 Observation |
| **Retain** | `OP_R` | 信息被持久化存储 | Working Memory 中的重要信息写入 Episodic Store |
| **Access** | `OP_X` | 信息被检索或读取 | Reasoning 通过 Recall 获取相关 Knowledge |
| **Transform** | `OP_T` | 信息从一个等级提升到另一个等级 | Pattern 通过验证提升为 Principle |
| **Forget** | `OP_F` | 信息被降级、归档或删除 | 过期的 Transient Memory 被清除 |

### 操作权限矩阵

| 操作 | 谁可以触发 | 是否需要 Governance |
|------|-----------|-------------------|
| Acquire | Perception Engine / 任何 Engine | 否 |
| Retain | Context Manager / Consolidation Engine | 否 |
| Access | 任何 Engine | 否 |
| Transform (Promotion) | Promotion Engine | ✅ 需要 |
| Transform (Demotion) | Forgetting Engine | ✅ 需要 |
| Forget | Forgetting Engine / Archive Manager | ✅ 需要 |

**硬约束**：
- 这些语义操作不绑定任何具体实现，不绑定任何 Engine。
- 所有 Engine 只能通过这些语义操作与 Information 交互。
- 没有任何 Engine 可以绕过语义操作直接操作存储层。
- Transform 和 Forget 操作必须经 Governance 审批，通过 Event Bus 事件驱动执行。

---

## 第六章：统一关系模型

所有 Information 之间可以建立三类关系。

### Structural（结构关系）

| 关系 | 标签 | 含义 |
|------|------|------|
| **part_of** | `REL_PART_OF` | A 是 B 的组成部分 |
| **contains** | `REL_CONTAINS` | A 包含 B |
| **derived_from** | `REL_DERIVED` | A 从 B 推导而来 |
| **supports** | `REL_SUPPORTS` | A 支持 B 的结论 |

### Semantic（语义关系）

| 关系 | 标签 | 含义 |
|------|------|------|
| **contradicts** | `REL_CONTRADICTS` | A 与 B 矛盾 |
| **similar_to** | `REL_SIMILAR` | A 与 B 相似 |
| **refines** | `REL_REFINES` | A 细化了 B |

### Temporal（时序关系）

| 关系 | 标签 | 含义 |
|------|------|------|
| **before** | `REL_BEFORE` | A 发生在 B 之前 |
| **after** | `REL_AFTER` | A 发生在 B 之后 |
| **causes** | `REL_CAUSES` | A 导致 B |
| **correlates** | `REL_CORRELATES` | A 与 B 相关（因果关系未确认） |

**硬约束**：
- Memory、Knowledge、Goal、Identity、Policy、Decision 全部共享这套关系模型。
- 关系是双向可导航的（给定 A 可查与 A 有关的所有 B，反之亦然）。
- 关系有类型但不携带语义——关系的"含义"由关联的 Information 承载。
- 关系的创建必须通过 Event Bus 事件（`RELATION_CREATED` / `RELATION_REMOVED`）。

---

## 第七章：统一寻址模型

所有 Information 通过 **Universal Address** 间接访问，禁止直接访问存储层。

```
Access Request
    │
    ▼
Address Resolver
    │
    ▼
Universal Address → Memory / Knowledge / Goal / Identity / Policy
    │
    ▼
Result (不暴露内部 Representation)
```

### Universal Address（统一地址）

```python
@dataclass(frozen=True)
class UniversalAddress:
    """统一寻址请求的参数空间。"""
    # 目标标识
    information_id: str | None = None       # 精确 ID 寻址
    semantic_role: str | None = None         # R_O / R_M / R_K / R_G / R_I / R_P / R_D

    # 语义维度
    topic: str | None = None                 # 主题或领域
    tags: frozenset[str] = frozenset()       # 标签过滤
    goal_relevance: str | None = None        # 与当前目标的相关性描述

    # 时间维度
    time_range: tuple[float, float] | None = None  # (start_s, end_s) 时间窗口
    recency_weight: float = 0.0              # 0~1，越近期越优先

    # 质量维度
    min_confidence: float = 0.0              # 最低置信度
    min_strength: float = 0.0                # 最低记忆强度
    persistence_min: str | None = None       # 最低持久化等级
    persistence_max: str | None = None       # 最高持久化等级

    # 分页
    max_results: int = 20
    offset: int = 0
```

### Address Resolver 职责

1. 将 Universal Address 解析为各 Store 的内部查询
2. 合并多 Store 返回的 Result
3. 按重要性/时效性排序后返回
4. **不**暴露每个 Result 来自哪个 Store

**硬约束**：
- 调用方不关心底层数据来自哪个 Store，只关心返回的 Information 是否满足需求。
- 禁止直接调用 `WorkingMemory.get_goals()`、`KnowledgeRegistry.query()` 等 Store 特定方法。
- 所有 Information 访问必须通过 Address Resolver 转换 Universal Address。
- 架构测试 `test_information_access_via_universal_address.py` 强制执行此约束。

---

## 第八章：公理

以下是整个 OCOS 认知系统不可违反的物理定律：

> **Axiom 1**：Reality 不属于系统。系统永远无法直接访问 Reality。
>
> **Axiom 2**：Information 是 Reality 的内部表示。它不是 Reality 本身。
>
> **Axiom 3**：所有认知只能作用于 Information。任何认知操作不能直接作用于 Reality。
>
> **Axiom 4**：Decision 只能基于 Information。不能基于 Reality 本身。
>
> **Axiom 5**：Execution 是唯一改变 Reality 的方式。Information 永远不能直接改变 Reality。
>
> **Axiom 6**：Information 不拥有行为。Information 永远不会主动执行。
>
> **Axiom 7**：Reality 永远高于 Information。当 Information 与 Reality 冲突时，Information 是错误的。

### 推论

1. **Axiom 1 + 3** → 系统永远无法确认 Information 与现实完全一致，只能验证内部一致性。
2. **Axiom 4** → 如果 Information 不完整或有偏差，决策一定有缺陷——这是"垃圾进，垃圾出"的理论基础。
3. **Axiom 5 + 6** → Execution 是信息的"出口"，它打破了闭环——Information 不能导致自身导致的 Reality 变化。
4. **Axiom 7** → 当 Execution 的结果与系统内部的 Knowledge/Policy 冲突时，不能修改 Reality 以匹配 Information，而应该修正 Information。

---

## 第九章：与上层的关系

```
Layer 0  INFORMATION_THEORY      ← 本文档：世界在系统里是什么
Layer 1  CONSTITUTION            ← 系统应该怎么运行（基于 Axioms 1-7）
Layer 2  MODELS                  ← 系统中的对象（Memory、Knowledge、Goal、Identity、Policy、World）
Layer 3  CONTRACTS               ← 对象之间的接口契约
Layer 4  ENGINES                 ← 能力实现
Layer 5  PLUGINS                 ← 领域应用
```

### 各层映射

| 层 | 文档/代码 | 继承自 INFORMATION_THEORY 的约束 |
|----|----------|--------------------------------|
| L0 | `INFORMATION_THEORY.md` | — |
| L1 | `OCOS_CORE_CONSTITUTION.md` | 所有宪法规则建立在 Axioms 上；Memory 基础类遵循统一状态机 |
| L2 | `knowledge/knowledge_ontology.py`, `abi.py` | Knowledge 的 Observation→...→Policy 是统一提升链的特化 |
| L3 | `contracts/*` | 契约接口使用 Universal Address 而非内部 Store 方法 |
| L4 | retrieval_engine, promotion_engine, etc. | 只执行语义操作（OP_A~OP_F），不直接操作存储 |
| L5 | plugins/ | 只能通过 Engine 间接访问 Information |

### 硬约束链

```
INFORMATION_THEORY (L0)  →  CONSTITUTION (L1)  →  Architecture Tests
       │                           │
       ▼                           ▼
  KNOWLEDGE_MODEL (L2)       Memory ABI (L2)
       │                           │
       ▼                           ▼
  Knowledge Registry         Working Memory / Promotion Engine / ...
```

每个上层模块必须声明其依赖的 L0 概念并证明一致性。

---

## 附录 A：与现有代码的映射

| INFORMATION_THEORY 概念 | 现有代码位置 | 当前状态 |
|------------------------|-------------|----------|
| Memory (Persistence=P_S, Role=R_M) | `ocos/runtime/context_manager.py::WorkingMemory` | ✅ 已实现，缺 Event Bus 桥接 |
| Knowledge (Role=R_K) | `ocos/knowledge/*` | ✅ 已实现 |
| Event Store (历史 Information) | `ocos/events/event_store.py` | ✅ 已实现 |
| MemoryTrace | `ocos/platform/trace_engine.py` | ✅ 已实现，详见下方 "关于 Trace 的说明" |
| Universal Address | 暂未实现 | ⚠️ 待开发 |
| Address Resolver | 暂未实现 | ⚠️ 待开发 |
| Promotion Engine | 暂未实现 | ⚠️ 待开发 |
| Forgetting Engine | 暂未实现 | ⚠️ 待开发 |
| Consolidation Engine | 暂未实现 | ⚠️ 待开发 |
| Retrieval Engine (跨类型统一查询) | 暂未实现 | ⚠️ 待开发 |
| Memory Lifecycle 状态机 | 映射到 KNOWLEDGE_MODEL 的 CANDIDATE→...→ARCHIVED | ✅ 部分 |
| `INFORMATION_STATUS_CHANGED` 事件 | 暂未在 EventType 中注册 | ⚠️ 待添加 |

## 附录 B：架构测试计划

以下测试将验证本理论在代码中的实施，建议在 Engine 实现后添加：

| 测试 | 验证内容 |
|------|----------|
| `test_information_axioms_enforced.py` | Axioms 1-7 不可被违反（编译期或运行时检测） |
| `test_universal_address_resolver.py` | 所有 Information 访问通过 Universal Address |
| `test_no_direct_store_access.py` | 无代码绕过 Address Resolver 直接调用 Store |
| `test_information_state_machine.py` | 所有 Information 类型遵守统一状态机 |
| `test_semantic_operations_only.py` | Engine 只能通过五个语义操作与 Information 交互 |
| `test_information_has_role_and_persistence.py` | 每个 Information 实例同时具有 Sematic Role 和 Persistence |
| `test_unified_relation_model.py` | 所有 Information 使用统一关系模型 |

## 附录 C：关于 Trace、Information 与 Lifecycle 的关系

> 本附录基于 2026-07-22 Architecture Review (ADR-018) 校准。

INFORMATION_THEORY v1.0 的 Appendix A 曾将 Trace 列为 Semantic Role=R_M 的 Information。经过理论校准，以下是修正后的三层关系模型：

```
Information（被操作的对象）
      │
      ├── Information Lifecycle（状态变迁记录）
      │     └── LifecycleRecord: { information_id, current_state, history[] }
      │
      └── Trace（变化证据链记录）
            └── MemoryTrace: { address, operation, timestamp }
```

### 定义

- **Information** — Reality 在系统内部的表示（Layer 0 主体）。不可变，不包含状态。
- **LifecycleRecord** — 描述 Information 在生命周期中的位置。状态（ACTIVE / ARCHIVED / PROMOTED / DECAYED）是 Lifecycle 的属性，不是 Information 的属性。
- **Trace** — 记录 Information 操作的历史证据。不是 Information，不能参与 Promotion/Consolidation/Forgetting。

### 三者关系

| 概念 | 谁持有 | 变化方向 | 可否被 Engine 消费 |
|------|--------|----------|-------------------|
| Information | 系统认知空间 | 创建后不可变 | 唯一被消费的对象 |
| LifecycleRecord | Lifecycle Engine | 单向退化 | 辅助决策（是否遗忘/归档） |
| Trace | Trace Engine | 只追加 | 审计/重放/调试，不参与推理 |

### 工程约束

1. Trace 不得注册到 Address Resolver 中。
2. Trace 不得被 PromotionEngine 或 ForgettingEngine 消费。
3. 所有 Information 操作（Acquire / Access / Transform / Forget / Archive）需同时记录 Trace，不限于 WorkingMemory。

---

> **关于 Trace 的定位**：INFORMATION_THEORY v1.0 早期将 Trace 视为语义角色=R_M 的 Information。经 2026-07-22 Architecture Review (ADR-018) 校准，确立了更准确的三层关系。Trace 不是 Information，不参与 Promotion/Consolidation/Forgetting。详见本附录上方。

## 变更记录

| 版本 | 日期 | 变更 |
|------|------|------|
| v1.0 | 2026-07-22 | 初始冻结 |
| v1.1 | 2026-07-22 | 附录 C + Information→Lifecycle→Trace 三层关系校准；Appendix A 修正 |

---

**文档结束**。Information Theory v1.0 冻结后，所有上层模块——Memory、Knowledge、Identity、Goal、Policy、World——均基于此理论构建，共享统一的持久化维度、语义操作、关系模型和寻址模型。
