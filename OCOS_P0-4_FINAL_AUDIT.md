# OCOS P0-4 FINAL AUDIT — ATTEMPT 2 裁决（冻结）

> 状态：**CONDITIONAL PASS（Attempt 2 已冻结）**；P0-4A = PASS/CLOSED；**P0-4B Production = FROZEN/BLOCKED（2026-09-13 裁决，见 §9）**。
> 本文件为 P0-4 Attempt 2 的正式审计结论，记录证据强度、降级说明、反证条件与后续独立验证项。
> **冻结纪律：不再为刷 PASS 修改 Production、不重跑 A2、不反向补 ThinkingTrace、不为满足审计而重构生产控制流。**

---

## 1. 阶段状态总览

```text
P0-1  Self S2 Power-on               ✅
P0-2  Self Evidence / Claim / Delta  ✅
P0-3  Production S2-only Thinking    ✅
P0-4  X → D → S2 → Decision → Y      🟡 CONDITIONAL (Attempt 2)
  ├─ P0-4A 实时认知消费              ✅ PASS / CLOSED
  └─ P0-4B 生产 LLM 决策验证         ⛔ FROZEN / BLOCKED（§9）
```

---

## 2. P0-4 Attempt 2 最终裁决

> **P0-4 Attempt 2：CONDITIONAL PASS / 有条件通过。**
>
> 在**冻结实验变量、冻结 Z、真实执行 A1/A2、排除 E1–E4 混杂因素**的条件下，
> OCOS 已在**受控、确定性的 Decision₂ Harness** 中验证：
>
> **真实失败 X → Recognition → Self Claim C01 → Self Delta D → governed S2 v3 → Decision₂/Strategy₂/Action₂ 相对 Z 发生结构性变化 → 实际产生 Y ≠ Z。**
>
> 该结果证明 **Self Delta 已具备进入后续认知决策并产生行为差异的真实因果通路**，
> 不再属于单纯 Prompt Injection 或版本变化证据。

---

## 3. 因果链证据钩子（全部可回放）

```text
X              真实 A1 执行 exit=127 command not found，side_effect_zero   (step1)
  ↓
evidence_id    S1E-863AF5B91BD2 | data_hash 310a18d8…a0a2              (step1)
  ↓
Recognition    C00(capability_uncertain)+ C01(failure_pattern)          (step2)
  ↓
D              delta_id=01b9a855…d73326 | claim=C01 | v2→v3            (step2)
  ↓
S2 v3          content_hash 63de6a90…→dd9ee999…                        (step2)
  ↓
Z freeze       P0-4-Z-001 @ 08:57:14Z，frozen BEFORE A2，Z_clean       (step3)
  ↓
Decision₂      policy(S2 v3)=verify_first ≠ policy(no-D)=trust(==Z)    (step4)
  ↓
Action₂/Strategy₂  ≠ Z（方法学改变：category-detect→可验证内容标签）   (step4)
  ↓
Y              moved={src_a,b→src_out; doc_c→doc_out}, out.txt 真实产物  (step4)
  ↓
Trace          TNG-F693EFA38C59→DEC-F0937AC6111C                       (step5/6)
```

---

## 4. 逐项判定表

| 层级 | 结论 |
| --- | --- |
| X 真实发生 | ✅ PASS |
| Recognition | ✅ PASS |
| Self Claim C01 | ✅ PASS |
| Self Delta D | ✅ PASS |
| Governed S2 commit | ✅ PASS |
| S2 v3 被读取 | ✅ PASS |
| Decision₂ 与 Z 差异 | ✅ PASS |
| Strategy₂ 与 Z 差异 | ✅ PASS |
| Action₂ 与 Z 差异 | ✅ PASS |
| Y 实际产生 | ✅ PASS |
| Y ≠ Z | ✅ PASS |
| Z 先于 A2 冻结 | ✅ PASS |
| E1 环境混杂 | ✅ 排除 |
| E2 sampling | ✅ 排除（限 deterministic harness） |
| E3 capability confounding | ✅ 排除 |
| E4 prompt variation | ✅ 排除 |
| C01 → Decision₂ **实时消费记录** | ✅ PASS / CLOSED（P0-4A，受控 harness 验证） |
| Production LLM behavioral proof | ⛔ UNEXECUTABLE（P0-4B，见 §9，非证伪） |

