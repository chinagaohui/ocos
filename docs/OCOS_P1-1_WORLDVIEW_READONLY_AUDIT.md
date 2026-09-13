# OCOS P1-1 Worldview — READ-ONLY REALITY & BOUNDARY AUDIT

> 状态：**READ-ONLY，已停止。等待 Human Gate 裁决。**
> 本报告只审计"OCOS 是否真的形成了属于'我'、由经历产生的、可追溯的世界判断，并在后续 Thinking 中真正使用"。未修改任何代码 / schema / prompt / decision semantics / 控制流。

---

## 1. Executive Verdict

> **NOT-IMPLEMENTED。**

OCOS **当前不存在**任何自归（self-owned）的 Worldview 载体、来源、Delta 或 Thinking 消费：

- `SelfState`（S2）与 `AgentSelfModel`（S1）的 Self 模型**恰好五个组件**（capability / knowledge_boundary / experience / preference / cognitive_state），**无 worldview 字段**，且 `SelfModel.update()` 的 `valid_components` 白名单会**拒绝**任何 worldview 类字段；
- 全代码库 `worldview` 一词仅出现在**负面文档字符串**（明确 "✗ 不做 Worldview / ✗ 7 域归并（Situation/Worldview）"），无任何定义或引用；
- 可被误认的最接近结构（外部 `WorldStore`、`belief`、`knowledge`）均**不是**自归 Worldview，且端点上已存在二义性注入风险。

最核心结论：**存在极成熟的"事件→证据→claim→delta→governed commit→S2 fidelity"基础设施，但这条管线当前被硬编码为只写五个 Self 组件；worldview 在语义上就是"没有座位"。**

---

## 2. Current Worldview Reality

```text
Reality ──✓──> Observation ──✓──> Experience ──✓──> Recognition ──✓──> Self Judgment(5域)
                                                                              │
                                                          Worldview Judgment ✗ 无目标组件
                                                                              │
                                                          SelfState.worldview ✗ 不存在
                                                                              │
                                                          Thinking ←── ✗ 无消费
```

- 真实、生产可达、带 Provenance 的 Self 变更链**存在**，但只落 `capability_awareness / knowledge_boundary / experience_profile / preference_model / cognitive_state`。
- "由外部世界经历形成的'我'的世界判断" 这一语义在 Self 层**完全没有落点**。

---

## 3. Carrier Audit

| 候选 | semantic role | 生产可达 | 持久化 | 可变 | provenance | consumer | 是否 Worldview |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `SelfState.worldview` | 应承载 Worldview | — | — | — | — | — | ❌ **不存在**（字段未定义） |
| `AgentSelfModel`(S1) | 行为 Self 模型，仅 Evidence 身份 | ✓ | ✓ | ✓(受限) | ✓(S1 Evidence) | 旧执行链路 | ❌ 无 worldview 字段 |
| `SelfModel`(S2) 5 组件 | 能力/知识边界/经历/偏好/认知态 | ✓ | ✓ | ✓ | ✓(SelfUpdateContract) | Thinking 投影 | ❌ 均为 self 组件但**非 Worldview** |
| `belief`（belief 表 / BeliefManager） | 信念：带证据的命题 | ✓ | ✓(schema) | ✓ | ✓(evidence_ids/source/confidence) | 上下文/召回 | ❌ 按红线"Belief ≠ Worldview" |
| `knowledge` / KnowledgeBoundary | 知识/边界声明 | ✓ | ✓ | ✓ | ✓ | 上下文/召回 | ❌ 事实/边界 ≠ 世界判断 |
| `WorldModel`/`WorldStore` | **外部**世界的结构化表示 | ✓(生产) | ✓ | ✓ | ✓(StateChange/CausalityLink) | converse/decision bridge | ❌ 按红线"WorldModel ≠ Worldview" |
| `reflection`(REFLECTION source) | 自我洞察 → 5 组件 | ✓ | ✓ | ✓ | ✓ | S2 commit | ❌ 反思输出仍落 5 组件，无世界观组件 |
| `experience` / `memory` | 经历与记忆 | ✓ | ✓ | — | ✓ | 召回/consolidation | ❌ 素材，非判断 |

**判定**：无任何候选本身就是"自归 Worldview"。

---

## 4. Production Source Audit

目标链：`Reality → Observation → Experience → Recognition → Worldview Judgment`

