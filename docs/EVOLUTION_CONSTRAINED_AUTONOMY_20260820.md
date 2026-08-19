# ③ 进化"受约束自主"——Authority 边界文档（2026-08-20）

- 状态：已实现并验证（OCOS 3218p 回归 + 6 项专项 + Gate GO）
- 性质：U5.2"提案治理"→ ③"受约束自主"的治理语义升级（老高授权，最高治理风险项）

---

## 一、治理语义升级（三层批准路径）

```text
进化提案
  ↓ 安全预检（Gate 1-4：sandbox / 边界 / 影响等级 / change_type）
  ↓
Gate 5 受约束自主判定（_auto_eligible）
  ├── 低风险自主域 → auto:governed（自动批准，受严格条件约束）
  ├── 高风险/权威域 → PENDING_REVIEW（人工批准 manual:xxx）
  └── 永禁域 → REJECTED（拒绝，永不批准）
```

## 二、受约束自主的边界（冻结）

### 可自主（auto:governed）——全部条件满足才可
```text
domain        ∈ {parameter, connection, adapter, knowledge}（低风险内部优化域）
impact.level  ∈ {negligible, low}
change_type   ∈ {optimize, add}
sandbox       通过
边界安全       is_boundary_safe
可回滚         rollback_viable（自主进化必须可回滚）
```

### 强制人工（manual）——任何一条触发
```text
domain ∈ {capability, attention, learning, extension}（能力面/策略/扩展）
impact.level ∈ {moderate, high, critical}
change_type = replace
不可回滚（rollback_viable=False → 更严格：拒绝）
```

### 永远禁止（FORBIDDEN）——拒绝
```text
domain ∈ {identity, constitution, permission_model, core_values, anchor}
```

## 三、Authority 原则（保持冻结）

```text
Capability ≠ Authority         （能力不自动获得权限）
Proposal ≠ Decision            （提案不经自动/人工批准 ≠ 决策）
auto:governed ≠ 无边界自主      （自主仅限低风险域 + 五条件）
Belief/Attention/Pattern       （认知层仍只读，不触 Decision/Mutation）
Decision 唯一 Mutation Authority（I-6 保持）
```

**关键防线**：受约束自主**不改变** I-6（Decision 唯一 Mutation Authority）——auto:governed 是"进化提案的自动批准"（针对低风险内部优化），不是"认知直接 Mutation"；任何触权威域的进化仍人工。

## 四、验证证据

| 验证 | 结果 |
|:---|:---|
| 低风险自主域（parameter+LOW+optimize+可回滚）→ auto:governed | ✅ |
| HIGH 影响 → 人工 | ✅ |
| capability 域 → 人工 | ✅ |
| 永禁域（identity）→ 拒绝 | ✅ |
| 不可回滚 → 拒绝（自主路径封死） | ✅ |
| 人工路径保留（manual_approve） | ✅ |
| OCOS 全量回归 | ✅ 3218 passed / 16 skipped |
| No Regression（Gate GO） | ✅ PASS 5 / DEGRADED 3 / FAIL 0 |

## 五、与老高治理哲学的衔接

- U5.2 的"禁止自动批准"是**第一版约束**（能力未验证前一律人工）
- ③ 的"受约束自主"是**治理成熟后的受控放开**（低风险域 + 五条件 + 可回滚 + 审计），**高风险/权威域约束不变**
- 若未来发现自主进化异常 → 一键回滚（rollback_engine）+ 收紧自主域（改 AUTO_GOVERNED_DOMAINS 一处）
