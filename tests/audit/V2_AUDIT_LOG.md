# V2 Audit Log：Architecture Boundary Audit

**版本：** 0.1
**起始日期：** 2026-07-17
**状态：** 🟢 IN PROGRESS（0/5 Findings）

---

## 使命

V1 已证明 Theory 正确，问题出在 Architecture。

V2 不再回答"Theory 是否成立"，而是回答：

> **每一层的边界是否清晰？箭头是否可信？**

### V2 验收标准

V1 的验收标准是：找到 Gap。

**V2 的验收标准是：找到唯一可信的数据流。**

最终产出应该是类似的图：

```
Theory
  │
  ▼
Gravity
  │
  ▼
Director
  │
  ▼
Decision Frame
  │
  ▼
Character Benchmark
  │
  ▼
Blueprint
  │
  ▼
Writer
```

并且每一条箭头都回答一个问题：**这一层到底向下一层交付了什么？**

如果某条箭头回答不清，那就是 V2 的 Finding。

### V2 第一原则

> **Every layer creates pressure for the next layer.**
> 任何一层都不应替下一层做决定。

---

## Finding 结构

每条 Finding 遵循 V1 确立的格式：

### V2-XXX

```yaml
Finding ID:          V2-XXX
Status:              ⏳ | ❌ | ✅
Primary Boundary:    [层A] → [层B]
Current:             当前边界存在什么越界/模糊
Expected:            SR2 预期的边界划分
Evidence:            实际审计证据
Impact:              越界/模糊对整条链路的影响
Repair Principle:    修复方向
Repair Target:       具体需要修改的资产/代码
Repair Cost:         S | M | L | XL
Regression Risk:     Low | Medium | High
```

---

## V2 Progress（当前状态面板）

| 指标 | 值 |
|:-----|:---|
| Progress | 5/5 Findings（✅ V2 COMPLETE）|
| L1（Implementation）| 0 |
| L2（Architecture） | 5 |
| L3（Theory）       | 0 |
| Current Bottleneck | SR2 信号抵达 Prompt 率为 0%（Data Flow Failure） |
| Primary Hotspot | 整条 Pipeline — 单一根因（Story Blueprint 范式） |
| Confidence | ✅ High（5/5，单一根因收敛，Theory Healthy） |

---

## Pipeline Boundary Map

```
Theory
  │  V2-001 [FOUND] Director 输出混合 Pressure + Character 决策
  ▼
Director
  │  V2-002 [FOUND] Blueprint 是"执行剧本"而非"压力记录"
  ▼
Blueprint
  │  V2-003 [FOUND] SR2 CB 从未构建；CharBrain 是 SR1 遗留
  ▼
Character Benchmark
  │  V2-004 [FOUND] Decision Leakage Cascade（97% 无损穿透）
  ▼
Writer
  │  V2-005 [FOUND] SR2 信号抵达 Prompt 率 = 0%
  ▼
正文
```

## V2 Final Summary

### 五关审计结果

| ID | 审计问题 | 结果 | 性质 |
|:---|:---------|:----|:-----|
| V2-001 | Director 是否只生成 Pressure？ | ❌ 输出混合 | L2 越界 |
| V2-002 | Blueprint 是否记录 Pressure？ | ❌ 执行剧本（≈97% DL）| L2 越界 |
| V2-003 | CB 能否独立推导 Decision Space？ | ❌ Framework 已设计但零实现 | L2 缺失 |
| V2-004 | 整条链路是否逐层越权？ | ❌ Decision Leakage Cascade | L2 全链路 |
| V2-005 | 数据流是否完整？ | ❌ SR2 信号抵达 Prompt 率 = 0% | L2 数据流 |

### 单一根因

V2-001 至 V2-005 不是五个独立问题。它们是 **同一个根因** 在 Pipeline 五个节点的持续表现：

> **整条 Pipeline 遵循 Story Blueprint 范式，未迁移到 Pressure Blueprint 范式。**

这是 V1（SCR 层面 Story Blueprint）根因向下的自然延伸。V1 证明 SCR 层是 Story Blueprint；V2 证明整条 Pipeline（SCR → Blueprint Parser → Director → CB[缺失] → Writer → Prompt）全部是 Story Blueprint。

### Decision Leakage Cascade（决策泄漏瀑布）

```
Blueprint（≈97% 行为指令）
    ↓  ≈95% 保留
ChapterSpec（summary = 行为文本）
    ↓  ≈70% 保留
Director（directives 含行为指令）
    ↓  ≈95% 保留
Writer Prompt（场景目的=BP行为，冲突=空）
    ↓  ≈100% 保留
正文（还原 Blueprint 行为）
```

### Decision Ownership（当前 vs SR2 目标）

| 层 | 当前 | SR2 目标 |
|:---|:----|:---------|
| SCR / Gravity | ≈60%（定义剧情方向+角色行为）| 0%（只定义方向）|
| Director | ≈25%（character_targets）| 0%（只输出 Pressure + DF）|
| Blueprint | ≈10%（场景级行为指令）| 0%（只记录压力+决策结果）|
| CharBrain / CB | ≈5%（情绪跟踪，非决策）| ≈100%（唯一决策者）|
| Writer | 0%（执行扩写）| 0%（只写正文，不决策）|

### V2 回答的问题

> V2 的根本问题：每一层的边界是否清晰？数据流是否可信？

V2 的回答：边界清晰但内容错误。每层的接口设计（大多）是干净的，但流经接口的内容是 Story Blueprint 的行为指令，不是 Pressure Blueprint 的压力/约束/决策。数据流因此不可信——它传递的是噪音（行为），而非信号（压力）。

### Theory Health Gake

| 指标 | 值 |
|:-----|:---|
| L1（Implementation）| 0 |
| L2（Architecture） | 5 |
| L3（Theory） | 0 |
| Theory Health | ✅ PASS |
| Architecture Health | ❌ FAIL |
| Root Cause | Story Blueprint → Pressure Blueprint 范式差异 |

### 下一步

- V3 Inference Validation（等待 V2 PASS 后启动）
- 最终资产冻结：DECISION_OWNERSHIP_MAP.md（架构契约）
- 修复从上游（Blueprint 格式）开始，非下游（Writer/Prompt）

---

## Finding 记录

### V2-001

