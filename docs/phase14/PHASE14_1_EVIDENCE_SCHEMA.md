# Phase14.1 Evidence Schema v1.0（冻结版）

> Status: **FROZEN ❄️** — Phase14.1 Evidence Schema v1.0 approved 2026-07-22.

**定位**：OCOS 创作学习的"科学实验记录系统"——不是数据库表设计，而是定义**什么样的信息、经过什么证明过程、才有资格成为后续能力演化的输入**。

**核心公理**：
> Evidence describes observed patterns. Evidence does not define truth.
> 证据记录观察，不产生结论。

**关联铁律**：76, 77, 82, 83

---

## §0 Evidence Core Principle

**Evidence 的唯一职责**：将 Raw Text 中观察到的创作特征与效果，转化为可追溯、可验证、可质疑的结构化记录。

**允许**：
- 记录观察到的特征（句长分布、情感曲线、冲突结构）
- 记录特征产生的上下文（场景类型、角色状态、叙事阶段）
- 记录观察到的效果（读者留存变化、情绪峰值位置）
- 记录反例和替代解释

**禁止**：
- 生成结论（"这种写法更好"）
- 生成规则（"应该使用短句"）
- 生成推荐（"建议采用此模式"）
- 包含价值判断字段（`quality_score`, `is_good`, `should_use`）

---

## §1 EvidenceNode Schema

```python
@dataclass(frozen=True)
class EvidenceNode:
    """证据节点 — 从文本中观察到的创作特征的结构化记录。
    
    铁律约束：
    - 铁律76：不得直接成为创作规则
    - 铁律77：单作品经验不得升级为通用能力
    - 铁律82：矛盾证据必须保留
    - 铁律83：相关性≠因果
    """
    schema_version: int = 1
    
    # === 身份 ===
    evidence_id: UUID
    
    # === 来源 ===
    source_ref: SourceRef
    
    # === 类型 ===
    evidence_type: EvidenceType
    
    # === 观察内容 ===
    observation: ObservationPayload      # 结构化观察数据
    
    # === 特征向量 ===
    feature_vector: FeatureVector        # 数值化特征
    
    # === 上下文 ===
    context: ContextScope                # 观察发生的上下文
    
    # === 效果记录 ===
    observed_effect: ObservedEffect | None
    
    # === 质量信息 ===
    quality: EvidenceQuality
    
    # === 关系 ===
    related_evidence: tuple[UUID, ...]   # 支持性关联证据
    counter_evidence: tuple[UUID, ...]   # 相悖证据（铁律82）
    alternative_explanations: tuple[str, ...]  # 竞争性解释（铁律83）
    
    # === 时间 ===
    created_at: datetime
    extraction_method: str               # 提取方法标识
```

**禁止字段清单**（AST 检查强制）：
```python
FORBIDDEN_EVIDENCE_FIELDS = {
    "conclusion", "rule", "recommendation", "decision",
    "quality_score", "is_good", "should_use", "preference",
    "best_practice", "optimal", "correct", "wrong"
}
```

---

## §2 EvidenceType Schema — 五大类

### A. Text Micro Feature（文本微观特征）

```python
class TextMicroFeature(Enum):
    SENTENCE_LENGTH_PATTERN = "sentence_length_pattern"      # 句长分布与动态变化
    PUNCTUATION_PATTERN = "punctuation_pattern"              # 标点使用模式
    PARAGRAPH_RHYTHM = "paragraph_rhythm"                    # 段落长度与结构节奏
    DIALOGUE_RATIO = "dialogue_ratio"                        # 对话与叙述比例
    DESCRIPTION_RATIO = "description_ratio"                  # 描写类型分布
    LEXICAL_DIVERSITY = "lexical_diversity"                  # 词汇丰富度
    SYNTAX_COMPLEXITY = "syntax_complexity"                  # 句法复杂度
```

**SENTENCE_LENGTH_PATTERN 的 observation 结构**：
```python
{
    "mean_length": float,                    # 平均句长
    "variance": float,                       # 句长方差
    "distribution": {                        # 句长分布
        "ultra_short": float,                # 1-5字比例
        "short": float,                      # 6-12字比例
        "medium": float,                     # 13-24字比例
        "long": float,                       # 25-40字比例
        "ultra_long": float                  # 40+字比例
    },
    "dynamic_pattern": {                     # 句长动态变化
        "trend": str,                        # "shortening" | "lengthening" | "alternating" | "stable"
        "change_points": list[int]           # 变化发生的位置索引
    },
    "sample_size": int                       # 样本句子数
}
```

### B. Narrative Feature（叙事特征）

```python
class NarrativeFeature(Enum):
    CONFLICT_STRUCTURE = "conflict_structure"              # 冲突类型与强度变化
    INFORMATION_RELEASE = "information_release"            # 信息释放节奏
    FORESHADOW_PATTERN = "foreshadow_pattern"              # 伏笔埋设与回收模式
    PAYOFF_DISTANCE = "payoff_distance"                    # 伏笔回收距离
    VIEWPOINT_SWITCH = "viewpoint_switch"                  # 视角切换模式
    TIME_STRUCTURE = "time_structure"                      # 时间线结构（倒叙/插叙/线性）
```

