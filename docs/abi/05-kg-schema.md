# OCOS Knowledge Graph Schema v1.0

> Freeze Deliverable #4b — 冻结日期: 2026-07-25
> 覆盖: KnowledgeGraph 节点/边模型、ExperienceMemory 表结构

---

## 1. 数据模型

### 1.1 节点类型

OCOS Knowledge Graph 有三种节点：**Capability**（能力）、**Provider**（提供者）、**Experience**（经验）。

```python
@dataclass
class CapabilityNode:
    id: str            # 唯一标识 (e.g. "code_gen")
    domain: str        # 领域 (e.g. "coding", "testing", "image")
    constraints: dict = {}  # 约束 {"max_tokens": 4096, "timeout": 30}

@dataclass
class ProviderNode:
    id: str            # 唯一标识 (e.g. "codex", "local_python")
    capabilities: tuple[str, ...]  # 提供的能力 ID 列表
    protocol: str      # "subprocess" | "http" | "grpc" | "inproc"
    health: float = 1.0  # 健康度 [0, 1]
    weight: float = 1.0  # 基础权重
    metadata: dict = {}  # {"endpoint": "...", "version": "1.0"}

@dataclass
class ExperienceNode:
    experience_id: str  # 唯一标识
    task_type: str      # 任务类型 (e.g. "code_generation", "testing")
    capability_id: str  # 关联 Capability
    provider_id: str    # 关联 Provider
    success: bool       # 成功/失败
    quality_score: float # 质量评分 [0, 1]
    duration_ms: int    # 执行耗时 (ms)
    reliability: float  # 可靠性评分 [0, 1]
    timestamp: float    # Unix 时间戳
    metadata: dict = {} # 扩展字段
```

### 1.2 边类型

```
Provider ──PROVIDES──→ Capability  (提供关系)
Provider ←──PROVIDED_BY── Capability  (逆向)
Capability ──REQUIRES──→ Capability  (依赖关系)
Experience ──INSTANCE_OF──→ Capability  (经验所属)
```

---

## 2. ExperienceMemory 表结构 (SQLite)

```sql
CREATE TABLE IF NOT EXISTS experiences (
    experience_id TEXT PRIMARY KEY,
    task_type TEXT NOT NULL,
    capability_id TEXT NOT NULL,
    provider_id TEXT NOT NULL,
    success INTEGER NOT NULL,        -- 0 or 1
    quality_score REAL NOT NULL,     -- [0.0, 1.0]
    score REAL NOT NULL,             -- alias for quality_score
    duration_ms INTEGER NOT NULL,
    reliability REAL NOT NULL,       -- [0.0, 1.0]
    latency REAL NOT NULL,           -- seconds, derived from duration_ms
    timestamp REAL NOT NULL,
    metadata TEXT DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_exp_capability ON experiences(capability_id);
CREATE INDEX IF NOT EXISTS idx_exp_provider ON experiences(provider_id);
CREATE INDEX IF NOT EXISTS idx_exp_task_type ON experiences(task_type);
CREATE INDEX IF NOT EXISTS idx_exp_success ON experiences(success);
CREATE INDEX IF NOT EXISTS idx_exp_timestamp ON experiences(timestamp);
```

### 查询维度

```python
class CapabilityExperienceMemory:
    def save(self, node: ExperienceNode) -> None: ...
    def query_by_capability(self, capability_id: str, limit: int = 50) -> list[dict]: ...
    def query_by_provider(self, provider_id: str, limit: int = 50) -> list[dict]: ...
    def query_by_task_type(self, task_type: str, limit: int = 50) -> list[dict]: ...
    def query_combined(self, capability_id: str, provider_id: str, 
                        min_success: bool = True, limit: int = 50) -> list[dict]: ...
    def get_stats(self, capability_id: str | None = None,
                  provider_id: str | None = None) -> dict: ...
```

### Stats 返回格式

```python
{
    "total": 42,
    "success_count": 38,
    "failure_count": 4,
    "success_rate": 0.9048,
    "avg_quality": 0.87,
    "avg_latency": 342.0,        # ms
    "avg_reliability": 0.91,
}
```

---

## 3. 评分公式

```python
# SelectionEngine 综合评分
score = kg_score * 0.3      # KG 固有权重
      + exp_score * 0.3     # 经验平均分
      + constraints_bonus * 0.4  # Provider weight * 约束匹配度

# threshold = 0.5  (默认)
# recovery_threshold = 0.3  (恢复模式，允许低分 Provider)
```

---

## 4. JSON Schema (用于验证)

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "ocos-knowledge-graph-v1",
  "type": "object",
  "properties": {
    "capabilities": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["id", "domain"],
        "properties": {
          "id": {"type": "string"},
          "domain": {"type": "string"},
          "constraints": {"type": "object"}
        }
      }
    },
    "providers": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["id", "capabilities", "protocol"],
        "properties": {
          "id": {"type": "string"},
          "capabilities": {"type": "array", "items": {"type": "string"}},
          "protocol": {"type": "string", "enum": ["subprocess", "http", "grpc", "inproc"]},
          "health": {"type": "number", "minimum": 0, "maximum": 1},
          "weight": {"type": "number", "minimum": 0}
        }
      }
    },
    "edges": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["source", "type", "target"],
        "properties": {
          "source": {"type": "string"},
          "type": {"type": "string", "enum": ["PROVIDES", "PROVIDED_BY", "REQUIRES", "INSTANCE_OF"]},
          "target": {"type": "string"}
        }
      }
    }
  }
}
```
