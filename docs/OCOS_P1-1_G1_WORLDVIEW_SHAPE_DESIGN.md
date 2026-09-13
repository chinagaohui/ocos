# OCOS P1-1 G1 — Worldview Physical Seat / Shape Design

> 状态：**G1 SHAPE DESIGN（设计授权，非实现授权）。Implementation = 继续 NOT AUTHORIZED。**
> 承接：`docs/OCOS_P1-1_WORLDVIEW_SEMANTIC_CONTRACT.md`（CONTRACT ACCEPTED, FROZEN）。
> 本文件回答：**SelfModel 第六组件"怎么落"**——类型、序列化复用、accessor 投影、source 复用、
> evidence 管线承载、commit 治理。**不实现**：不修改任何生产文件。

---

## 0. 授权边界

| 项 | 状态 |
| --- | --- |
| G1 Shape Design（本文件） | ✅ AUTHORIZED |
| G1 Implementation | ❌ NOT AUTHORIZED（须 G1 Design → Human Gate → 另行授权） |
| 改 SelfModel / schema / prompt / Converse / DecisionBridge / 生产控制流 | ❌ 禁止 |
| 跑 P1-1D | ❌ 禁止 |

## 1. Scope（G1 只做"座位"）

G1 只做一件事：**让 SelfState 具备可写、可持久化、可投影的 worldview 物理座位**。

```text
G1 交付（设计层）：
  SelfModel.worldview 字段 + valid_components 白名单
  WorldView 组件类型 + WorldViewJudgment 叶子类型 + StanceType/ContinuityKind
  canonical 序列化注册（_TYPE_REGISTRY）
  create/init 助手 + update_worldview 助手
  accessor project() 自动可投影（render/brief 文本注入 → 归 G4，G1 不碰）

G1 不交付（后续阶段）：
  G3：evidence 管线（recognize/ClaimKind/delta_from_claim/apply_delta 的 worldview 分支）
  G4：Thinking 消费接线（render/brief 文本投影 + component_consumption 实际读取点）
  P1-1D：Worldview X→D→Y 实验
```

## 2. 设计原则（复用既有组件模式）

逐条对照既有五组件落点（本设计严格照此模式）：

