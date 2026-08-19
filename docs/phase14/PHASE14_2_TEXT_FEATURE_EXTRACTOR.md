# Phase14.2 Text Feature Extractor v1.0

> Status: **DRAFT 📝** — awaiting review.
>
> Phase14.1 Evidence Schema frozen → defining the Extractor layer.
>
> Critical boundary:
>
> ```
> Raw Text ↓ Feature Extraction ↓ Observation ↓ EvidenceNode ↓ Evidence Graph
>                          ↑
>                    Extractor stops here
> ```
>
> Extractor learns **WHAT exists**.
> Extractor never decides **WHAT it means**.

---

## §0 Core Principle — FROZEN

```
Extractor observes features, not meanings.
```

**三个禁止**（架构级，非仅校验级）：

| 禁止 | 含义 | 示例（错误） |
|------|------|-------------|
| Feature ≠ Principle | 特征不是规律 | "短句多" → "节奏快" ❌ |
| Feature ≠ Recommendation | 观察不是建议 | "句长12字" → "应该用短句" ❌ |
| Feature ≠ Quality Judgment | 描述不是评价 | "对白42%" → "对白比例优秀" ❌ |

**允许 / 禁止对照**：

```
✅ 第15章：平均句长 11.3 字
✅ 动作段落：连续短句比例 67%
✅ 对白占比：42%

❌ 该作者节奏优秀
❌ 应该增加短句
❌ 这种写法更商业化
```

---

## §1 Extractor ABI

### Interface

```python
@dataclass(frozen=True)
class RawText:
    """Extractor 的唯一输入 — 原始文本块"""
    text: str
    source_ref: SourceRef
    language: str = "zh"               # 当前限定中文
    encoding: str = "utf-8"

class FeatureExtractor(ABC):
    """统一 Extractor 接口。
    
    输入：Raw Text + SourceRef
    输出：EvidenceNode[]            ← 唯一出口
    
    禁止输出：Pattern, Principle, Capability, Suggestion
    """
    
    @property
    @abstractmethod
    def extractor_id(self) -> str:
        """全局唯一提取器标识，如 'micro_sentence_rhythm_v1'"""
    
    @property
    @abstractmethod
    def version(self) -> str:
        """语义版本号，用于 §9 版本追踪"""
    
    @abstractmethod
    def extract(
        self,
        source_text: RawText,
        source_ref: SourceRef
    ) -> list[EvidenceNode]:
        """执行特征提取。
        
        Args:
            source_text: 原始文本块
            source_ref:  来源引用（自动绑定到每个 EvidenceNode）
            
        Returns:
            零个或多个 EvidenceNode，每个代表一个独立观察。
            
        Raises:
            ExtractionError: 提取过程内部错误（非校验错误）
        """
```

### 禁止的出口模式

```python
# ❌ Extractor 不得输出的类型
FORBIDDEN_EXTRACTOR_OUTPUTS = {
    "Pattern",           # "短句-紧张正相关"
    "Principle",         # "快节奏场景应使用短句"
    "Capability",        # {capability: "tension_controller", params: {...}}
    "Suggestion",        # "建议增加短句比例"
    "QualityScore",      # {rhythm_score: 8.5}
    "Conclusion",        # "该段落使用了紧张节奏模式"
}
```

### Extractor Runtime Contract (NEW — FROZEN)

每个 Extractor 实例携带运行时元信息，确保进入 EvidenceStore 的每个 EvidenceNode 可追溯其生产环境和行为约束。

```python
@dataclass(frozen=True)
class ExtractorRuntimeInfo:
    """Extractor 运行时契约 — 每个 Evidence 都知道是谁产生的、怎么产生的、是否可复现。"""
    extractor_id: str
    extractor_version: str
    input_type: str                      # "RawText" | "PreprocessedText"
    output_type: str                     # 始终为 "list[EvidenceNode]"
    deterministic: bool                  # 是否确定性（EVX-06）
    observation_only: bool               # 是否纯观察（始终 True）
    allowed_evidence_types: tuple[str, ...]  # 该 Extractor 可产生的 EvidenceType
    created_at: datetime

    def as_extraction_method(self) -> str:
        """格式：extractor_id@version+deterministic"""
        det = "det" if self.deterministic else "nondet"
        return f"{self.extractor_id}@{self.extractor_version}+{det}"
```

