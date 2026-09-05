"""Phase 45: LifecycleManager — 能力生命周期管理。

管理能力的状态变迁:
    REGISTERED → AVAILABLE ↔ BUSY
                    ↓
              DEGRADED / UNAVAILABLE / DEPRECATED

负责任:
    - 激活/停用
    - 降级检测
    - 性能追踪
    - 废弃标记
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ocos.capability.capability_types import CapabilityState
from ocos.capability.capability_registry import CapabilityRegistry


@dataclass
class LifecycleManager:
    """能力生命周期管理器。"""

    registry: CapabilityRegistry = field(default_factory=CapabilityRegistry)

    def activate(self, capability_id: str) -> None:
        """将能力从 REGISTERED → AVAILABLE。"""
        cap = self.registry.get(capability_id)
        if cap and cap.state == CapabilityState.REGISTERED:
            self.registry.update_state(capability_id, CapabilityState.AVAILABLE)

    def mark_busy(self, capability_id: str) -> None:
        self.registry.update_state(capability_id, CapabilityState.BUSY)

    def mark_available(self, capability_id: str) -> None:
        self.registry.update_state(capability_id, CapabilityState.AVAILABLE)

    def degrade(self, capability_id: str, reason: str = "") -> None:
        """降级能力。"""
        self.registry.update_state(capability_id, CapabilityState.DEGRADED)

    def disable(self, capability_id: str) -> None:
        """停用能力。"""
        self.registry.update_state(capability_id, CapabilityState.UNAVAILABLE)

    def deprecate(self, capability_id: str) -> None:
        """废弃能力。"""
        self.registry.update_state(capability_id, CapabilityState.DEPRECATED)

    def record_result(
        self, capability_id: str, success: bool, latency_ticks: int,
    ) -> None:
        """记录执行结果，调整性能分数。"""
        score = 1.0 if success else 0.0
        self.registry.update_performance(capability_id, score)

    def get_state(self, capability_id: str) -> CapabilityState | None:
        cap = self.registry.get(capability_id)
        return cap.state if cap else None


# ─────────────────────────────────────────────────────────────────────────
# Phase 24-C / ABI #9: AgentLifecycleManager — Agent 级生命周期管理
#
# 状态机: idle → connecting → authenticated → executing → releasing → idle
#                       ↘ error → idle      ↘ hibernated / destroyed
#
# 与 LifecycleManager（能力级）的关系:
#   LifecycleManager      = 能力 (capability) 的注册/激活/降级
#   AgentLifecycleManager = Agent 实例的完整生命周期 (出生→执行→休眠→销毁)
#   agent/lifecycle.py    = 宏观阶段 (BOOTING→ACTIVE→…) 与微观循环包装
#   三者职责不同, 各司其职, 不互相替换。
#
# ABI #9 (docs/abi/02-agent-adapter-abi.md §5) 冻结于 2026-07-25。
# ─────────────────────────────────────────────────────────────────────────
import logging
import threading
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable

logger = logging.getLogger(__name__)


class AgentState(Enum):
    """Agent 生命周期状态 (ABI #9 §5)。"""

    CREATED = auto()        # 已注册, 未连接
    CONNECTING = auto()     # 连接中
    CONNECTED = auto()      # 已连接
    AUTHENTICATING = auto()  # 鉴权中
    AUTHENTICATED = auto()  # 已鉴权, 可执行
    IDLE = auto()           # 空闲 (执行后/唤醒后)
    EXECUTING = auto()      # 执行中
    SLEEPING = auto()       # 休眠
    ERROR = auto()          # 错误 (连接失败等)
    DEGRADED = auto()       # 降级 (执行异常/健康检查失败)
    DESTROYED = auto()      # 已销毁 (释放后)


class ConnectMethod(Enum):
    """连接方式 (ABI #9, 供注册时声明)。"""

    DIRECT = auto()         # 直接进程内连接
    AUTO = auto()           # 自动发现
    DISCOVERED = auto()     # 经 EngineBridge.discover_and_register
    HTTP = auto()           # 远程 HTTP 适配
    LOCAL = auto()          # 本地子进程


# Phase 24-C: 状态名 → AgentState 映射（AsyncBridge 等委托方用字符串状态名）
_STATE_ALIASES: dict[str, AgentState] = {
    "connecting": AgentState.CONNECTING,
    "connected": AgentState.CONNECTED,
    "ready": AgentState.IDLE,          # ready 语义 = 可执行（等价 idle）
    "executing": AgentState.EXECUTING,
    "idle": AgentState.IDLE,
    "authenticated": AgentState.AUTHENTICATED,
    "sleeping": AgentState.SLEEPING,
    "degraded": AgentState.DEGRADED,
    "error": AgentState.ERROR,
    "destroyed": AgentState.DESTROYED,
}


@dataclass
class AgentHandle:
    """Agent 实例句柄 (ABI #9)。"""

    agent_id: str
    agent_type: str
    state: AgentState = AgentState.CREATED
    execution_count: int = 0
    error_count: int = 0
    max_idle_seconds: float = 300.0
    connect_method: ConnectMethod = ConnectMethod.DIRECT
    _last_active: float = field(default_factory=time.monotonic)

    def touch(self) -> None:
        """刷新活跃时间戳 (任何状态变更时调用)。"""
        self._last_active = time.monotonic()


class AgentLifecycleManager:
    """Agent 实例生命周期管理器 (线程安全)。

    职责:
      - 注册/注销 Agent 句柄
      - 驱动 connect → authenticate → execute → sleep/wake → release 状态机
      - 空闲回收 (reclaim_idle)
      - 统计与健康检查
    """

    def __init__(self) -> None:
        self._agents: dict[str, AgentHandle] = {}
        self._lock = threading.RLock()

    # ── 注册 / 查询 ────────────────────────────────────────────────────

    def register(self, agent_id: str, agent_type: str,
                 connect_method: ConnectMethod = ConnectMethod.DIRECT) -> AgentHandle:
        """注册 Agent。重复注册返回已有句柄 (幂等)。"""
        with self._lock:
            existing = self._agents.get(agent_id)
            if existing is not None:
                return existing
            handle = AgentHandle(
                agent_id=agent_id,
                agent_type=agent_type,
                connect_method=connect_method,
            )
            self._agents[agent_id] = handle
            return handle

    def ensure_registered(self, agent_id: str, agent_type: str = "agent",
                          connect_method: ConnectMethod = ConnectMethod.DIRECT) -> AgentHandle:
        """确保注册: 已存在则重置为新句柄 (CREATED), 不存在则新建。"""
        with self._lock:
            self._agents.pop(agent_id, None)
            return self.register(agent_id, agent_type, connect_method)

    def deregister(self, agent_id: str) -> None:
        """注销 Agent (立即移除, 不回调)。"""
        with self._lock:
            self._agents.pop(agent_id, None)

    def get(self, agent_id: str) -> AgentHandle | None:
        with self._lock:
            return self._agents.get(agent_id)

    # ── 状态机驱动 ─────────────────────────────────────────────────────

    def connect(self, handle: AgentHandle,
                connect_fn: Callable[[AgentHandle], bool]) -> bool:
        """连接: CREATED/CONNECTED → CONNECTED, 失败 → ERROR。"""
        with self._lock:
            if handle.state not in (AgentState.CREATED, AgentState.CONNECTED,
                                    AgentState.AUTHENTICATED, AgentState.IDLE):
                return False
            handle.state = AgentState.CONNECTING
            ok = bool(connect_fn(handle))
            handle.state = AgentState.CONNECTED if ok else AgentState.ERROR
            if not ok:
                handle.error_count += 1
            handle.touch()
            return ok

    def authenticate(self, handle: AgentHandle,
                     auth_fn: Callable[[AgentHandle], bool]) -> bool:
        """鉴权: CONNECTED → AUTHENTICATED, 失败 → ERROR。"""
        with self._lock:
            if handle.state not in (AgentState.CONNECTED, AgentState.AUTHENTICATED,
                                    AgentState.IDLE):
                return False
            handle.state = AgentState.AUTHENTICATING
            ok = bool(auth_fn(handle))
            handle.state = AgentState.AUTHENTICATED if ok else AgentState.ERROR
            if not ok:
                handle.error_count += 1
            handle.touch()
            return ok

    def execute(self, handle: AgentHandle,
                exec_fn: Callable[[AgentHandle, Any], Any],
                context: Any = None) -> tuple[bool, Any]:
        """执行: 仅 AUTHENTICATED/IDLE 可执行。异常 → DEGRADED + error_count。"""
        with self._lock:
            if handle.state not in (AgentState.AUTHENTICATED, AgentState.IDLE):
                return False, None
            handle.state = AgentState.EXECUTING
            handle.touch()
            try:
                result = exec_fn(handle, context)
                handle.execution_count += 1
                handle.state = AgentState.IDLE
                return True, result
            except Exception:
                handle.error_count += 1
                handle.state = AgentState.DEGRADED
                return False, None

    def sleep(self, handle: AgentHandle) -> bool:
        """休眠: → SLEEPING。"""
        with self._lock:
            if handle.state in (AgentState.DESTROYED,):
                return False
            handle.state = AgentState.SLEEPING
            handle.touch()
            return True

    def wake(self, handle: AgentHandle) -> bool:
        """唤醒: SLEEPING → IDLE。"""
        with self._lock:
            if handle.state != AgentState.SLEEPING:
                return False
            handle.state = AgentState.IDLE
            handle.touch()
            return True

    def health_check(self, handle: AgentHandle,
                     check_fn: Callable[[AgentHandle], bool]) -> bool:
        """健康检查: 失败 → DEGRADED。"""
        with self._lock:
            ok = bool(check_fn(handle))
            if not ok:
                handle.state = AgentState.DEGRADED
            handle.touch()
            return ok

    def health_check_all(self,
                         check_fn: Callable[[AgentHandle], bool]) -> dict[str, bool]:
        """批量健康检查全部注册 Agent（Phase 24-C 契约）。

        返回 {agent_id: ok}；任一失败 → 该 Agent 置 DEGRADED。
        """
        results: dict[str, bool] = {}
        with self._lock:
            for agent_id, h in list(self._agents.items()):
                try:
                    ok = bool(check_fn(h))
                except Exception:
                    ok = False
                if not ok:
                    h.state = AgentState.DEGRADED
                h.touch()
                results[agent_id] = ok
        return results

    def release(self, handle: AgentHandle,
                release_fn: Callable[[AgentHandle], None] | None = None) -> None:
        """释放: 调 release_fn → DESTROYED → 从注册表移除。"""
        with self._lock:
            if release_fn is not None:
                try:
                    release_fn(handle)
                except Exception:
                    handle.error_count += 1
            handle.state = AgentState.DESTROYED
            self._agents.pop(handle.agent_id, None)

    # ── 回收 / 统计 ────────────────────────────────────────────────────

    def reclaim_idle(self) -> list[str]:
        """回收超时空闲 Agent, 返回被回收的 agent_id 列表。"""
        reclaimed: list[str] = []
        now = time.monotonic()
        with self._lock:
            for agent_id, h in list(self._agents.items()):
                idle_secs = now - h._last_active
                if idle_secs > h.max_idle_seconds:
                    h.state = AgentState.DESTROYED
                    self._agents.pop(agent_id, None)
                    reclaimed.append(agent_id)
        return reclaimed

    def transition(self, agent_id: str, state: str) -> bool:
        """Phase 24-C: 按名称将 Agent 迁移到指定状态（AsyncBridge 委托用）。

        Args:
            agent_id: Agent ID
            state: 状态名 — connecting/connected/ready/executing/idle/
                   degraded/error/sleeping/destroyed（大小写不敏感）

        Returns:
            是否存在该 agent 且状态名合法
        """
        target = _STATE_ALIASES.get(state.lower())
        if target is None:
            logger.warning("AgentLifecycleManager: unknown state %r", state)
            return False
        with self._lock:
            handle = self._agents.get(agent_id)
            if handle is None:
                return False
            handle.state = target
            handle.touch()
            logger.info(
                "AgentLifecycleManager: %s → %s", agent_id, target.name
            )
            return True

    def get_stats(self) -> dict[str, Any]:
        """统计: total + 各状态计数。"""
        with self._lock:
            by_state: dict[str, int] = {}
            for h in self._agents.values():
                by_state[h.state.name] = by_state.get(h.state.name, 0) + 1
            return {
                "total": len(self._agents),
                "by_state": by_state,
            }

    def reap_timeout(self, timeout: float) -> list[str]:
        """ABI #9 兼容别名: 回收 idle 超过 timeout 秒的 Agent。"""
        with self._lock:
            for h in self._agents.values():
                if h.max_idle_seconds != timeout:
                    h.max_idle_seconds = timeout
        return self.reclaim_idle()


__all__ = [
    "LifecycleManager",
    "AgentLifecycleManager", "AgentHandle", "AgentState", "ConnectMethod",
]
