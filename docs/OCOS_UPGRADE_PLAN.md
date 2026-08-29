# OCOS 升级优化方案 v1.0

> **生成时间**: 2026-08-28  
> **依据**: OCOS_AUDIT_KERNEL.md v2.1 审计报告  
> **范围**: Phase 22-A 至 Phase 28 升级路径

---

## 一、问题优先级矩阵

| 优先级 | 问题 | 影响 | 建议方案 | 预计工作量 |
|--------|------|------|----------|-----------|
| **P0-A** | EngineBridge 未自动注入 | act() 降级为 simulated | 构造函数自动创建 | 1 天 |
| **P0-B** | congruity check 缺失 | 行为与身份可能漂移 | 添加一致性验证 | 2 天 |
| **P0-C** | AgentLifecycleManager 缺失 | test_phase24 失败 | 从 async_bridge 提取 | 1 天 |
| **P1-A** | CircuitBreaker 重复定义 | 维护混乱 | 统一到 stability/ | 0.5 天 |
| **P1-B** | MigrationState 状态有限 | 无法追踪完成/失败 | 扩展枚举 | 0.5 天 |
| **P2-A** | 76 个引擎命名不统一 | 注册表混乱 | 重命名规范化 | 2 天 |

---

## 二、详细实施方案

### 2.1 P0-A：EngineBridge 自动注入

**问题**: `MasterAgent.__init__()` 中 `self._engine_bridge = None`，需外部调用 `set_engine_bridge()` 才能激活。

**方案**: 在构造函数中自动创建 EngineBridge 实例。

```python
# ocos/agent/master_agent.py
def __init__(self, ...):
    ...
    # Phase 22-A: 自动创建 EngineBridge
    from ocos.agent.engine_bridge import EngineBridge
    self._engine_bridge = EngineBridge(
        event_bus=self._event_bus,
        working_memory=self.working_memory,
    )
    # 注册所有可用引擎
    self._engine_bridge.register_all()
```

**预期效果**:
- `act()` 方法中 `self._engine_bridge is not None` 为 True
- 决策派发到真实引擎（reasoner/planner/writer）
- 测试通过率不变，但行为从 simulated 变为 executed

**风险**: 无 — EngineBridge 已完整实现，仅改变初始化时机

---

### 2.2 P0-B：congruity check 实现

**问题**: Phase 26 计划中的"一致性验证"未在代码中实现。

**方案**: 在 `act()` 后添加身份一致性检查。

```python
# ocos/agent/master_agent.py
def act(self, decision: Any = None) -> Any:
    ...
    action_result = self._perform_act(d)  # 原有逻辑
    
    # Phase 26: 一致性验证
    congruity_result = self._check_congruity(action_result, d)
    if congruity_result and not congruity_result.congruent:
        logger.warning(
            f"Act result not congruent with identity: "
            f"{congruity_result.reason}"
        )
        # 可选：触发自省或记录审计日志
        self._log_identity_drift(congruity_result)
    
    return action_result

def _check_congruity(self, action_result: dict, decision: dict) -> Optional[CongruityResult]:
    """检查行动结果是否与当前身份一致。"""
    # 1. 检查 Action 类型是否在 Identity 允许范围内
    action_type = decision.get("type", "")
    identity = self.identity.get_identity_data()
    
    if action_type not in identity.get("allowed_actions", []):
        return CongruityResult(
            congruent=False,
            reason=f"Action type '{action_type}' not in identity allowed_actions",
        )
    
    # 2. 检查决策优先级是否与 Identity 价值观冲突
    priority = decision.get("priority", 0)
    if priority > identity.get("max_priority", 10):
        return CongruityResult(
            congruent=False,
            reason="Decision priority exceeds identity max_priority",
        )
    
    return CongruityResult(congruent=True, reason="")
```

**CongruityResult 定义**:
```python
@dataclass
class CongruityResult:
    congruent: bool
    reason: str = ""
    details: dict = field(default_factory=dict)
```

**预期效果**:
- 行为漂移时可被检测并记录
- 为 Phase 26 "Embodiment" 提供基础

**风险**: 低 — 仅添加日志，不影响正常流程

---

### 2.3 P0-C：AgentLifecycleManager 恢复