### Extractor Registry

```python
@dataclass
class ExtractorRegistry:
    """所有已注册 Extractor 的集中管理"""
    extractors: dict[str, FeatureExtractor]
    
    def register(self, extractor: FeatureExtractor):
        assert extractor.extractor_id not in self.extractors or \
               self.extractors[extractor.extractor_id].version < extractor.version
        self.extractors[extractor.extractor_id] = extractor
    
    def get(self, extractor_id: str) -> FeatureExtractor | None:
        return self.extractors.get(extractor_id)
    
    def run_all(self, text: RawText, source_ref: SourceRef) -> list[EvidenceNode]:
        """串行运行所有注册的 Extractor，收集 EvidenceNodes"""
        results: list[EvidenceNode] = []
        for extractor in self.extractors.values():
            results.extend(extractor.extract(text, source_ref))
        return results
```

---

## §2 Extractor Pipeline

### Preprocessor Boundary Rule (FROZEN)

```
Preprocessor performs structural segmentation only.
Preprocessor does NOT perform semantic interpretation.
```

**允许**：
- 句子切分（按句号/问号/叹号/省略号）
- 段落切分（按换行/缩进）
- 对白识别（按引号/对话标记）
- 章节定位（按章节标题模式）

**禁止**：
- 情绪识别（"这段是悲伤的"）
- 冲突识别（"这是冲突场景"）
- 人物意图判断（"主角想复仇"）
- 任何语义标签（"高潮段" "铺垫段"）
- 任何价值判断（"关键信息" "核心情节"）

**违规后果**：语义污染提前进入 Feature Layer，直接使下游 Evidence Graph 失去可验证性。

### Observation Payload ABI (NEW — FROZEN)

为防止各 Extractor 自由定义 observation 格式导致未来无法统一，冻结统一指标格式：

```python
@dataclass(frozen=True)
class MetricObservation:
    """统一观察指标格式 — 所有 Extractor 的 observation 必须使用此类"""
    metric_name: str                     # 全局唯一指标名，如 "sentence_length_mean"
    metric_value: float | int            # 数值
    unit: str                            # 单位，如 "character", "ratio", "count", "count_per_1000chars"
    aggregation_method: str              # 聚合方法，如 "mean", "median", "sum", "distribution"
    sample_range: str                    # 样本范围，如 "chapter_001-010", "full_text"
```

**禁止的 observation 格式**（自由发挥，不受 Payload ABI 约束）：
```python
# ❌ 错误 — 不同 Extractor 各自定义
Extractor A: {"length": 12}
Extractor B: {"average_sentence_size": 12}
Extractor C: {"句长均值": 12.4}

# ✅ 正确 — 统一格式
{"metric_name": "sentence_length_mean", "metric_value": 12.4, 
 "unit": "character", "aggregation_method": "mean", "sample_range": "chapter_001-010"}
```

### Pipeline Flow (updated)

```
Raw Text
    │
    ▼ Preprocessor
    │  ├── sentence_segment()       按句号/问号/叹号/省略号分割
    │  ├── paragraph_segment()      按段落标记分割
    │  └── dialogue_mark()          " " " 标记对白区域
    ▼
Feature Extractors
    │
    ├── Micro Text Extractors (Phase14.2-A)
    │   ├── Sentence Rhythm          ← 第一批
    │   ├── Punctuation Pattern      ← 第一批
    │   ├── Paragraph Rhythm         ← 第一批
    │   ├── Dialogue Ratio           ← 第一批
    │   └── Description Ratio        ← 第二批
    │
    ├── Narrative Extractors (Phase14.2-B)
    │   ├── Conflict Structure
    │   ├── Information Release
    │   ├── Foreshadow Pattern
    │   └── Viewpoint Switch
    │
    ├── Character Extractors (推迟 — §5)
    │   └── (ABI only)
    │
    └── Style Extractors (推迟 — §6)
        └── (ABI only)
    │
    ▼ Evidence Validator
    │  EVX-01 ~ EVX-04 强制校验
    ▼
EvidenceStore.append()
```

### Preprocessor 职责

