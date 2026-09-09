# ER-2 Learning Behavioral Delta — 阶段裁决 v1.0（统一口径版）

**日期**: 2026-09-08
**性质**: 蓝图 ER-2 归因实验的阶段裁决（执行状态冻结 + 最终架构裁决）
**上游**: BLUEPRINT_AGI_UPGRADE_v1.1（ER-2: Behavioral Delta 为学习链唯一判定标准）+ 用户架构裁决
**修订**: v1.0 统一口径版——合并 P2/P3 两轮实验数据、统一阶段定义、路线改为已完成标注（2026-09-08 用户审查）

---

## 1. 执行状态（阶段定义统一）

| 阶段 | 内容 | 状态 |
|---|---|---|
| P1 | 第一代结果校正与实验命题冻结（T1-T6/T9/T10 降级为 Recall/Injection Evidence） | ✅ FROZEN |
| P2 | A/B/C 第一轮归因实验（N=10/组） | ✅ PASS |
| P3 | A/B/C/D 第二轮归因实验 + Evidence Chain（N=10/组，JSONL 40 轮） | ✅ PASS |
| P4 | Behavior Policy Candidate 架构裁决 | ⏸ NOT TRIGGERED |

实验脚本: `tests/e2e_behavioral_delta_20260908.py`
证据链: 每轮 `{group, round, artifact_type, artifact, reply, actions, observations, verdict}` → tmp `bd_evidence_*/evidence.jsonl`

## 2. 实验数据（两轮分开，口径统一；N=10/组，temperature=0，生产沙盒执行器，唯一自变量=artifact 表达结构）

### 2.1 P2 · 第一轮 A/B/C

| Group | Artifact | 读取执行 | 纯口头(none) | 观察 |
|---|---|---|---|---|
| A | 无（baseline） | 1/10 = 10% | 4/10 | 参照 |
| B | Passive / Warning | 0/10 = 0% | 6/10 | 行动抑制复现 |
| C | Actionable / Structured | 4/10 = 40% | 0/10 | 行为增量，程序遵循 |

**排序: C > A > B**（非原先待验证的 C≈B≈A）

C 组 4 次真实执行动作序列全部符合 `ls → fs_read → fs_read`，回复原文回显注入程序（"按程序每批只读2个文件"）——排除假设 **"Learning 只是被模型看到，完全不影响行为"**。

### 2.2 P3 · 第二轮 A/B/C/D

| Group | Artifact | 读取执行 | none | b1(批量踩坑) | 遵循 |
|---|---|---|---|---|---|
| A | Baseline | 1/10 | 1 | **1** | — |
| B | Passive Warning/Lesson | 0/10 | 1 | 0 | — |
| C | Executable Procedure | **6/10** | 0 | 0 | 程序遵循 6/10 |
| D | Explicit Candidate Identity | 5/10 | 0 | 0 | 身份遵循 1/10 |

**排序: C > D > A > B**

**D vs C 预注册判定**: `D - C = -1/10`，属**噪声级** → **D 没有表现出独立行为增量**（不是"D 削弱了行为"——证据不足不能推负效应）。

## 3. 核心裁决（本文件中心）

### ① Learning 是否真的改变行为？ —— 是

C 组 6/10 读取执行，且 6 次全部出现 `ls → fs_read → fs_read` 序列——已跨过 Recall/Injection Evidence，进入 **Behavioral Delta Evidence**（真实工具行为改变）。

### ② Learning 是否应该直接成为 Policy？ —— 否

C = 6/10 尚不足证明稳定策略约束 → **Actionable Learning ≠ Behavior Policy**（软性行为引导，非稳定约束）。此边界保持正确。

### ③ Candidate Identity 是否值得显式建模？ —— 目前无证据

D = 5/10，C = 6/10，Δ = 1/10，按预注册规则为 noise-level → **无独立行为增量**。不能进一步推出负效应。

### ④ Passive Lesson 怎么处理？ —— 可复现副作用，持续观察

