# OCOS 自主生命化升级 — 落地方案 v1.0

> **日期**: 2026-09-09
> **性质**: 执行级落地方案（Step-by-Step），不是架构蓝图
> **上游**: `docs/BLUEPRINT_AGI_UPGRADE_v1.1.md`（架构裁决）+ Coze 报告《OCOS 自主生命化升级方案 v1.0》
> **前置约束**: 本方案每个 Step 独立可验收，每步结束后必须 pytest 全量零回归才能进入下一步

---

## 0. 进度总览

```
阶段        报告内容摘要                          我们完成度    本方案 Step
─────────────────────────────────────────────────────────────────────
P0 地基     诚实化 + condition 字段修复             ✅ 已完成     —
P1 宪法     宪法修正案 + GoalGenesis 提案引擎       ❌ 未做       Step 1
P2 学习闭环  Lesson 注入决策 + 行为对照              ✅ 已完成     —
P3 知识库   KB 自维护 + UnifiedIngestor + Graph     ✅ 已完成     —
P4 自治度   4 级自治阶梯 + 人类刹车 + 权限分级       ❌ 未做       Step 2
P5 自进化   GrowthOptimizer → 进化管线 + 影子验证    🟡 半完成     Step 3
治理层 5-6  风险与缓解 + 审计日志增强                ❌ 未做       Step 4
治理层 7-8  指标看板 + 快速行动项                    🟡 部分做了   Step 5
端到端验收   跑通完整 cycle + 产出证据               ❌ 未做       Step 6
```

**每步产出独立 commit，每步不提前改后续代码。**

---

## 1. Step 1 — P1 宪法修正案 + GoalGenesis 提案引擎

### 1.1 背景

报告正确指出：

> 现行 `ocos/decision/decision_types.py` Goal source 闭集枚举只有 `HUMAN / DECOMPOSED` — Agent 不能凭空创建 Goal。要实现"独立产生目标"，必须先走宪法修正案，而不是偷偷绕过。

我们当前的做法：EpistemicDrive → motivation 直接生成 SELF goal。这是合法入口（不走 HUMAN/DECOMPOSED），但**缺少**报告要求的：
- GoalProposal 中间层（提案 → 审批 → goal 创建）
- 价值评分 + 风险评估（分级批准通道）
- 可审计记录（每个 goal 可追溯 proposal_id + approval_path）

### 1.2 改动清单

#### 1.2.1 DecisionSource 枚举扩展

| 项 | 内容 |
|----|------|
| **文件** | `ocos/decision/decision_types.py` |
| **改动** | DecisionSource 枚举新增 `SELF_PROPOSED` 值 |
| **约束** | 不破坏现有 `HUMAN / DECOMPOSED` 的所有引用；pytest 零回归 |
| **验证** | `grep -rn "DecisionSource\." ocos/` 确认现有所有引用的枚举值仍存在 |

#### 1.2.2 GoalProposal 数据模型

| 项 | 内容 |
|----|------|
| **新建** | `ocos/motivation/goal_genesis.py` |
| **内容** | `GoalProposal` dataclass + `GoalGenesis` 引擎类 |

GoalProposal 结构：
```
GoalProposal
├── proposal_id: str           # "PROP-{hash(description)[:8]}"
├── description: str            # 要做什么（自然语言）
├── domain: str                 # 所属 domain（用于聚类）
├── source: str                 # "epistemic_growth" / "epistemic_explore" / "failure_cluster"
├── value_score: float          # 价值评分 [0.0, 1.0]
│                                # EpistemicDrive 不确定性越高 → score 越高
│                                # 历史同类 goal 成功率越高 → score 越高
├── risk_level: str             # "LOW" / "MEDIUM" / "HIGH"
│                                # LOW = 不涉及权限，纯 self-reflection
│                                # MEDIUM = 涉及搜索/调研但不改代码
│                                # HIGH = 涉及 SelfModification / 文件写操作
├── required_resources: list    # 所需资源（agent 类型/工具）
├── status: str                 # "PENDING" / "APPROVED" / "REJECTED" / "COMPLETED"
├── approval_path: str          # "auto" / "requested" / "rejected"
├── approved_at: Optional[datetime]
├── created_at: datetime
└── metadata: dict              # 扩展字段
```