```
Finding ID:               V2-001（Director Boundary）
Status:                   ❌ Non-Compliant
Primary Boundary:         Director → Character
Secondary Impact:         Writer（接收已决策的行为指令而非压力）
Evidence Strength:        E2（MasterDirector 和 DirectorService 均存在相同的越界模式）

Four Questions：

Q1 - Director 的输入是什么？
  当前：
  · NovelRuntimeContext（outline / world / characters / chapter_specs / genre）
  · 上一章上下文（character_delta / quality_report / reader_feedback）
  · 系统配置
  缺失：
  · Narrative Gravity！Director 不接收 Gravity 作为显式输入。
    这意味着 Director 无法判断其产出是否服务于 Gravity。
    → 这是一个独立的隔离泄漏（Input Isolation Gap）

Q2 - Director 的输出是什么？

  两套输出路径：

  路径 A：MasterDirector（directors/master_director.py）→ PreChapterPlan → prompt block
    - emotion_arc_beat        ✅ 压力信息（情感弧）
    - character_targets       ❌ 角色发展指令（"林烬:推进弧"）
    - commercial_targets      ✅ 商业约束（留存率等）
    - directives:             ❌ 混合了压力和行为指令
        · "推进危机发展"          → ❌ 行为指令
        · "保持张力不泄"          → ✅ 约束/压力
        · "林烬:推进弧"           → ❌ 角色发展指令
    - writing_strategy        ⚠️ 部分属于 Writer，部分属于约束
    - reader_focus            ✅ 读者约束

  路径 B：DirectorService（director/service.py）→ WriterPackage
    - scene_plans              ❌ 场景方案（预定义了场景内容）
    - mission（ChapterMission） ⚠️ 混合
    - constraints（ConstraintMatrix） ✅ 约束
    - memory_block / canon_block ✅ 上下文

Q3 - 哪些信息应该留给 Character？
  以下信息被 Director 提前决策，应留给 Character Benchmark：
  · character_targets              — "角色该发展什么"
  · directives 中的字符行为指令     — "角色该做什么"
  · scene_plans                    — "场景里发生什么"

  Character Benchmark 需要的输入是：
  · Pressure（角色面对什么压力）
  · Constraints（不能做什么）
  · Stakes（失败意味着什么）
  · Resources（有什么可用）
  → 然后 CB 独立推导：角色选择什么行动。
  → Director 不应提前告诉 Writer "角色该做什么"。

Q4 - 哪些信息被 Director 提前决定了？

  证据汇总：
  ┌──────────────────────┬──────────────────┬──────────────────┐
  │ 输出字段             │ 当前归属层        │ SR2 应归属层     │
  ├──────────────────────┼──────────────────┼──────────────────┤
  │ character_targets   │ Director          │ Character BM     │
  │ scene_plans         │ Director          │ Writer + CB      │
  │ directives(行为)    │ Director          │ Pressure→CB      │
  │ directives(约束)    │ Director          │ Director（保留）  │
  │ emotion_arc_beat    │ Director          │ Director（保留）  │
  │ writing_strategy    │ Director          │ Writer           │
  │ commercial_targets  │ Director          │ Director（保留）  │
  │ Gravity              │ 不存在            │ Director Input   │
  └──────────────────────┴──────────────────┴──────────────────┘

  Director 越界决策的内容权重（按输出行数/字段数估算）：
  · 角色行为相关：~30%（character_targets + 行为 directives）
  · 场景内容相关：~40%（scene_plans）
  · 应当保留为压力/约束：~25%（emotion + 约束 directives + commercial）
  · 缺失的输入：5%（Gravity）

  这不是 Director "写错了"，而是 Director 的接口契约没有定义
  哪些属于 Director，哪些属于 Character。
  Director 的产出一锅端地给了 Writer，
  NarrativePressure → CharacterChoice 的中间推导环节缺失。

Current:
  Director 的输出是一份"行动蓝图"，混合了压力、角色行为指令、
  场景设计、写作策略。Writer 被动执行已决策的内容，
  Character Benchmark 没有介入的接口。

Expected:
  Director 输出应严格限于：
  · Constraints     ——不能做什么的规则
  · Stakes          ——失败代价
  · Resources       ——可用资源
  · NarrativePressure——角色必须面对的压力（而非应对方式）
  · EmotionArc      ——情感节奏（作为压力的一部分）

  以下应移除出 Director 输出：
  · character_targets           → 由 Character Benchmark 推导
  · 行为 directives             → 替换为压力描述
  · scene_plans 的预定义内容    → 减少至场景层级约束（地点、时间）
  · writing_strategy            → 移交 Writer 自主判断

  新增 Director 输入：
  · Narrative Gravity           → Director 需要知道 Gravity 来判断压力方向

Impact:
  · Character Benchmark 无法介入：Director 的 character_targets + scene_plans
    已经替角色做了选择，CB 没有机会推导决策。
  · Writer 被降级为"指令执行器"：接收到的是行为指令而非压力，
    不需要理解角色，只需要按剧本写。
  · 因果链断裂：压力 → 决策 → 行动的链条在 Director 层就被截断了。
    Writer 接到的是"林烬做了什么"，不是"林烬面临什么压力，他怎么选"。
  · Reader Memory 无法建立：既然角色行为是 Director 指定的而非
    角色自主的选择，读者无法建立"角色是谁"的认知。

Repair Principle:
  Director 只输出压力，不输出解决方案。
  "Every layer creates pressure for the next layer"
  在 Director → Character 边界上具体化为：
  Director 输出 Pressure，Character Benchmark 输出 Decision。

Repair Target:           Director → Character 接口契约
                         需要：移除 character_targets、清理 directives、
                         移除 scene_plans 中的预定义内容、
                         新增 Gravity 输入、新增 NarrativePressure 输出
Repair Cost:             M（重新划定接口边界，涉及 MasterDirector、
                         DirectorService、WriterPackage 三层改动）
Regression Risk:         Medium（接口变化影响下游 Writer 和 Character
                         Benchmark 的输入格式）

补充说明：
  Director 的越界模式与 V1-004/SR1 SCR 的越界模式高度相似：
  都是"Story Blueprint"范式的延续——Director 在输出"故事该怎样"
  而非"压力源是什么"。这是 V1 根因（Story → Pressure 范式）
  在 Director 层的再次验证。
```

### V2-002

