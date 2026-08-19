# Calibration Engine Contract v1.0

> Phase 10 — Experience Intelligence Layer
> ABI anchor: `docs/abi/OCOS-Experience-ABI-1.0.md`
> Data Contract: `docs/contracts/EXPERIENCE_DATA_CONTRACT.md`
> Store Contract: `docs/contracts/EXPERIENCE_STORE_CONTRACT.md`
> Retrieval Contract: `docs/contracts/RETRIEVAL_PIPELINE_CONTRACT.md`
> Status: **FROZEN ✅** — Audit passed with 3 meta-boundary clarifications applied.
> Design principle: **Calibration is confidence maintenance, not truth optimization.**

---

## 1. Calibration Responsibility

### 1.1 唯一职责

Calibration Engine 做一件事：

> 根据可验证的事件（time decay / scope mismatch / source accuracy 变化 / 手动修正），调整 ExperienceRecord 的 `calibrated_confidence`，并记录完整的校准溯源。

### 1.2 职责边界

| 属于 Calibration Engine | 不属于 Calibration Engine |
|-------------------------|---------------------------|
| 调整 `calibrated_confidence` | 修改变 `expected_outcome` / `actual_outcome` → **不允许** |
| 追加 `CalibrationEvent` | 修改 `raw_confidence` → **永久冻结** |
| 自动衰减（time decay） | 决定是否使用经验 → **Evaluation Layer** |
| 按 scope 不匹配降权 | 根据结果好坏调整 → **不属于（防 bias）** |
| 标记经验局限 | 删除/归档经验 → **Store** |
| 记录 calibration 溯源 | 修改 `is_rule` / `is_decision` / `is_obligation` → **Store 防火墙** |

### 1.4 Outcome Observation Ownership

```
Calibration Engine does not own outcome observation.

当后期观察（later observation）发生时：
  - 记录观察属于 Evaluation Layer 或 Store metadata
  - Calibration 仅通过显式 calibration events 消费观察结果
  - Calibration 不判断结果是否"证明"了经验正确性

目的：防止未来产生隐藏学习循环：
  ❌ Experience used → outcome observed → calibration auto upgrades confidence
  ✅ Experience used → outcome observed → Evaluation records → (opt) scope mismatch → penalty
```

```python
class CalibrationEngine:
    """Calibration Engine — 只维护 confidence，不优化 truth"""

    # ── 允许 ──
    def apply_time_decay(self, experience_id: str) -> CalibrationEvent: ...
    def apply_scope_mismatch_penalty(self, experience_id: str, mismatch_reason: str) -> CalibrationEvent: ...
    def apply_source_accuracy_update(self, experience_id: str, new_accuracy: float) -> CalibrationEvent: ...
    def apply_manual_adjustment(self, experience_id: str, new_confidence: float, reason: str) -> CalibrationEvent: ...
    def apply_batch_decay(self, domain: str | None = None) -> List[CalibrationEvent]: ...
    def get_calibration_history(self, experience_id: str) -> List[CalibrationEvent]: ...

    # ── 禁止 ──
    # def auto_increase(self, ...)     ❌ — ABI 禁止自动升 confidence
    # def success_bonus(self, ...)     ❌ — winner bias 风险
    # def adjust_authority(self, ...)  ❌ — confidence ≠ authority
```

---

## 2. Direction Boundary

### 2.1 ABI 冻结规则

```
Confidence only decreases automatically.
  - time decay           → decrease
  - scope mismatch       → decrease
  - source accuracy ↓    → decrease

Confidence increases ONLY via:
  - manual_adjustment(reason=..., actor=...)
  - 必须有显式 actor 签名 + 可审计理由

ABI 约束原文:
  "Confidence 只降不升"
  例外: Manual user explicitly increases (带完整审计)
```

### 2.2 策略定义

```python
@dataclass
class DecayConfig:
    """confidence 自动衰减配置"""
    decay_rate: float = 0.05      # 每次衰减量
    decay_interval_days: int = 7  # 每 7 天衰减一次
    min_confidence: float = 0.1   # 衰减下限（低于此值不再自动衰减）
    scope_mismatch_penalty: float = 0.15   # scope 不匹配单次惩罚
    source_accuracy_factor: float = 0.3    # source_accuracy 对 confidence 的影响系数
```

### 2.3 自动衰减算法

```python
def apply_time_decay(self, experience_id: str) -> CalibrationEvent:
    """
    confidence 随时间衰减。

    规则 (ABI v1.0 约束):
      1. calibrated_confidence -= decay_rate (每 decay_interval_days)
      2. 下限 = min_confidence (从不降至 0 以下)
      3. raw_confidence 不受影响（永久冻结）
      4. 每次衰减生成一个 CalibrationEvent

    数学:
      calibrated_confidence(t+1) = max(
          calibrated_confidence(t) - decay_rate,
          min_confidence
      )

    不依赖:
      - 该经验的结果好坏（成功/失败不影响衰减速度）
      - 该经验的使用频率（使用频率不影响 decay）
      - 检索频率（检索多≠更重要）
    """
```