**CONFLICT_STRUCTURE 的 observation 结构**：
```python
{
    "conflict_type_distribution": {          # 冲突类型分布
        "internal": float,                   # 内心冲突比例
        "interpersonal": float,              # 人际冲突比例
        "environmental": float,              # 环境冲突比例
        "societal": float                    # 社会冲突比例
    },
    "intensity_curve": list[float],          # 冲突强度曲线（章节级）
    "escalation_pattern": str,               # "gradual" | "spike" | "wave" | "staircase"
    "resolution_timing": {                   # 冲突解决时机
        "within_chapter": float,
        "within_arc": float,
        "across_arcs": float
    }
}
```

### C. Character Feature（人物特征）

```python
class CharacterFeature(Enum):
    CHARACTER_BEHAVIOR_CHANGE = "character_behavior_change"    # 行为模式变化
    RELATIONSHIP_SHIFT = "relationship_shift"                  # 关系网络演化
    EMOTIONAL_RESPONSE_PATTERN = "emotional_response_pattern"  # 情感反应模式
    MOTIVATION_CLARITY = "motivation_clarity"                  # 动机清晰度变化
    TRAIT_CONSISTENCY = "trait_consistency"                    # 人格一致性
```

### D. Reader Effect Feature（读者效果特征）

```python
class ReaderEffectFeature(Enum):
    COMPLETION_PATTERN = "completion_pattern"          # 完读率变化
    RE_READ_PATTERN = "re_read_pattern"                # 重读热点
    EMOTIONAL_PEAK_POSITION = "emotional_peak_position"  # 情绪峰值位置
    TENSION_ACCUMULATION = "tension_accumulation"      # 紧张感积累模式
    SATISFACTION_SIGNAL = "satisfaction_signal"        # 满意度信号
```

**关键约束**：只能记录 `reader_signal`，不能记录 `reader_preference_truth`。
- ✅ `completion_rate_change: +12%`
- ❌ `this_style_is_better`

### E. Style Feature（作者风格特征）

```python
class StyleFeature(Enum):
    STYLE_SIGNATURE = "style_signature"            # 风格指纹
    VOICE_PATTERN = "voice_pattern"                # 叙事声音模式
    HUMOR_PATTERN = "humor_pattern"                # 幽默类型与频率
    DESCRIPTION_STYLE = "description_style"        # 描写风格分类
    DIALOGUE_STYLE = "dialogue_style"              # 对白风格特征
```

---

## §3 SourceRef — 溯源规则

```python
@dataclass(frozen=True)
class SourceRef:
    """证据来源的精确定位。
    任何 Evidence 必须回答：你从哪里来的？
    """
    source_id: UUID                      # 作品/语料唯一ID
    source_type: SourceType              # 来源类型
    checksum: str                        # 原文内容 SHA256（前16字符）
    location: SourceLocation             # 精确定位
    extraction_method: str               # "manual" | "analyzer" | "imported"
    
class SourceType(Enum):
    NOVEL = "novel"
    CHAPTER = "chapter"
    CORPUS = "corpus"
    USER_INPUT = "user_input"

@dataclass(frozen=True)
class SourceLocation:
    chapter: int | None
    paragraph_range: tuple[int, int] | None
    sentence_range: tuple[int, int] | None
    scope: str  # "sentence" | "paragraph" | "scene" | "chapter" | "work"
```

**规则**：
- `checksum` 确保原文可验证。校验和不匹配时，Evidence 自动标记为 `needs_review`。
- `source_type` + `scope` 决定了该 Evidence 可以参与哪个层级的聚合。`"sentence"` 级的证据不能直接与 `"work"` 级的证据混合。

**示例（正确）**：
```
source: 某作品
chapter: 23
sentence: 430-520
pattern: sentence_length_mean=8.2
sample: 90 sentences
```

**示例（错误）**：
```
Evidence: 某作者喜欢短句  ← 无精确来源
```

---

## §4 EvidenceQuality — 质量评估

```python
@dataclass(frozen=True)
class EvidenceQuality:
    """证据质量 — 多维评估，非单一分数"""
    sample_size: int                     # 样本量
    source_diversity: int                # 来源多样性（不同作品数）
    consistency: float                   # 样本一致性（0-1）
    variance: float | None               # 统计方差
    contradiction_count: int             # 反例数量
    extraction_confidence: float         # 提取方法置信度（0-1）
```

**关键规则**：
- `source_diversity` 是区分"作者习惯"与"跨作品规律"的核心字段。
  - `source_diversity=1`：仅证明单个作品内的模式。
  - `source_diversity≥5`：才具备跨作品泛化的初步资格。
- `consistency` 高但 `source_diversity` 低 → 仅限该作品有效。
- `contradiction_count > 0` → 自动降低该 Evidence 在 Capability 形成中的权重。

---

## §5 Confidence Profile — 结构化置信度

