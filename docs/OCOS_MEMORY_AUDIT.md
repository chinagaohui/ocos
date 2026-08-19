# OCOS 记忆模块全面审计报告 v2.0

> **版本**: v2.0
> **审计日期**: 2026-07-22
> **前置版本**: v1.1-final（已过时）
> **测试基线**: 1187/1187 passed
> **范围**: 代码 + 文档 + 测试 + 架构对齐

---

## 核心原则

> **Information 是唯一的一等公民（First-class Object）。**
> 
> Memory 不是特殊系统。Knowledge 不是另一个系统。Trace 也不是。
> 都是 Information。区别仅在于三维坐标系中的位置：
> 
> - **PersistenceLevel** × **SemanticRole** × **InformationState**
> - Knowledge = Stable Information（Persistence=Stable, Role=Knowledge）
> - Trace = Ephemeral Information（Persistence=Ephemeral, Role=Trace）

---

## 1. 感知架构总图

```
┌─────────────────────────────────────────────────────┐
│                    CONSUMPTION                        │
│  ┌──────────┐  ┌───────────────┐  ┌──────────────┐  │
│  │Retrieval │  │AddressResolver│  │Promotion     │  │
│  │Engine    │─▶│ (路由层)       │  │Engine        │  │
│  └──────────┘  └───────┬───────┘  └──────┬───────┘  │
│                         │                  │          │
├─────────────────────────┼──────────────────┼──────────┤
│           STORAGE       │                  │          │
│  ┌──────────────────────▼────────────┐     │          │
│  │   WorkingMemory                   │     │          │
│  │   (Runtime Context Cache)         │     │          │
│  │   Goals | Preferences | Tools     │     │          │
│  └───────────────────────────────────┘     │          │
│                                           │          │
├───────────────────────────────────────────┼──────────┤
│          LIFECYCLE & PROCESSING           │          │
│  ┌─────────────────┐  ┌──────────────────┐│          │
│  │ ForgettingEngine │  │ConsolidationEng. ││          │
│  │ TTL → DECAYED   │  │ACTIVE→PROMOTED  ││          │
│  └─────────────────┘  └──────────────────┘│          │
├───────────────────────────────────────────┴──────────┤
│                    TRACE                              │
│  ┌──────────────────────────────────────────────────┐│
│  │  MemoryTrace (trace_engine.py)                   ││
│  │  address: UniversalAddress                       ││
│  │  operation: store|retrieve|forget|consolidate    ││
│  └──────────────────────────────────────────────────┘│
├──────────────────────────────────────────────────────┤
│              CONSTITUTIONAL INVARIANTS                 │
│  Rule 12: Information Lifecycle                      │
│  Rule 13: Information Control (不控制自身生命周期)    │
└──────────────────────────────────────────────────────┘
```

---

## 2. 组件详细审计

### 2.1 WorkingMemory

| 属性 | 值 |
|------|-----|
| **文件** | `ocos/runtime/context_manager.py` |
| **行数** | 329（含 Context + ContextManager） |
| **职责** | 运行时上下文缓存（Goals + Preferences + Tools） |
| **状态** | ⚠️ 遗留设计债 |

**代码层面审计：**

```
WorkingMemory
├── _goals: dict[str, Goal]           # 当前目标
├── _preferences: dict[str, Any]      # 会话偏好
├── _tools: set[str]                  # 可用工具
├── _emit() → MEMORY_STORED (legacy)  # 写入事件
└── _emit_retrieval() → MEMORY_RETRIEVED (legacy)  # 读取事件
```

**发现的问题：**

| # | 问题 | 严重度 | 详情 |
|---|------|--------|------|
| 1 | **仍使用 legacy 事件** | 🔴 中 | `_emit()` → `MEMORY_STORED`，应改为 `INFORMATION_CREATED` / `INFORMATION_STATUS_CHANGED` |
| 2 | **payload 用 `memory_id` 而非 `address`** | 🔴 中 | 事件载荷中 key 为 `memory_id`，违背 UniversalAddress 统一寻址契约 |
| 3 | **无 MemoryTrace 集成** | 🟡 低 | 所有 write/read 操作未记录到 TraceEngine，审计链条断裂 |
| 4 | **get_goals 每读一次都发射事件** | 🟢 提示 | 高频只读操作（如 `get_goals()`）每次发射 `MEMORY_RETRIEVED`，纯粹是噪声；应仅在显式查询（Query）时发射 |