### 2.4 scope 不匹配惩罚

```python
def apply_scope_mismatch_penalty(self, experience_id: str, mismatch_reason: str) -> CalibrationEvent:
    """
    当经验被检索后发现当前 scope 与记录 scope 不匹配时，
    降低 calibrated_confidence。

    规则:
      1. penalty = scope_mismatch_penalty (配置项，默认 0.15)
      2. 不降低至 min_confidence 以下
      3. mismatch_reason 必须记录

    应用场景:
      - Retrieval Pipeline 返回了该经验，但 Evaluation 发现
        实际条件与 scope 不完全匹配，请求降权
      不应用场景:
      - 结果好坏（不能因为 outcome=failure 而额外降权）
    """
```

---

## 3. Calibration Event Provenance

### 3.1 事件格式

每一次校准调整必须记录：

```python
@dataclass
class CalibrationEvent:
    """校准事件：confidence 变化的完整记录"""
    experience_id: str
    timestamp: str                # ISO 8601
    old_confidence: float         # 调整前的 calibrated_confidence
    new_confidence: float         # 调整后的 calibrated_confidence
    delta: float                  # new - old (始终 ≤ 0，除非 manual)
    reason: str                   # 原因枚举（见 §3.2）
    source: str                   # 触发者标识（engine / user / system）
    actor: str                    # 执行者标识
    metadata: dict | None = None  # 附加信息（可选）

    # 约束
    # - old_confidence ≠ new_confidence (无操作调整禁止记录)
    # - delta ≤ 0 除非 reason='manual_adjustment'
    # - reason 必须是 §3.2 枚举中的值
```

### 3.2 原因枚举

```python
class CalibrationReason(str, Enum):
    # 自动衰减 (delta ≤ 0)
    TIME_DECAY = "time_decay"                         # 时间衰减
    SCOPE_MISMATCH = "scope_mismatch"                 # scope 不匹配
    SOURCE_ACCURACY_DECREASE = "source_accuracy_decrease"  # 来源准确度降低
    CONTEXT_OBSOLETE = "context_obsolete"             # 上下文过时

    # 手动调整 (delta 任意)
    MANUAL_ADJUSTMENT = "manual_adjustment"           # 用户/系统手动修正
```

### 3.4 Historical Observation Rule

```python
# 原始 ExperienceRecord 字段不可变。
# later observations MUST be represented as:
#
#   正确路径:
#     CalibrationEvent(experience_id, delta=0, reason="observation", ...)
#     或
#     Store metadata append (由 Evaluation 写入)
#
#   禁止路径:
#     rewriting actual_outcome        ❌
#     rewriting expected_outcome      ❌
#     replacing original experience   ❌
#     merging observations into       ❌
#       raw_confidence / source / scope
#
# 如果后期发现原始经验记录有误：
#   不能修改原始记录
#   正确做法：保存新的 experience + 记录校准事件关联旧记录
```

### 3.5 校准回看

```python
def get_calibration_history(self, experience_id: str) -> List[CalibrationEvent]:
    """
    返回该 experience 的全部校准历史，按时间升序。

    每次校准都是 append-only 追加到 Store 的 calibration_events 表。
    不得压缩、合并、覆盖历史事件。
    """
```

---

## 4. No Authority Escalation

### 4.1 Confidence ≠ Authority

```
即使 calibrated_confidence = 0.99，也绝不改变:
  is_rule = False
  is_decision = False
  is_obligation = False

防止: confidence=0.99 → authority_level++

Reason (ABI v1.0):
  Confidence 是"这条经验在多大程度上反映了当时发生的事"
  Authority 是"这条经验是否有权影响决策"

前者是历史准确度，后者是权力分配。
两者正交。
```

### 4.2 运行时断言

```python
def validate_no_authority_escalation(record: ExperienceRecord) -> None:
    """确保 calibration 不会通过 confidence 提升 authority"""
    # confidence 可以变
    # authority flags 永远 False
    assert record.is_rule is False
    assert record.is_decision is False
    assert record.is_obligation is False
    # 这条断言在每次 calibration 后运行
```

### 4.3 禁止的映射

```python
# ❌ 禁止: confidence ≥ 0.9 → "应采纳"
USE_IF_CONFIDENCE_ABOVE = None  # 不存在此配置

# ❌ 禁止: confidence 高 → 检索时优先
# Retrieval 的排序只依据 similarity, 不是 confidence

# ❌ 禁止: confidence 升 → 自动调整 scope 范围
CALIBRATION_DOES_NOT_EXPAND_SCOPE = True
```

