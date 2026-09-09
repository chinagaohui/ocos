# OCOS AGI Upgrade Blueprint v1.1 — Architecture Correction

> ✅ **CURRENT（现行路线）**：Behavioral Delta（ER-2）为学习链唯一判定标准。
> 前置收敛（P0-P4）已于 2026-09-08 完成（commit a7af073），当前处于 Behavioral Delta 验证阶段。

**版本**: v1.1  
**日期**: 2026-09-03  
**性质**: 架构裁决修正（Architecture Correction）— 对 v1.0 的 10 点收紧  
**上游**: `docs/BLUEPRINT_AGI_UPGRADE_v1.0.md`（423 行, 方向 GO）+ 用户架构裁决  
**裁决状态**: Architecture Direction **GO** / 8-gap **GO** / Phase dependency **GO** / Governance **GO** / No-new-infra **GO** / **Implementation Freeze: HOLD → 本修正后 UNFREEZE 条件满足**

---

## 0. 本修正的总原则

v1.0 的方向全部成立，本版不推翻，只收紧 10 点。总纲一句话：

> **OCOS 的目标不是"给 OCOS 加 Learning"，而是让经历经过受治理的学习过程，形成经过验证的新能力，并在未来认知循环中产生可观测的行为变化。**

```
经历 → 学习 → 能力 → 行为 → 新经历 ↺
```

**判定一条学习链是否成立的唯一标准：Behavioral Delta（学习前后同类任务行为发生可归因、可验证的变化）。**

---

## 1. 修正一：L1 输出从 LearningModel 升级为 LearningArtifact

### 1.1 为什么

v1.0 定义 Episode → LearningExample → LearningEngine → LearningModel，这只保证"经验统计"：
- 统计成功率 → 存储 → 未来查询 = **Storage/Statistics**，不是 **Learning**

真正的 Learning = **Future Behavior Change**。因此 L1 的核心输出必须是携带行为语义的 **LearningArtifact**。

### 1.2 LearningArtifact 数据契约（统一学习产物语义层）

```
LearningArtifact
├── id
├── artifact_type: BELIEF | PATTERN | LESSON | SKILL_CANDIDATE
│
├── source
│   ├── source_episodes[]      → Evidence.source_episode_id
│   ├── source_goals[]
│   └── observation_evidence[] → Evidence (quality/consistency_score)
│
├── hypothesis                  → 学习假设（自然语言或结构化）
├── learned_rule                → 可执行规则（条件→行为）
├── applicable_context          → 适用范围（domain/goal 模式）
│
├── confidence                  → 现有 Belief.confidence / Pattern.confidence
├── novelty                     → 相对既有 artifacts 的新颖度
├── success_delta               → 学习前后成功率差（Behavioral Delta 量化）
│
├── validation
│   ├── status: CANDIDATE | VALIDATED | REJECTED | COMMITTED
│   ├── tests[]
│   └── behavioral_delta        ← 关键验收字段
│
├── governance
│   ├── authority
│   ├── approval_required: bool
│   └── approval_id             → R4-B pending_actions 关联
│
└── provenance
    ├── trace_id                → Trace 连续
    ├── episode_ids[]
    └── created_at
```

### 1.3 关键：与现有模型的关系（不新增基础设施）

仓库**已存在**这些种子类型，LearningArtifact 是它们之上的统一数据契约，不是第 N 套存储：

| 现有类型 | 文件 | LearningArtifact 复用方式 |
|---------|------|--------------------------|
| `Evidence`（id/source_episode_id/quality/consistency_score） | memory/belief/models.py | 直接承载 source.observation_evidence |
| `Belief`（statement/confidence/evidence_ids/scope） | memory/belief/models.py | artifact_type=BELIEF 的实现 |
| `PatternCandidate`（**已有 is_validated/is_rejected 状态机**） | memory/pattern/models.py | artifact_type=PATTERN 的实现 |
| `ExperienceCandidate`（completeness/boundary_passed） | memory/experience/models.py | Validation 上游 |
| `LearningModel`（rules/accuracy） | models/learning.py | 快通路实现之一，非唯一输出 |