Preprocessor 的输出必须是 **结构化的、可重现的** 中间格式：

```python
@dataclass(frozen=True)
class PreprocessedText:
    """预处理后的结构化文本"""
    source_ref: SourceRef
    
    # 句子级
    sentences: list[SegmentedSentence]
    
    # 段落级
    paragraphs: list[SegmentedParagraph]
    
    # 对白标记
    dialogue_ranges: list[tuple[int, int]]      # sentence index ranges
    
    # 元信息
    preprocessing_version: str
    checksum: str

@dataclass(frozen=True)
class SegmentedSentence:
    index: int
    text: str
    char_count: int
    is_dialogue: bool           # 是否对白句
    paragraph_index: int        # 所属段落索引

@dataclass(frozen=True)
class SegmentedParagraph:
    index: int
    sentence_indices: tuple[int, ...]
    is_dialogue_heavy: bool     # 对白占比 > 60%
```

**关键约束**：
- Preprocessor 本身也是 Evidence 生产环节的一员 —— 其分段方式会影响所有下游 Extractor。
- Preprocessor 版本必须记录在 EvidenceNode 的 `extraction_method` 字段中。

---

## §3 TextMicroFeature Extractor — Phase14.2-A

### 3.1 Sentence Rhythm Extractor

**extractor_id**: `micro_sentence_rhythm_v1`

**输入依赖**: PreprocessedText

**观察内容**（仅统计，无标签）：

```python
{
    "evidence_type": "SENTENCE_RHYTHM",
    "observation": {
        "sentence_count": int,             # 总句子数
        "mean_length": float,              # 平均句长（字符）
        "median_length": float,            # 中位句长
        "variance": float,                 # 句长方差
        "length_distribution": {           # 句长分布
            "ultra_short_ratio": float,    # 1-5字
            "short_ratio": float,          # 6-12字
            "medium_ratio": float,         # 13-24字
            "long_ratio": float,           # 25-40字
            "ultra_long_ratio": float      # 40+字
        },
        "segment": str                     # "full_text" | "chapter" | "paragraph"
    }
}
```

**禁止输出**：
- ❌ `"fast_paced": true` — 这是解释
- ❌ `"rhythm_score": 8.5` — 这是评价
- ❌ `"style": "tense"` — 这是标签

### 3.2 Punctuation Pattern Extractor

**extractor_id**: `micro_punctuation_v1`

```python
{
    "evidence_type": "PUNCTUATION_PATTERN",
    "observation": {
        "comma_frequency": float,           # 每1000字逗号数
        "period_frequency": float,          # 每1000字句号数
        "question_frequency": float,        # 每1000字问号数
        "exclamation_frequency": float,     # 每1000字叹号数
        "ellipsis_frequency": float,        # 每1000字省略号数
        "dialogue_pause_markers": {         # 对白内停顿标记
            "dash_frequency": float,        # 破折号
            "comma_in_dialogue": float      # 对白内逗号
        },
        "segment": str
    }
}
```

### 3.3 Paragraph Rhythm Extractor

**extractor_id**: `micro_paragraph_rhythm_v1`

```python
{
    "evidence_type": "PARAGRAPH_RHYTHM",
    "observation": {
        "paragraph_count": int,
        "mean_sentences_per_paragraph": float,
        "paragraph_length_distribution": {
            "very_short_ratio": float,      # 1句段
            "short_ratio": float,           # 2-3句段
            "medium_ratio": float,          # 4-6句段
            "long_ratio": float,            # 7+句段
        },
        "short_paragraph_ratio": float,     # 1-2句段占比
        "long_paragraph_ratio": float,      # 6+句段占比
        "segment": str
    }
}
```

### 3.4 Dialogue Ratio Extractor

**extractor_id**: `micro_dialogue_ratio_v1`

```python
{
    "evidence_type": "DIALOGUE_RATIO",
    "observation": {
        "dialogue_char_count": int,
        "narration_char_count": int,
        "inner_monologue_char_count": int,
        "dialogue_ratio": float,            # 对白字符占比
        "narration_ratio": float,           # 叙述字符占比
        "inner_monologue_ratio": float,     # 内心独白字符占比
        "dialogue_by_paragraph": {          # 各段对白占比
            "dialogue_heavy_ratio": float,  # >60%段的比例
            "narration_heavy_ratio": float, # <20%段的比例
            "mixed_ratio": float            # 20-60%段的比例
        },
        "segment": str
    }
}
```