```
Finding ID:               V2-002（Blueprint Boundary）
Status:                   ❌ Non-Compliant
Primary Boundary:         Blueprint → Writer
Primary Boundary (alt):   Blueprint → Character Benchmark
Evidence Strength:        E2（全五卷 Blueprint 一致——决策泄漏 95%+）

V2 四问审计法：

Q1 - Blueprint 保存了什么？

  Volume Blueprint 保存的是"执行剧本"——详细到每章每场景的
  角色行为、对话、事件序列。

  字段构成：
  · 章节编号 / 字数 / 时间 / 场景     ✅ 元信息
  · 剧情推进（Chapter Goal）            ❌ 详细剧情描述
  · 人物成长                            ❌ 角色发展（CB 职责）
  · 伏笔                                ✅ 叙事标记
  · Cliffhanger                         ⚠️ 情节悬念，非认知问题
  · 多轮多章分阶段详细描述              ❌ 行为+对话+场景

  典型章节内容样例如下：
  > 林烬看了一眼设备："一小时。"
  > 格雷冷嘲："一个奴隶，你知道这是什么设备吗？"
  > 林烬没理他，拆开外壳，更换一条损坏的能量传导线路…
  > 四十七分钟，设备恢复正常。

  Blueprint 的字段中缺少：
  · Gravity 引用                   → ❌ 不存在
  · 角色面对的压力                  → ❌ 不存在
  · Constraints（角色不能做什么）   → ❌ 不存在
  · Stakes（如果失败意味着什么）     → ❌ 不存在
  · Resources（角色有什么可用）     → ❌ 不存在
  · Reader Hook（认知问题）         → ⚠️ 仅情节悬念
  · Decision Space                  → ❌ 角色决策空间未定义

Q2 - 哪些信息应该来自 Director？

  Blueprint 中属于 Director 职责的：
  · Pressure（压力定义：角色必须面对什么）
  · Constraints（规则：什么不能做）
  · Stakes（代价：失败意味着什么）
  · Resources（可用资源：有什么可以失去）
  · Emotion Arc（情感节奏）

  以上均不存在。Blueprint 没有等待 Director
  提供 Pressure 再传导给 Character Benchmark。
  Blueprint 直接替所有下游做了决定。

Q3 - 哪些信息应该来自 Character Benchmark？

  Blueprint 中应属于 CB 推导结果的：
  · 角色名字出现在章节描述中           → ❌ CB 应推导决策，非角色名对应章节
  · "林烬决定……"                     → ❌ CB 应推导，Blueprint 只记录结果
  · "阿七潜入……"                     → ❌ 同上
  · "林烬面临选择：A 还是 B？"         → ⚠️ 这是 CB 的输入（Decision Space），
                                          但 Blueprint 记录了角色的选择
  · 角色行为序列（做什么→说什么→去哪）→ ❌ 全部应属于 CB 推导

  当前 Blueprint 中涉及角色行为的占比：
  全五卷统计（Volume 1-5）：
  · 角色名（林烬）出现合计：1075 次（平均每 7 行一次）
  · 压力/约束/代价关键词合计：34 次
  · 字符与压力比：24:1 ~ 66:1

  每个 Volume Blueprint 的 Decision Leakage：
  ┌──────────┬──────┬──────┬────────┬──────────────┐
  │ Volume   │ 角色名 │ 压力词 │ 行数   │ DL(%)        │
  ├──────────┼──────┼──────┼────────┼──────────────┤
  │ V1       │ 297  │ 12   │ 2081   │ 96.2%        │
  │ V2       │ 264  │ 4    │ 2224   │ 98.6%        │
  │ V3       │ 173  │ 9    │ 1887   │ 95.1%        │
  │ V4       │ 150  │ 6    │ 1787   │ 96.2%        │
  │ V5       │ 191  │ 3    │ 1772   │ 98.5%        │
  └──────────┴──────┴──────┴────────┴──────────────┘

  综合 Decision Leakage: ≈97%
  Blueprint 中 97% 的内容是故事执行方案，
  只有 ≈3% 提到压力或约束。

Q4 - Blueprint 是否还能作为中立的数据交接层？

  答案：否。

  当前的 Blueprint 不是"数据交接层"，而是"完整执行方案"：
  · 它不是 Director 的输出（它替 Director 决定了剧情）
  · 它不是 CB 的输入（它替 CB 决定了角色行为）
  · 它不是 Writer 的约束（它替 Writer 决定了写作内容）
  · 它不是 Reader Memory 的载体（没有认知遗留设计）

  当前 Blueprint 本质上是一份"作者亲手写的故事"。
  它承载了所有层的职责，因此它无法作为任何层的契约。
  
  一个真正的中立 Blueprint 应该：
  · 从 Director 接收：Pressure + Constraints + Stakes + Resources
  · 从 CB 接收：Decision Space + Character Choice + Cost
  · 向 Writer 提供：以上两者的组合（"角色面对什么压力，他选择怎么应对"）
  · 向 Reader Memory 提供：Hook（什么认知将被攻击）

Current:
  Blueprint = 作者手动写的详细故事大纲。
  每卷 1500-2200 行，其中 95%+ 的内容是"谁做了什么"。

Expected:
  Blueprint = Pressure + Decision Record。
  应包含：
  · Narrative Gravity 引用
  · Pressure（角色必须面对的困境）
  · Constraint（角色不能做的事）
  · Stakes（失败代价）
  · Resources（可失去的东西）
  · Decision Space（角色选项，非预选）
  · Decision Result（如果已由 CB 独立推导完成）
  · Reader Hook（认知问题，非情节悬念）

  以下应从 Blueprint 移除：
  · 角色行为描述（"林烬走进…"）→ 由 CB 决定，Writer 记录
  · 角色对话（"他说…"）→ 由 CB 决定，Writer 表达
  · 场景级叙事细节（"他拆开外壳…"）→ Writer 职责
  · 替角色写的决策（"他决定…"）→ CB 职责

Impact:
  · 整条链路无法建立：Blueprint 已经把所有下游职责全部占用了
  · Character Benchmark 没有接入点：所有角色行为已在 Blueprint 中写明
  · Writer 没有决策空间：Writer 的职责被 Blueprint 降低为"扩写"而非"表达"
  · V1 发现的 Story Blueprint 范式在 Blueprint 层达到最严重程度
    （SCR 层 4 项 Finding，Director 层 ≈70% 泄漏，Blueprint 层 97% 泄漏）

Repair Principle:
  Blueprint 应从中立的 Pressure → Decision 接收层，
  每卷结束后只记录不可逆的压力变化和决策结果。

Repair Target:            Volume Blueprint Template
                          需要：新增 Pressure 字段 / Constraints / Stakes /
                          Reader Memory Hook；移除角色行为字段
Repair Cost:              S（修改 Template 字段，不涉及代码）
Regression Risk:          Low（Template 变更不影响下游管线）

Decision Leakage 跨层汇总：
  ┌─────────────┬─────────────────────┐
  │ 层          │ Decision Leakage    │
  ├─────────────┼─────────────────────┤
  │ SCR (V1)    │ ≈100%（4/5 ➡ 范式） │
  │ Director    │ ≈70%（≈30%行为+40%场景）│
  │ Blueprint   │ ≈97%（1075:34 角色:压力）│
  │ Writer      │ 待 V2-004/005 验证  │
  └─────────────┴─────────────────────┘

  注意：
  V2-001 的 Director ≈70% 包含 30% 角色行为指令 + 40% 场景内容，
  但 MasterDirector 和 DirectorService 的分量不同。
  V2-002 的 Blueprint 97% 是纯 Story Blueprint——
  Blueprint 层的范式问题比 Director 层更严重。
  这不是意外：Volume Blueprint 是 SR1 的原始设计产物，
  未被 SR2 架构调整过，因此保留了最完整的 Story Blueprint 痕迹。
```

```
Theory
  │  V2-001: Director 是否只生成 Pressure，不替 Character 做决策？
  ▼
Director
  │  V2-002: Blueprint 是否记录"必须发生的压力"而非"应该发生的剧情"？
  ▼
Blueprint
  │  V2-003: Character Benchmark 是否能独立推导 Decision Space？
  ▼
Character Benchmark
  │  V2-004: 整条链路逐层检查是否越权？
  ▼
Writer
  │  V2-005: Theory → Architecture → Pipeline → Prompt → Generation，每一层是否信息损失？
  ▼
正文
```

---

## 审计索引

| ID | 审计问题 | 边界 |
|:---|:---------|:-----|
| V2-001 | Director 是否只生成 Pressure，没有替 Character 做决策？ | Director → Character |
| V2-002 | Blueprint 是否记录"必须发生的压力"，而非"应该发生的剧情"？ | Blueprint → Scene |
| V2-003 | Character Benchmark 是否能独立推导 Decision Space？ | CB → Director |
| V2-004 | 整条链路逐层检查：有没有替下一层做决定？ | Gravity → Writer |
| V2-005 | 数据流审计：每一层是否发生信息损失？ | Theory → Generation |

---

## V2 与 V1 的关系

| | V1 | V2 |
|:--|:---|:---|
| 问题 | Theory 是否成立？ | 边界是否清晰？ |
| 对象 | SCR（Story→Pressure 范式） | 全链路（Gravity→Writer） |
| 验收标准 | 找到 Gap | 找到唯一可信的数据流 |
| 风险 | Theory Failure | Architecture Leakage |
| 产出 | 5 项 L2 Finding | 每层边界图 + 可信度 |

---

## 变更记录

