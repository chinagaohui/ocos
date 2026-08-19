"""
M2 Knowledge ABI — 公共 API 接口。

KnowledgeABI 定义了知识平面对外（Context Manager、Attention Engine、
Policy Engine 等）的标准化公共 API。

ABI 版本: 1.0.0
"""

from __future__ import annotations

import logging
from typing import Any

from ocos.knowledge.store.lifecycle import KnowledgeLifecycle
from ocos.knowledge.store.ontology import (
    KnowledgeLevel,
    KnowledgeStatus,
    KnowledgeUnit,
)
from ocos.knowledge.store.registry import (
    AccessMatrix,
    AccessScope,
    KnowledgeRegistry,
)
from ocos.knowledge.process.promotion_rules import (
    PromotionRuleEngine,
    PromotionTriggerType,
)

logger = logging.getLogger(__name__)


ABI_VERSION = "1.0.0"


class KnowledgeABI:
    """知识平面公共 ABI。

    所有外部模块（引擎、运行时、插件）必须通过此接口操作知识，
    不能直接访问 KnowledgeRegistry 或 KnowledgeLifecycle 的内部。
    """

    def __init__(
        self,
        registry: KnowledgeRegistry,
        lifecycle: KnowledgeLifecycle,
        promotion_engine: PromotionRuleEngine | None = None,
    ):
        self._registry = registry
        self._lifecycle = lifecycle
        self._promotion = promotion_engine or PromotionRuleEngine()

    @property
    def abi_version(self) -> str:
        """返回 ABI 版本标识。"""
        return ABI_VERSION

    # ── 读取操作 ──

    def get_unit(
        self, unit_id: str, requestor: str = ""
    ) -> dict[str, Any] | None:
        """获取知识单元信息（安全过滤后的公共视图）。"""
        entry = self._registry.get(unit_id, requestor=requestor)
        if not entry:
            logger.debug("get_unit: %s not found (requestor=%s)", unit_id, requestor)
            return None
        view = self._to_public_view(entry)
        logger.debug("get_unit: %s found (requestor=%s)", unit_id, requestor)
        return view

    def query(
        self,
        requestor: str = "",
        *,
        level: KnowledgeLevel | None = None,
        status: KnowledgeStatus | None = None,
        owner: str | None = None,
        tags: set[str] | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """多条件查询知识单元。"""
        entries = self._registry.search(
            requestor=requestor,
            level=level,
            status=status,
            owner=owner,
            tags=tags,
        )
        results = [self._to_public_view(e) for e in entries[:limit]]
        logger.debug("query: found %d results (limit=%d)", len(results), limit)
        return results

    def get_by_level(
        self,
        level: KnowledgeLevel,
        requestor: str = "",
    ) -> list[dict[str, Any]]:
        """按层级查询。"""
        entries = self._registry.get_by_level(level, requestor=requestor)
        results = [self._to_public_view(e) for e in entries]
        logger.debug("get_by_level: level=%s count=%d", level.value, len(results))
        return results

    def get_active_units(
        self, requestor: str = ""
    ) -> list[dict[str, Any]]:
        """获取所有 ACTIVE 状态单元的公共视图。"""
        entries = self._registry.get_by_status(
            KnowledgeStatus.ACTIVE, requestor=requestor
        )
        results = [self._to_public_view(e) for e in entries]
        logger.debug("get_active_units: count=%d", len(results))
        return results

    # ── 写入操作 ──

    def submit_observation(
        self,
        content: dict[str, Any],
        source: str,
        owner: str,
    ) -> tuple[bool, str]:
        """提交一条 Observation 级别的知识（最常用的写入入口）。"""
        unit = KnowledgeUnit(
            level=KnowledgeLevel.OBSERVATION,
            status=KnowledgeStatus.CANDIDATE,
            content=content,
            source=source,
        )
        ok, msg = self._registry.register(unit, owner=owner)
        logger.info("submit_observation: owner=%s source=%s ok=%s id=%s",
                    owner, source, ok, msg)
        return ok, msg

    def create_unit(
        self,
        level: KnowledgeLevel,
        content: dict[str, Any],
        source: str,
        owner: str,
        scope: AccessScope = AccessScope.PROTECTED,
    ) -> tuple[bool, str]:
        """通用创建知识单元入口。"""
        unit = KnowledgeUnit(
            level=level,
            status=KnowledgeStatus.CANDIDATE,
            content=content,
            source=source,
        )
        ok, msg = self._registry.register(unit, owner=owner, scope=scope)
        logger.info("create_unit: level=%s owner=%s ok=%s id=%s",
                    level.value, owner, ok, msg)
        return ok, msg

    def update_unit(
        self,
        unit_id: str,
        requestor: str,
        **content_updates: Any,
    ) -> tuple[bool, str]:
        """更新知识单元内容。"""
        ok, msg = self._registry.update(unit_id, requestor, **content_updates)
        logger.debug("update_unit: %s requestor=%s ok=%s", unit_id, requestor, ok)
        return ok, msg

    # ── 状态机操作 ──

    def verify(self, unit_id: str, verified_by: str) -> tuple[bool, str]:
        """验证知识单元。"""
        ok, msg = self._lifecycle.verify(unit_id, verified_by)
        logger.info("verify: %s by=%s ok=%s", unit_id, verified_by, ok)
        return ok, msg

    def activate(self, unit_id: str, activated_by: str) -> tuple[bool, str]:
        """激活知识单元。"""
        ok, msg = self._lifecycle.activate(unit_id, activated_by)
        logger.info("activate: %s by=%s ok=%s", unit_id, activated_by, ok)
        return ok, msg

    def deprecate(
        self, unit_id: str, deprecated_by: str
    ) -> tuple[bool, str]:
        """弃用知识单元。"""
        ok, msg = self._lifecycle.deprecate(unit_id, deprecated_by)
        logger.info("deprecate: %s by=%s ok=%s", unit_id, deprecated_by, ok)
        return ok, msg

    def archive(
        self, unit_id: str, archived_by: str
    ) -> tuple[bool, str]:
        """归档知识单元。"""
        ok, msg = self._lifecycle.archive(unit_id, archived_by)
        logger.info("archive: %s by=%s ok=%s", unit_id, archived_by, ok)
        return ok, msg

    # ── 提升操作 ──

    def can_elevate(
        self,
        unit_id: str,
        target_level: KnowledgeLevel,
        requestor: str = "",
    ) -> tuple[bool, list[str]]:
        """检查是否有资格提升知识单元。"""
        entry = self._registry.get(unit_id, requestor=requestor)
        if not entry:
            logger.debug("can_elevate: %s not found (requestor=%s)", unit_id, requestor)
            return (False, ["单元不存在或无权访问"])
        return self._promotion.can_promote(
            entry.unit, target_level, source=requestor
        )

    def elevate(
        self,
        unit_id: str,
        target_level: KnowledgeLevel,
        requestor: str,
        reason: str = "",
    ) -> tuple[bool, str]:
        """提升知识单元到目标层级。

        自动完成：新层级创建、父关联、版本递增。
        """
        entry = self._registry.get(unit_id, requestor=requestor)
        if not entry:
            logger.warning("elevate failed: %s not found (requestor=%s)", unit_id, requestor)
            return (False, "单元不存在或无权访问")

        # 检查提升合法性
        ok, errors = self._promotion.can_promote(
            entry.unit, target_level, source=requestor
        )
        if not ok:
            logger.warning("elevate can_promote denied: %s -> %s errors=%s",
                          unit_id, target_level.value, errors)
            return (False, "; ".join(errors))

        # 创建提升后的新单元（frozen dataclass 只能新建）
        new_unit = KnowledgeUnit(
            level=target_level,
            status=KnowledgeStatus.CANDIDATE,  # 新层级从 candidate 开始
            content=entry.unit.content,
            source=entry.unit.source,
            version=entry.unit.version + 1,
            parent_id=unit_id,
        )
        ok, msg = self._registry.register(
            new_unit, owner=entry.owner, scope=AccessScope.PROTECTED
        )
        logger.info("elevate: %s -> %s (%s) by=%s ok=%s",
                    unit_id, target_level.value, msg, requestor, ok)
        return ok, msg

    # ── 审计操作 ──

    def get_status_history(
        self, unit_id: str | None = None
    ) -> list[dict[str, Any]]:
        """获取状态变更历史。"""
        records = self._lifecycle.get_status_history(unit_id)
        return [
            {
                "unit_id": r.unit_id,
                "from": r.from_status.value,
                "to": r.to_status.value,
                "by": r.changed_by,
                "reason": r.reason,
                "timestamp": r.timestamp,
            }
            for r in records
        ]

    # ── 工具 ──

    @property
    def total_knowledge_units(self) -> int:
        """知识单元总数。"""
        return self._registry.total_count

    def get_owners(self) -> list[str]:
        """返回所有知识拥有者列表。"""
        return sorted(self._registry.get_owners())

    @staticmethod
    def _to_public_view(entry) -> dict[str, Any]:
        """将内部 OwnershipEntry 转换为公共可序列化视图。"""
        return {
            "unit_id": entry.unit.unit_id,
            "level": entry.unit.level.value,
            "status": entry.unit.status.value,
            "content": entry.unit.content,
            "source": entry.unit.source,
            "owner": entry.owner,
            "scope": entry.scope.value,
            "version": entry.unit.version,
            "parent_id": entry.unit.parent_id,
            "tags": sorted(entry.tags),
            "timestamp": entry.unit.timestamp,
        }