### 3.5 Description Ratio Extractor (Phase14.2-A 可选)

**extractor_id**: `micro_description_ratio_v1`

```python
{
    "evidence_type": "DESCRIPTION_RATIO",
    "observation": {
        "total_description_chars": int,
        "description_categories": {
            "environment_ratio": float,     # 环境描写
            "action_ratio": float,          # 动作描写
            "psychological_ratio": float,   # 心理描写
            "dialogue_stage_ratio": float   # 对白场景布置
        },
        "description_density": float,       # 描写字符/总字符
        "segment": str
    }
}
```

---

## §4 NarrativeFeature Extractor — Phase14.2-B

### 4.1 Conflict Structure Extractor

**extractor_id**: `narrative_conflict_v1`

**注意**：此处提取的是**可计算的叙事结构特征**，不是**剧情分析**。

```python
{
    "evidence_type": "CONFLICT_STRUCTURE",
    "observation": {
        "conflict_event_count": int,
        
        # 冲突间隔（按段落计）
        "conflict_intervals": list[int],
        "mean_conflict_interval": float,
        "min_conflict_interval": float,
        "max_conflict_interval": float,
        
        "conflict_type_distribution": {
            # 仅记录 type 出现次数，不判断优劣
            "interpersonal_count": int,
            "internal_count": int,
            "environmental_count": int,
            "societal_count": int
        },
        
        "segment": str
    }
}
```

**禁止输出**：
- ❌ `"conflict_intensity": "high"` — 强度标签需由上游 Knowledge 层推断
- ❌ `"conflict_density_is_good"` — 价值判断

### 4.2 Information Release Extractor

```python
{
    "evidence_type": "INFORMATION_RELEASE",
    "observation": {
        # 新信息出现的数量与位置（按段落计）
        "new_information_count": int,
        "new_information_positions": list[int],
        
        # 信息跨度
        "information_spans": list[tuple[int, int]],
        "mean_information_span": float,     # 信息从出现到补充的平均距离
        
        "segment": str
    }
}
```

**注释**：所谓的"伏笔"在此阶段 = 一个信息出现后，在后续章节被再次引用或补充。引用位置 = payoff。这不是语义判断，而是文本距离计算。

### 4.3 Foreshadow Pattern Extractor

```python
{
    "evidence_type": "FORESHADOW_PATTERN",
    "observation": {
        "setup_count": int,                 # 作者显式标记的伏笔设置点数量
        "payoff_count": int,                # 伏笔回收点数量
        "unresolved_count": int,            # 未回收数量（截止到当前文本）
        
        "distances": list[float],           # 设置-回收距离（章节数）
        "mean_distance": float,
        "min_distance": float,
        "max_distance": float,
        
        "segment": str
    }
}
```

**注意**：真正的伏笔识别（语义级）属于 Knowledge 层。此 Extractor 仅记录**在文本中可定位的 setup-payoff 关联对**。

### 4.4 Viewpoint Switch Extractor

```python
{
    "evidence_type": "VIEWPOINT_SWITCH",
    "observation": {
        "switch_count": int,
        "switch_positions": list[int],      # 切换位置的章节/段落索引
        "chapter_switch_pattern": {         # 章节级视角分布
            "single_pov_chapters": int,
            "multi_pov_chapters": int
        },
        "segment": str
    }
}
```

---

## §5 CharacterFeature Extractor — ABI Only

### 原因：推迟实现

人物模型依赖：

```
Entity extraction         — 命名实体识别
Dialogue attribution     — "谁说了什么" 指代消解
State tracking           — 状态变化跟踪（多章节）
```

复杂度明显高于文本特征。Phase14.2 只定义 ABI。

### ABI

```python
class CharacterFeatureExtractor(FeatureExtractor):
    """Character Feature Extractor ABI。
    
    实现推迟到 Phase14.2-C 或后续独立阶段。
    
    当前约束：
    - 不包含实体识别
    - 不包含情感分析
    - 仅设计观察维度
    """
    
    pass  # ABI only — implementation deferred
```

