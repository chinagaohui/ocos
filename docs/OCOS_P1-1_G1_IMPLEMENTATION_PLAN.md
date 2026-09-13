# OCOS P1-1 G1 — Implementation Scope / Plan + Safety Audit

> 状态：**G1 Implementation Authorization 的裁决材料（准备文档）。G1 Implementation = 仍 NOT AUTHORIZED。**
> 承接：`G1_SHAPE_DESIGN`（ACCEPTED / FROZEN）。本文件**不再设计语义、不再重开契约**，只回答：
>
> **"按已 ACCEPTED 的 G1 Shape Design，实施是否安全、最小、可验证，以及实施后如何证明没有破坏既有 SelfState / persistence / governance / prompt 行为？"**
>
> 本文件同样是只读产出：**未改任何代码**。

---

## 0. Gate 流程定位

```text
G1 Design ACCEPTED ──→ 本文件（Scope/Plan + Safety Audit）──→ Human Gate ──→ G1 Implementation GO / NO-GO
```

## 1. 实施范围（精确到文件与变更）

全部变更**仅 5 个文件**（1 个新建），对齐已 ACCEPTED 的 G1 Design §12：

| # | 文件 | 变更 |
| --- | --- | --- |
| 1 | `ocos/self/self_types.py` | +`StanceType` / +`ContinuityKind` / +`WorldViewJudgment`；+`SelfModel.worldview: Optional[Any] = None`；`valid_components` 追加 `"worldview"`；+`has_worldview`；docstring 五→六组件 |
| 2 | `ocos/self/worldview.py`（新建） | +`WorldView` 容器（judgments dict / count / overall_confidence / get / declare / summary） |
| 3 | `ocos/self/self_state.py` | `_TYPE_REGISTRY` 追加 4 类型（WorldView / WorldViewJudgment / StanceType / ContinuityKind）——**生死线** |
| 4 | `ocos/self/self_model.py` | +imports；`create_self_model` 增 `worldview=None`；`initialize_empty_components` 补 init；+`update_worldview`；`__all__` |
| 5 | `ocos/self/__init__.py` | +导出（WorldView / WorldViewJudgment / StanceType / ContinuityKind / update_worldview） |

**明确不在本范围**：`render()/brief()`、`self_summary()`、`context_builder.py`、`decision_pipeline.py`、`self_evidence.py`（G3）、schema（无 DB 变更）、converse/bridge/recall_router/agent_runtime/decision_*。

## 2. 不触碰清单（No-TOUCH，附审计证据）

