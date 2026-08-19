# Phase14.4.3 — Evidence Chain / Explanation ABI

**Status**: ❄️ FROZEN (2026-07-22)
**Phase**: Phase14.4 Meta Principle Formation
**Previous**: §14.4.2 Pattern→Principle Inference ✅
**Next**: §14.4.4 Principle Validation

---

## 0. Positioning — Why Evidence Chain Matters

Phase14.4.3 回答的核心问题：

> 一个 PrincipleCandidate 如何被"解释"——它的证据路径是什么？

**不是**生成漂亮解释，而是**冻结证据链结构、Explanation 边界和完整性的束**。

Phase14.4.3 的首要风险是"伪知识"：

```
Pattern ──► LLM 自然语言生成 ──► 看起来合理的解释 ──► 被当成真实机制
```

为防止这一点，我们必须强制：

```
PrincipleCandidate
  └── InferenceRecord
        ├── Pattern References     (可解析的 ID 列表)
        ├── Evidence References    (可解析的 ID 列表)
        ├── Relation Path          (Relation graph 追踪)
        ├── Derivation Path        (自然语言, 但受约束)
        └── Abstraction Trace      (L0→L1→L2 的层级路径)
```

所有引用必须是**可解析的 ID**，不能是"模型认为"的自由文本。

---

## 1. InferenceRecord Model

```python
@dataclass
class InferenceRecord:
    """从 PrincipleCandidate 到证据的完整追踪记录."""

    # 标识
    record_id: str                          # 格式: ir-{uuid_short}
    candidate_id: str                       # 对应的 PrincipleCandidate ID (pc-*)

    # 可解析引用 (非自由文本)
    pattern_references: List[PatternRef]    # Pattern ID + 角色
    evidence_references: List[EvidenceRef]  # Evidence ID + 支撑类型
    relation_path: List[RelationRef]        # Relation 链追踪

    # 追踪信息
    abstraction_level: AbstractionLevel     # L0→L1/L2/L3
    derivation_path: ExplanationConstraint  # 受约束的推导路径描述
    abstraction_trace: List[str]            # 层级路径, 如 ["pat-*", "pc-*"]

    # 元信息
    created_at: datetime
    version: int = 1
```

### 1.1 PatternRef

```python
@dataclass
class PatternRef:
    pattern_id: str                         # pat-* 格式
    role: str                               # "primary_support" | "contrast" | "contextual"
    work_context: str                       # 作品上下文 (简短)
```

### 1.2 EvidenceRef

```python
@dataclass
class EvidenceRef:
    evidence_id: str                        # ev-* / e-* 格式
    support_type: str                       # "direct" | "indirect" | "structural"
    confidence: ConfidenceLevel             # 观察置信度 (不是价值判断)
```

### 1.3 RelationRef

```python
@dataclass
class RelationRef:
    relation_type: str                      # 同 Phase14.2-B2
    pattern_a_id: str                       # pat-*
    pattern_b_id: str                       # pat-*
    strength: float                         # 0.0~1.0 (结构强度, 非价值)
    context: str                            # 关系出现的上下文
```

### 1.4 ConfidenceLevel

```python
class ConfidenceLevel(str, Enum):
    """观察置信度 — 仅表示观察层面的确认程度，不是价值判断."""
    LOW = "low"               # 单一来源, 低发生频次
    MEDIUM = "medium"         # 多源交叉, 中等频次
    HIGH = "high"             # 跨作品/跨类型确认
    ESTABLISHED = "established"  # 被多阶段验证支持
```

**ConfidenceLevel 须知**:
- LOW/MEDIUM/HIGH/ESTABLISHED 仅描述**观察确认度**
- 不代表"正确/有效/成功"
- 一个 ESTABLISHED 的 Principle 仍然**不是**写作规则
- HIGH/LOW 的含义由 `support_definition` 字段显式说明

---

## 2. Explanation ABI

### 2.1 ExplanationConstraint — 受约束的解释数据结构

Explanation 不是自由文本，而是受约束的结构化数据。

```python
@dataclass
class ExplanationConstraint:
    """受约束的解释 — 只能包含结构层内容."""

    # 允许的字段
    observed_relationship: str              # 观察到什么结构关系
    structural_similarity: str              # 结构相似性描述
    cross_context_pattern: str              # 跨上下文出现的模式
    abstraction_path_description: str       # L0→L1/L2 的抽象路径

    # 引用锚点 (保持 ID 可解析)
    key_pattern_ids: List[str]              # 关键 Pattern IDs
    key_evidence_ids: List[str]             # 关键 Evidence IDs

    # 元信息
    format_version: str = "1.0"
```

