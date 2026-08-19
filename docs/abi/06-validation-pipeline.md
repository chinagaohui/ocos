# OCOS Result Validation Pipeline v1.0

> Freeze Deliverable #4c — 冻结日期: 2026-07-25
> 覆盖: ResultUnderstandingLayer 三阶段管道

---

## 1. 管道架构

```
Agent Output (raw)
       │
       ▼
┌──────────────────────────────────────┐
│  Phase 1: VALIDATE                   │
│  ─────────────────                   │
│  StatementValidator.scan_all()        │
│  → ExaminationResult (passed/blocked) │
└──────────────┬───────────────────────┘
               │
               ▼
┌──────────────────────────────────────┐
│  Phase 2: STRUCTURE                  │
│  ────────────────────                │
│  Auto-extract metrics:              │
│  · quality_score                     │
│  · user_satisfaction                │
│  · duration_ms                       │
│  · content_summary (truncated)      │
│  → StructuredResult dataclass       │
└──────────────┬───────────────────────┘
               │
               ▼
┌──────────────────────────────────────┐
│  Phase 3: LEARN                      │
│  ──────────────                      │
│  ExperienceNode → ExperienceMemory   │
│  ExperienceNode → KnowledgeGraph     │
│  → ProcessedResult dataclass        │
└──────────────────────────────────────┘
```

---

## 2. 核心数据类型

### ExaminationResult (Phase 1 输出)

```python
@dataclass
class ExaminationResult:
    passed: bool              # 是否通过所有禁令检查
    violations: list[str]     # 违反的禁令名称列表
    severity: str             # "PASS" | "WARN" | "BLOCK"
    details: dict[str, Any]   # 详细匹配信息
    blocked: bool             # 是否应拦截
```

### StructuredResult (Phase 2 输出)

```python
@dataclass
class StructuredResult:
    capability_id: str        # 关联能力
    provider_id: str          # 关联 Provider
    outcome: str = "success"  # success | failure | partial
    quality_score: float = 0.0
    duration_ms: float = 0
    reliability: float = 0.0
    task_type: str = ""
    user_satisfaction: float = 0.0
    content_summary: str = "" # 截断到 200 字符
    raw_structure: dict = {}  # 原始提取数据
    is_success: bool          # outcome == "success"
```

### ProcessedResult (Phase 3 输出)

```python
@dataclass
class ProcessedResult:
    validated: bool           # Phase 1 通过
    structured: StructuredResult  # Phase 2 输出
    errors: list[str]         # 验证错误
    experience_stored: bool   # Phase 3 经验已写入
    kg_updated: bool          # Phase 3 KG 已更新
```

---

## 3. API 参考

```python
class ResultUnderstandingLayer:
    def __init__(self, 
        experience: CapabilityExperienceMemory | None = None,
        kg: KnowledgeGraph | None = None,
        auto_learn: bool = True,
        block_on_violation: bool = False,
    ): ...

    # Phase 1 — 验证
    def validate(self, output: str | dict) -> ExaminationResult: ...

    # Phase 2 — 结构化
    def structure(self, output: str | dict,
        capability_id: str = "", provider_id: str = "",
        outcome: str = "success", duration_ms: float = 0,
        task_type: str = "",
    ) -> StructuredResult: ...

    # Phase 3 — 学习
    def learn(self, structured: StructuredResult) -> dict[str, bool]:
        """返回 {'experience_stored': bool, 'kg_updated': bool}"""
        ...

    # 完整管道
    def process_result(self, output: str | dict,
        capability_id: str = "", provider_id: str = "",
        outcome: str = "success", duration_ms: float = 0,
        task_type: str = "", quality_score: float | None = None,
    ) -> ProcessedResult: ...
```

---

## 4. Quality Score 自动提取规则

`structure()` 会尝试从输出中自动提取 quality_score：

1. `output` 是 `dict` 时，按优先级查找：`quality_score` → `quality` → `score` → `satisfaction`
2. `output` 是 `str` 时，设为默认值 0.5
3. 也可以通过参数显式传入 `quality_score=`

### 提取优先级

| 字段名 | 优先级 | 说明 |
|-------|--------|------|
| `quality_score` | 1 (最高) | 直接匹配 |
| `quality` | 2 | 别名 |
| `score` | 3 | 通用评分 |
| `satisfaction` | 4 | user_satisfaction 映射 |
| `duration` | — | duration_ms 映射 |
| 显式参数 | 覆盖所有 | `quality_score=0.95` 覆盖自动提取 |

---

## 5. 集成点: AgentRuntime Tick Step 9

```python
def _tick_step_result_ingest(self) -> dict:
    """Step 9: Result Ingest — 结果反刍 (Phase 26 enhanced)"""
    
    # 记录基础经验 (Phase 22 兼容)
    self.experiences.record(situation=f"tick_{self._cycle_count}", ...)
    
    # Phase 26 pipeline
    try:
        pipeline = self.result_understanding_layer.process_result(f"tick_{self._cycle_count}")
        result["phase26_pipeline"] = {
            "validated": pipeline.validated,
            "experience_stored": pipeline.experience_stored,
            "kg_updated": pipeline.kg_updated,
        }
    except Exception:
        # pipeline 失败不阻塞 tick
        result["phase26_pipeline"] = {"error": "pipeline_failed"}
    
    result["recorded"] = True
    return result
```

---

## 6. 安全边界

1. **Phase 1 (Validate) 不可跳过**: 所有 Agent 输出必须通过 StatementValidator
2. **block_on_violation 默认 False**: 违规标记但不过滤 (透明模式)
3. **管道失败不阻断**: Phase 2/3 异常不中断 Tick 循环
4. **未来可切换 block_on_violation=True**: 无需修改调用方代码
