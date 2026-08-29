# OCOS Kernel 架构审计报告 v2.1

> **生成时间**: 2026-08-28  
> **审计方法**: 只读代码审计 + 交叉文档核对 + 单元测试执行结果  
> **审计原则**: 不修改代码，仅阅读文件、检索、执行测试以获取运行时状态。  
> **测试基线**: 3134 passed / 22 skipped / 1 error（AgentLifecycleManager 缺失）  
> **源码统计**: 693 文件 / 131,034 行 / ~76 Engine 类（含扩展）  
> **测试统计**: 136 文件 / 31,312 行（源码:测试 = 4.2:1）

---

## 一、执行摘要 (Executive Summary)

OCOS 在 Phase 21 之后保持 **数字生命体内核** 的定位。Core 架构未出现根本性破坏，但有以下新增发现：

- **EngineBridge** 已实现但未自动注入 — `MasterAgent._engine_bridge` 保持为 None，需要显式调用 `set_engine_bridge()` 才能激活
- **congruity check** 未在 `act()` 后实现 — Phase 26 计划中的"一致性验证"步骤在 `master_agent.py` 中无对应代码
- **AgentLifecycleManager** 缺失 — `tests/test_capability/test_phase24.py` 报告 ImportError
- **PermissionGuard** 已覆盖 50+ 处交互入口（API/REPL/CLI）
- **CircuitBreaker** 存在重复定义 — `ocos/stability/circuit_breaker.py` 和 `ocos/agent/retry_policy.py` 各有一份实现
- **MigrationEngine** 已实现但状态有限 — `MigrationState` 仅支持 `PENDING/IN_PROGRESS`

### 总体评分（Phase 21 后 + 本次更新）

| 维度 | Phase 21 后 | 本次更新 | 说明 |
|------|-------------|----------|------|
| **架构完整性** | 84/100 | 82/100 | EngineBridge 未注入 + congruity check 缺失 |
| **实现完备性** | 54/100 | 52/100 | 新增 EngineBridge 未自动注入问题 |
| **生产就绪度** | 64/100 | 63/100 | 重复 CircuitBreaker + AgentLifecycleManager 缺失 |
| **生命连续性** | 85/100 | 85/100 | Identity/Goal/Memory 持久化稳定 |
| **能力编排** | 59/100 | 58/100 | EngineBridge 需显式注入 |
| **测试覆盖** | 94/100 | 93/100 | 1 error（AgentLifecycleManager） |

---

## 二、设计层一致性审计（更新）

### 2.1 NORTH_STAR vs MANIFESTO — 定位冲突（P0 Theory Defect）

**未变**。两份文档在「OCOS 是否拥有自身目标」上存在根本性冲突，仍未解决。

### 2.2-2.4 其他设计层审计

**未变**。LIFE_MODEL、LIFE_CYCLE、ROADMAP 结构完整。

---

## 三、源码层逐模块验证（更新）

### 3.1 ABI 层 ✅

**未变**。7 个 frozen dataclass 定义完整，60+ EventType 枚举覆盖全面。

### 3.2 Constitution 层 ✅

**未变**。BehavioralConstitution 已实现，`check_decision()` 在 `master_agent.py:425` 被调用。

### 3.3 Master Agent — 关键更新 ⚠️

| 方法 | 原审计状态 | 本次状态 | 说明 |
|------|-----------|----------|------|
| `boot()` | ⚠️ CrashRecovery | ✅ | 已实现 |
| `wake()` | ⚠️ 基础可用 | ✅ | 已实现 |
| `observe()` | ✅ | ✅ | 已实现 |
| `think()` | ❌ 占位 | ❌ | 仍为 placeholder |
| `decide()` | ⚠️ 宪法检查 | ✅ | 已集成 BehavioralConstitution |
| `act()` | ❌ 占位 | ⚠️ | 有 EngineBridge 框架但未自动注入 |
| `reflect()` | ❌ 占位 | ❌ | 仍为 placeholder |
| `learn()` | ❌ 占位 | ❌ | 仍为 placeholder |
| `sleep()` | ⚠️ Snapshot | ✅ | 已集成 RLock + AgentSnapshot |
| `dream()` | ❌ 占位 | ❌ | 仍为 placeholder |

**新增发现**:

```python
# master_agent.py:116-117
self._engine_bridge: Any = None  # set by injection or externally

# master_agent.py:146-148
def set_engine_bridge(self, engine_bridge: Any) -> None:
    """Phase 22-A: 注入 EngineBridge 供 act() 真实化使用。"""
    self._engine_bridge = engine_bridge
```

EngineBridge 类存在（`ocos/agent/engine_bridge.py`），但 **未被自动注入**。需要外部调用 `set_engine_bridge()` 才能激活。