### 2.2 Allowed Explanation Content

| 内容类型 | 格式约束 | 示例 |
|----------|----------|------|
| `observed_relationship` | 结构关系的陈述 | "Pattern A 和 B 均包含'信息隐藏→认知偏差'的结构" |
| `structural_similarity` | 共同结构的抽象 | "两组的共同底层结构是'受限信息+决策约束'而非表面情节相似" |
| `cross_context_pattern` | 跨上下文的一致性 | "同一结构在都市/玄幻/科幻类型中均出现" |
| `abstraction_path_description` | 抽象路径 | "从 3 组 Pattern (pat-a, pat-b, pat-c) 中提取共同结构" |

### 2.3 Forbidden Explanation Content

| 禁止内容 | 原因 | 示例 |
|----------|------|------|
| `this_works_because` | 有效性判断 | "这个机制有效是因为" |
| `reader_preference` | 读者偏好 | "读者喜欢这种" |
| `effectiveness_claim` | 效果断言 | "这种结构能提高" |
| `retention_claim` | 留存断言 | "增加读者留存" |
| `recommendation` | 推荐 | "建议使用" |
| `prescription` | 规定性语言 | "作者应该" |
| `quality_judgment` | 质量判断 | "优秀的叙事方式" |
| `commercial_claim` | 商业断言 | "这能带来市场成功" |
| `comparative_value` | 比较性价值 | "比其它方式更好" |

### 2.4 Forbidden Explanation Fields

```python
FORBIDDEN_EXPLANATION_FIELDS = {
    "this_works_because",
    "reader_preference_note",
    "effectiveness_claim",
    "retention_claim",
    "recommendation_note",
    "prescription_text",
    "quality_judgment",
    "commercial_claim",
    "comparative_value",
    "success_story",
}
```

### 2.5 Explanation ≠ Evaluation

```
正确:
  Explanation: "Pattern A 和 B 共享'信息受限+决策约束'的底层结构,
                跨作品(都市/玄幻)出现, Relation Graph 显示
                信息不对称→决策压力的因果链在两组中一致。"

错误:
  Explanation: "这是一个有效的叙事机制, 能够增强读者期待感,
                比传统单线叙事更好, 建议在关键情节使用。"
```

---

## 3. Evidence Chain Integrity

### 3.1 Minimum Chain Requirements

```
PrincipleCandidate
  └── InferenceRecord
        ├── ≥1 pattern_references      (每个可解析到 Pattern Registry)
        ├── ≥1 evidence_references     (每个可解析到 Evidence Chain)
        ├── ≥0 relation_path           (可选, 但有更完整)
        └── derivation_path 非空且不含禁止词
```

### 3.2 Integrity Rules

| 规则 | 违反后果 |
|------|----------|
| 每个 PatternRef.pattern_id 必须以 `pat-` 开头 | 格式不正确 |
| 每个 EvidenceRef.evidence_id 必须以 `ev-`/`e-` 开头 | 格式不正确 |
| InferenceRecord.candidate_id 必须对应存在的 PrincipleCandidate | 孤立记录 |
| derivation_path.observed_relationship 不能为空 | 不完整 |
| key_pattern_ids 必须与 pattern_references 匹配的子集 | 不一致 |
| key_evidence_ids 必须与 evidence_references 匹配的子集 | 不一致 |

### 3.3 Forbidden Chain States

```
InferenceRecord with 0 pattern_references     ❌ 无 Pattern 追踪
InferenceRecord with 0 evidence_references    ❌ 无 Evidence 追踪
InferenceRecord with all empty ExplanationConstraint  ❌ 无解释
ExplanationConstraint with all empty fields             ❌ 空解释
PatternRef.pattern_id not in Pattern Registry          ❌ 不可解析
```

---

## 4. Derivation Path Constraints

Explanation 中的 `derivation_path` 必须是受约束的文本，不含：

| 禁止模式 | 正则 |
|----------|------|
| 效果断言 | `"works.because"`, `"effective.because"` |
| 读者偏好 | `"reader.*like"`, `"audience.*prefer"` |
| 推荐用语 | `"should.*use"`, `"recommend"`, `"suggest"` |
| 比较级 | `"better.*than"`, `"more.*effective"` |
| 规定性 | `"author.*should"`, `"writer.*must"` |
| 质量 | `"good.*technique"`, `"excellent.*structure"` |