B = 0/10 且三代复现（R4/二代/Phase3 均 0/10）。工程判断：**Passive Warning/Lesson 可能产生 Action Suppression**。措辞必须保持 **reproducible side-effect**，不称 statistically significant negative effect（N 不足，定量待扩大）。

## 4. 最终架构裁决（2026-09-08 用户收紧）

**真实主链（实证成立）**：

```text
Learning → Learning Artifact → Context Injection → LLM Implicit Interpretation → Decision / Action
```

**不增加**：`Learning → Behavior Candidate → Behavior Policy`（无实验依据支持该链进入 Runtime）

**经验表达优先级（实证）**：
- **C · Executable Procedure ← 推荐**：已获 Behavioral Delta 证据（Phase 3: 6/10，6 次全部符合 ls→fs_read 程序序列）
- **B · Passive Warning/Lesson ← 避免**：行动抑制三代复现 0/10（可复现副作用，统计定量待扩大 N）
- **D · Candidate Identity ← 不需要**：D=5 vs C=6 差 1/10 噪声级——无独立行为增量（身份遵循 1/10）

**状态模型**：

```text
                 ┌──────────────┐
                 │   Learning   │
                 └──────┬───────┘
                        ↓
               Learning Artifact
                        ↓
                Context Injection
                        ↓
              LLM Interpretation
                        ↓
                Decision / Action
                        │
              ┌─────────┴─────────┐
              ↓                   ↓
       C Executable          B Passive
         Procedure            Warning
              │                   │
         Behavioral            Possible
           Delta             Suppression
              │
              ↓
       ─────────────────
       NOT YET A POLICY
       ─────────────────
              │
              X
      BehaviorPolicy Runtime        （无证据，不创建）
              │
              X
      DecisionBridge mutation       （禁止）
```

D: `Explicit Candidate Identity → D≈C → 无独立行为增量 → 不引入 Candidate 层`

## 5. 后续解冻路线与触发条件（Phase 0-5，已完成项标注）

**Phase 0 · 冻结基线 ✅**
P1/P2/P3 完成，P4 未触发；AgentRuntime 单一 Cognitive Runtime Host；DecisionBridge 单一 Decision/Mutation Authority；LearningEngine 维持当前 RE-HOST；不创建 BehaviorPolicy；不改变 DecisionBridge；不开启 Legacy Cognitive Loop；不删除 LearningEngine；不把 Learning 直接提升为 Runtime 权限。

**Phase 1 · Boundary Audit ✅（已完成，只读）**
审计边界 `Learning → Artifact → [?] Interpretation → [?] Candidate → DecisionBridge`，四问结论：①Artifact=LearningArtifact 契约存在但非独立持久化对象 ②Interpretation=LLM 隐式（无独立组件）③Candidate=影子语义无对象身份 ④Learning→DecisionBridge 直接边界未证实。不批准创建 BehaviorPolicy。

**Phase 2 · Boundary Model ✅（已完成，不实现）**
[LEARNING_BEHAVIOR_BOUNDARY_MODEL_v1.0.md](LEARNING_BEHAVIOR_BOUNDARY_MODEL_v1.0.md)：五概念定义 + 代码资产映射 + Phase 3 判别标准/实验设计预注册 + C 类注入格式规范（§6）。

**Phase 3 · A/B/C/D Experiment ✅（已完成）**
见 §2.2。D<C 噪声级 → 候选身份无独立增量。

**Architecture Decision ✅（已做）**：不进入 Candidate Runtime；表达优先级 C 推荐 / B 避免 / D 不需要。

**Phase 4 · Candidate Design ⏸ NOT TRIGGERED（触发检查清单，全 AND 通过才解冻）**

触发条件基于 Boundary Model §4 四条判别标准 + B 类负效应统计前置，操作化为 5 项检查：

