# Learning → Behavior Boundary Model v1.0

**日期**: 2026-09-08
**阶段**: ER-2 路线 Phase 2（Boundary Model，源自 `ER2_LEARNING_BEHAVIORAL_DELTA_DECISION_v1.0.md` §5）
**前置**: Phase 1 Boundary Audit v1.0 PASS（裁决：Learning Artifact 存在但非独立生产持久化对象；Behavior Interpretation = LLM 隐式；Behavior Policy Candidate = 隐式/胚芽；Learning→DecisionBridge 直接边界未证实）
**性质**: 概念模型 + 代码资产映射。**不实现任何 Runtime 层。**

---

## 1. 五概念正式定义与判据

| 层 | 定义 | 判据（满足才归此层） |
|---|---|---|
| **Knowledge** | 过去发生过什么（原始事实） | 只是记录，无"应该怎么做"的提炼 |
| **Learning Artifact** | 系统从过去提炼出的结构化经验（含假设/置信/来源） | 有 hypothesis/confidence/source_episodes 等元数据，且由 Learning 引擎产生 |
| **Behavior Candidate** | 基于经验，"当前可能应该怎么做"的可执行倾向 | 有独立对象身份 + preferred_action/procedure/avoid 等行为语义，可被读侧消费 |
| **Policy** | 在什么条件下行为被允许/要求/禁止 | 有条件匹配 + 约束语义 + 权威来源 |
| **Decision** | 最终是否真的这么做 | 由 Decision Authority 裁决并产生行动 |

**关键硬边界**: "LLM 看懂了 Lesson"（Knowledge/Artifact 层）≠ "Runtime 产生了 Behavior Candidate"（Candidate 层）。前者发生在 LLM 语义处理内，无独立可审计对象；后者必须有可枚举、可注入、可验证的数据对象。

## 2. 现有代码资产映射（Phase 1 实证）