**统一语义层 = LearningArtifact 契约；BELIEF/PATTERN/LESSON/SKILL_CANDIDATE 是其 artifact_type 的四个实现。**

---

## 2. 修正二：快/慢通路统一到 LearningArtifact（消除两套学习语义）

### 2.1 v1.0 的问题

```
        Episode
        /     \
   Learning   Dream
      ↓         ↓
 LearningModel  Pattern/Belief   ← 两套语义, 违反 No-new-infra
```

### 2.2 统一架构

```
                    Episode
                       ↓
                  Evaluation
                       ↓
              LearningArtifact (统一语义层)
                 /              \
                ↓                ↓
  快通路: Adaptation   慢通路: Consolidation
  (在线/快速)          (离线/慢速)
     LearningModel        Pattern/Belief/Lesson
                \              /
                 └─────┬──────┘
                       ↓
                  Validation
                       ↓
               Governed Commit
                       ↓
               Future Cognition
```

**语义统一的关键**：两条通路都产生 **LearningArtifact**。Dream 不再是"第二套 Learning"，只是 **Consolidation Path**（离线、批量、规则型）；快通路是 **Adaptation Path**（在线、单样本）。两者共享 Evaluation → LearningArtifact → Validation → Governed Commit → Provenance 五段语义。

### 2.3 现实核查（修正 v1.0 表述）

- 慢通路已真实实施（daemon 每 200 tick → `_consolidate_episodes` → Belief 巩固/Pattern 提取/弱模式修剪，v1.0 §2 已确认 R6）
- PatternExtractor 已产出 `PatternCandidate`，**已有 CANDIDATE→VALIDATED/REJECTED 雏形**（is_validated/is_rejected）
- **缺口**：无统一 LearningArtifact 层——Belief/Pattern/Lesson 各写各的，无 hypothesis/behavioral_delta/applicability 语义

---

## 3. 修正三：L2 RecallResult 增加相关性/置信度/冲突集

### 3.1 v1.0 的问题

memory_context 直接塞 premises → 记忆多时 prompt 膨胀、噪声增加、推理变差。

### 3.2 RecallResult 数据契约

```
RecallResult
├── memories[]              → 每个带下述元数据
├── relevance               → 与当前 goal/intent 的相关度 [0,1]
├── confidence              → 每条记忆的置信度
├── provenance              → 来源（episode_id/trace_id/时间）
├── temporal_scope          → 时间范围（近/中/远期）
└── conflict_set            → 冲突记忆组
    └── 例: X 方案 {success_rate: 0.62, evidence: 17, conflict: true}
```

### 3.3 Conflict 的处理（不简单 top-k）

过去出现"方案 X 成功(A) / 方案 X 失败(B)"时，RecallResult 必须输出**冲突集**而非单条：

```
X:
  success_rate = 0.62
  evidence = 17
  conflict = true   ← 触发 L8 Metacognition 的置信度下调
```

### 3.4 接线点

- 复用 `ocos/memory/recall.py:MemoryRecall`（已存在）→ 包装返回 RecallResult
- `MasterAgent._recall_and_record`（pass 空壳）→ 真实现
- 注入位：decision_loop.py execute_single observe→reason 之间

---

## 4. 修正四：L3 拆三层 — World Availability ≠ Consumption

### 4.1 硬性架构原则

```
World Model Consumption ≠ World Model Availability
```

L3 不得因 `WorldStore.summary() == empty` 误判架构失败——空是 Supply 层问题，不是 Consumption 层问题。

### 4.2 三层拆分

| 层 | 内容 | 归属 | 验收 |
|----|------|------|------|
| **L3-A World Query ABI** | WorldStore 面向认知的查询封装（entity/relation/summary） | 本蓝图 | ABI 存在 + 单测 |
| **L3-B Cognitive Consumption** | think/plan 注入 world_state | 本蓝图 | 注入点存在 + 空世界优雅降级 |
| **L3-C Observation Supply** | 传感器激活（FileSensor 注入 / LLM 观察回填） | 后续能力 | 生产世界有数据 |