---

## 5. Bias Protection

### 5.1 winner bias 防御

```python
# 绝对禁止:
#   success_count++ → confidence += bonus
#   即使连续成功 10 次，calibrated_confidence 也不会自动上升

# 原因:
#   一次成功不能覆盖 100 次失败
#   结果好坏是 outcome 字段的事，不是 confidence 的事
#   Confidence 反映的是:
#     "信息源的可信度 + 时间衰减 + 范围匹配度"
#   不是:
#     "这条经验看起来是对的"
```

### 5.2 recency bias 防御

```python
# 衰减速率与时间绑定，与最近结果无关
#   最近一次检索/使用不改变衰减速率
#   经验不使用也会衰减（冷处理≠遗忘）
#   经验频繁使用也不停止衰减（使用≠重要性）
```

### 5.3 outcome-independent decay

```python
# 衰减不区分 outcome:
#   outcome=success  → 衰减速率不变
#   outcome=failure  → 衰减速率不变
#   outcome=unknown  → 衰减速率不变
#   outcome=partial  → 衰减速率不变

# 只有以下三个因素可以影响衰减:
#   1. 时间 (decay_rate)
#   2. Scope 不匹配 (scope_mismatch_penalty)
#   3. Source accuracy 变化 (source_accuracy_factor)
```

---

## 6. Calibration Engine Tests

### T31 — Confidence Decrease Only

```python
def test_confidence_decrease_only():
    """自动校准只降不升"""
    record = make_experience(calibrated_confidence=0.8)
    store.save(record)

    engine = CalibrationEngine(store)

    # 自动衰减
    engine.apply_time_decay("test-001")  # 0.8 → 0.75
    record = store.get("test-001")
    assert record.calibrated_confidence < 0.8

    # scope mismatch
    engine.apply_scope_mismatch_penalty("test-001", reason="domain_differs")
    record = store.get("test-001")
    initial = record.calibrated_confidence
    assert initial <= 0.75  # 持续下降

    # 手动增加可行
    engine.apply_manual_adjustment("test-001", new_confidence=0.85, reason="user_correction")
    record = store.get("test-001")
    assert record.calibrated_confidence == 0.85  # 手动可以升
```

### T32 — No Automatic Increase

```python
def test_no_automatic_increase():
    """Calibration Engine 不提供任何自动升 confidence 的方法"""
    engine = CalibrationEngine(store)

    # CalibrationEngine 的公开方法中不应该有:
    assert not hasattr(engine, "auto_increase")
    assert not hasattr(engine, "success_bonus")
    assert not hasattr(engine, "confidence_boost")
    assert not hasattr(engine, "positive_reinforcement")

    # 手动调整必须指定 reason='manual_adjustment'
    with pytest.raises(ValueError):
        engine.apply_manual_adjustment("test-001", new_confidence=0.9, reason="auto_correct")
```

### T33 — Calibration Event Provenance

```python
def test_calibration_event_provenance():
    """每次校准产生完整的溯源事件"""
    record = make_experience(calibrated_confidence=0.8)
    store.save(record)

    engine = CalibrationEngine(store)
    event = engine.apply_time_decay("test-001")

    # 完整的溯源字段
    assert event.experience_id == "test-001"
    assert event.old_confidence == 0.8
    assert event.new_confidence == 0.75
    assert event.delta == -0.05
    assert event.reason == "time_decay"
    assert event.source == "engine"
    assert event.actor == "calibration_engine"
    assert event.timestamp is not None

    # 历史可回溯
    history = engine.get_calibration_history("test-001")
    assert len(history) == 1
    assert history[0].old_confidence == 0.8
```

### T34 — No Authority Escalation

```python
def test_no_authority_escalation():
    """校准后 is_rule/is_decision/is_obligation 始终为 False"""
    record = make_experience(calibrated_confidence=0.7)
    store.save(record)

    engine = CalibrationEngine(store)

    # 多次校准
    for _ in range(5):
        engine.apply_time_decay("test-001")

    record = store.get("test-001")
    assert record.is_rule is False
    assert record.is_decision is False
    assert record.is_obligation is False

    # 手动升回高置信度
    engine.apply_manual_adjustment("test-001", new_confidence=0.95, reason="user_correction")
    record = store.get("test-001")
    assert record.calibrated_confidence == 0.95
    assert record.is_rule is False       # 即使 confidence 很高，也不是规则
    assert record.is_decision is False
```

### T35 — No Winner Bias