| 版本 | 日期 | 变更内容 |
|:-----|:-----|:---------|
| 0.1 | 2026-07-17 | 初始创建。定义 V2 使命、五项审计方向、验收标准、与 V1 的关系。 |
| 0.2 | 2026-07-17 | V2-001（Director Boundary）审计完成。 |
|     |        | V2-001 定值：L2（Architecture Gap）/ E2 / M / Medium。 |
|     |        | 四问审计法：Director 输入缺 Gravity、输出混合 Pressure+Character 决策。 |
|     |        | 关键发现：Director 输出 ≈30% 行为指令 + 40% 场景内容 + 25% 压力/约束。 |
|     |        | 修复方向：Director 只输出 Pressure，Character 决策交 CB。 |
|     |        | 新增 V2 四问审计法（输入/输出/应留给CB的/提前决定的）。 |
| 0.2 | 2026-07-17 | V2-002（Blueprint Boundary）审计完成。 |
|     |        | V2-002 定值：L2（Architecture Gap）/ E2 / S / Low。 |
|     |        | Decision Leakage 指标首次使用：全五卷 Blueprint ≈97%。 |
|     |        | 关键发现：角色:压力比 24:1~66:1，Blueprint 是"执行剧本"非"压力记录"。 |
|     |        | 跨层 Decision Leakage 汇总：SCR ≈100% → Director ≈70% → Blueprint ≈97%。 |
|     |        | 修复方向：新增 Pressure/Constraints/Stakes 字段，移除角色行为字段。 |
| 0.3 | 2026-07-17 | V2-003（Character Benchmark Boundary）审计完成。 |
|     |        | V2-003 定值：L2（Architecture Gap）/ E1 / M / Medium。 |
|     |        | V2 判定点：SR2 CB Framework 已设计但零实现。 |
|     |        | CharBrain 是 SR1 情绪跟踪器，非 SR2 CB。 |
|     |        | Decision Ownership 汇总构建完成（SCR 60% → Director 25% → BP 10% → CharBrain 5% → SR2 CB 0%）。 |
| 0.4 | 2026-07-17 | V2-004（Interface Boundary — 全链路 Cascade）审计完成。 |
|     |        | V2-004 定值：L2（Architecture Gap）/ E2 / L / High。 |
|     |        | 关键发现：Decision Leakage 是 Cascase 模式（逐层累积的单向泄漏瀑布）。 |
|     |        | Cascade Total：Blueprint ≈97% → Parser ≈95% → Director ≈70% → Writer ≈95% → LLM ≈100%。 |
|     |        | 核心证明：行为指令从 Blueprint 到正文几乎无损穿透。 |
|     |        | Writer 被降级为"扩写器"（场景冲突/转折/出口全部为空）。 |
| 0.5 | 2026-07-17 | V2-005（Data Flow Audit — Theory → Generation）审计完成。 |
|     |        | V2-005 定值：L2（Architecture Gap）/ E2 / L / High。 |
|     |        | 关键发现：SR2 信号抵达 Prompt 率为 0%。 |
|     |        | Prompt 中大量存在行为指令（≈95%），而非压力/决策信息。 |
|     |        | Narrative Gravity / Theme / Core Question / Decision Frame 均未到达。 |
|     |        | 修复必须从上游开始（Blueprint 格式），修 Writer/Prompt 无效。 |
|     |        | V2 最终结论：Theory Healthy（0 L3）| Architecture Failed（5 L2）。 |
|     |        | 单一根因收敛：整条链采用 Story Blueprint 范式，不是四/五个独立问题。 |
|     |        | 新增 V2 五问审计法（Input/Output/Independence/Uniqueness/Replacement Test）。 |
|     |        | 发现 V2-003 的性质与之前不同：不是"越界"，而是"缺失"。 |

### V2-003