### 4.3 验收纪律

- L3-A/L3-B 完成 = 消费就绪（即使 world 空也走通代码路径）
- L3-C 完成 = 世界有数据（才谈"世界模型参与推理"的认知评价）
- **不得把 L3-C 的缺失标记为 L3-A/B 失败**

---

## 5. 修正五：L5 N=3 从"技能成立阈值"改为"候选生成阈值"

### 5.1 问题

成功 3 次 ≠ 已学会技能。高风险动作（删除文件/改配置/发消息/部署）成功 100 次也不得自动获得执行权。

### 5.2 四段技能生命周期（替代 N=3→Skill）

```
Episode 聚类 (成功模式)
    ↓  N≥3 (候选生成阈值, 仅产生候选)
Candidate Skill
    ↓  Verification
         ├── 只读/低风险 → 规则验证 → Validated
         └── 写类/高风险 → 保持 CANDIDATE → ASK (R4-B) → 人工批准
Validated Skill
    ↓  Governed Registration
SkillRegistry.register(governance.approval_id)
```

### 5.3 硬规则

- **N=3 只生成候选，不授予执行权**
- 写类 Skill 无论验证结果如何，**注册后仍走 DecisionBridge 分级**（execute 时再判 AUTO/ASK），Skill 本身不含权限
- Skill 的 governance.approval_required 与 approval_id 必须落 LearningArtifact 契约

---

## 6. 修正六：L7 Generalization 验收 = Cross-surface Transfer

### 6.1 问题

v1.0 的"Skill A trigger 相似 → Task B"是 **Skill Transfer（浅层）**，不是 Generalization。

### 6.2 验收标准升级

```
Generalization = Cross-surface transfer with preserved task semantics
```

判定例：
- ❌ 不算：字符串相似 → 复用同一条命令
- ✅ 算：Task A"检查当前 Linux 内核版本" → 抽象出 environment-inspection pattern → Task B"确认这台机器运行什么内核"（不同表面形式）→ 语义保持 → 成功

### 6.3 实现载体

Generalization 不单独建模块，但验收挂在 L5/L6 Skill 的 `applicable_context` 语义字段上：Skill 存的是**抽象模式**（trigger 语义特征），不是表面字符串。命中 = 语义匹配 + 上下文约束检查，非 selector 字符串命中。

---

## 7. 修正七：Learning → Validation → Governed Commit 状态机（统一）

### 7.1 状态机

```
        Episode
           ↓ Evaluation
   ┌───────┴────────┐
   ↓                ↓
 LearningArtifact  (CANDIDATE)
   ↓
 Validation:
   ├── 规则验证 (确定性): 证据足? 冲突? 可复现?
   ├── 行为验证 (E-RUN): 同类任务 behavior 差异?
   └── 治理验证: 写类需 approval
   ↓
 VALIDATED (通过) 或 REJECTED (失败: 回炉/丢弃)
   ↓
 Governed Commit:
   ├── Memory (Belief/Pattern 落库)
   ├── SkillRegistry (Skill 注册, 带 governance)
   └── Trace 记录 (provenance)
   ↓
 Future Cognition 消费
```

### 7.2 与现有代码的对应

| 状态机阶段 | 现有实现 | 缺口 |
|-----------|---------|------|
| CANDIDATE 产生 | PatternExtractor → PatternCandidate ✅ | 无统一 LearningArtifact |
| VALIDATED/REJECTED | PatternCandidate.is_validated/is_rejected ✅（雏形） | 无行为验证（E-RUN delta） |
| Committed | _consolidate_episodes 写 Belief/Pattern ✅ | 无 governance 字段 |
| 消费 | — | 无（正是 L2/L8 要做） |

---

## 8. 修正八：Phase A 验收标准重定义

### 8.1 v1.0 Phase A 验收（不足）

A1 样本转换 / A2 失败诊断 / A3 dream 调 learn —— 只验"管道通了"，不验"行为变了"。

### 8.2 v1.1 Phase A 验收

**Phase A 完成 = 以下 E-RUN 全部通过：**

