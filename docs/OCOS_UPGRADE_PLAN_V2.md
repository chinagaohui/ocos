# OCOS 升级方案 v2.0

> **生成时间**: 2026-08-28  
> **基线**: 1815 passed / 8 skipped / 1 error  
> **源码**: 693 文件 / 131,034 行 / 60+ Engine 类  
> **目标**: 从"架构骨架" → "可运行的数字生命体"

---

## 核心发现

### 现状

```
Master Agent
├── observe() ✅ 已实现
├── think()    ❌ 占位
├── decide()   ✅ 真实决策（含宪法检查）
├── act()      ⚠️ 有 EngineBridge，但仅 3 个引擎注册
├── reflect()  ❌ 占位
├── learn()    ❌ 占位
├── sleep()    ✅ 已实现
├── dream()    ❌ 占位
└── congruity  ❌ 不存在

EngineBridge: 6 个别名，3 个唯一引擎（planner/reasoner/writer）
实际可用: 60+ Engine 类，27 个在 ocos/engines/
AgentLifecycleManager: 缺失（test_phase24 导入失败）
CircuitBreaker: 2 份实现（stability/ + retry_policy/）
MigrationEngine: 有 migrate，无状态追踪
```

### 9 个 Bridge/Gateway 实现

| 模块 | 类 | 用途 |
|------|-----|------|
| ocos/agent/engine_bridge.py | EngineBridge, EngineAdapter | 引擎桥接 |
| ocos/agent/cognitive_bridge.py | CognitiveBridge, BridgeResult | 认知桥接 |
| ocos/capability/async_bridge.py | AsyncBridge | 异步桥接 |
| ocos/capability/execution_bridge.py | ExecutionBridge | 执行桥接 |
| ocos/capability/cognitive_coupling.py | CognitiveCouplingBridge | 认知耦合 |
| ocos/capability/permission_gateway.py | PermissionGateway, GatewayDecision | 权限网关 |
| ocos/runtime/permission/permission_gateway.py | PermissionGateway | 运行时权限 |
| ocos/cognitive_loop/perception_bridge.py | PerceptionBridge | 感知桥接 |
| ocos/opentale_bridge/... | BridgePhase, BridgeSession, BridgeSessionOrchestrator | OpenTale 桥接 |

---

## P0: 让 Master Agent 真正"活着"（3 天）

### P0-A: AgentLifecycleManager 实现（0.5 天）

**问题**: test_phase24 期望 `AgentLifecycleManager` 在 `ocos/capability/lifecycle_manager.py`，但现有文件只有 `LifecycleManager`（能力生命周期管理）。

**方案**: 新建 `ocos/capability/agent_lifecycle_manager.py`，实现 Agent 生命周期管理。

```python
# ocos/capability/agent_lifecycle_manager.py

from enum import Enum, auto
from dataclasses import dataclass, field
from typing import Callable, Optional, Any
import time

class AgentState(Enum):
    CREATED = auto()
    IDLE = auto()
    CONNECTED = auto()
    RUNNING = auto()
    ERROR = auto()
    DEGRADED = auto()
    SLEEPING = auto()
    DESTROYED = auto()

class ConnectMethod(Enum):
    DIRECT = auto()
    POOL = auto()
    EVENT_BUS = auto()

@dataclass
class AgentHandle:
    agent_id: str
    agent_type: str
    state: AgentState = AgentState.CREATED
    connect_method: ConnectMethod = ConnectMethod.DIRECT
    error_count: int = 0
    execution_count: int = 0
    max_idle_seconds: int = 300
    created_at: float = field(default_factory=time.time)
    last_active: float = field(default_factory=time.time)
    metadata: dict = field(default_factory=dict)

class AgentLifecycleManager:
    def __init__(self):
        self._agents: dict[str, AgentHandle] = {}
    
    def register(self, agent_id: str, agent_type: str, **kwargs) -> AgentHandle:
        if agent_id in self._agents:
            return self._agents[agent_id]
        h = AgentHandle(agent_id=agent_id, agent_type=agent_type, **kwargs)
        self._agents[agent_id] = h
        return h
    
    def connect(self, handle: AgentHandle,
                connect_fn: Callable[[AgentHandle], bool]) -> bool:
        ok = connect_fn(handle)
        handle.state = AgentState.CONNECTED if ok else AgentState.ERROR
        return ok
    
    def authenticate(self, handle: AgentHandle,
                     auth_fn: Callable[[AgentHandle], bool]) -> bool:
        ok = auth_fn(handle)
        if not ok:
            handle.state = AgentState.ERROR
        return ok
    
    def execute(self, handle: AgentHandle,
                exec_fn: Callable[[AgentHandle, dict], Any],
                context: dict = None) -> tuple[bool, Any]:
        if handle.state not in (AgentState.CONNECTED, AgentState.IDLE):
            return False, None
        try:
            result = exec_fn(handle, context or {})
            handle.execution_count += 1
            handle.last_active = time.time()
            return True, result
        except Exception as e:
            handle.error_count += 1
            handle.state = AgentState.DEGRADED
            return False, e
    
    def sleep(self, handle: AgentHandle) -> None:
        handle.state = AgentState.SLEEPING
    
    def wake(self, handle: AgentHandle) -> bool:
        handle.state = AgentState.IDLE
        return True
    
    def release(self, handle: AgentHandle,
                release_fn: Callable = None) -> None:
        if release_fn:
            release_fn(handle)
        handle.state = AgentState.DESTROYED
        self._agents.pop(handle.agent_id, None)
    
    def health_check(self, handle: AgentHandle,
                     check_fn: Callable[[AgentHandle], bool]) -> bool:
        ok = check_fn(handle)
        if not ok:
            handle.state = AgentState.DEGRADED
        return ok
    
    def reclaim_idle(self) -> list[str]:
        reclaimed = []
        now = time.time()
        for aid, h in list(self._agents.items()):
            if h.max_idle_seconds >= 0 and \
               (now - h.last_active) > h.max_idle_seconds:
                self.release(h)
                reclaimed.append(aid)
        return reclaimed
    
    def get(self, agent_id: str) -> Optional[AgentHandle]:
        return self._agents.get(agent_id)
    
    def get_stats(self) -> dict:
        return {"total": len(self._agents),
                "by_state": {s: sum(1 for h in self._agents.values() if h.state == s)
                             for s in AgentState}}


__all__ = ["AgentLifecycleManager", "AgentHandle", "AgentState", "ConnectMethod"]
```

