"""
D1 Capability Registry — Tool/Plugin/Model 注册中心。

职责：
- 为 Tool、Plugin、Model 提供统一的注册/查询/注销接口
- 支持按类型、标签、名称搜索
- 同名能力注册时自动版本递增（不覆盖已有注册）

架构定位：
  CapabilityRegistry 是 Plugin Framework 的基础设施。
  Plugin Loader (D3) 在加载插件时会自动注册其 Capability。
  Sandbox (D2) 通过查询 Registry 获取插件的权限声明。
  Scheduler (B3) 通过 Registry 动态发现可执行的 Engine。

依赖：
  - ocos.kernel.abi (SCHEMA_VERSION)
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from ocos.kernel.abi import SCHEMA_VERSION
from ocos.logging import get_logger


logger = get_logger(__name__)


# ── 枚举 ─────────────────────────────────────────────────────────────────────

class CapabilityType(str, Enum):
    """能力类型。"""
    TOOL = "tool"
    PLUGIN = "plugin"
    MODEL = "model"


# ── 数据模型 ─────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class CapabilityDescriptor:
    """一个能力描述——注册中心的最小条目。

    不可变对象，注册后不可修改。
    如需更新描述或版本，应取消注册旧条目并重新注册。
    """

    capability_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    type: str = CapabilityType.TOOL.value
    name: str = ""
    description: str = ""
    tags: tuple[str, ...] = field(default_factory=tuple)
    version: str = "0.1.0"
    entry_point: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        """注册时验证字段有效性。"""
        _validate_type(self.type)

    @property
    def tag_set(self) -> set[str]:
        """返回标签集合，便于查询。"""
        return set(self.tags)


def _validate_type(type_value: str) -> None:
    """验证能力类型值。"""
    valid = {t.value for t in CapabilityType}
    if type_value not in valid:
        raise ValueError(
            f"无效能力类型 '{type_value}'。有效值: {', '.join(sorted(valid))}"
        )


# ── 注册中心 ─────────────────────────────────────────────────────────────────

class CapabilityRegistry:
    """Capability 注册中心。

    使用方式：
        registry = CapabilityRegistry()
        cid = registry.register(
            type=CapabilityType.PLUGIN,
            name="opentale-writer",
            description="OpenTale 写作引擎插件",
            tags=("creative-writing", "narrative"),
            version="1.0.0",
            entry_point="ocos.plugins.opentale.writer:WriterPlugin",
        )
        plugin = registry.get(cid)
        results = registry.query(type=CapabilityType.PLUGIN, tags=["narrative"])
    """

    def __init__(self) -> None:
        self._descriptors: dict[str, CapabilityDescriptor] = {}
        # name -> list of (capability_id, version) for version tracking
        self._name_index: dict[str, list[tuple[str, str]]] = {}
        logger.debug("CapabilityRegistry __init__ completed", component="capability_registry")

    # ── 属性 ────────────────────────────────────────────────────────────────

    @property
    def count(self) -> int:
        """当前注册的能力总数。"""
        return len(self._descriptors)

    # ── 注册 / 注销 ────────────────────────────────────────────────────────

    def register(
        self,
        descriptor: Optional[CapabilityDescriptor] = None,
        *,
        type: Optional[str] = None,
        name: str = "",
        description: str = "",
        tags: Optional[tuple[str, ...]] = None,
        version: str = "0.1.0",
        entry_point: str = "",
        metadata: Optional[dict[str, Any]] = None,
    ) -> str:
        """注册一个能力。

        支持两种调用方式：
        1. registry.register(descriptor=CapabilityDescriptor(...))
        2. registry.register(type=..., name=..., ...)

        同名注册时自动递增版本（不覆盖已有条目）。

        Returns:
            capability_id
        """
        if descriptor is not None:
            cd = descriptor
        else:
            cd = CapabilityDescriptor(
                type=type or CapabilityType.TOOL.value,
                name=name,
                description=description,
                tags=tuple(tags or ()),
                version=version,
                entry_point=entry_point,
                metadata=dict(metadata or {}),
            )

        # 检查同名已有条目，自动版本递增
        existing = self._name_index.get(cd.name, [])
        if existing:
            # 存在同名能力，如果版本相同则自动递增 patch
            for eid, eversion in existing:
                if eversion == cd.version:
                    parts = eversion.split(".")
                    try:
                        new_patch = int(parts[-1]) + 1
                        new_version = ".".join(parts[:-1] + [str(new_patch)])
                    except (ValueError, IndexError):
                        new_version = cd.version + ".1"
                    # 用新版本重新创建 descriptor
                    cd = CapabilityDescriptor(
                        capability_id=cd.capability_id,
                        type=cd.type,
                        name=cd.name,
                        description=cd.description,
                        tags=cd.tags,
                        version=new_version,
                        entry_point=cd.entry_point,
                        metadata=cd.metadata,
                        schema_version=cd.schema_version,
                    )
                    break

        self._descriptors[cd.capability_id] = cd
        self._name_index.setdefault(cd.name, []).append(
            (cd.capability_id, cd.version)
        )
        logger.info("Capability registered", component="capability_registry", capability_id=cd.capability_id, cap_name=cd.name, version=cd.version, type=cd.type)
        return cd.capability_id

    def unregister(self, capability_id: str) -> bool:
        """注销一个能力。

        Returns:
            True 注销成功，False 能力不存在
        """
        descriptor = self._descriptors.pop(capability_id, None)
        if descriptor is None:
            logger.warning("Capability not found for unregister", component="capability_registry", capability_id=capability_id)
            return False

        # 从名称索引中移除
        entries = self._name_index.get(descriptor.name, [])
        self._name_index[descriptor.name] = [
            (eid, ev) for eid, ev in entries if eid != capability_id
        ]
        if not self._name_index[descriptor.name]:
            del self._name_index[descriptor.name]

        logger.info("Capability unregistered", component="capability_registry", capability_id=capability_id, cap_name=descriptor.name)
        return True

    # ── 查询 ─────────────────────────────────────────────────────────────────

    def get(self, capability_id: str) -> Optional[CapabilityDescriptor]:
        """按 capability_id 获取能力。"""
        return self._descriptors.get(capability_id)

    def find_by_name(self, name: str) -> Optional[CapabilityDescriptor]:
        """按精确名称查找最新版本的能力。"""
        entries = self._name_index.get(name)
        if not entries:
            return None
        # 返回最新注册的（列表末尾）
        latest_id = entries[-1][0]
        return self._descriptors.get(latest_id)

    def get_all_versions(self, name: str) -> list[CapabilityDescriptor]:
        """获取指定名称的所有版本。"""
        entries = self._name_index.get(name, [])
        return [
            self._descriptors[eid]
            for eid, _ in entries
            if eid in self._descriptors
        ]

    def query(
        self,
        type: Optional[str] = None,
        tags: Optional[list[str]] = None,
        name_contains: Optional[str] = None,
    ) -> list[CapabilityDescriptor]:
        """按条件查询能力。

        Args:
            type: CapabilityType.value 过滤
            tags: 标签交集过滤（能力必须包含所有指定标签）
            name_contains: 名称子串匹配

        Returns:
            匹配的能力列表（按注册顺序）
        """
        results: list[CapabilityDescriptor] = []
        for cd in self._descriptors.values():
            # 类型过滤
            if type is not None and cd.type != type:
                continue
            # 标签过滤（交集）
            if tags is not None and tags:
                if not all(t in cd.tag_set for t in tags):
                    continue
            # 名称子串过滤
            if name_contains is not None and name_contains not in cd.name:
                continue

            results.append(cd)

        return results

    def list_by_type(self, type: str) -> list[CapabilityDescriptor]:
        """按类型列出能力。"""
        return self.query(type=type)

    def list_all_types(self) -> list[str]:
        """列出当前注册的所有能力类型。"""
        return sorted(set(cd.type for cd in self._descriptors.values()))

    # ── 管理 ─────────────────────────────────────────────────────────────────

    def reset(self) -> None:
        """清空注册中心。"""
        logger.info("Resetting capability registry", component="capability_registry")
        self._descriptors.clear()
        self._name_index.clear()