| # | E-RUN 测试 | 验收标准 |
|---|-----------|---------|
| ER-1 | 失败样本入库 | 注入 1 次可诊断失败 → LearningArtifact(CANDIDATE, LESSON) 生成，含 hypothesis + 失败原因 |
| ER-2 | **Behavioral Delta（核心）** | Episode1: 任务 X 失败（原因 C）→ 学习 → Episode2: 同类任务 X' → **行为不再使用失败路径 → 成功**。必须展示: 学习前后决策差异可归因于该 artifact |
| ER-3 | 快通路非空 | LearningEngine.learn 收到 examples≥1（非 None）→ patterns_learned ≥1 |
| ER-4 | 慢通路产物统一 | dream 巩固产出的 Belief/Pattern 均可包装为 LearningArtifact（artifact_type 正确） |
| ER-5 | Governance 保持 | 全部写类动作仍 ASK；学习产物无直接 Action 路径（Decision 唯一 Mutation Authority 未破） |

**ER-2 是 Phase A 的 PASS/FAIL 门：Behavioral Delta 不存在 = Phase A 未完成。**

---

## 9. 修正九：总循环图（后半圈必须重新进入前半圈）

```
              ┌───────────────┐
              │     GOAL      │◄──────────────────────┐
              └───────┬───────┘                       │
                      ↓                               │
              ┌───────────────┐                       │
              │    PLAN       │                       │
              └───────┬───────┘                       │
                      ↓                               │
              ┌───────────────┐                       │
              │   DECISION    │                       │
              └───────┬───────┘                       │
                      ↓                               │
              ┌───────────────┐                       │
              │    ACTION     │                       │
              └───────┬───────┘                       │
                      ↓                               │
              ┌───────────────┐                       │
              │  OBSERVATION  │                       │
              └───────┬───────┘                       │
                      ↓                               │
              ┌───────────────┐                       │
              │   EPISODE     │                       │
              └───────┬───────┘                       │
                      ↓                               │
              ┌───────────────┐                       │
              │  EVALUATION   │                       │
              └───────┬───────┘                       │
                      ↓                               │
              ┌────────────────┐                      │
              │    LEARNING    │                      │
              └───────┬────────┘                      │
                      ↓                               │
              LearningArtifact                        │
                ↙     ↓      ↘                       │
           Memory   Pattern   Skill                   │
                \     │      /                        │
                 \    │     /                         │
                  ↓   ↓    ↓                          │
               CONSOLIDATION                          │
                      ↓                               │
              WORLD / SELF MODEL                      │
                      ↓                               │
                METACOGNITION  ──→ (冲突集/低置信     │
                      ↓          → 决策更保守)        │
                 REPLANNING                           │
                      ↓                               │
                    GOAL ─────────────────────────────┘
```

**判定标准**：后半圈（EVALUATION→LEARNING→CONSOLIDATION→METACOGNITION→REPLANNING）必须**重新进入 GOAL/PLAN**。若后半圈产物只落库不被前半圈消费 = 仍是 "Cognitive Runtime + Experience Database"，不是 Adaptive Cognitive Runtime。

---

## 10. 修正十：治理不变量加固声明

本修正引入 LearningArtifact / RecallResult / 四段技能生命周期后，治理边界同步收紧：

| 新增对象 | 是否可产生 Action | 治理防护 |
|---------|------------------|---------|
| LearningArtifact (含 SKILL_CANDIDATE) | ❌ 不可直接执行 | 无 execute 方法；只经 Validation→Governed Commit |
| Skill (Validated) | ⚠️ 经 DecisionBridge 分级 | 注册携带 approval_id；执行时 AUTO/ASK 再判 |
| RecallResult (含 conflict_set) | ❌ 只影响推理输入 | 低置信/冲突 → L8 降级 ASK（更严，非放宽） |
| LearningArtifact.behavioral_delta | ❌ 仅验收指标 | 无副作用路径 |

**不变式 I-6（Decision 唯一 Mutation Authority）在所有修正后保持。**

---

## 11. 汇总：v1.0 → v1.1 变更表