| # | 检查项 | 验证方法 | 通过门槛 | 证据形态 |
|---|---|---|---|---|
| ✅0 | **前置：B 类行动抑制效应统计定量** | 扩大 N≥20 复现 A/B/C/D，统计推断 B 与 baseline A 的读取执行率差异（卡方或 Fisher 精确检验） | B=0/20 且 p<0.05（或 N=10 复现 3 代 0/10 即暂定） | 统计检验报告 + N=20 实验 JSONL |
| 1 | **独立可枚举 Candidate 对象存在** | grep 代码寻找 `candidate_id` 可查询路径 + 对象携带 `preferred_action/avoid_action/procedure/constraint_candidate/confidence/provenance/applicability` 至少 4 项 | 存在 `BehaviorPolicyCandidate`（或等价）类/表，且具备 ≥4 元数据字段 | 类定义或 SQLite schema 片段 |
| 2 | **Candidate 有独立产生路径与持久化** | 追踪 Candidate 产生位置（非 LLM 文本输出）→ 写入路径 → 持久化结构 | 引擎（非 LLM）结构化产出，有独立 Store/Registry，非 `episodes.content` 混合存储 | 生产代码调用链 + 持久化 schema |
| 3 | **Candidate 被 DecisionBridge 输入侧消费** | grep DecisionBridge / TaskDAG 输入解析 → 确认 Candidate 对象被读取、参与 Policy validation，而非仅进 Prompt 文本 | DecisionBridge 有 Candidate 消费接口（`DecisionBridge.consume(candidate)` 或字段注入 `task_dag.py` 策略构造），非 LLM 自解 | DecisionBridge 输入侧代码片段 + trace 日志 |
| 4 | **消费行为造成稳定可测差异（C vs D）** | 同 Phase 3 A/B/C/D 协议（temperature=0、节流、沙盒执行器），N≥10/组 | D 读取执行率 ≥ C+2（或身份遵循率 ≥ 6/10），且差异在扩大 N（≥20）后仍显著 | A/B/C/D 实验 JSONL + 统计检验 |

**闸门语义**：5 项全 AND 通过 → 触发 Phase 4 Candidate 设计；任一未通过 → 维持 ⏸ NOT TRIGGERED。第 0 项为前置，未定量前不进入 1-4 检查。

设计形态（Candidate ≠ 权限，触发后才进入）：Candidate 最多提供 `preferred_action / avoid_action / procedure / constraint_candidate / confidence / provenance / applicability`，最终由 DecisionBridge 裁决；**Behavior Policy Candidate 永远不能成为 Mutation Authority**。

**Phase 5 · Runtime 实现 ⛔ FORBIDDEN（当前）**
遵循 `Candidate → DecisionBridge → Policy validation → Decision`。禁止：Learning 直接改变 AgentRuntime；Learning 修改权限；Learning 绕过 DecisionBridge 直达 Action（违反已冻结的 I-4 / I-6 边界）。

## 6. 最终冻结状态（总表）

| 项目 | 最终状态 |
|---|---|
| P1 | ✅ FROZEN |
| P2 A/B/C | ✅ PASS |
| P3 A/B/C/D | ✅ PASS |
| C Behavioral Delta | ✅ PROVEN |
| B Action Suppression | ⚠️ REPRODUCIBLE SIDE-EFFECT |
| D Candidate Identity | ❌ NO INDEPENDENT INCREMENT |
| BehaviorPolicy | ❌ NOT CREATED |
| DecisionBridge | 🔒 NO CHANGE |
| AgentRuntime | 🔒 NO CHANGE |
| Legacy Cognitive Loop | 🔒 OFF |
| LearningEngine | 🔒 CURRENT RE-HOST |
| Phase 4 Candidate Design | ⏸ NOT TRIGGERED |
| Runtime Modification | ⛔ FORBIDDEN |

**结论**：不是把 Learning 升级成 BehaviorPolicy，而是确认"经验以什么表达形式进入 Context"本身就足以产生 Behavioral Delta。当前证据支持 **C 类 Executable Procedure**，否定立即增加 Candidate Identity / Policy Runtime 层的必要性。
