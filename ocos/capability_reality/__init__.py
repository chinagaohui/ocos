"""Phase 55: Capability Reality Layer.

OCOS 的真实能力层 — 将抽象能力 (ocos/capability/) 连接到真实世界。

职责分工(GAP-P3-7 裁决): 本包 = 真实能力层 (Phase 55, 可执行
能力注册 CapabilityDescriptor + shell/fs 适配器, 连接真实世界);
ocos/capability/ = 抽象能力神经系统 (Phase 45, Capability 对象
注册/状态/路由)。两包是两个正式 Phase 的分层设计, 注册表 API
不同 (CapabilityDescriptor vs Capability), 非重复实现 → 不合并。

核心原则:
    CR55-01: Capability ≠ Execution — 注册不代表已执行
    CR55-02: Adapter Isolation — 适配器崩溃不影响主脑
    CR55-03: Execution Recorded — 每次执行产生 EventMemory 记录
    CR55-04: Capability Discovery — 自动发现，不假设能力存在

架构:
    Decision (from cognitive loop)
        ↓
    CapabilitySelector → CapabilityRegistry
        ↓
    CapabilityValidator (pre-execution check)
        ↓
    CapabilityAdapter.execute (sandboxed)
        ↓
    ExecutionResult → EventLifecycle.record()
        ↓
    World Model update

真实适配器:
    - FilesystemAdapter: fs_read / fs_write / fs_list / fs_stat / fs_exists
    - ShellAdapter: shell_exec (危险命令检测 + 沙盒)

与已有 ocos/capability/ 的关系:
    ocos/capability/ 提供抽象框架 (类型、路由、图形)
    ocos/capability_reality/ 添加上层真实性 (真实 I/O、验证、发现)
"""

from ocos.capability_reality.adapter_types import (
    AdapterHealth, ExecutionStatus, CapabilityCategory,
    CapabilityDescriptor, AdapterStatus,
    ExecutionContext, ExecutionResult, AdapterConfig,
)
from ocos.capability_reality.capability_registry import (
    CapabilityRegistry, RegisteredCapability,
)
from ocos.capability_reality.capability_selector import (
    CapabilitySelector, SelectionResult,
)
from ocos.capability_reality.capability_adapter import (
    CapabilityAdapter,
)
from ocos.capability_reality.adapter_fs import (
    FilesystemAdapter,
)
from ocos.capability_reality.adapter_shell import (
    ShellAdapter,
)
from ocos.capability_reality.adapter_discovery import (
    AdapterDiscovery, DiscoveryReport,
)
from ocos.capability_reality.capability_validator import (
    CapabilityValidator, ValidationResult, ValidationDecision,
)


__all__ = [
    # Types
    "AdapterHealth", "ExecutionStatus", "CapabilityCategory",
    "CapabilityDescriptor", "AdapterStatus",
    "ExecutionContext", "ExecutionResult", "AdapterConfig",
    # Registry
    "CapabilityRegistry", "RegisteredCapability",
    # Selector
    "CapabilitySelector", "SelectionResult",
    # Adapter
    "CapabilityAdapter",
    # Real adapters
    "FilesystemAdapter",
    "ShellAdapter",
    # Discovery
    "AdapterDiscovery", "DiscoveryReport",
    # Validator
    "CapabilityValidator", "ValidationResult", "ValidationDecision",
]