**预定义的观察维度**（将来实现）：

```python
CHARACTER_OBSERVATION_DIMENSIONS = {
    "BEHAVIOR_PATTERN",        # 行为模式：动作/对白/心理的比例变化
    "RELATIONSHIP_SIGNAL",     # 关系信号：共同出现频率、对白交互次数
    "EMOTION_CURVE",           # 情感曲线：正面/负面标记词的分布
    "MOTIVATION_MARKER",       # 动机标记：目标陈述的出现
    "TRAIT_INDICATOR",         # 特质指示器：特定行为模式的出现频率
}
```

---

## §6 StyleFeature Extractor — ABI Only

### 定位

这是未来实现"作者风格能力"的关键。

但必须避免：**"模仿作者"**。

Phase14.2 只定义观察维度。

### 第一阶段观察：STYLE_SIGNATURE

```python
# 仅统计层面，无"风格标签"
STYLE_SIGNATURE_OBSERVATIONS = {
    "sentence_pattern": {                   # 句首/句尾模式
        "sentence_start_types": dict,       # "主语开头" vs "状语开头" vs "对白开头"
        "sentence_end_types": dict      # "句号" vs "省略号" vs "叹号"
    },
    "dialogue_style": {                     # 对白模式
        "attribution_pattern": dict,        # "XX说" vs "说XX" vs 无引导
        "dialogue_length_distribution": dict
    },
    "description_style": {
        "sensory_detail_density": float,    # 感官细节密度（视觉/听觉/触觉词汇比例）
        "abstract_vs_concrete_ratio": float # 抽象描述 vs 具体描述
    },
    "humour_marker": {
        "humour_marker_types": list,        # 特定幽默标记（如反讽引号、夸张副词）
        "frequency": float
    },
    "emotion_expression": {
        "direct_emotion_words": list,       # 直接情感词出现频率
        "indirect_emotion_cues": list       # 间接情感线索（行为描述）
    }
}
```

---

## §7 SourceRef Auto-Binding

每个 EvidenceNode 必须自动绑定 SourceRef。Extractor 不自创 SourceRef — 由 Pipeline 传入。

```python
@dataclass(frozen=True)
class ExtractedSourceRef:
    """由 Pipeline 自动生成的 SourceRef 绑定"""
    source_id: UUID
    source_type: SourceType
    checksum: str                        # RawText 的 SHA256（前16字符）
    location: SourceLocation             # 由 Preprocessor 定位
    extractor_info: ExtractorInfo        # 由 Extractor 注册信息生成

@dataclass(frozen=True)
class ExtractorInfo:
    """记录哪个 Extractor 提取了此 Evidence"""
    extractor_id: str
    extractor_version: str
    preprocessing_version: str
```

**绑定流程**：

```
Pipeline receives RawText + SourceRef
    │
    ▼
Preprocessor → PreprocessedText + mapped SourceLocation
    │
    ▼
Extractor receives PreprocessedText
    │
    ▼
EvidenceNode created with:
    source_ref.source_id = RawText.source_ref.source_id
    source_ref.source_type = RawText.source_ref.source_type
    source_ref.checksum = sha256(RawText.text)[:16]
    source_ref.location = derived from PreprocessedText
    source_ref.extraction_method = f"{extractor_id}@{extractor_version}+preprocess@{preprocess_version}"
```

**未来价值**：

```
重新分析时，可比较：
Extractor v1 产生的 Evidence
vs
Extractor v2 产生的 Evidence

两项都保留，不覆盖。
```

---

## §8 Validation Layer — EVX Rules

在 EvidenceNode 写入 EvidenceStore 前，必须经过 `EvidenceValidator`。

### Validation Rules