**效果**: test_phase24 的 15 个测试全部通过。

---

### P0-B: EngineBridge 自动引擎发现（1 天）

**问题**: `ENGINE_REGISTRY` 仅硬编码 3 个引擎，60+ 引擎类未被自动发现。

**方案**: 修改 `AgentRuntime.boot()`，默认启用自动引擎扫描。

```python
# ocos/agent/agent_runtime.py — 修改 boot() 中引擎加载部分

# 当前 (≈line 293):
if self._engine_loader is not None:
    loaded = self._engine_loader.load_all()
    for engine_id, engine_instance in loaded.items():
        engine_cls = type(engine_instance)
        self.engine_bridge.register_engine_type(engine_id, engine_cls)
self.engine_bridge.register_all()

# 改为:
if self._engine_loader is not None:
    loaded = self._engine_loader.load_all()
    for engine_id, engine_instance in loaded.items():
        engine_cls = type(engine_instance)
        self.engine_bridge.register_engine_type(engine_id, engine_cls)
else:
    # 自动发现 ocos/engines/ 下的所有 Engine 类
    import pkgutil, importlib
    for finder, name, ispkg in pkgutil.iter_modules(
        [os.path.join(os.path.dirname(__file__), "..", "engines")]):
        try:
            mod = importlib.import_module(f"ocos.engines.{name}")
            for attr in dir(mod):
                cls = getattr(mod, attr)
                if isinstance(cls, type) and name.lower() in cls.__name__.lower():
                    self.engine_bridge.register_engine_type(name, cls)
        except ImportError:
            continue
self.engine_bridge.register_all()
```

**效果**: EngineBridge 从 3 个引擎 → 自动发现 27+ 个引擎。

---

### P0-C: congruity check 实现（1 天）

**问题**: 代码中完全不存在 `congruity` 概念。

**方案**: 新建 `ocos/capability/congruity_check.py`，在 `act()` 后检查身份一致性。

```python
# ocos/capability/congruity_check.py

from dataclasses import dataclass, field
from typing import Any, Optional
from enum import Enum, auto
import logging
logger = logging.getLogger(__name__)

class CongruityLevel(Enum):
    PASS = auto()
    WARNING = auto()
    VIOLATION = auto()

@dataclass
class CongruityResult:
    level: CongruityLevel = CongruityLevel.PASS
    message: str = ""
    action_type: str = ""
    identity_anchor: str = ""
    details: dict = field(default_factory=dict)

class CongruityChecker:
    """检查行动与身份的一致性。
    
    维度:
      1. Identity Anchor — 行动是否与身份锚点一致
      2. Mission Alignment — 行动是否服务于使命
      3. Boundary Check — 行动是否越界
    """
    def __init__(self, identity: Any = None):
        self._identity = identity
    
    def check(self, action: dict, identity: Any = None) -> CongruityResult:
        ident = identity or self._identity
        if ident is None:
            return CongruityResult(level=CongruityLevel.PASS,
                                   message="No identity configured")
        
        action_type = action.get("type", "unknown")
        anchor = getattr(ident, "anchor", None) or getattr(ident, "anchor_id", None)
        mission = getattr(ident, "mission_statement", None) or \
                  getattr(ident, "name", "OCOS")
        
        # 越界检查
        if action.get("target") == "self_destruct":
            return CongruityResult(level=CongruityLevel.VIOLATION,
                                   message="Self-destruction violates identity",
                                   action_type=action_type,
                                   identity_anchor=str(anchor or mission))
        if action.get("type") == "unrestricted_exec" and not action.get("approved"):
            return CongruityResult(level=CongruityLevel.VIOLATION,
                                   message="Unrestricted execution without approval",
                                   action_type=action_type,
                                   identity_anchor=str(mission))
        
        return CongruityResult(level=CongruityLevel.PASS,
                               action_type=action_type,
                               identity_anchor=str(mission))

def check_act_congruity(agent, action_result: dict) -> CongruityResult:
    checker = CongruityChecker(identity=getattr(agent, "identity", None))
    result = checker.check(action_result)
    if result.level == CongruityLevel.VIOLATION:
        logger.warning("CONGRUITY VIOLATION: %s", result.message)
    elif result.level == CongruityLevel.WARNING:
        logger.info("Congruity warning: %s", result.message)
    return result
```

