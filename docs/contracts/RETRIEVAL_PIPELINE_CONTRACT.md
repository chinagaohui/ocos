# Retrieval + Context Injection Pipeline Contract v1.0

> Phase 10 — Experience Intelligence Layer
> ABI anchor: `docs/abi/OCOS-Experience-ABI-1.0.md`
> Data Contract: `docs/contracts/EXPERIENCE_DATA_CONTRACT.md`
> Store Contract: `docs/contracts/EXPERIENCE_STORE_CONTRACT.md`
> Status: **FROZEN ✅** — Audit passed with 2 minor clarifications applied.
> Design principle: **Retrieval can select. Retrieval cannot decide.**

---

## 1. Retrieval Responsibility

### 1.1 唯一职责

Retrieval Pipeline 做一件事：

> 根据当前 Evaluation Context，从 Experience Store 中找到相关的 `ExperienceRecord`，组装为 `ExperienceContext` 注入 Evaluation Layer。

### 1.2 职责边界

| 属于 Retrieval | 不属于 Retrieval |
|---------------|-----------------|
| 按 scope 计算相似度 | 修改 ExperienceRecord 内容 → **Store** |
| 按 domain/context 筛选 | 校准 confidence → **Calibration Engine (Step 4)** |
| 排序/排名（按 relevance） | 判断假设好坏 → **Evaluation Layer** |
| 组装 `ExperienceContext` | 给出行动建议 → **决策系统** |
| 标记经验局限 | 修改 Reality → **Commit** |
| 空结果处理 | 自动重试 / fallback 到不相关经验 → **Evaluation Layer** |

### 1.3 核心契约

```python
class RetrievalPipeline:
    """Retrieval + Context Injection Pipeline"""

    def retrieve(
        self,
        evaluation_context: EvaluationContext,
    ) -> ExperienceContext:
        """
        输入: EvaluationContext（当前正在评估的假设 + 环境状态）
        输出: ExperienceContext（相关经验集合 + 相似度 + 局限）
        效果: 只读 Store，不修改任何 ExperienceRecord
        """
        ...

    def retrieve_by_id(
        self,
        experience_id: str,
    ) -> ExperienceRecord | None:
        """直接通过 ID 获取原始经验（审计 / 调试用）"""
        ...
```

---

## 2. Retrieval Pipeline Architecture

```
Evaluation Layer
      │
      │  调用 retrieve(EvaluationContext)
      ▼
┌─────────────────────────────────────┐
│         Retrieval Pipeline          │
│                                     │
│  1. Scope Extraction               │
│     - 从 EvaluationContext 提取      │
│       domain / context / condition  │
│                                     │
│  2. Store Query                    │
│     - Store.list(domain=...,       │
│                  scope_exact=...)   │
│                                     │
│  3. Scope Similarity Scoring       │
│     - 非精确匹配的记录按相似度降权   │
│     - 相似度算法（可配置）           │
│                                     │
│  4. Filter by Threshold            │
│     - 排除 similarity < 0.3 的记录  │
│                                     │
│  5. Context Assembly               │
│     - 组装 ExperienceContext       │
│     - 包含 refs / confidence /     │
│       scope_match / limitations    │
│                                     │
└─────────────┬───────────────────────┘
              │
              ▼
     ExperienceContext
              │
              ▼
     Evaluation Layer
```

### 2.1 EvaluationContext 输入定义

```python
@dataclass
class EvaluationContext:
    """Retrieval Pipeline 的查询上下文"""
    hypothesis: str                          # 当前正在评估的假设
    domain: str                              # 领域
    context: str                             # 当前场景
    conditions: List[str]                    # 当前条件
    # 不包含: 预期答案 / 期望结果 / 决策倾向
```

### 2.2 Scope 相似度算法

```python
def scope_similarity(request_scope: str, record_scope: str) -> float:
    """
    Scope 相似度评分 [0, 1]

    规则:
      - domain 不同 → 0.2  (即使 context 相同也跨域了)
      - domain 同, context 不同 → 0.4
      - domain 同, context 同, condition 不同 → 0.7
      - domain 同, context 同, condition 同 → 1.0

    输出: raw_similarity ∈ [0, 1]
      反映条件匹配程度。**不含 calibrated_confidence 加权。**

    唯一允许的 weighted 使用:
      在 §4.3 aggregate_experiences() 中:
        weight = raw_similarity
        (weighted by similarity, not by confidence — 防止高置信经验在低相似度域中产生过高影响)

    ABI 约束:
      - 不返回负值（没有 "惩罚" 概念）
      - 不过 similarity 再高，也不改变 is_rule/is_decision 标志
      - 不过 similarity 再高，也不自动提升 confidence
    """
```