#### 1.2.3 GoalGenesis 引擎

```python
class GoalGenesis:
    """GoalProposal 生成 + 分级批准."""

    def produce(self, trigger_suggestions: list[str]) -> list[GoalProposal]:
        """从 EpistemicDrive suggestions 生成 GoalProposal 列表."""

    def score_value(self, proposal: GoalProposal) -> float:
        """价值评分 = f(不确定性, 历史成功率, domain 重要性)."""

    def assess_risk(self, proposal: GoalProposal) -> str:
        """风险评估 = g(required_resources, 是否涉及文件写, 是否涉及 SelfModification)."""

    def approve(self, proposal: GoalProposal) -> GoalProposal:
        """分级批准通道:
        - LOW risk → 自动批准 (approval_path="auto")
        - MEDIUM risk → 自动批准但记录 (approval_path="auto") + logger.info
        - HIGH risk → 拒绝 (approval_path="rejected") 写入审计日志
        """

    def to_goal(self, proposal: GoalProposal) -> Optional[Goal]:
        """proposal → Goal (origin_level=SELF, source=SELF_PROPOSED)."""
```

#### 1.2.4 motivation.py 接入 GoalGenesis

| 项 | 内容 |
|----|------|
| **文件** | `ocos/daemon/motivation.py` |
| **改动** | EpistemicDrive.suggest_*() 不再直接调 goal.create，而是：<br>① GoalGenesis.produce(suggestions) → proposals<br>② GoalGenesis.approve(proposal) → 分级批准<br>③ GoalGenesis.to_goal(proposal) → Goal 创建<br>④ 写入 DB goal_proposal 审计表 |
| **约束** | 现有 29 个 SELF goal 路径不受影响（新 goal 走提案通道，旧 goal 保持原有路径） |

#### 1.2.5 goal_proposal 审计表

| 项 | 内容 |
|----|------|
| **位置** | `~/.ocos/ocos.db` |
| **Schema** | `CREATE TABLE goal_proposal (proposal_id, description, domain, source, value_score, risk_level, status, approval_path, approved_at, created_at, metadata_json)` |
| **写入时机** | GoalGenesis.approve() 时 INSERT；status 更新时 UPDATE |
| **DB 迁移** | 首次运行时自动 CREATE TABLE（SemanticStore.initialize() 已有模式） |

### 1.3 验收标准（必须全部满足）

- [ ] DecisionSource 枚举新增 SELF_PROPOSED，HUMAN/DECOMPOSED 所有现有引用正常
- [ ] pytest 全量零回归
- [ ] GoalGenesis.produce() 能产出 GoalProposal（含 proposal_id / value_score / risk_level）
- [ ] GoalGenesis.approve() 分级逻辑正确：
  - LOW → status=APPROVED, approval_path="auto"
  - MEDIUM → status=APPROVED, approval_path="auto"
  - HIGH → status=REJECTED, approval_path="rejected"
- [ ] motivation 通过 GoalGenesis → 新 goal 能自动创建
- [ ] DB goal_proposal 表有记录，每个 proposal 可追溯
- [ ] 手动模拟 HIGH risk proposal → 被拒绝 → 审计日志可查

---

## 2. Step 2 — P4 自治度阶梯 + 人类刹车

### 2.1 背景

报告说：

> 自治不是"开关"，是阶梯。每级有明确的能力边界、权限范围和刹车。最低级（Level 0）是"只监听不行动"，最高级（Level 3）是"自主规划+执行+自进化，但可随时一键切回"。

当前 OCOS 的 autonomy_level 只有 `ask` 和 `auto` 两档——太粗了。

### 2.2 改动清单

#### 2.2.1 自治度 4 级阶梯定义