```python
@dataclass(frozen=True)
class ConfidenceProfile:
    """结构化置信度 — 不产生单一权威数字"""
    sample_strength: str         # "insufficient" | "adequate" | "strong"
    cross_source_strength: str   # "single_source" | "few_sources" | "diverse_sources"
    stability: str               # "stable" | "moderate_variance" | "high_variance"
    contradiction_level: str     # "none" | "minor" | "significant" | "unresolved"
```

**输出格式**：
- ✅ `样本充分（n=500），但存在3类反例，矛盾等级：minor`
- ❌ `可信度95%`（单数字，容易产生权威感）

---

## §6 Evidence Lifecycle — 生命周期

```
CREATED ──→ VALIDATED ──→ LINKED ──→ USED_BY_CAPABILITY ──→ ARCHIVED
                │                    │
                ▼                    ▼
           INVALIDATED         DEPRECATED
```

**状态说明**：
- `CREATED`：初始提取，尚未通过质量校验。
- `VALIDATED`：通过 §7 的校验规则，具备进入 Evidence Graph 的资格。
- `LINKED`：已与其他 Evidence 建立关联（`related_evidence` / `counter_evidence`）。
- `USED_BY_CAPABILITY`：已被至少一个 Capability 引用。
- `ARCHIVED`：长期未被使用或已被更新 Evidence 替代，不参与默认查询。
- `INVALIDATED`：被证明存在方法错误（不可恢复）。
- `DEPRECATED`：因时效性或适用范围变化而不再推荐，但保留。

**关键规则**：
- **无 DELETE 状态**。Evidence 一旦写入，永久保留。
- `INVALIDATED` ≠ 删除。失效的 Evidence 仍然可查询，只是不参与 Capability 形成。

---

## §7 Evidence Storage Contract — 存储契约

```python
class EvidenceStore:
    """Evidence 存储接口 — 追加写入，不可删除，支持重建"""

    def append(self, evidence: EvidenceNode) -> EvidenceNode:
        """追加写入。写入后不可修改。通过 §8 校验后返回。"""

    def get(self, evidence_id: UUID) -> EvidenceNode | None:
        """按ID检索"""

    def query(self, filters: EvidenceQuery) -> list[EvidenceNode]:
        """按条件检索"""

    def link(self, source_id: UUID, target_id: UUID, relation: str) -> None:
        """建立证据间关联（related / counter）"""

    def archive(self, evidence_id: UUID) -> None:
        """归档（不删除）。归档后不参与默认查询。"""

    def invalidate(self, evidence_id: UUID, reason: str) -> None:
        """标记为失效（不删除）。需提供失效原因。"""

    def rebuild_from_works(self, work_ids: list[UUID]) -> int:
        """从原始作品重建全部 Evidence。返回重建数量。
        这是派生数据的核心保证——删除 Evidence Store 后可完整恢复。
        """
```

**允许的操作**：`ADD`, `LINK`, `ARCHIVE`, `INVALIDATE`
**禁止的操作**：`DELETE`, `OVERWRITE`, `ALTER_ORIGINAL`

更新操作通过"追加新 Evidence + 关联旧 Evidence + 归档旧 Evidence"实现，类似 Git 的不可变历史。

---

## §8 Validation Rules — 校验规则

在 `append()` 写入前强制执行：

| 编号 | 规则 | 拒绝动作 | 对应铁律 |
|------|------|----------|----------|
| EV-01 | `source_ref` 为空 → 拒绝 | 写入拒绝 | 可追溯 |
| EV-02 | 包含禁止字段（`recommendation`, `rule`, `quality_score` 等）→ 拒绝 | 写入拒绝 | 铁律76 |
| EV-03 | 执行删除操作 → 拒绝 | 操作拒绝 | 铁律82 |
| EV-04 | `counter_evidence` 为空且 `evidence_type` 为效果类 → 警告（不拒绝） | 警告标记 | 铁律83 |
| EV-05 | `source_diversity == 1` 且被用于 Capability → 标记为 `single_source_limited` | 标记 | 铁律77 |
| EV-06 | `sample_size < 5` → 拒绝 | 写入拒绝 | 统计有效性 |
| EV-07 | `checksum` 不匹配 → 标记 `needs_review` | 标记 | 可验证性 |
| EV-08 | `observation` 与 `evidence_type` 的 schema 不匹配 → 拒绝 | 写入拒绝 | 结构化 |

---

## §9 产出清单

| 文件 | 内容 |
|------|------|
| `contracts/evidence.py` | `EvidenceNode`, `SourceRef`, `EvidenceQuality`, `ConfidenceProfile`, `EvidenceType` 枚举 |
| `contracts/evidence_schemas.py` | 每种 `EvidenceType` 的 `observation` 结构定义与校验函数 |
| `reality/evidence_store.py` | `EvidenceStore` 实现（内存版，支持 `rebuild`） |
| `tests/kernel/test_evidence_contract.py` | 合约测试（frozen、禁止字段、类型匹配） |
| `tests/kernel/test_evidence_store.py` | 存储契约测试（追加、归档、失效、重建） |
| `tests/kernel/test_evidence_validation.py` | §8 校验规则测试（EV-01 ~ EV-08） |

---

*Phase14.1 Evidence Schema v1.0 已冻结 → 下一步：Phase14.2 Text Feature Extractor*