---

## 5. Phase14.4 → Phase14.5 Interface Freezing

§3 的输出是：

```
Evidence-backed Principle (PrincipleCandidate + InferenceRecord)
```

§3 的输出不是：

```
Writing Rule               ❌
Writing Prompt              ❌
Template                    ❌
Agent Instruction           ❌
Stylistic Configuration     ❌
Author Recommendation       ❌
```

### 5.1 Interface Type

```python
@dataclass
class Phase14Dot3Output:
    """Evidence Chain / Explanation ABI 的输出."""
    candidate: PrincipleCandidate          # 从 Phase14.4.2
    inference_record: InferenceRecord       # 本阶段的追踪记录
    explanation: ExplanationConstraint      # 受约束的解释

    # 明确禁止的字段
    # NO: quality_score, effectiveness, recommendation,
    #     writing_prompt, template, agent_instruction
```

---

## 6. Explanation ≠ LLM Reasoning Check

**关键禁止**: Explanation 不能仅基于 LLM 推理生成。必须基于可解析的引用链。

```python
def check_explanation_integrity(output: Phase14Dot3Output) -> List[str]:
    """检查解释完整性.

    验证:
    1. 所有引用 ID 有对应记录
    2. derivation_path 不含禁止内容
    3. key_pattern_ids 与 pattern_references 一致
    4. 没有仅基于 LLM 推理的内容
    """
    errors = []

    # 关键检查: pattern_references 必须在 inference_record 中可解析
    if not output.inference_record.pattern_references:
        errors.append("No pattern references in inference record")

    # key_pattern_ids 必须在 pattern_references 中
    pat_ref_ids = {p.pattern_id for p in output.inference_record.pattern_references}
    for pid in output.explanation.key_pattern_ids:
        if pid not in pat_ref_ids:
            errors.append(f"key_pattern_id {pid} not in pattern_references")

    # 类似检查 for evidence

    return errors
```

---

## 7. Boundary Guards

```python
# conftest guard — Phase14.4.3
def pytest_configure(config):
    """Guard: ExplanationConstraint must not have forbidden fields."""
    for field in FORBIDDEN_EXPLANATION_FIELDS:
        assert field not in ExplanationConstraint.__dataclass_fields__, (
            f"ExplanationConstraint must NOT have field: {field}"
        )
```

---

## 8. Example Flow

```
Input:
  PrincipleCandidate pc-a1b2 (Constrainted Information Decision Pressure, L2)
    ├── source_pattern_ids = ["pat-A", "pat-B", "pat-C"]
    └── source_evidence_ids = ["e-001", "e-002", "e-003"]

InferenceRecord ir-001:
  pattern_references:
    - {pattern_id: "pat-A", role: "primary_support", work_context: "都市职场"}
    - {pattern_id: "pat-B", role: "primary_support", work_context: "玄幻修炼"}
    - {pattern_id: "pat-C", role: "contextual", work_context: "科幻"}
  evidence_references:
    - {evidence_id: "e-001", support_type: "direct", confidence: HIGH}
    - {evidence_id: "e-002", support_type: "direct", confidence: MEDIUM}
    - {evidence_id: "e-003", support_type: "structural", confidence: MEDIUM}
  relation_path:
    - {relation_type: "reinforces", pattern_a_id: "pat-A", pattern_b_id: "pat-B", ...}

ExplanationConstraint:
  observed_relationship: >
    "Pattern A(信息隐藏) 和 B(信息隐藏+时间压力) 均导致
     角色决策路径中的认知偏差"
  structural_similarity: >
    "两组 Pattern 的共同底层结构是'受限信息环境→决策约束'"
  cross_context_pattern: >
    "同一结构在都市/玄幻/科幻类型中均出现"
  abstraction_path_description: >
    "从 3 组 Pattern 中提取的共同结构抽象, L0→L2"
  key_pattern_ids: ["pat-A", "pat-B", "pat-C"]
  key_evidence_ids: ["e-001", "e-002"]
```

---

**Document Author**: Hermes Agent (Phase14.4.2 → Phase14.4.3 transition)
**Freeze Date**: 2026-07-22
**Next Document Phase**: §14.4.4 Principle Validation