| 编号 | 规则 | 拒绝动作 | 检查时机 |
|------|------|----------|---------|
| **EVX-01** | 禁止解释字段：`quality`, `better`, `optimal`, `recommended` | 写入拒绝 | 字段名 + 值内容检查 |
| **EVX-02** | 禁止能力字段：`style_should`, `apply_rule`, `generate_with` | 写入拒绝 | 字段名检查 |
| **EVX-03** | 必须包含完整 SourceRef（source_id + checksum + location） | 写入拒绝 | SourceRef 完整字段 |
| **EVX-04** | 必须 observation-only：`observation` 外无额外自解释字段 | 写入拒绝 | `EvidenceNode.__dataclass_fields__` 检查 |
| **EVX-05** | Extractor Isolation — 输出不得包含 `capability`, `principle`, `recommendation` | 写入拒绝 | 全字段递归检查 |
| **EVX-06** | Source Determinism — 同一输入 + 同一版本 → 同一输出 | 测试断言 | 单元测试对比 |
| **EVX-07** | Schema Purity — observation 内不得混入未来层字段（`impact`, `meaning`, `purpose`, `emotion_effect` 等） | 写入拒绝 | observation 字段名 + 值内容递归检查 |

### Validator

```python
class EvidenceValidator:
    """Extractor 输出的 EvidenceNode 校验器"""
    
    # 递归检查的关键词 — EVX-05
    FORBIDDEN_CAPABILITY_WORDS = {
        "capability", "principle", "recommendation",
        "style_should", "apply_rule", "generate_with"
    }
    
    def validate(self, node: EvidenceNode) -> ValidationResult:
        """验证单个 EvidenceNode。返回通过 / 拒绝 + 原因。"""
        violations = []
        
        # EVX-01
        for field, value in node.__dict__.items():
            self._check_interpretation_field(field, value, violations)
        
        # EVX-02
        for field, value in node.__dict__.items():
            self._check_capability_field(field, value, violations)
        
        # EVX-03
        self._check_source_ref(node.source_ref, violations)
        
        # EVX-04
        self._check_observation_only(node, violations)
        
        # EVX-05 — 递归检查全字段
        self._check_extractor_isolation(node, violations)
        
        if violations:
            return ValidationResult(passed=False, violations=violations)
        return ValidationResult(passed=True)
    
    def _check_interpretation_field(self, field: str, value: Any, violations: list):
        """检查是否包含解释类字段"""
        if field.lower() in FORBIDDEN_INTERPRETATION_WORDS:
            violations.append(Violation("EVX-01", f"Forbidden interpretation field: {field}"))
    
    def _check_capability_field(self, field: str, value: Any, violations: list):
        """检查是否包含能力类字段"""
        if field.lower() in FORBIDDEN_CAPABILITY_WORDS:
            violations.append(Violation("EVX-02", f"Forbidden capability field: {field}"))
    
    def _check_source_ref(self, ref: SourceRef, violations: list):
        """检查 SourceRef 完整性"""
        if ref.source_id is None or ref.checksum is None or ref.location is None:
            violations.append(Violation("EVX-03", "Missing required SourceRef fields"))
    
    def _check_observation_only(self, node: EvidenceNode, violations: list):
        """检查是否仅包含 observation 数据"""
        allowed_fields = {
            "schema_version", "evidence_id", "source_ref", "evidence_type",
            "observation", "feature_vector", "context", "observed_effect",
            "quality", "related_evidence", "counter_evidence",
            "alternative_explanations", "created_at", "extraction_method"
        }
        unexpected = set(node.__dict__.keys()) - allowed_fields
        if unexpected:
            violations.append(Violation("EVX-04", f"Unexpected non-observation fields: {unexpected}"))
    
    def _check_extractor_isolation(self, node: EvidenceNode, violations: list):
        """EVX-05: 递归检查所有字段值是否包含 capability/principle/recommendation
        防止未来开发人员将推理层数据绕道塞入 Extractor 输出。
        """
        def _recurse(value, path: str):
            if isinstance(value, str):
                lower = value.lower()
                for keyword in self.FORBIDDEN_CAPABILITY_WORDS:
                    if keyword in lower:
                        violations.append(Violation(
                            "EVX-05",
                            f"Extractor isolation breach: '{keyword}' found in field '{path}'"
                        ))
            elif isinstance(value, dict):
                for k, v in value.items():
                    _recurse(k, f"{path}.{k}")
                    _recurse(v, f"{path}.{k}")
            elif isinstance(value, (list, tuple)):
                for i, v in enumerate(value):
                    _recurse(v, f"{path}[{i}]")
        
        _recurse(node.__dict__, "root")


# EVX-06 — Source Determinism: 同一输入 + 同一版本 → 同一输出
# 不在运行时校验，而是在单元测试中通过哈希对比断言实现：
#
# def test_evx_06_source_determinism(extractor_v1, sample_text, sample_ref):
#     """同一文本 + 同一版本 → 每次输出相同"""
#     result_1 = extractor_v1.extract(sample_text, sample_ref)
#     result_2 = extractor_v1.extract(sample_text, sample_ref)
#     hash_1 = hashlib.sha256(str(result_1).encode()).hexdigest()
#     hash_2 = hashlib.sha256(str(result_2).encode()).hexdigest()
#     assert hash_1 == hash_2, "Extractor v1 output is not deterministic"
#     assert len(result_1) == len(result_2), "Extractor v1 output count changed"
```

