# Phase 10 — Test Registry v1.0

> Status: **FROZEN ✅** — 测试编号已锁定，对应 contract 文档中的测试规约。
> 所有测试的目标：验证 Contract 中的约束是**可执行的**，不是装饰性的。

---

## T19 Skip Notes

T19 (`test_modify_result_does_not_affect_store`) 在 Phase 10 测试中被跳过。

```
SKIP REASON: In-memory Store → 返回对象引用 → 修改影响原对象
属于测试替身行为，不代表 Contract 违反。
PRODUCTION: SQLite / DB backend → deserialize → new object instance
天然满足隔离。
```

有关 T19 的集成级验证，参见 T42/T43（Gate 1 — Identity Preservation），
其验证的是接口层隔离而非具体实现细节。

---

## Registry Structure

|| Range | 模块 | 测试文件 | 数量 | 来源 |
||-------|------|---------|------|------|
|| T8–T13 | Data Contract Boundary | `tests/phase10/test_data_contract.py` | 6 | EXPERIENCE_DATA_CONTRACT.md |
|| T14–T20 | Store Contract Boundary | `tests/phase10/test_store_contract.py` | 7 | EXPERIENCE_STORE_CONTRACT.md |
|| T21–T25 | Store Physical / Provenance | `tests/phase10/test_store_contract.py` | 5 | EXPERIENCE_STORE_CONTRACT.md |
|| T26–T30 | Retrieval Pipeline Boundary | `tests/phase10/test_retrieval_contract.py` | 5 | RETRIEVAL_PIPELINE_CONTRACT.md |
|| T31–T35 | Calibration Engine Boundary | `tests/phase10/test_calibration_contract.py` | 5 | CALIBRATION_ENGINE_CONTRACT.md |
|| T36+ | Authority Intrusion Cross-Layer | `tests/phase10/test_authority_intrusion.py` | 5+ | ABI + 全部 contracts |
|| **T42–T58** | **Integration Gate** | `tests/phase10/test_integration_gate.py` | **17** | PHASE10_INTEGRATION_GATE.md |
|| **Total** | | | **~55** | |

---

## T8–T13: Data Contract Boundary Tests

| # | 名称 | Contract 来源 | ABI 映射 | 预期失败条件 |
|---|------|--------------|----------|-------------|
| T8 | ExperienceRecord Creation | Data §1 | T5 (Provenance) | 创建 `is_rule=True` 不报错 |
| T9 | is_rule=False Enforcement | Data §1.2 | T6 (IsRule False) | `is_rule=True` 被接受 |
| T10 | is_decision/is_obligation=False | Data §1.2 | T6 | 任何 authority flag=True 被接受 |
| T11 | Historical Failure ≠ Veto | Data §1.1 | T2 (No Veto) | 100 次失败阻止新假设 |
| T12 | Confidence Range [0,1] | Data §1.3 | T5 | confidence<0 或 >1 被接受 |
| T13 | Source Validation | Data §1.2 | T5 | simulation 来源 confidence>0.5 |

## T14–T20: Store Contract Boundary Tests

| # | 名称 | Contract 来源 | 预期失败条件 |
|---|------|--------------|-------------|
| T14 | Save/Get Roundtrip | Store §2 | 保存后检索不到或字段丢失 |
| T15 | Retrieve by Domain | Store §2.3 | domain 过滤不生效 |
| T16 | Retrieve by Source Type | Store §2.3 | source_type 过滤不生效 |
| T17 | Retrieve by Scope | Store §2.3 | scope 过滤不生效 |
| T18 | Retrieve by Created At | Store §2.3 | 时间过滤不生效 |
| T19 | Retrieve is Read-Only | Store §2.2 | 修改检索结果影响 Store |
| T20 | Audit Log on Save | Store §2.4 | save 不生成 audit event |

## T21–T25: Store Physical / Provenance Tests

| # | 名称 | Contract 来源 | 预期失败条件 |
|---|------|--------------|-------------|
| T21 | Query Timeout Enforcement | Store §2.3 | timeout>5s 不报错或默认值≠5s |
| T22 | Append-Only Calibration Events | Calibration §3.3 | 事件被覆盖/删除/合并 |
| T23 | Empty Store Retrieval | Store §2.3 | 空查询不返回空列表 |
| T24 | Config Mutation Isolation | Store §2.1 | 修改运行中配置影响执行 |
| T25 | Concurrent Read Safety | Store §2.2 | 并发读取损坏数据 |

## T26–T30: Retrieval Pipeline Boundary Tests

| # | 名称 | Contract 来源 | ABI 映射 | 预期失败条件 |
|---|------|--------------|----------|-------------|
| T26 | Scope Isolation | Retrieval §4 | T9 (Scope Violation) | 跨 scope 返回匹配 |
| T27 | Similarity ≠ Authority | Retrieval §4 + H | — | similarity=0.99 → 产生 decision |
| T28 | Context Injection (Read-Only) | Retrieval §5 | — | Retrieval 输出被调用方修改后影响源 |
| T29 | No Decision Leak | Retrieval §3 | T1 | 输出包含 recommended_action / best_choice / final_answer |
| T30 | Empty Experience | Retrieval §5.3 | — | 无匹配经验时输出非空 |