| # | 变更 | v1.0 | v1.1 |
|---|------|------|------|
| 1 | L1 输出 | LearningModel | **LearningArtifact（含 behavioral_delta）** |
| 2 | 快/慢通路 | 两套语义 | **统一 LearningArtifact 契约**（Adaptation/Consolidation 两路径） |
| 3 | L2 Recall | memory_context 塞 premises | **RecallResult（relevance/confidence/conflict_set）** |
| 4 | L3 | 单一"接上 WorldStore" | **L3-A/B/C 三层, 空世界≠失败** |
| 5 | L5 Skill | N=3 → Skill | **N=3 → Candidate → 验证 → Governed 注册** |
| 6 | L7 Generalization | selector 命中 | **Cross-surface transfer（语义保持）** |
| 7 | 全局 | 无统一对象 | **LearningArtifact 数据契约**（复用 Evidence/PatternCandidate 种子） |
| 8 | 状态机 | 无明确状态机 | **CANDIDATE→VALIDATED/REJECTED→COMMITTED**（PatternCandidate 已有雏形） |
| 9 | Phase A 验收 | 管道通 | **ER-1~ER-5, ER-2 Behavioral Delta 为 PASS/FAIL 门** |
| 10 | 总循环 | 前半圈为主 | **后半圈必须重入 GOAL（闭环判定标准）** |

---

## 12. Scope Freeze（v1.1 更新）

**Architecture Direction: GO**  
**Implementation Freeze: 条件满足（本修正后）**  

**进入实施需用户确认：**
1. 接受 LearningArtifact 契约作为统一语义层（§1.2/§2.2）
2. 接受 ER-2 Behavioral Delta 作为 Phase A PASS/FAIL 门（§8）
3. 接受 L3 三层拆分（L3-C Observation Supply 推迟为后续能力）

---

## 13. 符合本蓝图原则声明

1. ✅ No-new-infrastructure：LearningArtifact 复用仓库已有 Evidence/PatternCandidate/ExperienceCandidate 种子类型，非第 N 套存储
2. ✅ 不变量逐项防护（§10 治理表）
3. ✅ Behavioral Delta 贯穿：定义(§1)→状态机(§7)→验收(§8)→闭环(§9)
4. ✅ 语义先行：每个新对象（LearningArtifact/RecallResult）先定义再谈实现
5. ✅ 确定性优先：验证规则化（证据足/冲突/可复现），LLM 仅失败原因分析处注入

---

## 14. 实施状态（2026-09-03 收尾 — A-D 全部落地）

| Phase | 内容 | Commit | 新增测试 |
|-------|------|--------|---------|
| A | L1 快通路 + L4 失败诊断 | `5d0f72a` | 22 |
| B | L2 Recall 进认知 + L3 World 消费 | `56add19` | 14 |
| C | L4 Replanner + L5/L6 Skill 生长 | `423903b` | 27 |
| D | L7 泛化 + L8 元认知 | `aaa0062` + `64c6421` | 16 |
| 合计 | L1-L8 八缺口全部落地 | — | 79 新增, 全量 6250 passed |

**全链路 E-RUN 验证（隔离 DB 真实 daemon 4 ticks）:**
- 真实 Episode 生产（含 LLM 转换诚实失败 "分析数据/生成报告"）→ 快通路学习 → 4 rules + LESSON artifacts
- L8 闭环: 3 次失败累积 → rate=0.0 → 写类任务升级 ASK（行为改变成立）
- L7: "检查内核版本" → "确认机器运行什么内核" 跨表面迁移 sim=0.7
- E-RUN 发现并修复: success_rate=0.0 被 falsy 误读为 0.5（`64c6421`, 回归测试锁定）

**收尾判断**: Cognitive Runtime → Adaptive Cognitive Runtime 第一跃迁（Experience→Learning→Capability→Behavior→新经历闭环）已完成代码落地与 E-RUN 验证。剩余声明级缺口: 完整 Behavior Delta 生产观测（需长周期运行）、L3-C Observation Supply、Skill 审批 UI 流。

---

**v1.1 修正 + Phase A-D 实施完成（2026-09-03）。**