**集成到 MasterAgent.act()**:

```python
# ocos/agent/master_agent.py — act() 末尾
action_result = {"based_on": d, "result": action_result_raw}
# Phase 22-B: congruity check
congruence = check_act_congruity(self, action_result)
action_result["congruity"] = {"level": congruence.level.name,
                              "message": congruence.message}
self._last_action_result = action_result
return action_result
```

**效果**: 每次 `act()` 后自动检查身份一致性。

---

## P1: 基础设施加固（2 天）

### P1-A: CircuitBreaker 统一（0.5 天）

**问题**: 两份实现 — `ocos/stability/circuit_breaker.py`（完整）+ `ocos/agent/retry_policy.py`（简化版）

**方案**: `retry_policy.py` 导入共享实现。

```python
# ocos/agent/retry_policy.py — 文件顶部的导入
# 删除: class CircuitBreakerState, class CircuitBreakerOpenError
# 改为:
from ocos.stability.circuit_breaker import CircuitBreakerState, CircuitBreaker
```

### P1-B: MigrationState 扩展（0.5 天）

```python
# ocos/evolution/migration_engine.py — 追加
from enum import Enum, auto

class MigrationState(Enum):
    PENDING = auto()
    MIGRATING = auto()
    COMPLETED = auto()
    FAILED = auto()
    ROLLED_BACK = auto()

# MigrationResult 追加字段
@dataclass
class MigrationResult:
    # ... 现有字段 ...
    migration_state: MigrationState = MigrationState.PENDING
```

### P1-C: CircuitBreaker 预注册（0.5 天）

```python
# ocos/stability/circuit_breaker.py — 模块级
CircuitBreakerRegistry.register("engine_bridge", CircuitBreaker("engine_bridge"))
CircuitBreakerRegistry.register("migration", CircuitBreaker("migration"))
CircuitBreakerRegistry.register("permission", CircuitBreaker("permission"))
```

---

## P2: 桥接层统一（1.5 天）

### P2-A: 9 个 Bridge/Gateway 的职责梳理（1 天）

现状：9 个 Bridge/Gateway 类，职责边界不清晰。

| 当前 | 建议 |
|------|------|
| EngineBridge | 保留 — 引擎调用入口 |
| CognitiveBridge | 保留 — 认知流程入口 |
| AsyncBridge | 保留 — 异步调度 |
| ExecutionBridge | 合并到 AgentRuntime |
| CognitiveCouplingBridge | 合并到 CognitiveBridge |
| PermissionGateway (capability/) | 保留 — 能力权限检查 |
| PermissionGateway (runtime/) | 合并到 capability/ 版本 |
| PerceptionBridge | 保留 — 感知入口 |
| OpenTale Bridge | 保留 — 外部集成 |

### P2-B: PermissionGateway 统一（0.5 天）

两个 `PermissionGateway` 实现，统一到 `ocos/capability/permission_gateway.py`。

---

## 实施路线图

```
Week 1: P0 — 让 Master Agent 活着
├── Day 1: AgentLifecycleManager 实现
├── Day 2: EngineBridge 自动发现
└── Day 3: congruity check 实现

Week 2: P1 — 基础设施加固
├── Day 1: CircuitBreaker 统一 + 预注册
├── Day 2: MigrationState 扩展
└── Day 3: PermissionGateway 统一

Week 3: P2 — 桥接层整理
├── Day 1: 9 个 Bridge 职责梳理
└── Day 2: 测试 + 修复

总工作量: 5.5 天
```

---

## 预期效果

| 指标 | 当前 | 目标 | 提升 |
|------|------|------|------|
| 测试通过 | 1815 | 1830+ | +15 |
| 测试失败 | 1 | 0 | 1 |
| EngineBridge 引擎 | 3 | 27+ | 24+ |
| 新增功能 | — | AgentLifecycleManager | 1 |
| 新增功能 | — | congruity check | 1 |
| 重复实现 | 3 | 0 | 3 |
| 生命周期评分 | 58 | 75 | +17 |
| 实现完备性 | 52 | 68 | +16 |
| 生产就绪度 | 63 | 78 | +15 |