| 组件模式 | 既有实例 | 落点 |
| --- | --- | --- |
| 叶子类型（frozen dataclass） | `DomainStatement` [self_types.py:159-167](file:///workspace/ocos/self/self_types.py#L159) | `self_types.py` |
| 容器类型（dataclass + `summary()`） | `KnowledgeBoundary` [knowledge_boundary.py:23](file:///workspace/ocos/self/knowledge_boundary.py#L23) | 独立模块 `self/worldview.py` |
| SelfModel Optional 字段 | [self_types.py:297-301](file:///workspace/ocos/self/self_types.py#L297) | `self_types.py` |
| 更新白名单 | `valid_components` [self_types.py:337-340](file:///workspace/ocos/self/self_types.py#L337) | `self_types.py` |
| 序列化注册表 | `_TYPE_REGISTRY` [self_state.py:88-109](file:///workspace/ocos/self/self_state.py#L88) | `self_state.py` |
| 更新助手 | `update_knowledge_boundary` [self_model.py:101-116](file:///workspace/ocos/self/self_model.py#L101) | `self_model.py` |
| 初始化助手 | `initialize_empty_components` [self_model.py:64-77](file:///workspace/ocos/self/self_model.py#L64) | `self_model.py` |

**G1 零行为影响保证**：不触碰 `render()/brief()`（[self_state.py:514-559](file:///workspace/ocos/self/self_state.py#L514)）与任何消费路径 ⇒ 生产 prompt/决策语义零变化。

---

## 3. 组件类型设计（语义层规范）

### 3.1 `StanceType`（枚举，`self_types.py`，对齐契约 §4）

```text
StanceType:
  INTERPRETIVE = "interpretive"   # 我如何理解这类事情
  NORMATIVE    = "normative"      # 我认为应如何/如何取舍
  EPISTEMIC    = "epistemic"      # 我知道自己的理解边界
```

### 3.2 `ContinuityKind`（枚举，`self_types.py`，对齐契约 §5 continuity）

```text
ContinuityKind:
  FIRST     = "first"      # 首次形成（W0 不存在）
  DERIVED   = "derived"    # 由既有判断衍生
  REVISED   = "revised"    # 修订既有判断（W1≠W0）
  REPLACED  = "replaced"   # 替换既有判断（范式级重构）
```

### 3.3 `WorldViewJudgment`（frozen dataclass，`self_types.py`，对齐契约 §4 Claim Schema）

```text
@dataclass(frozen=True)
WorldViewJudgment:
  domain: str                        # 领域（dict key，同 KnowledgeBoundary.domains 语义）
  judgment: str                      # 判断语句（立场/理解方式，非事实）
  stance_type: StanceType            # 立场类型
  frame: str                         # 框架描述（如何理解"这类事情"）
  confidence: float = 0.5            # [0,1]
  evidence_ids: tuple[str, ...] = () # 归因证据（累计：新建/修订时追加）
  source: str = ""                   # 来源标签（"reflection"/"runtime_observation"）
  claim_id: str = ""                 # 最近一次写入的 SelfClaim 身份（commit 级溯源）
  created_tick: int = 0              # 首次形成 tick
  last_updated_tick: int = 0         # 最近修订 tick
  continuity: ContinuityKind = ContinuityKind.FIRST
  note: str = ""                     # 变更理由（W0→W1 的 reason）
```

**设计决策**：
- `evidence_ids` 放叶子（累计 genesis evidence），commit 级 provenance 由 `SelfUpdateContract.evidence_ids/claim_id` 承担（契约 §9）——两层并存、职责分离。
- `RecognitionType`（contract §5）**不在 G1**：它属于 Recognition→Delta 阶段（G3），G1 不引入未消费类型。

### 3.4 `WorldView`（容器，新模块 `ocos/self/worldview.py`，镜像 `KnowledgeBoundary`）

```text
@dataclass
WorldView:
  judgments: dict[str, WorldViewJudgment] = field(default_factory=dict)
      # key = domain；每域当前一份立场（最小语义，多立场/域 → G3+，不在 G1）

  @property count: int                       # len(judgments)
  @property overall_confidence: float        # 均值；空 → 0.5
  get(domain) -> Optional[WorldViewJudgment]
  declare(judgment) -> None                 # 按 domain 插/换（保持容器哑）
  summary() -> str                           # "WorldView: N domain stances, confidence=.."
```

容器操作保持哑（`declare/get`），Revision 语义由调用方构造新 judgment 并带 `continuity` —— 与
`KnowledgeBoundary.declare/downgrade` 风格一致，不引入新 authority。

---

## 4. SelfModel 集成（`self_types.py`）

```text
1. 字段：在 cognitive_state 之后新增
     worldview: Optional[Any] = None          # WorldView（第 6 组件，默认 None 向后兼容）
2. 白名单：valid_components 追加 "worldview"   # 必须，否则 SelfModel.update() 路径拒绝
3. 文档串：五组件 → 六组件（docstring 注释级）
4. 属性：has_worldview（镜像 has_capability_awareness）
```

**为什么必须加白名单**：`SelfModel.update()` 是 S1-free 助手路径的守门（[self_types.py:337-342](file:///workspace/ocos/self/self_types.py#L337)）；不加则 `update_worldview` 永远返回 False。
（证据管线路径 `build_candidate→apply_delta→commit_change` 不走 `SelfModel.update`，见 §9 说明。）

---

## 5. create / init 助手（`self_model.py`）

```text
create_self_model:                # 第 6 组件初始化为 None
    worldview=None,
initialize_empty_components:      # 追加
    if self_model.worldview is None:
        self_model.worldview = WorldView()
```

---

## 6. 序列化 / 注册表（`self_state.py`）—— G1 的硬性接线点

- **`_TYPE_REGISTRY` 追加**：`WorldView`、`WorldViewJudgment`、`StanceType`、`ContinuityKind`。
- **为什么必须**：`build_candidate()` = `_to_canonical(current) → _rebuild`（[self_state.py:390-393](file:///workspace/ocos/self/self_state.py#L390)）；`_rebuild` 按 `__type` 标签查注册表重建。**不注册 ⇒ 任何含 worldview 的 committed 态无法重建 ⇒ 管线整体断裂。**这是 G1 的生死线。
- **不需要改 `_to_canonical`**：它按 dataclass 声明顺序泛化序列化，新增类型自动兼容（`dict[str, WorldViewJudgment]` 键为 str，无歧义）。
- **向后兼容**：S2 持久化为单行 JSON blob（`state_json` + `content_hash`，[self_state.py:284-300](file:///workspace/ocos/self/self_state.py#L284)），**无 DB schema 变更**；旧状态无 `worldview` 键 → dataclass 默认 `None` 恢复。`deserialize_state` 的 `_rebuild` 对缺失键用默认值（设计须以测试验证，见 §13）。

---

## 7. 更新助手（`self_model.py`）

```text
update_worldview(self_model, worldview: WorldView,
                 source, reason, tick_id) -> bool
    contract = SelfUpdateContract(
        source=source, reason=reason, tick_id=tick_id,
        fields_changed=("worldview",),
        confidence_impact=0.05,               # 默认保守；调用方可改 contract 后走 update
    )
    return self_model.update(contract, "worldview", worldview)
```

**contract 形状**：`fields_changed=("worldview",)` 满足 `SelfUpdateContract.is_valid`
（[self_types.py:100-106](file:///workspace/ocos/self/self_types.py#L100)）；`confidence_impact` 默认 0.05，
受 `SelfBoundaryRules` 治理门约束（[-1,1] + self_confidence 边界 [0.1,1.0]，[self_types.py:253-263](file:///workspace/ocos/self/self_types.py#L253)）。**治理门无需改动。**

---

## 8. SelfUpdateSource 复用决策（不新增 authority）

**G1 不新增枚举成员**。`allowed_update_sources` 已含 5 源（[self_types.py:245-251](file:///workspace/ocos/self/self_types.py#L245)），
worldview 写入按契约 §12 映射复用：

| 形成路径 | 复用 source | 理由 |
| --- | --- | --- |
| 真实经历观测 → 世界理解变化 | `RUNTIME_OBSERVATION` | 与 failure/capability 同源语义 |
| 事后反思重构理解框架 | `REFLECTION` | 自归洞察路径 |
| 记忆整合出模式性理解 | `MEMORY_CONSOLIDATION` | 跨经历归纳 |

**红线**：若后续要新增专属 source（如 `WORLDVIEW_*`），属 decision-semantics 变更 → 单独立项，
G1 不越界。

---

## 9. Evidence 管线承载（G3 设计注记，不在 G1 实现）

G1 只保证"座位在"；G3 才把线接上。已核实管线结构（[self_evidence.py:343-373](file:///workspace/ocos/self/self_evidence.py#L343)）：

- `recognize()`：现 ClaimKind 仅 3 类（[self_evidence.py:95-100](file:///workspace/ocos/self/self_evidence.py#L95)），**G3 需扩展** worldview 识别规则（可复用 RECOGNITION 语义，新增 ClaimKind 成员或独立识别例程）。
- `delta_from_claim()`：现按 kind 分支构造 old/new（[self_evidence.py:257-299](file:///workspace/ocos/self/self_evidence.py#L257)），**G3 需加 worldview 分支**（old=`current.worldview.get(domain)`，new=`WorldViewJudgment(...)`）。
- `apply_delta()`：现按 kind 分支 setattr（[self_evidence.py:302-321](file:///workspace/ocos/self/self_evidence.py#L302)），**G3 需加 `candidate.worldview.declare(...)` 分支**。
- **管线路径不经过 `SelfModel.update()`**（走 `build_candidate + commit_change`），故 G3 的 apply 不受白名单阻隔；白名单是 S1-free 助手路径（§7）的守门。

---

## 10. Accessor 投影设计（G1 最小投影，消费接线归 G4）

| 投影 | G1 处理 | 理由 |
| --- | --- | --- |
| `project()`（canonical dict，[self_state.py:460-462](file:///workspace/ocos/self/self_state.py#L460)） | **自动包含**（字段加入 SelfModel 即出现，零代码） | canonical 全量投影，非 prompt 源 |
| `render()`（文本投影） | **不碰** | render 输出进入生产 prompt（converse L4-2 槽）⇒ 改 render = 改 prompt = G4 接线范畴 |
| `brief()`（决策自注入） | **不碰** | 同上，消费接线范畴 |
| `component_consumption("worldview")`（[self_state.py:485-512](file:///workspace/ocos/self/self_state.py#L485)） | **自动兼容**（按 `fields_changed` 扫描 update_history，零代码） | 契约成立后自动可归因 |

**G1 严格边界**：worldview 出现在 `project()`（机器可投影）即止；**不得**进入 render/brief/任何 prompt。

---

## 11. Commit 与治理（零改动）

- `SelfStateManager.commit_change`（[self_state.py:395-426](file:///workspace/ocos/self/self_state.py#L395)）：治理门只校验 contract（source/reason/fields_changed/confidence_impact），**无组件白名单** ⇒ worldview 自动可提交。
- `update_history` 入账 provenance（claim_id/evidence_ids）⇒ `committed_claims()`/`component_consumption()` 自动覆盖 worldview。

---

## 12. 文件级变更映射（设计规格，非实现）

| 文件 | 变更（实现时） |
| --- | --- |
| `ocos/self/self_types.py` | +`StanceType`、`ContinuityKind`、`WorldViewJudgment`；+`SelfModel.worldview` 字段、`valid_components` 加 "worldview"、`has_worldview` |
| `ocos/self/worldview.py`（新） | +`WorldView` 容器（declare/get/summary） |
| `ocos/self/self_state.py` | +`_TYPE_REGISTRY` 注册 4 类型（§6，生死线） |
| `ocos/self/self_model.py` | +`create_self_model` worldview=None、`initialize_empty_components` 补 init、+`update_worldview` |
| `ocos/storage/schema.py` | **无变更**（JSON blob 持久化） |
| `converse/bridge/recall_router/agent_runtime/decision_*` | **无变更**（G1 不接线） |

---

## 13. 验证设计（G1 实现授权后执行，非现在）

1. **零行为影响**：既有测试全绿（render/brief/prompt 未变）。
2. **canonical 往返**：含 worldview 的 committed 态 `serialize→deserialize` 重建一致、hash 一致。
3. **向后兼容**：无 worldview 键的旧 state_json 可加载（`worldview=None`）。
4. **白名单**：`SelfModel.update(contract,"worldview",v)` 返回 True；`"worldview"` 之外的假组件仍拒绝。
5. **治理门**：`EXTERNAL_AGENT` source 更新 worldview 被拒。
6. **project 可投影**：`accessor.project()` 含 worldview 结构化值；render/brief 输出与改动前逐字相同。
7. **consumption 兼容**：写入含 claim 的 worldview contract 后，`component_consumption("worldview")` 返回 manifest。

## 14. Non-Goals / 递延

- G2（语义）已由 Semantic Contract FROZEN；G1 不重开。
- G3（evidence 管线 worldview 分支）：不在 G1。
- G4（render/brief 文本投影 + 实际读取点接线）：受 P0-4B B1–B5 冻结，不在 G1。
- P1-1D（X→D→Y 实验）：NOT STARTED。

## 15. Human Gate

- 本文件 = **G1 Shape Design 产出**。G1 实现仍 **NOT AUTHORIZED**。
- Gate 裁决选项：
  - **G1 DESIGN ACCEPTED** → 进入"实现授权"单独裁决（实现方案仍须另行 GO）；
  - **G1 DESIGN AMENDED** → 返回修订设计；
  - **G1 DESIGN REJECTED** → P1-1 停止，语义保持 NOT-IMPLEMENTED。
- 冻结纪律不变：在实现授权前，不修改 SelfModel / schema / prompt / Converse / DecisionBridge / 生产控制流。

---

*本文件为设计规格，非代码。等待 Human Gate 裁决。*