---

## §9 Extractor Versioning

### 为什么必须版本化

因为未来：

```
旧分析不能覆盖
```

例如：

```
Extractor v1: 仅基于字符长度统计句长（"。" "！" "？" 分割）
Extractor v2: 加入语法树分析，能区分复合句和省略句
```

两个版本的输出**都保留**。这使 Evidence Graph 可以：

- 追踪分析精度提升对下游的影响
- 在退化场景下回退到旧版 Evidence
- 比较新旧版差异

### 版本策略

```python
# Extractor 版本格式：semver
extractor_version = f"{major}.{minor}.{patch}"

# major: 破坏性变更（segmentation 策略变化）
# minor: 非破坏性增强（新增观察字段）
# patch: 修复（bug fix，不影响输出结构）

# Preprocessor 版本格式独立
preprocess_version = f"{major}.{minor}.{patch}"
```

### EvidenceNode 中的版本记录

```python
# extraction_method 字段自动记录
extraction_method = f"sentence_rhythm@1.0.0+preprocess@1.0.0"

# 查询时可指定版本
store.query(filters=EvidenceQuery(
    extraction_method="sentence_rhythm@1.0.0+preprocess@1.0.0"
))
```

---

## §10 Implementation Scope — Phase14.2-A / B / C

### Phase14.2-A（第一批 — 最小闭环）

**优先级**：立即实现。

| 组件 | 产出 |
|------|------|
| Preprocessor | 句子分割、段落分割、对白标记 |
| Sentence Rhythm Extractor | SENTENCE_RHYTHM 输出 |
| Punctuation Pattern Extractor | PUNCTUATION_PATTERN 输出 |
| Paragraph Rhythm Extractor | PARAGRAPH_RHYTHM 输出 |
| Dialogue Ratio Extractor | DIALOGUE_RATIO 输出 |
| Extractor ABI Base | `FeatureExtractor` 抽象基类 |
| Extractor Registry | 注册 + run_all |
| EvidenceValidator | EVX-01 ~ EVX-04 |
| SourceRef Auto-Binder | ExtractedSourceRef 自动生成 |
| 产出文件 | `contracts/extractor_abi.py`, `contracts/extractor_evx.py` |
| 产出文件 | `reality/extractors/micro_text/` 各 Extractor 实现 |
| 产出文件 | `reality/evidence_validator.py` |
| 产出文件 | `tests/extractors/test_micro_text_extractors.py` |

**验证标记**：
- 提取后的 EvidenceNode 通过 `Phase14.1 Evidence Schema` 的 §8 校验规则（EV-01 ~ EV-08）
- 提取后的 EvidenceNode 通过本节 EVX-01 ~ EVX-07 校验规则
- Observation Payload 不违反 MetricObservation ABI
- EVX-06: 同一输入 + 同一版本 → 同一输出（单元测试断言）
- ExtractorRuntimeInfo 随每个注册的 Extractor 绑定

### PH14.2-A Gate Criteria

Phase14.2-A 实现的冻结条件：

| # | 条件 | 验证方式 |
|---|------|----------|
| G1 | Extractor ABI tests PASS | `pytest tests/contracts/test_extractor_abi.py` |
| G2 | Preprocessor 无语义污染（仅 structural segmentation） | 代码审查 + 测试断言 |
| G3 | 所有 EvidenceNode 包含完整 SourceRef | EVX-03 强制 |
| G4 | 同版本同输入 → hash 一致（deterministic） | EVX-06 单元测试 |
| G5 | 输出无法产生 Principle / Capability / Recommendation 字段 | EVX-05 + EVX-07 强制 |
| G6 | 删除 Extractor 后 Evidence Schema 不变化 | 删除注册 → Phase14.1 测试不变 |
| G7 | Phase 0-13 无任何变化 | `git diff --stat docs/phase*/ contracts/*/` |