---

## 5. 为什么不是 FULL PASS（两层限制，均如实登记）

**限制 1 — 认知消费证据时序性（P0-4A 已在受控 harness CLOSED；Production 仍为缺口）**

> 受控 harness 内，`component_consumption()` 已证明"决策时刻实际读取组件 → consumption manifest → fused ThinkingTrace+DecisionRecord 同步持久化"成立（P0-4A = CLOSED）。
>
> 但**生产运行时**未接入该机制：生产仍在决策处调用旧 `record_thinking_trace()`（全量 claims），且 `component_consumption` 未接到一个"唯一 + 原样"的实际读取点。此缺口列入 Section 9（Production Wiring GAP）。
>
> 未因 Step 4 已得到漂亮 verify_first 而反向补 ThinkingTrace。

**限制 2 — 生产运行时未接入**

- 本轮 `provider=no_api_key`（无 live LLM key，Step 0 如实披露）。
- 不能外推为："生产 LLM 已证明能因 Self Delta 改变思考与行为。"

---

## 6. 反证条件（此证据被推翻的场景）

若下列任一成立，P0-4 不再成立：
1. 同一确定性 policy 在**去除 C01 的 S2** 下仍输出 verify_first ⇒ C01 attribution 失效。
2. Z 被证明依赖 A2 后验信息 ⇒ post-hoc contamination。
3. recommend trace 无法在决策时刻同步产生 ⇒ 保持 CONDITIONAL 上限。
4. capability 缺失在 no-D 对照下同样翻转分支 ⇒ E3 未排除。

---

## 7. 后续独立验证项（不再重跑本次实验）

### P0-4A：Contemporaneous Cognitive Consumption

目标：把"消费关系"从**决策发生当下**同步持久化，而非事后倒推。

```text
Decision₂ 发生
     ↓ 同一事务/同一决策上下文
ThinkingTrace 持久化
     ↓
consumed_delta_ids = [C01]
consumed_evidence_ids = [E]
self_version = 3
```

重点：证明消费关系成立于决策时刻；`consumed_delta_ids` 精确锚定主因果 D。

### P0-4B：Production DecisionRuntime / LLM

```text
真实 S2
 ↓
真实 DecisionRuntime
 ↓
真实 LLM
 ↓
Decision₂
 ↓
Action₂
```

回答：真实 LLM 是否真的因为 Self Delta 改变自己的决策。需 API/provider 配置后才可执行；不得把 deterministic policy 结果直接外推。

---

## 8. 冻结结论

> **P0-4 Attempt 2 = CONDITIONAL PASS。**
>
> 本轮已获得 OCOS 第一条**有边界、有降级说明、有反证条件**的真实主体生命链证据：
> X → D → S2 → Decision₂(≠Z) → Y(≠Z)，且 E1–E4 排除。
>
> 子项结算：**P0-4A = PASS / CLOSED**（受控 harness 实时消费）；**P0-4B = FROZEN / BLOCKED**（见 §9）。

---

## 9. P0-4B 生产接线 — FROZEN / BLOCKED（2026-09-13 只读落点审计裁决）

> **本轮不写代码。P0-4B 生产段正式冻结。**
> 结论：**不是代码能力不足**，而是生产 runtime 的"真实决策边界"当前不存在足够小的接线点；
> 强行把"可观测性补线"凑上去，会升级成"决策控制流重构"——这正是审计阶段应挡住的。

### 9.1 阶段结算