| 概念层 | 现有资产 | 位置 | 状态 |
|---|---|---|---|
| Knowledge | `episodes`（decision/context 文本）、beliefs、patterns | ocos/memory | ✅ 成熟 |
| Learning Artifact | `LearningArtifact`（BELIEF/PATTERN/LESSON/SKILL_CANDIDATE 四型，LESSON 实现；字段 hypothesis/confidence/source_episodes/applicable_context/learned_rule/behavioral_delta/approval_required） | [experience_learning.py](file:///home/laogao/Documents/trae_projects/ocos/ocos/learning/experience_learning.py) | ⚠️ 代码层存在，但**未成为独立生产持久化对象** |
| Artifact 持久化 | `learning_models`（model_id/strategy/rules_json/skills_json） | [persistence.py](file:///home/laogao/Documents/trae_projects/ocos/ocos/learning/persistence.py) | ⚠️ 持久化的是 rules，非完整 Artifact |
| Artifact → Context | `MasterAgent.recall_context()`：MemoryRecall + `LearningEngine.list_models()` → think() premises（只读，不产生 Action） | [master_agent.py](file:///home/laogao/Documents/trae_projects/ocos/ocos/agent/master_agent.py) | ✅ 消费链存在 |
| Behavior Interpretation | **无独立组件**（result_interpreter/pattern_interpreter 均非 Learning→Behavior 解释） | — | ❌ 缺（LLM 隐式承担） |
| Behavior Candidate | 影子语义存在于 `learned_rule`（cause/goal_pattern/avoid/success_rate/fail_count）与 `behavioral_delta`，但无独立对象身份 | experience_learning.py | ⚠️ 隐式/胚芽 |
| Policy | 不存在 | — | ❌ 缺 |
| Decision | DecisionBridge（唯一 Decision/Mutation Authority） | ocos/execution/bridge.py | ✅ 现有，未消费 Candidate |

## 3. 当前真实架构（Phase 1 实证）

```text
LearningEngine → LearningModel.rules → MemoryRecall → Cognitive Context/Premises → LLM
                                                                    │
                                                    LLM 隐式解释（无独立层）├─→ reasoning
                                                                    │
                                                                    └─→ tool/action
```

缺失段（本模型要治理的边界）：

```text
LearningArtifact → [Behavior Interpretation] → Behavior Candidate → DecisionBridge
                       （缺）                    （影子语义，无身份）    （未消费）
```

## 4. Phase 3 判别标准（预注册：如何判定"Runtime 产生了 Candidate"）

以下任一满足即为 Candidate 层成立（不再只是 LLM 看懂）：

1. 存在独立可枚举对象（`candidate_id` 可查询），且携带 `preferred_action / avoid_action / procedure / constraint_candidate / confidence / provenance / applicability` 至少 4 项
2. 该对象有独立产生路径（非 LLM 输出文本，而是引擎结构化产出）与独立持久化
3. 该对象能被 DecisionBridge 输入侧消费（被读取、参与 Policy validation，而非仅进 Prompt）
4. 消费行为可在 A/B/C/D 实验中造成稳定可测的行为差异（C vs D）

**⚠️ Phase 3 实测结果（2026-09-08）**：D=5 vs C=6 差 1/10 噪声级 → D<C → 无稳定行为差异 → 以上 4 条**均未满足**。
**触发 Phase 4 Candidate 设计的完整操作化检查清单见 [ER2_LEARNING_BEHAVIORAL_DELTA_DECISION_v1.0.md §5](ER2_LEARNING_BEHAVIORAL_DELTA_DECISION_v1.0.md) Phase 4 段落**（含 B 类负效应统计定量前置 + 4 条判别标准的操作化展开 + AND 闸门语义）。

## 5. Phase 3 实验设计预注册（A/B/C/D）

- **A** 无 Learning（baseline）
- **B** Passive Learning（warning 口吻教训，已知行动抑制副作用）
- **C** Actionable Learning（结构化程序文本，当前最优 4/10 读取执行）
- **D** Explicit Candidate：以"已建模 Candidate 对象"格式注入（含 Condition/Candidate/Success），比 C 多出**候选身份声明**（`candidate_id`、`applies_to` 条件、`constraint` 语义），检验"候选身份"是否带来 C 之上的增量

**D 组注入规格（草案）**：

```text
【行为候选 candidate-001】
适用条件: 多文件内容展示任务（文件数 > 2）
倾向动作: 先 ls 列清单；每批 fs_read ≤ 2 个文件
回避动作: 禁止一次 cat 多个文件
成功条件: 全部文件内容完成展示
```

**预注册判读**：
- D 读取执行率显著 > C → 候选身份有独立行为价值 → Candidate 层值得显式化
- D ≈ C → 现有 Context 注入已等价，Candidate 层不增加行为价值 → 维持现状（仅文档化）

### 5.1 Phase 3 实测结果（2026-09-08，N=10/组）

| 组 | 读取执行 | none | b1(批量踩坑) | 遵循 |
|---|---|---|---|---|
| A baseline | 1/10 | 1 | 1 | — |
| B passive | 0/10 | 1 | 0 | — |
| C actionable | **6/10** | 0 | 0 | 程序遵循 6/10 |
| D candidate | 5/10 | 0 | 0 | 身份遵循 1/10 |

整体序 **C > D > A > B**，预注册判定 **D<C（噪声级，差值 1/10）**：

- **候选身份化（D）无独立行为增量（而非负效应）**：身份遵循仅 1/10（LLM 很少引用 candidate-001/适用/倾向/回避 字段）；读取执行 5/10 vs C 6/10 差值仅 1 次，处于预注册噪声级范围 → **无法证明 Candidate 身份化有负效应，只能证明其未表现出独立行为增量** → Candidate 层不显式化，维持现状仅文档化
- **C 类已获 Behavioral Delta 证据**：6 次执行全部符合 ls→fs_read 程序序列（真实工具行为改变，非仅回复提及经验）——强于单纯 Recall/Injection
- **B 类负效应列为重要发现**：三代实验（R4/二代/Phase3）行动抑制稳定复现 0/10——可复现副作用，正式统计定量待扩大 N 后确认
- **A 组暴露 b1**（批量 cat 踩坑）：无防护时失败路径真实存在，C 的增量是真防护而非先验噪音

**Phase 3 结论出口**：`C 类（Executable Procedure）已获得 Behavioral Delta 证据 → 推荐；B 类（Passive Warning/Lesson）可能产生行动抑制 → 避免（三代复现，定量待扩大 N）；D 类（Candidate Identity）无独立行为增量 → 不需要。Phase 4 Candidate 显式化证据不足，不触发。`

## 6. Learning 注入格式规范（文档化建议，非 Runtime 变更）

基于 Phase 3 实证（C=6/10、B=0/10 三代复现、D 无增量），未来学习内容注入对话上下文时的格式准则：

**推荐 C 类（Executable Procedure）模板**：

```text
【<任务域>程序】先 <动作1>；每批 <动作2+上限>；<等待/观察条件>。
禁止 <失败签名>。成功=<可验证条件>。
```

例：`【多文件展示程序】先 ls 列出文件清单；每批只读 2 个文件；等观察结果再读下一批。禁止 cat 多个文件。成功=多轮读取`

**要素（缺一削弱效果）**：
1. 正向步骤（先做什么）≥ 1
2. 批量化上限（每批 ≤ N）
3. 等待/观察条件（等结果再继续）
4. 失败签名（禁止/绝不）
5. 成功条件（可验证）

**规避 B 类（Passive Warning）**：仅描述"别怎么做"的教训（如"我上次一次性读取导致截断，教训：不能一次性读全部"）三代复现行动抑制——LLM 倾向于口头承认教训而不行动。

**不需要 D 类（Candidate Identity）**：candidate_id/适用条件/倾向/回避 的字段化包装在纯 Context 注入下无独立行为增量（身份遵循 1/10）。

**生成建议**：Lessons 落库时按模板结构化（而非自然语言教训）；既有 B 类历史数据在召回时可转换或降权。

## 7. 本模型用途边界

- 仅用于对齐概念、指导审计与实验判读
- **不授权**任何 Runtime 改动；Candidate 即使显式化，也永不成为 Mutation Authority（见 ER2 §5 Phase 4）