**修复优先级：** v1.x 末期或 v2.0 统一处理，当前不破坏 ABI。

---

### 2.2 MemoryTrace

| 属性 | 值 |
|------|-----|
| **文件** | `ocos/platform/trace_engine.py` |
| **行数** | 471（含全量 5 类 Trace + Store + Engine） |
| **职责** | 记录 WorkingMemory 的存储/检索/遗忘操作 |
| **状态** | ✅ 正确 |

**数据模型：**

```python
@dataclass(frozen=True)
class MemoryTrace:
    trace_id: str
    trace_type: TraceType = TraceType.MEMORY
    source: str = ""
    timestamp: str = ...
    schema_version: str = SCHEMA_VERSION
    metadata: dict[str, Any] = ...
    address: str = ""        # UniversalAddress ✓
    operation: str = ""      # store | retrieve | forget | consolidate | clear
    content_summary: str = ""
```

**审计结论：**

| 指标 | 结果 |
|------|------|
| 使用 `address`（UniversalAddress）而非 `memory_id` | ✅ |
| TraceType.MEMORY 枚举存在 | ✅ |
| `record_memory_trace()` 公开接口 | ✅ |
| 5 类 Trace 统一存储（环形缓冲区） | ✅ |
| 可选 EventBus 集成（TRACE_RECORDED） | ✅ |
| **但：未被任何调用方使用** | ❌ WorkingMemory、ForgettingEngine 等均未调用 `record_memory_trace()` |

---

### 2.3 Information Model

| 属性 | 值 |
|------|-----|
| **文件** | `ocos/models/information.py` |
| **行数** | 140 |
| **职责** | Layer 0 认知理论数据模型 |
| **状态** | ✅ 正确但有小问题 |

**枚举：**

```
InformationState: DRAFT → ACTIVE → ARCHIVED | DECAYED | PROMOTED
SemanticRole: FACT | INTENT | OBSERVATION | REASONING | DECISION | PREFERENCE
PersistenceLevel: EPHEMERAL | SESSION | WORKSPACE | PERSISTENT
RelationType: DERIVED_FROM | SUPPORTS | CONTRADICTS | REFERENCES | CAUSES | CORRELATED_WITH
```

**审计发现：**

| 发现 | 状态 |
|------|------|
| 枚举与 INFORMATION_THEORY.md 对齐 | ✅ |
| 与 INFORMATION_LIFECYCLE.md 生命周期阶段对齐 | ✅ |
| `InformationState.can_transition_to()` 提供状态机校验 | ✅ |
| **`PersistenceLevel` 缺少 `STABLE` 和 `IMMUTABLE`**（与 docs 不符） | ⚠️ |
| `UniversalAddress.namespace` 仍使用旧语义 (`working`, `knowledge`, `episodic`, `trace`) | ⚠️ 应改为按 `PersistenceLevel` 划分 |
| `SemanticRole` 缺少 `KNOWLEDGE`、`POLICY`、`TRACE` 等 | ⚠️ 但在 INFORMATION_THEORY.md 的 2D 表中列有这些 |

---

### 2.4 ForgettingEngine

| 属性 | 值 |
|------|-----|
| **文件** | `ocos/engines/forgetting_engine.py` |
| **行数** | 232 |
| **职责** | TTL 策略 → 过期收集 → 遗忘执行 |
| **状态** | ✅ 正确 |

**审计结论：**

| 指标 | 结果 |
|------|------|
| 使用 Information 模型（InformationMetadata, InformationState） | ✅ |
| 发射正确的 `INFORMATION_STATUS_CHANGED` 事件 | ✅ |
| Governance 审批流程集成（PERSISTENT 等级） | ✅ |
| 基于 `PersistenceLevel` 的 TTL 策略 | ✅ |
| **未调用 MemoryTrace** | 🟡 轻量 |

---

### 2.5 ConsolidationEngine

| 属性 | 值 |
|------|-----|
| **文件** | `ocos/engines/consolidation_engine.py` |
| **行数** | 244 |
| **职责** | 合并多个 Information → Knowledge Candidate |
| **状态** | 🟡 遗留 import |