**Scope 相似度 ≠ 正确性评分**

```
相似度 0.9 的含义：
    这条经验发生的条件与当前条件高度相似。
不是：
    这条经验的结果在当前条件下 90% 正确。
```

### 2.3 默认阈值

```python
# Retrieval 默认过滤阈值
MIN_SIMILARITY_THRESHOLD = 0.3   # 低于此值的经验不返回
DEFAULT_MAX_RESULTS = 20         # 单次检索最大返回数
```

---

## 3. Retrieval Output Contract

### 3.1 允许的输出

```python
@dataclass
class ExperienceContext:
    """Retrieval Pipeline 的唯一输出类型"""

    # 匹配的经验引用
    # references 按 similarity 降序排列。
    # 顺序反映条件匹配强度 (condition matching strength)。
    # 顺序不表示:
    #   - 推荐优先级 (recommendation priority)
    #   - 决策偏好 (decision preference)
    #   - 行动排名 (action ranking)
    # Top-1 ≠ Best Decision.
    references: List[ExperienceReference]

    # 聚合置信度（按 similarity 加权平均）
    aggregated_confidence: float   # [0, 1]

    # 检索范围
    domain: str
    scope_requested: str

    # 局限声明
    limitations: List[str]         # 至少包含空列表

    # 来源分布
    source_distribution: Dict[str, int]  # e.g. {"observation": 5, "simulation": 2}
```

```python
@dataclass
class ExperienceReference:
    """单条匹配经验的引用（不是完整 record）"""
    experience_id: str
    similarity: float              # scope 相似度 [0, 1]
    calibrated_confidence: float   # 经验的当前置信度
    actual_outcome: str            # 结果
    scope: str
    limitations: List[str]

    # 不是 Decision, 不是 Action, 不是 Rule
    # 不是 recommended_action, 不是 best_choice, 不是 final_answer
```

### 3.2 禁止的输出字段

| 字段 | 禁止原因 |
|------|---------|
| `recommended_action` | 隐含"这是你应该做的" |
| `best_choice` | 隐含 ranking → 偏好 → 隐性决策 |
| `final_answer` | Retrieval 不提供最终答案 |
| `decision_support` | 太模糊，可被解释为建议 |
| `vote` / `score` | 聚合分数不等同于投票 |
| `priority` | 排序优先级不等同于行动优先级 |

### 3.3 输出合规检查

```python
def validate_experience_context(ctx: ExperienceContext) -> None:
    """运行时断言：确保输出不携带禁区字段"""

    for ref in ctx.references:
        assert not hasattr(ref, "recommended_action")
        assert not hasattr(ref, "best_choice")
        assert not hasattr(ref, "final_answer")
        assert not hasattr(ref, "vote")
        assert ref.is_rule is False      # 继承自 Store
        assert ref.is_decision is False
        assert ref.is_obligation is False

    assert ctx.aggregated_confidence >= 0.0
    assert ctx.aggregated_confidence <= 1.0
```

---

## 4. Similarity Boundary

### 4.1 相似度 ≠ 权威度

```
相似度 = 条件匹配程度
权威度 = 建议的可信度 (Retrieval 没有这个字段)

相似度 0.95 ≠ "这条经验可信"
相似度 0.95 = "这条经验的发生条件与当前高度相似，仅供参考"
```

### 4.2 禁止的相似度用途

| 用途 | 允许？ | 原因 |
|------|--------|------|
| 筛选相关经验 | ✅ | Retrieval 的职责 |
| 计算加权置信度 | ✅ | 合理聚合 |
| 决定"应该怎么做" | ❌ | 这属于 Decision |
| 根据相似度 veto 某个假设 | ❌ | 违反 Experience Influence Contract |
| 相似度 > 0.9 自动视为"真理" | ❌ | 违反 Article IV (Prediction ≠ Truth) |

### 4.3 聚合算法约束