```
Finding ID:               V2-003（Character Benchmark Boundary）
Status:                   ❌ Non-Compliant
Primary Boundary:         Character Benchmark → Director / Blueprint
Secondary Impact:         整个 Character First 架构的基石
Evidence Strength:        E1（架构设计存在但零实现，无法运行验证）
                          注：这不是实现不完整，而是 SR2 的 CB 从未构建。
                          现有的 CharBrain 是 SR1 遗留的情绪跟踪器，
                          与 SR2 CB Framework 不是同一件事。

V2 五问审计法：

Q1 - CB 实际收到哪些信息？

  CharBrain（正在运行）的输入：
  · character names / roles / summaries          ✅ 元信息
  · appearance_map（谁在本章出场）               ✅ 出场跟踪
  · 外部设置的情绪/目标/互动                     ❌ 被动接收，非主动推理
  ❌ NarrativePressure                            → 从不接收
  ❌ Constraints（不能做什么）                     → 从不接收
  ❌ Stakes（失败代价）                            → 从不接收
  ❌ Resources（有什么可失去）                     → 从不接收
  ❌ Decision Frame（Knowledge Boundary + 选项集）→ 从不接收
  ❌ Narrative Gravity                            → 从不接收
  ❌ Character Identity/Value/Belief（CB Framework 定义的核心）→ 从不接收

  CB Framework（设计文档）定义的输入：
  · Decision Frame（含 Knowledge Boundary、可选项集）
  · Identity Profile（Primary / Secondary / Dormant）
  · Value System + 演化轨迹
  · Belief System + Strength + Decay
  · Fear / Desire（显式化，含激活条件）

  实际运行的 CharBrain 与设计文档完全不匹配。
  CharBrain 接收的是角色出场信息，不是决策场景信息。

  结论：输入不足且数据类型错误。
  CB 当前收到的信息不足以推导任何 Decision Space。

Q2 - CB 输出的是 Decision Space，还是直接输出行为？

  CharBrain（正在运行）的输出：
  · desire_text —— 基于情绪+角色模板的"行为建议"
    例："angry" → "发泄愤怒"、"sad" → "独自疗伤"
    这不是 Decision Space，是硬编码的行为模板。
  · pulse —— 自然语言摘要（供 Writer 消费）
    例："林烬 | 情绪=determined | 渴望=推进核心目标 | 动力=高"
    这是信息性摘要，不是决策输出。

  CB Framework（设计文档）定义的输出：
  · Decision Space（结构化：candidates + probabilities + reasoning chain）
  · Semantic Decision（核心语义：用一句话描述"这次选择意味着什么"）
  · Cost（这次选择的代价）

  CB-001（Lin Jin）的 Decision Trace 样例：
  event: "陈卫请求侦察灰烬星"
  candidates: ["批准侦察", "拒绝侦察", "派遣无人侦察机"]
  chosen: "批准侦察"
  semantic: "允许局部风险换取整体建设收益"
  cost: "失去两艘船和核心船员三天的防守力"

  实际运行的 CharBrain 输出与 SR2 Decision Space 格式完全不同。
  CharBrain 的 desire 是"角色想做什么"，不是"角色面临什么抉择"。

Q3 - 去掉 Director 的行为指令后，CB 是否还能稳定推导？

  当前：不能。

  如果 Director 不再提供 character_targets（"林烬:推进弧"），
  CharBrain 会回到默认模板：
  · 情绪=determined → 渴望="推进核心目标"
  · 情绪=happy → 渴望"与人分享喜悦"
  这些都是"如果角色出现在场景中"的泛化行为建议，
  不是"当角色面对特定 Pressure 时的决策"。

  没有 Decision Frame 输入 → 没有决策可推导。
  CharBrain 的 tick() 其实只是"情绪管理"，不是"决策推理"。

  CB Framework 设计层面：理论成立。
  但实现层面：零代码支撑此能力。

Q4 - 是否只有 CB 能回答这个决策？（Uniqueness）

  当前：否。任何人/模块都能回答 CharBrain 当前输出的内容。
  · "角色angry所以想发泄"——写作者不必依靠 CharBrain
  · "角色determined所以推进目标"——Blueprint 自己就能写

  关键问题是：CB 的 Unique Value Proposition 是什么？

  SR2 CB Framework 定义的 USP：
  Identity（Primary/Secondary/Dormant）只有 CB 能推导
  Value System 的演化轨迹（哪卷优先级变化 + 触发事件）只有 CB 能推导
  Belief 的 Strength/Decay 只有 CB 能计算
  Decision Space 的候选概率分布只有 CB 能推导
  Semantic Decision + Cost 只有 CB 能选择

  CharBrain 实际提供的 USP：
  情绪漂移机制（30% 概率回归默认）—— 任何一个随机数生成器能实现
  关系衰减机制（每章 0.05）—— 任何一个计数器能实现
  缺席告警（10 章未出场触发）—— 任何一个 if 语句能实现

  CharBrain 没有 Unique Value。
  它的所有能力都可以被 Director 或 Writer 轻易替代。
  它当前的 Decision Ownership 约等于 5%。

  SR2 CB Framework 设计上有 Unique Value，
  但实现为零。

Q5 - Replacement Test（删除 Blueprint 中所有角色行为，
      仅保留 Pressure + Constraints，CB 是否还能恢复出合理决策？）

  当前测试条件：
  Step 1: 删除 Volume 1 Blueprint 中所有 297 处"林烬"
          + 79 处"做"类动词指令 + 6 处对话
  Step 2: 仅保留：各 Phase 的核心压力和约束
  Step 3: 输入 CharBrain
  Step 4: CharBrain 输出：情绪+渴望模板

  结果：无法恢复任何合理决策。
  · CharBrain 知道角色是"protagonist"且"determined"
    → 输出"推进核心目标"
  · 但无法知道"林烬面临什么压力"→ 无法推导"
    面对维修设备被格雷抢走、主管在旁施压的压力下，
    林烬应该选择沉默观察还是主动竞争"

总结 & 分析：

  当前状态（SR1 遗留）：
  模块　　　　　　| Decision Ownership
  SCR　　　　　　 | 60%（定义了剧情→角色做什么）
  Director　　　　| 25%（character_targets + directives）
  Blueprint　　　 | 10%（场景级角色行为）
  CharBrain　　　 | 5%（情绪跟踪，无关决策）

  SR2 目标：
  模块　　　　　　| Decision Ownership
  Gravity　　　　 | 0%（定义方向，非决策）
  Director　　　　| 0%（生成 Pressure，非决策）
  Blueprint　　　 | 0%（记录结果，非决策）
  CB (SR2)　　　　| ~100%（唯一推导决策）

  SR2 CB Framework 已设计（文档冻结）但零实现。
  CB-001 的 Decision Trace 数据已就绪（可用作验证）
  CharBrain 是 SR1 遗留物，不是 SR2 CB

  结论：
  这不是"CB 能力不足"（Result A），
  也不是"CB 有能力但没获得决策权"（Result B）。
  而是比两者更根本的问题：

  SR2 CB 从未被构建。

  已冻结的 Framework 文档、CB-001 标注数据、P0 Interface Isolation
  构成了完整的 SR2 CB 设计蓝图，但没有任何代码实现它。
  现有的 CharBrain 可以退役——它在 SR2 架构中没有位置。

  这意味着 V2-003 的修复方向不是"增强 CharBrain"，
  而是"根据已冻结的 Framework 重新构建 SR2 CB"。

Decision Ownership 全景（V2 累计）：
  ┌──────────────┬────────────┬────────────────────────────┐
  │ 模块         │ Ownership │ 身份                       │
  ├──────────────┼────────────┼────────────────────────────┤
  │ SCR          │ ~60%      │ SR1 遗留,需降为0%          │
  │ Director     │ ~25%      │ SR1 遗留,需转为Pressure     │
  │ Blueprint    │ ~10%      │ SR1 遗留,需转为记录层       │
  │ CharBrain    │ ~5%       │ SR1 遗留,需退役             │
  │ SR2 CB       │ 0%        │ 已设计,未构建               │
  └──────────────┴────────────┴────────────────────────────┘

Impact:
  · V2-003 是 V2 的判定点（Decision Point）
  · 它证明了一个比"越界"更严重的问题：
    不是"Decision Ownership 被分走了"，
    而是"SR2 的 Decision Owner 不存在"
  · 如果 V2-003 这个判定点确认为 Current 状态，
    那么 SR2 的 Architecture 修复不只是"削减越界"，
    而是"新建 CB 模块"。
  · 后续 V2-004 和 V2-005 的走向会因此变化：
    如果 CB 不存在，那么"接口越权"和"数据流损失"
    的优先级可能低于"先建 CB"。

Repair Principle:
  不是在现有架构上修修补补，
  而是根据已冻结的 Framework 文档构建新的 CB 模块。
  CharBrain 退役或降级为"情绪跟踪辅助模块"。

Repair Target:            新建 opentale/app/cie/ 模块（Character Inference Engine）
                          实现：Identity Activation → Value Prioritization →
                          Belief Strength Decay → Knowledge Boundary →
                          Decision Space Derivation → Semantic Decision + Cost
                          验证：使用 CB-001 Decision Trace 做单选题验证
Repair Cost:              M（新模块构建）→ 可拆分为 CIE Core + CB-001 验证两步
Regression Risk:          Medium（新建模块存在集成风险，但可通过 CB-001 验证降低）

补充说明：
  V2-003 的 Finding 与前两项（V2-001、V2-002）性质不同。
  V1-V2-001-V2-002 证明了同一个根因（Story Blueprint 范式）
  从 SCR 向下传播到 Director 再到 Blueprint。

  V2-003 证明了一个不同的问题：
  SR2 定义了解决 Story Blueprint 范式的方案（CB），
  但只定义了方案，没有构建方案。

  这意味着：
  · Theory（SR2 的 Pressure Blueprint 范式）✅ 稳定
  · Architecture（SR2 设计的 CB Framework）✅ 存在
  · Implementation（实际运行代码）❌ 缺失

  如果修复 V2-003（构建 CB），
  SR2 就从"设计"变成了"可运行系统"。
```

### V2-004