| Level | 名称 | 能力边界 | 权限范围 | 刹车 |
|-------|------|----------|----------|------|
| **L0** | 观察模式 | 只感知、记录、学习，不创建任何 goal | 只读 episode/belief/pattern | 无行动 → 零风险 |
| **L1** | 学习模式 | L0 + dream 巩固 + EpistemicDrive 生成 proposal（但不自动批准） | 只读 + goal_proposal 写 | proposal 必须 L2+ 才能批准 |
| **L2** | 自主执行 | L1 + LOW/MEDIUM risk 提案自动批准 + goal 执行 | 读 + 写 goal + 执行 agent | HIGH risk 永远拒绝 |
| **L3** | 自进化模式 | L2 + GrowthOptimizer + SelfModification + 影子验证 | 全部 + 代码写权限 | 影子验证不通过自动回滚 |

#### 2.2.2 代码改动

| 文件 | 改动 |
|------|------|
| `ocos/agent/agent_self_model.py` | autonomy_level 从 `str` 改为 `AutonomyLevel(IntEnum)`，0-3 四档 |
| `ocos/daemon/motivation.py` | L0→不调 EpistemicDrive.approve；L1→只 produce 不 approve；L2→LOW/MEDIUM auto；L3→全允许 |
| `ocos/agent/wisdom_trigger.py` | L0→不跑 dream consolidate；L1+→正常跑 |
| `ocos/growth/engine.py` | L0-L2→GrowthOptimizer 不触发 apply；L3→允许 apply + 影子验证 |
| CLI | `ocos autonomy set L1` / `ocos autonomy status` — 人类可控切换 |

#### 2.2.3 人类刹车

| 机制 | 实现 |
|------|------|
| **一键降级** | CLI `ocos autonomy set L0` → 立即停止所有 SELF goal + 禁止新 proposal 批准 |
| **审批队列表** | MEDIUM risk proposal 可以标记 "request_human_review" → 等人类 approve |
| **审计日志** | 每次 autonomy_level 切换 → 写 audit 表 |
| **超时熔断** | SELF goal 执行超过 goal_timeout → 自动 cancel + 降级到 L0 |

### 2.3 验收标准

- [ ] autonomy_level 支持 4 档 (L0-L3)，每档边界清晰
- [ ] L0 模式下 daemon 不执行任何 agent，只积累 episode
- [ ] L1 模式下 EpistemicDrive 生成 proposal 但不批准
- [ ] L2 模式下 LOW/MEDIUM 自动批准，HIGH 拒绝
- [ ] L3 模式下 GrowthOptimizer 能 apply（但必须过影子验证）
- [ ] CLI 能 set/status，能一键切回 L0
- [ ] 审计日志可追溯 autonomy_level 每次变化
- [ ] pytest 全量零回归

---

## 3. Step 3 — P5 自进化闭环

### 3.1 背景

报告说：

> evolution 为模拟桩，无真实自改进。需要分层自进化 + 影子验证 + 回滚。

我们已有：
- GrowthOptimizer（scale guard 双轨护栏 + 自动 pytest 回归）
- SelfModificationAgent（审批 gate）
- 但 **GrowthOptimizer 是手动调用的，没接到自动进化管线**

### 3.2 改动清单

#### 3.2.1 自进化触发管线

```
GrowthOptimizer 当前路径 (手动):
  GrowthAnalyzer.analyze(code_change) → GrowthOptimizer.apply() → pytest

自进化路径 (自动):
  EpistemicDrive 发现 "知识/代码 缺口"
    → daemon tick 检测到 "连续 N 个同类 goal 失败"
      → 生成 GrowthProposal (含目标代码路径 + 拟改动)
        → 影子验证 (复制代码到 tmp_dir → apply → pytest)
          → 通过 → commit + 切换到新代码
          → 失败 → 回滚，保留影子验证失败日志
```

#### 3.2.2 改动范围

| 文件 | 改动 |
|------|------|
| `ocos/growth/evolution_loop.py` | **新建** 自进化管线编排器 |
| `ocos/growth/shadow_verifier.py` | **新建** 影子验证器（tmp_dir 沙箱隔离） |
| `ocos/daemon/__init__.py` | dream 之后 + L3 自治 → 触发 evolution_loop.tick() |
| `ocos/growth/engine.py` | GrowthOptimizer 加 `apply_in_sandbox()` 方法 |

#### 3.2.3 安全护栏（必须全部满足才能自动 apply）