### 3.4 Runtime 层 ✅

**未变**。Scheduler 优先级队列调度正确。

### 3.5 Identity 层 ✅

**未变**。Phase 21 已通过 AgentSnapshot 实现 `born_at`/`owner_id` 持久化。

### 3.6 Memory 层 — 更新 ⚠️

**未变**。Episode/Belief/Pattern 仍为内存存储。

### 3.7 Engine 层 — 大幅更新 🔄

**引擎数量**: 76 个（原审计 17 个，差异来自扩展引擎和 runtime engines）

| 类别 | 数量 | 说明 |
|------|------|------|
| 核心引擎（`ocos/engines/`） | 18 | reasoning/decision/planning/simulation/learning/reflection/prediction/consolidation/promotion/forgetting/retrieval/arbitration/narrative/text_generator/writer 等 |
| Runtime/Extension 引擎 | 22 | agent_engine/memory_engine/knowledge_engine/self_audit_engine 等 |
| 自定义引擎（用户定义） | 36 | `custom_reasoning_engine`、`custom_consultancy_engine` 等 |

**Engine 类统计**:
```
ocos/engines/ — 27 个引擎类定义
ocos/capability/ — 16 个引擎类定义  
ocos/cognitive_loop/ — 8 个引擎类定义
其他（evolution/storage/runtime 等）— 25 个引擎类定义
```

**关键引擎**:
- `EngineBridge` — 已实现但未自动注入
- `MigrationEngine` — 已实现，但 `MigrationState` 仅支持 `PENDING/IN_PROGRESS`
- `AgentEngine`（runtime）— 用于非对话场景的独立运行
- `ConstitutionViolationError` — 在 `behavioral.py` 中定义，`master_agent.py` 中抛出

---

## 四、19 维度数字生命体审计（更新）

### Dim 1 — 生命模型 ✅ (85/100)
**未变**。

### Dim 2 — Master Agent 诞生条件 ⚠️ (58/100)
**变化**: EngineBridge 未自动注入，降低了诞生条件的完备性。

### Dim 3 — 引擎权威性 ✅ (95/100)
**未变**。

### Dim 4 — Runtime 权威性 ✅ (90/100)
**未变**。

### Dim 5 — 记忆连续性 ❌ (30/100)
**未变**。

### Dim 6 — Identity 持久性 ⚠️ (50/100)
**改进**: Phase 21 已实现 `born_at`/`owner_id` 持久化（`identity_anchor.py:43, 71-72, 95-97, 134-135, 146-152`）。

### Dim 7 — 能力契约 ⚠️ (70/100)
**变化**: EngineBridge 未注入 + AgentLifecycleManager 缺失。

### Dim 8 — 生产就绪度 ⚠️ (40/100)
**变化**: CircuitBreaker 重复定义（stability + retry_policy），MigrationState 状态有限。

### Dim 9 — Phase 21 完整性 ✅ (65/100)
**改进**: Phase 21 已完成，但 EngineBridge 注入和 congruity check 需后续 Phase 补齐。

### Dim 10 — Phase 22-28 排序 ✅ (85/100)
**未变**。

### Dim 11 — 意识评分 ⚠️ (48/100)
**变化**: act() 有 EngineBridge 框架但需注入，congruity check 缺失。

### Dim 12 — Goal ⚠️ (50/100)
**未变**。

### Dim 13 — Self ⚠️ (45/100)
**未变**。

### Dim 14 — Value ❌ (0/100)
**未变**。

### Dim 15 — Life Continuity ❌ (30/100)
**未变**。

### Dim 16 — Information Lifecycle ⚠️ (55/100)
**未变**。

### Dim 17 — Capability Architecture ⚠️ (65/100)
**变化**: 76 个引擎类，EngineBridge 未自动注入。

### Dim 18 — Homeostasis ⚠️ (35/100)
**未变**。

### Dim 19 — Governance ⚠️ (60/100)
**未变**。

---

## 五、关键发现（新增/变化）

| 优先级 | 发现 | 类型 | 状态 |
|--------|------|------|------|
| **P0** | `EngineBridge` 未自动注入 — `MasterAgent._engine_bridge = None` | 实现缺口 | 需 Phase 22-A 完成 |
| **P0** | `congruity check` 未在 `act()` 后实现 | 功能缺失 | Phase 26 计划 |
| **P0+** | `AgentLifecycleManager` 缺失导致 test_phase24 收集错误 | 实现缺口 | 需恢复或更新测试 |
| **P1** | `CircuitBreaker` 重复定义 — `stability/` 和 `agent/retry_policy/` | 代码重复 | P2 清理 |
| **P1** | `PermissionGuard` 已覆盖 50+ 处交互入口 | ✅ 改进 | 已部分完成 |
| **P2** | `MigrationState` 仅支持 PENDING/IN_PROGRESS | 功能限制 | Phase 21.04 可扩展 |