```python
def test_no_winner_bias():
    """结果好坏不影响 confidence 衰减速度"""
    store.save(make_experience(experience_id="success-exp", outcome="success", calibrated_confidence=0.8))
    store.save(make_experience(experience_id="failure-exp", outcome="failure", calibrated_confidence=0.8))

    engine = CalibrationEngine(store)

    # 同时衰减
    engine.apply_time_decay("success-exp")
    engine.apply_time_decay("failure-exp")

    success_rec = store.get("success-exp")
    failure_rec = store.get("failure-exp")

    # 衰减量相同
    assert success_rec.calibrated_confidence == failure_rec.calibrated_confidence
```

---

## 7. 与上下游的契约边界

```
Store (Step 2)          Calibration (Step 4)        Retrieval (Step 3)
    │                          │                          │
    │  get(id) → Record        │                          │
    │  append_calibration()    │                          │
    │  audit_log()             │                          │
    ▼                          │                          │
┌──────────┐                  │                          │
│  Store   │                  │                          │
│  (raw)   │  Store 输出原始记录+可追加校准事件            │
└────┬─────┘                  │                          │
     │                        │                          │
     │  Store.get(id)         │                          │
     │  Store.append_calibration(event)                   │
     │                        │                          │
     │                        ▼                          │
     │              ┌──────────────────┐                 │
     │              │   Calibration    │                 │
     │              │     Engine       │                 │
     │              │                  │                 │
     │              │  只操作:          │                 │
     │              │  calibrated_     │                 │
     │              │  confidence      │                 │
     │              │                  │                 │
     │              └────────┬─────────┘                 │
     │                       │                           │
     │                       │ CalibrationEvent          │
     │                       ▼                           │
     │              ┌──────────────────┐                 │
     │              │ 校准后的 Record   │                 │
     │              │ (confidence 更新) │                 │
     └──────────────┴──────────────────┘                 │
                               ▲                         │
                               │                         │
                    Retrieval 读取校准后的 confidence     │
                               │                         │
                    (但 Retrieval 不发起校准)             │
```

**关键契约线：**

```
Store ↔ Calibration:
  Calibration 读取 ExperienceRecord (只读)
  Calibration 追加 CalibrationEvent 到 Store (append-only)
  Store 校验 CalibrationEvent 格式

Calibration ↔ Retrieval:
  Retrieval 读取校准后的 calibrated_confidence
  Retrieval 可以向 Evaluation 报告 scope mismatch，
    由 Evaluation 决定是否触发 CalibrationEngine.apply_scope_mismatch_penalty()
  但 Retrieval 从不直接调用 CalibrationEngine

Calibration ↔ Evaluation:
  Evaluation 可以触发 scope_mismatch_penalty
  Evaluation 可以触发 manual_adjustment (用户操作)
  Calibration 不决定"是否使用经验"(那是 Evaluation 的事)
```

---

## 8. Meta Boundary Declaration — Calibration ≠ Learning Authority

```
Calibration Engine improves representation quality.
It does not:
  - create knowledge
  - establish truth
  - generate rules
  - grant authority
  - initiate decisions

Confidence improvement represents information quality.
Confidence improvement does not represent system authority growth.

ABI 对应:
  "Experience can inform. Experience cannot rule."
  → "Confidence can improve. Authority cannot expand."

运行时:
  Calibration Engine 是整个 Experience 层中对 Authority Impact 最低的模块。
  它不启动任何决策路径。
  它不自发增长知识。
  它的唯一职责是:
    Experience → better confidence representation → Better Context → Better Hypothesis
  (停止，不继续向 Authority / Decision 渗透)
```

---

## 附录 A — 校准原因速查

| reason | delta | 自动/手动 | 触发者 |
|--------|-------|-----------|--------|
| `time_decay` | ≤0 | 自动 | engine (定时器) |
| `scope_mismatch` | ≤0 | 自动 | evaluation 请求 |
| `source_accuracy_decrease` | ≤0 | 自动 | engine (source 更新) |
| `context_obsolete` | ≤0 | 自动 | engine (上下文检测) |
| `manual_adjustment` | 任意 | 手动 | user/system (显式) |

## 附录 B — 冻结条件清单

| 条件 | 验证方式 |
|------|---------|
| 自动校准只降不升 | §2.1 + T31 |
| 无 auto_increase / success_bonus 方法 | T32 |
| 每次校准有完整 provenance | §3.1 + T33 |
| 校准后 is_rule/is_decision 不变 | §4.1 + T34 |
| 结果好坏不影响衰减速率 | §5.3 + T35 |
| raw_confidence 永久冻结 | ABI v1.0 §4 |
| 手动调整必须带 actor+reason | §3.2 |
| confidence ≠ authority 运行时断言 | §4.2 |
| Calibration 不拥有 outcome observation | §1.4 |
| 后期观察只能 append，不可改写原始记录 | §3.4 |
| Confidence 可改善，Authority 不可扩展 | §8 |
