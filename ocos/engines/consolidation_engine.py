"""
Consolidation Engine — 信息合并/汇聚集引擎。

三层职责:
1. 将多个相关 Information 合并为更高层级的统一表示
2. 通过 KnowledgeABI 创建 Knowledge Candidate（桥接到知识平面）
3. 发射 INFORMATION_STATUS_CHANGED + KNOWLEDGE_CANDIDATE_PROPOSED 事件

执行流:
   consolidate(sources) → 校验 → 合并 → KnowledgeABI.create_unit()
                        → INFORMATION_STATUS_CHANGED (VALIDATED→DEPRECATED)
                        → KNOWLEDGE_CANDIDATE_PROPOSED
"""

from __future__ import annotations

import uuid
from typing import Any

from ocos.kernel.abi import Event, EventType
from ocos.knowledge.knowledge_abi import KnowledgeABI
from ocos.knowledge.knowledge_ontology import (
    KnowledgeLevel,
    KnowledgeStatus,
    KnowledgeUnit,
    get_elevation_targets,
)
from ocos.models.information import (
    InformationMetadata,
    InformationState,
    UniversalAddress,
)

from ocos.logging import get_logger

_SOURCE = "consolidation_engine"

logger = get_logger(__name__)

# 合并时允许的最小信息数量
_MIN_SOURCES = 2

# SemanticRole → KnowledgeLevel 映射（与 PromotionEngine 对齐）
_ROLE_TO_LEVEL: dict[str, KnowledgeLevel] = {
    "observation": KnowledgeLevel.OBSERVATION,
    "memory": KnowledgeLevel.EVIDENCE,
    "knowledge": KnowledgeLevel.PATTERN,
    "goal": KnowledgeLevel.EVIDENCE,
    "identity": KnowledgeLevel.EVIDENCE,
    "policy": KnowledgeLevel.PRINCIPLE,
    "decision": KnowledgeLevel.PATTERN,
}


def _infer_source_level(role_value: str) -> KnowledgeLevel:
    return _ROLE_TO_LEVEL.get(role_value, KnowledgeLevel.EVIDENCE)