```
Finding ID:               V2-004（Interface Boundary — 全链路 Cascade）
Status:                   ❌ Non-Compliant
Primary Boundary:         Gravity → SCR/Director → Blueprint → CB → Writer
Secondary Impact:         证实 Decision Leakage 不是独立事件，而是沿 Pipeline
                          逐层累积的"决策泄漏瀑布（Decision Leakage Cascade）"
Evidence Strength:        E2（代码追踪 + 数据流追踪，五层中有四层可量化）

V2 四问审计法（对全链路应用）：

Q1 - 整条链路的输入和预期输出是什么？

  SR2 预期数据流：

  Theory
    │  输出: Narrative Gravity（文明观察者主题）
    ▼
  Gravity
    │  输出: 主题约束（什么不能做）
    ▼
  SCR (Pressure Blueprint)
    │  输出: 角色必须面对的压力 / Constraints / Stakes
    ▼
  Director
    │  输出: Decision Frame（Knowledge Boundary + 可选集）
    ▼
  Character Benchmark
    │  输出: Decision Space + Semantic Decision + Cost
    ▼
  Blueprint (记录层)
    │  输出: 不可逆决策的记录
    ▼
  Writer
    │  输出: 将决策转化为叙事散文

  SR1 实际数据流：

  Blueprint（SR1 Story Blueprint）
    │  输出: 执行剧本（行为+事件+对话 ≈97% 决策泄漏）
    ▼
  BlueprintParser.parse_volume()
    │  转化: 提取 summary（剧情推进）→ 放入 ChapterSpec
    │  泄漏保留率: ≈100%（行为文本原样传递，不压缩）
    ▼
  ChapterSpec
    │  key_events = summary 前几句（行为指令）
    │  scene_cards → purpose = summary 第一段
    │  泄漏保留率: ≈95%
    ▼
  MasterDirector / DirectorService
    │  生成: directives（含 character_targets）+ scene_cards
    │  泄漏保留率: ≈70%（见 V2-001）
    ▼
  WriterInputContract
    │  接收: narrative_goal / key_events / scene_cards
    │  字段设计干净但内容已被上游决策
    ▼
  WriterExecutor._generate_scene()
    │  构建: _struct_block（场景目的=蓝本原文, 冲突="", 转折=""）
    │  最终提示词: "场景目的: 林烬走向设备..."
    ▼
  LLM → 正文（与蓝本一致的行为）

Q2 - 哪些信息在当前流程中被传递到下一层时发生泄漏？

  追踪示例（Volume 1 Blueprint → 正文的完整穿透）：

  Step 1: Volume Blueprint 写"林烬修复通讯器"
          ↓ 泄漏类型：行为指令（作者直接写了角色做什么）
          
  Step 2: BlueprintParser 提取 summary = "林烬看了一眼设备..."
          ↓ 泄漏：原样提取，不做任何压力抽象
          
  Step 3: ChapterSpec created with:
          - key_events = ["林烬检查维修设备", "格雷嘲讽", ...]
          - scene_cards[0].purpose = "林烬看了一眼设备：一小时..."
          ↓ 泄漏：行为细节进入关键事件和场景目的
          
  Step 4: MasterDirector adds directives:
          - character_targets 指定角色行为
          - directives 混合压力和指令
          ↓ 泄漏（V2-001）：~70% 保留
          
  Step 5: WriterExecutor reads scene_card:
          - purpose → "场景目的: 林烬看了一眼设备..."
          - conflict → ""（空）
          - turn → ""（空）
          - exit_state → ""（空）
          ↓ 关键发现：Writer 没有得到场景冲突/转折/出口
            只得到了"场景目的=蓝本剧情描述"
            
  Step 6: LLM prompt 组装：
          "场景目的: 林烬看了一眼设备：一小时。"
          "场景冲突: "（空）
          "场景转折: "（空）
          "场景出口状态: "（空）
          ↓ Writer 被降级为"扩写器"
            LLM 被告知"写这个场景"，而不是"面对这个压力的角色，他选了..."

Q3 - 当前 Pipeline 的每一层是否都在侵蚀下一层的决策权？

  汇总量化：

  ┌───────────────────┬────────────┬────────────────────────────────┐
  │ 层               │ 泄漏率     │ 说明                            │
  ├───────────────────┼────────────┼────────────────────────────────┤
  │ Blueprint        │ ≈97%      │ Story Blueprint — 全剧本         │
  │ BP→ChapterSpec   │ ≈95%      │ 原样提取，不压缩                │
  │→Director         │ ≈70%      │ 混合压力和行为指令               │
  │→Writer           │ ≈95%      │ 接收"场景目的=蓝本行为"         │
  │→LLM→正文         │ ≈100%     │ LLM 遵命执行，产生一致行为      │
  ├───────────────────┼────────────┼────────────────────────────────┤
  │ Cascade Total    │ 90-97%    │ 从 Blueprint 到正文，            │
  │                  │           │ 行为指令几乎无损穿透             │
  └───────────────────┴────────────┴────────────────────────────────┘

  Character Benchmark 在整个流程中不存在。
  这不是"泄漏到 CB 又泄漏出去"——是"CB 根本没参与"。
  
  CB 的缺失意味着整条 Pipeline 中没有任何一层能回答：
  "角色为什么做这个选择？"
  
  答案一直是：因为 Blueprint 这么写了。

Q4 - 整条链路是否可以被抽象为一条统一的越权链？

  是。证据如下：

  Decision Leakage Cascade Mode（决策泄漏瀑布模式）：

  理论层: Theme / Gravity 指定方向
    │
  Blueprint: "林烬走向设备并拆开外壳"  ← 写死了角色行为
    │  泄漏类型：替角色做了决定
    ▼
  Parser: ChapterSpec.summary = 同上
    │  泄漏类型：原样传递，不做抽象
    ▼
  Director: directives = 补充角色指令
    │  泄漏类型：替 CB 推导了角色决策
    ▼
  Writer: "场景目的: 蓝本行为" → LLM
    │  泄漏类型：替 Writer 决定了内容
    ▼
  正文: 角色做了 Blueprint 写过的事

  这条链的每一条箭头都不回答"压力是什么"，
  而回答"角色应该做什么"。

  这就是 Story Blueprint → Pressure Blueprint
  范式的完整代码级实证。

当前状态：
  整条 Pipeline 遵循 Story Blueprint 范式。
  每一层都在告知下一层"故事该怎样"，
  而非"角色面临什么压力、他如何选择"。

  Character Benchmark 不是"能力不足"——它根本不在 Pipeline 中。
  没有 CB 存在的情况下，Decision Ownership 必然落在
  Blueprint / Director / Writer 上。

  这是"设计"问题，不是"实现"问题。
  SR2 设计了 CB 但未构建它，
  所以 Pipeline 在 SR1 范式下运行，
  产生 SR1 的结果（100% Story Blueprint）。

Expected（SR2 目标）：
  Gravity → Pressure → Decision Frame → CB → Decision Space → Writer
  
  每一条箭头只回答"我向下一层交付什么压力"，
  不回答"下一层应该怎么选"。

  修复链：
  1. 构建 CB（V2-003 修复）
  2. Director 只输出 Pressure + Decision Frame（V2-001 修复）
  3. Blueprint 只记录压力/约束，不写角色行为（V2-002 修复）
  4. Writer 接收 Decision Space（角色选了A）而非"角色应该做A"
     （内容变化：prompt 从"场景目的=蓝本行为"变为
      "压力=林烬面对设备维修被格雷抢夺的局面，优势=技术自信，
       劣势=在主管监视下，选择=沉默观察还是主动竞争"）

Impact:
  · V2-004 是"决策泄漏瀑布"的最终实证。
  · 它不是独立的 Finding，而是 V2-001~V2-003 的综合证明：
    前三项分别证明 SCR/Director/Blueprint 三个点的泄漏，
    V2-004 证明这些泄漏是沿整条 Pipeline 持续累积的。
  · 修复必须从上游（Blueprint）开始，不能从下游（Writer）开始。
    因为 Cascade 的方向是单向的（上游→下游），
    修复 Writer 而不修复 Blueprint 等于在瀑布底部修水。
  · Character Benchmark 的构建（V2-003 修复）是 Cascase 能否
    被中断的关键——它是唯一被设计来吸收 Presssure → Decision
    转化层的位置。

Repair Principle:
  每一层只能向下一层交付压力和约束，不能交付行为指令或决策。
  整条 Pipeline 应重构为单向 Pressure Transmission 链。

Repair Target:            Volume Blueprint → WriterPrompt 整条链的范式重构。
                          不是修单个文件，而是修链路契约。
                          关键动作：
                          (1) 在新 CB 就位前不修改 Writer 接口
                              （CB 是唯一合法的 Decision Source）
                          (2) Blueprint 改为 Pressure Blueprint 格式
                          (3) BlueprintParser 改为提取 Pressure 而非剧情推进
                          (4) Director 改为生成 Decision Frame 而非 directives
                          (5) Writer 改为接收 "角色面对什么 + 他选了" 而非 "角色做什么"
Repair Cost:              L（整条 Pipeline 的契约变更，涉及
                          BlueprintTemplate / BlueprintParser /
                          DirectorService / WriterInputContract /
                          WriterExecutor 五层）
Regression Risk:          High（需要新 CB 模块就位后，
                          才能验证角色决策的正确性；
                          修复过程中 Pipeline 需临时双轨运行）

补充说明：
  V2-004 回答了老高提出的核心问题：
  "Decision Leakage 究竟是在每一层独立发生，
  还是沿着整条 Pipeline 不断累积？"
  
  答案是：不断累积。
  
  每一层都在前一层的基础上延续相同的泄漏模式。
  泄漏率的微小差异（97%→70%→95%）取决于各层的
  具体实现差异，但核心趋势是"行为指令从 Blueprint
  到正文几乎无损穿透"。
  
  Writer 的 WriterInputContract 设计本身是干净的
  （见 contracts.py——字段标注 owner、禁止 dict[str, Any]），
  但内容是被上游污染之后才到达 Writer 的。
  不是 Writer 的错——是上游数据格式的错。
```

