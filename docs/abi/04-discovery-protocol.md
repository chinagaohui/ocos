# OCOS Discovery Protocol v1.0

> Freeze Deliverable #4a — 冻结日期: 2026-07-25
> 覆盖: CapabilityRegistry.discover(), CapabilityDescriptor 自动发现

---

## 1. 概述

OCOS 的能力发现是一个**两阶段过程**：

```
Phase 1 (Registry Lookup)  → CapabilityRegistry.discover(capability_id)
Phase 2 (Selection)        → CapabilitySelector.rank() → SelectionEngine.select_top()
```

### 核心参与者

| 组件 | 职责 | 文件 |
|-----|------|------|
| CapabilityDescriptor | 能力声明 (dataclass) | `ocos/capability/descriptor.py` |
| CapabilityRegistry | 注册中心 (dict-based) | `ocos/capability/registry.py` |
| CapabilityProvider | 提供者发现 + 汇总 | `ocos/capability/provider.py` |
| CapabilitySelector | 评分排序 (weighted) | `ocos/capability/selector.py` |
| SelectionEngine | KG + 经验综合选择 | `ocos/capability/selection_engine.py` |

---

## 2. CapabilityDescriptor

能力声明的不可变数据结构。

```python
@dataclass(frozen=True)
class CapabilityDescriptor:
    capability_id: str          # 能力唯一标识
    domain: str                 # 领域: coding / image / data / browser / testing / search
    actions: tuple[str, ...]    # 动作: generate / analyze / edit / review / execute / test / search
    input_types: tuple[str, ...]  # 输入: text / code / image / data / command
    output_types: tuple[str, ...] # 输出: text / code / image / data
    params: dict[str, Any] = {}   # JSON Schema 参数
    tags: tuple[str, ...] = ()    # 标签: fast / reliable / experimental / batch / streaming
```

### 标准能力清单

| capability_id | domain | actions | 对应 Provider |
|--------------|--------|---------|-------------|
| code_gen | coding | generate, review | codex, local_python, gpt_engineer |
| code_review | coding | analyze, review | codex, local_python |
| test_gen | testing | generate, execute | local_python, codex |
| data_analysis | data | analyze, execute | local_python |
| web_search | search | search | browser_agent |
| image_gen | image | generate | dalle_proxy |

---

## 3. Discovery 流程

### 3.1 Registry Lookup

```python
class CapabilityRegistry:
    """能力注册中心 (thread-safe dict-based)。"""
    
    def discover(self, capability_id: str) -> list[CapabilityProvider]:
        """返回给定能力的所有 Provider (按 weight 降序)。"""
        ...
    
    def discover_all(self) -> dict[str, list[CapabilityProvider]]:
        """返回所有已注册的能力 → Provider。"""
        ...
```

### 3.2 Provider Selection (CapabilitySelector)

```python
class CapabilitySelector:
    """能力选择器 — 基于权重 + 标签的 Provider 评分。"""
    
    def score(self, provider: CapabilityProvider, 
              requirements: dict[str, Any] | None = None) -> float: ...
    
    def rank(self, providers: list[CapabilityProvider],
             requirements: dict[str, Any] | None = None) -> list[tuple[CapabilityProvider, float]]: ...
```

### 3.3 高级选择 (SelectionEngine) — Phase 25+

```python
class SelectionEngine:
    """能力选择引擎 — KG 评分 + 经验评分 + 约束加分。"""
    
    def select_top(self, task_type: str, 
                   requirements: dict[str, Any] | None = None,
                   n: int = 3) -> list[SelectionResult]:
        """
        评分公式: kg_score × 0.3 + exp_score × 0.3 + constraints_bonus × 0.4
        """
        ...
    
    def score(self, capability_id: str, provider_id: str,
              requirements: dict[str, Any] | None = None) -> float: ...
```

---

## 4. Metadata Discovery

### CapabilityProvider 元数据

```python
@dataclass
class CapabilityProvider:
    provider_id: str
    capabilities: tuple[CapabilityDescriptor, ...]
    weight: float = 1.0          # 基础权重
    protocol: str = "subprocess"   # subprocess / http / grpc / inproc
    metadata: dict = {}            # 自定义键值对 (version, endpoint, max_concurrency...)
```

### 权重系统

- `weight = 1.0`: 基准 (local_python)
- `weight = 0.8`: 次级 (fallback provider)
- `weight = 1.2`: 增强 (specialized provider, e.g. gpt_engineer for complex coding)

---

## 5. 扩展提供者 (Future)

### SkillGraph Discovery

```python
# 未来: 自动发现技能图中的原子操作
def discover_from_skillgraph(skill_id: str) -> list[CapabilityDescriptor]: ...
```

### Agent-to-Agent Discovery (Phase 30+)

```python
# 未来: 跨 Agent 能力广告
AGENT_REGISTRY.advertise(agent_id="ocr_agent", capabilities=[...])
AGENT_REGISTRY.discover(capability_id="ocr")
```