**问题**: `tests/test_capability/test_phase24.py` 导入 `AgentLifecycleManager` 失败。

**方案**: 从 `async_bridge.py` 或新建 `lifecycle_manager.py` 提取。

```python
# ocos/capability/lifecycle_manager.py
"""AgentLifecycleManager — Phase 24: Agent 生命周期管理。

管理 Agent 的连接状态、生命周期转换。
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class AgentState(Enum):
    """Agent 状态。"""
    IDLE = "idle"
    CONNECTED = "connected"
    RUNNING = "running"
    SUSPENDED = "suspended"
    TERMINATED = "terminated"


class ConnectMethod(Enum):
    """连接方式。"""
    SYNC = "sync"
    ASYNC = "async"
    EVENT_BUS = "event_bus"


@dataclass
class AgentHandle:
    """Agent 句柄 — 指向一个已注册的 Agent。"""
    agent_id: str
    state: AgentState = AgentState.IDLE
    connect_method: ConnectMethod = ConnectMethod.SYNC
    connected_at: Optional[float] = None
    metadata: dict = field(default_factory=dict)


class AgentLifecycleManager:
    """Agent 生命周期管理器。
    
    职责:
    - 管理 Agent 的连接/断开
    - 追踪 Agent 状态转换
    - 提供 Agent 发现与查询
    """
    
    def __init__(self):
        self._agents: dict[str, AgentHandle] = {}
        self._state_history: list[dict] = []
    
    def register(self, agent_id: str, connect_method: ConnectMethod = ConnectMethod.SYNC) -> AgentHandle:
        """注册新 Agent。"""
        handle = AgentHandle(
            agent_id=agent_id,
            state=AgentState.CONNECTED,
            connect_method=connect_method,
            connected_at=__import__("time").time(),
        )
        self._agents[agent_id] = handle
        self._record_transition(agent_id, AgentState.CONNECTED)
        return handle
    
    def unregister(self, agent_id: str) -> bool:
        """注销 Agent。"""
        if agent_id not in self._agents:
            return False
        handle = self._agents.pop(agent_id)
        handle.state = AgentState.TERMINATED
        self._record_transition(agent_id, AgentState.TERMINATED)
        return True
    
    def get_state(self, agent_id: str) -> Optional[AgentState]:
        """获取 Agent 状态。"""
        handle = self._agents.get(agent_id)
        return handle.state if handle else None
    
    def transition(self, agent_id: str, new_state: AgentState) -> bool:
        """状态转换。"""
        handle = self._agents.get(agent_id)
        if not handle:
            return False
        old_state = handle.state
        handle.state = new_state
        self._record_transition(agent_id, new_state, old_state)
        return True
    
    def list_agents(self) -> list[AgentHandle]:
        """列出所有已注册 Agent。"""
        return list(self._agents.values())
    
    def _record_transition(self, agent_id: str, new_state: AgentState, old_state: Optional[AgentState] = None):
        """记录状态转换历史。"""
        self._state_history.append({
            "agent_id": agent_id,
            "from": old_state.value if old_state else None,
            "to": new_state.value,
            "timestamp": __import__("time").time(),
        })
```

**预期效果**: test_phase24 通过，Agent 生命周期可被外部管理。

**风险**: 低 — 纯新增类，不影响现有逻辑

---

### 2.4 P1-A：CircuitBreaker 统一

**问题**: `ocos/stability/circuit_breaker.py` 和 `ocos/agent/retry_policy.py` 各定义一次。

**方案**: 删除 `retry_policy.py` 中的重复定义，统一引用 `stability/` 版本。

```python
# ocos/agent/retry_policy.py
# 删除以下内容:
# class CircuitBreakerOpenError(RuntimeError): ...
# class CircuitBreakerState: ...
# class RetryPolicy: ...

# 改为:
from ocos.stability.circuit_breaker import CircuitBreaker, CircuitBreakerError, CircuitBreakerRegistry

# 保留 RetryPolicy，但使用 stability 版本的 CircuitBreaker
class RetryPolicy:
    def __init__(self):
        self.breaker = CircuitBreaker("default")
```

**预期效果**: 单一来源，消除维护混乱。

