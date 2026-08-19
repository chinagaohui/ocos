"""Phase 55: Capability Reality Layer — Types.

CR55-01: Capability ≠ Execution — 注册 ≠ 执行
CR55-02: Adapter Isolation — 适配器崩溃不影响主脑
CR55-03: Execution Recorded — 每次执行都有 EventMemory 记录
CR55-04: Capability Discovery — 自动发现，不假设能力存在

核心区别:
    现有 ocos/capability/ = 抽象框架 (类型、路由、选择器)
    Phase 55 capability_reality/ = 真实适配 (真正的 FS/Shell/HTTP 操作)

适配器不替换已有 capability 框架——它搭在框架之上，连接决策到真实世界。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Callable
import time as _time


class AdapterHealth(str, Enum):
    UNKNOWN = "unknown"
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    FAILED = "failed"
    DISCONNECTED = "disconnected"


class ExecutionStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"
    REJECTED = "rejected"       # 被 validator 拒绝


class CapabilityCategory(str, Enum):
    FILESYSTEM = "filesystem"
    SHELL = "shell"
    NETWORK = "network"
    CODE = "code"
    BROWSER = "browser"
    GENERATIVE = "generative"
    CUSTOM = "custom"


@dataclass
class CapabilityDescriptor:
    """能力描述符 — 一个可执行的能力。

    包含:
        - 名称和分类
        - 输入/输出 schema
        - 所需权限
        - 预估成本/风险
    """
    name: str
    category: CapabilityCategory
    description: str = ""

    # 输入约束
    required_params: list[str] = field(default_factory=list)
    optional_params: list[str] = field(default_factory=list)

    # 权限
    permissions: list[str] = field(default_factory=list)  # fs_read, fs_write, shell, network, ...

    # 风险等级 1-5
    risk_level: int = 1

    # 预估执行时间 (秒)
    estimated_duration: float = 1.0

    # 是否可逆
    reversible: bool = True

    # 元数据
    metadata: dict = field(default_factory=dict)


@dataclass
class AdapterStatus:
    """适配器状态 — 运行时健康快照。"""
    adapter_id: str
    health: AdapterHealth = AdapterHealth.UNKNOWN
    last_check: float = 0.0
    last_success: float = 0.0
    last_failure: float = 0.0
    total_executions: int = 0
    total_failures: int = 0
    avg_latency_ms: float = 0.0
    message: str = ""

    @property
    def failure_rate(self) -> float:
        if self.total_executions == 0:
            return 0.0
        return self.total_failures / self.total_executions


@dataclass
class ExecutionContext:
    """执行上下文 — 一次能力调用的完整上下文。

    CR55-03: 每条执行都会被 EventLifecycle 记录。
    """
    execution_id: str
    capability_name: str
    params: dict = field(default_factory=dict)
    started_at: float = 0.0
    decision_id: str = ""      # 触发此次执行的决策
    goal_id: str = ""          # 关联的目标
    sandboxed: bool = True     # 默认沙盒模式
    timeout: float = 30.0      # 超时秒数


@dataclass
class ExecutionResult:
    """执行结果。"""
    context: ExecutionContext
    status: ExecutionStatus
    output: object = None
    error: str = ""
    duration_ms: float = 0.0
    event_id: str = ""         # 对应 EventMemory 中的事件 ID
    metrics: dict = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.status == ExecutionStatus.SUCCESS


@dataclass
class AdapterConfig:
    """适配器配置。"""
    sandboxed: bool = True
    default_timeout: float = 30.0
    max_retries: int = 1
    retry_delay: float = 1.0
    log_level: str = "info"
    allow_unsafe_ops: bool = False
    max_output_bytes: int = 1_000_000     # 1MB max output
    permissions: list[str] = field(default_factory=list)


__all__ = [
    "AdapterHealth", "ExecutionStatus", "CapabilityCategory",
    "CapabilityDescriptor", "AdapterStatus",
    "ExecutionContext", "ExecutionResult", "AdapterConfig",
]