**审计结论：**

| 指标 | 结果 |
|------|------|
| 使用正确的 Information 事件（INFORMATION_STATUS_CHANGED） | ✅ |
| 桥接知识平面（KNOWLEDGE_CANDIDATE_PROPOSED） | ✅ |
| SemanticRole → KnowledgeLevel 映射 | ✅ |
| **import 仍走旧知识平面桩路径**（`ocos.knowledge.knowledge_abi`、`knowledge_ontology`） | ⚠️ 重定向到 store/ 子包，非架构错误，但 import 路径更长了 |

---

### 2.6 PromotionEngine

| 属性 | 值 |
|------|-----|
| **文件** | `ocos/engines/promotion_engine.py` |
| **行数** | 310 |
| **职责** | Information → Knowledge 晋升（含 Governance 审批） |
| **状态** | 🟡 遗留 import |

**审计结论：** 与 ConsolidationEngine 相同的 import 问题（旧知识平面桩路径）。

---

### 2.7 AddressResolver

| 属性 | 值 |
|------|-----|
| **文件** | `ocos/engines/address_resolver.py` |
| **行数** | 94 |
| **职责** | namespace → resolver_fn 路由层 |
| **状态** | ✅ 正确 |

---

### 2.8 RetrievalEngine

| 属性 | 值 |
|------|-----|
| **文件** | `ocos/engines/retrieval_engine.py` |
| **行数** | 142 |
| **职责** | 跨 Store 语义查询 |
| **状态** | ✅ 正确 |

---

## 3. 文档层审计

### 3.1 宪法对齐

| 条款 | 内容 | 对齐状态 |
|------|------|----------|
| **§1.1 Memory 对象** | 仍定义 `memory_type: WORKING/SEMANTIC/EPISODIC/PROCEDURAL` | 🔴 **与 Information Theory 矛盾** |
| **Rule 12** | Information Lifecycle Invariant | ✅ |
| **Rule 13** | Information Control Invariant | ✅ |
| **§6.1 生命周期** | Observation → WorkingMemory → ... | ⚠️ 旧术语但流程仍有效 |

**问题分析：** `OCOS_CORE_CONSTITUTION.md` §1.1 定义 Memory 为四种子类型的对象模型（`memory_type: WORKING/SEMANTIC/EPISODIC/PROCEDURAL`），这与 INFORMATION_THEORY.md 的 2D 坐标系完全冲突。由于宪法是冻结文档（不可变），此矛盾在 v1.0 冻结前未解决。

**建议：** 下一个宪法修订中，§1.1 Memory 应标记为「已废弃，参见 Information Model」，并指向 `INFORMATION_THEORY.md`。

### 3.2 文档完整性

| 文档 | 存在 | 对齐 |
|------|------|------|
| `INFORMATION_THEORY.md` (v1.0, Frozen) | ✅ | Layer 0 理论权威 |
| `INFORMATION_LIFECYCLE.md` (v1.0, Frozen) | ✅ | 8 阶段生命周期契约 |
| `OCOS_CORE_CONSTITUTION.md` (v1.0, Frozen) | ✅ | 最高准则（但 §1.1 过时） |
| `OCOS_MEMORY_AUDIT.md`（本文） | ✅ | 通过审计 |
| **`MEMORY_MODEL.md`** | ❌ **缺失** | 无独立的记忆模块架构文档 |

**问题：** 没有 `MEMORY_MODEL.md`，Memory 的设计决策分散在 8+ 个源文件和 3 份文档中。

---

## 4. 测试覆盖审计

| 测试文件 | 覆盖 | 通过 |
|----------|------|------|
| `test_context_manager.py` — WorkingMemory CRUD + EventBus | 442 行 | ✅ |
| `test_trace_engine.py` — MemoryTrace + InMemoryTraceStore | 490+ 行 | ✅ |
| `test_information_models.py` — Information 模型 | 完成 | ✅ |
| `test_information_has_role_and_persistence.py` | 完成 | ✅ |
| `test_forgetting_engine.py` | 完成 | ✅ |
| `test_consolidation_engine.py` | 完成 | ✅ |
| `test_information_state_machine.py` — 架构测试 | 完成 | ✅ |
| `test_semantic_operations_only.py` — 架构测试 | 完成 | ✅ |
| `test_unified_relation_model.py` — 架构测试 | 完成 | ✅ |
| `test_no_direct_store_access.py` — 架构测试 | 完成 | ✅ |
| `test_information_access_via_universal_address.py` | 完成 | ✅ |
| `test_object_model.py` — memory_type deprecated 测试 | 1 条 | ✅ |