---

## 六、测试体系审计

| 指标 | 数据 |
|------|------|
| 源码文件数 | 693 |
| 测试文件数 | 136 |
| 源码总行数 | 131,034 |
| 测试总行数 | 31,312 |
| 通过率 | 3134 passed / 22 skipped / 1 error |
| 错误来源 | `tests/test_capability/test_phase24.py` — `AgentLifecycleManager` 缺失 |

---

## 七、结论与建议

### 7.1 完成 Phase 22-A：EngineBridge 自动注入

```python
# 建议：在 MasterAgent.__init__() 中自动注入
def __init__(self, ...):
    ...
    self._engine_bridge = EngineBridge(self)  # 自动创建
```

### 7.2 补充 congruity check

在 `act()` 方法中添加一致性验证：
```python
def act(self, decision: Decision) -> ActResult:
    ...
    result = self._engine_bridge.act(self, decision)
    # Phase 26: 添加一致性验证
    if not self.check_congruity(result):
        logger.warning("Act result not congruent with identity")
    return result
```

### 7.3 恢复 AgentLifecycleManager

在 `ocos/capability/lifecycle_manager.py` 中重新实现或重新导出：
- `AgentLifecycleManager`
- `AgentHandle`
- `AgentState`
- `ConnectMethod`

### 7.4 清理重复 CircuitBreaker

选择一处保留（建议 `stability/circuit_breaker.py`），删除另一处。

### 7.5 扩展 MigrationState

添加 `COMPLETED/FAILED/CANCELLED` 状态。

---

## 八、最终裁决

```
┌──────────────────────────────────────────────────────┐
│  Go — Phase 21+ 完成，Phase 22-A 待推进              │
│                                                      │
│  新增发现：                                           │
│    • EngineBridge 已实现但未自动注入 ⚠️               │
│    • congruity check 未实现 ❌                        │
│    • AgentLifecycleManager 缺失 ❌                    │
│    • CircuitBreaker 重复定义 ⚠️                       │
│                                                      │
│  评分变化：                                           │
│    • 架构完整性: 84 → 82                             │
│    • 实现完备性: 54 → 52                             │
│    • 生产就绪度: 64 → 63                             │
│    • 能力编排:   59 → 58                             │
│                                                      │
│  下一步: Phase 22-A EngineBridge 注入 +               │
│          Phase 26 congruity check +                   │
│          Phase 24 AgentLifecycleManager 恢复          │
└──────────────────────────────────────────────────────┘
```

---

*审计完成于 2026-08-28 | 基于只读审计与最新单元测试运行结果*

---

## 九、GAP-P2 阶段决策记录（追加，2026-08-29）

### P2-1 SemanticStore 写入管道
- KnowledgeRegistry 增加可选 semantic_store 注入；register/update/remove 三写点
  自动同步 knowledge 表（KnowledgeUnit→KnowledgeEntry 映射）。
- 修复 SemanticStore.save 死代码：knowledge 表 id PRIMARY KEY（单行模型），
  原实现按多行版本链假设预标记 SUPERSEDED 再 INSERT，revision>1 必然触发
  UNIQUE 冲突 → 更新静默丢失。改为 UPSERT（ON CONFLICT 就地覆盖，
  created_at 保留首版时间，revision 演进）。**单行模型下无历史行，
  版本链 = revision 数字演进，历史内容不可查（schema 决定，非缺陷）。**
- deprecate 放宽至 ACTIVE/UNSTABLE 均可弃用（候选单元 remove 不再失效）。
- 生产装配点：factory.build_knowledge_registry(semantic_store=MemoryHub.semantic)。

### P2-2 runtime/stages 4 个占位接线
- **event_ingestion** → EventBus.ingest(max_events) drain（可注入，缺省空）。
- **execution_check** → TaskDAG.resolve_ready() 生成 execution_candidates
  （ocos/task 首个生产消费者）；gateway 权限过滤保留。
- **memory_sync** → 决策：MemoryHub 是 store 聚合门面，无"差异同步"API；
  收敛为转发语义——注入 hub 后 get_stats() 快照注入 context.memory_changes
  （只反映状态，不写长期记忆，符合阶段约束）。
- **result_collection** → 决策：RuntimeKernel 不持有 ExecutionManager
  （agent/execution_manager 属 AgentRuntime 侧）；收敛为转发语义——
  注入后 get_history() 只读转发，不消费不清空。
- 全部 stage 惰性注入（构造参数 Any，模块零新 import），零注入=旧行为。