| 步 | 存在? | file:line | caller / 运行时路径 | 等级 |
| --- | --- | --- | --- | --- |
| Reality→Observation | ✓ | [perception/pipeline.py:7](file:///workspace/ocos/perception/pipeline.py) 描述生产链；tick 写入 [pipeline.py:114-166](file:///workspace/ocos/perception/pipeline.py#L114) | daemon factory 组装 [factory.py:375](file:///workspace/ocos/daemon/factory.py#L375) `PerceptionPipeline(world=WorldStore(),...)` | R4-ACTIVE |
| Observation→WorldStore(外部) | ✓ | [pipeline.py:146](file:///workspace/ocos/perception/pipeline.py#L146) `_bridge_to_world` 写 WorldStore | 同上 | R4/R5 |
| Recognition→SelfClaim→Delta | ✓(限 5 域) | [self_evidence.py:343-373](file:///workspace/ocos/self/self_evidence.py#L343) `ingest()`；Recognition 后写 claim/delta/commit | SelfEvidencePipeline → SelfStateManager | R4/R5 |
| **Worldview Judgment→SelfState.worldview** | ✗ | **无目标组件**；`SelfModel.update()` 白名单 [self_types.py:337-340](file:///workspace/ocos/self/self_types.py#L337) 拒绝 | 无 | **UNWIRED / 语义缺失** |

- 生产链**前端存在且实际运行**（感知→外部世界模型 + 证据→5 域 Self commit）。
- 但"Worldview Judgment"这一步**没有可写目的组件**：任何含 worldview 的更新会被白名单拒绝 → **UNWIRED（目标缺失）**，非"仅测试"。

---

## 5. Provenance Audit

问题："我为什么形成这个判断？"

**基础设施完备，但无可承载对象。**

- `SelfUpdateContract` 带 `source/reason/tick/fields_changed/evidence_ids/claim_id/confidence_impact` [self_types.py:79-90](file:///workspace/ocos/self/self_types.py#L79)：可回答"某个 Self 组件为何变了"。
- `SelfDelta` 带 `old_value/new_value/source/confidence_impact` [self_evidence.py:118-131](file:///workspace/ocos/self/self_evidence.py#L118)；`delta_from_claim()` 从 committed Self 算 A→B [self_evidence.py:257-299](file:///workspace/ocos/self/self_evidence.py#L257)。
- `WorldStore` 事件/因果带来源与证据：`WorldEvent.source/tick` [world_types.py:199-215](file:///workspace/ocos/world_model/world_types.py#L199)、`CausalityLink.cause_event_id/evidence_ids/counter_evidence_ids` [world_types.py:237-257](file:///workspace/ocos/world_model/world_types.py#L237)。
- `belief` 带 `evidence_ids/source_knowledge_ids/confidence/uncertainty/scope` [schema.py:132-149](file:///workspace/ocos/storage/schema.py#L132)。

> 由于 worldview 组件不存在，**对"Worldview Claim"成立 provenance 无从谈起** → 对该语义标记为 **NO PROVENANCE**（语义缺失，而非机制缺失）。

（红线 11 提示的"禁止把原始 DB aggregation 当成 Self-owned Worldview"对于 `WorldStore.cognitive_world_state()` 尤其适用——它只是外来实体/关系聚合。）

---

## 6. Worldview Delta Audit

目标：真实 `W0 → Experience X → Contradiction/Recognition → Worldview Delta → W1`，且 `W1 != W0`。

- Self 层 **Delta 机匣存在**：`SelfDelta(old,new,evidence,confidence)` + `SelfUpdateContract` + govern commit [self_state.py:395-426](file:///workspace/ocos/self/self_state.py#L395)。
- `WorldStore` 有 `StateChange(from_state_id,to_state_id,changed_keys,cause_event_id)` [world_types.py:93-103](file:///workspace/ocos/world_model/world_types.py#L93)。

但这两套 delta 都是**非 worldview** 对象（5 域 Self 组件 / 外部实体状态）。**不存在任何承载 W（worldview）的 delta** → Worldview Delta = **N/A / 缺失**。禁止用 `version+1 / prompt+1 / knowledge/Belief+1` 冒充（红线 1、11）。

---

## 7. WorldModel / Worldview Boundary

- 代码已正确区分：`WorldModel` 模块自述 "World Model ≠ Knowledge Base/Belief/Goal" [world_model/__init__.py:18-22](file:///workspace/ocos/world_model/__init__.py#L18)；SelfEvidence 明确 "✗ 做 Worldview/WorldModel 持久化" [self_evidence.py:18](file:///workspace/ocos/self/self_evidence.py#L18)。
- **无语义碰撞**（因为 self 侧根本不存在 worldview 可被碰撞），但存在**二义性注入风险点**：`WorldStore.cognitive_world_state()` 被作为上下文行注入 `converse`（"世界状态: N 实体/N 关系", [converse.py:1091-1098](file:///workspace/ocos/interaction/converse.py#L1091)）。这一外部世界摘要**绝不能**被日后误标为 "Self Worldview"。标记为 `semantic collision (哈希值)` 待防。
- **结论**：WorldModel≠Worldview 这一冻结红线在现状下**天然成立**（未被违反），但也意味着"WorldModel 永远不会自己变成 Worldview"。

---

## 8. Worldview → Thinking Consumption

问题：`SelfState.worldview → Thinking` 是否存在。

- **无 Worldview 可消费** → 无该种消费。
- 现存接近项（非 worldview）：
  - `WorldStore` 世界状态 → context 行 [converse.py:1091]（**CONTEXT-ONLY**，无行为约束）；
  - `WorldStore` / Attention → DecisionBridge 注入 [agent_runtime.py:1646-1678](file:///workspace/ocos/agent/agent_runtime.py#L1646)（**Decision 语义供源，非 worldview**）；
  - S2 5 域经 `SelfProjectionAccessor` → Thinking 投影 [agent_runtime.py:548-581](file:///workspace/ocos/agent/agent_runtime.py#L548)（这是**真·Self→Thinking**，但内容是 5 域，非 worldview）。

> 结论：**Worldview→Thinking = N/A**。切不可把以上外部/context 注入算作 "Thinking consumed worldview"（红线 10、12）。

---

## 9. Counterfactual / Continuity

目标：`W0(无 X) / X(真实经历) / W1(经历 X 后) / Z(若无 X，Thinking 是否仍用 W0)`。

- **反事实机匣已存在（P0 级）**：`counterfactual_baseline`（Z 冻结）+ `SelfDelta` + P0-4 因果链，证明"过去 X 能可审计改变 5 域 Self 与行为"。
- **事件连续性**：`continuity_trigger`/`load_continuity` 被读入 context [converse.py:1102-1108](file:///workspace/ocos/interaction/converse.py#L1102)。
- 但这两者都**不是 worldview** 的反事实。对"Worldview W0/W1/Z"并无承载 → Q7 对 worldview = **记录缺口（N/A）**，不补实现，仅记录。

---

## 10. Evidence Matrix

证据等级：R0 定义 / R1 测试 / R2 接线 / R3 生产可达 / R4 生产活跃 / R5 生产持久 / R6 行为消费 / R7 因果验证。

| 对象 | 等级 | 说明 |
| --- | --- | --- |
| `SelfModel.worldview` 字段 | **R0 缺失** | 无定义；[self_types.py:297-301](file:///workspace/ocos/self/self_types.py#L297) |
| `SelfUpdateSource` 世界观来源 | **R0 缺失** | 枚举仅 5 来源 [self_types.py:35-55](file:///workspace/ocos/self/self_types.py#L35) |
| Self 5 域 Evidence→Claim→Delta→S2 | **R5/R6** | [self_evidence.py:343](file:///workspace/ocos/self/self_evidence.py#L343)、[self_state.py:395](file:///workspace/ocos/self/self_state.py#L395) |
| WorldStore（外部世界模型） | **R4/R5**（R6 仅 context） | 感知写入 + converse/decision 读取 |
| belief（信念） | **R5** | 持久化，带 evidence |
| Worldview→Thinking 全链 | **R0/R1（无）** | 语义不在 |

关键提示：`R3/R4 ≠ R6`，`R6 ≠ R7` 在此全部成立；**没有任何一条连到 "Worldview"**。

---

## 11. Production Reachability Matrix

| 资产 | import 来源（生产，非测试） | 是否主链可达 | 语义角色 |
| --- | --- | --- | --- |
| `SelfState/accessor` | agent_runtime L548、converse L968、bridge L2428 | ✓ 主链 | 真身 5 域 Self |
| `WorldStore` | daemon/factory L375、perception/pipeline L28、converse L1091、agent_runtime L1662 | ✓ 主链 | 外部世界模型（非 worldview） |
| `believe` | recall_router、agent_runtime | ✓ | 信念（非 worldview） |
| `SelfEvidencePipeline` | self_evidence | ✓ | 证据→5 域 claim/delta |
| `DecisionBridge` | agent_runtime L1678 | ✓ | 决策供源 |

---

## 12. Semantic Gaps

1. **无 Self 级 Worldview 组件/座位**（`SelfModel` 仅 5 组件；白名单拒绝 worldview）。
2. **无 Worldview 类 SelfUpdateSource**（无 "worldview / situation / reinterpretation" 来源）。
3. **无 Worldview Judgment→Claim→Delta 管线目标**（前端证据链完备，终点缺失）。
4. **WorldModel 外部化**（WorldStore 是外部世界表示，非自归；红线 8 禁止冒充）。
5. **belief/knowledge ≠ Worldview**（红线 9 禁止冒充）。
6. **prompt/context 注入 ≠ Thinking 消费**（红线 10、12；converse L1091 仅 context）。

---

## 13. Minimal Architecture Gap（只陈述，不实现）

若要 P1-1 真正成立，**最小增量**（复用既有设施，无并列 runtime，无新 authority，不进 P1-2/P1-3，不重构 Converse）：

> 在既有 S2/SelfModel 内**增补一个自归 worldview 组件并把它的 "judgment→claim→delta→commit" 接到既有 Evidence/契约管线上**，再经既有投影注入 Testing。其余全部基础设施已存在，不需新建。

具体最小缺口点（按"复用优先"排序）：
- **G1（核心）**：`SelfModel` 新增 worldview 组件，并加入 `valid_components` 白名单 [self_types.py:337-340]（否则任何更新被拒）。
- **G2（来源映射）**：确定 worldview 的来源语义。**优先复用**既有 `SelfUpdateSource.REFLECTION / RUNTIME_OBSERVATION`（世界理解作为自归洞察/观测产物），避免新增 authority；仅当无法语义归类时才需新增枚举成员（属 decision-semantics 变更，需单独立项）。
- **G3（判定/管线）**：把外部世界证据（可取自 `WorldStore` / `belief` 事件）转成一条 worldview `SelfClaim`，走既有 `SelfEvidencePipeline.ingest()` → `SelfDelta(old,new,evidence,confidence)` → govern commit（整条链路已存在）。
- **G4（消费）**：经既有 `SelfProjectionAccessor` 输出 worldview，并在决策侧做**实际消费点接线**——此点已知受 P0-4B 的 B1–B5（生产单入口缺失 + fused-before-action 时序）阻塞，按 P0-4 冻结处理，不得为它重构 Converse。

> 唯一**必须新增**的就是 G1（一个组件座位）——它依 G3 复用全部证据/provenance/delta 设施；G4 是 P0-4B 遗留的接线缺口，不是本阶段可独立补的。

---

## 14. P1-1 Gate Recommendation

**门裁定：NOT-IMPLEMENTED（不通过，不进入实现）。**

- 理由：没有可信的**自归 Worldview 载体**，也无任何生产语义（非"有候选结构但链断了"的 BLOCKED，而是"语义角色本身不存在"的 NOT-IMPLEMENTED）。
- 建议：P1-1 以 **Design / 立项** 而非 Implementation 进入，聚焦 §13 的 G1–G4 设计（尤其 G1/G3 是否会引入 decision-semantics 变更需单独立项），并由 Human Gate 裁决后再考虑实现。
- 不得为避免 NOT-IMPLEMENTED 而扩大实现范围（红线）。

---

## 15. Explicit Non-Goals

本阶段不解决：
- 不实现 worldvew 组件 / 来源 / delta / 消费（只读审计）。
- 不改 `world_model` 为 "worldview"，不把 `belief/knowledge` 升级为 worldview。
- 不改 Converse/Bridge 控制流来制造 pseudo-consumption。
- 不进入 P1-2 / P1-3 认知功能。
- 不为通过审计造证据。

---

## 16. Frozen Redlines

本阶段冻结（延续 P0 纪律）：
1. 不修改任何生产代码 / DB schema / Prompt / Decision semantics / Converse 控制流。
2. 不新建 Runtime / 第二套 Self。
3. 不把 WorldModel 当 Worldview；不把 Belief 当 Worldview。
4. 不把 Prompt Context 当 Thinking Consumption；不把 DB aggregation 当 Worldview Provenance。
5. 不用最终行为反推 Worldview 已被消费；不补造证据。
6. Worldview 语义缺口保持登记，不掩饰、不越界实现。

---

*本报告为只读审计产物，已停止。等待 Human Gate 裁决后再决定是否进入 Writing / 实现阶段。*