### V2-005

```
Finding ID:               V2-005（Data Flow Audit — Theory → Generation）
Status:                   ❌ Non-Compliant
Primary Boundary:         Theory → Gravity → Director → CB → Writer Prompt → Generation
Evidence Strength:        E2（Prompt 字符串分析 + 模板对比）

Q1 - SR2 Theory 层的信号，哪些到达了最终 Prompt？

  SR2 Theory 预期的信号链：

  Theory（单一根因：Story→Pressure 范式迁移未完成）
    │
    ├─ Narrative Gravity                                    ❌ 未到达
    │  例："真正毁灭文明的，从来不是未知，而是确定的未来"
    │
    ├─ Theme                                                ❌ 未到达
    │
    ├─ Core Question                                        ❌ 未到达
    │  例："如果未来已被证明会发生，人的选择还有意义吗"
    │
    ├─ Narrative Constraints（C-01 ~ C-05）                  ❌ 未到达
    │  例："不提前解释"——Prompt 中没有对应字段
    │
    ├─ NarrativePressure                                     ⚠️ 部分到达（但空）
    │  对应 Prompt 字段：SceneCard.conflict = ""（空）
    │
    ├─ Decision Frame                                        ❌ 未到达
    │  Prompt 中没有"角色面临什么选择"字段
    │
    ├─ Character Decision Space                              ❌ 未到达
    │  Prompt 中没有 Decision Space 字段
    │
    ├─ Constraints                                            ⚠️ 部分到达
    │  Prompt 中有"Style rules"和"Requirements"
    │  但它们是写作约束（字数/格式/视角），非叙事约束（不能做什么）
    │
    └─ Character Identity / Value / Belief                   ❌ 未到达
       Prompt 中有"角色声线约束"（voice_profiles），
       但这不是 Identity（Primary/Secondary/Dormant）

  SR1 实际到达 Prompt 的信号：

    ├─ Chapter summary（来自 Blueprint 剧情推进）              ✅ 到达
    │   这是一个"行为文本"，不是压力文本
    │
    ├─ Scene cards（目的/地点/角色/入场）                     ✅ 到达
    │   但 conflict（冲突） / turn（转折） / exit（出口）通常为空
    │
    ├─ Key events（关键事件）                                 ✅ 到达
    │   有清洗逻辑（过滤元叙事指令），但清洗后仍是行为描述
    │
    └─ Story premise / World rules / Cast / Previous chapter  ✅ 到达
       这些是背景信息，不是决策/压力信息

Q2 - 数据流在每一层的损失率是多少？

  ┌─────────────────────┬──────────┬─────────────────────────┐
  │ 信号               │ SR1 状态 │ 到达 Prompt 的百分比    │
  ├─────────────────────┼──────────┼─────────────────────────┤
  │ Narrative Gravity  │ 不存在   │ 0%                      │
  │ Theme              │ 不存在   │ 0%                      │
  │ Core Question      │ 不存在   │ 0%                      │
  │ Constraints(C-01~) │ 不存在   │ 0%                      │
  │ NarrativePressure  │ 存在但空 │ ≈5%（conflict 字段可能填）│
  │ Decision Frame     │ 不存在   │ 0%                      │
  │ Decision Space     │ 不存在   │ 0%                      │
  │ Character Identity │ 不存在   │ 0%                      │
  │ Character Belief   │ 不存在   │ 0%                      │
  │ Stakes             │ 不存在   │ 0%                      │
  ├─────────────────────┼──────────┼─────────────────────────┤
  │ 行为指令（来自 BP） │ 大量     │ ≈95%（经过清洗仍有大量）│
  │ 写作约束           │ 中等     │ ≈80%（风格/格式/视角）   │
  │ 背景信息           │ 中等     │ ≈70%（前提/世界/阵营）   │
  └─────────────────────┴──────────┴─────────────────────────┘

  关键发现：
  整条 Theory → Prompt 链路中，SR2 定义的所有核心信号
  （Gravity / Theme / Pressure / Decision / Identity / Belief）
  抵达率均为 0%。

  Prompt 中大量存在的是"行为指令"（来自 Blueprint 剧情推进）。
  Writer 被告知"角色做什么"，而非"角色面临什么"。

  Prompt Builder（prompt_builder.py）实际上有一些清洗逻辑，
  试图过滤 key_events 中的元叙事指令（"推进:XXX""出场:XXX"），
  但这种清洗只是去除"元叙事标签"，保留的仍然是行为描述。

  这是"信号替换"而非"信号损失"：
  · 应该存在的信号（Pressure / Decision Space）从未进入 Pipeline
  · 不应该存在的信号（行为指令）占据整个 Prompt

Q3 - 从数据流角度看，Decision Leakage Cascade 在 Prompt 层的表现？

  整条泄漏链的最终终点：

  Blueprint（97% 行为）
    ↓  Parser 原样提取
  ChapterSpec.summary（行为文本）
    ↓  Director 传递给 Writer
  WriterInputContract（场景目的=BP行为，冲突=空）
    ↓  prompt_builder.py 组装（含清洗逻辑）
  最终 Prompt：
    "Chapter summary: 林烬走进房间..."
    "Scene 1 purpose=林烬看了一眼设备... conflict="" turn="" exit=""
    "Key events: 林烬检查设备, 格雷嘲讽..."
    ↓  LLM 生成
  正文（还原 Blueprint 行为）

  如果去除 Prompt 中所有来自上游的行为指令（summary / scene_card
  purpose / key_events），只保留压力/约束/决策信息，当前 Prompt
  会变得极为稀疏：
  · Story premise（背景）
  · World rules（背景）  
  · Cast（背景）
  · Style rules（风格）
  · 以上全部不是决策信息

  Writer 无法从"角色面临什么压力"开始写作，
  因为 Prompt 中没有压力信息。
  Writer 只能从"角色做什么"开始写作，
  因为 Prompt 中充满了行为信息。

Q4 - 如果整条数据流按 SR2 重构，Prompt 会有什么变化？

  SR2 预期的 Prompt 结构：

  Writer 接收的是：
  · Narrative Gravity（故事方向，一劳永逸）
  · Context（世界/阵营/历史）
  · Character Pressure + Character's Knowledge Boundary
    （角色知道什么、面对什么困境）
  · Decision Space + Character Choice
    （角色在什么选项中选了哪个、为什么）
  · Constraints（这一章不能做什么）
  · Writing Requirements（风格要求）
  · Previous Chapter（上一章正文）

  Prompt 中不包含：
  · 角色行为描述（"林烬走向设备"）
  · 场景细节（"他拆开外壳"）
  · 对话内容（"一小时，他说"）

  这些全部应该由 Writer 根据"角色面对什么压力 + 角色做了什么选择"
  自然推导。

  示例对比（SR1 vs SR2 Prompt）：

  SR1 Prompt:
  Chapter summary: 林烬在维修舱检查通讯设备，格雷嘲讽他。
  Scene 1: purpose=林烬看了一眼设备说一小时
            conflict= turn= exit=
  Key events: 林烬检查设备, 格雷嘲讽

  SR2 Prompt:
  面对场景：林烬需要在格雷的挑衅下维修设备，
            主管在一旁观察，这是一个测试。
  林烬的选择：专注维修（builder Identity），不理会格雷
  林烬的代价：被格雷视为软弱
  约束：不能主动冲突、不能在主管面前暴露技术能力
  林烬知道：这台设备是旧型号（维修难度高但可修）
  林烬不知道：格雷在测试他的忠诚
  Chapter purpose: 通过林烬的维修过程展示他的 builder Identity
                   同时埋下格雷怀疑的伏笔

  SR2 的 Prompt 更具信息密度，
  且不会提前写出"林烬说了什么、做了什么"。
  这些细节应由 Writer 根据"林烬选择了专注维修"推导。

Impact:
  · V2-005 作为 V2 最后一关，证明了整条理论→正文数据流的
    Signal Arrival Rate 为 0%。
  · 不是"信号衰减"（比如 Gravity 到达但模糊），
    而是"信号从未进入 Pipeline"（Gravity 从未被写入任何字段）。
  · 与此同时，"噪音信号"（行为指令）以 ≈95% 的比率
    从 BP 到达 Prompt。
  · 修复路径：不是增强 Prompt Builder 的清洗逻辑，
    而是从上游蓝本格式开始重做——让正确的信号进入 Pipeline。
  · V2-005 确认了 V2 全链路的发现：
    问题不是"In Prompt"，而是"In Pipeline"。
    整条链都是 SR1 范式，没有任何一层接入 SR2 数据。

Repair Principle:
  从 Theory 层开始，建立信号注入 Pipeline：
  (1) Gravity 在项目创建时写入（一劳永逸，每章继承）
  (2) Volume Blueprint 记录 Pressure 而非剧情
  (3) Director 从 Gravity + Blueprint Pression 生成 Decision Frame
  (4) CB 从 Decision Frame 推导 Decision Space + Choice
  (5) Writer Prompt 接收 Decision Space + Choice，而非剧情描述
  (6) Writer 从"角色面对什么 + 它选了"推导正文

  Prompt 层面的唯一变更：
  删除"Chapter summary"和"Key events"（行为指令来源），
  替换为"Chapter Pressure"和"Character Decision"。

Repair Cost:              L（Data Flow Pipeline 重做）
Regression Risk:          High（依赖 CB 构建完成后才能验证）

补充说明：
  V2-005 是 V2 全链路的逻辑终点。
  
  如果说不考虑 Chain of Findings：
  V1：SCR 不是 Pressure Blueprint
  V2-001：Director 不只输出 Pressure
  V2-002：Blueprint 是执行剧本
  V2-003：Character Benchmark 不存在
  V2-004：Decision Leakage 沿 Pipeline 级联
  ⋮
  V2-005：Prompt 中没有任何 SR2 信号，
          全是 SR1 行为指令。
  
  那 V2-005 是预期之中。
  既然上游全链是 SR1 范式，
  下游 Prompt/Writer 自然只有 SR1 数据。
  
  V2-005 的价值不是"发现了问题"，
  而是"证明了整条链从 Theory 到正文
  没有任何一个可以自然转化为 SR2 的节点"。
  
  这意味着：**修复必须从上游开始**。
  修 Writer/Prompt 不解决任何问题，
  因为 Writer 收到的数据格式来自上游。 
  只有上游格式变（Blueprint 从行为→压力），
  Writer 的输出才会变。

  V2 五关全部完成。
```