```
GrowthOptimizer 自动 apply 护栏:
① autonomy_level == L3                     # 自治度足够
② shadow_verifier.pass()                    # 影子验证通过
③ scale_guard 通过 (绝对50行 OR 比例15% OR 保留≥50%)
④ pytest 零回归                             # 全量 pytest
⑤ 改动文件数 ≤ 5                            # 范围限制
⑥ 不碰宪法/权限/身份相关文件                # 红线文件
⑦ 回滚快照已创建                            # 可回滚
```

### 3.3 验收标准

- [ ] evolution_loop.tick() 能被 daemon 触发（仅 L3）
- [ ] shadow_verifier 在 tmp_dir 复制完整项目 → apply → pytest
- [ ] 护栏 ①-⑦ 全部满足才能自动 commit
- [ ] 护栏任何一条不满足 → 回滚 + 记录日志
- [ ] 人类可通过 CLI `ocos evolution status` 看当前进化状态
- [ ] pytest 全量零回归（初始 apply 不应该触发，因为还没有"连续 N 个同类 goal 失败"）

---

## 4. Step 4 — 治理层 5-6：风险与缓解 + 审计增强

### 4.1 改动清单

| 子项 | 内容 | 代码落点 |
|------|------|----------|
| 4.1 | **风险注册表** — 已知风险 + 缓解措施 + 触发阈值 | `ocos/governance/risk_registry.py` 新建 |
| 4.2 | **审计日志增强** — 每次 autonomy_level 变化 / GoalProposal 批准 / GrowthOptimizer apply 全记录 | 接入现有 `ocos/governance/audit_engine.py` |
| 4.3 | **红线文件守护** — 宪法/权限/决策类型等文件被标记为 UNTOUCHABLE | GovernanceEngine 加白名单 |
| 4.4 | **熔断机制** — L3 自治下连续 3 次 GrowthOptimizer apply 失败 → 自动降级到 L2 | daemon tick 检测 |

### 4.2 验收标准

- [ ] risk_registry.py 有结构化风险列表（已知触发条件 + 缓解措施）
- [ ] 每个 L3 自治下的 GrowthOptimizer apply → 审计日志可追溯
- [ ] 红线文件列表存在，GrowthOptimizer 不会改它们
- [ ] 熔断机制在连续 apply 失败后自动降级
- [ ] pytest 全量零回归

---

## 5. Step 5 — 治理层 7-8：指标看板 + 快速行动项

### 5.1 指标看板

北极星指标从报告来，必须可观测：

| 指标 | 目标值 | 实现方式 |
|------|--------|----------|
| 越权事件数 | = 0 | audit_engine 实时计数 → Prometheus 端点 |
| 无人干预时段目标完成率 | ≥ 70% | goal 表 + autonomy_level 时间戳 → 每小时统计 |
| 同类任务重复犯错率 | ↓ 50% | episodes + pattern → 新旧成功率对比 |
| GoalProposal 批准率 | ≥ 50% | goal_proposal 表 status 分布 |
| GrowthOptimizer apply 成功率 | ≥ 80% | 审计日志 |

**实现方式**: 复用 OCOS 已有的 Prometheus 端点（docs 目录 Y 阶段），加 5 个新 gauge。

### 5.2 快速行动项

报告说"本周就动手的 5 件事"——但我们已经做完了 P0/P2/P3，所以改为**本方案就动手的事**：

| # | 内容 | 对应 Step |
|---|------|-----------|
| 1 | DecisionSource 加 SELF_PROPOSED | Step 1 |
| 2 | GoalGenesis 引擎 + goal_proposal 表 | Step 1 |
| 3 | autonomy_level 4 级阶梯 | Step 2 |
| 4 | GrowthOptimizer sandbox + 影子验证 | Step 3 |
| 5 | 审计日志增强 + 熔断机制 | Step 4 |

---

## 6. Step 6 — 端到端验收

### 6.1 验收场景

在 daemon 正常运行 24 小时后，检查：