class ConsolidationEngine:
    """信息合并引擎。

    将多个相关但分散的 Information 合并为一个更高层级的
    Knowledge Candidate。KnowledgeABI 为必选依赖（否则无法桥接知识平面）。
    EventBus 为可选依赖。
    """

    def __init__(
        self,
        knowledge_abi: KnowledgeABI | None = None,
        event_bus: Any | None = None,
    ) -> None:
        self._knowledge_abi = knowledge_abi
        self._event_bus = event_bus
        logger.debug("__init__ completed", component="consolidation_engine")

    # ── 合并 ────────────────────────────────────────────────────────────

    def consolidate(
        self,
        sources: list[InformationMetadata],
        target_level: KnowledgeLevel | None = None,
        owner: str = "system",
    ) -> tuple[bool, str]:
        """将多个源 Information 合并为 Knowledge Candidate。

        流程:
        1. 校验源信息数量和状态
        2. 推断目标层级
        3. 通过 KnowledgeABI 创建 KnowledgeUnit
        4. 发射事件

        Args:
            sources: 待合并的源信息列表（≥2 条）
            target_level: 目标知识层级（None=自动推断）
            owner: 知识单元所有者

        Returns:
            (success, message_or_knowledge_unit_id)
        """
        logger.info("consolidate", extra=dict(source_count=len(sources), owner=owner))
        # ── 校验 ──
        if len(sources) < _MIN_SOURCES:
            logger.error("consolidate failed: insufficient sources", extra=dict(
                actual=len(sources), min_required=_MIN_SOURCES,
            ))
            return (
                False,
                f"至少需要 {_MIN_SOURCES} 条源信息，当前 {len(sources)}",
            )

        # 推断目标层级
        if target_level is None:
            # 取最高源层级 +1
            current_max = KnowledgeLevel.OBSERVATION
            for s in sources:
                lvl = _infer_source_level(s.semantic_role.value)
                if lvl.value > current_max.value:
                    current_max = lvl
            targets = get_elevation_targets(current_max)
            if not targets:
                return (False, f"无法从 {current_max.value} 推断晋升目标")
            target_level = targets[0]

        # 准备合并内容
        content = self._merge_content(sources)

        # ── 桥接知识平面 ──
        knowledge_unit_id = ""
        if self._knowledge_abi is not None:
            ok, result = self._knowledge_abi.create_unit(
                level=target_level,
                content={
                    "source_ids": [s.address.id for s in sources],
                    "merged_content": content,
                    "consolidated_by": _SOURCE,
                },
                source=_SOURCE,
                owner=owner,
            )
            if not ok:
                return (False, f"知识单元创建失败: {result}")
            knowledge_unit_id = result

        # ── 发射事件 ──
        for src in sources:
            self._emit(
                EventType.INFORMATION_STATUS_CHANGED,
                {
                    "unit_id": src.address.id,
                    "from_state": src.state.value,
                    "to_state": InformationState.DEPRECATED.value,
                    "reason": f"consolidated_to:{knowledge_unit_id}",
                    "target_level": target_level.value,
                },
            )

        self._emit(
            EventType.KNOWLEDGE_CANDIDATE_PROPOSED,
            {
                "knowledge_unit_id": knowledge_unit_id,
                "source_ids": [s.address.id for s in sources],
                "level": target_level.value,
                "owner": owner,
                "source_count": len(sources),
            },
        )

        return (True, knowledge_unit_id or "consolidated")

    # ── 预合并 (propose candidate) ────────────────────────────────────────

    def propose_candidate(
        self,
        content: dict[str, Any],
        source_ids: list[str],
        target_level: KnowledgeLevel = KnowledgeLevel.EVIDENCE,
        owner: str = "system",
    ) -> tuple[bool, str]:
        """直接提交一个 Knowledge Candidate（不经过合并流程）。

        Args:
            content: 候选知识内容
            source_ids: 来源信息 ID 列表
            target_level: 目标知识层级
            owner: 知识单元所有者

        Returns:
            (success, knowledge_unit_id_or_error)
        """
        if len(source_ids) < _MIN_SOURCES:
            return (
                False,
                f"至少需要 {_MIN_SOURCES} 个来源引用，当前 {len(source_ids)}",
            )

        if not content:
            return (False, "候选知识内容不能为空")

        knowledge_unit_id = ""
        if self._knowledge_abi is not None:
            ok, result = self._knowledge_abi.create_unit(
                level=target_level,
                content={
                    "source_ids": source_ids,
                    "content": content,
                    "proposed_by": _SOURCE,
                },
                source=_SOURCE,
                owner=owner,
            )
            if not ok:
                return (False, f"知识单元创建失败: {result}")
            knowledge_unit_id = result

        self._emit(
            EventType.KNOWLEDGE_CANDIDATE_PROPOSED,
            {
                "knowledge_unit_id": knowledge_unit_id,
                "source_ids": source_ids,
                "level": target_level.value,
                "owner": owner,
            },
        )

        return (True, knowledge_unit_id or "proposed")

    # ── 内部方法 ──────────────────────────────────────────────────────────

    @staticmethod
    def _merge_content(sources: list[InformationMetadata]) -> dict[str, Any]:
        """将多个源信息合并为一个统一内容字典。"""
        merged: dict[str, Any] = {
            "_consolidation_id": uuid.uuid4().hex[:12],
            "_source_count": len(sources),
            "_sources": [],
        }
        for s in sources:
            merged["_sources"].append({
                "id": s.address.id,
                "role": s.semantic_role.value,
                "importance": s.importance,
                "tags": list(s.tags),
            })
        return merged

    def _emit(self, event_type: EventType, payload: dict[str, Any]) -> None:
        if self._event_bus is None:
            return
        event = Event(
            event_type=event_type,
            source=_SOURCE,
            payload=payload,
        )
        self._event_bus.publish(event, sync=True)

# ── Engine Manifest ──────────────────────────────────────────────────────────
from ocos.platform.engine_manifest import EngineManifest

__manifest__ = EngineManifest(
    engine_id="consolidation_engine",
    name="Consolidation Engine",
    version="1.0.0",
    engine_class="ocos.engines.consolidation_engine.ConsolidationEngine",
    capabilities=['consolidation'],
    dependencies=[],
    singleton=True,
    auto_load=True,
)
