"""
M1 Knowledge Ownership — Registry 边界 + 读写矩阵。

KnowledgeRegistry 管理 KnowledgeUnit 的完整生命周期，包括：
- 所有权边界：每个单元属于一个 owner（模块名）
- 读写矩阵：按 owner + 层级控制的细粒度访问权限
- 可见性作用域：public / protected / private
"""

from __future__ import annotations

import dataclasses
import logging
from collections import defaultdict
from enum import Enum
from typing import Any

from ocos.knowledge.store.ontology import (
    KnowledgeLevel,
    KnowledgeStatus,
    KnowledgeUnit,
)

logger = logging.getLogger(__name__)


class AccessScope(str, Enum):
    """知识单元的可见性作用域。"""
    PUBLIC = "public"          # 任何模块可读
    PROTECTED = "protected"    # 仅相同 owner 或上层可读
    PRIVATE = "private"        # 仅 owner 可读


@dataclasses.dataclass(frozen=True)
class OwnershipEntry:
    """所有权条目：绑定 KnowledgeUnit 和它的所有者信息。"""
    unit: KnowledgeUnit
    owner: str                  # 拥有者模块名
    scope: AccessScope = AccessScope.PROTECTED
    tags: frozenset[str] = dataclasses.field(default_factory=frozenset)


class AccessMatrix:
    """读写矩阵：定义按 owner 和层级的访问权限。

    核心概念：
    - Read: 查询知识（列表、筛选）
    - Write: 创建、修改、删除知识
    - Elevate: 提升知识的层级
    """

    def __init__(self):
        # 格式: (owner, level) -> {"read": bool, "write": bool, "elevate": bool}
        self._permissions: dict[tuple[str, KnowledgeLevel], dict[str, bool]] = {}
        # 通配符: owner="*" 对所有模块生效
        self._wildcard_permissions: dict[KnowledgeLevel, dict[str, bool]] = {}

    def set_permission(
        self,
        owner: str,
        level: KnowledgeLevel,
        can_read: bool = True,
        can_write: bool = False,
        can_elevate: bool = False,
    ) -> None:
        """设置一个 owner 对特定层级的权限。"""
        self._permissions[(owner, level)] = {
            "read": can_read,
            "write": can_write,
            "elevate": can_elevate,
        }
        logger.debug("set_permission: owner=%s level=%s read=%s write=%s elevate=%s",
                     owner, level.value, can_read, can_write, can_elevate)

    def set_default_permissions(self, owner: str) -> None:
        """设置 owner 对所有层级的默认权限。
        
        默认规则：
        - 所有层级可读
        - 仅低层级（OBSERVATION, EVIDENCE）可写
        - 仅低层级可提升
        """
        for level in KnowledgeLevel:
            can_write = level in (
                KnowledgeLevel.OBSERVATION,
                KnowledgeLevel.EVIDENCE,
            )
            can_elevate = level in (
                KnowledgeLevel.OBSERVATION,
                KnowledgeLevel.EVIDENCE,
            )
            self.set_permission(owner, level, True, can_write, can_elevate)

    def set_wildcard_permission(
        self,
        level: KnowledgeLevel,
        can_read: bool = True,
        can_write: bool = False,
    ) -> None:
        """设置通配符权限（对所有未被专门设置的 owner 生效）。"""
        self._wildcard_permissions[level] = {"read": can_read, "write": can_write}
        logger.debug("set_wildcard_permission: level=%s read=%s write=%s",
                     level.value, can_read, can_write)

    def can_read(self, owner: str, level: KnowledgeLevel) -> bool:
        """owner 能否读取指定层级的已知数据。"""
        key = (owner, level)
        if key in self._permissions:
            return self._permissions[key].get("read", False)
        # 通配符回退
        if level in self._wildcard_permissions:
            return self._wildcard_permissions[level].get("read", False)
        return False

    def can_write(self, owner: str, level: KnowledgeLevel) -> bool:
        """owner 能否写入指定层级的知识。"""
        key = (owner, level)
        if key in self._permissions:
            return self._permissions[key].get("write", False)
        if level in self._wildcard_permissions:
            return self._wildcard_permissions[level].get("write", False)
        return False

    def can_elevate(self, owner: str, level: KnowledgeLevel) -> bool:
        """owner 能否提升指定层级的知识。"""
        key = (owner, level)
        if key in self._permissions:
            return self._permissions[key].get("elevate", False)
        return False

    def check_read_access(
        self,
        entry: OwnershipEntry,
        requestor: str,
    ) -> bool:
        """检查 requestor 是否有权读取该知识条目。"""
        # PUBLIC → 任何模块可读
        if entry.scope == AccessScope.PUBLIC:
            return True

        # PRIVATE → 仅 owner
        if entry.scope == AccessScope.PRIVATE:
            return entry.owner == requestor

        # PROTECTED → 相同 owner 或矩阵允许
        if entry.owner == requestor:
            return True
        return self.can_read(requestor, entry.unit.level)


# ── Registry ────────────────────────────────────────────────────────────────