```python
def aggregate_experiences(refs: List[ExperienceReference]) -> float:
    """
    加权聚合置信度。

    约束:
      1. 权重 = similarity, 不是 calibrated_confidence
         (原因: 防止高置信度经验在低相似度域中产生过高影响)
      2. 聚合结果 ∈ [0, 1]
      3. 聚合结果不用于 veto 假设
      4. 聚合结果不是 "成功率"

    这不是:
      - 投票系统 (每个经验没有相等投票权)
      - 权威评分 (聚合分高不意味应该采纳)
      - 决策依据 (Retrieval 不提供 "做什么")
    """
    if not refs:
        return 0.0

    total_weight = sum(r.similarity for r in refs)
    if total_weight == 0:
        return 0.0

    weighted = sum(r.similarity * r.calibrated_confidence for r in refs)
    return weighted / total_weight
```

---

## 5. Context Injection Boundary

### 5.1 注入目标

```
正确路径:

  Retrieval ────────────────────┐
                                ▼
  Evaluation Layer ←── ExperienceContext
        │
        ▼
  Hypothesis Quality
        │
        ▼
  Governance (是否提交 Decision)
        │
        ▼
  Decision (用户/系统)
        │
        ▼
  Mutation
```

```
禁止路径:

  Retrieval ──► Decision            ❌ (跳过 Evaluation)
  Retrieval ──► Governance          ❌ (跳过评估)
  Retrieval ──► Mutation            ❌ (跳过决策链)
```

### 5.2 Context 格式约束

```python
@dataclass
class EvaluationContext:
    """
    Evaluation Layer 接收的上下文

    ├── from Planner: 当前假设
    ├── from Environment: 当前状态
    └── from Retrieval: ExperienceContext
         │
         └── 这是"参考信息"，不是"判断依据"
    """
    hypothesis: str
    domain: str
    user_intent: str
    environmental_state: dict

    # 注入的经验上下文
    experience_context: ExperienceContext | None = None
```

### 5.3 injection 不做的事

```python
class ContextInjector:
    """
    ContextInjector 只做：
      1. 接收 ExperienceContext
      2. 将其附加到 EvaluationContext
      3. 传递到 Evaluation Layer

    不做：
      1. 不解析 / 不解释经验
      2. 不改写假设
      3. 不应用经验（那是 Evaluation 的事）
      4. 不调整 confidence（那是 Calibration Engine 的事）
    """
```

---

## 6. Retrieval Tests

### T26 — Retrieval Scope Isolation

```python
def test_retrieval_scope_isolation():
    """不同 scope 的检索返回不同且正确的结果"""
    store.save(make_experience(scope="code_review:python:microservice", outcome="success"))
    store.save(make_experience(scope="code_review:python:monolith", outcome="failure"))
    store.save(make_experience(scope="creative_writing:urban_romance:outlining", outcome="success"))

    pipeline = RetrievalPipeline(store)

    # 检索 python microservice
    ctx = pipeline.retrieve(EvaluationContext(
        hypothesis="refactor X",
        domain="code_review",
        context="python",
        conditions=["microservice"]
    ))

    assert len(ctx.references) == 1
    assert ctx.references[0].scope == "code_review:python:microservice"
```

### T27 — Similarity ≠ Authority

```python
def test_similarity_not_authority():
    """高相似度的经验不获得权威标记"""
    store.save(make_experience(
        experience_id="high-sim",
        scope="code_review:python:microservice",
        outcome="success",
        raw_confidence=0.95
    ))

    ctx = pipeline.retrieve(EvaluationContext(
        hypothesis="refactor X",
        domain="code_review",
        context="python",
        conditions=["microservice"]
    ))

    high_ref = ctx.references[0]
    assert high_ref.similarity > 0.9   # 高相似度
    assert high_ref.is_rule is False    # 但不获得权威
    assert high_ref.is_decision is False
    assert high_ref.is_obligation is False
    # 不包含 recommended_action
    assert not hasattr(high_ref, "recommended_action")
```

### T28 — Context Injection Boundary

```python
def test_context_injection_boundary():
    """ContextInjector 只传递，不解释"""
    store.save(make_experience(scope="code_review:python:microservice", outcome="failure"))
    ctx = pipeline.retrieve(EvaluationContext(
        hypothesis="deploy X",
        domain="code_review",
        context="python",
        conditions=["microservice"]
    ))

    # ContextInjector 附加经验上下文
    evaluation_ctx = EvaluationContext(
        hypothesis="deploy X",
        domain="code_review",
        user_intent="check risk",
        environmental_state={"branch": "main"},
        experience_context=ctx,
    )

    # 验证：ExperienceContext 是附加的，不是替代的
    assert evaluation_ctx.hypothesis == "deploy X"  # 假设未被改写
    assert evaluation_ctx.experience_context is not None
    assert len(evaluation_ctx.experience_context.references) == 1
```