## T31–T35: Calibration Engine Boundary Tests

| # | 名称 | Contract 来源 | 预期失败条件 |
|---|------|--------------|-------------|
| T31 | Confidence Decrease Only | Calibration §2.1 + §6 | 自动校准增加了 confidence |
| T32 | No Automatic Increase Methods | Calibration §1.3 + §6 | 存在 auto_increase / success_bonus |
| T33 | Calibration Event Provenance | Calibration §3.1 + §6 | calibration 无完整 9 字段 |
| T34 | No Authority Escalation | Calibration §4.1 + §6 | confidence=0.95 改变 is_rule |
| T35 | No Winner Bias | Calibration §5.3 + §6 | success/failure 衰减速率不同 |

## T36+: Authority Intrusion Cross-Layer Tests

| # | 名称 | ABI 映射 | 入侵场景 | 预期报错 |
|---|------|---------|---------|---------|
| AI-01 | Experience → Decision Leak | §1.4 (Immutable Rules) | ExperienceOutput 试图产生 Decision | TypeError / ContractViolation |
| AI-02 | High Confidence Authority Escalation | §2 (Article II) | confidence=1.0 → upgrade_to_rule() | AttributeError / ContractViolation |
| AI-03 | Retrieval Top-1 Authority Leak | §3 (Influence Contract) | similarity=0.99 → recommended_action | 输出字段不存在 |
| AI-04 | Historical Failure Veto | §4 (Bias Tests) | 100 failures → block hypothesis | Hypothesis 被拒绝 |
| AI-05 | Simulation Authority Leak | §2.5 (Article V) | simulation+confidence=0.95 → rule | rule 被创建 |

## T42–T46: Gate 1–2 (Identity + Authority Boundary)

| # | 名称 | Gate | 预期失败条件 |
|---|------|------|-------------|
| T42 | Identity Through Store | Gate 1 | save/get 修改 experience_id/source/timestamp/scope |
| T43 | Identity Through Retrieval | Gate 1 | retrieve 后 identity 字段丢失 |
| T44 | Decision Rejects Experience | Gate 2 | Decision 接受 ExperienceRecord |
| T45 | Decision Accepts String Only | Gate 2 | string 参数被拒绝 |
| T46 | Context Path ≠ Decision Path | Gate 2 | Experience 影响 Decision 的直接入口 |

## T47–T51: Gate 3–4 (Confidence + Memory Bias)

| # | 名称 | Gate | 预期失败条件 |
|---|------|------|-------------|
| T47 | Max Confidence No Authority | Gate 3 | confidence=1.0 改变 is_rule |
| T48 | Max Confidence Pipeline | Gate 3 | 全链后 authority flag 改变 |
| T49 | 100 Failures → Confidence Decrease | Gate 4 | failure 历史无法影响 confidence |
| T50 | Failures Do Not Veto | Gate 4 | 100 次失败阻止新假设创建 |
| T51 | Retrieval Includes All Outcomes | Gate 4 | 检索屏蔽某些 outcome |

## T52–T58: Gate 5–6 (Simulation + E2E)

| # | 名称 | Gate | 预期失败条件 |
|---|------|------|-------------|
| T52 | Simulation Confidence Cap | Gate 5 | simulation confidence 超过 0.5 |
| T53 | Simulation No Rule API | Gate 5 | simulation 记录有 create_rule 方法 |
| T54 | Simulation Source Clear | Gate 5 | context 中 simulation 来源标记丢失 |
| T55 | Full E2E Pipeline | Gate 6 | 全链中 authority 泄漏 |
| T56 | E2E Authority Never Leaks | Gate 6 | 全链后 is_rule 改变 |
| T57 | E2E Null Context | Gate 6 | 空上下文时系统报错 |
| T58 | Context Is Reference Only | Gate 6 | Context 包含指令性字段 |

---

## Execution Order

测试应按照以下顺序执行（下层失败则上层不必运行）：

```
1. Data Contract (T8–T13)          ← 基础类型定义
2. Store Contract (T14–T25)        ← 存储基础设施
3. Retrieval Pipeline (T26–T30)    ← 查询能力
4. Calibration Engine (T31–T35)    ← 校准能力
5. Authority Intrusion (T36+)      ← 跨层安全验证（最重）
6. Integration Gate (T42–T58)      ← 全链路集成验证
```

## Success Criteria

```
T8–T13  PASS:  Data Contract 可执行
T14–T25 PASS:  Store Contract 可执行
T26–T30 PASS:  Retrieval Contract 可执行
T31–T35 PASS:  Calibration Contract 可执行
T36+    PASS:  Authority 边界不可穿透
T42–T58 PASS:  Integration Gate — Experience has memory, not power
----------------------------------------
Phase 10 Commitment:  Experience can influence Context.
                      Experience cannot decide, veto, rule, or mutate reality.
```
