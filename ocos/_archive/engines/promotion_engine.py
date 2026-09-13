"""
Promotion Engine — 信息晋升到知识平面的桥接引擎。

三层职责:
1. 晋升条件检查（委派给 PromotionRuleEngine）
2. Governance 审批流程集成（Pattern→Principle, Principle→Policy）
3. 知识平面桥接（通过 KnowledgeABI 创建 KnowledgeUnit）
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
    can_elevate,
)
from ocos.knowledge.promotion_rules import PromotionRuleEngine
from ocos.models.information import InformationMetadata, InformationState

from ocos.logging import get_logger

_SOURCE = "promotion_engine"

logger = get_logger(__name__)

# SemanticRole → KnowledgeLevel 映射表（信息层角色 → 知识层初始层级）
_ROLE_TO_LEVEL: dict[str, KnowledgeLevel] = {
    "observation": KnowledgeLevel.OBSERVATION,
    "memory": KnowledgeLevel.EVIDENCE,
    "knowledge": KnowledgeLevel.PATTERN,
    "goal": KnowledgeLevel.EVIDENCE,
    "identity": KnowledgeLevel.EVIDENCE,
    "policy": KnowledgeLevel.PRINCIPLE,
    "decision": KnowledgeLevel.PATTERN,
}

# 需要 Governance 审批的目标层级
_GOVERNANCE_GATED_LEVELS: set[KnowledgeLevel] = {
    KnowledgeLevel.PRINCIPLE,
    KnowledgeLevel.POLICY,
}


def _infer_source_level(role_value: str) -> KnowledgeLevel:
    """从 SemanticRole 推断信息当前在知识层级中的源层级。"""
    return _ROLE_TO_LEVEL.get(role_value, KnowledgeLevel.EVIDENCE)


class PromotionEngine:
    """信息晋升引擎。

    连接信息层（InformationState.VALIDATED→DEPRECATED）与知识层
    （KnowledgeUnit 创建），可选的 Governance 审批流程。

    依赖:
        rule_engine: 必选 — 触发条件 + 策略检查
        knowledge_abi: 可选 — 知识平面桥接
        event_bus: 可选 — 事件发射 + Governance 集成
    """

    def __init__(
        self,
        rule_engine: PromotionRuleEngine,
        knowledge_abi: KnowledgeABI | None = None,
        event_bus: Any | None = None,
    ) -> None:
        self._rule_engine = rule_engine
        self._rule_engine.load_default_policies()
        self._knowledge_abi = knowledge_abi
        self._event_bus = event_bus
        self._pending: dict[str, dict[str, Any]] = {}
        logger.debug("__init__ completed", component="promotion_engine")

    # ── 条件检查 ──────────────────────────────────────────────────────────

    def check_promotion(
        self,
        metadata: InformationMetadata,
        target_level: KnowledgeLevel | None = None,
        repetition_count: int = 0,
        confidence: float = 0.0,
        governance_approved: bool = False,
    ) -> tuple[bool, list[str]]:
        """检查信息是否满足晋升条件。"""
        logger.info("check_promotion", extra=dict(
            info_id=metadata.address.id if metadata.address else "unknown",
            target_level=target_level.value if target_level else "auto",
        ))
        errors: list[str] = []

        if metadata.state != InformationState.VALIDATED:
            errors.append(
                f"信息必须是 VALIDATED 状态，当前为 {metadata.state.value}"
            )
            return (False, errors)

        target = target_level
        source = _infer_source_level(metadata.semantic_role.value)
        if target is None:
            from ocos.knowledge.knowledge_ontology import (
                get_elevation_targets,
            )

            targets = get_elevation_targets(source)
            target = targets[0] if targets else None
            if target is None:
                errors.append(
                    f"无合法的晋升目标层级（从 {source.value}）"
                )
                return (False, errors)
        else:
            source = _infer_source_level(metadata.semantic_role.value)

        # 层级合法性检查
        if not can_elevate(source, target):
            errors.append(
                f"不可从 {source.value} 直接晋升到 {target.value}"
            )
            return (False, errors)

        # 触发条件 + 策略检查（委派给 PromotionRuleEngine）
        unit = KnowledgeUnit(
            level=source, status=KnowledgeStatus.ACTIVE
        )
        triggered, _ = self._rule_engine.check_trigger(
            unit,
            repetition_count=repetition_count,
            confidence=confidence,
        )
        if not triggered:
            errors.append("触发条件不满足")

        # Governance 检查
        if target in _GOVERNANCE_GATED_LEVELS and not governance_approved:
            errors.append("此晋升路径需要 Governance 审批")

        return (len(errors) == 0, errors)

    # ── 晋升执行 ──────────────────────────────────────────────────────────

    def promote(
        self,
        metadata: InformationMetadata,
        target_level: KnowledgeLevel | None = None,
        requestor: str = "system",
        repetition_count: int = 0,
        confidence: float = 0.0,
        governance_approved: bool = False,
    ) -> tuple[bool, str]:
        """执行信息晋升。

        流程:
        1. 校验信息状态（必须 ACTIVE）
        2. 若目标层级需 Governance 审批 → 创建立即审批请求，返回 promotion_id
        3. 检查触发条件
        4. 通过 KnowledgeABI 创建 KnowledgeUnit
        5. 发射 INFORMATION_STATUS_CHANGED + KNOWLEDGE_PROMOTED 事件

        Returns:
            (success, message_or_knowledge_unit_id)
        """
        if metadata.state != InformationState.VALIDATED:
            return (
                False,
                f"信息状态必须是 VALIDATED，当前为 {metadata.state.value}",
            )

        target = target_level
        source = _infer_source_level(metadata.semantic_role.value)
        if target is None:
            from ocos.knowledge.knowledge_ontology import (
                get_elevation_targets,
            )

            targets = get_elevation_targets(source)
            target = targets[0] if targets else None
            if target is None:
                return (
                    False,
                    f"无合法的晋升目标层级（从 {source.value}）",
                )

        # Governance 审批流程（异步：先返回请求 ID）
        if target in _GOVERNANCE_GATED_LEVELS and not governance_approved:
            promotion_id = uuid.uuid4().hex[:12]
            self._pending[promotion_id] = {
                "metadata": metadata,
                "target_level": target,
                "requestor": requestor,
                "repetition_count": repetition_count,
                "confidence": confidence,
            }
            self._emit(
                EventType.GOVERNANCE_APPROVAL_REQUESTED,
                {
                    "promotion_id": promotion_id,
                    "unit_id": metadata.address.id,
                    "target_level": target.value,
                    "requestor": requestor,
                },
            )
            return (False, f"需要 Governance 审批; promotion_id={promotion_id}")

        # 条件检查（含 governance_approved）
        ok, errors = self.check_promotion(
            metadata,
            target_level=target,
            repetition_count=repetition_count,
            confidence=confidence,
            governance_approved=governance_approved,
        )
        if not ok:
            return (False, "; ".join(errors))

        # 创建 KnowledgeUnit（桥接到知识平面）
        knowledge_unit_id = ""
        if self._knowledge_abi is not None:
            ok2, result = self._knowledge_abi.create_unit(
                level=target,
                content={
                    "source_address_id": metadata.address.id,
                    "semantic_role": metadata.semantic_role.value,
                    "importance": metadata.importance,
                },
                source=_SOURCE,
                owner=requestor,
            )
            if not ok2:
                return (False, f"知识单元创建失败: {result}")
            knowledge_unit_id = result

        # 发射状态变更事件
        self._emit(
            EventType.INFORMATION_STATUS_CHANGED,
            {
                "unit_id": metadata.address.id,
                "from_state": InformationState.VALIDATED.value,
                "to_state": InformationState.DEPRECATED.value,
                "target_level": target.value,
            },
        )

        # 发射知识晋升事件
        if knowledge_unit_id:
            self._emit(
                EventType.KNOWLEDGE_PROMOTED,
                {
                    "source_unit_id": metadata.address.id,
                    "knowledge_unit_id": knowledge_unit_id,
                    "level": target.value,
                    "requestor": requestor,
                },
            )

        return (True, knowledge_unit_id or "promoted")

    # ── Governance 回调 ───────────────────────────────────────────────────

    def approve_promotion(
        self, promotion_id: str, approved_by: str
    ) -> tuple[bool, str]:
        """批准待审批的晋升申请。"""
        if promotion_id not in self._pending:
            return (False, f"promotion_id '{promotion_id}' 不存在")

        entry = self._pending.pop(promotion_id)
        ok, msg = self.promote(
            entry["metadata"],
            target_level=entry["target_level"],
            requestor=entry["requestor"],
            repetition_count=entry.get("repetition_count", 0),
            confidence=entry.get("confidence", 0.0),
            governance_approved=True,
        )
        if ok:
            self._emit(
                EventType.GOVERNANCE_APPROVED,
                {
                    "promotion_id": promotion_id,
                    "approved_by": approved_by,
                    "knowledge_unit_id": msg,
                },
            )
        return (ok, msg)

    def reject_promotion(
        self, promotion_id: str, rejected_by: str, reason: str = ""
    ) -> tuple[bool, str]:
        """拒绝待审批的晋升申请。"""
        if promotion_id not in self._pending:
            return (False, f"promotion_id '{promotion_id}' 不存在")

        self._pending.pop(promotion_id)
        self._emit(
            EventType.GOVERNANCE_REJECTED,
            {
                "promotion_id": promotion_id,
                "rejected_by": rejected_by,
                "reason": reason,
            },
        )
        return (True, "已拒绝")

    # ── 内部方法 ──────────────────────────────────────────────────────────

    def _emit(
        self, event_type: EventType, payload: dict[str, Any]
    ) -> None:
        if self._event_bus is None:
            return
        event = Event(
            event_type=event_type, source=_SOURCE, payload=payload
        )
        self._event_bus.publish(event, sync=True)

# ── Engine Manifest ──────────────────────────────────────────────────────────
from ocos.platform.engine_manifest import EngineManifest

__manifest__ = EngineManifest(
    engine_id="promotion_engine",
    name="Promotion Engine",
    version="1.0.0",
    engine_class="ocos.engines.promotion_engine.PromotionEngine",
    capabilities=['promotion'],
    dependencies=[],
    singleton=True,
    auto_load=True,
)
