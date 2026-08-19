"""Phase 23-A — ProviderDescriptor ABI (§4.4.2 ProviderNode)。

提供者描述符：将引擎/模块/外部服务映射为能力提供者。
一个 Provider 可以声明多个 CapabilityDescriptor。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable


class ProviderType(str, Enum):
    """提供者类型。"""
    ENGINE = "engine"           # 本地引擎类
    MODULE = "module"           # Python 函数/模块
    EXTERNAL = "external"       # 外部 API/服务
    HYBRID = "hybrid"           # 本地 + 外部混合


class ProviderStatus(str, Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    ERROR = "ERROR"
    DEPRECATED = "DEPRECATED"


@dataclass(frozen=True)
class ProviderDescriptor:
    """提供者描述符 — 能力的具体实现入口。

    §4.4.2 ProviderNode 的 ABI 定义。

    Attributes:
        provider_id: 全局唯一标识 (e.g. "ocos.engines.reasoning_engine")
        name: 人类可读名称
        provider_type: 提供者类型
        class_path: Python 类路径 (e.g. "ocos.engines.reasoning_engine.ReasoningEngine")
        capabilities: 提供的能力 capability_id 列表
        singleton: 是否单例
        auto_load: 启动时自动加载
        version: 语义版本
        status: 提供者状态
        factory: 可选的实例化工厂函数
        metadata: 扩展元数据
    """
    provider_id: str
    name: str
    provider_type: ProviderType = ProviderType.ENGINE
    class_path: str = ""
    capabilities: list[str] = field(default_factory=list)
    singleton: bool = True
    auto_load: bool = True
    version: str = "1.0.0"
    status: ProviderStatus = ProviderStatus.ACTIVE
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc),
        compare=False,
    )

    @property
    def is_local(self) -> bool:
        return self.provider_type in (ProviderType.ENGINE, ProviderType.MODULE)

    @property
    def is_external(self) -> bool:
        return self.provider_type == ProviderType.EXTERNAL