class KnowledgeRegistry:
    """知识注册表：管理 KnowledgeUnit 的存储、查询和所有权验证。"""

    def __init__(self, access_matrix: AccessMatrix | None = None):
        self._entries: dict[str, OwnershipEntry] = {}  # unit_id -> entry
        self._access_matrix = access_matrix or AccessMatrix()

    # ── 写入操作 ──

    def register(
        self,
        unit: KnowledgeUnit,
        owner: str,
        scope: AccessScope = AccessScope.PROTECTED,
        tags: set[str] | None = None,
    ) -> tuple[bool, str]:
        """注册一个新知识单元。

        写入权限由 AccessMatrix 控制。
        Returns:
            (success, message_or_id)
        """
        if not self._access_matrix.can_write(owner, unit.level):
            logger.warning("register denied: owner=%s level=%s unit=%s",
                           owner, unit.level.value, unit.unit_id)
            return (
                False,
                f"'{owner}' 无权写入 {unit.level.value} 层级",
            )

        if unit.unit_id in self._entries:
            logger.warning("register failed: unit %s already exists", unit.unit_id)
            return (False, f"单元 {unit.unit_id} 已存在")

        entry = OwnershipEntry(
            unit=unit,
            owner=owner,
            scope=scope,
            tags=frozenset(tags or set()),
        )
        self._entries[unit.unit_id] = entry
        logger.info("register ok: unit=%s level=%s owner=%s scope=%s",
                    unit.unit_id, unit.level.value, owner, scope.value)
        return (True, unit.unit_id)

    def update(
        self,
        unit_id: str,
        requestor: str,
        **updates: Any,
    ) -> tuple[bool, str]:
        """更新一个已注册的知识单元。"""
        entry = self._entries.get(unit_id)
        if not entry:
            logger.warning("update failed: unit %s not found", unit_id)
            return (False, f"单元 {unit_id} 不存在")

        # 只有 owner 或有权写入该层级的模块可以更新
        if not self._can_modify(entry, requestor):
            logger.warning("update denied: requestor=%s unit=%s", requestor, unit_id)
            return (
                False,
                f"'{requestor}' 无权修改单元 {unit_id}",
            )

        # 重建单元（frozen dataclass 只能重建）
        new_unit = dataclasses.replace(
            entry.unit,
            **{k: v for k, v in updates.items() if hasattr(entry.unit, k)},
            version=entry.unit.version + 1,
        )
        new_entry = dataclasses.replace(entry, unit=new_unit)
        self._entries[unit_id] = new_entry
        logger.debug("update ok: unit=%s version=%d updates=%s",
                     unit_id, new_unit.version, set(updates.keys()))
        return (True, unit_id)

    def remove(self, unit_id: str, requestor: str) -> tuple[bool, str]:
        """删除一个知识单元。"""
        entry = self._entries.get(unit_id)
        if not entry:
            logger.warning("remove failed: unit %s not found", unit_id)
            return (False, f"单元 {unit_id} 不存在")

        if not self._can_modify(entry, requestor):
            logger.warning("remove denied: requestor=%s unit=%s", requestor, unit_id)
            return (False, f"'{requestor}' 无权删除单元 {unit_id}")

        del self._entries[unit_id]
        logger.info("remove ok: unit=%s", unit_id)
        return (True, unit_id)

    # ── 查询操作 ──

    def get(self, unit_id: str, requestor: str = "") -> OwnershipEntry | None:
        """获取指定单元（含权限过滤）。"""
        entry = self._entries.get(unit_id)
        if not entry:
            return None
        if requestor and not self._access_matrix.check_read_access(entry, requestor):
            return None
        return entry

    def get_by_level(
        self,
        level: KnowledgeLevel,
        requestor: str = "",
    ) -> list[OwnershipEntry]:
        """按层级查询。"""
        result = []
        for entry in self._entries.values():
            if entry.unit.level == level:
                if not requestor or self._access_matrix.check_read_access(
                    entry, requestor
                ):
                    result.append(entry)
        # 按时间排序（最近优先）
        result.sort(key=lambda e: e.unit.timestamp, reverse=True)
        return result

    def get_by_owner(
        self, owner: str, requestor: str = ""
    ) -> list[OwnershipEntry]:
        """按拥有者查询。"""
        result = []
        for entry in self._entries.values():
            if entry.owner == owner:
                if not requestor or self._access_matrix.check_read_access(
                    entry, requestor
                ):
                    result.append(entry)
        return result

    def get_by_status(
        self,
        status: KnowledgeStatus,
        requestor: str = "",
    ) -> list[OwnershipEntry]:
        """按状态查询。"""
        result = []
        for entry in self._entries.values():
            if entry.unit.status == status:
                if not requestor or self._access_matrix.check_read_access(
                    entry, requestor
                ):
                    result.append(entry)
        return result

    def search(
        self,
        requestor: str = "",
        *,
        level: KnowledgeLevel | None = None,
        owner: str | None = None,
        status: KnowledgeStatus | None = None,
        tags: set[str] | None = None,
    ) -> list[OwnershipEntry]:
        """多条件组合查询。"""
        result = []
        for entry in self._entries.values():
            # 权限过滤
            if requestor and not self._access_matrix.check_read_access(
                entry, requestor
            ):
                continue

            # 条件过滤
            if level and entry.unit.level != level:
                continue
            if owner and entry.owner != owner:
                continue
            if status and entry.unit.status != status:
                continue
            if tags and not tags.issubset(entry.tags):
                continue

            result.append(entry)
        logger.debug("search: found %d results (level=%s owner=%s status=%s)",
                     len(result), level.value if level else None,
                     owner, status.value if status else None)
        return result

    @property
    def total_count(self) -> int:
        """注册单元总数。"""
        return len(self._entries)

    def get_owners(self) -> set[str]:
        """返回所有注册过的 owner 列表。"""
        return {e.owner for e in self._entries.values()}

    def check_write(self, owner: str, level: KnowledgeLevel) -> bool:
        """检查 owner 对指定层级是否有写入权限。"""
        return self._access_matrix.can_write(owner, level)

    # ── 内部方法 ──

    def _can_modify(self, entry: OwnershipEntry, requestor: str) -> bool:
        """检查是否可以修改指定条目。"""
        if entry.owner == requestor:
            return True
        return self._access_matrix.can_write(requestor, entry.unit.level)
