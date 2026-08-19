# OCOS Capability ABI Specification v1.0

> Freeze Deliverable #1 — 冻结日期: 2026-07-25
> 覆盖: §4.4 Capability 层 完整接口契约

---

## 1. 概述

Capability ABI (Application Binary Interface) 定义 OCOS 中 **每一个能力提供者必须遵守的最小接口契约**。
所有 Provider（codex, browser, local_python, gpt_engineer, custom agent…）必须实现此 ABI。

### 设计原则
- **最小接口**: 仅 1 个必需方法 `execute()`
- **无状态**: Provider 不持有 OCOS 内部状态
- **异步兼容**: 同步接口，异步由 EngineBridge + AsyncBridge 封装
- **无 import OCOS**: Provider 不得 import 任何 OCOS 内部模块（单向依赖）

---

## 2. 核心接口: `ICapabilityProvider`

```python
from typing import Any, Protocol


class ICapabilityProvider(Protocol):
    """Capability ABI v1.0 — 所有 Provider 的最小接口.

    Attributes:
        provider_id (str): 提供者唯一标识
        capabilities (tuple[str, ...]): 提供的能力 ID 列表
        protocol (str): 通信协议 ('subprocess' | 'http' | 'grpc' | 'inproc')
    """

    @property
    def provider_id(self) -> str: ...

    @property
    def capabilities(self) -> tuple[str, ...]: ...

    @property
    def protocol(self) -> str: ...

    def execute(self, **kwargs: Any) -> Any:
        """执行能力。

        Args:
            **kwargs: 输入参数，由 CapabilityDescriptor.params 定义 schema

        Returns:
            Any: 输出结果，建议返回 dict 便于 ResultUnderstandingLayer 处理
                 但 str / list / 任意类型均可。

        Raises:
            RuntimeError: 执行失败时抛出
            ValueError: 参数无效
        """
        ...
```

---

## 3. 能力发现: `CapabilityDescriptor`

Provider 通过 `CapabilityDescriptor` 声明自己的能力。

```python
from dataclasses import dataclass
from typing import Any

@dataclass(frozen=True)
class CapabilityDescriptor:
    capability_id: str          # 能力唯一标识
    domain: str                 # 领域: coding / image / data / browser
    actions: tuple[str, ...]    # 动作列表: generate / analyze / edit / review
    input_types: tuple[str, ...]  # 输入类型: text / code / image
    output_types: tuple[str, ...] # 输出类型: text / code / image / data
    params: dict[str, Any] = {}   # JSON Schema 参数定义
    tags: tuple[str, ...] = ()    # 标签: fast / reliable / experimental
```

### `params` Schema 示例

```python
{
    "input": {"type": "string", "required": True, "description": "输入文本"},
    "temperature": {"type": "number", "default": 0.7, "required": False},
    "max_tokens": {"type": "integer", "default": 1024, "required": False},
}
```

---

## 4. 注册与生命周期

### 4.1 CapabilityRegistry

```python
class CapabilityRegistry(Protocol):
    def register(self, provider: ICapabilityProvider) -> None: ...
    def unregister(self, provider_id: str) -> None: ...
    def discover(self, capability_id: str) -> list[ICapabilityProvider]: ...
    def list_all(self) -> dict[str, list[ICapabilityProvider]]: ...
```

### 4.2 CapabilityAdapter (协议层)

```python
class CapabilityAdapter:
    """统一能力适配器 — 重试 + 降级 + 监控。"""

    def execute(self, inputs: dict[str, Any] | None = None) -> AdapterResult:
        """执行能力（含重试逻辑）。"""
        ...

@dataclass
class AdapterResult:
    success: bool
    capability_id: str
    provider_id: str
    output: dict[str, Any]
    error: str
    attempt: int
    duration_ms: float
```

### 4.3 AgentLifecycleManager

```python
class AgentLifecycleState(Enum):
    IDLE = "idle"
    CONNECTING = "connecting"
    AUTHENTICATED = "authenticated"
    EXECUTING = "executing"
    RELEASING = "releasing"
    HIBERNATED = "hibernated"
    DESTROYED = "destroyed"

class AgentLifecycleManager:
    def transition(self, engine_name: str, target: AgentLifecycleState) -> bool: ...
    def get_state(self, engine_name: str) -> AgentLifecycleState: ...
    def reap_timeout(self, timeout: float) -> list[str]: ...
```

---

## 5. 安全边界: PermissionGateway

**所有外部交互必须经过 Gateway 验证**。

```
调用方 → PermissionGateway.validate() → CapabilityAdapter.execute() → Provider
                                      ↘ 审计日志 (audit.log)
```

### Gateway 验证规则 (6 类)

| 规则 | 值 | 说明 |
|-----|-----|------|
| L1 CALLER_ID | agent_id 必须在白名单 | 调用者身份校验 |
| L2 ACTION | action 必须在 allowed_actions | 操作白名单 |
| L3 PARAM | 参数必须通过 schema 验证 | 参数合法性 |
| L4 REVERSE_CONTROL | 检测"指挥 OCOS"模式 | 反向控制拦截 |
| L5 INJECTION | 路径穿越/命令注入/SSRF | 注入攻击检测 |
| L6 RATE_LIMIT | 同 agent 30s 内 ≤ 10 次 | 频率限制 |

### Gateway 决策

```python
class GatewayDecision(Enum):
    ALLOWED = "allowed"
    DENIED = "denied"
    QUARANTINED = "quarantined"
```

---

## 6. 执行流程 (一次完整调用)

```
1. CapabilitySelector 选择 Provider
2. PermissionGateway.validate(caller_id, action, params)
3. AgentLifecycleManager.transition(engine, "executing")
4. EngineBridge.dispatch(engine_name, action, params)
5. CapabilityAdapter.execute(inputs)  ← 重试/降级在此
6. ResultUnderstandingLayer.process_result(output)
   ├─ StatementValidator.validate()     → 禁令扫描
   ├─ ResultUnderstandingLayer.structure() → 结构化提取
   └─ ResultUnderstandingLayer.learn()     → Experience + KG 更新
7. AgentLifecycleManager.transition(engine, "idle")
```

---

## 7. 版本兼容性

| 版本 | 变更 | 兼容性 |
|-----|------|--------|
| v1.0 | 初始冻结 | — |
| v1.x | 只增不减 | 向后兼容：新增字段使用 Optional |
| v2.0 | 重大变更 | 需要 Migration Guide + 2-phase 过渡期 |

### ABI 冻结承诺
- **v1.0 所有 `ICapabilityProvider` 方法签名不可删除/重命名**
- 新增方法使用 Optional 关键字参数
- Registry 的 `discover()` 返回值不可改变类型

---

## 8. echo_agent — 参考实现

参见 `ocos/examples/echo_agent.py` — 完整的 Capability ABI v1.0 参考实现。