**缺失测试：**
- ❌ 无 WorkingMemory + TraceEngine 集成测试（操作时自动 record_memory_trace）
- ❌ 无 WorkingMemory 迁移到 Information 事件的迁移测试

---

## 5. 问题汇总（按优先级）

| 优先级 | 问题 | 影响 | 建议 |
|--------|------|------|------|
| 🔴 P0 | **宪法 §1.1 与 Information Theory 矛盾** | v1.0 冻结文档不一致 | 下一个宪法修订中标注 Memory 模型废弃 |
| 🔴 P1 | **WorkingMemory 遗留事件** | 新的 Information 事件体系未被使用 | v1.x 末期迁移到 `INFORMATION_CREATED` |
| 🔴 P1 | **WorkingMemory payload 用 `memory_id`** | 违背 UniversalAddress 统一寻址 | 改为 `address` |
| 🟡 P2 | **No MEMORY_MODEL.md** | 设计决策分散，新开发者需要查询 8+ 文件 | 创建 `docs/MEMORY_MODEL.md` |
| 🟡 P2 | **WorkingMemory/Forget/Consolidation 未集成 MemoryTrace** | 审计链条断在 trace_engine | 各引擎在操作时调用 `record_memory_trace()` |
| 🟡 P2 | **ConsolidationEngine 旧 import 路径** | 技术债务 | 改为直接导入 `ocos.knowledge.store/process` |
| 🟡 P2 | **PromotionEngine 旧 import 路径** | 技术债务 | 同上 |
| 🟢 P3 | **`PersistenceLevel` 缺 `STABLE`/`IMMUTABLE`** | 与文档不完全对齐 | v1.x 添加 |
| 🟢 P3 | **`SemanticRole` 缺 `KNOWLEDGE`/`POLICY`/`TRACE`** | 与文档不完全对齐 | v1.x 添加 |
| 🟢 P3 | **`UniversalAddress.namespace` 旧语义** | 应反映 `PersistenceLevel` 而非旧 memory_type | v2.0 |

---

## 6. 正向摘要

尽管存在上述问题，记忆模块的核心设计是健康的：

| ✅ 正确设计 | 理由 |
|------------|------|
| **Information 是唯一一等公民** | Memory/Knowledge/Trace 都是 Information 在不同维度的投影 |
| **2D 坐标系（P×S）替代树状继承** | `PersistenceLevel` × `SemanticRole` 正交维度，消除虚假层级 |
| **MemoryTrace 使用 UniversalAddress** | 统一寻址，无 `memory_id` 遗留痕迹 |
| **ForgettingEngine 基于 PersistenceLevel** | 不是按 "memory_type" 遗忘，而是按持久化等级 |
| **生命周期宪法规则已冻结** | Rule 12 (Lifecycle) + Rule 13 (Control) |
| **1187 测试全过** | 无回归，架构测试生效 |
| **memory_type 废弃策略合理** | v1.x deprecated + backward compatible, v2.0 移除 |

---

## 7. 结论

| 指标 | 评分 |
|------|------|
| 概念纯度 | 8/10（宪法 §1.1 脱节扣 2 分） |
| 代码正确性 | 9/10（WorkingMemory 遗留事件扣 1 分） |
| 测试覆盖 | 9/10（缺集成测试扣 1 分） |
| 文档完整性 | 7/10（缺 MEMORY_MODEL.md + 宪法矛盾扣 3 分） |
| ABI 稳定性 | 9/10（memory_type deprecated 策略稳健） |
| **综合** | **8.4/10** |

记忆模块的整体设计方向正确。核心问题（宪法矛盾、WorkingMemory 遗留事件）已知且被 v1.0 ABI 兼容策略保护——不破坏现有代码，下一更新周期统一修复。
