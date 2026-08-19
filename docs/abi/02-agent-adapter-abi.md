# OCOS Agent Adapter ABI v1.0

> Freeze Deliverable #2 — 冻结日期: 2026-07-25
> Python Protocol + Markdown

---

## 1. 概述

Agent Adapter ABI 定义 **外部 Agent/引擎 如何接入 OCOS 运行时**。任何 Agent（Codex、Browser、Excel、自定义 Agent）
必须实现此协议才能被 OCOS 的 EngineBridge / SkillGraph 调度。

### 核心原则
- **单向依赖**: Agent → OCOS (Agent 不反向导入 OCOS)
- **签名兼容**: 使用 `inspect.signature` 动态过滤 kwargs（EngineBridge.register()）
- **无状态注入**: Agent 不持有 OCOS 内部组件引用

---

## 2. Python Protocol Definition

```python
"""ocos/capability/agent_adapter_protocol.py — Agent Adapter ABI v1.0"""
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class IAgentAdapter(Protocol):
    """Agent 接入协议 v1.0。

    任何实现此 Protocol 的类可自动注册到 ENGINE_REGISTRY。
    """

    # ── 必需属性 ──
    engine_name: str          # 引擎唯一名称 (e.g. "codex", "browser", "echo")
    engine_type: str          # 引擎类型: "llm" | "tool" | "agent" | "service"

    # ── 必需方法 ──
    def execute(self, **kwargs: Any) -> Any:
        """执行引擎能力。

        Args:
            **kwargs: 由 EngineBridge 根据 inspect.signature 动态过滤后传入。
                      常用参数：
                        - action (str): 操作名
                        - input (str): 输入文本
                        - params (dict): 附加参数

        Returns:
            Any: 引擎输出，建议返回 dict 便于 ResultUnderstandingLayer 处理

        Raises:
            RuntimeError: 执行失败
        """
        ...

    def __repr__(self) -> str:
        """返回可读的引擎表示。"""
        ...
```

---

## 3. 可选属性（EngineBridge 自动检测）

EngineBridge.register() 使用 `inspect.signature` 动态过滤 kwargs：

```python
# engine_bridge.py 核心逻辑
def register(self, engine: Any) -> None:
    sig = inspect.signature(engine.__init__)
    kwargs = {}
    if "event_bus" in sig.parameters:
        kwargs["event_bus"] = self.event_bus
    if "working_memory" in sig.parameters:
        kwargs["working_memory"] = self.working_memory
    instance = engine.__class__(**kwargs)
    ENGINE_REGISTRY[engine.engine_name] = instance
```

### 可选 __init__ 参数

| 参数名 | 类型 | 说明 |
|-------|------|------|
| `event_bus` | EventBus | OCOS 事件总线 (发布/订阅) |
| `working_memory` | WorkingMemory | 工作记忆读写接口 |

Agent 可在 `__init__` 中声明这些参数即可自动获得注入，不需要则忽略。

---

## 4. 注册流程

```python
from ocos.agent.engine_bridge import EngineBridge, ENGINE_REGISTRY

# 方式 1: 手动注册
engine = MyAgent()
EngineBridge.register_engine(engine)

# 方式 2: 自动发现 (通过 AgentLifecycleManager)
EngineBridge.discover_and_register()
```

---

## 5. 生命周期管理

Agent 的完整生命周期由 `AgentLifecycleManager` 管理：

```
idle → connecting → authenticated → executing → releasing → idle
                                    ↘ error → idle
                                                       ↘ hibernated
                                                       ↘ destroyed
```

### AgentLifecycleManager API

```python
class AgentLifecycleManager:
    def transition(self, engine_name: str, target: AgentLifecycleState) -> bool: ...
    def get_state(self, engine_name: str) -> AgentLifecycleState: ...
    def reap_timeout(self, timeout: float) -> list[str]: ...
    def stats(self) -> LifecycleStats: ...
```

---

## 6. 参考实现

参见 `ocos/examples/echo_agent.py` — 最小的 IAgentAdapter 参考实现。