### Phase14.2-B1 — Narrative Structure Observation（第一批 B 阶段）

**状态**：边界合约已签署 ✅ — 可进入实施。

**优先级**：Phase14.2-A 冻结后立即进入。

| 组件 | 产出 |
|------|------|
| B1-A: Event Boundary Extractor | EVENT_BOUNDARY 输出（首批实施） |
| B1-B: Information Distribution Extractor | INFORMATION_DISTRIBUTION 输出 |
| B1-C: Scene Rhythm Extractor | SCENE_RHYTHM 输出 |
| B1-D: Foreshadow Distance Extractor | FORESHADOW_DISTANCE 输出 |
| Narrative Observation Boundary Contract | `docs/phase14/PHASE14_2_B1_NARRATIVE_BOUNDARY.md` ✅ APPROVED |

**约束**：
- 输出仍为 `EvidenceNode`（Phase14.1 Schema）
- 无 interpretation / quality / recommendation 字段（EVX-01~07 继承）
- SourceRef 完整（EVX-03 继承）
- Deterministic（EVX-06 继承）
- 不修改 Phase14.1 Schema

**入口条件**：
1. Phase14.2-A FROZEN ✅
2. Narrative Observation Boundary Contract 批准 📝
3. EVX-01~07 继承验证通过

### Phase14.2-B2 — Narrative Relation Extraction（第二批 B 阶段）

**优先级**：B1 稳定后进入。

| 组件 | 产出 |
|------|------|
| Event Node → Relation Edge Extractor | NARRATIVE_GRAPH 输出 |
| Relation Type Classifier | causal / temporal / referential |

**约束**：
- 关系提取仍保持结构纯观察
- 不添加语义评价字段
- 继承 B1 全部边界约束

### Phase14.2-C（推迟）

| 组件 | 备注 |
|------|------|
| CharacterFeature ABI + Extractor | 需先有 Entity + Dialogue Attribution 基础设施 |
| StyleFeature ABI + Extractor | 需先有 Stable Extractor v2 基础 |

---

## Consistency Check

| Phase14.1 Evidence Schema | Phase14.2 Text Feature Extractor | Status |
|--------------------------|----------------------------------|--------|
| §0 核心原则：Evidence describes observation | §0 核心原则：Extractor observes features, not meanings | ✅ 一致 |
| §1 EvidenceNode 禁止字段 | §8 EVX-01/02 禁止解释/能力字段 | ✅ 强制执行 |
| §2 五大 EvidenceType | §3-6 对应 Extractor 定义 | ✅ 逐类对应 |
| §3 SourceRef | §7 SourceRef Auto-Binding | ✅ 自动绑定 |
| §8 EV-01~08 校验 | §8 EVX-01~04 Extractor 校验 | ✅ 两层校验 |
| 不可变历史 | §9 版本化，新旧保留 | ✅ 一致 |
| 先证据后能力 | §0 三禁止：Principle/Recommendation/Judgment | ✅ 边界冻结 |

---

## Freeze Metadata

```
Document:            Phase14.2 Text Feature Extractor v1.1
Preceded by:         Phase14.1 Evidence Schema v1.0 (FROZEN ❄️)
Contains:            §0 Core Principle, §1 Extractor ABI + Runtime Contract
                     §3-6 Extractor Specs, §7 SourceRef, §8 Validator (EVX-01~07)
                     §9 Versioning, §10 Phased Implementation + Gate Criteria
                     + Observation Payload ABI (NEW)
                     + Preprocessor Boundary Rule (NEW)
                     + ExtractorRuntimeContract (NEW)
                     + EVX-05~07: Isolation + Determinism + Schema Purity
Status:              ✅ FROZEN ❄️ — v1.1+ approved 2026-07-22
Created:             2026-07-22
Next:                Phase14.2-A implementation — Micro Text Extractors
```

---

*Extractor observes features, not meanings.*