**风险**: 中 — 需检查所有引用点

---

### 2.5 P1-B：MigrationState 扩展

**问题**: `MigrationEngine` 未使用 `MigrationState` 枚举，直接用字符串。

**方案**: 定义枚举并扩展状态。

```python
# ocos/evolution/migration_engine.py
from enum import Enum

class MigrationState(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"
    CANCELLED = "cancelled"
```

**预期效果**: 状态可追踪，便于审计。

**风险**: 低

---

### 2.6 P2-A：引擎命名规范化

**问题**: 76 个引擎类命名不统一（如 `SelectionEngine` 在 capability/，`AttentionEngine` 在 runtime/）。

**方案**: 按职责分层命名。

| 类别 | 当前命名 | 建议命名 |
|------|---------|---------|
| 核心认知 | `ReasoningEngine` | ✅ 保持不变 |
| 核心认知 | `DecisionMakingEngine` | ✅ 保持不变 |
| 核心认知 | `PlanningEngine` | ✅ 保持不变 |
| Runtime 调度 | `DecisionRuntimeEngine` | → `DecisionSchedulerEngine` |
| Runtime 调度 | `ExecutionRuntimeEngine` | → `ExecutionSchedulerEngine` |
| Capability 管理 | `SelectionEngine` | → `CapabilitySelectionEngine` |
| Attention | `AttentionScoringEngine` | → `AttentionEngine` |

**预期效果**: 注册表清晰，便于外部扩展。

**风险**: 高 — 需更新所有引用

---

## 三、实施路线图

### Phase 22-A: EngineBridge 激活（1 天）
- [ ] 修改 `MasterAgent.__init__()` 自动创建 EngineBridge
- [ ] 运行测试验证 act() 派发到真实引擎
- [ ] 更新文档

### Phase 22-B: congruity check 实现（2 天）
- [ ] 定义 `CongruityResult` 数据类
- [ ] 实现 `_check_congruity()` 方法
- [ ] 集成到 `act()` 流程
- [ ] 添加测试

### Phase 24: AgentLifecycleManager 恢复（1 天）
- [ ] 创建 `ocos/capability/lifecycle_manager.py`
- [ ] 实现 `AgentLifecycleManager`、`AgentHandle`、`AgentState`
- [ ] 修复 test_phase24
- [ ] 更新 async_bridge.py 使用新类

### Phase 21.05: CircuitBreaker 统一（0.5 天）
- [ ] 检查 retry_policy.py 引用
- [ ] 删除重复定义
- [ ] 统一导入

### Phase 21.06: MigrationState 扩展（0.5 天）
- [ ] 定义枚举
- [ ] 更新 migrate() 方法使用枚举

---

## 四、预期收益

| 维度 | 当前评分 | 预期评分 | 提升 |
|------|---------|---------|------|
| 架构完整性 | 82/100 | 90/100 | +8 |
| 实现完备性 | 52/100 | 65/100 | +13 |
| 生产就绪度 | 63/100 | 75/100 | +12 |
| 能力编排 | 58/100 | 72/100 | +14 |

---

## 五、风险评估

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|---------|
| EngineBridge 注入导致启动变慢 | 低 | 低 | 延迟初始化 |
| congruity check 误报 | 中 | 中 | 仅日志，不阻塞 |
| LifecycleManager 命名冲突 | 低 | 低 | 检查现有类名 |
| CircuitBreaker 删除影响其他模块 | 中 | 中 | 先 grep 所有引用 |

---

## 六、验收标准

### Phase 22-A
- [ ] `MasterAgent` 启动时 `self._engine_bridge is not None`
- [ ] `act()` 返回 `status: executed` 而非 `status: simulated`
- [ ] test_phase22 通过

### Phase 22-B
- [ ] `_check_congruity()` 被 `act()` 调用
- [ ] 违规行动被记录到日志
- [ ] 无违规行动不触发警告

### Phase 24
- [ ] `from ocos.capability.lifecycle_manager import AgentLifecycleManager` 成功
- [ ] test_phase24 收集通过
- [ ] 测试通过率恢复到 3135+

---

*方案生成于 2026-08-28 | 基于 OCOS_AUDIT_KERNEL.md v2.1*