### T29 — No Decision Leakage

```python
def test_no_decision_leakage():
    """Retrieval 输出不能包含决策信息（编译级检查）"""
    # 静态类型检查: ExperienceReference 没有 recommended_action/best_choice/final_answer
    ref = ExperienceReference(
        experience_id="test",
        similarity=0.8,
        calibrated_confidence=0.7,
        actual_outcome="success",
        scope="code_review:python:microservice",
        limitations=[]
    )
    with pytest.raises(AttributeError):
        _ = ref.recommended_action  # 类型不包含此字段

    # 聚合结果不提供建议
    ctx = pipeline.retrieve(some_context)
    assert not hasattr(ctx, "recommended_action")
    assert not hasattr(ctx, "best_choice")
```

### T30 — Empty Experience Handling

```python
def test_empty_experience_handling():
    """Store 中没有相关经验时，Retrieval 返回空 Context（不是报错）"""
    # 没有保存任何经验
    ctx = pipeline.retrieve(EvaluationContext(
        hypothesis="unknown_topic",
        domain="nonexistent",
        context="unknown",
        conditions=[]
    ))

    assert ctx is not None  # 返回有效对象
    assert len(ctx.references) == 0
    assert ctx.aggregated_confidence == 0.0
    assert ctx.limitations == ["no_experience_found"]
```

---

## 7. 与上下游的契约边界

```
Store (Step 2)              Retrieval (Step 3)           Evaluation (Step 3+) 
    │                              │                              │
    │  list(filter) → Records     │                              │
    │  get(id) → Record          │                              │
    ▼                              │                              │
┌──────────┐                       │                              │
│  Store   │                       │                              │
│  (raw)   │  Store 输出原始记录    │                              │
└──────────┘                       │                              │
        │                          │                              │
        │                          │                              │
        │  相似度计算               │                              │
        │  筛选                     │                              │
        │  组装 ExperienceContext   │                              │
        │                          ▼                              │
        │                    ┌──────────────┐                     │
        │                    │  Retrieval   │                     │
        │                    │  Pipeline    │                     │
        │                    └──────┬───────┘                     │
        │                           │                             │
        │                           │ ExperienceContext           │
        │                           ▼                             │
        │                    ┌──────────────┐                     │
        │                    │   Context    │                     │
        │                    │  Injector    │                     │
        │                    └──────┬───────┘                     │
        │                           │                             │
        │                           │ 附加到 EvaluationContext    │
        │                           ▼                             │
        │                    ┌──────────────┐                     │
        └────────────────────│  Evaluation  │─────────────────────┘
                             │    Layer     │
                             └──────────────┘
```

**关键契约线：**

```
Store → Retrieval:  原始 ExperienceRecord（无排名、无分数）
Retrieval → Evaluation: ExperienceContext（含相似度、有筛选、有局限）
```

---

## 附录 A — 输出字段合规速查表

```
ExperienceReference

id               ✅ 唯一标识
similarity       ✅ 范围 [0, 1]
confidence       ✅ 经验置信度
outcome          ✅ 历史结果
scope            ✅ 适用域
limitations      ✅ 局限声明
is_rule          ✅ 永远 False
is_decision      ✅ 永远 False
is_obligation    ✅ 永远 False

recommended_action    ❌ 不在 Schema 中
best_choice           ❌ 不在 Schema 中
final_answer          ❌ 不在 Schema 中
vote                  ❌ 不在 Schema 中
priority              ❌ 不在 Schema 中
```

## 附录 B — 冻结条件清单

| 条件 | 验证方式 |
|------|---------|
| Retrieval 输出无 recommended_action/best_choice/final_answer | 类型检查 + 运行时断言 |
| Scope 相似度 ≠ 正确性评分 | §2.2 明确声明 |
| 聚合算法不过 similarity + confidence 加权 | §4.3 |
| ContextInjector 只附加不改写 | §5.3 |
| T26–T30 全部通过 | 测试运行 |
| 不修改 Store 中的 ExperienceRecord | 只读 API |
| 空经验返回空 Context（非报错） | §6 T30 |