| 资产 | 为何不碰 | 证据 |
| --- | --- | --- |
| `render()/brief()` | 输出进生产 prompt 槽位，改 = 改 prompt = G4 | [self_state.py:514-559](file:///workspace/ocos/self/self_state.py#L514)；消费点 [converse.py:971](file:///workspace/ocos/interaction/converse.py#L971)、[bridge.py:2431](file:///workspace/ocos/execution/bridge.py#L2431) |
| `self_summary()` | **无生产消费者**（仅导出），决策上下文当前是占位串 | [decision_pipeline.py:74](file:///workspace/ocos/cognitive_loop/decision_pipeline.py#L74)；grep 无 import 方 |
| `components_loaded` | 无生产消费者、无测试断言其数值 | [self_types.py:366-373](file:///workspace/ocos/self/self_types.py#L366)；grep tests 无命中 |
| `self_evidence.py` | G3 范畴 | — |
| `schema.py` / 迁移 | S2 为 JSON blob 持久化，无列结构 | [self_state.py:284-300](file:///workspace/ocos/self/self_state.py#L284) |

## 3. 实施顺序（实现授权后执行）

```text
Step 1  self_types.py：StanceType / ContinuityKind / WorldViewJudgment / SelfModel 字段+白名单+has_worldview
Step 2  worldview.py（新建容器）
Step 3  self_state.py：_TYPE_REGISTRY 注册 4 类型（与 Step1/2 同批，防中间态断裂）
Step 4  self_model.py：imports / create / init / update_worldview
Step 5  __init__.py 导出
Step 6  新增测试（§5 矩阵）+ 全量回归
Step 7  提交验证证据（R-level 升级）
```

> Step 1–3 必须同批落地：注册表与类型定义分离的中间态会导致 `_rebuild` 抛
> `SelfStateIntegrityError("unknown type tag")`（[self_state.py:170-172](file:///workspace/ocos/self/self_state.py#L170)）。

## 4. 实施安全性审计（Safety Audit）

### 4.1 行为零影响论证

- **Prompt 行为**：`render()/brief()` 逐字不变 ⇒ 生产 prompt 注入内容零变化（T6 逐字节验证）。
- **决策行为**：决策上下文 self 槽为占位串（非 render/self_summary），不受影响。
- **持久化行为**：无 schema/迁移变更；`_to_canonical` 泛化序列化（dataclass 声明序），新增类型零改动（[self_state.py:112-151](file:///workspace/ocos/self/self_state.py#L112)）。
- **治理行为**：`SelfBoundaryRules` 治理门零改动；仅 `valid_components` 增加一项（[self_types.py:337-340](file:///workspace/ocos/self/self_types.py#L337)），且只放行、不放宽 source。
- **既有数据**：旧 `state_json` 无 `worldview` 键 → `_rebuild` 经 `value.get(f.name, _default_for(f))` 回退默认值 `None`（[self_state.py:175](file:///workspace/ocos/self/self_state.py#L175)）——**代码层已确认**，仍须测试验证（T2）。

### 4.2 风险清单与缓解

| # | 风险 | 影响 | 缓解 |
| --- | --- | --- | --- |
| R1 | `_TYPE_REGISTRY` 注册不全 | 含 worldview 的 committed 态无法 `_rebuild`，S2 管线断裂 | Step1–3 同批；T1/T3 |
| R2 | 旧状态无 worldview 键 | 反序列化失败 | 代码层已确认回退 None（§4.1）；T2 |
| R3 | `components_loaded` 计数变化 | 无消费者、无测试断言 | 已核实；是否把 worldview 计入该属性 → §6 决策点 |
| R4 | 导入环 | 新模块崩溃 | worldview.py 只 import self_types（与 knowledge_boundary.py 同构），无环；全量 import 冒烟 |
| R5 | 新枚举 round-trip | 反序列化失真 | 既有枚举机制已工作（KnowledgeConfidence 等注册往返）；T1 覆盖 |
| R6 | `initialize_empty_components` 生产调用方 | 初始组件数 5→6 行为变化 | grep 无生产调用方（仅导出）；实施时复核；T8 |
| R7 | 测试环境 flakiness | 误判回归 | 新测试全部用临时 DB（`:memory:` 除外按 db_path 隔离，accessor 注册表按 db_path 键控，[self_state.py:567-576](file:///workspace/ocos/self/self_state.py#L567)） |
| R8 | Provider 环境缺失干扰 | 无 | G1 测试纯确定性，无 LLM 依赖（MockProvider 不影响） |

### 4.3 设计结论 ≠ 已验证事实（严格执行）

以下三项在 G1 Design 中为**结构性设计推论**，只有实现后测试通过才升级为 **R-level production evidence**（用户裁决要求，本文件列为硬验证项，见 §5 T1/T2/T7）：

```text
① serialize → deserialize 的 worldview canonical round-trip      （T1）
② 旧 S2 无 worldview 字段恢复 None                                （T2）
③ component_consumption("worldview") 形成正确 manifest            （T7）
④ project() 自动出现 worldview                                    （T6a）
```

## 5. 验证方案（实现授权后的测试矩阵）

| # | 用例 | 断言 | 覆盖 |
| --- | --- | --- | --- |
| T1 | worldview canonical round-trip | 含 judgment 的 committed 态 serialize→deserialize 全字段一致、content_hash 一致 | R1/R5 |
| T2 | 旧状态向后兼容 | 无 worldview 键的 state_json → deserialize 得 `worldview is None`、hash 校验通过 | R2 |
| T3 | 注册表完整性 | 含 4 新类型的 canonical `_rebuild` 成功 | R1 |
| T4 | 白名单 | `SelfModel.update(contract,"worldview",WorldView())` → True；假组件 → False；identity_ref → False | 治理 |
| T5 | 治理门 | EXTERNAL_AGENT source 更新 worldview → update False / commit_change 抛 SelfStateRejected | 治理 |
| T6a | project 投影 | `accessor.project()` 含 worldview 结构化段 | ④ |
| T6b | **render/brief 逐字节不变** | 改动前后 render()/brief() 输出完全相同 | Prompt 零影响 |
| T7 | consumption manifest | 写入含 claim 的 worldview contract 后 `component_consumption("worldview")` 返回正确 manifest | ③ |
| T8 | init 行为 | `create_self_model` → worldview None；`initialize_empty_components` → WorldView() 实例 | R6 |
| T9 | 全量回归 | 既有套件全绿（重点：`test_l4_self_model.py`、`tests/self/*`、`test_self_*`） | 零破坏 |

## 6. 待 Gate 裁决的决策点（1 个，非设计变更）

**D1：`components_loaded` 是否计入 worldview？**
- 事实：无生产消费者、无测试断言（已核实）。
- 推荐：**计入**（语义上确为第 6 组件；仅当初始化后才 +1，无行为影响）。
- 备选：不计入（更保守，维持现状 5 计数语义）。
- 由本 Gate 一并裁决；不默认扩大范围。

## 7. 回滚方案

- **零迁移、零格式变更**：旧状态不受影响；worldview 数据仅由新代码写入。
- 回滚 = 撤销 5 文件变更（删除 worldview.py、还原 4 文件增量），无数据迁移、无降级残留。
- 因无任何生产代码写入 worldview（G3 未授权），回滚后运行态与现状完全一致。

## 8. 已知环境项（不阻塞 G1）

- 生产 provider = MockProvider（无 key）——与 G1 无关（G1 无 LLM 依赖）。
- P0-4B B1–B5 冻结照旧生效；G1 不触碰生产接线。

## 9. Human Gate

- 本文件 = **G1 Implementation 裁决材料**。G1 Implementation 在通过前仍 **NOT AUTHORIZED**。
- 裁决选项：
  - **G1 IMPLEMENTATION GO** → 授权按 §1/§3 实施 + §5 验证，产出 R-level 证据；
  - **GO WITH D1 DECISION** → 连同 §6 D1 一并裁决后实施；
  - **NO-GO / AMENDED** → 返回修订，不实施。
- 冻结纪律不变：本阶段仍不写代码、不改 SelfModel / schema / prompt / Converse / DecisionBridge、不跑 P1-1D。
- G1 之后：G3 / G4 / P1-1D 仍 NOT STARTED，需各自另行 Gate。

---

*本文件为只读裁决材料，未改代码。等待 Human Gate。*