```
完整 cycle:
  daemon tick
    → EpistemicDrive.suggest_growth() → [suggestions]
    → GoalGenesis.produce() → [GoalProposal]
    → GoalGenesis.approve() → LOW risk auto-approved
    → GoalGenesis.to_goal() → Goal (origin_level=SELF, source=SELF_PROPOSED)
    → agent 执行 goal → episodes (condition="agent=X, success=Y")
    → dream consolidate → belief + pattern + wisdom + knowledge (4层沉淀)
    → daemon._ingest_experience → UnifiedIngestor → SemanticStore
    → daemon._epistemic_research → WebResearcher → UnifiedIngestor
    → think() premises 注入 wisdom + belief + knowledge → 决策改变 ✅
    → 如果 autonomy_level=L3 → evolution_loop.tick() → 影子验证

验收 checklist:
  ☐ goal_proposal 表有 ≥ 5 条记录（daemon 正常运行后自动产出）
  ☐ DB knowledge 表 ≥ 20 行（dream consolidate + UnifiedIngestor 沉淀）
  ☐ belief statement 是语义化的（"XXX.execute 类任务通常成功 N/M"）
  ☐ wisdom label 是语义化的（"「XXX.execute」类任务成功率高 — N 次观察"）
  ☐ pattern 表 ≥ 30 行（condition=agent=X 格式，无 tick@N）
  ☐ autonomy_level 默认 L2（自主执行）
  ☐ 北极星指标看板有实时数据
  ☐ 越权事件数 = 0
  ☐ pytest 全量零回归
```

---

## 7. 约束与风险

| 约束 | 处理 |
|------|------|
| **不破坏现有 4366+ tests** | 每步后 pytest 全量；改动只加不删（加枚举值、加新方法、加新表） |
| **宪法红线不可碰** | DecisionSource 扩展是最小化改动（只加 SELF_PROPOSED）；不改 HUMAN/DECOMPOSED |
| **GrowthOptimizer 自动 apply 安全** | 必须 L3 + 影子验证 + 护栏 ①-⑦ + 回滚快照 + 熔断 |
| **上下文断片** | 每步独立 commit + 独立验收 + 不提前改后续代码 |
| **未知依赖问题** | 每步 edit 前先 grep 全仓库确认引用路径；edit 后立即 pytest |

---

## 8. 时间线估算

```
Step 1 (P1 宪法):        4-6 小时  (DecisionSource + GoalGenesis + motivation 接入 + goal_proposal 表)
Step 2 (P4 自治度):      3-5 小时  (4 级阶梯 + CLI 切换 + 刹车机制)
Step 3 (P5 自进化):      5-8 小时  (evolution_loop + shadow_verifier + 护栏 ①-⑦)
Step 4 (治理层):          3-4 小时  (risk_registry + 审计增强 + 熔断)
Step 5 (指标看板):        2-3 小时  (Prometheus gauge + 指标计算)
Step 6 (端到端验收):      24 小时  (daemon 运行 + 数据积累 + 验收 checklist)
─────────────────────────────────────
总计                      ~2-3 天
```

---

## 9. 本方案未覆盖（留后续）

- **P2-4/7 治理层细节**（自治度阶梯的完整治理协议）
- **LLM 引入 belief/wisdom 语义摘要**（冻结令评估）
- **KnowledgeOntology 实装**（实体类型/关系类型约束）
- **多渠道自动调度的完整联动**（WebResearcher/LLMTutor 完全自动化）
- **非 agent_runtime 路径的 condition 格式修复**（conversation_reply / boot_awareness / self_check）

---

## 附录 A: 关键 commit 记录（本轮已做）

| commit | 内容 |
|--------|------|
| `c8037d4` | 学习管线根因级修复 + 多渠道外部学习 |
| `5cc055d` | Phase S2 三层知识层（SemanticStore + Registry + Graph） |
| `4f884b8` | P0+P1 消费闭环（knowledge_context + daemon 自动 ingest/research） |
| `e76a2c5` | P2 质量提升（belief/wisdom 语义化 + Graph persist/load + working_memory） |

## 附录 B: 当前 pytest baseline

```
pytest --deselect ocos/tests/test_import_rules.py
  → 4366-4367 passed (baseline, 允许 ≤2 failed 为 LLM key 配置导致的 test_say_channel 回归)
```