---

## V2 最终架构判定（老高 2026-07-17 16:26）

```
Status:                   COMPLETE
Architecture:             FAILED
Root Cause:               Blueprint Execution Paradigm
Severity:                 L2 Structural Failure（非单层问题，全 Pipeline 范式级）
Impact:                   Entire Generation Pipeline
Required Action:          引入 Intent Inference Layer
Mark PASS/FAIL:           不标记 PASS，标记 Architecture FAIL / Refactor Required
```

### V2 的定性

V2-001 ~ V2-005 不是五个 Bug，是一个 **Single Root Cause Finding**。

OpenTale 当前 Pipeline 的核心数据模型仍然是 **Blueprint Execution Model**，不是 **Narrative Intent Translation Model**。

```
现在：
Story Blueprint → 章节生产 → 正文生成
本质：把作者设计好的行为计划翻译成文字

目标：
Narrative Theory → Constraints / Intent / State → Inference → Scene Possibilities → Writer Generation
本质：根据叙事约束推导故事
```

两者外形态似，但智能性质完全不同。

### 老高对各发现的补充判断

**V2-001 Director Boundary**
> Director 不应该告诉 Writer "林晨必须怀疑张某、必须发现线索、必须冲突升级"。这些已经是剧情选择。
> Director 应该输出：Narrative Objective / Character State / Available Pressure / Forbidden。
> Director 提供空间，不提供动作。

**V2-002 Blueprint Boundary**（最重要的一刀）
> 当前 Blueprint 是 Script，不是 Blueprint。
> 真正 Blueprint 应该包含：Chapter Function / Reader Question / State Delta / Required Pressure / Forbidden Resolution。

**V2-003 CB Boundary**
> CB 不是缺一个模块，而是整个架构缺少中间推理层（Intent Interpretation Layer）。
> CB 的真正定位不是 Chapter Builder，而是 **Constraint Bridge**——理论→可执行叙事约束。

**V2-004 Pipeline Cascade**（五个中价值最高）
> 不是某个 Prompt 写坏，而是输入数据已经污染。
> 以前 Quality Gate 发现的问题（人物机械、情节可预测、冲突模板化）其实都是上游 Decision Leakage。

**V2-005 Data Flow**
> 理论存在，但没有 Runtime Effect。相当于数据库有字段但业务没有读取。

### 正确顺序（非 V3）

```
Step 1: DECISION_OWNERSHIP_MAP.md（定义谁有权决定什么）
Step 2: Intent Data Schema（替换 ChapterSpec.summary 为 ChapterIntent）
Step 3: V3 Inference Validation（验证 Theory → Intent → Inference → Scene Candidate 是否真实存在）
```

### 老高的最终判断

> V2 已经完成它最大的价值：不是修 Bug，而是证明当前 Engine 需要从「剧情执行器」升级为「叙事推理系统」。这也是后续 NarrativeAgent、ReaderOS、Belief Engine 能真正接入的前提。