```text
P0-4A  Decision-time Consumption        = PASS / CLOSED
P0-4B  Step 1 Provider Verifiability    = PASS / CLOSED
P0-4B  Production LLM                   = BLOCKED（MockProvider / 无真实 provider）
P0-4B  Production Consumption Wiring    = GAP CONFIRMED（NOT AUTHORIZED）
P0-4B  Production Causal Validation     = UNEXECUTABLE（不是 FAIL / 不是证伪）
```

### 9.2 核心阻点：Q4（fused trace 须先于 Action）

冻结的 P0-4A 顺序：

```text
真实 Decision₂
    ↓
Consumption Manifest
    ↓
ThinkingTrace + DecisionRecord 原子落库
    ↓
Action
```

生产现状（converse.py 多步主循环）是 **LLM 生成与 USE| 动作执行同轮交织**：

```text
LLM generation
    ↓
产生 decision / strategy / action
    ↓
同轮交织执行 USE| → Action
```

- `ThinkingTrace`（D 消费）在生成前已知；
- `DecisionRecord`（decision/strategy/action）是 LLM **输出**，生成后才可得；
- `Action` 与生成耦合在同一循环内，**不存在"输出到手但动作未执行"的干净单点**。

要为满足顺序拆解生成/执行循环 ⇒ 是 **Decision/Action control-flow refactor**，而非 minimal wiring。**此即决定性阻断。**

### 9.3 Q2 更深问题：KB 并非单一语义来源

生产 LLM 实际获得：

```text
                 ┌─ S2.knowledge_boundary（S2 字段）
                 │     └─ 有 SelfClaim / Delta / Evidence provenance
LLM Context ─────┤
                 └─ _knowledge_boundary_block()（原始 DB 聚合）
                       └─ knowledge/belief/episode 聚合，无 Self provenance
```

因此**不能宣布**："LLM 看到了 knowledge_boundary ⇒ 它消费了 C01。" 否则会把 `C01→S2` 的消费关系**合成**出来，而非 observed consumption —— 这是本审计体系最需要防的**假因果归因**。

### 9.4 冻结：三条 Production Redline

- **Redline-1 — Consumption Source**：只有"Decision₂ 实际读取的 S2 component"才能产生 consumption manifest。禁止：扫描全部 committed claims、按最终 Action 反推、按 prompt 出现某字段反推、语义猜测、用原始 DB 聚合冒充 Self Delta consumption。
- **Redline-2 — Decision-time Boundary**：必须真实存在 `LLM output complete → DecisionRecord → manifest captured → ThinkingTrace+DecisionRecord atomic persist → Action` 边界。若当前 runtime 无此边界，**不为了满足审计而重构生产控制流**。
- **Redline-3 — Dual KB Semantics**：`S2.knowledge_boundary` 与 `_knowledge_boundary_block()` 视为**两个不同 provenance source**，禁止在 P0-4B 中合并为 `knowledge_boundary = C01`（属另一架构问题，应单独立项）。

### 9.5 冻结事实：P0-4B PRODUCTION BLOCKER

```text
B1  Provider unavailable（MockProvider / 无真实 provider）
B2  No single production S2 decision consumption point（converse/bridge/recall_router 多处读 S2）
B3  knowledge_boundary has dual provenance（S2 字段 vs 原始 DB 聚合）
B4  Current LLM→USE execution is interleaved（生成/动作同轮交织）
B5  Fused decision-time persistence therefore requires control-flow change, not minimal wiring
```

### 9.6 冻结纪律（防"顺手改 Converse"）

> **不得为 P0-4B 改动 Production 决策入口 / Converse 控制流 / LLM prompt / Decision semantics。**
> P0-4B 转入 **FROZEN / BLOCKED**，等待真实 provider 条件后，再按 B1–B5 清单评估是否放行最小 wiring。
> 两条结论严格分开：
>   - Production LLM causal validation = currently **unexecutable, not disproven**；
>   - Production cognitive-consumption observability = currently **incomplete, independently of provider availability**。

*文件结尾不变式：本结论已冻结，不再为追求 PASS 而改实验、改 Prompt、改生产代码或重跑。*